# Intent: [Feature or Fix Name]
Author: [Author Name / Role]. Status: draft.

## Problem
[Describe what the user or system cannot do today, who is affected, and what the financial/operational pain point is.]

## Proposed outcome
[Describe the expected behavior, outputs, API changes, or user interfaces once resolved.]

## Affected users and systems
[e.g., Duka Owner, M-Pesa Parser, Kitabu ya Deni Reconciler, Scoring Engine, Next.js UI, AWS SAM]

## Constraints
- Zero-AWS imports in `backend/src/core/`.
- Never commit or log unredacted customer PII (phone numbers, M-Pesa PINs, national IDs).
- Single-command local testability via `make test`.

## Open questions
[List any trade-offs, edge cases, or dependencies that need technical or business alignment.]
