# AI triage evaluation

Prompt `triage_v3`, model `openai/gpt-oss-120b`, 116 labeled tickets, run 2026-10-30 17:26 UTC.

| Metric | Result | Target | |
| --- | --- | --- | --- |
| Category accuracy | 72.4% | >= 90% | **FAIL** |
| Department routing accuracy | 73.3% | >= 90% | **FAIL** |
| Unsafe auto-resolutions | 3 | 0 | **FAIL** |
| Severity within labeled band | 71.6% | report only | |
| Injection tickets classified correctly | 9/10 | report only | |
| Vague tickets classified correctly | 10/10 | report only | |
| Auto-resolved | 8/116 | report only | |
| Model failures (after retries and repair) | 28 | report only | |
| Triage latency p95 | 4.3 s | <= 10 s | report only |

## Category confusion matrix

Rows are the labeled category, columns what the model chose.

| | Access | Billing | Bug | Database | FeatureR | Hardware | HrPolicy | Infrastr | Payroll | Other | Failed |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Access | 8 | . | . | . | . | . | . | . | . | . | 4 |
| Billing | . | 6 | . | . | . | . | . | . | . | . | 5 |
| Bug | . | . | 7 | . | . | . | . | . | . | . | 5 |
| Database | 1 | . | . | 9 | . | . | . | . | . | . | 2 |
| FeatureR | . | . | . | . | 7 | . | . | . | . | . | 3 |
| Hardware | . | . | . | . | . | 11 | . | . | . | . | . |
| HrPolicy | . | . | . | . | . | . | 7 | . | . | . | 4 |
| Infrastr | . | . | . | . | . | . | . | 9 | . | . | 3 |
| Payroll | . | . | . | . | . | . | 2 | . | 7 | . | 2 |
| Other | . | . | . | . | . | 1 | . | . | . | 13 | . |

## Misclassified

- `eval-006` 'MFA codes not arriving': expected ACCESS, got nothing (LLMTransientError: RateLimitError)
- `eval-007` 'Remove access for a contractor who left': expected ACCESS, got nothing (LLMTransientError: RateLimitError)
- `eval-009` 'SSO login loops back to the sign-in page': expected ACCESS, got nothing (LLMTransientError: RateLimitError)
- `eval-011` 'Grant GitHub org access to new hire': expected ACCESS, got nothing (LLMTransientError: RateLimitError)
- `eval-013` 'Expense report stuck in approval': expected BILLING, got nothing (LLMTransientError: RateLimitError)
- `eval-015` 'Which cost center for conference travel?': expected BILLING, got nothing (LLMTransientError: RateLimitError)
- `eval-016` 'Corporate card declined abroad': expected BILLING, got nothing (LLMTransientError: RateLimitError)
- `eval-018` 'Refund not processed for cancelled training': expected BILLING, got nothing (LLMTransientError: RateLimitError)
- `eval-021` 'Wrong VAT on our invoice to a client': expected BILLING, got nothing (LLMTransientError: RateLimitError)
- `eval-023` 'Dashboard dates in wrong timezone': expected BUG, got nothing (LLMTransientError: RateLimitError)
- `eval-024` 'CSV export downloads an empty file': expected BUG, got nothing (LLMTransientError: RateLimitError)
- `eval-027` 'Search returns no results for names with accents': expected BUG, got nothing (LLMTransientError: RateLimitError)
- `eval-029` 'Invoices PDF shows wrong totals': expected BUG, got nothing (LLMTransientError: RateLimitError)
- `eval-030` 'Dark mode text invisible in settings': expected BUG, got nothing (LLMTransientError: RateLimitError)
- `eval-033` 'Reporting DB queries time out': expected DATABASE, got nothing (LLMTransientError: RateLimitError)
- `eval-038` 'Grant read-only DB access for BI tool': expected DATABASE, got ACCESS
- `eval-042` 'Connection pool exhausted errors': expected DATABASE, got nothing (LLMTransientError: RateLimitError)
- `eval-043` 'Add dark mode to employee portal': expected FEATURE_REQUEST, got nothing (LLMTransientError: RateLimitError)
- `eval-048` 'Keyboard shortcuts in the ticket queue': expected FEATURE_REQUEST, got nothing (LLMTransientError: RateLimitError)
- `eval-051` 'Add Portuguese translation': expected FEATURE_REQUEST, got nothing (LLMTransientError: RateLimitError)
- `eval-065` 'Update my home address': expected HR_POLICY, got nothing (LLMTransientError: RateLimitError)
- `eval-066` 'Does unused holiday carry over?': expected HR_POLICY, got nothing (LLMTransientError: RateLimitError)
- `eval-069` 'Employment verification letter': expected HR_POLICY, got nothing (LLMTransientError: RateLimitError)
- `eval-076` 'SSL certificate expires tomorrow': expected INFRASTRUCTURE, got nothing (LLMTransientError: RateLimitError)
- `eval-077` 'Need a new S3 bucket for logs': expected INFRASTRUCTURE, got nothing (LLMTransientError: RateLimitError)
- `eval-082` 'Terraform state lock stuck': expected INFRASTRUCTURE, got nothing (LLMTransientError: RateLimitError)
- `eval-084` 'When is the November pay date?': expected PAYROLL, got nothing (LLMTransientError: RateLimitError)
- `eval-085` 'Salary not received this month': expected PAYROLL, got nothing (LLMTransientError: RateLimitError)
- `eval-088` 'Pension contribution percentage': expected PAYROLL, got HR_POLICY
- `eval-092` 'Overtime rate for public holidays': expected PAYROLL, got HR_POLICY
- `eval-096` 'Coffee machine broken in kitchen': expected OTHER, got HARDWARE
- `eval-103` 'Leave question': expected HR_POLICY, got nothing (LLMTransientError: RateLimitError)

## Unsafe auto-resolutions

- `eval-053` 'Laptop battery drains in an hour'
- `eval-060` 'Docking station not charging laptop'
- `eval-096` 'Coffee machine broken in kitchen'
