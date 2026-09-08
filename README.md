# epitaxy

mcp-name: xyz.crossgrain/epitaxy

Federal drug shortages and recalls, joined to the federal contracts that
buy those drugs. One call, no signup.

**What it claims:** this government supplier has an active FDA shortage
or recall. **What it does not claim:** that a specific contract supplies
a specific drug. Federal contract descriptions average 47 characters and
almost never name the drug, so we say so instead of pretending otherwise.

## Try it now, no key

```bash
curl https://drugs.crossgrain.xyz/v1/exposure?limit=5
```

## MCP

Remote, nothing to install:

```json
{ "mcpServers": { "epitaxy": { "url": "https://drugs.crossgrain.xyz/v1/mcp" } } }
```

Local, stdio:

```json
{ "mcpServers": { "epitaxy": { "command": "uvx", "args": ["epitaxy-mcp"] } } }
```

Tools: `get_data_freshness`, `list_drug_shortages`, `list_drug_recalls`,
`list_federal_drug_contracts`, `get_supplier_exposure`.

## Read the confidence field, always

| value | meaning |
| --- | --- |
| `exact` | match on a shared identifier, here an NDC inside FDA data |
| `probable` | normalized company name, or a drug name token in the contract text |
| `weak` | anything softer, an indication only |

Matching on both company and drug at once is **not** promoted to
`exact`. Cross source joins are never `exact`, because FDA and
USAspending share no identifier. Anyone claiming otherwise has a
different source or is guessing.

## Free tier

Works forever, no key, no signup. Returns at most 20 rows, without the
`evidence` field, without `weak` matches, and with data delayed by 24
hours. Nothing is stored: no counters, no IP addresses.

## Paid

| plan | price | contents |
| --- | --- | --- |
| Starter | 29 USD/mo | 10 000 calls |
| Pro | 99 USD/mo | 100 000 calls plus daily delta feed |
| x402 | 0.004 USD/call | USDC on Base, no signup |
| Bulk dump | 199 USD | one off, Stripe only |

## Sources and licence

- openFDA, public domain, CC0 1.0 Universal
- USAspending, public domain, code under CC0

Data is unvalidated and must not be used for medical decisions.
This project is MIT licensed. Docs: https://docs.crossgrain.xyz
