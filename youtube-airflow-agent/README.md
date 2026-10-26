# YouTube Comment AI Agent — Airflow + Telegram

**[Tiếng Việt](README.vi.md) | [English](README.en.md)**

Monitor new **public** YouTube comments on [@ydang7076](https://www.youtube.com/@ydang7076) every 12 hours and notify a Telegram chat. OpenAI-based question classification and draft replies are optional. This project is a local **MVP / proof of concept**, not a hosted service. It does not automatically reply to YouTube comments or read private YouTube messages.

**Architecture:** YouTube Data API v3 → Airflow DAG (00:00 / 12:00 ICT) → SQLite deduplication → optional OpenAI analysis → Telegram Bot API.

**Status:** Tested locally using Airflow + Docker; an earlier user run fetched 399 public comment records and a Telegram test message was received. **Delivery of a real new-comment notification remains unverified.** A green Airflow task without a Telegram notification is not proof of a live alert; see the troubleshooting section in the guides.

## Quick commands (PowerShell)

```powershell
# From the folder containing docker-compose.yaml
Copy-Item .env.example .env  # first setup only
notepad .env                  # add your own secrets; NEVER commit this file

docker compose up -d          # start/restart

docker compose ps             # status

docker compose stop           # stop Airflow; keeps database/state

docker compose exec airflow python -m agent.check_connections --send-test

docker compose exec airflow python -m agent.monitor  # manual poll now
```

Open Airflow at <http://localhost:8080> (Docker must be running) and enable `youtube_comment_ai_telegram` if paused. See **[full Vietnamese guide](README.vi.md)** or **[complete English guide](README.en.md)** for Google Cloud API setup, Telegram setup, startup after reboot, auto-start, Airflow login, SQLite permission fix, checking logs, and limitations.

**Privacy:** `.env`, SQLite data and local runtime files are excluded by `.gitignore`. The repository must contain only `.env.example` with **blank** credentials.

## Source tree

```text
youtube-airflow-agent/
├── .env.example                  # example config (no secrets)
├── .gitignore
├── docker-compose.yaml           # local Airflow 3 standalone
├── dags/youtube_comments.py     # schedule: 00:00 and 12:00 Vietnam time
├── agent/monitor.py             # fetch / filter / analyze / notify
├── agent/check_connections.py   # verify APIs and send Telegram test
├── agent/telegram_setup.py      # find numeric Telegram chat ID
├── tests/test_monitor.py        # automated unit tests
├── README.md                    # language selector / quick reference
├── README.vi.md                 # Vietnamese instructions
├── README.en.md                 # English instructions
└── SETUP_VI.md                  # original brief setup notes
```

Docs: [YouTube CommentThreads](https://developers.google.com/youtube/v3/docs/commentThreads/list) · [Telegram Bot API](https://core.telegram.org/bots/api) · [Airflow](https://airflow.apache.org/docs/)

## Optional FAQ auto-reply / Tự trả lời FAQ

Default OFF: approved phrase → fixed reply; Google OAuth 2.0 is required to post. Setup in [Tiếng Việt](README.vi.md#tự-trả-lời-faq-tùy-chọn-mặc-định-tắt) / [English](README.en.md#optional-faq-auto-replies-disabled-by-default). The Airflow schedule stays at 00:00/12:00 Vietnam time.
