# Server deployment, operations and rollback

This is a reproducible deployment plan for an **authorized prototype server**. No bank/cloud server has been provisioned or deployed by committing these files.

## Local Docker

Install Docker Engine/Desktop with Compose. From `mms-ai-checker`:

```bash
cp .env.example .env
docker compose config --quiet
docker compose up --build -d
docker compose ps
curl --fail http://127.0.0.1:8000/healthz
```

PowerShell: use `Copy-Item .env.example .env` and `curl.exe` if needed. Local UI is `http://127.0.0.1:8000`. The published port binds only loopback. Model calls need outbound connectivity in Gemini mode. The named volume keeps snapshots and uploads across container replacements. `docker compose down` retains it; **do not use `down -v` unless deliberately discarding all demo data**.

## Prepare an authorized server

1. Use a dedicated deployment checkout of `ydangishere/dev-projects`, Docker/Compose and a TLS reverse proxy. Do not deploy from a personal dirty checkout.
2. Review the security gaps in `SECURITY.md`. This app is a prototype with demo seed data and token mapping, not a ready bank service. Integrate bank SSO and storage contracts before real data.
3. Keep `.env` outside Git with restricted file permissions, or inject from a secret manager. Configure `AI_MODE`, `GEMINI_MODEL`, `GEMINI_API_KEY` and `DATA_DIR`. The app's production gate requires strong configured tokens; this does not replace SSO.
4. For a private prototype, generate a random token, e.g. `python -c "import secrets; print(secrets.token_urlsafe(48))"`, then set `TOKENS_JSON` to a JSON object mapping that secret to `{ "user": "reviewer-1", "tenant": "pvcb", "role": "checker" }`. Set `APP_ENV=production`. Never copy this value into README/logs/model context.
5. Set `ALLOWED_HOSTS=localhost,127.0.0.1,YOUR_ACTUAL_HOST`. Configure proxy Host forwarding, HTTPS, connection/body/read timeouts and distributed rate limits; allowlist outbound model/approved bank origins at the firewall. Existing app process limits do not replace gateway controls.
6. Enable encrypted disk/volume and backups. No DB encryption or cloud KMS is built into this prototype. Set access to the `/data` volume and audit exports appropriately.

## Deployment steps

On a clean dedicated clone, record the previous deployed SHA and build an immutable image tag for the reviewed new SHA:

```bash
git fetch origin
git checkout REVIEWED_COMMIT_SHA
cd mms-ai-checker
docker build -t mms-ai-checker:REVIEWED_COMMIT_SHA .
docker compose up --build -d
curl --fail http://127.0.0.1:8000/healthz
```

The example `REVIEWED_COMMIT_SHA` is a placeholder, not a literal branch. Compose builds the current checkout; retain the immutable image tag and SHA as release evidence. Start with demo data, log in with your configured identity, run a check, inspect source/evidence, upload a replacement, confirm staleness and verify denied cross-tenant access. For a live Gemini test, use synthetic PDF/images and inspect model results before any real documents.

Do not use the demo-only smoke script with custom production tokens: it intentionally authenticates using the public demo token. CI runs it only in the isolated default demo container. For a configured deployment, test the same API with the configured identity over TLS.

## CI and CD boundaries

`.github/workflows/mms-ai-checker.yml` at the monorepo root runs lint, tests, synthetic evaluation, `pip-audit`, Docker build and container HTTP smoke for this folder. It needs no AI secret and never runs untrusted PR code with production credentials. The workflow does not publish a container registry image or deploy to a server. A push adds the workflow; check the actual run outcome in Actions, including permissions or infrastructure failures.

CD is manual here because no target server/registry/SSO has been supplied. To automate later, publish tested immutable image digests to an approved registry and use workload identity or an approved deployment agent, environment gates, scoped secrets, health checks and rollback. Do not place bank SSH/API secrets into this public repository.

## Readiness and monitoring

`/healthz` verifies the process can query SQLite. It returns demo/Gemini mode and configured model ID, but **does not call Gemini**. A healthy process can still have a wrong API key, upstream quota failure or bad model ID.

The result `events` captures failed extraction, explanation fallback and selected suspicious input events. Audit stores upload/check/evidence/download/feedback events with actor and tenant; check records preserve model ID, policy hash and timestamp. No Prometheus/OpenTelemetry exporter, cost dashboard or alert router is configured.

Production metrics should include requests/errors/429s, p50/p95 stage duration, extraction failure, fallback rate, field/source accuracy on reviewed samples, false-clean rate, feedback disagreements, model tokens/cost, disk usage and backup freshness. Send metadata to controlled central logging without document content or credentials. Test alerts with a model timeout and a full-disk scenario.

## Backup and restore

Use SQLite's consistent backup API rather than copying a changing DB file. Example inside the running container:

```bash
docker compose exec checker python -c "import sqlite3; source=sqlite3.connect('/data/checker.sqlite3'); target=sqlite3.connect('/data/backup.sqlite3'); source.backup(target); target.close(); source.close()"
docker compose cp checker:/data/backup.sqlite3 ./backup.sqlite3
```

Move the backup to approved encrypted storage; it contains uploaded source documents and audit data. Test restore in a separate disposable environment, confirm application/check/evidence consistency, then document recovery time and retention. Restore to production only during an authorized maintenance window; do not overwrite a live DB.

## Rollback

Record previous Git SHA/image tag and preserve a consistent backup before deployment. In the dedicated deployment checkout, check out the previous reviewed SHA, rebuild/restart and verify health plus an authenticated sample check. Prefer immutable digest deployment in the future. Avoid deleting the named data volume.

This version uses `CREATE TABLE IF NOT EXISTS` only; there are no destructive migrations. Future schema changes need versioned forward/backward-compatible migrations and restore rehearsals; reverting code alone may not roll back data semantics.

## Hướng dẫn ngắn tiếng Việt

Chạy trên máy cá nhân bằng Docker Compose, truy cập cổng localhost. Triển khai lên server được cấp phép cần bản code đã kiểm thử, domain/TLS, khóa giữ ngoài Git, phân quyền thật, sao lưu và kiểm tra model bằng giấy tờ giả lập. Nhật ký và health check đã có ở mức cơ bản; dashboard chi phí/cảnh báo và kết nối ngân hàng chưa có. Quay lại bản cũ theo Git SHA/image đã ghi nhận, giữ nguyên volume dữ liệu và kiểm tra lại API sau khi chạy.
