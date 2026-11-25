# Your own commits before submission (27 Nov 2026)

Individual contribution is assessed, and most of this repository was committed from one machine. Each member makes at
least **two small, real commits from their own GitHub account** before 27 Nov, 18:00 IST:

1. **Your statement** in `CONTRIBUTIONS.md`: what you built, designed, reviewed or decided, in your own words.
2. **One review task** from the table below, signed with your name.

Everything here works in the GitHub web editor. You don't need to install anything. Only the K5 freeze needs the
project set up on your machine.

## Who does what

| Member | GitHub | 1. Statement | 2. Review task (pick at least one) |
|---|---|---|---|
| Tejas | `tejast12` | `CONTRIBUTIONS.md` → "Tejas" | **K5 freeze** of the safety suite (steps in `evaluation/safety_v2/README.md`), **or** H21 APR transcription column A (`evaluation/gold/fixtures/apr_transcription_sheet.md`), **or** H22 hand-check rows 1–4 (`evaluation/gold/hand_check.md`) |
| Suresh | `SureN8088` | `CONTRIBUTIONS.md` → "Suresh" | H21 APR transcription column B, **or** H20 the two help pages (`docs/help/ask-credassure.md`, `docs/help/ai-safety.md`), **or** H9 protected-attribute word list |
| Abhishek | `pareekabhishek` | `CONTRIBUTIONS.md` → "Abhishek" | H24 code review of the safety_v2 critical rule (`evaluation/src/credassure/evaluation/safety_v2.py`), **or** H11 OWASP/ASI mapping (`docs/security/owasp-asi-mapping.md`), **or** H2 unanswerable queries DN01–DN08 |
| Adesh | `adeshsurroach` | `CONTRIBUTIONS.md` → "Adesh" | **K9 clean-machine run**: follow `README.md` §2–§7 ("Sign in and test") on your laptop and record what worked and what failed in a progress entry, **or** H26 the 18 v2 lender replies (`data/frozen/v2/lender_scripts/L01–L09.yaml`) |
| Mousita | `mousitaD` | `CONTRIBUTIONS.md` → "Mousita Dhar" | Optional: H13 employee-name masking (ADR 0030 §2) |

Reviewer rule (ADR 0031): don't review anything for a module you own. The table already follows it.

## Code you wrote that someone else committed

If you wrote or designed code that Pritish committed from his machine, list it under **"Written by me, committed by
Pritish"** in your statement. Give the file paths or the commit hashes (`git log --oneline -- <path>` shows them, or
use the file's History view on GitHub). Pritish confirms each line in his review of your PR. Only list what you
actually wrote: the history is not changed, and every line has to hold up if an examiner asks.

## Steps in the GitHub web editor

1. Open the file on GitHub (`main` branch) and press the pencil icon (**Edit this file**).
2. Make your change:
   - **Statement:** in your own section, replace the italic line under "Statement (written and signed by …)" with your
     text. End it with `Signed: <your name>, <date>`.
   - **Review task in `docs/plan/human-review.md`:** in your row, set *Status* to `Accepted`, `Changed` or `Rejected`, and
     write `<your name>, <date>: <one line on what you checked>` in *Signed off*.
   - **Forms** (APR transcription, hand check): fill your column only, without looking at the other column.
3. Press **Commit changes…** and choose **Create a new branch for this commit and start a pull request**. Name the branch
   `feature/docs-p16-<yourname>`. Make sure the pull request targets `main`.
4. Open the pull request. Pritish reviews and merges it. Your name stays on the commit.

If an automated check fails only on `PROGRESS.md` or the progress check, leave it: Pritish regenerates the file when he
merges.
