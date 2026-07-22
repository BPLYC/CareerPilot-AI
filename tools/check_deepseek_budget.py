"""Budget guard for real DeepSeek API verification runs.

Run this before and after every real API verification. It refuses to
authorise a run when the account balance has fallen to the configured
floor, so an unattended optimization loop cannot drain the account.

Usage:
    python tools/check_deepseek_budget.py            # check against the floor
    python tools/check_deepseek_budget.py --quiet    # print the balance only

Exit codes:
    0  balance is above the floor; a real API run is authorised
    1  balance is at or below the floor; use deterministic fallback instead
    2  the balance could not be read (missing key, network failure)
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

# Floor agreed with the repository owner on 2026-07-23. Below this, the
# unattended loop stops making real API calls and verifies offline instead.
DEFAULT_FLOOR_CNY = 2.00


def load_env(path: str = ".env") -> dict:
    """Read KEY=VALUE pairs from a .env file without extra dependencies."""

    values = {}
    if not os.path.exists(path):
        return values
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def read_balance_cny() -> float:
    """Return the DeepSeek CNY balance, or raise RuntimeError."""

    env = load_env()
    api_key = os.environ.get("DEEPSEEK_API_KEY") or env.get("DEEPSEEK_API_KEY", "")
    base_url = os.environ.get("DEEPSEEK_BASE_URL") or env.get("DEEPSEEK_BASE_URL", "")
    if not api_key or not base_url:
        raise RuntimeError("DEEPSEEK_API_KEY or DEEPSEEK_BASE_URL is not configured.")

    request = urllib.request.Request(
        base_url.rstrip("/") + "/user/balance",
        headers={"Authorization": f"Bearer {api_key}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.load(response)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Could not read the DeepSeek balance: {exc}") from exc

    for info in payload.get("balance_infos", []):
        if info.get("currency") == "CNY":
            return float(info["total_balance"])
    raise RuntimeError(f"No CNY balance in the DeepSeek response: {payload}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--floor", type=float, default=DEFAULT_FLOOR_CNY)
    parser.add_argument("--quiet", action="store_true", help="Print the balance and exit 0.")
    args = parser.parse_args()

    try:
        balance = read_balance_cny()
    except RuntimeError as exc:
        print(f"BUDGET UNKNOWN: {exc}", file=sys.stderr)
        return 2

    if args.quiet:
        print(f"{balance:.2f}")
        return 0

    if balance <= args.floor:
        print(
            f"BUDGET EXHAUSTED: balance {balance:.2f} CNY is at or below the "
            f"{args.floor:.2f} CNY floor. Verify with the deterministic "
            f"fallback path and note in the log that this step was not "
            f"confirmed against the real API."
        )
        return 1

    print(f"BUDGET OK: balance {balance:.2f} CNY, floor {args.floor:.2f} CNY, "
          f"{balance - args.floor:.2f} CNY available for verification runs.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
