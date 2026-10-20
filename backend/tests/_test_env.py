"""The one authoritative bootstrap for an isolated backend test environment.

Called from ``tests/conftest.py`` (``pytest_configure``, before any ``app`` module is
imported) and from the ``run`` CLI for standalone scripts. Never imports ``app``.

Per test run it creates:
  * a private ``mongod`` on a random loopback port with a temp data directory
    (or, for CI, an explicit ``SIGNGUY_TEST_MONGO_URL`` service that holds no foreign data),
  * one database per xdist worker, ``signguy_test_<run_id>_<worker>``, each carrying an
    ownership marker (run id + hash of a random owner token),
  * a run directory (manifest, mongod log, file storage) so abandoned runs are identifiable.

Cleanup only ever drops a database whose name AND ownership marker match the current run.
Nothing here reads or writes ``MONGO_URL``/``DB_NAME`` supplied by the caller: preset
values are refused so the developer database can never be the target.

CLI:  python -m tests._test_env list | reap | run -- <command...>
"""
from __future__ import annotations

import atexit
import hashlib
import json
import os
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.core.test_isolation import (  # noqa: E402  (stdlib-only module; safe before app imports)
    OWNER_COLLECTION,
    OWNER_TOKEN_VAR,
    RUN_ID_VAR,
    TEST_API_URL_VAR,
    TEST_DB_PREFIX,
    UnsafeTestTargetError,
    parse_run_db_name,
    test_db_name,
    validate_mongo_url,
    validate_test_api_url,
    validate_test_target,
)

RUNS_ROOT = Path(tempfile.gettempdir()) / "signguy-test-runs"
EXTERNAL_URL_VAR = "SIGNGUY_TEST_MONGO_URL"
MONGOD_VAR = "SIGNGUY_TEST_MONGOD"
RUN_DIR_VAR = "SIGNGUY_TEST_RUN_DIR"
SYSTEM_DBS = {"admin", "config", "local"}

# Integrations a test run must never reach. Blanked even if the caller's shell sets them.
_BLANKED = (
    "SENDGRID_API_KEY", "SENDGRID_FROM_EMAIL", "SENDGRID_WEBHOOK_PUBLIC_KEY", "OPENAI_API_KEY",
    "AI_PROVIDER_API_KEY", "STRIPE_API_KEY", "STRIPE_SECRET_KEY", "STRIPE_PUBLISHABLE_KEY",
    "STRIPE_WEBHOOK_SECRET", "STRIPE_CONNECT_CLIENT_ID", "STRIPE_CONNECT_WEBHOOK_SECRET",
    "SMS_PROVIDER_KEY", "SMS_PROVIDER_SECRET", "GOOGLE_OAUTH_CLIENT_ID", "GOOGLE_OAUTH_CLIENT_SECRET",
    "OBJECT_STORAGE_BASE_URL", "PUBLIC_APP_URL",
)
_DISABLED = (
    "AI_ENABLED", "SMS_ENABLED", "STRIPE_ENABLED", "STRIPE_WRITES_ENABLED", "STRIPE_WEBHOOK_ENABLED",
    "GOOGLE_AUTH_ENABLED", "OPENAI_REALTIME_ENABLED", "SENDGRID_WEBHOOK_ENABLED",
)
_UNSET = ("DEV_LOGIN_EMAIL", "DEV_LOGIN_FULL_NAME", "DEV_LOGIN_PLATFORM_CREATOR", "STRIPE_MODE", "CORS_ORIGINS")


class TestEnvError(RuntimeError):
    """The isolated test environment could not be created or was asked to do something unsafe."""

    __test__ = False  # not a pytest class


# ---------------------------------------------------------------- small helpers

def _sha(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _pid_alive(pid: int) -> bool:
    if os.name == "nt":
        import ctypes

        handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return False
        code = ctypes.c_ulong()
        ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(code))
        ctypes.windll.kernel32.CloseHandle(handle)
        return code.value == 259  # STILL_ACTIVE
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _client(url: str):
    from pymongo import MongoClient

    return MongoClient(url, serverSelectionTimeoutMS=15000)


def find_mongod() -> str | None:
    configured = os.environ.get(MONGOD_VAR)
    if configured:
        return configured if Path(configured).is_file() else None
    found = shutil.which("mongod")
    if found:
        return found
    candidates = sorted(Path("C:/Program Files/MongoDB/Server").glob("*/bin/mongod.exe")) if os.name == "nt" else []
    candidates += [Path(p) for p in ("/usr/bin/mongod", "/usr/local/bin/mongod", "/opt/homebrew/bin/mongod")]
    for path in reversed(candidates):
        if path.is_file():
            return str(path)
    return None


# ---------------------------------------------------------------- run lifecycle (controller)

def _write_manifest(run_dir: Path, data: dict) -> None:
    (run_dir / "manifest.json").write_text(json.dumps(data, indent=1), encoding="utf-8")


def _start_private_mongod(run_dir: Path) -> tuple[subprocess.Popen, str, int]:
    mongod = find_mongod()
    if not mongod:
        raise TestEnvError(
            "No test MongoDB is configured. Install MongoDB (mongod) or set "
            f"{MONGOD_VAR}=<path to mongod>, or point {EXTERNAL_URL_VAR} at a disposable test server. "
            "Refusing to fall back to the development database."
        )
    port = _free_port()
    data_dir = run_dir / "mongo-data"
    data_dir.mkdir()
    flags = 0x08000000 | 0x00000200 if os.name == "nt" else 0  # CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP
    proc = subprocess.Popen(
        [mongod, "--dbpath", str(data_dir), "--port", str(port), "--bind_ip", "127.0.0.1",
         "--wiredTigerCacheSizeGB", "0.5", "--logpath", str(run_dir / "mongod.log")],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=flags,
    )
    url = f"mongodb://127.0.0.1:{port}"
    deadline = time.time() + 60
    while time.time() < deadline:
        if proc.poll() is not None:
            raise TestEnvError(f"Private test mongod exited early; see {run_dir / 'mongod.log'}")
        try:
            client = _client(url)
            client.admin.command("ping")
            client.close()
            return proc, url, port
        except Exception:
            time.sleep(0.3)
    proc.terminate()
    raise TestEnvError("Private test mongod did not become ready in 60s")


def _assert_server_holds_no_foreign_data(url: str, run_id: str) -> None:
    client = _client(url)
    foreign = [n for n in client.list_database_names() if n not in SYSTEM_DBS and not n.startswith(f"{TEST_DB_PREFIX}{run_id}_")]
    client.close()
    if foreign:
        raise UnsafeTestTargetError(
            f"{url} already holds {len(foreign)} database(s) not created by this test run "
            f"(e.g. {foreign[0]!r}); it is not a disposable test server."
        )


def start_run() -> dict:
    """Controller step: create the run and export its environment. Refuses unsafe presets."""
    if os.environ.get("DB_NAME") or os.environ.get("MONGO_URL"):
        raise UnsafeTestTargetError(
            "DB_NAME/MONGO_URL are set in the environment "
            f"(DB_NAME={os.environ.get('DB_NAME')!r}). Tests never use caller-supplied database settings; "
            "unset them. Use SIGNGUY_TEST_MONGO_URL only for a disposable CI service."
        )
    run_id = secrets.token_hex(6)
    token = secrets.token_hex(16)
    RUNS_ROOT.mkdir(exist_ok=True)
    run_dir = RUNS_ROOT / run_id
    run_dir.mkdir()
    (run_dir / "dbs").mkdir()
    (run_dir / "storage").mkdir()
    manifest = {"run_id": run_id, "token_sha256": _sha(token), "runner_pid": os.getpid(),
                "created": time.time(), "mongod_pid": None, "port": None, "external": False, "run_dir": str(run_dir)}
    external = os.environ.get(EXTERNAL_URL_VAR)
    try:
        if external:
            validate_mongo_url(external, os.environ)
            _assert_server_holds_no_foreign_data(external, run_id)
            url, manifest["external"], manifest["url"] = external, True, external
        else:
            proc, url, port = _start_private_mongod(run_dir)
            manifest.update(mongod_pid=proc.pid, port=port, url=url)
            _CONTROLLER["proc"] = proc
        _write_manifest(run_dir, manifest)
    except BaseException:
        _teardown_run(manifest)
        raise
    _CONTROLLER.update(manifest=manifest, token=token)
    os.environ.update({RUN_ID_VAR: run_id, OWNER_TOKEN_VAR: token, RUN_DIR_VAR: str(run_dir), "MONGO_URL": url})
    _apply_safe_environment(run_dir)
    atexit.register(finish_run)
    return manifest


_CONTROLLER: dict = {}


def _apply_safe_environment(run_dir: Path) -> None:
    env = os.environ
    for name in _UNSET:
        env.pop(name, None)
    for name in _BLANKED:
        env[name] = ""
    for name in _DISABLED:
        env[name] = "false"
    env.update(ENV="test", AUTH_DEV_BYPASS="true", STORAGE_BACKEND="filesystem",
               OBJECT_STORAGE_PATH=str(run_dir / "storage"), JWT_SECRET=secrets.token_hex(32))


def finish_run() -> None:
    """Controller step: sweep owned databases, stop the private mongod, delete the run directory."""
    manifest = _CONTROLLER.pop("manifest", None)
    if manifest:
        _teardown_run(manifest)


def _drop_owned_dbs(url: str, manifest: dict) -> None:
    run_dir = Path(manifest["run_dir"])
    client = _client(url)
    try:
        for marker in sorted((run_dir / "dbs").glob("*")):
            drop_owned_database(client, marker.name, manifest["run_id"], manifest["token_sha256"])
    finally:
        client.close()


def _teardown_run(manifest: dict) -> None:
    run_dir = Path(manifest["run_dir"])
    if run_dir.parent != RUNS_ROOT:
        raise TestEnvError(f"Refusing to clean {run_dir}: not inside {RUNS_ROOT}")
    url = manifest.get("url")
    try:
        if manifest.get("external") and url:
            _drop_owned_dbs(url, manifest)
        elif manifest.get("port"):
            _shutdown_private_mongod(manifest)
    except Exception as exc:  # cleanup must never mask the test result
        sys.stderr.write(f"[test-env] cleanup warning for run {manifest['run_id']}: {exc}\n")
    proc = _CONTROLLER.pop("proc", None)
    if proc is not None:
        try:
            proc.wait(timeout=20)
        except subprocess.TimeoutExpired:
            proc.kill()
    shutil.rmtree(run_dir, ignore_errors=True)


def _shutdown_private_mongod(manifest: dict) -> None:
    """Shut down the mongod recorded in the manifest, after proving it is the one this run started."""
    client = _client(manifest["url"])
    try:
        opts = client.admin.command("getCmdLineOpts")["parsed"]
        expected = os.path.normcase(str(Path(manifest["run_dir"]) / "mongo-data"))
        if os.path.normcase(os.path.abspath(opts.get("storage", {}).get("dbPath", ""))) != expected:
            raise TestEnvError("Server on the recorded port is not this run's private mongod; not stopping it")
        try:
            client.admin.command("shutdown", force=True)
        except Exception:
            pass  # connection drops as the server exits
    finally:
        client.close()


# ---------------------------------------------------------------- per-worker database

def drop_owned_database(client, db_name: str, run_id: str, token_sha: str) -> bool:
    """Drop ``db_name`` only if its name AND ownership marker belong to this run."""
    parse_run_db_name(db_name, run_id)
    marker = client[db_name][OWNER_COLLECTION].find_one({"_id": "owner"})
    if not marker or marker.get("run_id") != run_id or marker.get("token_sha256") != token_sha:
        return False
    client.drop_database(db_name)
    return True


def create_worker_database(worker: str) -> str:
    """Create this worker's owned database (marker only) and export DB_NAME."""
    run_id, token = os.environ[RUN_ID_VAR], os.environ[OWNER_TOKEN_VAR]
    db_name = test_db_name(run_id, worker)
    os.environ["DB_NAME"] = db_name
    validate_test_target(os.environ)
    client = _client(os.environ["MONGO_URL"])
    try:
        if db_name in client.list_database_names():
            raise TestEnvError(f"{db_name} already exists; refusing to reuse it")
        client[db_name][OWNER_COLLECTION].insert_one(
            {"_id": "owner", "run_id": run_id, "token_sha256": _sha(token), "worker": worker, "pid": os.getpid(), "created": time.time()})
    finally:
        client.close()
    (Path(os.environ[RUN_DIR_VAR]) / "dbs" / db_name).touch()
    return db_name


def drop_worker_database() -> None:
    db_name = os.environ.get("DB_NAME", "")
    run_id = os.environ.get(RUN_ID_VAR, "")
    try:
        client = _client(os.environ["MONGO_URL"])
        drop_owned_database(client, db_name, run_id, _sha(os.environ[OWNER_TOKEN_VAR]))
        client.close()
    except Exception as exc:
        sys.stderr.write(f"[test-env] could not drop {db_name}: {exc}\n")


# ---------------------------------------------------------------- pytest entry points

def configure_for_pytest(num_processes: int) -> None:
    """Select and validate the test environment. Must run before any ``app`` import."""
    worker = os.environ.get("PYTEST_XDIST_WORKER")
    if RUN_ID_VAR not in os.environ:
        start_run()
    else:  # inherited from the xdist controller (or a `run` CLI parent): validate, never trust
        if not os.environ.get(OWNER_TOKEN_VAR) or not os.environ.get(RUN_DIR_VAR):
            raise UnsafeTestTargetError("Inherited test run is incomplete")
        validate_mongo_url(os.environ.get("MONGO_URL", ""), os.environ)
    if worker is None and num_processes:
        return  # xdist controller: owns the server, writes no data itself
    create_worker_database(worker or "main")


def finish_for_pytest() -> None:
    if os.environ.get("DB_NAME"):
        drop_worker_database()
    if "manifest" in _CONTROLLER:
        finish_run()


# ---------------------------------------------------------------- abandoned-run tooling

def _manifests() -> list[dict]:
    out = []
    for path in sorted(RUNS_ROOT.glob("*/manifest.json")) if RUNS_ROOT.exists() else []:
        try:
            out.append(json.loads(path.read_text(encoding="utf-8")))
        except Exception:
            continue
    return out


def list_runs() -> list[dict]:
    return [{**m, "abandoned": not _pid_alive(m["runner_pid"])} for m in _manifests()]


def reap_abandoned() -> int:
    """Clean up runs whose runner process is gone. Only touches resources named in a manifest."""
    count = 0
    for m in list_runs():
        if m["abandoned"]:
            _teardown_run(m)
            count += 1
    return count


# ---------------------------------------------------------------- run a command in an isolated env

def run_command(argv: list[str], with_server: bool = True) -> int:
    start_run()
    create_worker_database("main")
    server = None
    try:
        if with_server:
            from tests.live_server import start_server

            server = start_server()
            os.environ[TEST_API_URL_VAR] = server.base_url
            validate_test_api_url(server.base_url)
        return subprocess.call(argv, cwd=BACKEND_DIR)
    finally:
        if server:
            server.stop()
        drop_worker_database()
        finish_run()


def main(argv: list[str]) -> int:
    cmd = argv[0] if argv else ""
    if cmd == "list":
        for m in list_runs():
            print(f"{m['run_id']}  runner_pid={m['runner_pid']}  {'ABANDONED' if m['abandoned'] else 'active'}  {m['run_dir']}")
        return 0
    if cmd == "reap":
        print(f"reaped {reap_abandoned()} abandoned run(s)")
        return 0
    if cmd == "run" and "--" in argv:
        return run_command(argv[argv.index("--") + 1:])
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
