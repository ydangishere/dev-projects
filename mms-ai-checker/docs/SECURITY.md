# Security boundaries / Ranh giới bảo vệ

This prototype implements concrete controls, not a claim of complete hacking protection. Documents, filenames, employee questions, model output and reviewer notes are untrusted. Policy files and principal configuration are server-controlled. The service can read/check/store evidence and feedback; it cannot approve, modify account state, call arbitrary tools or move money.

## Threat-to-control matrix

| Threat | Implemented boundary | Test/evidence | Residual risk / next production control |
|---|---|---|---|
| Indirect injection inside PDF/image/TXT | Separate extraction system instruction; strict fields; no model tools; document verification/tenant not extracted; immutable deterministic findings; all Gemini facts need human source review | TXT injection and malformed/model-output tests | A malicious document can still influence extracted facts or quotes. Screening is incomplete. Held-out PDF/image attack tests and isolated OCR required. |
| Reverse-approach/social-engineering questions | Employee question never forwarded to Gemini or used to alter retrieval/rules; fixed checking workflow | Question attack produces same findings as normal question | No general chat/tool executor is exposed. Expand threat corpus if conversational capabilities are added. |
| Hidden instructions and Unicode | NFKC normalization and format-character removal for supplemental instruction screening; authority remains server-owned | Zero-width instruction test | Encoded, multilingual or image-based instructions can evade detection. Detector is not the security boundary. |
| Fake role/tenant or object ID | Token maps to server-owned principal; application and check queries include tenant; every source/evidence route checks authorization first | Other-tenant application/check/evidence/source tests | Tokens are local demo auth. Integrate bank OIDC with issuer/audience/signature/expiry validation and explicit role mapping. |
| Manipulating input fields / mass assignment | Strict Pydantic check/feedback models reject extra JSON fields. Upload kind allowlist; arbitrary client metadata ignored; server generates ID/version/hash/pending status | Extra tenant/approved fields rejected; uploaded verification/version cannot take effect | Application edit/verification workflow is intentionally not exposed. Validate bank adapter response schema too. |
| Upload traversal / spoofed content | Original filename never used as disk path; bytes stored in DB; fixed kinds; PDF signature/parser; JPEG/PNG decoder checks; extension/type agreement | Traversal filename, fake PDF/image, HTML and NUL tests | No antivirus/CDR or isolated parser. PDF active-content rejection is partial, not a malware verdict. |
| File bombs / resource exhaustion | Actual streamed HTTP body bound; 5 MiB/file, 20 pages/PDF, 20M pixels/image; actor write limit 20/min; two check slots; 60-second model-call timeout, one attempt; Docker CPU/memory/PID limits | Oversized body, rate limit and decoder tests | Parser CPU/memory can still be abused; request slowloris/distributed limits and hard OCR subprocess deadline belong at gateway/isolated worker. |
| Output injection / XSS / unsafe explanation | UI uses textContent; fixed same-origin API routes; CSP, nosniff, no-store; no model HTML; strict explanation IDs and supplemental output screening | Header and explanation tests; browser flow when available | Natural-language explanations can still be wrong. Findings remain authoritative; inspect originals. |
| Fabricated citation or overconfident extraction | Bounded document pages; per-fact quote/confidence schema; value must appear in quote; original sources preserved; Gemini extraction always review-only | Out-of-range page, inconsistent quote, missing/duplicate/low-confidence facts | Quote may itself be hallucinated for image/PDF. Only source verification or independent OCR/annotation can establish textual grounding. |
| Stale/replaced document | Incremented revision, pending new version, immutable evidence snapshot; stale result flag; feedback blocked on stale result | Replaced document invalidates result and retains old source | Changes in a future remote MMS need authoritative revision/ETag checks and atomic upstream contracts. |
| SQL/command injection, SSRF | Parameterized SQLite queries; no shell execution; no URL input/fetch tool; Gemini endpoint controlled by SDK/server | Source inspection; fixed API surface | Lock down outbound network to model endpoint and approved bank hosts at infrastructure level. |
| Secret/PII leakage | API key only server env; `.env` excluded from Git and Docker build context; no prompt/secret logs; second explanation call strips raw identity fields | Source inspection, ignored runtime paths | Gemini extraction sends complete uploaded document to Google. Data region, retention, agreement, classification and access approval must be set by bank. |
| Feedback poisoning | Checker-only feedback recorded as audit data, never automatically inserted into RAG/rules or used for training | Role/feedback/audit tests | Human-curated review and controlled releases required before changing policy/model. |
| Dependency/supply-chain vulnerabilities | Pinned direct dependencies; pip-audit blocking CI; Docker runs non-root | Audit and CI configuration | Audit is point-in-time and not proof of no defects. Transitive releases and base image must be reviewed and refreshed. |

## Actual access model

| Role | Read authorized application/check/evidence | Upload/check | Feedback | Approve/pay |
|---|---|---|---|---|
| viewer | Yes | No | No | No |
| maker | Yes | Yes | No | No |
| checker | Yes | Yes | Yes | No |

PVcomBank maker and checker are bank employee roles. This project stores demo role mappings, not the full MMS access matrix. Tenant isolation applies even when an ID is guessed. Unknown and forbidden-tenant objects both return 404. Audit records contain actor, tenant, action, time, object and bounded details. Local SQLite audit is **not tamper-proof/WORM storage**; ship it to controlled central logging for production.

## Production configuration and limits

Set `APP_ENV=production` with explicit token mapping using secrets of at least 32 characters; public `demo-*` tokens are rejected. This gate does not implement production SSO. Disable/revoke demo identities and seed-data access when implementing a bank pilot; the present app always seeds synthetic applications and is not a production tenant provisioning service.

No open CORS policy is enabled. Tokens stay in browser memory, not localStorage, URLs or cookies. CSP currently prevents framing the app: integrate as a standalone workbench, or review frame ancestors/SSO deliberately before embedding into MMS. OpenAPI metadata and health are public; business data requires authorization. No browser prompt can grant a role.

Before an authorized pilot: bank-reviewed identity mapping, official policy release ownership, encrypted disks/backups, key rotation, central audit/alerts, gateway limits/TLS, isolated file processing, malware scanning, model data governance, broader adversarial evaluation and incident/restore procedures. These are explicit remaining work, not implemented features claimed by this repository.

## Tóm tắt tiếng Việt

Biện pháp quan trọng nhất là **tài liệu và câu hỏi không có quyền thay luật, phân quyền hay quyết định duyệt**. Từ khóa phát hiện tấn công chỉ hỗ trợ; AI vẫn có thể đọc sai hoặc bị ảnh hưởng khi bóc thông tin. Vì vậy bản này giữ phát hiện bằng luật riêng, lưu nguồn thật, bắt đối chiếu thông tin Gemini đọc, và không cung cấp lệnh duyệt/chuyển tiền.

“Reverse approach” được hiểu ở đây là hỏi ngược hoặc giả lập vai trò để moi cách vượt quy định, không phải tên một giao thức riêng. Bản này không chuyển câu hỏi thành lệnh/công cụ; chưa chứng minh chống được mọi cách tấn công đó. Những kiểm thử hiện có chỉ chứng minh các ranh giới được ghi rõ ở trên.
