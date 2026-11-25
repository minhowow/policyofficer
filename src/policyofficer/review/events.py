"""review 가 내는 진행 사건. 계산 코드는 사건을 내기만 하고, 그리는 일은 report/progress 의 표시기가 한다.

사건은 실제 코드가 도는 순서대로 나온다. 의무별 조사·반박·직접 대조는 의무 묶음마다 이어서 돌아 서로 겹친다(묶음 하나의
조사 답이 오면 바로 인용을 대조하고, 그 묶음의 반박을 묻는다). 질문은 Run.ask 한 번(run.questions 의 기록 하나)이다.
기록 재생(review/replay)도 저장된 결과에서 같은 사건을 만들어 같은 표시기로 그린다.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

STAGES = {
    "profile": "기능 신호",
    "understand": "기능 파악",
    "investigate": "의무별 조사",
    "rebut": "반박",
    "gate": "직접 대조",
}
"""단계와 그 이름. 표시기는 이 순서로 늘어놓는다. 이름은 포스터·영상·웹이 같은 과정을 부르는 말과 같다(기능 파악 →
의무 고르기 → 의무별 조사 → 반박 → 직접 대조 → 체크리스트. 2026-11-25)."""


@dataclass(frozen=True)
class Begin:
    """검토 하나의 머리. CLI(또는 기록 재생)가 표시기에 직접 준다."""

    repo: str
    commit: str | None
    model: str
    checker: str | None
    """반박 모델. None 이면 반박을 끔."""
    batch: str
    usd: float
    seconds: float
    concurrency: int
    egress: str | None = None
    """모델이 읽은 코드가 나가는 곳(가린 주소). 기록 재생은 None."""
    replay: float | None = None
    """기록 재생이면 원래 걸린 초."""


@dataclass(frozen=True)
class Stage:
    stage: str
    state: str
    """start | end | skip | fail"""
    detail: dict = field(default_factory=dict)
    """단계마다 다르다. profile: features·platforms, understand: features·nodes·reused·signals(신호로 잡힌 기능 수)·
    removed(AI 가 뺀 수)·added(AI 가 더한 수), investigate: questions·duties, fail: error, skip: why."""


@dataclass(frozen=True)
class Planned:
    """물을 질문 수가 바뀌었다(+ 더 묻기로 함, - 묻지 않게 됨). 질문 k/N 의 N 이다."""

    delta: int


@dataclass(frozen=True)
class Duty:
    id: str
    law: str
    article: str
    title: str


@dataclass(frozen=True)
class Asked:
    """질문을 보냈다. 상한에 걸려 보내지 않은 질문은 Asked 없이 Answered(failure cost-cap·time-cap)만 온다."""

    q: int
    stage: str
    duties: tuple[Duty, ...] = ()


@dataclass(frozen=True)
class Tool:
    """질문 안에서 모델이 쓴 도구. name 은 read_file·search·list_files, target 은 경로나 검색어."""

    q: int
    name: str
    target: str


@dataclass(frozen=True)
class Result:
    duty: str
    status: str
    """체크리스트 상태(prompts.STATUS_LABEL 의 키). 답이 없으면 unknown."""
    cite: str | None = None
    """관문을 통과한 첫 인용 file:line."""
    verdict: str | None = None
    """반박의 결과: upheld | overturned | overturn-ungrounded."""


@dataclass(frozen=True)
class Answered:
    q: int
    stage: str
    usd: float = 0.0
    seconds: float = 0.0
    failure: str | None = None
    duties: tuple[Duty, ...] = ()
    results: tuple[Result, ...] = ()
    tools: int = 0


@dataclass(frozen=True)
class Checked:
    """질문 하나의 답을 인용 관문과 검색 다시 돌리기에 걸었다(모델이 댄 것만 센다)."""

    q: int
    citations: int
    citations_ok: int
    searches: int
    searches_ok: int


@dataclass(frozen=True)
class Notice:
    """상한 도달·동시 수 줄임·다시 보냄·답을 못 읽어 다시 묻기·서비스에 닿지 못함.

    kind: cost-cap | time-cap | throttle(status, before, after) | retry(status) | repair(q, ok) | unreachable"""

    kind: str
    status: int | None = None
    before: int | None = None
    after: int | None = None
    q: int | None = None
    ok: bool | None = None


Event = Begin | Stage | Planned | Asked | Tool | Answered | Checked | Notice
Sink = Callable[[Event], None]


def ignore(_event: Event) -> None:
    """사건을 받지 않는 곳(시험, 웹이 아닌 라이브러리 사용)의 기본값."""
