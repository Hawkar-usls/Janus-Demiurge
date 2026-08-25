# -*- coding: utf-8 -*-
"""JANUS Trinity Core — public-clean modern reconstruction.

Historical architecture preserved here as an operator, not as religious or
metaphysical evidence. The January 2026 JANUS lineage repeatedly used three
independent views before a synthesis/critic gate:
  Father / Strategist -> logic
  Son / Seer         -> intuition / alternative view
  Spirit / Doer      -> action proposal

This modern reconstruction contains no API keys, provider names, network calls,
or autonomous system mutation. Callers inject async role/synthesis/critic
functions and retain final authority.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, asdict
import json
from typing import Awaitable, Callable, Dict, Literal, Mapping

RoleFn = Callable[[str, str], Awaitable[str]]
SynthesisFn = Callable[[str, Mapping[str, str]], Awaitable[str]]
CriticFn = Callable[[str, str], Awaitable[tuple[bool, str]]]


@dataclass(frozen=True)
class CouncilResult:
    prompt: str
    views: Dict[str, str]
    draft: str
    accepted: bool
    final: str
    critic_note: str

    def receipt(self) -> dict:
        return asdict(self)


class TrinityCouncil:
    """Three-view council followed by explicit synthesis and critic veto."""

    ROLES = {
        "father": "strategist_logic",
        "son": "seer_alternative",
        "spirit": "doer_action",
    }

    def __init__(self, runner: RoleFn, synthesizer: SynthesisFn, critic: CriticFn):
        self.runner = runner
        self.synthesizer = synthesizer
        self.critic = critic

    async def consult(self, prompt: str) -> CouncilResult:
        tasks = {key: asyncio.create_task(self.runner(role, prompt)) for key, role in self.ROLES.items()}
        views = {key: await task for key, task in tasks.items()}
        draft = await self.synthesizer(prompt, views)
        accepted, critic_text = await self.critic(prompt, draft)
        final = draft if accepted else critic_text
        return CouncilResult(prompt, views, draft, bool(accepted), final, "OK" if accepted else "REWRITTEN_BY_CRITIC")


Vote = Literal["accelerate", "hold", "stabilize"]


@dataclass(frozen=True)
class TemporalVote:
    name: str
    risk: float
    reward: float
    vote: Vote


@dataclass(frozen=True)
class TemporalConsensus:
    consensus: Vote
    stage_bias: int
    sync: float
    pressure: float
    judges: Dict[str, TemporalVote]

    def receipt(self) -> dict:
        return asdict(self)


class TemporalTrinityCouncil:
    """Public-clean preservation of the later Past/Present/Future 2-of-3 gate."""

    @staticmethod
    def vote(risk: float, reward: float) -> Vote:
        if risk >= 0.62 or reward < -0.22:
            return "stabilize"
        if risk <= 0.34 and reward > 0.18:
            return "accelerate"
        return "hold"

    @classmethod
    def decide(cls, observations: Mapping[str, tuple[float, float]]) -> TemporalConsensus:
        required = ("past", "present", "future")
        if set(observations) != set(required):
            raise ValueError("observations must contain exactly past, present, future")
        judges: Dict[str, TemporalVote] = {}
        for name in required:
            risk, reward = map(float, observations[name])
            judges[name] = TemporalVote(name, risk, reward, cls.vote(risk, reward))
        votes = [j.vote for j in judges.values()]
        if votes.count("stabilize") >= 2:
            consensus: Vote = "stabilize"; stage_bias = -1
        elif votes.count("accelerate") >= 2:
            consensus = "accelerate"; stage_bias = 1
        else:
            consensus = "hold"; stage_bias = 0
        risks = [j.risk for j in judges.values()]
        sync = 1.0 - max(0.0, min(1.0, max(risks) - min(risks)))
        pressure = max(0.0, min(1.0, sum(risks) / 3.0))
        return TemporalConsensus(consensus, stage_bias, sync, pressure, judges)


async def _demo_runner(role: str, prompt: str) -> str:
    return f"{role}: view({prompt})"


async def _demo_synth(prompt: str, views: Mapping[str, str]) -> str:
    return " | ".join(views[k] for k in ("father", "son", "spirit"))


async def _demo_critic(prompt: str, draft: str) -> tuple[bool, str]:
    return (bool(draft and prompt), draft)


async def selftest() -> dict:
    council = TrinityCouncil(_demo_runner, _demo_synth, _demo_critic)
    result = await council.consult("test")
    assert result.accepted
    assert set(result.views) == {"father", "son", "spirit"}
    temporal = TemporalTrinityCouncil.decide({"past": (0.20, 0.30), "present": (0.25, 0.25), "future": (0.50, 0.00)})
    assert temporal.consensus == "accelerate"
    assert temporal.stage_bias == 1
    return {"status": "PASS", "semantic_council": result.receipt(), "temporal_council": temporal.receipt()}


if __name__ == "__main__":
    print(json.dumps(asyncio.run(selftest()), ensure_ascii=False, indent=2))
