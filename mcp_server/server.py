"""MCP server nad epitaxy API. Stdio transport, len stdlib.

Toto je zároveň distribučný kanál číslo 1 aj 2 z research/distribution.md:
zápis do MCP registrov a vlastný open source klient. Balík sa spúšťa
jedným príkazom a funguje bez kľúča, lebo bezplatná vrstva nepotrebuje
registráciu.

Spustenie:
    python3 -m mcp_server.server

Premenné:
    EPITAXY_API_URL   základ API, predvolene https://drugs.crossgrain.xyz
    EPITAXY_API_KEY   nepovinný, bez neho beží bezplatná vrstva
"""

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

API_URL = os.environ.get("EPITAXY_API_URL", "https://drugs.crossgrain.xyz")

# Zaloha na obdobie, kym Railway vyda certifikat pre subdomenu.
# Klient tak funguje aj v case, ked domena este nebezi. Az certifikat
# bude, zaloha sa moze odstranit, ale skodit nebude ani potom.
FALLBACK_URL = os.environ.get(
    "EPITAXY_API_FALLBACK_URL",
    "https://api-production-16c2.up.railway.app")
API_KEY = os.environ.get("EPITAXY_API_KEY")
USER_AGENT = "epitaxy-mcp/0.1.3"
PROTOCOL_VERSION = "2025-06-18"

TOOLS = [
    {
        "name": "get_data_freshness",
        "description": ("Vrati cas poslednej aktivacie dat, pocet zivych "
                        "segmentov a stav posledneho behu. Volaj to prve, "
                        "ked chces vediet, ci su data cerstve."),
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "list_drug_shortages",
        "description": ("Vypadky liekov podla FDA. Filtre: status, "
                        "generic_name, company_id, limit."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "status": {"type": "string"},
                "generic_name": {"type": "string"},
                "company_id": {"type": "string"},
                "limit": {"type": "integer"},
            },
        },
    },
    {
        "name": "list_drug_recalls",
        "description": "Stiahnutia liekov podla FDA. Filtre: classification, company_id, limit.",
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
        "description": ("Federalne kontrakty na lieky, PSC 6505. "
                        "Filtre: agency, company_id, limit."),
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
            "Spojenie kontraktu s vypadkom alebo stiahnutim. KAZDY riadok "
            "nesie confidence exact, probable alebo weak a match_method. "
            "Cross source spojenie NIKDY nie je exact, lebo medzi FDA a "
            "USAspending neexistuje spolocny identifikator. Tvrdenie znie: "
            "tento dodavatel vlady ma u FDA aktivny vypadok alebo "
            "stiahnutie. NETVRDI, ze konkretny kontrakt dodava konkretny "
            "liek. Bez kluca sa vracaju len exact a probable zhody, "
            "najviac 20 riadkov, bez evidence."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "award_id": {"type": "string"},
                "company_id": {"type": "string"},
                "min_confidence": {"type": "string",
                                   "enum": ["probable", "weak"]},
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
                "serverInfo": {"name": "epitaxy", "version": "0.1.3"},
                "instructions": (
                    "Data o vypadkoch a stiahnutiach liekov spojene s "
                    "federalnymi kontraktmi. Vzdy citaj pole confidence."),
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
