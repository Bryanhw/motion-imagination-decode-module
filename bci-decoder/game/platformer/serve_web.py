"""Serve the browser game locally at a stable address on port 8765."""

from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import os

WEB_ROOT = Path(__file__).resolve().parent / "web"


class GameHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_ROOT), **kwargs)

    def end_headers(self):
        # Keep a bookmarked local page in sync with fixes made during gameplay.
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_GET(self):
        if self.path == "/replay_demo.jsonl":
            replay_path = WEB_ROOT.parent / "replay_demo.jsonl"
            try:
                payload = replay_path.read_bytes()
            except OSError:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        super().do_GET()


def main():
    host = os.environ.get("GAME_HOST", "127.0.0.1")
    port = int(os.environ.get("GAME_PORT", "8766"))
    server = ThreadingHTTPServer((host, port), GameHandler)
    print(f"MI Pixel Run is available at http://{host}:{port}/", flush=True)
    print("Keep this process running; press Ctrl+C to stop the local game server.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nGame server stopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
