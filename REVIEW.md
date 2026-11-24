# Review Instructions

## Passes
Run three passes and tag each finding with its pass:
- **Bugs**: logic errors, broken edge cases in statement parsing, subtle regressions, numerical inaccuracies in score calculation or debt reconciliation.
- **Security**: AWS credentials in diffs, unredacted M-Pesa PII (real phone numbers, customer names, national IDs) in code or test fixtures, unauthorized network egress.
- **Compliance**: change matches `spec.md` and `plan.md`; strictly maintains the Zero-AWS rule in `backend/src/core/` (zero `boto3` imports).

## What Important Means Here
Reserve **Important** for findings that would break calculation accuracy, leak customer PII, introduce unmocked AWS calls to local dev, or fail `make test`. Style and variable naming are nits.

## Cap the Nits
Report at most five nits per review; summarize the rest as a count.

## Do Not Report
Generated files (e.g., build artifacts, `.pytest_cache`, `.next`), `package-lock.json`, and anything the linter already checks mechanically.
