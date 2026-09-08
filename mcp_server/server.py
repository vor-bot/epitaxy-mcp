"""MCP server for the epitaxy API. Stdio transport, standard library only.

US federal drug shortages and recalls joined to the federal contracts
that buy those drugs. The free tier needs no key and no signup, so this
server answers straight after installation.

Run it:
    epitaxy-mcp
    python3 -m mcp_server.server

Environment:
    EPITAXY_API_URL   API base, defaults to https://drugs.crossgrain.xyz
    EPITAXY_API_KEY   optional, without it the free tier is used
"""

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

API_URL = os.environ.get("EPITAXY_API_URL", "https://drugs.crossgrain.xyz")

# Fallback for the window in which the custom domain has no certificate
# yet. Harmless once it does, so it stays.
FALLBACK_URL = os.environ.get(
    "EPITAXY_API_FALLBACK_URL",
    "https://api-production-16c2.up.railway.app")
API_KEY = os.environ.get("EPITAXY_API_KEY")
VERSION = "0.1.4"
USER_AGENT = "epitaxy-mcp/%s" % VERSION
PROTOCOL_VERSION = "2025-06-18"

TOOLS = [
    {
        "name": "get_data_freshness",
        "description": ("Returns when the data was last activated, how many "
                        "segments are live, and the state of the last run. "
                        "Call this first when you need to know whether the "
                        "data is fresh."),
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "list_drug_shortages",
        "description": ("Current and resolved US drug shortages as reported "
                        "by the FDA. Each row carries the generic name, the "
                        "reporting company and its company_id. Filters: "
                        "status, generic_name, company_id, limit."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "status": {"type": "string",
                           "description": "for example Current or Resolved"},
                "generic_name": {"type": "string"},
                "company_id": {"type": "string"},
                "limit": {"type": "integer"},
            },
        },
    },
    {
        "name": "list_drug_recalls",
        "description": ("FDA drug recalls and enforcement reports. Filters: "
                        "classification (Class I, II, III), company_id, "
                        "limit."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "classification": {"type": "string"},
                "company_id": {"type": "string"},
                "limit": {"type": "integer"},
            },
        },
    },
    {
        "name": "list_federal_drug_contracts",
        "description": ("US federal contracts for drugs, product service "
                        "code 6505, from USAspending. Filters: agency, "
                        "company_id, limit."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "agency": {"type": "string"},
                "company_id": {"type": "string"},
                "limit": {"type": "integer"},
            },
        },
    },
    {
        "name": "get_supplier_exposure",
        "description": (
            "The join: a federal contract whose supplier has an FDA shortage "
            "or recall. Every row carries company_name, confidence (exact, "
            "probable or weak) and match_method. A cross source join is "
            "NEVER exact, because FDA and USAspending share no identifier. "
            "The claim is: this government supplier has an active FDA "
            "shortage or recall. It does NOT claim that this contract "
            "delivers that drug. Without a key you get exact and probable "
            "matches only, at most 20 rows, without the evidence field."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "award_id": {"type": "string",
                             "description": "federal award identifier"},
                "company_id": {"type": "string"},
                "min_confidence": {"type": "string",
                                   "enum": ["probable", "weak"],
                                   "description": "weak needs a paid key"},
                "limit": {"type": "integer"},
            },
        },
    },
]


TOOL_PATHS = {
    "get_data_freshness": "/v1/meta",
    "list_drug_shortages": "/v1/shortages",
    "list_drug_recalls": "/v1/recalls",
    "list_federal_drug_contracts": "/v1/contracts",
    "get_supplier_exposure": "/v1/exposure",
}


def _fetch(base, path, query):
    url = "%s%s%s" % (base, path, ("?" + query) if query else "")
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if API_KEY:
        headers["X-API-Key"] = API_KEY
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def call_api(path, params):
    query = urllib.parse.urlencode(
        dict((k, v) for k, v in params.items() if v not in (None, "")))
    bases = [API_URL]
    if FALLBACK_URL and FALLBACK_URL != API_URL:
        bases.append(FALLBACK_URL)
    last = None
    for base in bases:
        try:
            return _fetch(base, path, query)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", "replace")
            try:
                return json.loads(body)
            except ValueError:
                return {"error": "http_%d" % exc.code, "body": body[:500]}
        except Exception as exc:
            last = exc
    return {"error": "network", "message": str(last)[:200]}


def handle(message):
    method = message.get("method")
    request_id = message.get("id")

    if method == "initialize":
        return {
            "jsonrpc": "2.0", "id": request_id,
            "result": {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "epitaxy", "version": VERSION},
                "instructions": (
                    "US federal drug shortages and recalls joined to the "
                    "federal contracts that buy those drugs. Always read "
                    "the confidence field. No key needed, the free tier "
                    "is on and needs no signup."),
            },
        }
    if method in ("notifications/initialized", "notifications/cancelled"):
        return None
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": TOOLS}}
    if method == "tools/call":
        params = message.get("params", {})
        name = params.get("name")
        path = TOOL_PATHS.get(name)
        if not path:
            return {"jsonrpc": "2.0", "id": request_id,
                    "error": {"code": -32601, "message": "neznamy nastroj"}}
        result = call_api(path, params.get("arguments") or {})
        return {
            "jsonrpc": "2.0", "id": request_id,
            "result": {
                "content": [{"type": "text",
                             "text": json.dumps(result, ensure_ascii=False)}],
                "isError": bool(result.get("error")),
            },
        }
    return {"jsonrpc": "2.0", "id": request_id,
            "error": {"code": -32601, "message": "neznama metoda %s" % method}}


def main(argv=None):
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except ValueError:
            continue
        response = handle(message)
        if response is not None:
            sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
