# 1. Run AI triage in a worker queue

Status: accepted (M2)

## Context

A triage call to the model takes 1 to 10 seconds and sometimes fails or times out. The PRD
requires the API to answer in under 300 ms and never to lose a ticket.

## Decision

`POST /tickets` saves the ticket as `TRIAGING`, enqueues `triage_ticket(ticket_id)` in
Redis with ARQ, and returns 201. A separate worker process calls the model, applies the
guardrails and routing, and writes the result. The browser polls the ticket until triage
finishes.

## Consequences

- The API stays fast and keeps working when the model provider is down.
- If the queue itself is unreachable, the API marks triage `FAILED` and the ticket goes to
  the Unassigned queue straight away.
- Jobs survive API restarts. ARQ may run a job twice after a worker crash, so the job locks
  the ticket row and does nothing unless the ticket is still `TRIAGING`.
- One more process to deploy and monitor (a second Render service from the same image).
