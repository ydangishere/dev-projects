# Credit Copilot — loan underwriting assistant

[Tiếng Việt (main README)](./README.md)

Credit Copilot helps **credit officers** at a Vietnamese bank: it reads an unsecured consumer-loan file, checks 10 policy conditions, drafts a credit memo and answers policy questions with clause citations. Every conclusion links back to the source line in the documents and to the policy clause it enforces.

This version runs with a **real LLM** (self-hosted Qwen via Ollama, or Gemini) and an operations toolchain: **LiteLLM** (model gateway, SDK and proxy), **Microsoft Presidio** (PII masking), **Llama Guard 3** (content safety), **Langfuse** (tracing), **Prometheus + Grafana** (metrics) and **DeepEval** (LLM-judged evaluation).

> **Honest scope:** only the **data is synthetic** (6 loan files, the policy, the customers). No real LOS or core-banking (T24) connection. The figures below come from GitHub CI running **Qwen 2.5 1.5B on CPU**, a small model chosen so CI can run it; a deployment should use 7B or larger. Output is a recommendation; the credit decision stays with a human approver.

## Design

- **The LLM never decides or calculates.** Income, instalment, DTI and pass/fail come from `app/rules.py`.
- **Regex first, LLM only for missing fields.** Standard-layout files never call the model.
- **The model never sees personal data.** Presidio replaces ID, account and phone numbers and names with placeholders (`<CCCD_1>`, `<PERSON_1>`); code restores them afterwards.
- **Anti-fabrication:** each extracted value must literally appear in the line the model cites. Any number in a memo or answer that is not in the computed facts or cited clauses makes the system fall back to a template.
- **Injection via documents:** lines that instruct the AI are flagged, kept away from the model and audited; they cannot change the verdict anyway.
- **Data stays in the bank:** the default compose stack uses an in-house Qwen; document text reaches a model only with `LLM_SEND_DOCUMENTS=true`.

## Results with a real model (CI, Qwen 2.5 1.5B, CPU)

Safety checks (enforced): rule verdicts unchanged by the LLM, no ID number in any prompt, injected line flagged and not sent, injection did not change the verdict, off-topic questions refused. All pass.

Quality (reported): messy-file verdicts 2/2 (offline: "needs more info"), messy-file field accuracy 88.5% (23/26), LLM memos passing the number check 6/6, policy citations 7/8 (one answer cited clause 5.1 instead of 4.1 and was not caught), LLM-written answers 4/6, Llama Guard 3/3 harmful questions caught with 0/3 false positives, DeepEval faithfulness 0.60 and GEval correctness 0.20 (judge: Qwen 2.5 3B; both models are small and weak in Vietnamese), assessment latency p50/p95 11/21 s on CPU. Results vary between runs with a model this small. Langfuse received 78 observations from one evaluation run. In an earlier run, Llama Guard 1B blocked 2 of 6 internal memos by mistake, so memo moderation is off by default.

## Run

```bash
pip install -r requirements.txt && uvicorn app.main:app --port 8000      # offline
docker compose up -d --build     # Copilot + Ollama (Qwen, Llama Guard) + LiteLLM proxy + Prometheus + Grafana
pip install -r requirements-eval.txt && LLM_MODEL=ollama_chat/qwen2.5:7b LLM_API_BASE=http://localhost:11434 \
  LLM_SEND_DOCUMENTS=true python scripts/evaluate_llm.py
```
