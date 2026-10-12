"""Join a shared sandbox using this computer's own model account."""
from __future__ import annotations

import argparse
import getpass
import json
import os
from pathlib import Path
import socket
import sys
import time
import urllib.error
import urllib.request
from urllib.parse import urlparse, parse_qs

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    from sandbox import provider
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", required=True, help="Host URL or private join link")
    parser.add_argument("--backend", choices=("claude-cli", "sol", "openrouter"), default="claude-cli")
    parser.add_argument("--model", default="")
    parser.add_argument("--name", default=socket.gethostname())
    parser.add_argument("--once", action="store_true", help="Complete one job, then exit")
    args = parser.parse_args()
    parsed = urlparse(args.server)
    token = parse_qs(parsed.fragment).get("token", [""])[0] or os.environ.get("AMBLE_SWARM_TOKEN") or getpass.getpass("Town join token: ")
    base = parsed.scheme + "://" + parsed.netloc
    config = {"model_backend": args.backend, "model": args.model}
    provider.configure(config)
    def call(path, body):
        request = urllib.request.Request(base + path, data=json.dumps(body).encode(),
                    headers={"Content-Type": "application/json", "X-Swarm-Token": token}, method="POST")
        with urllib.request.urlopen(request, timeout=120) as response:
            return json.load(response)
    print("Worker connected to " + base + ". Ctrl-C stops this worker; no model credentials are sent to the host.", flush=True)
    while True:
        lease = None
        try:
            lease = call("/api/lease", {"worker_id": args.name}).get("lease")
            if lease:
                raw = provider.answer(lease["prompt"], config)
                result = call("/api/complete", {"worker_id": args.name, "lease_id": lease["id"],
                         "resident_id": lease["resident"]["id"], "raw": raw, "result": provider.parse_result(raw)})
                print(json.dumps({"job": lease["job"]["title"], "result": result}), flush=True)
                if args.once:
                    return
        except KeyboardInterrupt:
            if lease:
                call("/api/release", {"worker_id": args.name, "lease_id": lease["id"], "error": "Worker stopped"})
            return
        except Exception as exc:
            print("Worker retry: " + type(exc).__name__, flush=True)
            if lease:
                try:
                    call("/api/release", {"worker_id": args.name, "lease_id": lease["id"], "error": type(exc).__name__})
                except Exception:
                    pass
        time.sleep(3)


if __name__ == "__main__":
    main()
