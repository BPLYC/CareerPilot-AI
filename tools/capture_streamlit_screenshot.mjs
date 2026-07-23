import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { mkdir, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = dirname(fileURLToPath(import.meta.url));
const repo = resolve(scriptDir, "..");

// A git worktree has no .venv of its own, so look in the main checkout too
// rather than failing with a bare ENOENT on a path that was never going to
// exist. PYTHON overrides both.
function findPython() {
  if (process.env.PYTHON) return process.env.PYTHON;
  const candidates = [
    resolve(repo, ".venv/Scripts/python.exe"),
    resolve(repo, ".venv/bin/python"),
    resolve(repo, "../../../.venv/Scripts/python.exe"),
    resolve(repo, "../../../.venv/bin/python"),
  ];
  const found = candidates.find((path) => existsSync(path));
  if (found) return found;
  throw new Error(
    `No project virtual environment found. Looked in:\n  ${candidates.join("\n  ")}\n` +
      "Set PYTHON to the interpreter that has streamlit installed."
  );
}

const python = findPython();
const chrome = process.env.CHROME_PATH ?? "C:/Program Files/Google/Chrome/Application/chrome.exe";
const homeOut = resolve(repo, "docs/assets/careerpilot-home.png");
const sampleOut = resolve(repo, "docs/assets/careerpilot-sample-input.png");
const reportOut = resolve(repo, "docs/assets/careerpilot-match-report.png");
const compareOut = resolve(repo, "docs/assets/careerpilot-compare-jobs.png");
const chromeProfile = resolve(tmpdir(), "careerpilot-chrome-profile");

// Screenshots are committed artifacts, so they default to the deterministic
// path: regenerating them produces the same images, costs nothing, and cannot
// freeze a one-off bad model response into the README. The live score for the
// sample data has been observed anywhere between 3 and 65 on identical input.
// Pass --live to capture real model output instead.
const live = process.argv.includes("--live");

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function waitForHttp(url, timeoutMs = 90000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    try {
      const res = await fetch(url);
      if (res.ok) return;
    } catch {}
    await sleep(1000);
  }
  throw new Error(`Timed out waiting for ${url}`);
}

async function connectPage(port = 9222, timeoutMs = 30000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    try {
      const pages = await fetch(`http://127.0.0.1:${port}/json/list`).then((r) => r.json());
      const page = pages.find((p) => p.type === "page" && p.webSocketDebuggerUrl);
      if (page) return new WebSocket(page.webSocketDebuggerUrl);
    } catch {}
    await sleep(500);
  }
  throw new Error("Timed out waiting for Chrome DevTools page");
}

function makeCdp(ws) {
  let id = 0;
  const pending = new Map();
  ws.addEventListener("message", (event) => {
    const msg = JSON.parse(event.data);
    if (msg.id && pending.has(msg.id)) {
      const { resolve, reject } = pending.get(msg.id);
      pending.delete(msg.id);
      msg.error ? reject(new Error(JSON.stringify(msg.error))) : resolve(msg.result);
    }
  });
  return (method, params = {}) =>
    new Promise((resolve, reject) => {
      const callId = ++id;
      pending.set(callId, { resolve, reject });
      ws.send(JSON.stringify({ id: callId, method, params }));
    });
}

async function waitForRenderedText(cdp, timeoutMs = 120000) {
  const start = Date.now();
  let lastText = "";
  while (Date.now() - start < timeoutMs) {
    const result = await cdp("Runtime.evaluate", {
      expression: "document.body.innerText",
      returnByValue: true,
    });
    lastText = result.result.value || "";
    if (lastText.includes("CareerPilot AI") && lastText.includes("Load Sample Data")) {
      return;
    }
    await sleep(1000);
  }
  throw new Error(`Timed out waiting for app text. Last text: ${lastText.slice(0, 300)}`);
}

async function waitForSampleData(cdp, timeoutMs = 30000) {
  const start = Date.now();
  let lastValue = "";
  while (Date.now() - start < timeoutMs) {
    const result = await cdp("Runtime.evaluate", {
      expression: "Array.from(document.querySelectorAll('textarea')).map((el) => el.value).join('\\n')",
      returnByValue: true,
    });
    lastValue = result.result.value || "";
    if (lastValue.includes("Alex Chen") && lastValue.includes("AI Intern")) {
      return;
    }
    await sleep(1000);
  }
  throw new Error(`Timed out waiting for sample data. Last textarea value: ${lastValue.slice(0, 300)}`);
}

async function clickByText(cdp, selector, text) {
  // Dispatch real mouse events at the element's centre rather than calling
  // .click(). Streamlit's primary button ignores a programmatic click: the
  // React handler is bound to pointer events, so the script would carry on
  // believing it had started an analysis that never ran.
  const box = await cdp("Runtime.evaluate", {
    expression: `(() => {
      const el = Array.from(document.querySelectorAll(${JSON.stringify(selector)}))
        .find((node) => node.innerText.trim().includes(${JSON.stringify(text)}));
      if (!el) return null;
      el.scrollIntoView({ block: "center" });
      const r = el.getBoundingClientRect();
      return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
    })()`,
    returnByValue: true,
  });
  const point = box.result.value;
  if (!point) throw new Error(`No ${selector} found matching "${text}"`);

  for (const type of ["mousePressed", "mouseReleased"]) {
    await cdp("Input.dispatchMouseEvent", {
      type,
      x: point.x,
      y: point.y,
      button: "left",
      clickCount: 1,
    });
  }
}

async function waitForText(cdp, needles, timeoutMs = 180000) {
  const wanted = Array.isArray(needles) ? needles : [needles];
  const start = Date.now();
  let lastText = "";
  while (Date.now() - start < timeoutMs) {
    const result = await cdp("Runtime.evaluate", {
      expression: "document.body.innerText",
      returnByValue: true,
    });
    lastText = result.result.value || "";
    if (wanted.some((needle) => lastText.includes(needle))) return;
    await sleep(1500);
  }
  if (process.env.DEBUG_CAPTURE) {
    await captureViewport(cdp, resolve(tmpdir(), "careerpilot-capture-failure.png"));
  }
  throw new Error(`Timed out waiting for ${wanted.join(" or ")}. Last text: ${lastText.slice(0, 600)}`);
}

async function captureViewport(cdp, outputPath) {
  const shot = await cdp("Page.captureScreenshot", {
    format: "png",
    fromSurface: true,
    captureBeyondViewport: false,
  });
  await writeFile(outputPath, Buffer.from(shot.data, "base64"));
  console.log(`Saved ${outputPath}`);
}

async function cleanupChromeProfile() {
  await sleep(1000);
  try {
    await rm(chromeProfile, { recursive: true, force: true });
  } catch {
    // Chrome can hold SQLite journal files briefly after exit. The profile is in C:/tmp
    // and can be removed by a later run, so cleanup should not fail the capture.
  }
}

await mkdir(resolve(repo, "docs/assets"), { recursive: true });
await cleanupChromeProfile();

if (!live) {
  // Otherwise the screenshot shows whatever a previous run left cached,
  // including output from a live run, and stops being reproducible.
  await rm(resolve(repo, "outputs/cache"), { recursive: true, force: true });
}

const streamlitEnv = { ...process.env };
if (!live) {
  // Set to empty rather than deleted. provider_config calls load_dotenv() at
  // import, which finds .env up the directory tree and would restore anything
  // merely absent; load_dotenv does not override a variable that is already
  // present, even when its value is empty.
  streamlitEnv.DEEPSEEK_API_KEY = "";
  streamlitEnv.DEEPSEEK_MODEL = "";
  streamlitEnv.CAREERPILOT_DISABLE_VECTORSTORE = "1";
}
console.log(live ? "Mode: LIVE (real model calls)" : "Mode: deterministic (pass --live for real calls)");

const streamlit = spawn(python, [
  "-m",
  "streamlit",
  "run",
  `${repo}/app.py`,
  "--server.address",
  "127.0.0.1",
  "--server.port",
  "8501",
  "--server.headless",
  "true",
], { cwd: repo, stdio: "inherit", env: streamlitEnv });

let browser;
try {
  await waitForHttp("http://127.0.0.1:8501");
  browser = spawn(chrome, [
    "--headless",
    "--disable-gpu",
    "--no-sandbox",
    "--hide-scrollbars",
    "--remote-debugging-port=9222",
    `--user-data-dir=${chromeProfile}`,
    "--window-size=1440,1200",
    "http://127.0.0.1:8501",
  ], { stdio: "ignore" });

  const ws = await connectPage();
  await new Promise((resolve) => ws.addEventListener("open", resolve, { once: true }));
  const cdp = makeCdp(ws);
  await cdp("Page.enable");
  await cdp("Runtime.enable");
  await cdp("Emulation.setDeviceMetricsOverride", {
    width: 1440,
    height: 1200,
    deviceScaleFactor: 1,
    mobile: false,
  });
  await waitForRenderedText(cdp);
  await captureViewport(cdp, homeOut);
  await clickByText(cdp, "button", "Load Sample Data");
  await waitForSampleData(cdp);
  await captureViewport(cdp, sampleOut);

  // Run one analysis so the result screenshots show real output, including the
  // Markdown export button, which only exists once there is a report.
  await clickByText(cdp, "button", "Run CareerPilot Analysis");
  // run_analysis returns before creating the status widget when the result is
  // cached, so waiting only for "Analysis complete" hangs on any repeat run.
  await waitForText(cdp, ["Analysis complete", "Loaded cached analysis"]);
  await clickByText(cdp, "button[role='tab']", "Match Report");
  await waitForText(cdp, "Download full report");
  await sleep(1500);
  await captureViewport(cdp, reportOut);

  // Each button click reruns the script and Streamlit returns to the first
  // tab, so the tab has to be reselected after every interaction.
  await clickByText(cdp, "button[role='tab']", "Compare Jobs");
  await waitForText(cdp, "Compare one resume against several roles");
  await clickByText(cdp, "button", "Load all sample JDs");
  await sleep(3000);
  await clickByText(cdp, "button[role='tab']", "Compare Jobs");
  await sleep(1000);
  await clickByText(cdp, "button", "Compare roles");
  await sleep(3000);
  await clickByText(cdp, "button[role='tab']", "Compare Jobs");
  await waitForText(cdp, "Best fit:");
  await sleep(1500);
  await captureViewport(cdp, compareOut);

  ws.close();
} finally {
  if (browser) browser.kill();
  streamlit.kill();
  await cleanupChromeProfile();
}
