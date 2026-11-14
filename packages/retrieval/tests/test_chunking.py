"""KR-01: three chunking strategies, each chunk carrying the section it sits in."""

from collections.abc import Callable

import pytest

from credassure.retrieval.chunking import by_section, fixed, sections, semantic
from credassure.retrieval.sources import strip_boilerplate

Embed = Callable[[list[str]], list[list[float]]]


def _words(n: int, word: str = "w") -> str:
    return " ".join(f"{word}{i}" for i in range(n))


DOC = f"""# Chapter I General
{_words(30)}
1. Fees and charges
{_words(40, "fee")}
1.1 Processing fee
{_words(20, "proc")}
ANNEX II
{_words(10, "annex")}
"""


def test_KR01_heading_detector_builds_section_paths() -> None:
    paths = [path for path, _ in sections(DOC)]
    assert paths == [
        "Chapter I General",
        "Chapter I General > 1. Fees and charges",
        "Chapter I General > 1. Fees and charges > 1.1 Processing fee",
        "ANNEX II",
    ]


def test_KR01_text_before_any_heading_has_no_section() -> None:
    assert sections("plain text only\nmore text")[0][0] is None


def test_KR01_fixed512_size_overlap_and_coverage() -> None:
    text = _words(1200)
    pieces = fixed(text, size=512, overlap=64)
    words = [p.text.split() for p in pieces]
    assert all(len(w) <= 512 for w in words)
    assert words[0][-64:] == words[1][:64]  # 64-word overlap
    assert words[-1][-1] == "w1199"  # nothing dropped at the end


def test_KR01_fixed_chunk_takes_the_section_it_starts_in() -> None:
    pieces = fixed(DOC, size=40, overlap=0)
    assert pieces[0].section_path == "Chapter I General"
    assert any(p.section_path and p.section_path.endswith("1.1 Processing fee") for p in pieces)


def test_KR01_section_chunks_follow_headings_and_split_long_blocks() -> None:
    pieces = by_section(DOC, size=512)
    assert [p.section_path for p in pieces][-1] == "ANNEX II"
    assert all(p.text.split()[0] != "#" for p in pieces)
    long = by_section("## Big\n" + _words(1100), size=512)
    assert len(long) == 3 and {p.section_path for p in long} == {"Big"}


def test_KR01_semantic_splits_at_a_topic_change(embed: Embed) -> None:
    topic_a = " ".join(["guarantee fee slab cgtmse annual"] * 40)
    topic_b = " ".join(["delayed payment supplier interest days"] * 40)
    pieces = semantic(f"{topic_a}\n{topic_b}", embed, unit=20, size=512)
    assert len(pieces) >= 2
    assert "guarantee" in pieces[0].text and "delayed" not in pieces[0].text
    assert "delayed" in pieces[-1].text and "guarantee" not in pieces[-1].text


def test_KR01_chunkers_are_deterministic(embed: Embed) -> None:
    assert fixed(DOC) == fixed(DOC)
    assert by_section(DOC) == by_section(DOC)
    assert semantic(DOC, embed) == semantic(DOC, embed)


def test_KR01_empty_text_gives_no_chunks(embed: Embed) -> None:
    assert fixed("") == [] and by_section("  \n") == [] and semantic("", embed) == []


def test_KR01_boilerplate_lines_repeated_across_a_source_are_dropped() -> None:
    nav = "Home\nContact Us\nसंपर्क करें\nAbout CGTMSE\n"
    texts = {
        f"D{i}": nav + f"Circular {i}\nUnique body text number {i} about fees." for i in range(10)
    }
    cleaned = strip_boilerplate(texts)
    assert "Contact Us" not in cleaned["D3"] and "Home" not in cleaned["D3"]
    assert "Circular 3" in cleaned["D3"] and "Unique body text number 3" in cleaned["D3"]


def test_KR01_boilerplate_filter_leaves_small_sources_alone() -> None:
    texts = {"A": "Home\nbody a", "B": "Home\nbody b"}
    assert strip_boilerplate(texts) == texts  # too few documents to call a line boilerplate


@pytest.mark.parametrize(
    "line",
    [
        "part of the establishment, at any time during",
        "KLEMS",
        "DDMMYYYY",
        "NSDP",
        "schedule of charges applies",
    ],
)
def test_KR01_prose_and_abbreviations_are_not_headings(line: str) -> None:
    assert sections(f"# Top\n{line}\nbody")[-1][0] == "Top"


@pytest.mark.parametrize(
    "line",
    [
        "Chapter III - Benchmark",
        "PART II",
        "Annex",
        "Annex XIII",
        "Schedule.",
        "NOTIFICATION",
        "KEY FACTS",
    ],
)
def test_KR01_real_headings_are_detected(line: str) -> None:
    assert sections(f"{line}\nbody")[0][0] == line


@pytest.mark.parametrize(
    "line",
    [
        "26  THE GAZETTE OF INDIA : EXTRAORDINARY    [PART II—SEC. 3(i)]",
        "SEC. 1] THE GAZETTE OF INDIA EXTRAORDINARY 5",
    ],
)
def test_KR01_gazette_running_headers_are_not_headings(line: str) -> None:
    assert sections(f"# Top\n{line}\nbody")[-1][0] == "Top"
