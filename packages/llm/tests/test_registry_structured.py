"""Prompt registry (scope #36) and structured output with repair (ARCHITECTURE §8.6, SUP-04)."""

import hashlib
from pathlib import Path

import pytest
from pydantic import BaseModel

from credassure.core import prompts as registry
from credassure.llm.fake import FakeLLM
from credassure.llm.structured import StructuredOutputError, complete_model

GOOD = "name: demo\nversion: 1.2.0\ntemplate: 'Hello $who'\nexamples: ['{\"a\": 1}']\n"


def test_scope36_prompt_file_loads_with_version_and_hash(tmp_path: Path) -> None:
    path = tmp_path / "demo.yaml"
    path.write_text(GOOD)
    p = registry.load_file(path)
    assert (p.name, p.version) == ("demo", "1.2.0")
    assert p.sha256 == hashlib.sha256(GOOD.encode()).hexdigest()
    assert p.render(who="world") == "Hello world"
    assert p.examples == ('{"a": 1}',)


@pytest.mark.parametrize(
    "text",
    [
        "name: demo\nversion: v1\ntemplate: x\n",  # not semver
        "name: demo\nversion: 1.0\ntemplate: x\n",
        "name: other\nversion: 1.0.0\ntemplate: x\n",  # name must match the file
        "name: demo\nversion: 1.0.0\n",  # no template
        "name: demo\nversion: 1.0.0\ntemplate: x\nmax_tokens: 0\n",  # cap must be positive
        "name: demo\nversion: 1.0.0\ntemplate: x\nmax_tokens: lots\n",
    ],
)
def test_scope36_invalid_prompt_files_are_refused(tmp_path: Path, text: str) -> None:
    path = tmp_path / "demo.yaml"
    path.write_text(text)
    with pytest.raises(ValueError):
        registry.load_file(path)


def test_scope36_render_refuses_missing_slots(tmp_path: Path) -> None:
    path = tmp_path / "demo.yaml"
    path.write_text(GOOD)
    with pytest.raises(KeyError):
        registry.load_file(path).render()


def test_scope36_repo_prompts_are_discovered() -> None:
    found = registry.registry()
    assert found["sup_plan"].version.count(".") == 2
    assert registry.prompt_version("sup_plan") == found["sup_plan"].version
    assert registry.prompt_version("no_such_prompt") == "unversioned"
    assert registry.versions()["sup_plan"] == found["sup_plan"].version


def test_scope36_changed_prompt_without_bump_is_a_violation() -> None:
    old = GOOD
    same_version = GOOD.replace("Hello", "Hi")
    bumped = same_version.replace("1.2.0", "1.3.0")
    lowered = same_version.replace("1.2.0", "1.1.9")
    assert registry.bump_violations([("a/prompts/demo.yaml", old, same_version)])
    assert registry.bump_violations([("a/prompts/demo.yaml", old, lowered)])
    assert registry.bump_violations([("a/prompts/demo.yaml", old, bumped)]) == []
    assert registry.bump_violations([("a/prompts/demo.yaml", None, GOOD)]) == []  # new file
    assert registry.bump_violations([("a/prompts/demo.yaml", old, None)]) == []  # deleted
    assert registry.bump_violations([("a/prompts/demo.yaml", old, old)]) == []  # unchanged


class Plan(BaseModel):
    stages: list[str]
    confidence: int


def test_valid_json_is_parsed_first_time() -> None:
    llm = FakeLLM({"p": '{"stages": ["a"], "confidence": 3}'})
    assert complete_model(llm, "p", Plan, "make a plan") == Plan(stages=["a"], confidence=3)
    assert len(llm.calls) == 1
    assert '"confidence"' in llm.calls[0][1]  # schema is in the prompt


def test_fenced_json_is_accepted() -> None:
    llm = FakeLLM({"p": '```json\n{"stages": [], "confidence": 1}\n```'})
    assert complete_model(llm, "p", Plan, "x").confidence == 1


@pytest.mark.parametrize("bad_replies", [1, 2])
def test_SUP04_invalid_output_is_repaired_up_to_twice(bad_replies: int) -> None:
    replies = ["not json"] * bad_replies + ['{"stages": [], "confidence": 2}']
    llm = FakeLLM({"p": replies})
    assert complete_model(llm, "p", Plan, "x").confidence == 2
    assert len(llm.calls) == bad_replies + 1
    assert "invalid" in llm.calls[1][1]
    assert "not json" in llm.calls[1][1]


def test_SUP04_third_failure_raises_StructuredOutputError() -> None:
    llm = FakeLLM({"p": ['{"stages": "oops"}']})
    with pytest.raises(StructuredOutputError):
        complete_model(llm, "p", Plan, "x")
    assert len(llm.calls) == 3


def test_schema_is_offered_for_guided_decoding() -> None:
    seen: list[object] = []

    class Spy(FakeLLM):
        def complete(
            self, prompt: str, *, name: str = "default", json_schema: object = None
        ) -> str:  # type: ignore[override]
            seen.append(json_schema)
            return '{"stages": [], "confidence": 1}'

    complete_model(Spy(), "p", Plan, "x")
    assert seen == [Plan.model_json_schema()]
