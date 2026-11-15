"""Client of NASA's earthdata-mcp server (https://github.com/nasa/earthdata-mcp).

The server speaks the Model Context Protocol over *streamable HTTP*: every request is a
JSON-RPC 2.0 message POSTed to one URL, and the answer comes back either as JSON or as a
short Server-Sent Events stream (``event: message`` / ``data: {...}``). ``initialize``
returns a session id (header ``Mcp-Session-Id``) that every later request carries.

The hosted endpoint answers the discovery tools without any login — they search NASA's
Common Metadata Repository (CMR): ``get_keywords`` (GCMD vocabulary), ``get_collections``,
``get_granules``, ``get_variables``, ``get_services``, ``get_tools``, ``get_citations``.
(The Harmony transformation tools of the repository need an Earthdata Login token and are
not offered by the hosted endpoint without it.)

Every answer is cached on disk so that an investigation can be replayed offline.
"""

from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

URL = "https://cmr.earthdata.nasa.gov/mcp/v1"
CACHE = Path(__file__).resolve().parents[1] / "data" / "earth" / "cache" / "mcp"
PROTOCOL = "2025-06-18"


class MCPError(RuntimeError):
    pass


def parse_messages(body: str, content_type: str) -> list[dict]:
    """JSON-RPC messages of an HTTP answer: a JSON body, or an SSE stream of ``data:`` lines."""
    if not body.strip():
        return []
    if "text/event-stream" in content_type:
        out = []
        for block in body.replace("\r\n", "\n").split("\n\n"):
            data = "\n".join(line[5:].lstrip() for line in block.splitlines() if line.startswith("data:"))
            if data:
                out.append(json.loads(data))
        return out
    got = json.loads(body)
    return got if isinstance(got, list) else [got]


class EarthdataMCP:
    def __init__(self, url: str = URL, cache: Path | None = CACHE, timeout: float = 90.0, offline: bool = False):
        self.url, self.cache, self.timeout, self.offline = url, cache, timeout, offline
        self.sid: str | None = None
        self.server: dict = {}
        self.instructions = ""
        self._id = 0
        if cache is not None:
            cache.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------- transport
    def _post(self, msg: dict) -> list[dict]:
        headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream",
                   "MCP-Protocol-Version": PROTOCOL, "User-Agent": "eva-trend-detective/0.1"}
        if self.sid:
            headers["Mcp-Session-Id"] = self.sid
        req = urllib.request.Request(self.url, data=json.dumps(msg).encode(), headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            sid = r.headers.get("Mcp-Session-Id")
            if sid:
                self.sid = sid
            return parse_messages(r.read().decode("utf-8"), r.headers.get("Content-Type", ""))

    def _request(self, method: str, params: dict | None = None) -> dict:
        self._id += 1
        msg = {"jsonrpc": "2.0", "id": self._id, "method": method}
        if params is not None:
            msg["params"] = params
        for m in self._post(msg):
            if m.get("id") == self._id:
                if "error" in m:
                    raise MCPError(f"{method}: {m['error']}")
                return m.get("result", {})
        raise MCPError(f"{method}: no answer")

    def connect(self) -> None:
        if self.sid:
            return
        res = self._request("initialize", {"protocolVersion": PROTOCOL, "capabilities": {},
                                           "clientInfo": {"name": "eva-trend-detective", "version": "0.1"}})
        self.server = res.get("serverInfo", {})
        self.instructions = res.get("instructions", "")
        self._post({"jsonrpc": "2.0", "method": "notifications/initialized"})

    # ----------------------------------------------------------------- tools
    def list_tools(self) -> list[dict]:
        self.connect()
        return self._request("tools/list").get("tools", [])

    def call(self, tool: str, **args) -> dict:
        """Call a tool; the answer (its structured content) is cached by tool and arguments."""
        args = {k: v for k, v in args.items() if v is not None}
        key = hashlib.sha1(json.dumps([tool, args], sort_keys=True).encode()).hexdigest()[:20]
        path = self.cache / f"{tool}-{key}.json" if self.cache is not None else None
        if path is not None and path.exists():
            return json.loads(path.read_text())
        if self.offline:
            raise MCPError(f"offline and not cached: {tool} {args}")
        res = None
        for attempt in range(3):
            try:
                self.connect()
                res = self._request("tools/call", {"name": tool, "arguments": args})
                break
            except urllib.error.HTTPError as e:
                if e.code in (400, 404) and self.sid:  # the session expired: open a new one
                    self.sid = None
                elif e.code not in (429, 500, 502, 503, 504) or attempt == 2:
                    raise
                time.sleep(2 * (attempt + 1))
            except (urllib.error.URLError, TimeoutError):
                if attempt == 2:
                    raise
                time.sleep(2 * (attempt + 1))
        if res is None:
            raise MCPError(f"{tool}: no answer")
        if res.get("isError"):
            text = " ".join(c.get("text", "") for c in res.get("content", []))
            raise MCPError(f"{tool}: {text[:500]}")
        data = res.get("structuredContent")
        if data is None:
            data = json.loads(res["content"][0]["text"])
        if path is not None:
            path.write_text(json.dumps(data))
        return data

    # --------------------------------------------------- the tools, by name
    def keywords(self, query: str, scheme: str | None = "sciencekeywords", limit: int = 10) -> list[dict]:
        return self.call("get_keywords", query=query, scheme=scheme, limit=limit).get("keywords", [])

    def collections(self, **kw) -> list[dict]:
        return self.call("get_collections", **kw).get("collections", [])

    def granules(self, collection_concept_id: str, **kw) -> dict:
        return self.call("get_granules", collection_concept_id=collection_concept_id, **kw)

    def variables(self, collection_concept_id: str | None = None, keyword: str | None = None, limit: int = 10,
                  **kw) -> list[dict]:
        return self.call("get_variables", collection_concept_id=collection_concept_id, keyword=keyword,
                         limit=limit, **kw).get("variables", [])

    def citations(self, collection_concept_id: str, limit: int = 5) -> list[dict]:
        return self.call("get_citations", collection_concept_id=collection_concept_id, limit=limit).get("citations", [])
