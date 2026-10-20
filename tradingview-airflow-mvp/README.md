# TradingView AI Research Automation — Apache Airflow MVP

A fail-closed prototype that receives TradingView alerts, prepares a configurable two-alert trigger, and models an AI research / risk review / Telegram reporting pipeline. **No live trading, no research conclusions, and no Telegram reports are currently executed.**

## End-to-end flow

```text
TradingView alert list (TO BE CONFIGURED)
    |
    v
TradingView webhook (HTTP POST)
    |
    v
FastAPI receiver -> SQLite alert event store
    |
    v
Apache Airflow DAG (poll every 1 minute)
    |
    v
Alert matching:
  - choose any TWO different configured alert IDs
  - either alert may arrive first
  - maximum separation: 4 hours
  - exact allowed alert list and pairing rules: TODO
    |
    +-- Not matched -> stop, await later events
    |
    v
AI Deep News Research (TODO: provider / Codex skill / research criteria)
    |
    v
Evidence check: support and contradict BUY / SELL thesis (TODO)
    |
    v
Deterministic Risk Check (TODO: limits / price / freshness)
    |
    v
Short Telegram report AFTER risk check (TODO: adapter)
    |
    v
Trade execution: DISABLED (no exchange API / real orders)
```

## Architecture and responsibility

- **TradingView:** generates alerts based on rules the user will supply later.
- **FastAPI:** validates webhook JSON, checks shared secret, timestamps and stores events.
- **SQLite:** prototype-only persistent event storage and processed-pair records.
- **Airflow 2.10.5:** scheduled DAG that matches alerts and represents downstream steps.
- **AI research:** intentionally NOT implemented; no claim of integration with Deep Research, Codex research skills, or LangChain.
- **Risk check:** intentionally NOT implemented; execution must never proceed without deterministic validation.
- **Telegram:** report step is placed after risk check; credentials and implementation are pending.
- **Execution:** hard-disabled; this repository cannot place orders.

## User-defined configuration to be supplied later

Edit `config/settings.json`:
- `alert_matching.allowed_alert_ids`: currently empty; user will supply TradingView alert list.
- `alert_matching.enabled`: false until pairing rules are agreed and tested.
- `alert_matching.window_hours`: **4**; order of arrival does not matter.
- `require_same_symbol` and `require_same_side`: placeholder safety defaults, NOT finalized trading rules.
- `ai_research.provider`, `skill`, `sources`, `decision_criteria`: empty.
- `risk_check.rules`: empty.
- `execution.enabled`: false; there is no order execution adapter.

## Quick start (Windows 11 + Docker Desktop)

Requires Docker Desktop running Linux containers, Docker Compose and sufficient RAM (Airflow needs several GB).

```powershell
Copy-Item .env.example .env
# Edit .env and replace WEBHOOK_SECRET with a long random secret.
docker compose up -d --build
docker compose logs airflow
```

- Airflow dashboard: http://localhost:8080 (standalone credentials appear in logs).
- Receiver health check: http://localhost:8000/health
- Airflow DAG: `tradingview_research_pipeline`.
- DAG checks every minute; matching is **disabled until configured**.

### Test webhook locally

```powershell
$secret = (Get-Content .env | Where-Object { $_ -match '^WEBHOOK_SECRET=' }) -replace '^WEBHOOK_SECRET=', ''
$body = @{alert_id='sample_A';symbol='BTCUSDT';side='BUY'} | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "http://localhost:8000/webhook/$secret" -ContentType 'application/json' -Body $body
```

Send `sample_B` similarly. The receiver stores both events; no research is triggered without matching configuration.

### Connect TradingView later

TradingView requires a publicly reachable HTTPS webhook endpoint; `localhost` is not accessible from TradingView. Put a secured HTTPS reverse proxy or tunnel in front of the receiver and use:

```text
https://YOUR_DOMAIN/webhook/YOUR_SECRET
```

Example JSON body:
```json
{"alert_id":"YOUR_ALERT_ID","symbol":"BTCUSDT","side":"BUY"}
```

Do not expose Airflow's web UI to the public internet. Protect the webhook with strong secrets, access controls, rate limiting, replay protection and deduplication before production use.

## Implementation status and limitations

| Step | Status |
| --- | --- |
| Webhook receiver and event persistence | Implemented; not Docker-tested |
| Airflow DAG scaffold | Implemented; not Docker-tested |
| Four-hour, order-independent pair matching | Implemented as a configurable placeholder |
| Specific list and matching semantics | Awaiting user input |
| AI research / LangChain / Codex skills | Not implemented; awaiting user input |
| Evidence quality and BUY/SELL rules | Not implemented |
| Risk validation | Not implemented |
| Telegram short report | Placeholder only |
| Exchange execution | Disabled by design |

**Prototype caveats:** SQLite, minute polling, and naive pair matching are not suitable for production trading. The current pairing logic can reuse one alert across multiple pairs; production must define consumption rules, event IDs, idempotency, deduplication, atomic processing and restart recovery. AI research can take minutes, so signal freshness and market price must be rechecked before any future execution. Do not treat AI-generated research as a guarantee of profitable trades.

## Next milestones

1. User supplies the TradingView alert list and exact pairing logic.
2. Add tests for arrival order, 4-hour boundary, duplicates, conflicting directions and restarts.
3. User selects research skill/provider, evidence sources and decision thresholds.
4. Implement risk rules and Telegram reporting.
5. Paper-trade only after end-to-end testing; live execution requires separate explicit authorization.
