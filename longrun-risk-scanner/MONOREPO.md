# Adding this project to [ydangishere/dev-projects](https://github.com/ydangishere/dev-projects)

## Security (API keys)

- **Never commit `.env`.** It is listed in `.gitignore`. Your OpenAI key stays only on your machine.
- Before every push, run from this folder:
  - `git check-ignore -v .env` → should show that `.env` is ignored.
  - `git status` → `.env` must **not** appear as a new file to commit.
- If you ever committed `.env` by mistake: revoke the key in the OpenAI dashboard, create a new key, and use `git filter-repo` or GitHub support to purge history (or accept the leak and rotate the key).

## Steps

1. Clone the monorepo (if you do not have it yet):

   ```bash
   git clone https://github.com/ydangishere/dev-projects.git
   cd dev-projects
   ```

2. Copy this whole `longrun-risk-scanner` directory into `dev-projects/` so you get:

   `dev-projects/longrun-risk-scanner/` (with `app/`, `rules/`, `README.md`, …).

   Do **not** copy your local `.env` into a path that will be force-added; normally `cp -r` copies `.env` too — that is fine **locally**, but only commit from a machine where `git status` does not list `.env` (ignored).

3. Update the **root** `dev-projects/README.md` to list `longrun-risk-scanner` like the other subprojects (one bullet + short description).

4. From `dev-projects/`:

   ```bash
   git add longrun-risk-scanner
   git status   # confirm .env is NOT listed
   git commit -m "Add longrun-risk-scanner (Java long-run risk scanner CLI + GUI)"
   git push origin main
   ```

5. Alternatively, keep **this** folder as its **own** Git repo and later add it as a submodule to `dev-projects` — only if you are comfortable with submodules; the copy-paste method above is simpler.
