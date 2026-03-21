# SSO Mini - Spring Boot

Login once, use many apps. No need to login again when switching apps.

---

## What You Have

| Service       | Port | What it does                    |
|---------------|------|---------------------------------|
| auth-service  | 8080 | Login page. Creates tokens.     |
| app-a         | 8081 | Dashboard (first app)           |
| app-b         | 8082 | Profile page (second app)       |

---

## How to Run

### Option A: Quick Start (no PostgreSQL)

Open 3 terminals. Run one command in each:

```powershell
# Terminal 1 - Auth (uses H2, no DB setup)
cd "d:\dev project\sso\auth-service"
mvn spring-boot:run "-Dspring-boot.run.profiles=dev"

# Terminal 2 - App A
cd "d:\dev project\sso\app-a"
mvn spring-boot:run

# Terminal 3 - App B
cd "d:\dev project\sso\app-b"
mvn spring-boot:run
```

Wait until each shows "Started ... in X seconds".

### Option B: With PostgreSQL

1. Create database: `CREATE DATABASE sso_auth;`
2. Run auth-service without the `-Dspring-boot.run.profiles=dev` part.
3. Run app-a and app-b as above.

### Option C: Docker

```powershell
cd "d:\dev project\sso"
docker-compose up -d
```

---

## Step-by-Step Testing Guide

### Step 1: Open App A

- Go to: **http://localhost:8081**
- You should be redirected to the login page (auth-service at 8080).
- If you see "Connection Failed", auth-service is not running. Start it first.

### Step 2: Login

- Username: **admin**
- Password: **admin123**
- Click Login.

### Step 3: See App A Dashboard

- You land on App A dashboard.
- You see: "Xin chào, Admin User!" and your username.
- This proves: login worked, token was saved.

### Step 4: Open App B (SSO Test)

- Click the link: **"Mở App B (SSO)"**
- Or go directly to: **http://localhost:8082**

### Step 5: No Login Again

- You go straight to App B profile page.
- No login form. No password asked.
- This proves: **SSO works**. One login, both apps.

### Step 6: Switch Back to App A

- Click **"Mở App A (SSO)"** on App B.
- You go to App A dashboard without logging in again.

### Step 7: Logout

- Click **Logout** on any app.
- Visit http://localhost:8081 again.
- You should see the login page again.

---

## Quick Checklist

| Step | Action                    | Expected result                    |
|-----|---------------------------|------------------------------------|
| 1   | Open http://localhost:8081| Redirect to login page             |
| 2   | Login admin / admin123    | Redirect to App A dashboard        |
| 3   | Click "Mở App B"          | App B opens, no login              |
| 4   | Click "Mở App A"          | App A opens, no login              |
| 5   | Logout                    | Next visit shows login again       |

---

## Flow in One Sentence

**You login at one place (auth-service). Both apps trust that place. So you login once, use both.**

---

## Project Structure

```
sso/
├── auth-service/     # IdP - login, JWT, session
├── app-a/            # Client A - dashboard
├── app-b/            # Client B - profile
├── docker-compose.yml
└── README.md
```
