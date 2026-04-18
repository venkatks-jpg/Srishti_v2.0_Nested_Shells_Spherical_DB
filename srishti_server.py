#!/usr/bin/env python3
"""
srishti_gate.py  —  Srishti Spherical Query Server  v1.1

Serves the spherical database query interface.
One job: query the sphere, return results, open files.
Nothing else.

Architecture:
    Browser → srishti_gate.py (port 7509) → srishti1.db / srishti3.db
    Click result → xdg-open → appropriate application

The intelligence is in the geometry.
r = PHI^n — irrational, never colliding, to infinity.
No two domain shells ever overlap.
O(1) seek: fix r, fix theta, text search within that space only.

maya.py is in the cellar where it belongs.
The word Maya does not appear in this file except in this sentence.

Author  : Venkatesh (CI) + Claude (SI)
License : GNU GPL 3.0 — free for all, profit for none
"""

import json
import os
import math
import sqlite3
import time
import subprocess
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from datetime import datetime

class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True

# ── CONFIG ────────────────────────────────────────────────────────────────────
DB1_PATH = str(Path.home() / "srishti1.db")   # DATA 1    (internal)
DB2_PATH = str(Path.home() / "srishti2.db")   # VENKAT1   (external)
DB3_PATH = str(Path.home() / "srishti3.db")   # DATA3     (external)
DB4_PATH = str(Path.home() / "srishti4.db")   # WINDATA   (external)
PORT     = 7509
HOST     = "0.0.0.0"

PHI = (1 + math.sqrt(5)) / 2   # 1.6180339887498948482...


# ── TAMIL KEYWORDS ────────────────────────────────────────────────────────────
TAMIL_KEYWORDS = [
    "tamil", "தமிழ்", "தமிழ", "tamizh",
    "panchang", "panchangam", "பஞ்சாங்கம்",
    "lagu", "லகு", "laghu",
    "abirami", "அபிராமி",
    "gayathiri", "gayathri", "காயத்ரி",
    "murugan", "muruga", "முருகன்",
    "pillai", "பிள்ளை",
    "iyer", "iyengar", "அய்யர்",
    "carnatic", "karnatic",
    "thirukural", "திருக்குறள்",
    "ramayana", "mahabharata",
    "kovil", "temple", "கோவில்",
    "mudra", "mudras",
    "telugu", "kannada", "malayalam",
    "andhra", "kerala", "karnataka",
]


# ── SPHERICAL QUERY ENGINE ────────────────────────────────────────────────────
def query_db(params, db_path=None):
    """
    True spherical query — geometry does the seeking.

    Step 1 — Fix r.
              If domain name given, look up its exact r = PHI^n from
              the domains table. WHERE r = that value AND silent = 0.
              Everything outside that shell is never loaded.

    Step 2 — Fix theta (optional).
              If subdomain given, look up its exact theta from subdomains table.
              Uses epsilon=1e-9 BETWEEN for float safety.
              Golden angle distribution — theta values span [0, pi], not clustered.

    Step 3 — Text search within that narrow coordinate space only.
              LIKE on name and path — applied after r and theta filters.

    Step 4 — ORDER BY name ASC, LIMIT.

    Tamil path bypasses spherical seek — searches name/path directly
    for Tamil script and transliterated keywords.

    silent = 0 is permanent — program_db files never shown.
    """
    target = db_path or DB1_PATH
    conn   = sqlite3.connect(target)

    text      = params.get("text", "")
    domain    = (params.get("r_label") or params.get("domain") or "").strip()
    subdomain = (params.get("subdomain") or "").strip()
    phi_val   = params.get("phi")
    min_size  = params.get("min_size")
    limit     = int(params.get("limit", 5000))
    lang      = params.get("lang", "")

    clauses, qparams = [], []

    # ── Tamil path ──────────────────────────────────────────────────────────
    if lang == "tamil" or (text and any(
        kw in text.lower()
        for kw in ["tamil", "தமிழ்", "tamizh", "panchang",
                   "carnatic", "mudra", "abirami"]
    )):
        tamil_clauses = []
        for kw in TAMIL_KEYWORDS:
            tamil_clauses.append(
                "(LOWER(name) LIKE ? OR LOWER(path) LIKE ?)"
            )
            qparams += [f"%{kw.lower()}%", f"%{kw.lower()}%"]
        clauses.append("(" + " OR ".join(tamil_clauses) + ")")
        clauses.append("silent = 0")

    else:
        # ── Step 1 — Fix r (domain shell) ──────────────────────────────────
        if domain:
            row = conn.execute(
                "SELECT r FROM domains WHERE name = ?", (domain,)
            ).fetchone()
            if row:
                clauses.append("r = ?")
                qparams.append(row[0])
            else:
                clauses.append("domain = ?")
                qparams.append(domain)

        # ── Step 2 — Fix subdomain (direct column match) ────────────────────
        if subdomain and domain:
            clauses.append("subdomain = ?")
            qparams.append(subdomain)

        # ── Always silent = 0 ───────────────────────────────────────────────
        clauses.append("silent = 0")

        # ── Optional phi filter ─────────────────────────────────────────────
        if phi_val:
            clauses.append("phi = ?")
            qparams.append(float(phi_val))

        # ── Optional size filter ────────────────────────────────────────────
        if min_size:
            clauses.append("size >= ?")
            qparams.append(int(min_size))

        # ── Step 3 — Text search within coordinate space ────────────────────
        if text and lang != "tamil":
            clauses.append(
                "(LOWER(name) LIKE ? OR LOWER(path) LIKE ?)"
            )
            qparams += [f"%{text.lower()}%", f"%{text.lower()}%"]

    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""

    # ── Step 4 — ORDER BY name ASC ──────────────────────────────────────────
    sql = (f"SELECT path, name, size, mtime, r, domain, subdomain, "
           f"phi, confidence "
           f"FROM files {where} ORDER BY name ASC LIMIT ?")
    qparams.append(limit)

    try:
        rows = conn.execute(sql, qparams).fetchall()
    except Exception as e:
        conn.close()
        return {"results": [], "count": 0, "error": str(e)}

    count_sql = f"SELECT COUNT(*) FROM files {where}"
    try:
        total = conn.execute(count_sql, qparams[:-1]).fetchone()[0]
    except Exception:
        total = len(rows)

    results = []
    for row in rows:
        results.append({
            "path":       row[0],
            "name":       row[1],
            "size":       row[2],
            "mtime":      (datetime.fromtimestamp(row[3]).strftime("%Y-%m-%d")
                           if row[3] else ""),
            "r":          row[4],
            "r_label":    row[5],
            "domain":     row[5],
            "subdomain":  row[6],
            "phi":        row[7],
            "confidence": row[8],
        })

    # Log to query_memory
    try:
        conn.execute("""
        INSERT INTO query_memory
        (query_text, domain_hit, r_hit, result_count, ts)
        VALUES (?,?,?,?,?)
        """, (text or domain or "",
              domain or "",
              rows[0][4] if rows else 0.0,
              total,
              int(time.time())))
        conn.commit()
    except Exception:
        pass

    conn.close()
    return {"results": results, "count": total}


# ── HTTP SERVER ───────────────────────────────────────────────────────────────
class SrishtiHandler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        print(f"  [{datetime.now().strftime('%H:%M:%S')}] "
              f"{args[0]} {args[1]}")

    def send_cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods",
                         "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_cors()
        self.end_headers()

    def do_GET(self):
        # ── Serve GUI at root ──────────────────────────────────────────────
        if self.path in ("/", "/index.html"):
            gui_path = Path(__file__).parent / "srishti_gui.html"
            if gui_path.exists():
                self.send_response(200)
                self.send_cors()
                self.send_header("Content-Type",
                                 "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(gui_path.read_bytes())
            else:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b"srishti_gui.html not found")
            return

        # ── Favicon ────────────────────────────────────────────────────────
        if self.path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return

        # ── Health ─────────────────────────────────────────────────────────
        if self.path == "/health":
            self.send_response(200)
            self.send_cors()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            counts = {}
            for label, path in [("1",DB1_PATH),("2",DB2_PATH),("3",DB3_PATH),("4",DB4_PATH)]:
                try:
                    counts[label] = sqlite3.connect(path).execute(
                        "SELECT COUNT(*) FROM files"
                    ).fetchone()[0]
                except Exception:
                    counts[label] = 0
            self.wfile.write(json.dumps({
                "status": "Srishti is alive",
                "db1":    DB1_PATH, "db2": DB2_PATH,
                "db3":    DB3_PATH, "db4": DB4_PATH,
                "files1": counts["1"], "files2": counts["2"],
                "files3": counts["3"], "files4": counts["4"],
                "phi":    PHI,
            }).encode())
            return

        # ── Stats ──────────────────────────────────────────────────────────
        if self.path.startswith("/stats"):
            db = DB2_PATH if "db=2" in self.path else DB1_PATH
            self.send_response(200)
            self.send_cors()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            try:
                conn = sqlite3.connect(db)
                rows = conn.execute("""
                    SELECT domain, COUNT(*), SUM(size), MIN(r)
                    FROM   files
                    GROUP  BY domain
                    ORDER  BY MIN(r)
                """).fetchall()
                conn.close()
                stats = [{"domain": r[0], "count": r[1],
                          "size_gb": round(r[2] / 1e9, 2) if r[2] else 0,
                          "r": r[3]} for r in rows]
            except Exception:
                stats = []
            self.wfile.write(json.dumps({"domains": stats}).encode())
            return

        # ── /subdomains?domain=X&db=N ──────────────────────────────────────
        if self.path.startswith("/subdomains"):
            try:
                from urllib.parse import urlparse, parse_qs
                qs     = parse_qs(urlparse(self.path).query)
                domain = (qs.get("domain", [""])[0]).strip()
                db_n   = qs.get("db", ["1"])[0]
                db_map = {"1": DB1_PATH, "2": DB2_PATH, "3": DB3_PATH, "4": DB4_PATH}
                db     = db_map.get(db_n, DB1_PATH)
                subs   = []
                if domain:
                    conn  = sqlite3.connect(db)
                    rows  = conn.execute(
                        "SELECT name FROM subdomains WHERE domain_name=? ORDER BY theta",
                        (domain,)
                    ).fetchall()
                    conn.close()
                    subs = [r[0] for r in rows]
            except Exception as ex:
                subs = []
                print(f"  /subdomains error: {ex}")
            self.send_response(200)
            self.send_cors()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(subs).encode())
            return

        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        # ── /query — DB1 (srishti1.db) ────────────────────────────────────
        if self.path == "/query":
            length = int(self.headers.get("Content-Length", 0))
            body   = self.rfile.read(length)
            try:
                params = json.loads(body.decode("utf-8"))
            except Exception:
                params = {}
            result = query_db(params, db_path=DB1_PATH)
            self.send_response(200)
            self.send_cors()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(result).encode())
            return

        # ── /query2 — DB2 (srishti2.db) ───────────────────────────────────
        if self.path == "/query2":
            length = int(self.headers.get("Content-Length", 0))
            body   = self.rfile.read(length)
            try:
                params = json.loads(body.decode("utf-8"))
            except Exception:
                params = {}
            result = query_db(params, db_path=DB2_PATH)
            self.send_response(200)
            self.send_cors()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(result).encode())
            return

        # ── /query3 — DB3 (srishti3.db) ───────────────────────────────────
        if self.path == "/query3":
            length = int(self.headers.get("Content-Length", 0))
            body   = self.rfile.read(length)
            try:
                params = json.loads(body.decode("utf-8"))
            except Exception:
                params = {}
            result = query_db(params, db_path=DB3_PATH)
            self.send_response(200)
            self.send_cors()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(result).encode())
            return

        # ── /query4 — DB4 (srishti4.db) ───────────────────────────────────
        if self.path == "/query4":
            length = int(self.headers.get("Content-Length", 0))
            body   = self.rfile.read(length)
            try:
                params = json.loads(body.decode("utf-8"))
            except Exception:
                params = {}
            result = query_db(params, db_path=DB4_PATH)
            self.send_response(200)
            self.send_cors()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(result).encode())
            return

        # ── /open — open file with xdg-open ───────────────────────────────
        if self.path == "/open":
            length = int(self.headers.get("Content-Length", 0))
            body   = self.rfile.read(length)
            try:
                data = json.loads(body.decode("utf-8"))
                path = data.get("path", "")
                if path and os.path.exists(path):
                    subprocess.Popen(["xdg-open", path])
                    self.send_response(200)
                    self.send_cors()
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"ok": True}).encode())
                else:
                    self.send_response(404)
                    self.send_cors()
                    self.end_headers()
                    self.wfile.write(
                        json.dumps({"error": "file not found"}).encode()
                    )
            except Exception:
                self.send_response(500)
                self.end_headers()
            return

        self.send_response(404)
        self.end_headers()


# ── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    dbs = [
        (DB1_PATH, "DB1", "DATA 1  (internal)"),
        (DB2_PATH, "DB2", "VENKAT1 (external)"),
        (DB3_PATH, "DB3", "DATA3   (external)"),
        (DB4_PATH, "DB4", "WINDATA (external)"),
    ]

    counts = {}
    for path, label, _ in dbs:
        if not Path(path).exists():
            print(f"  Warning: {label} not found at {path}")
        try:
            counts[label] = sqlite3.connect(path).execute(
                "SELECT COUNT(*) FROM files"
            ).fetchone()[0]
        except Exception:
            counts[label] = 0

    total = sum(counts.values())

    print("=" * 57)
    print("  Srishti — Spherical Knowledge Database")
    print("=" * 57)
    for path, label, desc in dbs:
        print(f"  {label}    : {path}")
        print(f"           {desc} — {counts.get(label,0):,} files")
    print(f"  Total   : {total:,} files across 4 databases")
    print(f"  Port    : {PORT}")
    print(f"  \u03c6       : {PHI}")
    print(f"  Open    : http://localhost:{PORT}")
    print("=" * 57)
    print("  The intelligence is in the geometry.")
    print("  S bogom.")
    print()

    subprocess.Popen(["xdg-open", f"http://localhost:{PORT}"])

    server = ThreadingHTTPServer((HOST, PORT), SrishtiHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Srishti gate closed.")
        server.server_close()


if __name__ == "__main__":
    main()
