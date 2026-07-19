from __future__ import annotations

import ast
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE_URL = "http://127.0.0.1:8000"


def run_step(label: str, command: list[str]) -> None:
    print(f"[build] {label}...")
    subprocess.run(command, cwd=ROOT, check=True)



def check_python_syntax() -> None:
    print("[build] syntax check...")
    for source_root in (ROOT / "app", ROOT / "tests"):
        for path in source_root.rglob("*.py"):
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

def check_http(path: str, timeout: float = 3.0) -> dict:
    url = f"{BASE_URL}{path}"
    with urllib.request.urlopen(url, timeout=timeout) as response:
        payload = response.read().decode("utf-8")
        return json.loads(payload)


def check_health_and_metrics() -> None:
    print("[build] api health check...")
    health = check_http("/health")
    if health.get("status") != "ok":
        raise RuntimeError(f"health check failed: {health}")
    print(f"[build] health ok: {health.get('service')} {health.get('version')}")

    print("[build] api metrics check...")
    metrics = check_http("/metrics")
    if not isinstance(metrics, dict) or not metrics:
        raise RuntimeError("metrics check failed: empty response")
    for key in ("service_status", "api_version"):
        if key not in metrics:
            raise RuntimeError(f"metrics check failed: missing {key}")
    print(f"[build] metrics ok: {sorted(metrics.keys())}")


def wait_for_api(max_seconds: int = 10) -> None:
    print(f"[build] waiting for api on {BASE_URL}...")
    deadline = time.time() + max_seconds
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            check_http("/health", timeout=1.0)
            return
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            time.sleep(0.5)
    raise RuntimeError(f"api not ready: {last_error}")


def main() -> int:
    check_python_syntax()
    run_step("dependency check", [sys.executable, "scripts/check_deps.py"])
    run_step("unit and contract tests", [sys.executable, "-m", "pytest"])

    if "--smoke-online" in sys.argv:
        wait_for_api()
        check_health_and_metrics()
    else:
        print("[build] skipped online API smoke check; pass --smoke-online after starting Uvicorn to enable it")

    print("[build] all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
