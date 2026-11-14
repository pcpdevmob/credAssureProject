# CredAssure — Data Sources and Resources (all agents)

Status legend: **✅ verified** = URL opened/seen in search on 3 Nov 2026 · **⚠️ verify** = known source, exact URL must be confirmed before adding to `data/corpus/manifest.yaml`.
Indian banks are migrating to `.bank.in` domains (e.g. `sbi.bank.in`, `bandhan.bank.in`) and RBI is moving to `website.rbi.org.in` / `rbi.org.in/en/web/rbi/...`; old URLs may redirect. Always record the URL you actually downloaded from plus its SHA-256.

Identifier note (5 Nov 2026): the R-IDs here are canonical; `docs/DATA_RESOURCES.md` maps P-numbers to them, adds new IDs
(R-RBI-01, -11, -12, -13, R-MSME-04..06, R-BANK-06..16, R-RATE-02, R-CAL-01, R-SIDBI-*, R-DATA-*) and replaces every
⚠️ verify below with the URL confirmed in the 5 Nov 2026 web check. Where this file still says ⚠️, DATA_RESOURCES.md wins.

All company, employee, lender and offer data stays **synthetic** (BRD §10). Real sources below serve two purposes only: (1) the copilot's retrieval corpus, and (2) realistic parameter ranges for the seeded generators. Every parameter range taken from a real source is recorded in the generator file header with the source ID from this document.

---

## 0. Design impacts found while sourcing (act on these before G1)

| # | Finding | Source | Change required |
|---|---|---|---|
| D1 | KFS and APR disclosure for commercial banks now sit in the **Commercial Banks – Responsible Business Conduct Directions, 2025** (Annex XIII – KFS), issued 28 Nov 2025 and updated as on 1 Jul 2026. The 2024 standalone KFS circular was part of the consolidation. | R-RBI-02 | Copilot must cite the 2025 Directions as current; tag older KFS circulars `superseded_by` (KR-04). Use Annex XIII as the template for synthetic KFS docs and for confirming the APR annualisation convention. |
| D2 | CGTMSE Annual Guarantee Fee for facilities sanctioned/renewed on or after 1 Apr 2025 is charged on the **guaranteed amount in year 1 and on the outstanding amount thereafter**. | R-CG-02 | Replace the offer field `guarantee.on{sanctioned,outstanding}` with `guarantee.basis = "y1_guaranteed_then_outstanding"` (keep the old enum values for planted variants). LW-07 known-answer cases must use this basis. |
| D3 | CGTMSE covers **micro and small** enterprises only, with guarantee ceiling raised to ₹10 crore. | R-CG-01, R-CG-03 | The demo MSME must be classified Small (≤ ₹25 cr investment, ≤ ₹100 cr turnover under S.O. 1364(E)) or CGTMSE offers are unrealistic. Add `enterprise_class` to `order.json`/case metadata. |
| D4 | MSE classification limits revised w.e.f. 1 Apr 2025: Micro ₹2.5 cr / ₹10 cr, Small ₹25 cr / ₹100 cr, Medium ₹125 cr / ₹500 cr (investment / turnover). | R-MSME-02 | Generator draws MSME profiles inside the Small band. |
| D5 | Payments to micro/small suppliers beyond the MSMED Act s.15 limit (max 45 days) are deductible only on actual payment — s.43B(h) of the 1961 Act, now s.37(2)(g) of the Income-tax Act 2025. | R-TAX-01 | Payables to `msme_supplier=true` must have due dates ≤ 45 days in synthetic data; WC validator flags violations as a data-quality warning (not a gate). Copilot gold answers cite s.37(2)(g). |
| D6 | Loans to Micro and Small Enterprises with floating rates are linked to an external benchmark (since 1 Oct 2019). | R-RBI-05 | Floating-rate synthetic offers use `benchmark="EBLR"`; an MCLR-linked MSE floating offer becomes a planted anomaly. |
| D7 | GST is 18% on loan processing / credit-granting fees, while interest is exempt. | R-GST-01, R-GST-02 | Keep `GST_RATE=0.18` on fees only; never on interest. Whether GST applies to a CGTMSE fee passed on to the borrower is **unconfirmed** — make it a per-offer flag `gst_applicable` and test both. **Recheck:** 11/2017 was amended by 15/2025-CT(R) (eff 22 Sep 2025); confirm heading 9971 is still 18% before G1. |
| D8 | RBI issued a TReDS Master Direction on 23 Jun 2026. | R-RBI-08 | Copilot explains TReDS from this document (not priced — BRD §4.3). |

---

## 1. Supervisor (master agent)

No external data. Inputs are agent results, config and the fact ledger.

| ID | Resource | Use | Status |
|---|---|---|---|
| T-01 | LangGraph (Python) + `langgraph-checkpoint-sqlite` | Typed state graph, interrupts for approval, SQLite checkpointer | package names ✅; docs URL ⚠️ verify |
| T-02 | Track B brief: `/mnt/project/Capstone-Templates-GenAI-Agentic-AI.md` | Planner→executor→critic, ≥3 tools, error handling, budget caps | ✅ project file |
| T-03 | `docs/BRD.md` §7, §8.2, §8.8 | Gate rules, routing threshold, boundary config | ✅ project file |

Synthetic config data: `app_config` seeds (threshold ₹1,50,00,000, `BOUNDARY_RULE=hold`, buffers).

---

## 2. Employee Onboarding Agent

**Runtime data:** synthetic HR store only (DATA_SPEC §1). **Corpus data** (policy collection + public) so training/rule explanations can cite real obligations:

| ID | Resource | Publisher | Use | Status / URL |
|---|---|---|---|---|
| R-DPDP-01 | Digital Personal Data Protection Rules, 2025 (G.S.R. 846(E), 13 Nov 2025) and DPDP Act, 2023 | MeitY | Basis for synthetic `DPDP-101` training and PII-handling policy; refusal reason for storing Aadhaar/PAN | ⚠️ verify on meity.gov.in / egazette.gov.in |
| R-RBI-09 | Commercial Banks – Know Your Customer Directions, 2025 (28 Nov 2025; amended 29 Dec 2025) | RBI | Basis for synthetic `AML-201` training content | ✅ listed at https://website.rbi.org.in/en/web/rbi/regulations-non-banking/notifications?delta=20 (find the commercial-banks KYC entry) |
| S-HR-01 | Synthetic training catalogue, role matrix, WC-POL v1–v3, data-handling policy | Team | Rule source for ONB-02 | generated |

Fake-but-valid identifiers for **redaction tests only** (never stored): generate Aadhaar-format numbers that pass Verhoeff, PAN-format strings, IFSC-format strings in `tests/security/fixtures.py`. Use `Faker` with `en_IN` locale for display names. ⚠️ verify Faker `en_IN` provider coverage for your installed version.

---

## 3. Working Capital Advisory Agent

**Runtime data:** synthetic case files (DATA_SPEC §2). **Parameter sources and corpus:**

| ID | Resource | Publisher | Use | Status / URL |
|---|---|---|---|---|
| R-MSME-01 | Micro, Small and Medium Enterprises Development Act, 2006 (esp. s.15–16: payment within agreed period, max 45 days; interest on delay) | Govt of India | Payables/receivables timing ranges; copilot answers | ⚠️ verify on indiacode.gov.in (moved from indiacode.nic.in) |
| R-MSME-02 | Notification S.O. 1364(E), 21 Mar 2025 — revised MSME classification (w.e.f. 1 Apr 2025) | Ministry of MSME | MSME profile bands (D3, D4) | ✅ https://egazette.gov.in/writeReadData/2025/261838.pdf ; reverse-graduation clarification ✅ https://udyamregistration.gov.in/docs/Circular_reverse_24102025.pdf |
| R-MSME-03 | Principal notification S.O. 2119(E), 26 Jun 2020 | Ministry of MSME | Superseded-limits distractor (KR-04 filter test) | ✅ https://dcmsme.gov.in/State-Gov/Notification_%20S%20O%202119.pdf |
| R-TAX-01 | Income-tax Act, 2025 s.37(2)(g) (successor of s.43B(h)); Rajya Sabha reply, 21 Jul 2026 | Ministry of Finance | D5; cash-timing rules for MSE payables | ⚠️ verify bare Act on incometaxindia.gov.in; 1961-Act s.43B page ✅ https://www.incometaxindia.gov.in/w/section-43b-40 |
| R-RBI-04 | Master Direction – Lending to MSME Sector (2017, updated 9 Feb 2026) | RBI | Working-capital assessment context; collateral-free lending | ✅ https://rbi.org.in/Scripts/BS_ViewMasDirections.aspx?id=11060 ; Feb 2026 amendment ✅ https://website.rbi.org.in/documents/d/rbi/amendmentdirections09022026 |
| R-RBI-05 | RBI FAQs — Micro, Small and Medium Enterprises (updated 29 Jul 2025) incl. how banks assess working-capital requirements, external-benchmark linkage | RBI | Copilot gold answers; D6 | ✅ https://www.rbi.org.in/scripts/FS_FAQs.aspx?Id=84 |
| R-RBI-06 | Priority Sector Lending – Targets and Classification Directions, 2025 (24 Mar 2025) | RBI | Copilot context (all bank loans to MSMEs are PSL) | ✅ listed at https://website.rbi.org.in/web/rbi/financial-inclusion-and-development/master-directions |
| S-WC-01 | Electronics-manufacturing cost structure (components, labour, testing, packaging, logistics shares), customer payment terms 30–90 days, advance 0–20% | Team assumption | Generator ranges | document as **assumption** in generator header; no public source required |

---

## 4. LendWise Agent (owner: Pritish)

**Runtime data:** synthetic offers, lender scripts, synthetic KFS docs (DATA_SPEC §3–4). **Parameter sources and corpus:**

| ID | Resource | Publisher | Use | Status / URL |
|---|---|---|---|---|
| R-RBI-02 | Commercial Banks – Responsible Business Conduct Directions, 2025 (RBI/DOR/2025-26/170, 28 Nov 2025; updated 1 Jul 2026), Chapter VIII Responsible Lending Conduct, **Annex XIII KFS** | RBI | KFS format for synthetic docs; APR definition and illustration (confirm `APR_CONVENTION`); copilot citations | ✅ https://rbi.org.in/Scripts/BS_ViewMasDirections.aspx?id=13140 ; PDF ✅ https://website.rbi.org.in/documents/d/rbi/commercial-banks-responsible-business-conduct-1- |
| R-RBI-03 | Commercial Banks – Interest Rates on Advances Directions, 2025 | RBI | Floating-rate/benchmark rules; LW-08 explanations | ✅ https://www.rbi.org.in/Scripts/BS_ViewMasDirections.aspx?id=13149 |
| R-RBI-10 | Commercial Banks – Credit Facilities Directions, 2025 | RBI | Definitions referenced by RBC Directions | ⚠️ verify via https://www.rbi.org.in/Scripts/BS_ViewMasterDirections.aspx |
| R-CG-01 | CGTMSE — Annual Guarantee Fee structure for CGS-I (guarantees approved/renewed on/after 1 Apr 2025), slab table starting 0.37% p.a. for ₹0–10 lakh | CGTMSE | AGF slab rates for synthetic offers (LW-07) | ✅ https://cgtmse.in/Home/VS/47 |
| R-CG-02 | CGTMSE — AGF basis: guaranteed amount in year 1, outstanding thereafter (sanctioned/renewed on/after 1 Apr 2025) | CGTMSE | D2 engine rule | ✅ https://cgtmse.in/Home/VS/101 |
| R-CG-03 | CGTMSE circulars list (incl. Circular 252/2024-25 AGF reduction above ₹1 cr; 256/2025-26 guarantee expiry extension for term loans) | CGTMSE | Corpus volume (~60 circulars) + fee history for superseded tests | ✅ https://www.cgtmse.in/Circulars |
| R-CG-04 | SBI CGTMSE page (AGF payable upfront for year 1, then annually) | SBI | Timing of AGF cash flow in schedule | ✅ https://sbi.bank.in/web/business/sme/sme-government-schemes/cgtmse |
| R-GST-01 | Notification 11/2017-Central Tax (Rate), heading 9971 financial services (18% residual) | CBIC | D7, `GST_RATE` | ⚠️ verify on cbic-gst.gov.in |
| R-GST-02 | Notification 12/2017-Central Tax (Rate), entry 27 — interest on loans exempt | CBIC | D7 (no GST on interest) | ⚠️ verify on cbic-gst.gov.in |
| R-BANK-01 | SBI Advances-related service charges (C&I, SME, AGL) w.e.f. 01.04.2019 | SBI | Processing / prepayment / review fee ranges | ✅ https://sbi.co.in/documents/16012/76239/ADVANCES+RELATED+SERVICE+CHARGES+W.E.F.+01.04.2019+A.pdf |
| R-BANK-02 | SBI SME Smart Score (unified processing fee 0.40%, WC margin 20%, TL margin 33%) | SBI | Low-fee lender archetype | ✅ https://sbi.co.in/portal/web/sme/sme-smart-score |
| R-BANK-03 | Bandhan Bank Schedule of Charges — SME & Corporate Loans (16 Jan 2026): processing up to 2%, prepayment up to 2% | Bandhan Bank | High-fee lender archetype | ✅ https://bandhan.bank.in/sites/default/files/2026-01/Schedule-of-Charges-SME-and-Corporate-Loans-16012026.pdf |
| R-BANK-04 | Indian Bank — Service Charges for MSME Products (term-loan upfront fee 1% for ₹5–100 lakh; rating-based above ₹100 lakh) | Indian Bank | Rating-dependent fee archetype | ✅ https://indianbank.in/wp-content/uploads/2018/11/Service-Charge-for-MSME-Products-1.pdf (2018 — tag as possibly superseded) |
| R-BANK-05 | Indian Bank MSME Service Charges (2022) | Indian Bank | Newer version of R-BANK-04 | ✅ https://www.indianbank.in/wp-content/uploads/2022/04/MSME-Service-Charges.pdf |
| R-BANK-06 | Schedules of charges from 8–12 more banks/NBFCs (BoB, PNB, Canara, Union, HDFC, ICICI, Axis, Kotak, IDFC FIRST, Bajaj Finance, Tata Capital, L&T Finance) | Banks | Fee ranges + corpus volume (~30 docs) | ⚠️ verify each "schedule of charges / MSME" page |
| R-RATE-01 | Lending-rate ranges (EBLR / repo-linked rates, weighted average lending rates) | Banks' EBLR pages; RBI data portal | Synthetic rate ranges for fixed and floating offers | ⚠️ verify (RBI DBIE / data portal and each bank's EBLR page) |

**Synthetic fee ranges for the generator** (cite these IDs in the header): processing fee 0.40%–2.00% (R-BANK-02, R-BANK-03); term-loan upfront 0.70%–1.25% (R-BANK-04); prepayment up to 2% (R-BANK-03); AGF from R-CG-01 slab table with basis R-CG-02; GST 18% on fees (R-GST-01).

---

## 5. Verification Critic

No external data. Its inputs are the fact ledger, retrieved passages and generated text.

| ID | Resource | Use | Status |
|---|---|---|---|
| S-VER-01 | Number-format fixture set (≥50 cases: `₹1,42,00,000`, `1.42 crore`, `142 lakh`, `Rs. 142L`, `12%`, `0.12`, dates) | VER-01 tests | generated in `tests/unit/test_normaliser.py` |
| S-VER-02 | Banned-phrase list (acceptance/signing language, approval predictions, false urgency) | VER-03 | team-written, versioned YAML |
| R-RBI-02 | KFS Annex XIII required fields | Report-completeness checklist (VER-04) | ✅ see §4 |
| T-04 | OWASP Top 10 for LLM Applications (prompt injection, sensitive information disclosure) | Red-team taxonomy for the 20-prompt log | ⚠️ verify current edition on owasp.org |

---

## 6. Ask CredAssure Copilot — corpus build plan (target 500–600 docs)

| Collection / tag | Sources (IDs above) | Target docs |
|---|---|---|
| `public/rbi_md` | R-RBI-02, -03, -04, -06, -09, -10 + other relevant 2025 Commercial Banks Directions from the master-directions index ✅ https://www.rbi.org.in/Scripts/BS_ViewMasterDirections.aspx ; consolidation press release ✅ https://website.rbi.org.in/documents/d/rbi/pr1588rbiconsolidatedmasterdirections-1- | 30–40 |
| `public/rbi_faq` | R-RBI-05 + other RBI FAQ pages (MSME, KFS, EBLR) | 10–15 |
| `public/rbi_treds` | R-RBI-08: TReDS Directions 2026 (draft ✅ https://www.rbi.org.in/scripts/bs_viewcontent.aspx?Id=4976 ; final RBI/DPSS/2026-27/406, 23 Jun 2026 ⚠️ verify RBI URL); 2014 guidelines page ✅ https://website.rbi.org.in/en/web/rbi/payment-and-settlements/other-links/information-useful-to-banks-fis/guidelines (tag superseded) | 5–10 |
| `public/cgtmse` | R-CG-01..04 + circulars | 50–70 |
| `public/msme_gov` | R-MSME-01..03, Udyam FAQs, MSME Samadhaan, scheme guidelines (⚠️ verify on msme.gov.in, dcmsme.gov.in, samadhaan.msme.gov.in) | 40–60 |
| `public/tax` | R-TAX-01, R-GST-01, R-GST-02, CBIC FAQs on financial services | 15–25 |
| `public/bank_charges` | R-BANK-01..06 | 30–40 |
| `public/sidbi` | SIDBI MSME schemes and FAQs (⚠️ verify on sidbi.in) | 15–20 |
| `public/dpdp_kyc` | R-DPDP-01, R-RBI-09 | 5–10 |
| `public/rbi_circulars_hist` | Pre-consolidation circulars withdrawn on 28 Nov 2025 (KFS 2024, older MSME circulars) — `superseded_by` set, used to test date filtering | 40–60 |
| `public/state_policies` | Other-state MSME/industrial policies (`jurisdiction` IN-GJ, IN-KA, IN-TN, IN-UP, IN-TS) — KR-04 distractors; Maharashtra (IN-MH) is the home state (ADR 0019) | 20 |
| `policy` | Synthetic internal policies + FAQ (DATA_SPEC §5) | 60–90 |
| `kfs` | Synthetic KFS docs (DATA_SPEC §4) | 120–160 |
| **Total** | | **~430–610** |

If public docs fall short of 320, the `rbi_circulars_hist` and `cgtmse` collections are the cheapest to expand.

---

## 7. Models, libraries and services

| ID | Item | Use | Status |
|---|---|---|---|
| M-01 | Course ≤8B OpenAI-compatible chat endpoint | All agent LLM calls | provided by course |
| M-02 | Course embeddings endpoint | Dense retrieval | provided by course |
| M-03 | `BAAI/bge-reranker-base` (local cross-encoder) | KR-03 reranker if mentor allows local models (Q7); fallback `llm_pointwise` | ⚠️ verify model card on Hugging Face |
| T-05 | Chroma; SQLite FTS5 (`bm25()`); `sentence-transformers` | Retrieval | package names ✅ |
| T-06 | Langfuse Python SDK (v5 current on PyPI) + self-hosted server via Docker Compose (ADR 0016, https://langfuse.com/self-hosting/deployment/docker-compose) | Tracing with mask function | ✅ 5 Nov 2026 |
| T-07 | FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, Streamlit, PyJWT, argon2-cffi, slowapi, tenacity, Jinja2 | App stack | package names ✅ |
| T-08 | pytest, hypothesis, numpy-financial (eval gold only), ruff, mypy, bandit, pip-audit, gitleaks | Quality and security | package names ✅ |
| T-09 | `mcp` Python SDK (FastMCP), stdio | Optional read-only dev MCP server (stretch) | ⚠️ verify |
| T-10 | Faker (`en_IN`) | Fictional names for synthetic HR/MSME data | ⚠️ verify locale coverage |

---

## 8. Licensing and handling

- Public regulatory documents: store only the manifest and download script in git; raw files and extracted text are gitignored (BRD §10). Record a `license_note` per document and check each site's terms before bulk download; throttle ≤1 request/second.
- Third-party commentary sites (taxguru, taxmann, vinodkothari, mondaq, etc.) were used only to locate primary sources. **Do not add them to the corpus** — cite primary publishers only.
- No real company, employee, customer or borrower data anywhere.
