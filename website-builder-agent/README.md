# Website Builder Agent — working local MVP

This is a **local workflow control center**, not a fully integrated autonomous production agent. It tracks requirements, concepts, reviews, approvals and artifacts across nine stages. It can optionally send review emails via SMTP, post announcements to a Google Chat space webhook, call OpenAI/Anthropic model APIs, and run an installed Codex CLI on local source files.

## Start on Windows 11
1. Install Python 3.11+ from python.org (`py -3 --version`).
2. Clone this repository. In PowerShell: `cd dev-projects\vietpay-agent` then `powershell -ExecutionPolicy Bypass -File .\start.ps1`.
3. Open http://127.0.0.1:8000. Stop with Ctrl+C.
4. (Optional) Edit `.env` to supply model API keys, SMTP credentials, Google Chat incoming webhook, Figma link, or approved document URL. **Do not share .env or API keys.**
5. (Optional) Install and authenticate Codex CLI separately; it must be on PATH for the Codex Execute control.

Linux/macOS: `bash start.sh`.

## Nine-stage process
1. Register approved `design_system` artifact (from Figma/Claude or elsewhere).
2. Register `requirements` source URL, add ALL reviewers, open a review round, send invite manually, collect explicit decisions. Optional one-by-one reminders capped at 3 across channels.
3. Generate distinct Claude and GPT concepts (or import existing concepts), register the chosen `selected_concept` and open a Figma review round with the Figma URL. Figma frame creation/comments synchronization is **not yet implemented**; record decisions manually.
4. Run Codex to build scaffold. Register `scaffold` artifact.
5. Open scaffold review round with its Figma URL, and collect member decisions.
6. Run Codex on the desktop design; register `desktop`, open desktop review round, collect decisions.
7. Run Codex for mobile based on desktop; register `mobile`.
8. Run QA and corrective Codex passes across 320/375/390/488/768/1024/1280/1440; particularly test hero overflow, line wrapping and image focal area; register `qa_report`, open QA review and collect decisions.
9. Run approved GitHub Pages deployment tasks manually, register `demo_url`. Backend/API is out of scope for this orchestrator and has a separate handoff. Do **not** put secrets in GitHub Pages.

**Gate rules:** Current step is stored in SQLite. Steps 2,3,5,6,8 need a review round with 100% active responses and no outstanding `changes_requested`. Approval is not inferred from comments or silence. Explicitly click “Verify gates & advance”. Steps 1,3,4,6,7,8 also require artifacts. Optional reminders are user-initiated, not scheduled.

## What is implemented versus not yet wired
Implemented: persistent SQLite audit log, artifact capture, reviewer response state, hard approval gates, manual invite and reminders (SMTP/Chat configurable), independent GPT/Claude calls, opt-in Codex CLI execution, state JSON export, responsive dashboard.

Not implemented: OAuth/Google Docs comment ingestion, Google Chat direct messages, automatically scheduled reminders, Figma design writes/comment ingestion, website visual-regression screenshots, GitHub automated publish, Sanity content deployment, full backend-agent handoff, authentication/multi-user web access. The local UI must **not** be exposed to the internet without authentication, role permissions, CSRF protection, job queue and secret management.

## Safety and operational notes
- Reviewer responses are recorded by the operator. Their identity is NOT authenticated in this MVP. Do not use them as formal authorization evidence.
- SMTP sends individual emails when clicked, Google Chat webhook posts to a space (not individual DMs). Failed sends are not counted as reminders.
- Codex `--full-auto` can alter files within the working site; keep the site under version control, review diffs and don't run untrusted instructions. Codex CLI authentication is separate from model API keys.
- API docs available at `/api`, state export `/export`; SQLite at `workspace/agent.sqlite3`. Back up the database and `workspace/site`.
- Requirements source is `VietPay_Website_Additional_Requirements_En`, including 6 requirements groups, VI/EN launch, Next.js + Sanity decision and no invented product claims.
