# HRM Mini - SvelteKit + Supabase

Small web-based HRM demo built to support a portfolio or job application.

## What it shows

- SvelteKit app structure for a small product-style web app
- Supabase-ready Auth and SSR helper files
- PostgreSQL schema + RLS migration for employees, departments, and leave requests
- Admin vs employee access model

## Pages

- `/` overview
- `/login` auth screen
- `/dashboard` summary cards and latest leave activity
- `/employees` employee directory
- `/leave-requests` leave request list

## Demo mode

The UI currently runs on local mock data so the project can open immediately without cloud setup.

Supabase wiring is prepared in:

- `src/lib/supabase/client.ts`
- `src/lib/supabase/server.ts`
- `src/hooks.server.ts`
- `supabase/migrations/20260418_hrm_init.sql`

## Environment

Copy `.env.example` to `.env` and fill in:

```env
PUBLIC_SUPABASE_URL=
PUBLIC_SUPABASE_PUBLISHABLE_KEY=
```

## Run locally

Run in `e:\cv ok\updated\New folder (3)\hrm`

```powershell
npm install
npm run dev
```

## Quality checks

```powershell
npm test
npm run check
```
# sv

Everything you need to build a Svelte project, powered by [`sv`](https://github.com/sveltejs/cli).

## Creating a project

If you're seeing this, you've probably already done this step. Congrats!

```sh
# create a new project
npx sv create my-app
```

To recreate this project with the same configuration:

```sh
# recreate this project
npx sv@0.15.1 create --template minimal --types ts --add prettier eslint vitest="usages:unit" --install npm hrm
```

## Developing

Once you've created a project and installed dependencies with `npm install` (or `pnpm install` or `yarn`), start a development server:

```sh
npm run dev

# or start the server and open the app in a new browser tab
npm run dev -- --open
```

## Building

To create a production version of your app:

```sh
npm run build
```

You can preview the production build with `npm run preview`.

> To deploy your app, you may need to install an [adapter](https://svelte.dev/docs/kit/adapters) for your target environment.

---

## Solution Architecture Review (implementation-backed)

**Business problem:** Represent a small HR product with employee directory, leave requests and separate admin/employee access concepts.

**Current demo flow (one line):** SvelteKit UI routes → Local mock employee/leave data → Dashboard and management views.

**Proposed connected flow (not yet live):** SvelteKit server routes → Supabase auth → PostgreSQL + RLS policies → Role-specific HR data.

**Architecture decisions**
- **Trust boundary:** Supabase client/server helpers and database row-level-security migrations prepare an authorization approach, but mock-data screens do not verify live Supabase enforcement.
- **UI/data separation:** Route and domain modules can be connected to a real backend without rewriting every page.
- **Privacy:** Real HR records would require least-privilege permissions, encrypted transport, retention rules and auditability.
- **Production path:** Wire live authentication, enforce RLS with integration tests, add access-policy tests, pagination, reliable migrations and tenant-specific data boundaries.
- **Evaluation:** Verify role matrix, unauthorized access attempts, leave transition rules and page/data performance.

**RAG status:** No AI knowledge retrieval or RAG.

**Status:** Local, mock-data frontend with Supabase-ready files; not a deployed HR data system.
