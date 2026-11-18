"""Product help as a cited source (ADR 0035): sections, FAQ split, BM25, Critic resolution."""

from pathlib import Path

from credassure.retrieval.help import HelpIndex, parse

ROOT = Path(__file__).resolve().parents[3]
PAGE = """# Preparer

Intro text.

## Upload
Upload the seven case files on **Documents**.

## Run
Press **Run** on Workflow.

## Run
A second section with the same heading.
"""
FAQ = """# FAQ

**Why is the cheapest lender not ranked first?**
Offers are ranked by APR.

**Does approval accept the loan?**
No. Approval is internal.
"""


def test_ADR0035_sections_get_stable_unique_help_ids() -> None:
    ids = [p.chunk_id for p in parse("preparer", PAGE)]
    assert ids == [
        "HELP-preparer#overview",
        "HELP-preparer#upload",
        "HELP-preparer#run",
        "HELP-preparer#run-2",
    ]
    p = parse("preparer", PAGE)[1].as_passage()
    assert p["collection"] == "help" and p["href"] == "/help/#preparer"
    assert p["title"] == "Preparer" and p["section_path"] == "Upload"


def test_ADR0035_a_faq_page_splits_on_its_bold_questions() -> None:
    heads = [p.section_path for p in parse("faq", FAQ)]
    assert heads == ["Why is the cheapest lender not ranked first?", "Does approval accept the loan?"]


def test_ADR0035_search_ranks_the_matching_section_first_and_resolve_is_closed() -> None:
    index = HelpIndex(parse("preparer", PAGE) + parse("faq", FAQ))
    assert index.search("does approval accept the loan")[0]["chunk_id"] == (
        "HELP-faq#does-approval-accept-the-loan"
    )
    assert index.search("zzz unknown words") == []
    found = index.resolve(["HELP-preparer#upload", "HELP-preparer#nope"])
    assert found["HELP-preparer#upload"][0] == "ok"
    assert found["HELP-preparer#nope"] == ("missing", "")


def test_ADR0035_missing_help_directory_is_an_empty_index(tmp_path: Path) -> None:
    assert len(HelpIndex.load(tmp_path / "absent")) == 0


def test_ADR0035_shipped_help_answers_the_safety_and_product_questions() -> None:
    """The help centre the gateway indexes covers what ADR 0035 promises the copilot can answer."""
    index = HelpIndex.load(ROOT / "docs/help")
    cases = {
        "How does CredAssure handle personal data?": "HELP-ai-safety#personal-data",
        "What does the AI decide and what does code decide?": "HELP-ai-safety#",
        "What guardrails protect requests?": "HELP-ai-safety#guardrails",
        "What can Ask CredAssure help with?": "HELP-ask-credassure#",
        "Does approval accept the loan?": "HELP-faq#does-approval-accept-the-loan",
        "How do I write a case in Excel?": "HELP-case-authoring#",
    }
    for q, want in cases.items():
        top = [p["chunk_id"] for p in index.search(q, 3)]
        assert any(t.startswith(want) for t in top), (q, top)
