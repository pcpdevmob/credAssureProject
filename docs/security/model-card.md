# CredAssure model card

Status: v1.1.0, 2026-11-20 (scope #3). Intended use, users, out-of-scope uses, refusal policy, evaluation results,
fairness, limitations and the Sutra mapping are in the system card: [../SYSTEM_CARD.md](../SYSTEM_CARD.md). This page keeps
the model and data details.

## Models
| Role | Model | Notes |
|---|---|---|
| Chat, all agents | Qwen3-8B (course endpoint `Qwen/Qwen3-8B`, local Ollama `qwen3:8b`) | ≤ 8B, no fine-tuning, no vision; thinking turned off; temperature 0; every call cached (NFR-05) |
| Embeddings | bge-small-en-v1.5 | Course endpoint or local |
| Reranker | BAAI/bge-reranker-base at a pinned revision | Scores for the answerability gate only (`RERANK_ORDER=false`) |
| Judge J1 | Same chat model | Calibrated against two human labellers on all 19 judged answers: agreement 17/19, kappa 0.789 (≥ 0.7, so J1 may score free text; ADR 0014) |

Swapping the model is configuration only (`MODELS=local|course|hf`, quality scenario Q7).

| Where the same Qwen3-8B runs | Build | Measured |
|---|---|---|
| Local Ollama `qwen3:8b` (`MODELS=local`, the evaluated path, ADR 0036) | 4-bit | 88/100; every reported number |
| Course endpoint `Qwen/Qwen3-8B` (`MODELS=course`) | full precision | 53/66 vs 54/66 on the model-dependent items (≈ 87/100; only T003 differs); latency p50 3.0 s vs 23.4 s on regulatory items; embeddings identical to the local index (cosine 1.00000 on 40 chunks) |
| Hugging Face router, provider Featherless `Qwen/Qwen3-8B:featherless-ai` (`MODELS=hf`) | FP8 | Not yet run; planned as the hosted deployment's fallback when the course endpoint is unreachable |

Detail and commands: [../evaluation/course-endpoint.md](../evaluation/course-endpoint.md). A different endpoint is a
comparison, not a new headline: switching the evaluated path would need a new ADR and a full rerun. Prompts are versioned, hashed YAML files
(`prompts/*.yaml` in each package, `credassure.core.prompts`); a version bump is a cache miss, so a changed prompt is never answered from an old reply.

Results, ablations, safety checks and limitations are in [system card §9 and §13](../SYSTEM_CARD.md#9-evaluation-and-adversarial-results).
In short: 88/100 against 23/100 for the best single-prompt baseline on the same model; the model is
kept out of arithmetic and gate decisions because, when it does them (ablations A1, A4), those categories fall from
41/41 to 10/41 and from 45/45 to 13/45. The 40-item safety suite safety_v2 passes 40/40 with 0 critical; with
the guardrails off (A6) it falls to 30/40, all ten failures personal-data items.

## What the model does and does not do
| Does | Does not |
|---|---|
| Draft stage narratives from ledger slots | Decide any gate, figure, route or ranking |
| Extract charges from one KFS per call (code keeps only verbatim spans) | See another offer's KFS in the same call |
| Pick one copilot tool from a fixed list | Add a tool, call a tool for another case, or run code |
| Write cited answers; code removes sentences without a valid span | Approve, accept, sign or submit anything |

## Data provenance
CredAssure's retrieval corpus is built only from public, official Indian sources: RBI, CGTMSE, the Gazette, CBIC and the
GST Council, SIDBI, ministries, courts and banks' published schedules of charges. Company, lender, employee and offer data
is synthetic, made by seeded code.

Collection follows ADR 0020:
- **Scripted fetches:** they honour robots.txt, make at most one request per second and identify the team with a
  contactable User-Agent. A host that blocks or refuses is stopped, and a temporary failure gets exactly one retry after
  24 hours. There are no spoofed headers, headless browsers or CAPTCHA solving.
- **Manual-only hosts:** blocked hosts, hosts whose terms restrict automated access, and RBI, e-Gazette, incometaxindia
  and India Code are downloaded by hand in a browser.
- **Where it runs:** on team members' personal machines and networks.
- **No redistribution:** raw third-party files are never redistributed; only hashes, licence basis and metadata are
  committed.
- **Court judgments:** used only for legal points, never for person-centric features.
- **Ingestion safety:** ingestion is size-limited and text-only (pypdf, no rendering). Rejected files are quarantined.
