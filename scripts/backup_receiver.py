"""Stand-in for Object Storage in the Compose smoke test (MKC-11.4). Test use only.

PUT <any path> stores the body in memory; GET /latest returns the last body.
Standard library only; run with: python backup_receiver.py <port>
"""

import http.server
import sys
import threading

_lock = threading.Lock()
_latest: dict[str, bytes] = {}


class Receiver(http.server.BaseHTTPRequestHandler):
    def do_PUT(self) -> None:
        length = int(self.headers["Content-Length"])
        body = self.rfile.read(length)
        with _lock:
            _latest["body"] = body
        print(f"received {length} bytes for {self.path.rsplit('/', 1)[-1]}", flush=True)
        self.send_response(200)
        self.end_headers()

    def do_GET(self) -> None:
        with _lock:
            body = _latest.get("body")
        if self.path != "/latest" or body is None:
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args: object) -> None:
        pass


if __name__ == "__main__":
    http.server.ThreadingHTTPServer(("0.0.0.0", int(sys.argv[1])), Receiver).serve_forever()
