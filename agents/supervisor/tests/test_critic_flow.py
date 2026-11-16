"""Critic in the workflow (VER-05, scope #21, ARCHITECTURE §6.3): every stage narrative is checked;
critical findings drive at most two regenerations, then the template; the Critic stage's findings
re-route the case to the offending stage (at most twice)."""

import json
from collections.abc import Callable, Sequence
from typing import Any

from credassure.core.blockers import BlockerCode
from credassure.core.enums import AgentName, Decision, Stage
from credassure.core.findings import CriticFinding, FindingSeverity
from credassure.core.ports import StageContext
from credassure.core.results import AgentResult

CASE = "CA-2026-0001"


class FakeLLM:
    def complete(self, prompt: str, *, name: str, **_: Any) -> str:
        return "unused"


class Narrating:
    """A stage agent whose narrative on call n is ``texts[n]`` (the last one repeats)."""

    def __init__(self, stage: Stage, texts: Sequence[str]) -> None:
        self.stage, self.texts = stage, list(texts)
        self.contexts: list[StageContext] = []

    def __call__(self, ctx: StageContext) -> AgentResult:
        self.contexts.append(ctx)
        text = self.texts[min(len(self.contexts), len(self.texts)) - 1]
        if ctx.template_only:
            text = "template"
        return AgentResult(
            agent=AgentName(self.stage.value),
            case_id=ctx.case_id,
            stage=self.stage,
            tenant_id=ctx.tenant_id,
            decision=Decision.GO,
            narrative=text,
            steps_used=1,
            trace_id=ctx.trace_id,
            agent_version="test",
        )


def finding(stage: Stage | None = None) -> CriticFinding:
    return CriticFinding(
        severity=FindingSeverity.CRITICAL,
        code=BlockerCode.VER_UNSUPPORTED_REASON,
        message="invented reason",
        target_stage=stage,
    )


def flags(*bad: str) -> Callable[[AgentResult], list[CriticFinding]]:
    return lambda r: [finding(r.stage)] if r.narrative in bad else []


def wc_run(build: Any, texts: Sequence[str], critic: Any, **kw: Any) -> tuple[Any, Narrating]:
    wc = Narrating(Stage.WORKING_CAPITAL, texts)
    h = build(agents={Stage.WORKING_CAPITAL: wc}, critic=critic, **kw)
    h.sup.run(CASE)
    return h, wc


def wc_final(h: Any) -> AgentResult:
    return [r for _, r in h.store.finished if r.stage is Stage.WORKING_CAPITAL][-1]


def test_scope21_a_finding_drives_one_regeneration_with_the_findings(build: Any) -> None:
    h, wc = wc_run(build, ["bad", "good"], flags("bad"), llm=FakeLLM())
    assert [c.findings != () for c in wc.contexts] == [False, True]
    assert not any(c.template_only for c in wc.contexts)
    final = wc_final(h)
    assert final.decision is Decision.GO and final.narrative == "good"
    assert h.store.event_types().count("CRITIC_BLOCKED") == 1
    assert "CRITIC_FALLBACK" not in h.store.event_types()


def test_VER05_two_regenerations_then_the_template(build: Any) -> None:
    h, wc = wc_run(build, ["bad"], flags("bad"), llm=FakeLLM())
    assert len(wc.contexts) == 4  # draft, two regenerations, template
    assert [c.template_only for c in wc.contexts] == [False, False, False, True]
    assert wc_final(h).narrative == "template"
    assert h.store.event_types().count("CRITIC_FALLBACK") == 1


def test_VER05_a_template_that_fails_too_blocks_the_stage(build: Any) -> None:
    h, _ = wc_run(build, ["bad"], flags("bad", "template"), llm=FakeLLM())
    final = wc_final(h)
    assert final.decision is Decision.NO_GO
    assert final.narrative != "template"  # withheld, never shown
    assert BlockerCode.VER_UNSUPPORTED_REASON in [b.code for b in final.blockers]


def test_VER05_model_off_means_no_regeneration(build: Any) -> None:
    h, wc = wc_run(build, ["bad"], flags("bad"))
    assert len(wc.contexts) == 1
    assert wc_final(h).decision is Decision.NO_GO


def test_scope1_A2_switches_the_critic_off(build: Any) -> None:
    calls: list[AgentResult] = []
    h, wc = wc_run(build, ["bad"], lambda r: calls.append(r) or [finding()], ablation="A2")
    assert calls == [] and len(wc.contexts) == 1
    assert wc_final(h).decision is Decision.GO


def test_scope1_ablation_reaches_the_agent(build: Any) -> None:
    _, wc = wc_run(build, ["good"], flags(), ablation="A5")
    assert wc.contexts[0].ablation == "A5"


# ---- Critic stage → re-route (ARCHITECTURE §6.3) -------------------------------------------------
class CriticStage:
    """NO_GO with a finding against ``target`` for the first ``fails`` calls, then GO."""

    def __init__(self, target: Stage, fails: int) -> None:
        self.target, self.fails, self.calls = target, fails, 0

    def __call__(self, ctx: StageContext) -> AgentResult:
        self.calls += 1
        bad = self.calls <= self.fails
        found = [finding(self.target).model_dump(mode="json")] if bad else []
        ctx.ledger.put_fact(
            ctx.case_id,
            "ver.findings",
            json.dumps(found),
            unit="json",
            source_type="critic",
            source_ref="test",
            produced_by="test",
        )
        return AgentResult(
            agent=AgentName.CRITIC,
            case_id=ctx.case_id,
            stage=Stage.CRITIC,
            tenant_id=ctx.tenant_id,
            decision=Decision.NO_GO if bad else Decision.GO,
            steps_used=1,
            trace_id=ctx.trace_id,
            agent_version="test",
        )


def test_ARCH63_critic_finding_reopens_only_the_offending_stage(
    build: Any, make_agent: Any
) -> None:
    lw = Narrating(Stage.LENDWISE, ["ok"])
    critic = CriticStage(Stage.LENDWISE, fails=1)
    onb, wc = make_agent(Stage.ONBOARDING), make_agent(Stage.WORKING_CAPITAL)
    h = build(
        agents={
            Stage.ONBOARDING: onb,
            Stage.WORKING_CAPITAL: wc,
            Stage.LENDWISE: lw,
            Stage.CRITIC: critic,
        },
        critic=flags(),
    )
    out = h.sup.run(CASE)
    assert out.status == "AWAITING_APPROVAL"
    assert (onb.calls, wc.calls, len(lw.contexts), critic.calls) == (1, 1, 2, 2)
    assert lw.contexts[1].findings and lw.contexts[1].findings[0].target_stage is Stage.LENDWISE
    assert h.store.event_types().count("CRITIC_REROUTE") == 1


def test_ARCH63_reroutes_are_capped_then_the_case_pauses(build: Any) -> None:
    lw = Narrating(Stage.LENDWISE, ["ok"])
    critic = CriticStage(Stage.LENDWISE, fails=99)
    h = build(agents={Stage.LENDWISE: lw, Stage.CRITIC: critic}, critic=flags())
    out = h.sup.run(CASE)
    assert out.status == "PAUSED" and out.stage is Stage.CRITIC
    assert len(lw.contexts) == 3 and critic.calls == 3  # first run + 2 re-routes
    assert h.store.event_types().count("CRITIC_REROUTE") == 2


class Verdict:
    def __init__(self, text: str) -> None:
        self.text, self.calls = text, 0

    def complete(self, prompt: str, *, name: str, **_: Any) -> str:
        self.calls += 1
        assert name == "sup_gate_a4"
        return self.text


def test_scope1_A4_the_model_decides_the_gate_in_free_text(build: Any, make_agent: Any) -> None:
    """Ablation A4: a NO_GO stage passes because the model says so (what code gates prevent)."""
    wc = make_agent(Stage.WORKING_CAPITAL, [Decision.NO_GO])
    llm = Verdict("I think this stage is GO.")
    h = build(agents={Stage.WORKING_CAPITAL: wc}, llm=llm, ablation="A4")
    out = h.sup.run(CASE)
    assert out.status == "AWAITING_APPROVAL" and llm.calls >= 4
    off = build(agents={Stage.WORKING_CAPITAL: make_agent(Stage.WORKING_CAPITAL, [Decision.NO_GO])})
    assert off.sup.run(CASE).status == "PAUSED"


def test_ARCH63_reroute_from_a_single_stage_run_resumes_the_plan(build: Any) -> None:
    lw = Narrating(Stage.LENDWISE, ["ok"])
    critic = CriticStage(Stage.LENDWISE, fails=1)
    h = build(agents={Stage.LENDWISE: lw, Stage.CRITIC: critic}, critic=flags())
    h.sup.run(CASE, stage=Stage.ONBOARDING)
    h.sup.run(CASE, stage=Stage.WORKING_CAPITAL)
    h.sup.run(CASE, stage=Stage.LENDWISE)
    out = h.sup.run(CASE, stage=Stage.CRITIC)
    assert len(lw.contexts) == 2 and critic.calls == 2
    assert out.status == "AWAITING_APPROVAL"
