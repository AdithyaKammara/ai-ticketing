# M2 AI triage

## Done

- **Provider interface** (`app/llm/base.py`) with a Groq implementation: JSON mode,
  temperature 0, 15 s timeout, 600 output tokens. The model name is config (`LLM_MODEL`).
- **Prompt `triage_v3`** (`app/llm/prompts/triage_v3.py`): categories and departments are
  injected from the database; ticket text is wrapped in `<ticket_title>` and `<ticket_body>`
  and declared to be data; tag look-alikes in user text are neutralized; eight worked
  examples with varied confidences, including one injection attempt and one vague ticket;
  no example numbers in the output schema.
- **Validation and retries** (`app/services/triage_model.py`): replies must match the
  `TriageResult` schema. Timeouts, rate limits and 5xx errors are retried up to 3 times with
  exponential backoff; a malformed reply gets one repair attempt; anything still wrong falls
  back.
- **Guardrails** (`app/services/guardrails.py`): see
  [ADR 2](../adr/0002-guardrails-decide-not-the-model.md).
- **Worker** (`arq app.workers.main.WorkerSettings`): the triage job, a daily global model
  budget (`LLM_DAILY_BUDGET`; past it, tickets skip AI and go to a person), and an hourly
  housekeeping job that closes tickets resolved 7 or more days ago and deletes triage logs
  older than 90 days. Every run writes an `ai_triage_logs` row with the prompt version,
  model, latency, tokens, raw output, parsed result and guardrail reasons. The worker
  refuses to start without `GROQ_API_KEY`.
- **Fallback (FR-2):** if the model times out or keeps answering badly, the ticket moves to
  `NEW`, unassigned, with `triage_status = FAILED`, and admins see it in Unassigned.
- **Eval:** 116 hand-labeled tickets in `backend/evals/dataset.jsonl` (10 injection
  attempts, 10 vague tickets), and `python -m app.evals.run`, which uses the same prompt,
  parser and guardrails as the worker, prints accuracy, a confusion matrix and unsafe
  auto-resolutions, and exits 1 below the targets. `.github/workflows/eval.yml` runs it
  nightly and on changes to the prompt, triage pipeline, guardrails or dataset.
- **Tests:** the PRD's required cases pass with a fake model, including
  `test_ticket_saved_when_llm_times_out` and `test_injection_text_cannot_force_auto_resolve`.

## Still to do

- **Run the eval against the real model.** It needs `GROQ_API_KEY` in `.env`, and as a
  GitHub Actions secret for the nightly run. Then tune the prompt until the targets pass,
  save the results with `--write`, and bump `PROMPT_VERSION` for any prompt change.
- Analytics endpoints (FR-8) for the M3 dashboard.
