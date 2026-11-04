# Capstone Project Templates

**Executive Post Graduate Programme in Generative AI and Agentic AI**

*Two four-week, six-member team project tracks*
- **Track A** — Model-Side (direct model access, GPU required)
- **Track B** — API-Side (hosted ≤8B endpoint, no GPU for teams)

---

## Overview

| Parameter | Specification |
|---|---|
| Team size | 6 members |
| Duration | 4 weeks |
| Assumed effort | ~8–10 focused hours per person per week (working professionals) |
| Curriculum coverage | Modules 1–5: transformers, prompting, RAG, PEFT, multimodal, agents, serving, responsible AI |
| Tracks | Track A (GPU, direct model access) · Track B (API only, ≤8B backend) |

Both tracks are designed so that the intellectual difficulty sits in the design and evaluation decisions rather than in infrastructure setup. Starter repositories, notebooks and containers are supplied beforehand; the learning is in what teams choose to do with them.

---

## Track A — "Model-Side" Capstone
*(direct model access, GPU required)*

### Title
**Domain-Adapted Assistant: Fine-Tuning and Serving a Small Open LLM for a Regulated Enterprise Workflow**

### Scenario
The team picks one narrow enterprise domain — for example insurance claim triage, IT helpdesk resolution, clinical discharge summarisation, bank KYC query handling, or manufacturing SOP question-answering. A general 7–8B instruct model handles the domain poorly: wrong jargon, wrong output schema, inconsistent tone. The team must adapt it and prove the adaptation worked.

### What the Team Must Build

1. **Dataset (Week 1).** 800–2,000 instruction–response pairs. Allowed sources: public datasets, synthetic generation from a larger teacher model, or de-identified internal documents. Must include a held-out test set of 150–200 examples the team never trains on.

2. **Baseline (Week 1).** Zero-shot and few-shot prompting of the base model (Llama-3.1-8B-Instruct / Qwen2.5-7B-Instruct / Mistral-7B-Instruct). Record the numbers — this is the bar to beat.

3. **Fine-tuning (Week 2).** QLoRA / LoRA (PEFT) on the base model. At least two runs with different configurations (rank, learning rate, target modules, or epochs) plus one ablation, so the report has a comparison rather than a single lucky run.

4. **Alignment-lite (Week 2–3, optional stretch).** DPO on 200–300 preference pairs, or a rejection-sampling pass — only if Week 2 finished cleanly.

5. **RAG layer (Week 3).** The fine-tuned model wrapped with retrieval over a 200–1,000 document domain corpus. Chunking strategy, embedding model choice and a reranking step must each be a documented decision. Required comparison: base + RAG vs. fine-tuned vs. fine-tuned + RAG.

6. **Evaluation (Week 3).** Task metric (exact match / F1 / ROUGE / schema validity), an LLM-as-judge rubric on the held-out set, and latency plus tokens-per-second measured on the team's own serving stack.

7. **Serving and responsible AI (Week 4).** Merge/export adapters, quantise (GGUF or AWQ/GPTQ), serve via vLLM behind a FastAPI endpoint, containerised. Plus a short model card: intended use, data provenance, failure modes, refusal behaviour, and a red-team log of 20 adversarial prompts.

### Role Split for Six Members

| Role | Responsibility |
|---|---|
| Data & synthetic generation | Corpus sourcing, pair generation, de-identification, train/test split |
| Fine-tuning & tracking | QLoRA runs, hyperparameter sweeps, experiment logging |
| RAG pipeline | Chunking, embeddings, vector store, reranking |
| Evaluation & red-teaming | Metric harness, LLM-as-judge rubric, adversarial prompts |
| Serving, quantisation & infra | Adapter merge, quantisation, vLLM + FastAPI, Docker |
| Integration & documentation | Repo hygiene, model card, report, demo |

> Every member runs at least one training job — no one should finish the course without having touched a GPU directly.

### Deliverables

- Git repository with reproducible training and serving code
- Experiment tracking dashboard (Weights & Biases or MLflow)
- Model card covering intended use, data provenance, failure modes and refusals
- 12-page technical report
- 10-minute demo of the deployed endpoint

### Guardrails (keeping it doable in four weeks)

- Model size capped at 8B. No pretraining and no full-parameter fine-tuning.
- SSH access to a GPU machine, a working QLoRA starter notebook, and a Dockerfile will be provided.
- Dataset ceiling of 2,000 examples — enough to show real gains, small enough that a run finishes overnight.
- Week 1 checkpoint is a hard gate: baseline numbers recorded and dataset frozen. Teams that slip here are instructed to drop the DPO and quantisation stretch goals.

---

## Track B — "API-Side" Capstone
*(no direct model access, ≤8B model behind an endpoint)*

### Title
**Multi-Agent Operations Copilot: An Agentic System Built Entirely on a Hosted ≤8B Inference API**

### Scenario
The team is given only an OpenAI-compatible chat-completions endpoint backed by a single shared ≤8B instruct model, plus an embeddings endpoint. They cannot change weights, inspect logits, or swap in a frontier model. Everything must be won through prompting, retrieval, tool design, orchestration and evaluation. This is deliberately the harder engineering discipline — and closer to what most participants will actually do at work.

**Suggested domains:** procurement and vendor-review assistant, travel-and-expense policy agent, competitive-research analyst, incident postmortem drafter, financial-report question-answering agent, HR policy navigator.

### What the Team Must Build

I. **Task decomposition (Week 1).** A written specification of what the copilot does, what it must refuse, and what a correct answer looks like. Plus an evaluation set of 60–100 realistic queries with gold answers, written before any code.

II. **Prompt engineering baseline (Week 1).** Single-agent, single-prompt attempt. Systematic comparison of at least three prompting strategies (structured output with few-shot, chain-of-thought or self-consistency, decomposition prompting). Small models break in specific ways — the team must document how theirs breaks.

III. **RAG over a real corpus (Week 2).** 500–2,000 documents. Required: chunking experiments, hybrid retrieval (BM25 plus dense), a reranker, and citation-grounded answers. Retrieval recall@k must be measured separately from end-to-end answer quality — a key diagnostic when the generator is weak.

IV. **Agentic layer (Week 3).** A multi-agent or tool-using system (LangGraph, CrewAI, AutoGen, or hand-rolled) with at least three tools, an explicit planner→executor→critic loop, persistent state across turns, and error handling for tool failures, malformed JSON, infinite loops and token budget caps.

V. **Evaluation and observability (Week 3–4).** End-to-end accuracy against the Week 1 evaluation set, task completion rate, average tool calls per task, cost and latency per query, and a failure taxonomy separating retrieval miss, reasoning error, tool-call error and hallucination. Tracing via LangSmith, Langfuse or OpenTelemetry.

VI. **Ship it (Week 4).** Streamlit or React front-end, containerised, with rate limiting and caching. Responsible-AI section covering prompt-injection tests against the document corpus, PII handling, refusal behaviour, and a stated human-in-the-loop boundary for consequential actions.

> Small models fumble tool calls, so constrained decoding, JSON schema validation and retry logic are the core engineering content of this track.

### Role Split for Six Members

| Role | Responsibility |
|---|---|
| Domain spec & eval design | Scope definition, gold-answer evaluation set, refusal policy |
| Prompt engineering | Strategy comparison, structured output, failure characterisation |
| RAG / retrieval | Chunking, hybrid search, reranking, citation grounding |
| Agent orchestration & tools | Planner/executor/critic loop, tool interfaces, state and memory |
| Observability & safety | Tracing, failure taxonomy, prompt-injection and PII testing |
| Front-end & deployment | UI, containerisation, rate limiting, caching, demo |

### Deliverables

- Git repository with the full agent stack
- Trace dashboard showing real query executions
- Evaluation report including the failure taxonomy
- 12-page technical report
- 10-minute live demo

### Guardrails (keeping it doable in four weeks)

- The endpoint, an API key with a per-team token quota, and a starter agent skeleton will be provided.
- Corpus capped at 2,000 documents; agent capped at 10 steps per query.
- Week 1 gate: evaluation set frozen and baseline numbers recorded before any agent code is written. This is the single most common failure mode — teams that build first and evaluate later have nothing to report.
- The weakness of the 8B model is an explicit learning objective, not a complaint. "What did we do to compensate for a small model?" is a graded section.

---

## Side-by-Side Comparison

| | Track A (GPU) | Track B (API) |
|---|---|---|
| Modules emphasised | 1, 3, 5 (and 2) | 2, 4, 5 |
| Core skill | Model adaptation and serving | Orchestration and evaluation |
| Hardest week | Week 2 (training instability) | Week 3 (agent reliability) |

---

## Grading

| Component | Weight |
|---|---|
| Technical depth and rigour | 30% |
| Punctuality and consistent progress | 25% |
| Working deployed system | 20% |
| Report and demo | 25% |
