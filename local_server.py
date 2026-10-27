"""Local-only server entry point used by start_app.ps1."""
import hashlib
import os
from pathlib import Path
import socket
import subprocess
import sys

from werkzeug.serving import BaseWSGIServer


PROJECT_ROOT = Path(__file__).resolve().parent


def source_fingerprint(root=PROJECT_ROOT):
    digest = hashlib.sha256()
    files = sorted(root.glob("*.py")) + sorted((root / "templates").glob("*.html"))
    for path in files:
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()[:12]


class ExclusiveLocalServer(BaseWSGIServer):
    allow_reuse_address = False

    def server_bind(self):
        if sys.platform == "win32":
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def serve_local(app):
    fingerprint = source_fingerprint()

    def local_status():
        return {
            "application": "cloud-transaction-app",
            "project_root": str(PROJECT_ROOT),
            "pid": os.getpid(),
            "fingerprint": fingerprint,
        }

    app.add_url_rule("/_local/status", "local_status", local_status)
    server = ExclusiveLocalServer("127.0.0.1", 5000, app)
    print(f"Cloud Transaction App [{fingerprint}] http://127.0.0.1:5000", flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == "__main__":
    if sys.argv[1:] == ["--fingerprint"]:
        print(source_fingerprint())
    elif sys.argv[1:] == ["--start-background"]:
        child = subprocess.Popen(
            [sys.executable, str(Path(__file__).resolve())],
            cwd=PROJECT_ROOT,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            creationflags=subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP,
        )
        print(child.pid)
    else:
        os.chdir(PROJECT_ROOT)
        log_folder = PROJECT_ROOT / "logs"
        log_folder.mkdir(exist_ok=True)
        log_file = (log_folder / "local-server.log").open("a", encoding="utf-8", buffering=1)
        sys.stdout = log_file
        sys.stderr = log_file
        from app import app

        serve_local(app)
