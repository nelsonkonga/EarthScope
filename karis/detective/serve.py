"""The detective as a local web app: the demo cases, plus new investigations on demand.

    python -m detective.serve [port]        # then open http://<host>:8765

GET  /                    the page, with the demo cases and the question form
GET  /api/status          {"live": true, "cases": [...ids]}
POST /api/investigate     {"region": "sahel" | "s,n,w,e", "vars": ["T2M", ...], "words": "..."}
                          -> {"case": {...}} (the same shape as the demo cases)
GET  /land                land intelligence (kepler.gl): the analysed regions of data/earth/land
POST /api/land            {"region": "west_sahel" | "s,n,w,e"} -> {"case": {...}}: fetch NASA POWER and
                          GPM IMERG, detect, test and predict (MODIS land cover only if already cached)
POST /api/ask             {"question": "...", "history": [...]} -> {"text", "focus"}: Ask Eva (detective/agent.py,
GET  /api/ask/status      needs ANTHROPIC_API_KEY); also under /land/api/ask for the page's relative URL

Only the standard library; one investigation at a time (they share the caches).
"""

from __future__ import annotations

import json
import re
import sys
import threading
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import agent, land, land_page
from .investigate import investigate
from .regions import parse_region
from .report import demo_cases, render, slim
from .variables import VARIABLES

CASES: list[dict] = []
LAND: list[dict] = []
LOCK = threading.Lock()
SEEN: dict = {}  # the analysed regions on disk when LAND was last read: {file name: modification time}


def land_cases() -> list[dict]:
    """The analysed regions, read again when a result on disk was added or changed (no restart needed)."""
    now = {f.name: f.stat().st_mtime for f in land.OUT.glob("*.json")}
    if now != SEEN:
        with LOCK:
            LAND[:] = land_page.cases_on_disk()
            SEEN.clear(); SEEN.update(now)
    return LAND


def new_case(body: dict) -> dict:
    regions = [parse_region(x) for x in re.split(r"\s*;\s*", str(body.get("region", "")).strip()) if x]
    if not regions:
        raise ValueError("choose a region")
    keys = [k for k in body.get("vars", []) if k in VARIABLES]
    if not keys:
        raise ValueError("choose at least one variable")
    words = body.get("words") or None
    with LOCK:
        res = investigate(regions, keys, words, log=lambda *_a: None, change_draws=0)  # minutes: not live
        cid = "case-" + re.sub(r"[^a-z0-9]+", "-", "-".join([r.key for r in regions] + keys).lower()).strip("-")
        title = ", ".join(VARIABLES[k].label for k in keys[:2]) + (" …" if len(keys) > 2 else "") + " · " + regions[0].name
        case = slim(res, cid, title, f"What is changing in {', '.join(VARIABLES[k].label.lower() for k in keys)} "
                                     f"over {' and '.join(r.name for r in regions)}?")
        CASES[:] = [c for c in CASES if c["id"] != cid] + [case]
    return case


def new_land_case(body: dict) -> dict:
    r = parse_region(str(body.get("region", "")).strip())
    if (r.north - r.south) * (r.east - r.west) > 400:
        raise ValueError("choose a box of at most about 20° x 20°: NASA POWER answers per 10° tile")
    with LOCK:
        res = land.run(r, offline=False, draws=99, log=lambda *_a: None)
        land.OUT.mkdir(parents=True, exist_ok=True)
        (land.OUT / f"{r.key}.json").write_text(json.dumps(res))
        case = land_page.slim(res)
        LAND[:] = [c for c in LAND if c["region"]["key"] != r.key] + [case]
        SEEN[f"{r.key}.json"] = (land.OUT / f"{r.key}.json").stat().st_mtime
    return case


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 (http.server API)
        if self.path.split("?")[0] in ("/", "/index.html"):
            self._send(200, render(CASES, live=True).encode("utf-8"), "text/html; charset=utf-8")
        elif self.path.split("?")[0] in ("/land", "/land/"):
            self._send(200, land_page.render(land_cases(), live=True).encode("utf-8"), "text/html; charset=utf-8")
        elif self.path.rstrip("/") in ("/api/ask/status", "/land/api/ask/status"):
            self._send(200, json.dumps({"agent": agent.available(), "model": agent.MODEL}).encode(), "application/json")
        elif self.path == "/api/status":
            self._send(200, json.dumps({"live": True, "cases": [c["id"] for c in CASES]}).encode(), "application/json")
        else:
            self._send(404, b'{"error": "not found"}', "application/json")

    def do_POST(self) -> None:  # noqa: N802
        if self.path.rstrip("/") in ("/api/ask", "/land/api/ask"):
            try:
                body = json.loads(self.rfile.read(min(int(self.headers.get("Content-Length", "0")), 64_000)) or b"{}")
            except ValueError:
                self._send(400, b'{"error": "bad request"}', "application/json")
                return
            code, out = agent.handle(body, self.client_address[0])
            self._send(code, json.dumps(out, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")
            return
        if self.path not in ("/api/investigate", "/api/land"):
            self._send(404, b'{"error": "not found"}', "application/json")
            return
        try:
            n = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(n) or b"{}")
            case = new_land_case(body) if self.path == "/api/land" else new_case(body)
            self._send(200, json.dumps({"case": case}).encode("utf-8"), "application/json")
        except ValueError as e:
            self._send(400, json.dumps({"error": str(e)}).encode(), "application/json")
        except Exception as e:  # noqa: BLE001 — report any failure to the page
            traceback.print_exc()
            self._send(500, json.dumps({"error": f"{type(e).__name__}: {e}"}).encode(), "application/json")

    def log_message(self, fmt, *args) -> None:
        sys.stderr.write("detective: " + fmt % args + "\n")


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    CASES[:] = demo_cases()
    land_cases()
    srv = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"Eva Trend Detective on http://0.0.0.0:{port}  ({len(CASES)} demo cases; Ctrl+C to stop)")
    print(f"Land intelligence on http://0.0.0.0:{port}/land  ({len(LAND)} region(s))")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
