# CredAssure web app — design plan (U0)

Status: draft for review · 2026-11-16 · Implements DESIGN_BRIEF.md process steps 1–2 · Base: `apps/web` = finbridge (ADR 0022)

**Direction (user decision, 2026-11-16): follow finbridge closely.** Its palette, type, shell, cards and effects stay.
This plan adds only what the brief requires: provenance on every number, a dark theme from the same tokens, colour-independent
gate states, approval wording and no silent rounding. Section 9 lists the brief conflicts that remain and why.

## 1. Stack as built

| Prompt says | Built (why) |
|---|---|
| Vite + React Router | Next.js 14 static export, app router (ADR 0022) |
| CSS Modules + `tokens.css` | Tailwind reading `src/styles/tokens.js`, emitted as `--fb-*` CSS variables (finbridge; one token source) |
| pnpm | npm workspaces (`npm run dev -w apps/web`); root `package.json` lists `apps/web`, `packages/api-client` |
| Radix, TanStack Query, react-hook-form + zod, Vitest + RTL + MSW, Playwright + axe | Added in U1 (none installed yet) |
| SVG charting library | recharts (already in finbridge) |

Already present and kept: lucide icons, framer-motion, `clsx` + `tailwind-merge`, generated `@credassure/api-client`, the
`services/*` mapping layer (gateway payload → view type, no maths).

## 2. Colour

Six named colours, all from `tokens.js`. Each has one job.

| Name | Hex | Token | Job |
|---|---|---|---|
| Midnight | `#0E1628` | `ink-900` | Sidebar, primary buttons, headings |
| Emerald | `#059669` | `brand-600` | Provenance mark, GO, validated figures (text uses `brand-700` `#047857`) |
| Champagne | `#DDB04F` | `gold-400` | Buffer line, held/attention accents on dark surfaces (text uses `gold-700` `#7A5A12`) |
| Ivory | `#F6F5F0` | `canvas` | Page background |
| Hairline | `#E7E4DB` | `line` | Card borders and dividers (decorative only) |
| Rose | `#BE123C` | `danger` | NO-GO, unaffordable, shortfall, errors |

### Dark theme (same token names, new values)
Set under `:root[data-theme="dark"]` and under `@media (prefers-color-scheme: dark)` guarded by `:root:not([data-theme="light"])`.
The theme toggle sits in the sidebar footer. Tailwind classes read variables, so components keep their class names.

| Token | Light | Dark |
|---|---|---|
| `canvas` | `#F6F5F0` | `#070C18` (ink-950) |
| `card` | `#FFFFFF` | `#0E1628` (ink-900) |
| text | `#172036` (ink-800) | `#E8ECF3` (ink-100) |
| muted text | `#525E75` (ink-500) | `#A2ADC2` (ink-300) |
| emerald text / mark | `#047857` / `#059669` | `#34D399` (brand-400) |
| champagne text | `#7A5A12` | `#EBCB7A` (gold-300) |
| rose | `#BE123C` | `#FB7185` |
| control border | `#647088` (ink-400) | `#647088` (ink-400) |

### Contrast checks (WCAG 2.2 AA, computed 2026-11-16)
| Pair | Ratio | Result |
|---|---|---|
| ink-800 on ivory | 14.84 | pass |
| ink-500 on white / ivory | 6.53 / 5.98 | pass |
| emerald-600 text on white | **3.77** | **fail → emerald text uses brand-700 (5.48 on white, 5.02 on ivory)** |
| emerald-600 as non-text mark on white | 3.77 | pass (≥3:1) |
| gold-700 on white | 6.37 | pass |
| rose on white | 6.29 | pass |
| ink-300 nav text on midnight | 7.98 | pass |
| ink-300 / slate-200 input border on white | **2.26** | **fail (1.4.11) → control borders ink-400 (4.98)** |
| dark: ink-100 on canvas | 16.49 | pass |
| dark: ink-300 on card | 7.98 | pass |
| dark: emerald-400 / gold-300 / rose-400 on card | 9.38 / 11.47 / 6.70 | pass |
| dark: ink-500 border on card | **2.76** | **fail → ink-400** |

## 3. Type

| Role | Face | Use |
|---|---|---|
| Display | Sora 600, tracking −0.015em | h1–h3, the hero figure on a screen |
| Text and UI | Inter 400/500/600 | Everything else |
| Figures | Inter with `tabular-nums` (`.num`) | Every amount, rate, date and week, in tables and in text |

Scale (px): 12 caption · 14 body and table · 16 lead · 20 h3 · 24 h2 · 36 hero figure. Line height 1.5 for body, 1.2 for display.
No monospace except trace and ledger IDs inside the provenance drawer.

## 4. The bold element — provenance on every number

Every amount, rate, date and week on screen renders through one component, `<Figure>`. It never formats or computes. It shows the
API's `display` string and keeps `paise` only as the lookup key.

```
  Validated need
  ₹1,42,00,000 ◈            ← dotted emerald underline (2 px, 3:1 non-text) + "◈" source glyph
  ≈ ₹1.42 crore             ← lakh/crore reading, only *beside* the exact amount, labelled "≈"
```

- **Affordance:** the figure is a `<button>` with an accessible name like "₹1,42,00,000, show source". Focus ring 2 px emerald,
  offset 2 px. Hover shows the full dotted underline; at rest a lighter one, so tables stay readable.
- **Drawer:** Radix Dialog. It opens from the right at 420 px, and as a bottom sheet (90 vh) at ≤ 640 px. Focus returns to the figure on close.
- **Lineage chain (top to bottom):**
  1. the value, ledger key (`wc.recommended_amount`) and version (`v3`), with "superseded by v4" in rose when stale;
  2. how it was produced: `produced_by` (`engines.cashflow@1`) and the formula line from the engine (e.g. peak + buffer − undrawn − mitigations);
  3. inputs: each case file kind with its sha12 and upload time, and each other fact it used (each one clickable, so a figure's sources can be followed);
  4. sources: KFS passage or regulation chunk with title and section;
  5. audit event (seq, actor, time) and trace ID (copy button).
- **API (built, scope #33):** `GET /v1/cases/{id}/facts/{key}/lineage[?version=n]` → `Lineage` in openapi.json:
  `{case_id, key, version, latest_version, superseded_by|null, value:{text, paise|null, display}, unit, created_at, source_type,
  source_ref, engine:{name, version|null}, input_hash, files:[{kind, name, sha256, uploaded_at}],
  inputs:[{kind: fact|hr_record|ref, ref, fact_key|null}], passages:[{doc_id, title|null, section|null, chunk_id|null}],
  producer:{agent|null, stage|null, trace_id|null}, audit:{seq, actor, ts}|null}`. The UI takes sha12 from `sha256[:12]` for display only.
  Ledger limits the drawer must handle:
  - `files[].name` is the upload label the agent cited (`order`, `offer:OF-01-A.v1`), not the original filename (not stored).
  - No fact cites chunk ids yet; reference-rate facts cite a corpus doc id, so `section` and `chunk_id` are null there.
  - `producer` is all null for facts written before #33 or outside a stage; show "not recorded", never blank.
  - An identical re-run adds no version, so `producer.trace_id` is the first run that wrote this value, not the latest run.
  - There is no engine formula line; step 2 shows `engine` only (a formula would be business logic in the UI).
- **Motion:** the drawer slides in over 180 ms ease-out. With reduced motion it appears without the slide. This and the decision
  confirmation are the only motion in app screens.

## 5. Gate states (never colour alone)

The finbridge `GateBadge` is kept: icon shape plus text plus tone. ERROR is added.

| State | Shape | Text | Tone |
|---|---|---|---|
| GO | filled circle-check | GO | emerald |
| NO_GO | circle-x | NO-GO | rose |
| NEEDS_INPUT | circle-question | NEEDS INPUT | champagne |
| ERROR | triangle-alert | ERROR | rose, solid fill |
| HELD | circle-pause | HELD | ink |
| RUNNING | spinner (static ring under reduced motion) | IN PROGRESS | emerald outline |
| PENDING | clock | PENDING | ink outline |

The stage tracker repeats the state as text under each step, so it survives greyscale and screen readers.

## 6. Layout concept

The finbridge shell stays. A midnight sidebar on desktop (≥ 1024 px) becomes a top bar with a menu sheet below it. The content
column is at most 1200 px, on ivory. Each case has a header band and pill tabs (Workflow · Readiness · Documents · Funding gap ·
Lender offers · Review & approval · Audit).

### Case workspace — desktop
```
┌──────────┬──────────────────────────────────────────────────────────────────────┐
│ ◆ Cred-  │ ← Cases                                                              │
│  Assure  │ ┌──────────────────────────────────────────────────────────────────┐ │
│          │ │ CA-2026-0001                                       Awaiting input│ │
│ Dashboard│ │ Shree Electronics Pvt Ltd · Due 12 Jan 2027                      │ │
│ Cases    │ │ Order ₹3,20,00,000◈  Requested ₹2,00,00,000◈  Need —   Next: …   │ │
│ New case │ │ [Workflow][Readiness][Documents][Funding gap][Offers][Review][Audit]│
│ Approvals│ └──────────────────────────────────────────────────────────────────┘ │
│ Audit    │ Stage tracker                                                        │
│          │  (✓)───────(?)───────( )───────( )───────( )                         │
│          │  Readiness  Funding   Lender    Verifi-   Routing                    │
│          │  GO         NEEDS     PENDING   PENDING   PENDING                    │
│          │             INPUT                                                    │
│          │ ┌─ One question ─────────────────────────────────────────────────┐  │
│          │ │ ? The opening position has no minimum cash buffer.             │  │
│          │ │   What buffer should the forecast keep?                        │  │
│          │ │   Fix: upload opening_position.json with min_cash_buffer.      │  │
│          │ │   [Upload corrected file]   [Resume funding stage]             │  │
│          │ └────────────────────────────────────────────────────────────────┘  │
│ ◐ Theme  │ Live progress (SSE): "Funding stage · validating files"              │
│ Acting   │                                                                      │
│ role ▾   │                                                     [? Help: stages] │
└──────────┴──────────────────────────────────────────────────────────────────────┘
```

### Case workspace — 360 px
```
┌────────────────────────────┐
│ ☰  CredAssure          ◐   │
├────────────────────────────┤
│ ← Cases                    │
│ CA-2026-0001               │
│ Shree Electronics Pvt Ltd  │
│ (?) NEEDS INPUT · Funding  │
│ Requested ₹2,00,00,000 ◈   │
│ [Workflow ▸ scrollable tabs]│
├────────────────────────────┤
│ (✓) Readiness       GO     │
│ (?) Funding    NEEDS INPUT │
│ ( ) Lender         PENDING │
│ ( ) Verification   PENDING │
│ ( ) Routing        PENDING │
├────────────────────────────┤
│ ? One question             │
│ The opening position has   │
│ no minimum cash buffer…    │
│ [Upload corrected file]    │
│ [Resume funding stage]     │
└────────────────────────────┘
```
The tracker becomes a vertical list at 360 px. Every touch target is at least 44 px (finbridge rule kept).

### Approval screen — desktop
```
┌──────────┬──────────────────────────────────────────────────────────────────────┐
│ sidebar  │ Approval · CA-2026-0001 · routed to Director, Finance                │
│          │ ┌─ Approval is internal, not loan acceptance ─────────────────────┐ │
│          │ │ Approving sends the proposal onward. The MSME chooses its lender │ │
│          │ │ outside CredAssure; nothing here accepts or signs an offer.      │ │
│          │ └─────────────────────────────────────────────────────────────────┘ │
│          │ Validated need      ₹1,42,00,000 ◈  (below ₹1,50,00,000 ◈ → Director)│
│          │ Requested           ₹2,00,00,000 ◈                                    │
│          │ Top-ranked offer    Lender B · APR 12.84% ◈ · fits cash flow (✓)      │
│          │ ⚠ Negotiation in progress — revised offer not re-audited             │
│          │ Verification        (✓) GO · 0 critical findings                     │
│          │ Evidence  [Funding need] [Offers] [Report] [Audit trail]             │
│          │ ┌─ Decision ──────────────────────────────────────────────────────┐ │
│          │ │ (•) Approve proposal  ( ) Reject  ( ) Return to stage [Funding ▾]│ │
│          │ │ Comment (required for reject/return) [_______________________]  │ │
│          │ │                                         [Approve proposal]      │ │
│          │ └─────────────────────────────────────────────────────────────────┘ │
└──────────┴──────────────────────────────────────────────────────────────────────┘
  Step-up confirm (Radix AlertDialog):
  ┌───────────────────────────────────────────────┐
  │ Approve proposal CA-2026-0001?                │
  │ Validated need ₹1,42,00,000 ◈                 │
  │ This is internal approval, not loan acceptance.│
  │ Type the case ID to confirm: [____________]   │
  │            [Cancel]  [Approve proposal]       │
  └───────────────────────────────────────────────┘
  → toast "Proposal approved"
```

### Approval screen — 360 px
```
┌────────────────────────────┐
│ ☰  CredAssure          ◐   │
├────────────────────────────┤
│ Approval · CA-2026-0001    │
│ ┌ Approval is internal, ─┐ │
│ │ not loan acceptance    │ │
│ └────────────────────────┘ │
│ Validated need             │
│ ₹1,42,00,000 ◈             │
│ ≈ ₹1.42 crore              │
│ Top offer: Lender B        │
│ APR 12.84% ◈  (✓) fits     │
│ ⚠ Revised offer not        │
│   re-audited               │
│ [Evidence ▸]               │
├────────────────────────────┤
│ sticky bottom bar:         │
│ [Return] [Reject] [Approve]│
└────────────────────────────┘
```
Approvers often use a phone. The decision bar stays fixed at the bottom, and each button opens the same step-up confirm as a bottom sheet.

## 7. Principles for this brief

1. **A figure is evidence.** No number appears without the ◈ mark and a lineage. If the API has no lineage for a figure, the mark
   reads "source not available yet". The figure is never shown unmarked.
2. **One question at a time.** A paused case shows exactly one question, the fix in plain words, and one primary action. A missing
   field arrives as the stage's question, not as an upload error.
3. **Say what a decision is not.** Every place a decision is taken shows "Approval is internal, not loan acceptance". Unaffordable,
   non-comparable and not-re-audited states are stated in words next to the figure they affect.
4. **Quiet around the figures, loud on provenance.** finbridge's effects stay on the landing and login pages. On case screens the
   only new emphasis is the provenance mark and drawer.

## 8. Money, errors, help

- **Money:** `src/lib/money.ts` takes `{paise, display}` and returns the `display` string. The lakh/crore reading is derived from the
  display string, labelled "≈", and shown only beside the exact amount. The finbridge `inr` and `inrShort` (float, `toFixed(2)`)
  are retired in U1.
- **Errors:** the mapper reads the **runtime** RFC 9457 body (`type`, `title`, `detail`, `errors[{field,row,reason}]`), not the
  generated types (openapi still declares free-form responses, PROGRESS E10 SHOULD-2). Field errors go to fields. Anything else
  becomes a banner: what happened, and how to fix it. Raw JSON is never shown.
- **Help:** `docs/help/*.md` is bundled at build time. Each screen header has a "? Help" link to its guide section.

## 9. Self-review against the brief (step 2)

The plan was compared with the brief's list of generic defaults. finbridge already contains several of them. By user decision
(2026-11-16, "follow finbridge closely") they are **accepted, not changed**:

| Brief default found | Where in finbridge | Decision |
|---|---|---|
| Warm ivory background | `canvas #F6F5F0` | Accepted (finbridge palette). The accent is emerald, not terracotta, and the display face is sans, not serif. |
| Identical rounded cards, soft grey shadow, gradient washes | `Card` (24 px radius, layered shadow), `.glass`, `.mesh-midnight`, case header gradient | Accepted |
| One accented / gradient word in a headline | `.text-gold-grad`, `.fb-shimmer` on the login wordmark | Accepted on landing and login only; not used on case screens |
| All-caps eyebrow labels | sidebar "Acting role", table headers | Accepted |
| Middle-dot meta strings | case header ("Order ref · value") | Accepted |
| Decorative motion | `TiltCard` on stats, 3D hero, nav pill spring | Accepted. Reduced motion already disables it (globals.css). |

**Open for review:** the imported wordmark, login and landing still say "FinBridge AI". BRD v3.1 renamed the product to
CredAssure, and the wireframes above use CredAssure. U1 changes the wordmark text only, unless told to keep FinBridge AI.

**Changed after review**, because the brief requires it rather than for taste:

| Change | Reason |
|---|---|
| Emerald text moves to `brand-700`; control borders move to `ink-400` in both themes | AA contrast failures found in §2 |
| Dark theme added from the same token names | Brief quality floor (step 3) |
| `ERROR` gate state added; tracker states repeated as text | Colour-independent gate encoding |
| `inrShort` / `toFixed` removed from figures; "≈" shown beside the exact amount | "Never round silently" |
| Funding view: monthly periods become the API's 26-week cash table; the drivers pie is removed | WC-03, and the brief makes the 26-week chart the centre; a pie of drivers would be computed in the browser (BR-05) |
| "Difference vs request" % in Funding.tsx is replaced by the API's bridge lines | The browser was computing it (BR-05) |
| Approval screen gets the internal-approval statement and a step-up confirm | Brief constraint, APR-06 |

## 10. Screen → route map

| Brief screen | Route | Step |
|---|---|---|
| Sign in | `/login` (existing) | U1 |
| Cases | `/cases`, `/dashboard` (existing) | U2 |
| Create case | `/cases/new` (existing) | U2 |
| Case workspace + stage tracker + question | `/case?id=&tab=workflow` (existing) | U2 |
| Upload (7 slots) | `/case?tab=documents` (existing) | U2 |
| Funding need | `/case?tab=funding` (rebuilt for 26 weeks) | U3 |
| Offers | `/case?tab=lenders` (existing) | U3 |
| Ask CredAssure | `/case?tab=copilot` (new) | U4 |
| Approval | `/approvals`, `/case?tab=review` (existing) | U2 (Director), U4 |
| Report | `/case?tab=report` (new) | U4 |
| Audit | `/audit`, `/case?tab=audit` (existing) | U5 |
| Evaluation | `/evaluation` (new) | U5 |
| Help | `/help` (new) | U5 |
| Provenance drawer | global component | U1 |
| Component gallery | `/__gallery` (dev only) | U1 |

## 11. API dependencies (ask before changing the API)

| Need | Status |
|---|---|
| `GET /v1/cases/{id}/facts/{key}/lineage` | Available (#33, 2026-11-16); typed in `@credassure/api-client`. Shape in §4. |
| Problem+json declared in openapi | Runtime only; the mapper reads the runtime body |
| Typed responses | Free-form objects in openapi; `services/*` cast. Typing them is a gateway task (ADR 0022). |
| Cash table, offers, readiness | Closed since ADR 0022 was written (9a, 9b, 9c): `/working-capital/cases/{id}/cash-table`, `/lendwise/cases/{id}/offers`, `/onboarding/cases/{id}/result` |
| Run progress | `/v1/jobs/{id}/events` (SSE) |
