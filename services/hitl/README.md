# Service: HITL Review (Phase 8)

Implements Human-in-the-Loop review for fields that fall below the confidence threshold,
using LangGraph's `interrupt()` mechanism.

## Responsibilities

- Identify low-confidence fields from the `ConfidenceResult` (Phase 6)
- Push review tasks to Label Studio with the field value and context
- Call `LangGraph interrupt()` to pause the graph state and wait for human input
- Resume the graph once the reviewer submits a correction via Label Studio webhook
- Write accepted corrections to the `corrections` table for use in Phase 9

## Key Tech

- LangGraph `interrupt()` + state persistence
- Label Studio (HITL review interface)
- httpx (Label Studio API)
- PostgreSQL (correction storage)

## Flow

```
low-confidence fields detected
        ↓
push task to Label Studio
        ↓
LangGraph interrupt() — graph paused
        ↓
human reviews and submits correction
        ↓
webhook received → graph resumes
        ↓
correction written to DB
```
