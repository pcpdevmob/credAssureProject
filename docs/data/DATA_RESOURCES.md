# CredAssure — Data resources for all agents (capstone, open data only)

Every input is Indian public data (legal basis L1–L4) or synthetic and team-owned (L5). No foreign documents (ADR 0019). Public files are downloaded via
`data/corpus/manifest.yaml`, hashed and frozen at G1. Nothing needs a login, payment, partnership or personal data.
URLs marked *verify* must be opened and confirmed before they enter the manifest.

Agents: SUP Supervisor + routing · ONB Onboarding · WC Working Capital · LW LendWise · VER Critic · CP Copilot · EVAL evaluation

## Identifier scheme
The **R-ID is canonical**: `data/corpus/manifest.yaml` `doc_id` values, generator file headers, gold-answer notes and
`data/corpus/audit.py` all use it. One resource that spans several documents gets suffixed manifest IDs
(e.g. R-RATE-02-REPO, R-MSME-01-S16, R-RBI-08-DRAFT). The P-number is kept only as a short row label for this table. Detailed per-agent notes
and design impacts D1–D8 for each R-ID are in `docs/RESOURCES.md`. Synthetic sets keep their S-numbers (S01–S24).

## Verification status (web check, 5 Nov 2026)
Every former *verify* row now has a primary-publisher URL. Open points that must be closed before G1:
- **GST (R-GST-01):** Notification 11/2017-CT(R) was amended by 15/2025-CT(R) (rate rationalisation, eff 22 Sep 2025).
  Confirm the heading 9971 rate for loan processing fees is still 18% before freezing `data/reference/gst.yaml` (D7).
- **CGTMSE ceiling:** RESOURCES D3 says ₹10 cr; the SIDBI CGTMSE page still says ₹5 cr. Confirm on cgtmse.in.
- **S21 APR example:** the RBI Annex B PDF returned HTTP 403 to the checker; the numbers come from the HTML of R-RBI-13 and
  R-RBI-02 para 348. Two team members transcribe from the PDF in a browser and sign off.
- **Bank of Baroda MSME fee table** was only visible on a third-party site; confirm on the bank page before using its range.
- **DPDP Rules phasing:** Rules 3, 5–16, 22–23 commence about 13 May 2027, after `AS_OF_DATE`; tag their `effective_from`.

## Legal basis codes
| Code | Basis | What the team may do |
|---|---|---|
| L1 | Government Open Data License – India (data.gov.in) | Use, adapt, redistribute with attribution |
| L2 | Copyright Act 1957 s.52(1)(q)(i): Official Gazette matter (except Acts) | Store, index, quote, redistribute |
| L3 | s.52(1)(q)(ii): Acts reproducible with commentary | Store/index locally; quote short passages with citation; never commit raw text |
| L4 | Public documents; research fair dealing s.52(1)(a); facts not copyrightable | Local research use; extract numeric facts; never redistribute files |
| L5 | Team-owned synthetic data, eval sets, code | Release: data CC BY 4.0, code MIT |

Court judgments (Supreme Court, High Courts) are **L2**: Copyright Act 1957 s.52(1)(q)(iv) permits reproducing a judgment
or order of a court unless the court prohibits it. L6 (US federal works) was removed with the US distractors (ADR 0019).

## Corpus sources (ADR 0019): ≥500 real Indian documents, target 750
`data/corpus/sources.yaml` holds index pages, link patterns and methods. Synthetic KFS and policies are extra and never
count toward 500; real + synthetic ≤ 2,000. RBI, e-Gazette, incometaxindia and India Code are manual only.

| # | Source | Target | Basis | applies_to | Jurisdiction | Method |
|---|---|---|---|---|---|---|
| 1 | RBI Master Directions (2025 consolidation) | 120 | L4 | per document | IN | manual |
| 2 | RBI circulars superseded by the 2025 consolidation | 60 | L4 | per document | IN | manual |
| 3 | RBI FAQs, lending-rate releases, MSME press releases, Bulletin/Annual Report chapters | 60 | L4 | all | IN | manual |
| 4 | CGTMSE circulars, scheme guidelines, fee pages | 180 | L4 | all | IN | script, else manual |
| 5 | NCGTC schemes (ECLGS, CGFMU, …) | 25 | L4 | all | IN | script, else manual |
| 6 | MUDRA / PMMY circulars and FAQs | 15 | L4 | all | IN | script, else manual |
| 7 | Ministry of MSME, Udyam, MSME Samadhaan | 40 | L2/L4 | all | IN | script, else manual |
| 8 | Gazette notifications (MSME classification, GST, DPDP, MCA MSME Form 1) | 40 | L2 | all | IN | manual |
| 9 | CBIC GST circulars/FAQs, GST Council press releases | 30 | L2/L4 | all | IN | script, else manual |
| 10 | CBDT on s.43B(h) / Income-tax Act 2025 s.37(2)(g); Act chapters | 10 | L3/L4 | all | IN | manual |
| 11 | SIDBI publications, MSME Pulse | 20 | L4 | all | IN | script, else manual |
| 12 | TReDS: RBI directions + RXIL, M1xchange, Invoicemart | 15 | L4 | all | IN | script, else manual |
| 13 | Bank and NBFC schedules of charges, sample KFS (~20 lenders) | 40 | L4 | per lender type | IN | script, else manual |
| 14 | Lok Sabha / Rajya Sabha answers on MSME credit | 50 | L4 | all | IN | script, else manual |
| 15 | Supreme Court and High Court judgments on the MSMED Act | 25 | L2 | all | IN | manual |
| 16 | State MSME/industrial policies: Maharashtra (home) + GJ, KA, TN, UP, TS (distractors) | 20 | L4 | all | IN-MH, IN-GJ, IN-KA, IN-TN, IN-UP, IN-TS | manual |

## Public resources
| P | R-ID (canonical) | Resource | Agents | Source | Basis | Used for |
|---|---|---|---|---|---|---|
| P01 | R-RBI-02 | RBI Commercial Banks – Responsible Business Conduct Directions 2025 (KFS Annex XIII, APR) | LW, CP | https://rbi.org.in/Scripts/BS_ViewMasDirections.aspx?id=13140 | L4 | KFS layout, APR convention, citations |
| P02 | R-RBI-03 | RBI Commercial Banks – Interest Rates on Advances Directions 2025 | LW, CP | https://www.rbi.org.in/Scripts/BS_ViewMasDirections.aspx?id=13149 | L4 | Floating/benchmark rules |
| P03 | R-RBI-04 | RBI Master Direction – Lending to MSME Sector (upd. 9 Feb 2026) | WC, CP | https://rbi.org.in/Scripts/BS_ViewMasDirections.aspx?id=11060 | L4 | WC context |
| P04 | R-RBI-05 | RBI FAQs – MSME | WC, CP | https://www.rbi.org.in/scripts/FS_FAQs.aspx?Id=84 | L4 | EBLR rule for MSE loans; gold answers |
| P05 | R-RBI-01 | RBI press release: 244 consolidated Master Directions (28 Nov 2025) | CP | https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid=61705 (verified 2026-11-14) | L4 | Superseded tagging |
| P06 | R-RBI-09 | RBI Commercial Banks – KYC Directions 2025 + 29 Dec 2025 amendment | ONB, CP | https://website.rbi.org.in/en/web/rbi/regulations-non-banking/notifications?delta=20 | L4 | AML/KYC training |
| P07 | R-RBI-11 | RBI (Digital Lending) Directions 2025 | CP | https://www.rbi.org.in/Scripts/NotificationUser.aspx?Id=12848&Mode=0 (verified 2026-11-14; withdrawn 28 Nov 2025, superseded by R-RBI-10 Credit Facilities Directions, Chapter III) | L4 | Copilot |
| P08 | R-RBI-08 | RBI TReDS Directions 2026 | CP | final (RBI/DPSS/2026-27/406, 23 Jun 2026) https://www.rbi.org.in/scripts/BS_ViewMasDirections.aspx?id=13526 ; draft (superseded) https://www.rbi.org.in/scripts/bs_viewcontent.aspx?Id=4976 | L4 | Copilot |
| P09 | R-RATE-01 | RBI "Lending and Deposit Rates of SCBs" monthly releases | LW, CP | https://rbi.org.in/scripts/BS_PressReleaseDisplay.aspx?prid=63702 (Sep 2026), prid=63481, prid=63049, prid=62471 | L4 facts | Rate ranges |
| P10 | R-RBI-06 | RBI Priority Sector Lending Directions 2025 | CP | https://website.rbi.org.in/web/rbi/financial-inclusion-and-development/master-directions | L4 | Copilot |
| P11 | R-CG-01 | CGTMSE AGF structure CGS-I | LW, CP | https://cgtmse.in/Home/VS/47 | L4 facts | Fee slabs |
| P12 | R-CG-02 | CGTMSE AGF basis (y1 guaranteed, then outstanding) | LW | https://cgtmse.in/Home/VS/101 | L4 facts | Loan-cost rule |
| P13 | R-CG-03 | CGTMSE circulars | CP | https://www.cgtmse.in/Circulars | L4 | Corpus volume |
| P14 | R-CG-04 | SBI CGTMSE page | LW | https://sbi.bank.in/web/business/sme/sme-government-schemes/cgtmse | L4 | Fee timing |
| P15 | R-MSME-02 | S.O. 1364(E) MSME classification, 21 Mar 2025 | WC, CP | https://egazette.gov.in/writeReadData/2025/261838.pdf | L2 | Size bands |
| P16 | R-MSME-03 | S.O. 2119(E) 2020 (superseded) | CP | https://dcmsme.gov.in/State-Gov/Notification_%20S%20O%202119.pdf | L2 | Date-filter test |
| P17 | R-MSME-04 | Udyam reverse-graduation circular 24 Oct 2025 | CP | https://udyamregistration.gov.in/docs/Circular_reverse_24102025.pdf | L2/L4 | Copilot |
| P18 | R-MSME-01 | MSMED Act 2006 s.15–16 | WC, CP | https://www.indiacode.nic.in/show-data?actid=AC_CEN_46_77_00002_200627_1517807324919&orderno=15 (s.16: `orderno=16`) | L3 | 45-day rule |
| P19 | R-TAX-01 | Income-tax Act 2025 s.37(2)(g); 1961 s.43B | WC, CP | https://www.incometaxindia.gov.in/w/section-43b-40 ; 2025 Act (as amended by Finance Act 2026; s.37(3) excludes clause (g) from the pay-before-return relief) https://www.incometaxindia.gov.in/documents/d/guest/income_tax_act_2025_as_amended_by_fa_act_2026-pdf | L3/L4 | Payables timing |
| P20 | R-GST-01, R-GST-02 | CGST notifications 11/2017 (rate) and 12/2017 (exemption) | LW, CP | 11/2017 https://cbic-gst.gov.in/hindi/pdf/central-tax-rate/Notification11-CGST.pdf (amended, latest 15/2025-CT(R) eff 22 Sep 2025 https://egazette.gov.in/WriteReadData/2025/266220.pdf); 12/2017 https://cbic-gst.gov.in/hindi/pdf/central-tax-rate/Notification12-CGST.pdf | L2 | GST 18% on fees, none on interest — **recheck the heading 9971 rate after 15/2025 before G1** |
| P21 | R-DPDP-01 | DPDP Act 2023 + DPDP Rules 2025 (G.S.R. 846(E)) | ONB, VER, CP | Act https://www.meity.gov.in/static/uploads/2024/02/Digital-Personal-Data-Protection-Act-2023.pdf (+ S.O. 5458(E), 5 Oct 2026); Rules https://egazette.gov.in/WriteReadData/2025/267650.pdf (+ corrigendum G.S.R. 892(E)) | L3/L2 | Data-protection training, PII policy |
| P22 | R-BANK-01 | SBI advances service charges | LW | https://sbi.co.in/documents/16012/76239/ADVANCES+RELATED+SERVICE+CHARGES+W.E.F.+01.04.2019+A.pdf | L4 facts | Fee ranges |
| P23 | R-BANK-02 | SBI SME Smart Score | LW | https://sbi.co.in/portal/web/sme/sme-smart-score | L4 facts | Low-fee archetype |
| P24 | R-BANK-03 | Bandhan Bank SME charges (Jan 2026) | LW | https://bandhan.bank.in/sites/default/files/2026-01/Schedule-of-Charges-SME-and-Corporate-Loans-16012026.pdf | L4 facts | High-fee archetype |
| P25 | R-BANK-04, R-BANK-05 | Indian Bank MSME charges 2018 / 2022 | LW, CP | https://indianbank.in/wp-content/uploads/2018/11/Service-Charge-for-MSME-Products-1.pdf ; https://www.indianbank.in/wp-content/uploads/2022/04/MSME-Service-Charges.pdf | L4 facts | Rating-based archetype; superseded pair |
| P26 | R-BANK-06..16 | 11 more bank/NBFC charge schedules (BoB, PNB, Canara, Union, HDFC, ICICI, Axis, Kotak, IDFC FIRST, Bajaj Finance, Tata Capital) | LW, CP | URLs in `data/corpus/manifest.yaml` | L4 | Fee ranges (processing 0.6%–3.5%, NBFC up to 4.72% incl. tax); corpus volume |
| P27 | R-DATA-01, R-DATA-02 | data.gov.in Udyam registration catalog + district-wise resource | WC | https://www.data.gov.in/catalog/udyam-registration-msme-registration | L1 | Optional realism |
| P28 | R-LIC-01 | GODL-India licence | All | https://data.gov.in/sites/default/files/Gazette_Notification_OGDL.pdf | — | Attribution |
| P30 | M-03 | BAAI/bge-reranker-base | CP | https://huggingface.co/BAAI/bge-reranker-base | MIT | Optional reranker |
| P31 | M-01, M-02 | Course chat (≤8B) + embeddings endpoints | All | course | course terms | Model calls |
| P32 | R-AA-01 | Sahamati FIU eligibility | CP | https://sahamati.org.in/financial-information-user-fiu | L4 | Copilot (AA limits) |
| P33 | R-RBI-10 | RBI Commercial Banks – Credit Facilities Directions 2025 (RBI/DOR/2025-26/154) | LW, CP | https://www.rbi.org.in/Scripts/BS_ViewMasDirections.aspx?id=13156 | L4 | Definitions used by R-RBI-02 |
| P34 | R-RBI-12 | RBI KFS for Loans & Advances circular RBI/2024-25/18, 15 Apr 2024 (content carried into R-RBI-02 para 348 / Annex XIII; `superseded_by: R-RBI-02`) | LW, CP | https://www.rbi.org.in/Scripts/NotificationUser.aspx?Id=12663&Mode=0 | L4 | APR illustration source for S21; superseded-filter test |
| P35 | R-RATE-02 | RBI policy repo rate 5.50% (MPC 7 Oct 2026) + SBI EBLR 8.15% (15 Oct 2026) + BoB BRLLR 8.15% (8 Oct 2026) | LW | manifest docs R-RATE-02-REPO / -SBI / -BOB: https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid=63742 ; https://sbi.bank.in/web/interest-rates/external-benchmark-based-lending-rate ; https://bankofbaroda.bank.in/interest-rate-and-service-charges/retail-loans-interest-rates | L4 facts | Reference rates for floating offers (LW-08) and D6; values in `data/reference/reference_rates.yaml` |
| P36 | R-CAL-01 | RBI NI Act holiday matrix (per regional office) | LW | https://www.rbi.org.in/scripts/HolidayMatrixDisplay.aspx?regoff=Mumbai | L4 facts | Optional instalment-date to week mapping (scope #7, ADR 0011) |
| P37 | T-04 | OWASP Top 10 for LLM Applications 2025 | EVAL, VER | https://genai.owasp.org/llm-top-10/ | CC BY-SA | Red-team taxonomy, risk register |
| P38 | R-RBI-13 | RBI NBFC – Responsible Business Conduct Directions 2025 (same APR illustration) | CP | https://www.rbi.org.in/scripts/NotificationUser.aspx?Id=12942&Mode=0 | L4 | Second source for S21 transcription |
| P39 | R-SIDBI-01..05 | SIDBI working capital, project funding, machinery loan, CGTMSE, TReDS pages | CP | https://www.sidbi.in/working-capital (others in manifest) | L4 | Copilot corpus |
| P40 | R-MSME-05, R-MSME-06 | MSME Samadhaan FAQ; Udyam "Important to know" | CP | https://samadhaan.msme.gov.in/MyMsme/MSEFC/FAQ.aspx ; https://www.udyamregistration.gov.in/Important.aspx | L4 | Copilot corpus (delayed payments, Udyam) |

## Synthetic datasets (L5)
| ID | Dataset | Size | Agents | Generated from |
|---|---|---|---|---|
| S01 | HR store (employees, required trainings, records, acks) | 20 | ONB | DATA_SPEC §1 plants |
| S02 | Policies + FAQ (WC-POL v1–v3, approval matrix, delegation, data handling, negotiation conduct, training catalogue) | 60–90 | ONB, CP, SUP | Team-written, dated versions |
| S03 | MSME cases × 7 files | 15 | WC, LW, SUP | R-MSME-02, R-MSME-01, cost-share assumptions |
| S04 | Lender offers + revisions | 45+ | LW | R-RATE-01/02, R-CG-01/02, R-GST-01, R-BANK-01..05 |
| S05 | Lender simulator scripts | 1/lender | LW | fee_waiver_v1 responses |
| S06 | Synthetic KFS docs | 120–160 | LW, CP, VER | R-RBI-02 Annex XIII layout; hidden charges; injection; cross-case |
| S07 | Negotiation templates | v1 (+v2) | LW, VER | Ledger-filled slots |
| S08 | Approval config, demo users | 5 users | SUP | BRD §8.8 |
| S09 | Chat-intent examples | ~60 | SUP | 4 labels × 15 |
| S10 | Number-format fixtures | ≥50 | VER | Indian formats |
| S11 | Banned phrases + refusal policy | ~40 / 7 rules | VER, CP | BRD §14 |
| S12 | PII test fixtures (never stored) | ~30 | ONB, VER | Generated in tests |
| S13 | Report + fallback templates | 1 + 5 | VER, SUP | UI-08, VER-05 |
| S14 | Test set + independent gold (10 hand-checked) | 100 | EVAL | BRD §13 |
| S15 | Retrieval queries | 40 | CP, EVAL | Labels by doc + section |
| S16 | Red-team prompts | 20 | EVAL | Injection, PII, scope, acceptance (taxonomy T-04) |
| S17 | Prompt registry | 1 YAML/prompt | All | Versioned + hashed |
| S18 | Data-correction intent fixtures | 15 | SUP | DATA_SPEC §8.1 |
| S19 | Login ↔ HR profile bindings (eval users) | 20 | ONB, SUP, EVAL | DATA_SPEC §8.2 |
| S20 | Header-variant case files | 10 | WC | DATA_SPEC §8.3 |
| S21 | RBI KFS APR illustration known-answer fixture | 1–2 | LW, EVAL | R-RBI-02 Annex / R-RBI-12; DATA_SPEC §8.4 |
| S22 | Reference parameter tables (CGTMSE AGF slabs, GST rate, reference repo/EBLR rate) | 3 YAML | LW, EVAL gold | R-CG-01, R-GST-01, R-RATE-02; DATA_SPEC §8.5 |
| S23 | Unanswerable copilot questions (abstention) | 10 | CP, EVAL | DATA_SPEC §8.6 |
| S24 | Bad-citation plants | 12 | VER, CP, EVAL | DATA_SPEC §8.7 |

Corpus target: ~600 documents, ≥400 real (RBI ~150, CGTMSE ~100, Gazette ~80, Acts ~5, bank schedules ~30, data.gov.in ~20, US ~10) + synthetic policies and KFS.
