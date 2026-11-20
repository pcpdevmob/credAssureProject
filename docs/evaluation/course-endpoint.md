# Model comparison: local qwen3:8b vs the course endpoint or the hosted provider

The evaluated path is the local profile (ADR 0036): every reported number comes from Ollama `qwen3:8b` on the Mac.
This page runs the same evaluation on the course endpoint (`MODELS=course`, `deploy/env/models-course.env`) and
compares the two, item by item. It changes no code path and no reported number; the result is a comparison for the
report ("scores on the course's full-precision model may differ by a few items", ADR 0036 consequences).

## 1. Credentials (once, in `.env`; never in `deploy/env/models-course.env`)
From the course portal: the group chat key, the shared embeddings key and the two CA certificates.
```
LLM_API_KEY=<group chat key>
EVAL_API_KEY=<group chat key>
EMBED_API_KEY=<shared embeddings key>
LLM_CA_CERT=/absolute/path/vm06-ca.crt
EMBED_CA_CERT=/absolute/path/vm02-ca.crt
```
Connect the course VPN first if the hosts (103.42.50.41) need it.

## 2. Reachability and structured output
```
make llm-probe MODELS=course
```
`guided JSON: OK` means the endpoint answers and honours the schema. A TLS error means a wrong CA path; a timeout
means VPN or network.

## 3. Vector index: copy or re-ingest
The course embeddings are the same model as the local index (bge-small-en-v1.5). Check before re-embedding
115,000 chunks (about two hours at the endpoint's rate limit):
```
make embed-parity MODELS=course
```
- `SAME` → `cp -R var/chroma-local-bge var/chroma-course-bge` (seconds).
- `DIFFERENT` → `make ingest MODELS=course` (about two hours; leaves the local index untouched).

## 4. Smoke test, then the comparison run
```
make eval MODELS=course ARGS="--ids T001 T082"
make eval MODELS=course ARGS="--only regulatory negotiation offers e2e injection refusal"
```
The second run covers every model-dependent category. Onboarding, cash flow, routing and isolation are decided by
code, so they show nothing about the model; add them (or drop `--only`) for a full 100-item run. The endpoint is
shared and rate limited (`LLM_RATE_PER_MINUTE=55`): expect it to be slower than the Mac and avoid the hours before
other groups' deadlines.

## 5. Compare
```
make compare-runs A=var/eval/<local run> B=var/eval/<course run> ARGS="--out var/eval/course-vs-local.md"
```
Passes per category on the shared items, every item that flipped, and latency and tokens. Use the latest local run
on the same code (today's 33-item recheck plus the 67-item run on main).

## Reading the result
- Code-decided categories should not move; if one does, it is a configuration difference (embeddings, context,
  thinking switch), not the model.
- Regulatory varies by about ±1 between runs on the same model; a larger gap is a real model or serving difference
  (quantisation: the Mac runs a 4-bit build, the course serves full precision).
- Do not switch the evaluated path from this comparison alone: that is an owner decision and a new ADR (it would
  change every reported number and needs a full rerun of K3 and the ablations on that endpoint).

## Same comparison for the hosted deployment model (`MODELS=hf`)
The deployment plan serves `Qwen/Qwen3-8B` through Hugging Face Inference Providers (provider Featherless AI, FP8).
Embeddings, reranker and the vector index stay local, so no index work is needed.
1. `.env`: `LLM_API_KEY=<Hugging Face fine-grained token with "Make calls to Inference Providers">` and
   `EVAL_API_KEY=<same token>`. (MODELS=local ignores them: its profile sets its own key.)
2. `make llm-probe MODELS=hf` (reachable, thinking off, JSON).
3. `make eval MODELS=hf ARGS="--ids T001 T082"`, then
   `make eval MODELS=hf ARGS="--only regulatory negotiation offers e2e injection refusal"` (about $0.05).
4. `make compare-runs A=var/eval/<local run> B=var/eval/<hf run>`.
