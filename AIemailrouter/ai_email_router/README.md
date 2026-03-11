# AI Email Router

## Usage Guide (Step by Step)

### Step 1: Install Python

- **Windows:** Download from [python.org](https://www.python.org/downloads/), run the installer, tick **Add Python to PATH**, then finish.
- **Mac:** Usually pre-installed. If not, run: `brew install python3`.
- Verify: open Terminal/CMD, type `python --version` (or `python3 --version` on Mac). You should see a version number.

### Step 2: Get API Key

- Sign up at [platform.openai.com](https://platform.openai.com), get your key at [api-keys](https://platform.openai.com/api-keys). You will paste this key into the **OpenAI API Key** field in the app (Step 4).

### Step 3: Run the App

- **Windows:** Double-click `run.bat`.
- **Mac:** Open Terminal, run:
  ```
  cd ai_email_router
  chmod +x run.sh
  ./run.sh
  ```
  (First time only: `chmod +x`. After that, just `./run.sh`.)

### Step 4: Use the App (paste key into the API key field)

1. **Paste your API key into the OpenAI API Key field** (top of the window).
2. Paste emails into **Email Inputs** (one per line).
3. Click **Analyze Emails**.
4. View results in **Classification Results** and in `email_classification_results.json`.

### Step 5 (optional): Send to Telegram

**How to create a Bot Token (via BotFather)**

1. Open **Telegram** (phone or desktop).
2. In the search bar at the top, type **@BotFather** and open the chat (choose the one with the blue checkmark).
3. Type **`/newbot`** (with the slash) and send.
4. BotFather asks for a name. Type any name, e.g. **AI Email Router**, then Enter.
5. BotFather asks for a username. It must end with `bot`, e.g. **ai_email_router_bot**, then Enter.
6. BotFather replies with a long token like `123456789:ABCdef...`. That is your **Bot Token**. Copy it.
7. Paste this token into the **Bot Token** field when you click **Send to Telegram** in the app.

**How to get your Telegram ID (recipient)**

1. Open **Telegram** and search for **@userinfobot**.
2. Open the chat with @userinfobot (the one named "User Info • Get ID • idbot").
3. Type **`/start`** and send.
4. The bot replies with **Id: 5193898256** (your number will be different). That number is your **Telegram ID**.
5. Copy this number and paste it into the **recipient** field in the app.

**Before sending:** The recipient must open your bot (e.g. t.me/ai_email_router_bot) and type **`/start`** first. Otherwise the bot cannot send them messages.

**Send from the app:** Click **Send to Telegram**, fill: (1) Bot Token, (2) Content, (3) Recipient (Telegram ID or username), then click **Send**.

---

## Overview

Desktop app that reads emails, uses an LLM to classify intent, and routes them to the correct department (sales, support, billing, spam, other).

## Project Structure

```
ai_email_router/
├── app.py
├── run.bat      ← Windows: double-click to run
├── run.sh       ← Mac: ./run.sh to run
├── config.py
├── email_classifier.py
├── ui.py
├── requirements.txt
└── README.md
```

## Output JSON

```json
[
  {"email": "Hello, I want to buy your product", "category": "sales"},
  {"email": "My account is not working", "category": "support"}
]
```
