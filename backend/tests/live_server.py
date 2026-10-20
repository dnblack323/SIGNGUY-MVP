"""Disposable backend server for HTTP tests and scripts.

Tests that need a real HTTP server never read a base URL from the environment. They start
this server, which runs the app against the current run's isolated database on a random
loopback port. An externally supplied ``SIGNGUY_API_BASE_URL`` (the old way of pointing at
the developer's running app) is refused outright.
"""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from app.core.test_isolation import UnsafeTestTargetError, validate_test_api_url, validate_test_target

BACKEND_DIR = Path(__file__).resolve().parents[1]
_RUNNING: "LiveServer | None" = None


class LiveServer:
    def __init__(self, proc: subprocess.Popen, port: int) -> None:
        self.proc, self.port = proc, port
        self.base_url = f"http://127.0.0.1:{port}"

    def stop(self) -> None:
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                self.proc.kill()


def start_server() -> LiveServer:
    validate_test_target(os.environ)
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "server:app", "--host", "127.0.0.1", "--port", str(port), "--log-level", "warning"],
        # Live-HTTP tests exercise the dev-mode auth/reset flows (dev-login, dev reset token); that is
        # safe here because the server only sees the run's disposable database and blanked integrations.
        cwd=BACKEND_DIR, env={**os.environ, "ENV": "development"},
    )
    server = LiveServer(proc, port)
    validate_test_api_url(server.base_url)
    deadline = time.time() + 60
    while time.time() < deadline:
        if proc.poll() is not None:
            raise RuntimeError("Disposable test server exited during startup")
        try:
            urllib.request.urlopen(f"{server.base_url}/api/health", timeout=2).read()
            return server
        except Exception:
            time.sleep(0.4)
    server.stop()
    raise RuntimeError("Disposable test server did not become healthy in 60s")


def live_base_url() -> str:
    """Base URL of this process's disposable server, started on first use and stopped at exit."""
    global _RUNNING
    if os.environ.get("SIGNGUY_API_BASE_URL"):
        raise UnsafeTestTargetError(
            "SIGNGUY_API_BASE_URL is no longer accepted: tests start their own disposable server. Unset it."
        )
    preset = os.environ.get("SIGNGUY_TEST_API_BASE_URL")
    if preset:  # provided by `python -m tests._test_env run`; still verified
        validate_test_api_url(preset)
        return preset
    if _RUNNING is None:
        _RUNNING = start_server()
        import atexit

        atexit.register(_RUNNING.stop)
    return _RUNNING.base_url
