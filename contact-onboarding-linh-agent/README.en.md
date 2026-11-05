# Linh Contact Onboarding Agent — English summary

See the [detailed bilingual README](./README.md) and [two-flow architecture diagram](./diagrams/onboarding-flow.svg).

**Linh is a simulated AI character, not a real person or employee.** This is a runnable Python FastAPI prototype with synthetic test data.

- **Sync Contacts:** showing an app-owned list requires the platform's contacts permission, even if the list stays local. Uploading permitted contacts to a server is a *separate optional consent* step. The demo stores only keyed phone digests.
- **Select to Invite:** use the OS-native contact picker with no broad address-book permission; draft invitations without syncing the entire address book. User confirms before opening the OS Share Sheet. The demo never sends anything.
- **AI model:** offline rules by default; optional OpenAI `gpt-4.1-mini` if an API key is set. Only non-PII metadata is sent to the model. Linh guides, but cannot grant permissions, upload contacts or send messages.

Run: `python -m pip install -r requirements-dev.txt`, then `python -m uvicorn app.main:app --reload`, open `/docs`, and test with `python -m pytest -q`.

**Not a production integration:** no mobile SDK, real users, cloud database, SMS/Zalo or referral attribution.