# YouTube AI Agent — English Guide

**[Tiếng Việt](README.vi.md) | [Home](README.md)**

## 1. What it does (and does not do)

Monitors **public** comments for [@ydang7076](https://www.youtube.com/@ydang7076) at **00:00 and 12:00 Vietnam time (UTC+7)**, delivering new comments to a Telegram chat. Optional OpenAI analysis classifies likely questions and drafts a proposed response for a human to review. By default the agent **does not post replies automatically**; an opt-in, approved-FAQ posting mode requires channel-owner OAuth. The agent does not access YouTube private messages, guarantee all replies in old threads, or see comments held for moderation using a public API key.

**Architecture:** YouTube Data API v3 → Apache Airflow scheduler → SQLite deduplication → optional OpenAI analysis → Telegram Bot API.

This is a **local-development MVP** and requires a running computer/Docker Engine. An Airflow task marked `Success` can still report `notified: 0`: successful polling does not automatically mean that a new Telegram alert was sent.

## 2. Requirements and secrets

- Windows 11 and Docker Desktop (Linux containers + Compose), or Linux Docker Engine.
- A Google Cloud project with **YouTube Data API v3** enabled and an API Key restricted to this API.
- A Telegram bot created with [@BotFather](https://t.me/BotFather), its private token, and a numeric Telegram Chat ID. Open your bot chat and press **Start**.
- Optional OpenAI API Key for question classification/draft replies. Without it, the basic heuristic is used and all comments still notify if `NOTIFY_ALL_COMMENTS=true`.

Never commit your `.env`, Airflow admin password, bot token, Google/OpenAI keys, or SQLite database. `.gitignore` blocks `.env`; the public `.env.example` intentionally has **no secrets**.

## 3. First-time installation (PowerShell)

```powershell
cd "E:\AI\youtube\youtube-airflow-agent"  # adjust if your folder is elsewhere
Copy-Item .env.example .env
notepad .env
```

Set these variables in your **local** `.env`:

```dotenv
YOUTUBE_CHANNEL_URL=https://www.youtube.com/@ydang7076
YOUTUBE_API_KEY=YOUR_PRIVATE_GOOGLE_API_KEY
TELEGRAM_BOT_TOKEN=YOUR_PRIVATE_TELEGRAM_TOKEN
TELEGRAM_CHAT_ID=YOUR_NUMERIC_CHAT_ID
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4.1-mini
NOTIFY_ALL_COMMENTS=true
MAX_PAGES=3
INITIAL_LOOKBACK_MINUTES=720
```

To create a YouTube API Key: [Google Cloud](https://console.cloud.google.com/projectcreate) → Create Project → [YouTube Data API v3](https://console.cloud.google.com/apis/library/youtube.googleapis.com) → Enable → [Credentials](https://console.cloud.google.com/apis/credentials) → Create credentials → API Key. Restrict the key to the **YouTube Data API v3**. Public comment reads do not require YouTube account OAuth.

To create a Telegram bot: open [BotFather](https://t.me/BotFather), send `/newbot`, choose a name and unique username ending in `bot`, save its private token, then open the bot chat and press **Start**. Once running, you can discover a chat ID with:

```powershell
docker compose exec airflow python -m agent.telegram_setup
```

Start the stack with `docker compose up -d`. After modifying `.env`, reload container environment variables using `docker compose up -d --force-recreate`.

## 4. Start on Windows (including after reboot)

1. Launch **Docker Desktop**, wait until **Engine running**.
2. Open PowerShell in the project directory containing `docker-compose.yaml`.
3. Run:

```powershell
cd "E:\AI\youtube\youtube-airflow-agent"
docker compose up -d
docker compose ps
```

4. Open <http://localhost:8080> on that PC. The Airflow standalone admin username is `admin`; retrieve the automatically generated password locally (never paste it publicly):

```powershell
docker compose logs airflow | Select-String "password"
docker compose exec airflow cat /opt/airflow/simple_auth_manager_passwords.json.generated
```

5. Find and **Unpause** the `youtube_comment_ai_telegram` DAG if necessary. Its `schedule="0 */12 * * *"` uses `Asia/Ho_Chi_Minh`.

**No need to recreate YouTube or Telegram credentials after a reboot.** The Compose file sets `restart: unless-stopped`, so containers may restart automatically as Docker Engine starts; verify with `docker compose ps` and run `docker compose up -d` if needed.

## 5. Stop, restart, and auto-start

```powershell
# Stop without deleting the SQLite database
docker compose stop

# Start again
docker compose up -d

# Inspect
docker compose ps

docker compose logs --tail=100 airflow
```

To stop only the scheduled polling while retaining the UI, **Pause** the `youtube_comment_ai_telegram` DAG; **Unpause** to resume. Closing a browser tab does not stop Airflow. Powering off or suspending the computer does stop scheduled execution. **Do not use `docker compose down -v`**: the `-v` option removes volumes and can destroy SQLite state and Airflow settings. `docker compose down` *without* `-v` keeps named volumes.

For automatic startup after logging into Windows: Docker Desktop → Settings → General → **Start Docker Desktop when you sign in**; verify `docker compose ps` after startup. Use `docker compose up -d` if required. For true 24/7 notifications when the PC is off, host the agent on an always-on server/VPS.

## 6. Verify connectivity and real comments

```powershell
# Test YouTube lookup, Telegram authentication, and send a test message
docker compose exec airflow python -m agent.check_connections --send-test

# Poll YouTube immediately without waiting for the 12-hour schedule
docker compose exec airflow python -m agent.monitor

# Run offline automated unit tests (Python on host)
python -m unittest discover -s tests -v
```

Alternatively, Airflow UI → DAG → **Trigger** for a manual run. Inspect **Task Instances → poll_analyze_notify → Logs**. `fetched` counts comment objects returned by a run; `notified` counts messages sent during that run. For example `fetched: 399, notified: 0` means data was retrieved but no alerts were issued. A successful Telegram test proves only the outbound Telegram connection.

For a live end-to-end test, post a **new public top-level comment** to an existing public video from a second YouTube account (do not reply to an old thread), confirm YouTube displays it publicly, then trigger/poll and check logs and Telegram. Newly posted comments can be delayed by indexing or moderation.

## 7. Troubleshooting

| Symptom | Recommended step |
| --- | --- |
| `docker` not recognized | Install Docker Desktop and restart PowerShell |
| Docker daemon unavailable | Start Docker Desktop and wait for `Engine running`; run `docker info` |
| Can't open `localhost:8080` | `docker compose ps`; `docker compose logs --tail=100 airflow` |
| `OperationalError: unable to open database file` | Correct persistent SQLite volume permissions using the command below |
| Airflow success but no Telegram alert | Check `notified`; if zero, inspect the comment time, API coverage, and whether the comment is public |
| Telegram test passes, real comment missing | Poll manually after posting a top-level public comment; check results and API visibility |
| Telegram `404` | Verify Bot Token, exact format, and bot creation |

The SQLite write-permission repair used on the original Windows development machine:

```powershell
docker compose exec --user root airflow sh -c "chown -R 50000:0 /opt/airflow/state && chmod -R ug+rwX /opt/airflow/state"
```

The database lives at `/opt/airflow/state/comments.sqlite3` in the persistent `agent_state` volume. Fix permissions rather than deleting the volume.

## 8. Functional and operational limitations

- Uses `commentThreads.list`, limited to the newest `MAX_PAGES × 100` **comment threads** per run. Replies may be partial, and new replies in old, unreturned threads can be missed. Prolonged downtime or heavy comment traffic may also cause missed alerts.
- `INITIAL_LOOKBACK_MINUTES=720` sets the **first-run** historical cutoff, which is persisted in SQLite. It is **not** a rolling 12-hour lookback for every later run.
- IDs are stored to avoid repeat alerts; after a crash between Telegram delivery and SQLite insertion, rare duplicates remain possible.
- Public API keys do **not** access YouTube private messages or moderation-held comments. The MVP does **not** auto-reply by default; opt-in owner-approved FAQ posting requires OAuth.
- When an OpenAI API Key is configured, comment text is sent to OpenAI for analysis. Review data/privacy policies for your deployment.
- `airflow standalone` is appropriate for a personal demo/prototype, **not production-grade secured hosting**.

References: [YouTube CommentThreads API](https://developers.google.com/youtube/v3/docs/commentThreads/list) · [Telegram Bot API](https://core.telegram.org/bots/api) · [Apache Airflow](https://airflow.apache.org/docs/)


## Optional FAQ auto-replies (DISABLED BY DEFAULT)

Auto-replies are restricted to **new public top-level comments**, matching exactly one owner-approved phrase rule in `config/faq_rules.json`. The public reply is the predefined FAQ answer, **never unconstrained AI-generated text**. Non-matches continue to be notified on Telegram. By default, only comments younger than 24 hours qualify and at most three posts per polling run are attempted. Replies inside existing threads are not auto-answered.

**Posting requires channel-owner OAuth 2.0; a read-only API key is insufficient.**

1. In the same Google Cloud project, configure the Google Auth Platform/OAuth consent screen and add yourself under Test users if Testing; create an OAuth **Desktop application** client. Save the downloaded JSON only on your PC as `secrets/client_secret.json`.
2. From the project directory on Windows (Python 3 required), run `python -m agent.oauth_setup`. Grant authorization using the Google account/channel that manages `@ydang7076`. The script writes a private `secrets/youtube_oauth.json` refresh-token file.
3. Populate `config/faq_rules.json`, e.g. `{"rules":[{"id":"thanks","triggers":["cảm ơn ad","cảm ơn bạn đã chia sẻ"],"reply":"Cảm ơn bạn đã xem video và ủng hộ kênh!"}]}`. Initially `{"rules":[]}`, so nothing is eligible.
4. Edit local `.env`: `AUTO_REPLY_ENABLED=true` and leave `AUTO_REPLY_DRY_RUN=true` for a **log-only dry run**. Reload: `docker compose up -d --force-recreate`. Once an eligible comment logs `DRY RUN` and you approve the wording, set `AUTO_REPLY_DRY_RUN=false`, then recreate containers again.
5. To stop public posting, set `AUTO_REPLY_ENABLED=false` and recreate. The 12-hour Airflow schedule does not change.

A network error after posting is treated as uncertain and is **never automatically retried**, preventing duplicate public responses. Attempts are stored in SQLite table `reply_attempts`. YouTube `comments.insert` costs 50 quota units per reply. OAuth Testing-mode refresh tokens may expire after seven days; reauthorize when needed. **Do not commit** `secrets/`, `.env`, or any token. See [YouTube comments.insert](https://developers.google.com/youtube/v3/docs/comments/insert).
