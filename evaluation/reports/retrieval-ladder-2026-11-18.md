# Retrieval ladder (plan v3.4 P4)

Section chunks, hybrid search, top 10. recall@5 = queries with a relevant passage in the top 5.
Frozen 40 (v1.0 labels) are reported only; every choice was made on the dev split.

| Rung | Label | Headers | Rewrite | Rerank | Frozen recall@5 | Frozen MRR@10 | Dev recall@5 | Dev MRR@10 |
|---|---|---|---|---|---|---|---|---|
| 0 | baseline | False | False | False | 23/40 | 0.349 | 13/20 | 0.5881 |
| 1 | headers | True | False | False | 25/40 | 0.4182 | 16/20 | 0.6318 |
| 2 | headers+glossary | True | True | False | 22/40 | 0.4107 | 17/20 | 0.6679 |
| 3 | headers+glossary+rerank | True | True | True | 24/40 | 0.4546 | 11/20 | 0.4749 |

## Answerability threshold (dev only)

Chosen: **0.4066** (at most 1 answerable dev query abstains).

| Threshold | Answerable abstained | Unanswerable caught |
|---|---|---|
| 0.0349 | 0 | 0 |
| 0.0884 | 0 | 1 |
| 0.1554 | 0 | 2 |
| 0.2033 | 1 | 2 |
| 0.2552 | 1 | 3 |
| 0.2655 | 1 | 4 |
| 0.2759 | 1 | 5 |
| 0.3941 | 1 | 6 |
| 0.4066 | 1 | 7 |
| 0.4427 | 2 | 7 |
| 0.8123 | 3 | 7 |
| 0.8328 | 4 | 7 |
| 0.8862 | 4 | 8 |
| 0.9567 | 5 | 8 |
| 0.9592 | 6 | 8 |
| 0.9709 | 7 | 8 |
| 0.9817 | 8 | 8 |
| 0.9836 | 9 | 8 |
| 0.9907 | 10 | 8 |
| 0.9918 | 11 | 8 |
| 0.9945 | 12 | 8 |
| 0.9948 | 13 | 8 |
| 0.9948 | 14 | 8 |
| 0.9955 | 15 | 8 |
| 0.9965 | 16 | 8 |
| 0.9977 | 17 | 8 |
| 0.9998 | 18 | 8 |
| 0.9998 | 19 | 8 |
