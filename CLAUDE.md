# CLAUDE.md — AI Receptionist Operating Contract

This file is binding. Load it every session before making changes.

## What this is

An inbound AI voice receptionist for HVAC companies, built on **Retell AI**
(Conversation Flow agent, node-based) with a **FastAPI** backend for Custom
Functions and post-call processing. This is the reusable v1 — no client is
signed yet, so all client-specific content lives behind `TODO(intake: ...)`
placeholders. Never fabricate a value for one of these; ask instead.

## Locked stack (do not substitute)

- **Agent type:** Retell Conversation Flow (node-based). Not single-prompt.
- **Telephony:** Retell native inbound number.
- **Calendar:** Google Calendar (free/busy + event CRUD).
- **CRM:** GoHighLevel (post-call upsert).
- **SMS:** Twilio (A2P 10DLC registered before live use).
- **Datastore:** Postgres — appointments, leads, call logs, transcripts.
- **FAQ:** Retell Node Knowledge Base, bound at the node level — not a custom function.
- **Excluded from v1:** ServiceTitan.

## Standing rules (every session, every endpoint)

1. **Verify `X-Retell-Signature` on every Custom Function endpoint.** Use
   `retell-sdk`'s `Retell(api_key=...).verify(raw_body_str, api_key, signature)`.
   Missing or invalid signature → **401**. Never skip this, even for local testing
   conveniences — gate it behind env config instead.
2. **Idempotency keyed on Retell `call_id`** (+ slot hash for bookings) on every
   write. A retried or redelivered request must produce the same result without
   a duplicate side effect. This is the single most important reliability
   primitive in this codebase — see `app/idempotency.py`.
3. **Defer all slow writes to the post-call webhook** (`call_ended` /
   `call_analyzed`): CRM upsert, SMS confirmation, transcript logging. Never do
   these inside a live-turn Custom Function — the live turn must stay fast
   (functions should resolve well under the ~1s realistic budget, hard cap ~2min
   server-side before Retell calls it a failure).
4. **Gas-safety check is the first conversation gate** (flow-level, not a
   function). A gas-smell answer hard-stops to the emergency-end node and must
   never route to booking.
5. **Never quote prices, never diagnose, never promise an exact arrival time.**
   Identify as an AI when asked. These are global hard rules enforced in the
   agent prompt/guardrails, not just suggestions for the backend.
6. **Recording is on → spoken consent disclosure is required** before
   substantive conversation; AI-disclosure compliance is always on.
7. **`TODO(intake: ...)` placeholders** mark unresolved client-specific values
   (business identity, greeting wording, FAQ answers, transfer destination,
   SMS sender + copy). Never fabricate these. Surface them as an open checklist.
8. Each Custom Function endpoint returns a compact `result` (**< 15,000 chars**,
   Retell's cap) and HTTP **200–299** on success.

## Repo map

```
app/
  config.py          Settings (env-driven), TODO(intake) placeholders
  db.py               SQLAlchemy engine/session (lazy singletons so tests can
                       override DATABASE_URL before first use)
  models.py           Appointment, Lead, EmergencyFlag, IdempotencyKey
  idempotency.py      run_idempotent() — generic cache-or-compute-and-store
  security.py         verify_signature() FastAPI dependency (401 on failure)
  util.py             slot_hash(), parse_function_call(), result-size guard
  retell/functions.py Custom Function endpoints (one per function)
  main.py             FastAPI app wiring
tests/                pytest suite; book_visit double-book test is load-bearing
retell/SETUP.md        (Phase 4) dashboard-only steps + provisioning script docs
```

## Custom Functions implemented (Phase 1)

`check_availability`, `book_visit`, `reschedule_visit`, `cancel_visit`,
`capture_lead`, `flag_emergency`, `transfer_to_human` — all under
`/retell/functions/*`, all signature-verified, all idempotent on `call_id`
(+ slot hash where relevant).

**Phase 1 scope note:** `check_availability`/`book_visit` currently treat
Postgres as the sole source of truth for "busy" slots (no Google Calendar
call yet). Phase 2 wires real Google Calendar free/busy and swaps the busy-slot
source without changing the function contracts. Cross-caller slot-conflict
checking is currently app-level (a query before insert); a Postgres
`tstzrange` EXCLUDE constraint is the Phase 2 hardening note for true
concurrent-booking safety — call_id+slot retry idempotency (the explicit
acceptance criterion) is already DB-constraint-backed via a unique
`(call_id, slot_hash)` index on `appointments`.

## Open `TODO(intake)` values (do not fabricate, ask the user)

- `business_identity` (legal name, service area, hours, after-hours policy)
- `greeting_wording` (must include AI + recording disclosure)
- `faq_answers` (Knowledge Base seed content)
- `human_transfer_destination` (phone number(s))
- `sms_sender` + `confirmation_copy` (A2P-registered number + message text)

## Verify against current docs, don't assume

`docs.retellai.com` was unreachable from this environment's egress policy
during initial research. Signature verification and function-call limits
(15k char cap, 2-retry, 2-min timeout, 200-299 success) were confirmed via
the `retell-sdk` PyPI package source and corroborating web search results —
but the exact request/response JSON envelope for Conversation Flow Custom
Functions (whether the webhook body is `{call, name, args}` or
`{args}`-only, controlled by a per-function "Payload" setting) was not
independently re-verified against live docs. `app/util.py:parse_function_call`
handles both shapes defensively. **Confirm the actual shape against your
Retell dashboard / a live test call in Phase 4** before relying on it.
