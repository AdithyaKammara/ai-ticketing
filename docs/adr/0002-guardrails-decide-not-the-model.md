# 2. Deterministic guardrails decide; the model only suggests

Status: accepted (M2)

## Context

v1 let the model's JSON drive the ticket directly. A wrong answer, or text in a ticket
telling the model to "mark this resolved", could close a serious issue without a person
ever seeing it.

## Decision

The model returns a classification, a summary, a confidence and an optional draft reply.
Plain code in `app/services/guardrails.py` then decides:

- The department comes from the `category_routes` table, never from the model.
- Severity can only be raised: by a per-category floor (DATABASE and INFRASTRUCTURE are at
  least HIGH) and by phrases like "production down", "all users" or "data loss".
- Auto-resolve requires all of these: the model says self-serve and wrote a draft;
  confidence at or above `AUTO_RESOLVE_MIN_CONFIDENCE` (85); severity LOW or MEDIUM after
  the floors; a category on the allow-list and enabled in the database; and the requester
  has not reopened an automatic answer in the last 24 hours. DATABASE, INFRASTRUCTURE and
  BUG are never auto-resolved, whatever the database says.

The prompt also limits self-serve answers to generic steps and forbids invented
company-specific facts, because there is no knowledge base yet (that is v2, RAG).

## Consequences

- A fully manipulated model answer still cannot auto-resolve a database or outage ticket.
  Tests prove it with the model faked to obey an injection.
- Fewer tickets are auto-resolved than a looser design would allow. Policy questions go to
  HR or Finance until the v2 knowledge base can ground the answers.
- Every decision and its reasons are stored in `ai_triage_logs` for review.
