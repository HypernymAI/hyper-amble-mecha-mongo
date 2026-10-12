"""Render this repository's Presents exhibit and run its separate shared swarm."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.parse import urlparse
import venv
import webbrowser

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from presents_run import configured_environment, package_config, private_json  # noqa: E402


def bootstrap(root: Path, argv: list) -> None:
    """Install only in this clone's venv, then return to this launcher."""
    if sys.version_info < (3, 9):
        raise ValueError("Python 3.9 or newer is required.")
    folder = root / "venv"
    python = folder / "bin" / "python3"
    if not python.is_file():
        print("Creating this clone's Python environment…", flush=True)
        venv.EnvBuilder(with_pip=True).create(folder)
    requirements = root / "requirements-presents.txt"
    digest = hashlib.sha256(requirements.read_bytes()).hexdigest()
    marker = folder / ".swarm-requirements"
    if not marker.exists() or marker.read_text().strip() != digest:
        print("Installing the Presents web and database dependencies into this venv…", flush=True)
        subprocess.run([str(python), "-m", "pip", "install", "-r", str(requirements)], check=True)
        marker.write_text(digest + "\n")
    os.execv(str(python), [str(python), str(root / "scripts/swarm_run.py")]
             + [arg for arg in argv if arg != "--bootstrap"])


def saved_settings(directory: Path) -> dict:
    path = directory / "config.json"
    if not path.exists():
        return {}
    if path.stat().st_size > 100_000:
        raise ValueError("The swarm configuration is too large.")
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError("The swarm configuration must be an object.")
    return value


def swarm_environment(root: Path, directory: Path, saved: dict, *, backend=None, model=None, incoming=None) -> dict:
    """CLI choices win over saved town preferences, then package/.env defaults."""
    incoming = dict(os.environ if incoming is None else incoming)
    selected = backend or saved.get("model_backend")
    selected = "sol" if selected == "codex" else selected
    selected_model = model or (saved.get("model") if not backend or selected == saved.get("model_backend") else None)
    if selected:
        incoming["AMBLE_PRESENTS_BACKEND"] = selected
        incoming["MODEL_BACKEND"] = selected
        # An explicit backend cannot inherit a model pin for another provider.
        for key in ("AMBLE_PRESENTS_MODEL", "MODEL_NAME", "AMBLE_MODEL", "AMBLE_CODEX_MODEL"):
            incoming[key] = ""
        if selected_model:
            incoming["AMBLE_PRESENTS_MODEL"] = selected_model
    elif model:
        for key in ("MODEL_NAME", "AMBLE_MODEL", "AMBLE_CODEX_MODEL"):
            incoming[key] = ""
        incoming["AMBLE_PRESENTS_MODEL"] = model
    env = configured_environment(root, incoming=incoming)
    env.update(AMBLE_RUNTIME_PROFILE="presents",
               AMBLE_CHANNEL_DATA=str(directory / "channel"),
               AMBLE_PRESENTS_DATA=str(directory / "channel" / "presents"),
               AMBLE_PRESENTS_INTAKE_URL="", AMBLE_PRESENTS_PUBLISH="off")
    return env


@contextmanager
def using_environment(env: dict):
    previous = dict(os.environ)
    os.environ.clear()
    os.environ.update(env)
    try:
        yield
    finally:
        os.environ.clear()
        os.environ.update(previous)


def prepare(root: Path, directory: Path, config: dict, env: dict) -> Path:
    """Local file rendering only: no web server, provider, bootstrap or Atlas."""
    with using_environment(env):
        from channel import presents
        manifest = root / "data" / "channel" / "presents" / "exhibits" / config["exhibit"] / "presentation.json"
        exhibit = presents.Exhibit(presents.find_exhibit(str(manifest.resolve())))
        return presents.render(exhibit, directory / "presents", subject=config["subject"])


def check_port(host: str, port: int) -> None:
    with socket.socket() as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind((host, port))
        except OSError as exc:
            raise ValueError("Port " + str(port) + " is unavailable; choose --port or stop the other server yourself.") from exc


def wait_for_launch(process, directory: Path, port: int, started: float) -> str:
    deadline = time.monotonic() + 20
    launch = directory / "launch.json"
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("The swarm server stopped during startup; inspect data/swarm/logs/server.log.")
        try:
            if launch.stat().st_mtime >= started:
                url = json.loads(launch.read_text()).get("url", "")
                parsed = urlparse(url)
                if parsed.scheme == "http" and parsed.hostname == "127.0.0.1" and parsed.port == port:
                    with socket.create_connection(("127.0.0.1", port), timeout=.2):
                        return url
        except (OSError, ValueError, AttributeError):
            pass
        time.sleep(.1)
    raise RuntimeError("The swarm server did not become ready; inspect data/swarm/logs/server.log.")


def run(root: Path, directory: Path, env: dict, saved: dict, *, host: str, port: int, workers: int, open_browser: bool) -> int:
    check_port(host, port)
    saved.update(model_backend=env["AMBLE_PRESENTS_BACKEND"], model=env["AMBLE_PRESENTS_MODEL"])
    private_json(directory / "config.json", saved)
    log_path = directory / "logs" / "server.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_fd = os.open(str(log_path), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    process = None
    try:
        with os.fdopen(log_fd, "a") as log:
            started = time.time()
            process = subprocess.Popen([sys.executable, str(root / "scripts/swarm_server.py"),
                                        "--host", host, "--port", str(port), "--workers", str(workers),
                                        "--data", str(directory)], cwd=root, env=env,
                                       stdout=log, stderr=subprocess.STDOUT)
            url = wait_for_launch(process, directory, port, started)
            print("Presents swarm is ready on port " + str(port) + ".", flush=True)
            print("Private local and join links: " + str(directory / "launch.json"), flush=True)
            print("Open Swarm, then Start to begin resident work. Ctrl-C stops this server.", flush=True)
            if open_browser:
                webbrowser.open(url)
            return process.wait()
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bootstrap", action="store_true", help="Create this clone's venv and install requirements-presents")
    parser.add_argument("--prepare-only", action="store_true", help="Render local files only, without bootstrap/network/model/server")
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--backend", choices=("claude-cli", "codex", "sol", "openrouter"))
    parser.add_argument("--model")
    parser.add_argument("--host", choices=("0.0.0.0", "127.0.0.1"), default="0.0.0.0")
    parser.add_argument("--port", type=int, default=3190)
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args(argv)
    try:
        if not 1 <= args.port <= 65535 or not 1 <= args.workers <= 6:
            raise ValueError("Choose port 1–65535 and 1–6 workers.")
        config = package_config(ROOT)
        if args.bootstrap and not args.prepare_only:
            bootstrap(ROOT, argv)
        directory = ROOT / "data" / "swarm"
        saved = saved_settings(directory)
        env = swarm_environment(ROOT, directory, saved, backend=args.backend, model=args.model)
        out = prepare(ROOT, directory, config, env)
        print("Rendered this repository's Presents exhibit: " + str(out), flush=True)
        if args.prepare_only:
            print("Preparation complete. No server, bootstrap, model request, or network connection was started.", flush=True)
            return 0
        return run(ROOT, directory, env, saved, host=args.host, port=args.port,
                   workers=args.workers, open_browser=not args.no_browser)
    except KeyboardInterrupt:
        print("\nPresents swarm stopped.")
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        # Invalid JSON includes positions, not its credential-bearing contents.
        print("Presents swarm could not start: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
