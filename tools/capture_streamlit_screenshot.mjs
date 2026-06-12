import { spawn } from "node:child_process";
import { mkdir, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = dirname(fileURLToPath(import.meta.url));
const repo = resolve(scriptDir, "..");
const python = process.env.PYTHON ?? resolve(repo, ".venv/Scripts/python.exe");
const chrome = process.env.CHROME_PATH ?? "C:/Program Files/Google/Chrome/Application/chrome.exe";
const homeOut = resolve(repo, "docs/assets/careerpilot-home.png");
const sampleOut = resolve(repo, "docs/assets/careerpilot-sample-input.png");
const chromeProfile = resolve(tmpdir(), "careerpilot-chrome-profile");

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
], { cwd: repo, stdio: "inherit" });

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
  await cdp("Runtime.evaluate", {
    expression: "Array.from(document.querySelectorAll('button')).find((el) => el.innerText.includes('Load Sample Data'))?.click()",
  });
  await waitForSampleData(cdp);
  await captureViewport(cdp, sampleOut);
  ws.close();
} finally {
  if (browser) browser.kill();
  streamlit.kill();
  await cleanupChromeProfile();
}
