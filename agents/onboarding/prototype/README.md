# CredAssure: Employee Onboarding Agent

> **Reference prototype, not part of the running app** (added 23 Nov 2026 by owner decision; author Mousita,
> PR #43 commit `6936705`, kept as written). It is a stand-alone readiness service with **its own synthetic rule set
> and HR data** (roles such as Finance Analyst, courses INDUCTION/COC/INFOSEC/FINDATA/WCPROC, policies POL_CREDIT and
> POL_DATA, employees `EMP-001`…, as-of 2026-11-02). The project's Gate 1 uses the frozen HR store and rules instead
> (`data/frozen/v1/hr.db`, DATA_SPEC §1: FIN-101, AML-201, DPDP-101, WC-POL v3, `E001`…, as-of 2026-11-15) and the
> 10 frozen onboarding items T026–T035. So:
> - Nothing here is mounted in the gateway, called by the Supervisor or used by the web app, and no reported number
>   comes from it. Its `eval/onboarding_eval.jsonl` (10/10) runs on its own data, not the BRD test set.
> - Its design is built into the real agent as **onboarding 0.3.0** (PR #44): an independent checker beside the engine
>   (`src/credassure/agents/onboarding/checker.py`), "who fixes it" on every blocker, a source record per rule.
> - Sections 4 and 5 below describe wiring it into the old FinBridge UI and nginx; those were retired (PR #37) and the
>   web app shows readiness from the gateway (`GET /v1/cases/{id}/readiness`). Do not follow them in this repo.
> - In this repo: `make onboarding-prototype` runs its tests (part of `make check`); `make install` already installs
>   what `requirements.txt` lists. To try its API, run it on another port than the gateway:
>   `cd agents/onboarding/prototype && uv run python -m readiness.generate_hr_data && uv run uvicorn readiness.demo_app:app --port 8100`
>   (`data/hr.db` and `data/hr_profiles.json` are gitignored).

This is the Employee Onboarding Agent for CredAssure (BRD v3.1, §4.2, ONB-01 to ONB-07). It decides whether the
employee preparing a loan proposal is cleared to do it: **GO**, **NO-GO** or **NEEDS_INPUT** (**ERROR** if the HR store
can't be read). Every rule is reported as pass, fail or unknown, every blocker is explained in plain language, and
Aadhaar, PAN and bank account numbers are removed from chat. Code makes the decision. The model (Qwen3-8B) only
rewords the explanation, and its wording is used only if a guard accepts it.

The full developer guide (requirements traceability, Supervisor integration and UI integration) is shared as a separate document.

## 1. Install (Windows PowerShell)

```powershell
cd agents/onboarding/prototype   # in this repo
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1          # if blocked: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
pip install -r requirements.txt
python -m readiness.generate_hr_data  # 20 synthetic employees -> data\hr.db
python -m pytest -q                   # expect: 127 passed
python -m eval.run_eval               # expect: 10/10, 8/8, 4/4
```
On macOS or Linux, use `python3 -m venv .venv` and `source .venv/bin/activate`.

## 2. Run the agent (no model needed)

```powershell
uvicorn readiness.demo_app:app --reload --port 8000
```
Open http://127.0.0.1:8000/docs and try:
- `GET /api/agents/onboarding/readiness?caseId=CASE-001&asOf=2026-11-02` returns GO (preparer EMP-001)
- `caseId=CASE-002` returns NO-GO (missing training); `caseId=CASE-003` returns NO-GO (credit policy not acknowledged)
- `POST /api/agents/onboarding/message` with `{"case_id":"CASE-002","message":"Why am I blocked? PAN ABCDE1234F","as_of":"2026-11-02"}`

## 3. Add a model

| Where | One-time setup | In each PowerShell window |
|---|---|---|
| Your computer (Ollama) | install Ollama, then `ollama pull qwen3:8b` | `. .\scripts\use_ollama_qwen.ps1` |
| Course endpoint (scored runs) | edit the two EDIT lines in `scripts\use_course_qwen.ps1` (group URL, path to your .crt) | `. .\scripts\use_course_qwen.ps1` (it asks for the key) |
| Off | | `. .\scripts\use_template_only.ps1` |

Then check it: `python -m readiness.llm_check`. It shows whether the model's wording was accepted or the template was used.
Never put the key in a file, Git, a screenshot or chat.

## 4. Connect the FinBridge UI

1. Copy `ui_integration/onboarding.live.ts` into the UI's `src/services/onboarding.ts`, and adjust `toReadinessResult` to `src/types/index.ts`.
2. In the UI's `.env.local`, set: `NEXT_PUBLIC_ONBOARDING_LIVE=true` and `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api` (see `ui_integration/env.local.example`).
3. Run the agent (step 2), then `npm run dev` in the UI, and log in as `preparer@finbridge.demo` (mapped to EMP-001 in `data/user_map.json`).
4. Live site: add `ui_integration/nginx_onboarding.conf` to the nginx server block.

Only **GO** unlocks the financial tabs. NO-GO, NEEDS_INPUT and ERROR keep them locked.

## 5. Connect to the team's backend and Supervisor

- FastAPI: `from readiness.api import router; app.include_router(router)`
- LangGraph: `from readiness.graph import readiness_node, route_after_readiness`, add the node, and route "go" or "pause"
- Chat: when the Supervisor classifies a message as onboarding, it calls `readiness.chat.handle_message(case_id, employee_id, text)`
- Shared database: set `CREDASSURE_DB` to the team database (it adds the `readiness_status` and `preparer_id` columns if missing)

## Layout
```
readiness/  rules.py  schemas.py  tools.py (read-only HR)  checker.py  explain.py (Qwen)  gate.py  pii.py  chat.py
            api.py  demo_app.py  graph.py  case_store.py  identity.py  audit.py  generate_hr_data.py  llm_check.py
eval/       onboarding_eval.jsonl (10, BRD test set)  regression_eval.jsonl (8)  pii_eval.jsonl (4)  run_eval.py
tests/      127 tests (rules, API, PII, Qwen client, HTTPS certificate)
scripts/    use_ollama_qwen.ps1/.sh  use_course_qwen.ps1/.sh  use_template_only.ps1
ui_integration/  onboarding.live.ts  env.local.example  nginx_onboarding.conf  ReadinessBanner.example.tsx
```
All data is synthetic. The gold answers in `eval/onboarding_eval.jsonl` are drafts: another team member must verify them (BRD §5.2).
