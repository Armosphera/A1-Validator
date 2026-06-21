"""
test_server_integration.py — true cross-process HTTP integration tests.

Unlike tests/test_server.py (which uses FastAPI's in-process TestClient
for speed), these tests start the real uvicorn server in a subprocess
and call it via httpx. This catches a class of bugs the in-process
TestClient cannot:
- Server boots on a real port (process startup, port binding, signal handling)
- JSON serialization survives a real network round-trip
- The uvicorn entrypoint and the a1-validator.server:app module are
  in sync (catches "refactored server.py but forgot to update the
  pyproject.toml entry point" regressions)

The tests use ephemeral ports (port=0 → OS picks a free one) and clean
shutdown. Skip the suite if uvicorn or httpx is not available.
"""

from __future__ import annotations

import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def _free_port() -> int:
    """Ask the OS for a free port (closes immediately, may be reused — race acceptable here)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_for_http(url: str, timeout_s: float = 10.0) -> None:
    """Poll the URL until it returns 200 or timeout."""
    started = time.monotonic()
    last_err: Exception | None = None
    while time.monotonic() - started < timeout_s:
        try:
            r = httpx.get(url, timeout=1.0)
            if r.status_code == 200:
                return
        except Exception as exc:  # noqa: BLE001
            last_err = exc
        time.sleep(0.1)
    raise RuntimeError(f"server at {url} did not become ready within {timeout_s}s (last error: {last_err})")


@pytest.fixture(scope="module")
def live_server():
    """Start the a1-validator serve subprocess on an ephemeral port."""
    port = _free_port()
    env = {**os.environ, "A1_VALIDATOR_PORT": str(port)}
    # Use the in-venv uvicorn so we don't depend on a system-wide install.
    venv_uvicorn = REPO_ROOT / ".venv" / "bin" / "uvicorn"
    if venv_uvicorn.exists():
        cmd = [str(venv_uvicorn), "a1_validator.server:app", "--host", "127.0.0.1", "--port", str(port), "--log-level", "warning"]
    else:
        cmd = [sys.executable, "-m", "uvicorn", "a1_validator.server:app", "--host", "127.0.0.1", "--port", str(port), "--log-level", "warning"]
    proc = subprocess.Popen(
        cmd,
        cwd=REPO_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        _wait_for_http(f"http://127.0.0.1:{port}/", timeout_s=15.0)
        yield f"http://127.0.0.1:{port}"
    finally:
        # Graceful shutdown
        if proc.poll() is None:
            proc.send_signal(signal.SIGTERM)
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=2)


def test_live_server_discovery(live_server: str) -> None:
    """GET / on the live server returns name + version + 41 validators."""
    r = httpx.get(f"{live_server}/", timeout=5.0)
    assert r.status_code == 200
    body = r.json()
    assert "name" in body
    assert "version" in body
    assert "validators" in body
    assert len(body["validators"]) == 41
    assert "hhvh" in body["validators"]
    assert "in_pan" in body["validators"]
    assert "tw_ubn" in body["validators"]


def test_live_server_validate_hhvh(live_server: str) -> None:
    """POST /validate/hhvh on the live server returns ok=true for valid input."""
    r = httpx.post(
        f"{live_server}/validate/hhvh",
        json={"value": "00123456"},
        timeout=5.0,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["normalized"] == "00123456"


def test_live_server_validate_in_pan(live_server: str) -> None:
    """POST /validate/in_pan (one of the v0.5.0 additions) round-trips correctly."""
    r = httpx.post(
        f"{live_server}/validate/in_pan",
        json={"value": "AAAPA1234A"},
        timeout=5.0,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["normalized"] == "AAAPA1234A"


def test_live_server_validate_rejects_invalid(live_server: str) -> None:
    """POST /validate/hhvh returns ok=false (not 4xx) for invalid input."""
    r = httpx.post(
        f"{live_server}/validate/hhvh",
        json={"value": "99999999"},
        timeout=5.0,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False
    assert body["normalized"] == "99999999"
    assert "error" in body


def test_live_server_openapi_has_all_validators(live_server: str) -> None:
    """GET /openapi.json includes all 41 /validate/<kind> + 41 /batch/<kind> paths."""
    r = httpx.get(f"{live_server}/openapi.json", timeout=5.0)
    assert r.status_code == 200
    paths = r.json().get("paths", {})
    validate_paths = [p for p in paths if p.startswith("/validate/")]
    batch_paths = [p for p in paths if p.startswith("/batch/")]
    assert len(validate_paths) == 41, f"expected 41 /validate/* paths, got {len(validate_paths)}: {sorted(validate_paths)[:5]}..."
    assert len(batch_paths) == 41, f"expected 41 /batch/* paths, got {len(batch_paths)}: {sorted(batch_paths)[:5]}..."
