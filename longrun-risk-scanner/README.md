# longrun-risk-scanner

Local-first CLI for **long-run Java / Spring Boot risk** review: find **risk candidates** in snippets, files, or whole trees, persist them in SQLite, expand context progressively, optionally verify with an **OpenAI-compatible LLM** using **compact context packs only**, and export **JSON + Markdown** under `scans/`.

Design: conservative, extensible, not a style linter.

## Requirements

- **Python 3.8+** (3.10+ recommended). Tested with pytest on Windows.
- Dependencies: see `requirements.txt`.

## Install

From the project root `longrun-risk-scanner/` (the folder that contains `app/` and `rules/`):

```powershell
cd D:\path\to\longrun-risk-scanner
python -m pip install -r requirements.txt
```

This installs packages **into your active Python environment** (system, venv, or conda). To isolate:

```powershell
cd D:\path\to\longrun-risk-scanner
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## Configuration

Copy `.env.example` to `.env` in the **same directory as `app/` and `rules/`** (project root `longrun-risk-scanner/`). Edit values there or set environment variables.

- **LLM is optional.** If `LLM_ENABLED=false` or no API key, all commands still work; `verify` uses **local** logic only.
- To enable LLM verification: `LLM_ENABLED=true`, set `LLM_API_KEY_ENV` (default `OPENAI_API_KEY`) to the name of an env var that holds your secret, and optionally adjust `LLM_API_BASE`, `LLM_MODEL`.

The tool **never** sends the whole project to the LLM—only a bounded context pack (rule excerpt, snippet, enclosing class/method hints, nearby lines, annotations, clues).

## Rules

Human-editable catalog: `rules/risks.yaml`. Restart not required for code paths that load rules each run (CLI loads rules on each invocation). Edit **signals**, **templates**, and **false_positive_notes** to tune behavior.

## GUI (Tkinter) — pick folder or file

**One-click launch (no need to remember `main.py`):**

- **Windows:** double-click **`CHAY_SCAN.bat`** in the project root (uses `pythonw` so no black CMD window flashes).
- **macOS / Linux:** in Terminal, `cd` to the project root, run `chmod +x CHAY_SCAN.sh` once, then **`./CHAY_SCAN.sh`** — same behavior as the `.bat` (starts `app/scan_gui.py`).

**Manual commands:** `python app/scan_gui.py` or `python app/main.py gui`. Plain `python app/main.py` without a subcommand is **CLI only**, not the GUI.

In the window: paste a path or use **Browse folder** / **Browse .java file**, then **Run scan** — results appear in the lower pane (JSON is still written under `scans/`). After a successful scan, **Verify whole session** and **Verify finding** (enter finding ID) run the same CLI as `verify-scan` / `verify` (local + LLM if `.env` allows).

You need Python built with **Tkinter** (official python.org installers usually include it). If no window appears, run `python app/main.py gui` in a terminal to see errors.

## Usage (terminal)

Run from **`longrun-risk-scanner/`** (project root):

```powershell
cd D:\AI\javacodechecker\longrun-risk-scanner
```

### Scan a file or folder

Ignores `.git`, `target`, `build`, `node_modules`, `.idea`, `.gradle`, `out`.

```powershell
python app/main.py scan --path "D:\your-java-project\src"
```

Creates a **scan session**, writes SQLite (`scans/longrun.db` by default), exports timestamped JSON + Markdown under `scans/`.

### Scan a snippet (line range)

```powershell
python app/main.py scan-snippet --file "src\main\java\com\acme\OrderService.java" --start-line 40 --end-line 70
```

Findings are stored with status **verifying** (candidates to refine with `verify`).

### Verify one finding

```powershell
python app/main.py verify --finding-id 12
```

Expands context (method/class hints, file clues, limited cross-file symbol hits), runs **local** verification, then **LLM** if enabled. Updates status: `new` / `verifying` → `confirmed`, `dismissed`, or stays `verifying` when uncertain.

### Verify all open findings in a session

```powershell
python app/main.py verify-scan --scan-id 3 --min-confidence low
```

Default: only findings in **new** or **verifying**. Use `--status confirmed` to re-verify, etc. Optional `--severity low|medium|high`.

### Report

```powershell
python app/main.py report --scan-id 3
```

Regenerates JSON + Markdown and prints a terminal summary.

### List / show

```powershell
python app/main.py list-findings --scan-id 3 --status verifying
python app/main.py show-finding --finding-id 12
```

## LLM mode

1. Set `LLM_ENABLED=true` in `.env`.
2. Put your API key in the environment variable named by `LLM_API_KEY_ENV` (e.g. user env var `OPENAI_API_KEY` on Windows).
3. `verify` / `verify-scan` will call the OpenAI-compatible **chat completions** API (`LLM_API_BASE` + `/chat/completions`), `response_format: json_object`, low temperature.

On failure (network, auth, invalid JSON), verification **falls back** to local-only.

## Tests

From project root:

```powershell
cd D:\AI\javacodechecker\longrun-risk-scanner
python -m pytest tests -v
```

## Limitations and future work

- **Heuristic** detection (regex + line context), not a full Java compiler; expect false positives—use **verify** and human review.
- Class/method **boundaries** are approximate (signature/brace heuristics).
- **Project** references are light (symbol name grep), not full type resolution.
- Stronger analysis (AST, Spring wiring, dataflow) can plug into `risk_engine` / `context_expander` without changing the storage or CLI contract.

## Architecture (short)

| Module | Role |
|--------|------|
| `rule_loader` | YAML → `RiskRule` |
| `risk_engine` | Candidate findings per rule |
| `file_scanner` / `snippet_scanner` / `project_scanner` | Entry points |
| `context_expander` | Context pack for verify / LLM |
| `verifier` / `llm_verifier` | Local + optional LLM |
| `storage` | SQLite |
| `reporter` | JSON / Markdown / terminal |

This layout is suitable to wrap later in a **Cursor extension** or a small UI without rewriting core logic.

## Adding to the `dev-projects` monorepo

To place this folder inside [ydangishere/dev-projects](https://github.com/ydangishere/dev-projects) without leaking API keys, follow **`MONOREPO.md`** (verify `.env` stays ignored before `git push`).
