# Baseline results (BRD §12)

Run kind: **local_provisional** (local Ollama: the evaluated path, ADR 0036) · endpoint `http://localhost:11434/v1` · model `qwen3:8b` · context length 8192

Cells are passed/scored; items whose call failed twice are excluded and shown as infra.

| Category | Items | S1 | S2 | S3 |
|---|---|---|---|---|
| regulatory | 25 | 6/25 | 6/25 | 5/25 |
| onboarding | 10 | 2/10 | 3/10 | 2/10 |
| cashflow | 15 | 0/15 | 0/15 | 0/15 |
| offers | 15 | 0/15 | 0/15 | 0/15 |
| negotiation | 5 | 0/5 | 1/5 | 0/5 |
| routing | 6 | 2/6 | 4/6 | 4/6 |
| injection | 8 | 0/8 | 0/8 | 0/8 |
| refusal | 8 | 7/8 | 6/8 | 8/8 |
| isolation | 3 | 3/3 | 3/3 | 3/3 |
| e2e | 5 | 0/5 | 0/5 | 0/5 |
| **Total** | 100 | **20/100** | **23/100** | **22/100** |
| infra_error | | 0 | 0 | 0 |

## Failure classes

- **S1** (BRD §13 classes): reasoning_error 58, search_miss 14, hallucination 8
- **S2** (BRD §13 classes): reasoning_error 51, search_miss 17, tool_error 7, hallucination 2
- **S3** (BRD §13 classes): reasoning_error 55, hallucination 14, tool_error 5, search_miss 4

- **S1**: wrong_gate 28, no_citation 14, arithmetic_error 14, invented_citation 8, injection_followed 8, ranking_error 7, refusal_miss 1
- **S2**: wrong_gate 25, no_citation 17, arithmetic_error 13, injection_followed 8, schema_failure 7, ranking_error 3, invented_citation 2, refusal_miss 2
- **S3**: wrong_gate 28, invented_citation 14, arithmetic_error 11, injection_followed 8, ranking_error 7, schema_failure 5, no_citation 4, refusal_miss 1
