"""Synthetic local retrieval fixture for the documented quick start (no API keys)."""

import argparse
import json
from contextlib import suppress
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            payload = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
            question = payload["query"]
            limit = max(0, int(payload.get("top_k", 5)))
            chunks = [{"chunk_id": "refund-policy", "content": "Refunds are allowed within 30 days.", "similarity": 1.0}] if "refund" in question.lower() else []
            body = json.dumps({"data": {"chunks": chunks[:limit]}}).encode()
        except (ValueError, KeyError, TypeError, AttributeError):
            self.send_error(400, "Expected JSON query and optional integer top_k")
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    with ThreadingHTTPServer(("127.0.0.1", args.port), Handler) as server:
        print(f"Development retriever: http://127.0.0.1:{server.server_port}/retrieve")
        with suppress(KeyboardInterrupt):
            server.serve_forever()
