# CredAssure — Data resources for all agents (capstone, open data only)

Every input is public (legal basis L1–L4, L6) or synthetic and team-owned (L5). Public files are downloaded via
`data/corpus/manifest.yaml`, hashed and frozen at G1. Nothing needs a login, payment, partnership or personal data.
URLs marked *verify* must be opened and confirmed before they enter the manifest.

Agents: SUP Supervisor + routing · ONB Onboarding · WC Working Capital · LW LendWise · VER Critic · CP Copilot · EVAL evaluation

## Legal basis codes
| Code | Basis | What the team may do |
|---|---|---|
| L1 | Government Open Data License – India (data.gov.in) | Use, adapt, redistribute with attribution |
| L2 | Copyright Act 1957 s.52(1)(q)(i): Official Gazette matter (except Acts) | Store, index, quote, redistribute |
| L3 | s.52(1)(q)(ii): Acts reproducible with commentary | Store/index locally; quote short passages with citation; never commit raw text |
| L4 | Public documents; research fair dealing s.52(1)(a); facts not copyrightable | Local research use; extract numeric facts; never redistribute files |
| L5 | Team-owned synthetic data, eval sets, code | Release: data CC BY 4.0, code MIT |
| L6 | US federal government works (public domain) | Any use |

## Public resources
| ID | Resource | Agents | Source | Basis | Used for |
|---|---|---|---|---|---|
| P01 | RBI Commercial Banks – Responsible Business Conduct Directions 2025 (KFS Annex XIII, APR) | LW, CP | https://rbi.org.in/Scripts/BS_ViewMasDirections.aspx?id=13140 | L4 | KFS layout, APR convention, citations |
| P02 | RBI Commercial Banks – Interest Rates on Advances Directions 2025 | LW, CP | https://www.rbi.org.in/Scripts/BS_ViewMasDirections.aspx?id=13149 | L4 | Floating/benchmark rules |
| P03 | RBI Master Direction – Lending to MSME Sector (upd. 9 Feb 2026) | WC, CP | https://rbi.org.in/Scripts/BS_ViewMasDirections.aspx?id=11060 | L4 | WC context |
| P04 | RBI FAQs – MSME | WC, CP | https://www.rbi.org.in/scripts/FS_FAQs.aspx?Id=84 | L4 | EBLR rule for MSE loans; gold answers |
| P05 | RBI press release: 244 consolidated Master Directions (28 Nov 2025) | CP | https://website.rbi.org.in/documents/d/rbi/pr1588rbiconsolidatedmasterdirections-1- | L4 | Superseded tagging |
| P06 | RBI Commercial Banks – KYC Directions 2025 + 29 Dec 2025 amendment | ONB, CP | https://website.rbi.org.in/en/web/rbi/regulations-non-banking/notifications?delta=20 | L4 | AML/KYC training |
| P07 | RBI (Digital Lending) Directions 2025 | CP | https://website.rbi.org.in/documents/d/rbi/directionsondigitallending | L4 | Copilot |
| P08 | RBI TReDS Directions 2026 | CP | draft https://www.rbi.org.in/scripts/bs_viewcontent.aspx?Id=4976 ; final *verify* | L4 | Copilot |
| P09 | RBI "Lending and Deposit Rates of SCBs" monthly releases | LW, CP | https://rbi.org.in/scripts/BS_PressReleaseDisplay.aspx?prid=63702 (Sep 2026), prid=63481, prid=63049, prid=62471 | L4 facts | Rate ranges |
| P10 | RBI Priority Sector Lending Directions 2025 | CP | https://website.rbi.org.in/web/rbi/financial-inclusion-and-development/master-directions | L4 | Copilot |
| P11 | CGTMSE AGF structure CGS-I | LW, CP | https://cgtmse.in/Home/VS/47 | L4 facts | Fee slabs |
| P12 | CGTMSE AGF basis (y1 guaranteed, then outstanding) | LW | https://cgtmse.in/Home/VS/101 | L4 facts | Loan-cost rule |
| P13 | CGTMSE circulars | CP | https://www.cgtmse.in/Circulars | L4 | Corpus volume |
| P14 | SBI CGTMSE page | LW | https://sbi.bank.in/web/business/sme/sme-government-schemes/cgtmse | L4 | Fee timing |
| P15 | S.O. 1364(E) MSME classification, 21 Mar 2025 | WC, CP | https://egazette.gov.in/writeReadData/2025/261838.pdf | L2 | Size bands |
| P16 | S.O. 2119(E) 2020 (superseded) | CP | https://dcmsme.gov.in/State-Gov/Notification_%20S%20O%202119.pdf | L2 | Date-filter test |
| P17 | Udyam reverse-graduation circular 24 Oct 2025 | CP | https://udyamregistration.gov.in/docs/Circular_reverse_24102025.pdf | L2/L4 | Copilot |
| P18 | MSMED Act 2006 s.15–16 | WC, CP | indiacode.nic.in *verify* | L3 | 45-day rule |
| P19 | Income-tax Act 2025 s.37(2)(g); 1961 s.43B | WC, CP | https://www.incometaxindia.gov.in/w/section-43b-40 ; 2025 Act *verify* | L3/L4 | Payables timing |
| P20 | CGST notifications 11/2017 (rate) and 12/2017 (exemption) | LW, CP | cbic-gst.gov.in *verify* | L2 | GST 18% on fees, none on interest |
| P21 | DPDP Act 2023 + DPDP Rules 2025 (G.S.R. 846(E)) | ONB, VER, CP | meity.gov.in / egazette.gov.in *verify* | L3/L2 | Data-protection training, PII policy |
| P22 | SBI advances service charges | LW | https://sbi.co.in/documents/16012/76239/ADVANCES+RELATED+SERVICE+CHARGES+W.E.F.+01.04.2019+A.pdf | L4 facts | Fee ranges |
| P23 | SBI SME Smart Score | LW | https://sbi.co.in/portal/web/sme/sme-smart-score | L4 facts | Low-fee archetype |
| P24 | Bandhan Bank SME charges (Jan 2026) | LW | https://bandhan.bank.in/sites/default/files/2026-01/Schedule-of-Charges-SME-and-Corporate-Loans-16012026.pdf | L4 facts | High-fee archetype |
| P25 | Indian Bank MSME charges 2018 / 2022 | LW, CP | https://indianbank.in/wp-content/uploads/2018/11/Service-Charge-for-MSME-Products-1.pdf ; https://www.indianbank.in/wp-content/uploads/2022/04/MSME-Service-Charges.pdf | L4 facts | Rating-based archetype; superseded pair |
| P26 | 8–12 more bank charge schedules | CP | each bank *verify* | L4 | Corpus volume |
| P27 | data.gov.in MSME/Udyam datasets | WC | data.gov.in *verify* | L1 | Optional realism |
| P28 | GODL-India licence | All | https://data.gov.in/sites/default/files/Gazette_Notification_OGDL.pdf | — | Attribution |
| P29 | US federal small-business lending docs (~10) | CP | sba.gov *verify* | L6 | Non-Indian distractors |
| P30 | BAAI/bge-reranker-base | CP | https://huggingface.co/BAAI/bge-reranker-base | MIT | Optional reranker |
| P31 | Course chat (≤8B) + embeddings endpoints | All | course | course terms | Model calls |
| P32 | Sahamati FIU eligibility | CP | https://sahamati.org.in/financial-information-user-fiu | L4 | Copilot (AA limits) |

## Synthetic datasets (L5)
| ID | Dataset | Size | Agents | Generated from |
|---|---|---|---|---|
| S01 | HR store (employees, required trainings, records, acks) | 20 | ONB | DATA_SPEC §1 plants |
| S02 | Policies + FAQ (WC-POL v1–v3, approval matrix, delegation, data handling, negotiation conduct, training catalogue) | 60–90 | ONB, CP, SUP | Team-written, dated versions |
| S03 | MSME cases × 7 files | 15 | WC, LW, SUP | P15, P18, cost-share assumptions |
| S04 | Lender offers + revisions | 45+ | LW | P09, P11–P12, P20, P22–P25 |
| S05 | Lender simulator scripts | 1/lender | LW | fee_waiver_v1 responses |
| S06 | Synthetic KFS docs | 120–160 | LW, CP, VER | P01 Annex XIII layout; hidden charges; injection; cross-case |
| S07 | Negotiation templates | v1 (+v2) | LW, VER | Ledger-filled slots |
| S08 | Approval config, demo users | 5 users | SUP | BRD §8.8 |
| S09 | Chat-intent examples | ~60 | SUP | 4 labels × 15 |
| S10 | Number-format fixtures | ≥50 | VER | Indian formats |
| S11 | Banned phrases + refusal policy | ~40 / 7 rules | VER, CP | BRD §14 |
| S12 | PII test fixtures (never stored) | ~30 | ONB, VER | Generated in tests |
| S13 | Report + fallback templates | 1 + 5 | VER, SUP | UI-08, VER-05 |
| S14 | Test set + independent gold (10 hand-checked) | 100 | EVAL | BRD §13 |
| S15 | Retrieval queries | 40 | CP, EVAL | Labels by doc + section |
| S16 | Red-team prompts | 20 | EVAL | Injection, PII, scope, acceptance |
| S17 | Prompt registry | 1 YAML/prompt | All | Versioned + hashed |

Corpus target: ~600 documents, ≥400 real (RBI ~150, CGTMSE ~100, Gazette ~80, Acts ~5, bank schedules ~30, data.gov.in ~20, US ~10) + synthetic policies and KFS.
