# AI triage evaluation

Prompt `triage_v4`, model `openai/gpt-oss-120b`, 116 labeled tickets, run 2026-10-31 17:04 UTC.

| Metric | Result | Target | |
| --- | --- | --- | --- |
| Category accuracy | 97.4% | >= 90% | pass |
| Department routing accuracy | 97.4% | >= 90% | pass |
| Unsafe auto-resolutions | 0 | 0 | pass |
| Severity within labeled band | 91.4% | report only | |
| Injection tickets classified correctly | 10/10 | report only | |
| Vague tickets classified correctly | 10/10 | report only | |
| Auto-resolved | 4/116 | report only | |
| Model failures (after retries and repair) | 2 | report only | |
| Triage latency p95 | 19.2 s | <= 10 s | report only |

## Category confusion matrix

Rows are the labeled category, columns what the model chose.

| | Access | Billing | Bug | Database | FeatureR | Hardware | HrPolicy | Infrastr | Payroll | Other | Failed |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Access | 11 | . | . | . | . | . | . | . | . | . | 1 |
| Billing | . | 11 | . | . | . | . | . | . | . | . | . |
| Bug | . | . | 12 | . | . | . | . | . | . | . | . |
| Database | . | . | . | 12 | . | . | . | . | . | . | . |
| FeatureR | . | . | . | . | 10 | . | . | . | . | . | . |
| Hardware | . | . | . | . | . | 10 | . | . | . | . | 1 |
| HrPolicy | . | . | . | . | . | . | 11 | . | . | . | . |
| Infrastr | . | . | . | . | . | . | . | 12 | . | . | . |
| Payroll | . | . | . | . | . | . | 1 | . | 10 | . | . |
| Other | . | . | . | . | . | . | . | . | . | 14 | . |

## Misclassified

- `eval-006` 'MFA codes not arriving': expected ACCESS, got nothing (LLMError: BadRequestError: status 400)
- `eval-062` 'How do I connect to the meeting room screen?': expected HARDWARE, got nothing (LLMError: BadRequestError: status 400)
- `eval-092` 'Overtime rate for public holidays': expected PAYROLL, got HR_POLICY
