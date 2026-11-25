"""저장소 검토(`policyofficer review`): 프로필 → 이해 → 의무별 근거 찾기 → 반박 검증 → 체크리스트.

1. 프로필(profile): 규칙 신호로 기능과 플랫폼(웹·모바일 앱·서버)을 알아본다. 모델 호출 0회.
2. 이해: 조사 모델이 저장소를 읽고 무슨 서비스인지 적고, 기능 목록의 기능마다 있는지 정하고(언어와 상관없이. 규칙
   신호는 JS·TS 만 보는 단서다), 아닌 기능을 빼고, 플랫폼(웹·모바일 앱·서버)을 적고, 개인정보 흐름(마디와 화살표)을
   그린다. 기능·빼기·플랫폼·마디·화살표 모두 인용이 관문을 통과해야 받는다. 플랫폼은 프로필이 package.json 으로 가르지
   못했을 때만 이해 단계의 것을 쓴다. 같은 커밋의 앞 결과를 넘기면(`reuse`) 묻지 않고 그 결과를 관문에 다시 걸어 쓴다.
3. 의무: 기능에 붙은 의무 전부가 목록 층이다. 그 가운데 검토 층 후보(조문 인용 대조 통과·확신 높음·지위가 아님)와 의무
   표의 krcore 칸이 켜진 의무를 묻는다(220개, 제재 표와 1:1). 묶음은 의무 하나(기본), 기능 하나(의무 최대 8개), 또는
   표의 묶음(features.yaml 의 bundles: 같은 기능·같은 코드 범위를 보는 의무 4개까지)이다(`batch`). 답과 관문은
   묶음이어도 의무마다다.
4. 근거 찾기: 조사 모델이 의무마다 상태와 인용·검색·질문을 낸다. 상태(prompts.STATUS_LABEL)와 받는 조건:
     충족 근거 있음        인용이 관문을 통과해야 한다. 아니면 '저장소 밖에서 확인할 것'
     코드에서 본 것        걸리는 처리의 인용이 관문을 통과해야 한다. 아니면 '저장소 밖에서 확인할 것'
     저장소 밖에서 확인할 것 · 해당 여부부터 확인할 것   그대로
     해당 없음             걸리는 조건 자체가 없다는 답(applies '아니오', condition, basis '처리 없음')이어야
                           하고, 찾아본 검색(정규식·줄 수)을 도구가 저장소에서 다시 돌려 줄 수가 같아야 한다(부재의
                           증명). 증명이 없으면 '걸리지 않는 것으로 보임(확인 안 됨)'이고 확인 목록에 올리지 않는다.
                           조건은 있는데 지킨 처리만 없다는 답과, 그 기능이 있으면 걸리는 의무(features.yaml 의
                           whenever)에 기능이 있는 경우는 '코드에서 본 것', 조건을 말하지 않았으면 '해당 여부부터
                           확인할 것'이다(gate). 나이·본인·지역을 확인하는 장치가 없다는 것은 조건이 없다는 증명이
                           아니다: 이용자가 누구인지에 걸리는 의무(features.yaml 의 audience)와 그것을 근거로 든 답
                           (basis '확인 장치 없음')은 '해당 여부부터 확인할 것'
     충족(덧붙임)          인용이 조문이 요구하는 행위 자체여야 한다(shows '행위'). 이름·기본값뿐이면 '코드에서 본 것'.
                           남은 부족한 점(remaining, 없으면 '없음')을 적었으면 '코드에서 본 것'
     걸리는지 모름         '확인할 것'이라도 applies '모름'이면 '해당 여부부터 확인할 것'(그 기능이 있으면 걸리는
                           의무는 빼고)
     해당 여부(덧붙임)     그 기능이 있으면 걸리는 의무를 '해당 여부'로 답해도 그 기능의 처리가 저장소에 있다고
                           보고(applies 예) 인용했으면 '코드에서 본 것'
     자유 입력 추측        이용자가 자유 입력·사진에 넣을 수 있다는 것(trigger '자유 입력 추측')은 걸리는 조건이
                           아니다. 그것뿐인 '코드에서 본 것'(applies 모름이 아닐 때)은, 그 정보를 받는 입력란·필드·
                           저장이 없다는 검색이 맞으면 '걸리지 않는 것으로 보임', 아니면 '해당 여부부터'(표시만으로는
                           목록에서 빼지 않는다). 그것을 근거로 한 반박의 뒤집기는 받지 않는다. 해당 여부·저장소 밖은
                           그대로
     반대쪽 의무           저장소가 서버만 또는 화면만이면 반대쪽이 하는 의무(features.yaml 의 sides)의 '코드에서
                           본 것'은 '저장소 밖에서 확인할 것'
     금지 의무             표의 prohibition("~하지 말 것")은 금지된 행위 자체나 그 빈틈의 인용(shows '금지 행위'·
                           '빈틈')이 있어야 '코드에서 본 것'이다. 아니면 '걸리지 않는 것으로 보임'(검색이 맞으면
                           '해당 없음')
   모델이 다는 표시 '금지 행위'·'빈틈'은 관문을 통과한 인용이 있을 때만 받는다(marked).
   시험 파일의 줄과 설정 파일의 줄은 인용으로 받지 않는다. 설정 파일이라도 주소(scheme://…)나 호스트 값이 글자 그대로
   있는 줄은 받는다(why: config-value). 요건은 조문 인용에 있는 것만 묻는다.
   특정 품목(주류·도서 등, features.yaml 의 goods) 의무는 프로필에 그 품목 신호가 없으면 묻지 않고 '해당 여부부터
   확인할 것'에 한 묶음(group: goods)으로 싣는다. AI 사전 고지·결과물 표시(features.yaml 의 generative)는 분류·인식
   모델(ai-model)만 있으면 묻지 않고 '해당 여부부터'로 싣는다(not-generative). 생성형 AI 기능이 있으면 묻는다. 그 기능이
   있으면 걸리는 의무로 고정하는 것은 프로필의 생성형 신호(SDK 꾸러미·import·호출·주소)가 있을 때만이다.
5. 반박: 다른 모델이 빼는 답(충족·해당 없음·걸리지 않는 것으로 보임)에는 "지키지 않은 곳을 찾아라", 코드에서 본 것과
   저장소 밖에서 확인할 것에는 "지킨 근거를 찾아라"로 다시 본다. 뒤집는 답도 같은 조건(인용·검색)을 넘어야 받는다
   (judge_rebut: 자유 입력 관문이 옮긴 항목은 입력란·필드·저장의 인용 없이, 금지 의무는 금지 행위의 인용 없이 깨지
   못하고, 조사와 반박이 같은 모델이면 '충족'으로 올리지 못하고, 남은 부족한 점을 적은 '충족'은 받지 않는다). 앞
   판단이 조문에 없는 요건을 들었는지도 적는다(off_quote). 해당 여부는 사업자의 판단이라 반박하지 않는다. 반박을 끄면
   (Limits.rebut, CLI --no-rebut) 묻지 않고 verification 은 not-run(why rebut-off), run.rebut 은 false 다. 반박을
   '코드에서 본 것'·'충족 근거 있음'에만 걸 수도 있다(Limits.rebut_scope 'found', CLI --rebut-scope found. 나머지는
   not-run, why rebut-scope).
6. 체크리스트는 상태의 갈래 순(코드에서 본 것이 맨 위), 그 안에서는 거의 모든 서비스·가입·AI·외부 전송 순이다.
   기능 안에서는 핵심 의무(일반 범위 → 흔한 것 → 확신 높은 것)가 먼저이고 품목 의무가 맨 뒤다. 묻는 순서도 같아서
   상한에 걸려도 핵심은 묻는다. `summary` 에 갈래별 수와 맨 위 다섯 건, 묶음(groups)이 있다. 항목마다 의무별 제재
   (sanction, profile/sanctions.jsonl)를 붙인다.

지키는 것: 인용 관문, 비밀값 가리기·비밀 파일 거부(judge/agent.RepoTools), 저장소 밖 읽기 금지, 저장소당 상한(어림
금액·시간). 상한 때문에 묻지 못한 의무는 '모름'으로 싣고 까닭을 적는다. 동시 요청은 429 를 보면 반으로 줄인다.
"""

from __future__ import annotations

import copy
import os
import queue
import re
import subprocess
import threading
import time
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path

from policyofficer import __version__
from policyofficer.evidence import gate
from policyofficer.judge.agent import MODELS, AgentAnswer, AgentJudge, RepoTools
from policyofficer.profile import load_duties, load_features, load_sanctions, profile
from policyofficer.review import events as E
from policyofficer.review import prompts as P
from policyofficer.roles import SERVICE, Role, classify

REVIEW_VERSION = 2
"""1 → 2: '확인할 것'을 세 갈래(seen-in-code·check-outside·check-applicability)로 나누고, 부재 증명(searches)과
'걸리지 않는 것으로 보임'(likely-not-applicable)을 더했다. 체크리스트를 갈래 순으로 늘어놓고 summary 를 더했다.
2판 안의 덧붙임(11/12): 답의 applies·condition·missing·shows 와 관문이 바꾼 까닭(gate), 품목 묶음(group,
summary.groups), not_answered 'goods-not-detected', 인용 why 'profile'(기능이 있다는 프로필 신호를 조건의 근거로
붙인 것)."""
PRIORITY = ("common", "signup", "genai", "external-transfer")
"""상한에 걸리면 이 순서로 먼저 묻고, 체크리스트의 같은 갈래 안에서도 이 순서로 놓는다. 나머지는 기능 목록의 순서다."""
GROUP_MAX = 8
BUNDLE_MAX = 4
"""표의 묶음(features.yaml 의 bundles) 하나에 넣는 의무 수의 상한."""
DROPS = ("evidence-found", "not-applicable", "likely-not-applicable")
"""목록에서 빼는 상태. 반박이 "지키지 않은 곳"을 찾는다."""
TO_CHECK = ("seen-in-code", "check-outside")
"""반박이 "지킨 근거"를 찾는 상태. 해당 여부(check-applicability)는 사업자의 판단이라 묻지 않는다."""
FOUND = ("seen-in-code", "evidence-found")
"""rebut_scope 'found' 에서 반박하는 상태: 코드에서 본 것과 충족 근거 있음."""
NONE_LEFT = ("", "없음", "none")
"""남은 부족한 점(remaining)이 없다는 값. 앞뒤 빈칸·마침표를 떼고 견준다. 그 밖의 글은 무엇이든 남은 점이 있다는
것이다."""
PLATFORM_KO = {"web": "웹", "mobile": "모바일 앱", "server": "서버"}
NOT_ANSWERED = {"cost-cap": "저장소당 금액 상한에 걸려 묻지 못했습니다", "time-cap": "시간 상한에 걸렸습니다"}
SERVER_LANGS = (".py", ".java", ".kt", ".go", ".rb", ".php", ".cs", ".rs", ".scala")
"""JS·TS 밖의 서버 코드. profile 의 platforms 는 package.json 과 JS·TS 파일로 가르므로, 이 파일이 있으면 화면만인
저장소로 보지 않는다(11/13: Excelerate 는 플랫폼이 웹뿐인데 Python 서버가 있다)."""
_VALUE = re.compile(
    r"[a-z][a-z0-9+.-]*://[^\s'\"`]+|\b(host|hostname|endpoint|domain)\w*['\"]?\s*[:=]\s*['\"]?[\w-]+(\.[\w-]+)+", re.I
)
"""설정 파일에서 인용으로 받는 줄: 주소(scheme://…)나 호스트 값이 글자 그대로 있다(Sentry DSN, API 주소, 메일 서버)."""
GOODS_LABEL = "특정 품목을 판다면 확인할 것"
FIRST_KEYS = (
    *("answered", "status", "citations", "searches"),
    *("applies", "condition", "missing", "shows", "basis", "trigger", "remaining", "gate", "reason", "question"),
)
PRICES = {
    "claude-opus-5-5": (4.0, 5.0, 0.20, 20.0),
    "claude-sonnet-5-5": (2.0, 2.5, 0.10, 10.0),
    "claude-haiku-5-5": (0.10, 0.125, 0.01, 0.50),
}
"""100만 토큰당 달러(입력, 5분 캐시 쓰기, 캐시 읽기, 출력). 공식 가격표(2026-11-12 확인,
platform.claude.com/docs/en/about-claude/pricing)다. 이 앞의 표는 옛 모델 단가(haiku $1/$5, sonnet $3/$15, 캐시 읽기
0.1배)라 11/12 실측을 2.4배로 셌다($36.64, 공식 단가로 약 $15). 모델 id 가 이 키로 시작하면 그 단가다."""
UNKNOWN_PRICE = (15.0, 18.75, 1.50, 75.0)
"""표에 없는 모델의 단가. 가격표에서 가장 비싼 값(opus 4.1)이라 틀려도 상한이 먼저 걸리는 쪽이다."""
LONG_PROMPT = {"claude-haiku-5-5": (100_000, 5.0)}
"""호출 하나의 프롬프트(입력 + 캐시 쓰기 + 캐시 읽기)가 이 토큰 수를 넘으면 그 호출의 모든 단가가 이 배수다."""
RESERVE = {"claude-haiku-5-5": 0.05, "claude-sonnet-5-5": 0.15, "claude-opus-5-5": 0.30}
"""질문 하나를 새로 보내기 전에 남아 있어야 하는 어림 금액. 대화 중에는 멈출 수 없어 상한을 넘지 않게 미리 남긴다.
11/12 실측 질문 하나의 최대(공식 단가): haiku 약 $0.02, sonnet $0.12. 표에 없는 모델은 UNKNOWN_RESERVE."""
UNKNOWN_RESERVE = 2.0
MAX_TOKENS = 16000
"""답 하나의 출력 상한. 이해 단계의 흐름과 기능 묶음의 답이 8192 에서 잘렸다(11/11 실측). 쓴 만큼만 청구된다."""


# ── 상한과 속도 ─────────────────────────────────────────────────────


def _model(model: str) -> str | None:
    return next((m for m in PRICES if model.startswith(m)), None)


def usd(model: str, usage: dict) -> float:
    """호출 하나의 금액."""
    known = _model(model)
    pin, pwrite, pread, pout = PRICES[known] if known else UNKNOWN_PRICE
    prompt = sum(usage.get(k, 0) for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
    limit, times = LONG_PROMPT.get(known or "", (0, 1.0))
    scale = (times if limit and prompt > limit else 1.0) / 1e6
    return scale * (
        usage.get("input_tokens", 0) * pin
        + usage.get("cache_creation_input_tokens", 0) * pwrite
        + usage.get("cache_read_input_tokens", 0) * pread
        + usage.get("output_tokens", 0) * pout
    )


def cost(model: str, ans: AgentAnswer) -> float:
    """질문 하나(대화의 호출 전부)의 금액. 호출마다 매겨 더한다."""
    return sum(usd(model, u) for u in ans.per_call)


class Spend:
    """어림 금액. 질문을 보내기 전에 `allows` 로 묻고, 답을 받으면 `add` 로 더한다."""

    def __init__(self, cap: float) -> None:
        self.cap, self.usd, self.usage = cap, 0.0, {}
        self._lock = threading.Lock()

    def allows(self, model: str) -> bool:
        with self._lock:
            return self.usd + RESERVE.get(_model(model) or "", UNKNOWN_RESERVE) <= self.cap

    def add(self, model: str, ans: AgentAnswer) -> None:
        with self._lock:
            self.usd += cost(model, ans)
            mine = self.usage.setdefault(model, {})
            for k, v in ans.usage.items():
                if isinstance(v, int):
                    mine[k] = mine.get(k, 0) + v


class Throttle:
    """동시에 보내는 요청 수. 429 를 받으면 반으로 줄인다(1 까지). 판정기의 전송을 감싸 쓴다."""

    def __init__(self, limit: int) -> None:
        self.start = self.limit = max(1, limit)
        self.active = self.rate_limited = 0
        self._cv = threading.Condition()
        self.listener: E.Sink = E.ignore
        """다시 보낼 때의 사건(429 면 throttle, 그 밖의 상태는 retry)을 받는 곳. review 가 진행 표시에 잇는다."""

    def __enter__(self):
        with self._cv:
            while self.active >= self.limit:
                self._cv.wait()
            self.active += 1

    def __exit__(self, *exc):
        with self._cv:
            self.active -= 1
            self._cv.notify_all()

    def saw(self, status: int) -> None:
        if status != 429:
            self.listener(E.Notice("retry", status=status))
            return
        with self._cv:
            before = self.limit
            self.rate_limited += 1
            self.limit = max(1, self.limit // 2)
        self.listener(E.Notice("throttle", status=status, before=before, after=self.limit))

    def wrap(self, send):
        def throttled(body: dict) -> dict:
            with self:
                return send(body)

        return throttled


@dataclass
class Limits:
    usd: float = 5.0
    seconds: float = 360.0
    concurrency: int = 6
    batch: str = "duty"  # duty | feature | bundle. 11/11 실측(사례 4곳): duty 가 의무마다 인용이 많고 비용은 1.8배
    rebut: bool = True  # False 면 반박을 묻지 않는다(verification not-run, why rebut-off). 웹의 기본은 켬
    rebut_scope: str = "all"  # all | found(코드에서 본 것·충족 근거 있음만 반박. 나머지는 not-run, why rebut-scope)


# ── 인용 ─────────────────────────────────────────────────────────────


def check(root: Path, citations: list[dict]) -> list[dict]:
    """인용 관문(evidence.gate)에 더해, 시험·픽스처·설정 파일의 줄은 받지 않는다(why: test-file). 설정 파일이라도
    주소나 호스트 값이 글자 그대로 있는 줄은 받는다(why: config-value. 11/13 실측: Sentry DSN 줄을 받지 않았다)."""
    out, root = gate(root, citations), root.resolve()
    for c in out:
        if c["ok"]:
            # 관문은 '..' 이 든 경로를 풀어 파일을 찾는다. 같은 파일을 저장소 기준 경로로 읽는다(11/13 실측:
            # 'src/styles/../components/…' 인용에서 없는 폴더를 거쳐 읽다가 검사가 멈췄다)
            path = (root / c["file"].lstrip("/")).resolve()
            rel = path.relative_to(root).as_posix()
            role = classify(rel, path.read_text(encoding="utf-8", errors="replace"))
            if role in SERVICE:
                c["file"] = rel
            elif role is Role.CONFIG and _VALUE.search(c["text"]):
                c["file"], c["why"] = rel, "config-value"
            else:
                c["ok"], c["why"] = False, "test-file"
    return out


def grounded(cs: list[dict]) -> bool:
    return any(c["ok"] for c in cs)


def _whenever() -> dict[str, str]:
    """그 기능이 있으면 걸리는 의무 → 기능 id (features.yaml 의 whenever)."""
    return {d: f["id"] for f in load_features()["features"] for d in f.get("whenever") or []}


def _audience() -> dict[str, str]:
    """이용자가 누구인지(나이·본인·지역)에 걸리는 의무 → 기능 id (features.yaml 의 audience)."""
    return {d: f["id"] for f in load_features()["features"] for d in f.get("audience") or []}


def _generative() -> dict[str, str]:
    """생성형 AI 신호가 있을 때만 묻는 의무 → 기능 id (features.yaml 의 generative)."""
    return {d: f["id"] for f in load_features()["features"] for d in f.get("generative") or []}


def _sides() -> dict[str, set[str]]:
    """화면이 하는 의무(screen)와 서버가 하는 의무(server) (features.yaml 의 sides)."""
    return {k: set(v) for k, v in (load_features().get("sides") or {}).items()}


def _goods() -> dict[str, dict]:
    """특정 품목을 팔 때만 걸리는 의무 → 그 품목(features.yaml 의 goods)."""
    return {d: g for g in load_features().get("goods") or [] for d in g["duties"]}


def _bundles() -> dict[str, str]:
    """한 질문에 묶어 묻는 의무 → 묶음 id (features.yaml 의 bundles)."""
    return {d: b["id"] for b in load_features().get("bundles") or [] for d in b["duties"]}


def core_key(d: dict) -> tuple:
    """기능 안에서 묻고 늘어놓는 순서: 품목 의무는 맨 뒤, 그 앞은 일반 범위 → 그 기능이 있으면 걸리는 의무(whenever) →
    흔한 것(의무 지도의 freq) → 확신 높은 것. 11/12 실측: id 순으로 물어 상한에 걸린 POS 가 농산물 원산지를 묻고
    탈퇴·해지(전자상거래법)는 묻지 못했다."""
    return (
        d["id"] in _goods(),
        d["scope"] != "general",
        d["id"] not in _whenever(),
        -(d.get("freq") or 0),
        d["confidence"] != "high",
        d["id"],
    )


def _present(feature: dict | None) -> bool:
    return feature is not None and "removed" not in feature


def _always(d: dict, feature: dict | None) -> bool:
    """그 기능이 있으면 걸리는 의무이고 기능이 있다. AI 사전 고지·결과물 표시(generative)는 생성형 신호(프로필)가
    있을 때만이다. 신호 없이 AI 기능만 있으면 묻고 조사 답을 따른다(11/13 4배치: Python 서버·자체 API·로컬 모델로 LLM
    을 부르는 곳은 프로필 신호가 없다)."""
    if d["id"] in _generative() and not generative(feature):
        return False
    return d["id"] in _whenever() and _present(feature)


def generative(feature: dict | None) -> bool:
    """생성형 AI 신호가 있다: 프로필 신호(SDK 꾸러미·import·호출·주소)로만 정한다. 경로 낱말(ai·gpt)이나 이해 단계가
    더한 것만으로는 아니다(11/13 실측: 포즈 분류 모델을 'AI 기능'으로 더했다)."""
    return _present(feature) and any(
        e.get("signal") in ("package", "import", "call", "url") for e in feature["evidence"]
    )


def lacks(root: Path, platforms: list[str]) -> str | None:
    """저장소에 없는 쪽: 서버만이면 'screen', 화면만(웹·모바일 앱, 다른 언어의 서버 파일도 없음)이면 'server'."""
    if platforms == ["server"]:
        return "screen"
    if not platforms or "server" in platforms:
        return None
    from policyofficer.judge.agent import SKIP_DIRS

    for _dir, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        if any(n.endswith(SERVER_LANGS) for n in filenames):
            return None
    return "server"


SIDE_KO = {"screen": "화면", "server": "서버"}


def marked(s: dict, cs: list[dict]) -> str | None:
    """답이 단 표시('금지 행위'·'빈틈')는 관문을 통과한 인용이 있을 때만 받는다. 표시는 모델이 스스로 달아서
    (11/13 5·6배치: 조건의 줄에도 '빈틈'을 달았다) 그것만으로는 규칙을 바꾸지 않는다. 받으면 그 표시, 아니면 None."""
    return s["shows"] if s.get("shows") in ("금지 행위", "빈틈") and grounded(cs) else None


def left(s: dict) -> bool:
    """'충족'이라 답하면서 남은 부족한 점(remaining)을 적었다. 비었거나 '없음'이면 아니다."""
    return str(s.get("remaining") or "").strip().strip(".").strip().lower() not in NONE_LEFT


def other_side(
    d: dict, status: str, gate_: dict | None, lacking: str | None, s: dict | None = None, cs: list | None = None
) -> tuple[str, dict | None]:
    """저장소에 없는 쪽이 하는 의무의 '코드에서 본 것'은 '저장소 밖에서 확인할 것'이다. 다만 답이 이 저장소의 줄을
    인용해 빈틈 자체를 보였으면(shows '빈틈'·'금지 행위', 관문 통과 인용) 옮기지 않는다(11/13 4배치: 화면만인 저장소의
    관리자 화면 보호가 상수 "true" 로 고정된 것을 '저장소 밖'으로 보냈다)."""
    if status != "seen-in-code" or not lacking or d["id"] not in _sides().get(lacking, set()):
        return status, gate_
    if s and marked(s, cs or []):
        return status, gate_
    where = SIDE_KO[lacking]
    note = f"이 저장소에는 {where} 코드가 없어 {where}에서 하는 의무는 '저장소 밖에서 확인할 것'으로 옮겼습니다."
    if gate_:
        note = f"{gate_['note']} {note}"
    return "check-outside", {"from": (gate_ or {}).get("from", "seen-in-code"), "why": "other-side", "note": note}


def _feature_citations(root: Path, feature: dict) -> list[dict]:
    """기능이 있다는 근거를 인용 꼴로(why: profile). 이해 단계의 인용(관문 통과)이 먼저, 다음이 프로필 신호의 줄이다."""
    out = [c for c in feature.get("model_citations", []) if c.get("ok")]
    for e in feature.get("evidence", []):
        text = ""
        if e.get("line"):
            with suppress(OSError, IndexError):
                text = (root / e["file"]).read_text(encoding="utf-8", errors="replace").splitlines()[e["line"] - 1]
        out.append({"file": e["file"], "line": e.get("line"), "text": text.strip()[:200], "ok": True, "why": "profile"})
    return out[:2]


def said(r: dict) -> dict:
    """답이 적은 걸리는 조건(applies·condition·basis·trigger), 없는 것(missing), 충족 인용의 성격(shows)."""
    return {
        "applies": r.get("applies") if r.get("applies") in P.APPLIES else None,
        "condition": str(r.get("condition") or "").strip()[:300],
        "basis": r.get("basis") if r.get("basis") in P.BASIS else None,
        "trigger": r.get("trigger") if r.get("trigger") in P.TRIGGER else None,
        "missing": str(r.get("missing") or "").strip()[:300],
        "shows": r.get("shows") if r.get("shows") in P.SHOWS else None,
        "remaining": str(r.get("remaining") or "").strip()[:300],
    }


def absent(d: dict, s: dict, proven: bool, feature: dict | None, cited: bool) -> tuple[str, dict | None]:
    """'해당 없음'은 걸리는 조건 자체가 없을 때만 받는다(11/12 실측: '약관이 아예 없다', '탈퇴 경로가 아예 없다',
    '위치 동의 철회 기능이 없다'를 해당 없음으로 읽었다 — 검색 관문은 줄 수만 맞춰 봐서 막지 못했다).
    (상태, 관문이 바꾼 까닭 또는 None)"""
    if _always(d, feature):
        note = f"{feature['name']} 기능이 있으면 걸리는 의무라 '해당 없음'으로 받지 않았습니다"
        note += ". 지킨 처리는 찾지 못했습니다"
        return "seen-in-code", {"from": "not-applicable", "why": "condition-present", "note": _missing(note, s)}
    if s["applies"] == "예":
        note = "걸리는 조건이 있다고 답해" + (f"({s['condition']})" if s["condition"] else "")
        note += " '해당 없음'으로 받지 않았습니다. 지킨 처리는 찾지 못했습니다"
        gate_ = {"from": "not-applicable", "why": "condition-present", "note": _missing(note, s)}
        return ("seen-in-code" if cited else "check-applicability"), gate_
    # 나이·본인·지역을 확인하는 장치가 없다는 것은 그런 이용자가 없다는 증명이 아니다(11/12 재실행: 나이 확인이 없는
    # 가입을 '아동 동의 해당 없음'으로 읽었다). 이용자가 누구인지에 걸리는 의무(audience)는 답과 상관없이, 다른 의무는
    # 답이 그것을 근거로 들 때(basis '확인 장치 없음') 해당 여부부터다
    if d["id"] in _audience() or s["basis"] == "확인 장치 없음":
        note = "나이·본인·지역을 확인하는 장치가 없다는 것은 그런 이용자가 없다는 증명이 아니라"
        note += " '해당 없음'으로 받지 않았습니다."
        if d["id"] not in _audience():
            return "check-applicability", {"from": "not-applicable", "why": "missing-check", "note": note}
        who = "이용자가 누구인지(아동·미성년자·청소년)에 걸리는 의무라 코드만으로는 '해당 없음'을 받지 않았습니다."
        note = f"{who} {note}"
        return "check-applicability", {"from": "not-applicable", "why": "audience", "note": note}
    if s["applies"] != "아니오" or not s["condition"] or s["basis"] != "처리 없음":
        note = "걸리는 조건 자체가 없다는 답(applies '아니오', condition, basis '처리 없음')이 없어"
        note += " '해당 없음'으로 받지 않았습니다."
        return "check-applicability", {"from": "not-applicable", "why": "no-condition", "note": note}
    return ("not-applicable" if proven else "likely-not-applicable"), None


def unknown(d: dict, s: dict, answered: str, feature: dict | None) -> dict | None:
    """걸리는지 모른다고 답한 '확인할 것'(applies '모름')은 해당 여부부터다(11/12 재실행: 외부 AI 호출을 '제3자
    제공'으로 보고 "제공인지 위탁인지는 개발자 판단"이라면서 '코드에서 본 것'에 뒀다). 그 기능이 있으면 걸리는 의무는
    그대로 둔다. 관문이 바꾼 까닭 또는 None."""
    if s["applies"] != "모름" or _always(d, feature):
        return None
    note = "걸리는지 모른다고 답해(applies '모름') '해당 여부부터 확인할 것'으로 옮겼습니다."
    return {"from": answered, "why": "applies-unknown", "note": note}


def _missing(note: str, s: dict) -> str:
    return note + (f": {s['missing']}." if s["missing"] else ".")


PROHIBITION_NOTE = (
    "금지 의무라 금지된 행위 자체나 그 빈틈을 인용하지 않으면 '코드에서 본 것'으로 받지 않았습니다(막는 장치가 없다는"
    " 것은 근거가 아닙니다)."
)
FREE_UNPROVEN_NOTE = (
    "걸리는 조건이 이용자가 자유 입력·사진에 넣을 수 있다는 추측뿐이라는 답인데, 그 정보를 받는 입력란·필드·저장이"
    " 없다는 검색 증명이 없어 '해당 여부부터 확인할 것'으로 옮겼습니다."
)
GUESSED_HINT = (
    "\n  앞 판단의 조건은 자유 입력 추측뿐이었다. 뒤집으려면 그 정보를 받는 입력란·필드·저장 코드를 인용하고"
    " applies '예', trigger '입력란·처리·저장'으로 답한다."
)
SAME_MODEL_NOTE = "조사와 반박이 같은 모델이라 '충족 근거 있음'으로 올리는 뒤집기는 받지 않았습니다."
GUESSED_NOTE = (
    "조사 답의 조건이 자유 입력 추측뿐이라 '걸리지 않는 것으로 보임'으로 둔 의무입니다. 그 정보를 받는 입력란·필드·저장"
    " 코드의 인용(applies '예', trigger '입력란·처리·저장')이 관문을 통과하지 않아 뒤집기를 받지 않았습니다."
)


def guess(d: dict, s: dict, answered: str, feature: dict | None) -> dict | None:
    """걸리는 조건이 이용자가 자유 입력·사진에 넣을 수 있다는 추측뿐이다(trigger '자유 입력 추측'). 11/13 실측: 채팅
    입력에 민감정보가, 인증 사진에 신분증이 들어올 수 있다며 '해당 없음'을 '해당 여부부터'로 뒤집었다. 그 기능이 있으면
    걸리는 의무와 이용자가 누구인지에 걸리는 의무는 그대로 둔다. 관문이 바꾼 까닭 또는 None."""
    if s["trigger"] != "자유 입력 추측" or _always(d, feature) or d["id"] in _audience():
        return None
    note = "이용자가 자유 입력·사진에 그 정보를 넣을 수 있다는 추측은 걸리는 조건이 아니라"
    return {"from": answered, "why": "free-input", "note": note}


def accept(
    d: dict, s: dict, answered: str, cs: list[dict], proven: bool, feature: dict | None, lacking: str | None = None
):
    """모델이 고른 상태에 받는 조건을 건다. `lacking` 은 저장소에 없는 쪽(lacks). (상태, 관문이 바꾼 까닭 또는 None)"""
    return other_side(d, *_accept(d, s, answered, cs, proven, feature), lacking, s, cs)


def _accept(d: dict, s: dict, answered: str, cs: list[dict], proven: bool, feature: dict | None):
    if answered == "not-applicable":
        return absent(d, s, proven, feature, grounded(cs))
    if answered == "seen-in-code" and s["applies"] != "모름" and (gate_ := guess(d, s, answered, feature)):
        # '코드에서 본 것' 후보를 내릴 때만 쓴다. '해당 여부'(사업자인지 모름 등)는 그대로 둔다(11/13 실측: 모델이 이
        # 표시를 "사업자 해당 여부를 모른다"는 뜻으로 달아 '해당 여부'가 '걸리지 않는 듯'으로 내려갔다). 목록에서 빼는
        # 것은 그 정보를 받는 입력란·필드·저장이 없다는 검색을 도구가 다시 돌려 맞을 때뿐이다(표시만으로는 빼지 않는다)
        if not proven:
            return "check-applicability", {**gate_, "note": FREE_UNPROVEN_NOTE}
        gate_["note"] += " '걸리지 않는 것으로 보임'으로 옮겼습니다."
        return "likely-not-applicable", gate_
    if answered == "check-applicability" and _always(d, feature) and s["applies"] == "예" and grounded(cs):
        # 조사 답이 그 기능의 처리가 저장소에 있다고 보고(applies 예) 그 줄을 인용했을 때만 올린다. "결제·주문 처리가
        # 저장소에 없다"(외부 판매 링크만)는 답은 '해당 여부'에 남는다(11/13 실측: 책 SNS 의 상거래 의무 5건)
        note = f"{feature['name']} 기능이 있으면 걸리는 의무라 '해당 여부'가 아니라 '코드에서 본 것'으로 옮겼습니다"
        return "seen-in-code", {"from": answered, "why": "condition-present", "note": _missing(note, s)}
    if answered in TO_CHECK and (gate_ := unknown(d, s, answered, feature)):
        return "check-applicability", gate_
    if answered == "seen-in-code" and d.get("prohibition") and not marked(s, cs):
        # 11/13 실측: 가짜 마감 타이머·'반품 불가' 문구를 찾지 못하고도 "막는 장치가 없다"며 코드에서 본 것으로 뒀다.
        # 금지된 행위가 일어나게 하는 빈틈을 인용했으면(shows '빈틈', 관문 통과) 둔다(11/13 7배치: 'BEST' 정렬의
        # 판매량을 브라우저가 보낸 값으로 바꾸는 줄을 '빈틈'으로 달아 '해당 없음'으로 내려갔다)
        status = "not-applicable" if proven else "likely-not-applicable"
        return status, {"from": answered, "why": "prohibition", "note": PROHIBITION_NOTE}
    if answered in ("evidence-found", "seen-in-code") and not grounded(cs):
        return "check-outside", None
    if answered == "evidence-found" and left(s):
        # 11/13 실측: 접근권한 최소화를 '충족'으로 답하면서 "탈퇴 API 는 본인 여부를 확인하지 않는다"고 적었다
        note = f"'충족'이라 답하면서 남은 부족한 점을 적어 '코드에서 본 것'으로 옮겼습니다: {s['remaining']}."
        return "seen-in-code", {"from": answered, "why": "remaining-gap", "note": note}
    if answered == "evidence-found" and s["shows"] != "행위":
        # 11/12 실측: helmet 의 기본 HSTS 만으로 전송 암호화 충족, 메뉴의 'GenAI' 글자로 AI 사전 고지 충족
        note = "인용이 조문이 요구하는 행위가 아니라 이름·기본값뿐이라 '충족 근거 있음'으로 받지 않았습니다."
        return "seen-in-code", {"from": answered, "why": "name-or-default", "note": note}
    return answered, None


def prove(root: Path, searches: list[dict]) -> tuple[list[dict], bool]:
    """모델이 "찾아봤는데 없다"며 낸 검색을 저장소에서 다시 돌린다. 검색마다 {pattern, path, claimed, found, ok, why}.
    증명은 검색이 하나 이상이고 모두 줄 수가 같을 때다(why: match). 다르면 mismatch, 정규식이 틀리거나 두 글자보다
    짧으면 bad-pattern, 저장소 밖이면 outside-repo, 줄 수를 적지 않았으면 no-count 다."""
    tools, out = RepoTools(root), []
    for s in searches:
        pattern, path = str(s.get("pattern") or ""), str(s.get("path") or ".")
        claimed = s.get("hits") if isinstance(s.get("hits"), int) else None
        rec = {"pattern": pattern[:200], "path": path[:200], "claimed": claimed, "found": None, "ok": False, "why": ""}
        if len(pattern.strip()) < 2:
            rec["why"] = "bad-pattern"
        else:
            try:
                rec["found"] = tools.count(pattern, path)
            except re.error:
                rec["why"] = "bad-pattern"
            except ValueError:
                rec["why"] = "outside-repo"
        if rec["found"] is not None:
            rec["why"] = "no-count" if claimed is None else "match" if claimed == rec["found"] else "mismatch"
            rec["ok"] = rec["why"] == "match"
        out.append(rec)
    return out, bool(out) and all(r["ok"] for r in out)


# ── 질문 기록 ─────────────────────────────────────────────────────────


@dataclass
class Run:
    root: Path
    investigator: AgentJudge
    checker: AgentJudge
    limits: Limits
    spend: Spend
    lacks: str | None = None
    platforms_from: str = "signal"
    questions: list[dict] = field(default_factory=list)
    t0: float = field(default_factory=time.monotonic)
    emit: E.Sink = E.ignore
    """진행 사건을 받는 곳(report/progress 의 표시기). 계산은 사건을 내기만 한다."""
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _next: int = 0
    _once: set = field(default_factory=set)

    def qid(self) -> int:
        """진행 사건의 질문 번호. 기록 번호(n)는 답을 받은 순서라 묻기 전에는 모른다."""
        with self._lock:
            self._next += 1
            return self._next

    def once(self, key: str, event: E.Event) -> None:
        """처음 한 번만 낸다(단계 시작, 상한 도달 알림)."""
        with self._lock:
            if key in self._once:
                return
            self._once.add(key)
        self.emit(event)

    def halt(self) -> None:
        """Ctrl+C·오류로 멈출 때: 새 질문은 보내지 않고(time-cap), 대화 중인 질문은 다음 차례를 보내지 않는다."""
        now = time.monotonic()
        for j in (self.investigator, self.checker):
            j.deadline = now

    def _tool(self, q: int, name: str, args: dict) -> None:
        target = args.get("pattern") if name == "search" else args.get("path") or args.get("pattern") or "."
        self.emit(E.Tool(q, name, str(target or "")[:200]))

    def ask(
        self,
        stage: str,
        judge: AgentJudge,
        prompt: str,
        budget: int,
        meta: dict,
        key: str,
        asked: E.Asked | None = None,
    ) -> tuple[dict | None, str | None, int]:
        """상한 안이면 묻고, 답에서 `key` 를 가진 JSON 객체를 읽고, 기록한다. (객체, 실패 까닭, 기록 번호).
        상한에 걸리면 묻지 않고 cost-cap·time-cap 이다. 답이 JSON 이 아니면 도구 없이 한 번 더, 그 답을 요청한 JSON 으로
        옮겨 달라고 묻는다(repaired). 그래도 안 되면 parse 이고 답의 글 앞부분을 기록에 남긴다. `asked` 는 보낼 때
        내는 진행 사건이다(그 질문 번호로 도구 사건을 낸다). 답의 사건(Answered)은 관문을 건 뒤 부르는 쪽이
        낸다(answered)."""
        if not self.spend.allows(judge.model):
            self.once("cost-cap", E.Notice("cost-cap"))
            return None, "cost-cap", self._log(stage, judge, meta, None, "cost-cap")
        if judge.deadline is not None and time.monotonic() >= judge.deadline:
            self.once("time-cap", E.Notice("time-cap"))
            return None, "time-cap", self._log(stage, judge, meta, None, "time-cap")
        on_tool = None
        if asked is not None:
            if stage == "rebut":
                self.once("stage-rebut", E.Stage("rebut", "start"))
            self.emit(asked)
            on_tool = lambda name, args: self._tool(asked.q, name, args)  # noqa: E731
        start = time.monotonic()
        text, ans = judge.converse(prompt, self.root, budget, max_tokens=MAX_TOKENS, on_tool=on_tool)
        self.spend.add(judge.model, ans)
        failure, doc, extra = ans.failure, None, {}
        if failure and failure.startswith("time"):
            failure = "time-cap"
            self.once("time-cap", E.Notice("time-cap"))
        elif failure == "transport: skipped":
            self.once("unreachable", E.Notice("unreachable"))
        if not failure:
            doc = P.parse_object(text, key)
            if doc is None and text.strip() and self.spend.allows(judge.model):
                self.emit(E.Notice("repair", q=asked.q if asked else None))
                fixed, fix = judge.converse(P.REPAIR.format(key=key, raw=text[-24000:]), self.root, 0, MAX_TOKENS)
                self.spend.add(judge.model, fix)
                ans.calls += fix.calls
                ans.per_call += fix.per_call
                for k, v in fix.usage.items():
                    ans.usage[k] = ans.usage.get(k, 0) + v
                doc = P.parse_object(fixed, key) if not fix.failure else None
                extra["repaired"] = doc is not None
            if doc is None:
                failure, extra["raw"] = "parse", text[:2000]
        timing = {"started": round(start - self.t0, 1), "seconds": round(time.monotonic() - start, 1)}
        return doc, failure, self._log(stage, judge, {**meta, **timing, **extra}, ans, failure)

    def _log(self, stage, judge, meta, ans: AgentAnswer | None, failure: str | None) -> int:
        rec = {"stage": stage, "model": judge.model, **meta, "failure": failure}
        if ans is not None:
            rec |= {
                "calls": ans.calls,
                "tool_calls": ans.tool_calls,
                "budget": ans.budget,
                "usage": ans.usage,
                "usd": round(cost(judge.model, ans), 4),
                "sent": {
                    "read": ans.read_files,
                    "searches": ans.searches,
                    "matched": ans.matched_files,
                    "listed": ans.listed,
                    "refused": ans.refused,
                    "masked": ans.masked,
                },
            }
        with self._lock:
            rec["n"] = len(self.questions)
            self.questions.append(rec)
            return rec["n"]

    def answered(self, q: int, n: int, duties: tuple[E.Duty, ...], results: tuple[E.Result, ...] = ()) -> None:
        """질문 하나의 끝(관문을 건 뒤의 상태). 금액·시간·실패는 기록 `n` 에서 읽는다."""
        rec = self.questions[n]
        usd_ = rec.get("usd", 0.0)
        seconds = rec.get("seconds", 0.0)
        tools = rec.get("tool_calls", 0)
        self.emit(E.Answered(q, rec["stage"], usd_, seconds, rec.get("failure"), duties, results, tools))

    def checked(self, q: int, results: list[dict]) -> None:
        """질문 하나의 답(관문을 건 결과들)을 인용 대조 사건으로 낸다. 조건의 근거로 붙인 프로필 신호는 세지 않는다."""
        cites = [c for r in results for c in r.get("citations", []) if c.get("why") != "profile"]
        searches = [x for r in results for x in r.get("searches", [])]
        if not cites and not searches:
            return
        self.once("stage-gate", E.Stage("gate", "start"))
        ok_c = sum(1 for c in cites if c["ok"])
        self.emit(E.Checked(q, len(cites), ok_c, len(searches), sum(1 for x in searches if x["ok"])))


def duty_of(d: dict) -> E.Duty:
    return E.Duty(d["id"], d.get("law_short") or d["law"], d["article"], d["title"])


def first_cite(cs: list[dict]) -> str | None:
    c = next((c for c in cs if c.get("ok")), None)
    return f"{c['file']}:{c['line']}" if c and c.get("line") else (c["file"] if c else None)


# ── 1·2. 프로필과 이해 ───────────────────────────────────────────────


def _where(e: dict) -> str:
    return f"`{e['file']}`" + (f":{e['line']}" if e.get("line") else "") + f" ({e['what']})"


def _found_lines(prof: dict) -> str:
    rows = [f"- {f['id']} ({f['name']}): " + "; ".join(_where(e) for e in f["evidence"][:3]) for f in prof["features"]]
    return "\n".join(rows) or "- (없음)"


def _platforms(platforms: list[str]) -> str:
    return ", ".join(PLATFORM_KO[p] for p in platforms) or "알 수 없음(package.json 으로 가르지 못함)"


def platforms_of(prof: dict, und: dict) -> tuple[list[str], str]:
    """(플랫폼, 출처). 프로필이 package.json 으로 가른 것이 먼저다. 가르지 못했으면(JS·TS 가 없는 저장소) 이해 단계가
    인용과 함께 적은 것(관문 통과)을 쓴다."""
    if prof.get("platforms"):
        return list(prof["platforms"]), "signal"
    said_ = {p["platform"] for p in und.get("platforms") or []}
    found = [p for p in PLATFORM_KO if p in said_]
    return found, ("model" if found else "none")


def understand(run: Run, prof: dict, catalog: dict[str, str]) -> dict:
    budget = 40
    prompt = P.UNDERSTAND.format(
        found=_found_lines(prof),
        platforms=_platforms(prof.get("platforms", [])),
        catalog="\n".join(f"- {k}: {v}" for k, v in catalog.items()),
        budget=budget,
        cite=P.CITE,
        rules=P.RULES,
    )
    q = run.qid()
    doc, _, n = run.ask("understand", run.investigator, prompt, budget, {}, "summary", E.Asked(q, "understand"))
    out = _understood(run.root, doc, catalog)
    run.answered(q, n, ())
    return out


def _understood(root: Path, doc: dict | None, catalog: dict[str, str], reused: bool = False) -> dict:
    """이해 단계의 답(또는 앞 결과에서 되살린 같은 꼴)을 관문에 건다. 있다고 본 기능은 features(전에는 features_added)
    다. 신호가 찾은 기능을 확인한 것도 여기 온다(그 기능의 출처에 model 이 붙는다)."""
    out = {"summary": "", "added": [], "removed": [], "platforms": [], "nodes": [], "edges": []}
    out |= {"rejected_claims": 0, "answered": False, "reused": reused}
    if doc is None:
        return out
    out["answered"] = True
    out["summary"] = str(doc.get("summary") or "")[:800]
    for key, dest in (("features", "added"), ("features_added", "added"), ("features_removed", "removed")):
        for item in doc.get(key) or []:
            if not isinstance(item, dict) or item.get("feature") not in catalog:
                continue
            cs = check(root, P.citations_of(item))
            rec = {"feature": item["feature"], "reason": str(item.get("reason") or ""), "citations": cs}
            if grounded(cs):
                out[dest].append(rec)
            else:
                out["rejected_claims"] += 1
    for item in doc.get("platforms") or []:
        if not isinstance(item, dict) or item.get("platform") not in PLATFORM_KO:
            continue
        cs = check(root, P.citations_of(item))
        if grounded(cs):
            out["platforms"].append({"platform": item["platform"], "citations": cs})
        else:
            out["rejected_claims"] += 1
    flow = doc.get("flow") if isinstance(doc.get("flow"), dict) else {}
    kept: set[str] = set()
    for n in flow.get("nodes") or []:
        if not isinstance(n, dict) or not isinstance(n.get("id"), str):
            continue
        cs = check(root, P.citations_of(n))
        if not grounded(cs):
            out["rejected_claims"] += 1
            continue
        kind = n.get("kind") if n.get("kind") in ("input", "server", "store", "external") else "server"
        kept.add(n["id"])
        out["nodes"].append(
            {
                "id": n["id"],
                "kind": kind,
                "label": str(n.get("label") or "")[:80],
                "data": [str(x)[:40] for x in n.get("data") or []][:12],
                "citations": cs,
            }
        )
    for e in flow.get("edges") or []:
        if not isinstance(e, dict) or e.get("from") not in kept or e.get("to") not in kept:
            continue
        cs = check(root, P.citations_of(e))
        if not grounded(cs):
            out["rejected_claims"] += 1
            continue
        out["edges"].append(
            {"from": e["from"], "to": e["to"], "data": [str(x)[:40] for x in e.get("data") or []][:12], "citations": cs}
        )
    return out


def from_previous(root: Path, prev: dict, catalog: dict[str, str]) -> dict:
    """앞 review 결과(같은 저장소·커밋)의 이해 단계 결과를 되살린다. 인용은 지금 저장소에서 관문에 다시 건다."""
    prof = prev.get("profile") or {}
    flow = prev.get("data_flow") or {}
    doc = {
        "summary": prof.get("summary", ""),
        "features_added": [
            {"feature": f["id"], "citations": f.get("model_citations", []), "reason": f.get("model_reason", "")}
            for f in prof.get("features", [])
            if "model" in f.get("sources", [])
        ],
        "features_removed": [
            {"feature": f["id"], **f["removed"]} for f in prof.get("features", []) if isinstance(f.get("removed"), dict)
        ],
        "platforms": prof.get("platform_evidence", []),
        "flow": {"nodes": flow.get("nodes", []), "edges": flow.get("edges", [])},
    }
    return _understood(root, doc, catalog, reused=True)


def commit_of(root: Path) -> str | None:
    try:
        out = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() if out.returncode == 0 and out.stdout.strip() else None


# ── 3·4. 근거 찾기와 반박 ─────────────────────────────────────────────


def _evidence_lines(feature: dict | None) -> str:
    if not feature:
        return "- (거의 모든 서비스에 걸리는 의무다. 서비스 전체에서 찾는다)"
    rows = [f"- {_where(e)}" for e in feature["evidence"]]
    model = feature.get("model_citations", [])[:3]
    rows += [f"- `{c['file']}`:{c['line']} {c['text'][:120]} (이해 단계)" for c in model]
    return f"{feature['name']}\n" + "\n".join(rows)


def _budget(n: int, base: int, per: int, cap: int) -> int:
    return min(base + per * max(0, n - 1), cap)


def investigate(run: Run, group: list[dict], feature: dict | None, summary: str, platforms: str) -> dict[str, dict]:
    budget = _budget(len(group), 20, 3, 40)
    prompt = P.INVESTIGATE.format(
        summary=summary or "(이해 단계의 요약 없음)",
        platforms=platforms,
        evidence=_evidence_lines(feature),
        duties="\n".join(P.duty_block(d) for d in group),
        budget=budget,
        cite=P.CITE,
        search=P.SEARCH,
        condition=P.CONDITION,
        act=P.ACT,
        absence=P.ABSENCE,
        rules=P.RULES,
    )
    meta = {"feature": group[0]["feature"], "duties": [d["id"] for d in group]}
    q, duties = run.qid(), tuple(duty_of(d) for d in group)
    asked = E.Asked(q, "investigate", duties)
    doc, failure, qn = run.ask("investigate", run.investigator, prompt, budget, meta, "results", asked)
    results: dict[str, dict] = {}
    if failure in ("cost-cap", "time-cap") and doc is None and not run.questions[qn].get("calls"):
        results = {d["id"]: {"asked": False, "why": failure, "q": qn} for d in group}
    else:
        by_id = {d["id"]: d for d in group}
        for r in (doc or {}).get("results") or []:
            if not isinstance(r, dict) or r.get("duty") not in by_id or r.get("status") not in P.ANSWER:
                continue
            first = judge_first(run.root, by_id[r["duty"]], r, feature, run.lacks)
            results[r["duty"]] = {"asked": True, **first, "q": qn}
        for d in group:
            if d["id"] not in results:
                results[d["id"]] = {"asked": True, "why": failure or "no-answer", "q": qn}
    run.checked(q, list(results.values()))
    run.answered(q, qn, duties, tuple(_found(x.id, results[x.id]) for x in duties))
    return results


def _found(duty: str, r: dict) -> E.Result:
    """조사 뒤의 상태(관문을 건 것). 답이 없으면 unknown."""
    return E.Result(duty, r.get("status", "unknown"), first_cite(r.get("citations", [])))


def judge_first(root: Path, d: dict, r: dict, feature: dict | None, lacking: str | None) -> dict:
    """조사 답 하나(모델 JSON 의 results 한 칸)를 관문에 건다. 실행과, 저장된 답에 규칙만 다시 거는 일이 함께 쓴다."""
    answered = P.ANSWER[r["status"]]
    cs = check(root, P.citations_of(r))
    searches, proven = prove(root, P.searches_of(r))
    s = said(r)
    status, gate_ = accept(d, s, answered, cs, proven, feature, lacking)
    if (status == "seen-in-code" or (gate_ or {}).get("why") == "other-side") and not grounded(cs):
        cs = cs + _feature_citations(root, feature)  # 조건(기능)이 있다는 근거는 프로필 신호다
    reason = str(r.get("reason") or "")[:800]
    return {
        "status": status,
        "answered": answered,
        "citations": cs,
        "searches": searches,
        **s,
        "gate": gate_,
        "question": str(r.get("question") or "")[:400],
        "reason": f"{gate_['note']} {reason}".strip() if gate_ else reason,
    }


def judge_rebut(
    root: Path, d: dict, r: dict, f: dict, feature: dict | None, lacking: str | None, same_model: bool
) -> dict:
    """반박 답 하나를 관문에 건다. `f` 는 그 의무의 조사 답(judge_first 의 결과)이다.
    빼는 답을 깨면 '코드에서 본 것'(인용 필요). 확인할 것을 깨면 충족(행위 자체를 보이는 인용) 또는 해당 없음(걸리는
    조건이 없다는 답과 검색 증명)이다. 해당 없음은 조사 답과 같은 관문(absent)을 넘어야 받는다. 더해서
    - 자유 입력 추측으로 깨거나, 자유 입력 관문이 옮긴 항목을 그 정보를 받는 입력란·필드·저장의 인용(applies '예') 없이
      깨면 받지 않는다(free-input)
    - 금지 의무는 금지된 행위 자체나 그 빈틈의 인용(shows '금지 행위'·'빈틈', 관문 통과) 없이 깨지 못한다(prohibition)
    - 조사와 반박이 같은 모델이면 '충족'으로 올리지 못한다(same-model. 11/13 실측: 약관의 면책 한 줄로 AI 사전 고지를
      충족으로 올렸다)
    - 남은 부족한 점을 적은 '충족'은 받지 않는다(remaining-gap)"""
    cs = check(root, P.citations_of(r))
    searches, proven = prove(root, P.searches_of(r))
    s = said(r)
    rec = {
        "citations": cs,
        "searches": searches,
        **s,
        "gate": None,
        "off_quote": r.get("off_quote") is True,
        "reason": str(r.get("reason") or "")[:800],
    }
    before = f["status"]
    claimed = P.ANSWER.get(r.get("status") or "", "")
    if r["result"] == "유지" or (before in TO_CHECK and claimed not in ("evidence-found", "not-applicable")):
        return {"result": "upheld", **rec}
    to = claimed or "seen-in-code"
    guessed = (f.get("gate") or {}).get("why") == "free-input"
    proper = s["applies"] == "예" and s["trigger"] == "입력란·처리·저장" and grounded(cs)
    if before in DROPS and (free := guess(d, s, to, feature)):  # 자유 입력 추측으로는 빼는 답을 깨지 못한다
        free["note"] += " 뒤집기를 받지 않았습니다."
        rec["gate"], after, ok = free, to, False
    elif before in DROPS and guessed and not proper:  # 11/13 실측: 표시만 '입력란'으로 바꿔 다시 올렸다
        rec["gate"], after, ok = {"from": to, "why": "free-input", "note": GUESSED_NOTE}, to, False
    elif before in DROPS and d.get("prohibition") and not marked(s, cs):
        rec["gate"], after, ok = {"from": to, "why": "prohibition", "note": PROHIBITION_NOTE}, to, False
    elif before in DROPS:
        rec["gate"] = unknown(d, s, "seen-in-code", feature)
        after, ok = ("check-applicability" if rec["gate"] else "seen-in-code"), grounded(cs)
        after, rec["gate"] = other_side(d, after, rec["gate"], lacking, s, cs)
    elif claimed == "evidence-found" and same_model:
        rec["gate"] = {"from": claimed, "why": "same-model", "note": SAME_MODEL_NOTE}
        after, ok = claimed, False
    elif claimed == "evidence-found" and left(s):
        note = f"'충족'이라 하면서 남은 부족한 점을 적어 뒤집기를 받지 않았습니다: {s['remaining']}."
        rec["gate"], after, ok = {"from": claimed, "why": "remaining-gap", "note": note}, claimed, False
    elif claimed == "evidence-found":
        after, ok = claimed, grounded(cs) and s["shows"] == "행위"
    else:
        got, rec["gate"] = absent(d, s, proven, feature, grounded(cs))
        after, ok = claimed, got == "not-applicable"
    return {"result": "overturned" if ok else "overturn-ungrounded", "status": after, **rec}


def rebut(
    run: Run, group: list[dict], first: dict[str, dict], summary: str, platforms: str, feature: dict | None = None
) -> dict[str, dict]:
    items = [d for d in group if first.get(d["id"], {}).get("status") in (*DROPS, *TO_CHECK)]
    if not items or not run.limits.rebut:
        if run.limits.rebut:
            run.emit(E.Planned(-1))  # 이 묶음은 반박을 묻지 않는다
        return {d["id"]: {"result": "not-run", "why": "rebut-off"} for d in items}
    out: dict[str, dict] = {}
    if run.limits.rebut_scope == "found":
        # 코드에서 본 것과 충족 근거 있음만 반박한다. 저장소 밖, 해당 없음, 걸리지 않는 것으로 보임은 묻지 않는다
        out = {
            d["id"]: {"result": "not-run", "why": "rebut-scope"} for d in items if first[d["id"]]["status"] not in FOUND
        }
        items = [d for d in items if d["id"] not in out]
        if not items:
            run.emit(E.Planned(-1))
            return out
    budget = _budget(len(items), 15, 3, 35)
    blocks = []
    for d in items:
        f = first[d["id"]]
        ok = [c for c in f["citations"] if c["ok"]]
        blocks.append(
            P.duty_block(d)
            + f"\n  앞 판단: {P.SAID[f['status']]} — {f['reason']}"
            + (f"\n  앞 판단의 걸리는 조건: {f['condition']} ({f['applies'] or '?'})" if f.get("condition") else "")
            + (f"\n  앞 판단이 적은 없는 것: {f['missing']}" if f.get("missing") else "")
            + (f"\n  앞 인용: {P.cite_lines(ok)}" if ok else "")
            + (f"\n  앞 검색: {P.search_lines(f['searches'])}" if f["searches"] else "")
            + (GUESSED_HINT if (f.get("gate") or {}).get("why") == "free-input" else "")
        )
    prompt = P.REBUT.format(
        summary=summary or "(요약 없음)",
        platforms=platforms,
        items="\n".join(blocks),
        budget=budget,
        cite=P.CITE,
        search=P.SEARCH,
        condition=P.CONDITION,
        act=P.ACT,
        absence=P.ABSENCE,
        rules=P.RULES,
    )
    meta = {"feature": group[0]["feature"], "duties": [d["id"] for d in items]}
    q, duties = run.qid(), tuple(duty_of(d) for d in items)
    doc, failure, qn = run.ask("rebut", run.checker, prompt, budget, meta, "results", E.Asked(q, "rebut", duties))
    if failure in ("cost-cap", "time-cap") and doc is None and not run.questions[qn].get("calls"):
        out |= {d["id"]: {"result": "not-run", "why": failure, "q": qn} for d in items}
    else:
        by_id = {d["id"]: d for d in items}
        same = run.investigator.model == run.checker.model
        for r in (doc or {}).get("results") or []:
            if not isinstance(r, dict) or r.get("duty") not in by_id or r.get("result") not in ("유지", "뒤집음"):
                continue
            d = by_id[r["duty"]]
            out[r["duty"]] = {**judge_rebut(run.root, d, r, first[r["duty"]], feature, run.lacks, same), "q": qn}
        for d in items:
            out.setdefault(d["id"], {"result": "not-run", "why": failure or "no-answer", "q": qn})
    run.checked(q, [out[d["id"]] for d in items])
    run.answered(q, qn, duties, tuple(_rebutted(x, out[x.id], first[x.id]) for x in duties))
    return out


def _rebutted(x: E.Duty, r: dict, f: dict) -> E.Result:
    """반박 뒤의 상태: 뒤집었으면 반박의 상태, 아니면 조사 답의 상태."""
    turned = r["result"] == "overturned"
    status = r["status"] if turned else f["status"]
    return E.Result(x.id, status, first_cite(r["citations"] if turned else f["citations"]), r["result"])


def _base(d: dict) -> dict:
    out = {
        "duty": d["id"],
        "feature": d["feature"],
        "law": d["law"],
        "article": d["article"],
        "title": d["title"],
        "duty_text": d["duty"],
        "url": d["url"],
        "quote": d["quote"],
    }
    return with_sanction(out)


def feature_counts(features: list[dict]) -> dict[str, int]:
    """기능 파악이 한 일(진행 화면): 남은 기능 수, 신호로 잡힌 수, AI 가 뺀 수·더한 수.
    기능 목록(select 의 첫 값, 결과의 profile.features)에서 센다. 기록 재생도 같은 것을 쓴다."""
    src = [set(f.get("sources", [])) for f in features]
    return {
        "features": sum(1 for f in features if "removed" not in f),
        "signals": sum(1 for s in src if "signal" in s),
        "removed": sum(1 for f in features if "removed" in f),
        "added": sum(1 for s in src if "model" in s and "signal" not in s),
    }


def with_sanction(item: dict) -> dict:
    """체크리스트 항목에 의무별 제재(profile/sanctions.jsonl 의 레코드에서 duty 를 뺀 것)를 붙인다. 표에 없는 의무나
    이미 붙은 항목은 그대로다."""
    s = load_sanctions().get(item.get("duty", ""))
    if s is not None and "sanction" not in item:
        item["sanction"] = copy.deepcopy(s)
    return item


def with_tables(item: dict, duties: dict[str, dict] | None = None) -> dict:
    """기록 재생: 화면에 쓰는 글(제재, 조문 표기)을 지금의 표 값으로 덮어쓴다. 결과 파일에는 그때의 글이 남아 있어
    표를 고친 뒤(11/24: '시정명령을 어기면' → '시정명령 불이행 시', '시행령 시행령')에도 옛 글이 나왔다. 표에 없는
    의무는 파일 값 그대로다. 판정과 인용은 건드리지 않는다. `duties` 는 의무 id → 의무 표의 줄."""
    did = item.get("duty", "")
    s = load_sanctions().get(did)
    if s is not None:
        item["sanction"] = copy.deepcopy(s)
    row = (duties if duties is not None else {d["id"]: d for d in load_duties()}).get(did)
    if row and row.get("article"):
        item["article"] = row["article"]
    return item


def _goods_item(d: dict, g: dict) -> dict:
    """품목 신호가 없어 묻지 않은 품목 의무. '해당 여부부터 확인할 것'의 맨 뒤에 한 묶음(group: goods)으로 싣는다."""
    return {
        **_base(d),
        "status": "check-applicability",
        "asked": False,
        "not_answered": "goods-not-detected",
        "group": "goods",
        "first": None,
        "verification": {"result": "not-run", "why": "goods-not-detected"},
        "citations": [],
        "searches": [],
        "question": f"{g['name']}도 판매하나요? 판매한다면 이 의무가 걸립니다.",
        "reason": f"{g['name']} 판매에만 걸리는 의무입니다. 코드에서 이 품목의 신호를 찾지 못해 묻지 않았습니다.",
    }


def _not_generative_item(d: dict) -> dict:
    """생성형 AI 신호가 없어 묻지 않은 AI 사전 고지·결과물 표시. '해당 여부부터 확인할 것'에 싣는다."""
    return {
        **_base(d),
        "status": "check-applicability",
        "asked": False,
        "not_answered": "not-generative",
        "first": None,
        "verification": {"result": "not-run", "why": "not-generative"},
        "citations": [],
        "searches": [],
        "question": "이 서비스의 AI 가 글·이미지·음성을 만들어 내는 생성형 AI 이거나 고영향 AI 인가요? "
        "그렇다면 이 의무가 걸립니다.",
        "reason": "AI 기능은 있지만 생성형 AI 를 부르는 신호(꾸러미·호출·주소)를 찾지 못해 묻지 않았습니다.",
    }


def _item(d: dict, first: dict, check_: dict | None) -> dict:
    base = _base(d)
    if not first.get("asked") or "status" not in first:
        why = first.get("why") or "no-answer"
        return {
            **base,
            "status": "unknown",
            "asked": bool(first.get("asked")),
            "not_answered": why,
            "first": None,
            "verification": {"result": "not-run", "why": why},
            "citations": [],
            "searches": [],
            "question": "",
            "reason": NOT_ANSWERED.get(why, "답을 받지 못했습니다"),
        }
    status, citations, searches = first["status"], first["citations"], first["searches"]
    why = "business-judgment" if status == "check-applicability" else "no-answer"
    verification = {"result": "not-run", "why": why}
    overturned = bool(check_) and check_["result"] == "overturned"
    if check_:
        verification = {k: v for k, v in check_.items() if k != "q"}
        if overturned:
            status, citations, searches = check_["status"], check_["citations"], check_["searches"]
    return {
        **base,
        "status": status,
        "asked": True,
        "first": {k: first[k] for k in FIRST_KEYS},
        "verification": verification,
        "citations": citations,
        "searches": searches,
        "missing": verification.get("missing", "") if overturned else (first["missing"] or _left_of(first)),
        "question": first["question"],
        "reason": first["reason"] if status == first["status"] else verification.get("reason", ""),
    }


def _left_of(first: dict) -> str:
    """'충족'이라 하면서 적은 남은 부족한 점으로 '코드에서 본 것'이 된 항목의 없는 것."""
    return first.get("remaining", "") if (first.get("gate") or {}).get("why") == "remaining-gap" else ""


def arrange(checklist: list[dict]) -> list[dict]:
    """갈래 순(prompts.ORDER), 그 안에서는 묻지 않은 품목 묶음이 맨 뒤, 그 앞은 PRIORITY·기능 목록 순, 기능 안에서는
    핵심 의무 순(core_key). rank·status_label 을 붙인다."""
    feats = [*PRIORITY, *(f["id"] for f in load_features()["features"] if f["id"] not in PRIORITY)]
    pos = {f: i for i, f in enumerate(feats)}
    rows = {d["id"]: d for d in load_duties()}

    def key(c: dict) -> tuple:
        row = rows.get(c["duty"])
        core = core_key(row) if row else (False, True, True, 0, True, c["duty"])
        return (P.ORDER.index(c["status"]), c.get("group") == "goods", pos.get(c["feature"], 99), *core)

    out = sorted(checklist, key=key)
    for i, c in enumerate(out, 1):
        c["rank"], c["status_label"] = i, P.STATUS_LABEL[c["status"]]
    return out


# ── 전체 ─────────────────────────────────────────────────────────────


def _blank(fid: str, name: str) -> dict:
    return {"id": fid, "name": name, "sources": [], "evidence": [], "evidence_total": 0, "model_citations": []}


def select(prof: dict, und: dict) -> tuple[list[dict], ...]:
    """(기능 목록, 목록 층 의무, 검토 층 의무, 묻지 않는 의무). 기능은 신호 + 이해 단계가 더한 것 − 뺀 것. 검토 층은
    묻는 순서다(PRIORITY·기능 목록 순, 기능 안에서는 core_key). 품목 의무는 프로필에 그
    품목 신호가 있을 때만 묻는다. 묻지 않는 의무는 품목 의무와, 생성형 AI 기능 없이 분류·인식 모델(ai-model)만 있을 때의
    AI 사전 고지·결과물 표시다."""
    spec = load_features()
    names = {f["id"]: f["name"] for f in spec["features"]}
    duties = load_duties()
    by_id = {d["id"]: d for d in duties}
    removed = {r["feature"]: r for r in und["removed"]}
    features: dict[str, dict] = {}
    for f in prof["features"]:
        features[f["id"]] = {
            "id": f["id"],
            "name": f["name"],
            "sources": ["signal"],
            "evidence": f["evidence"],
            "evidence_total": f["evidence_total"],
            "model_citations": [],
        }
    for a in und["added"]:
        f = features.setdefault(a["feature"], _blank(a["feature"], names[a["feature"]]))
        if "model" not in f["sources"]:
            f["sources"].append("model")
        f["model_citations"] += [c for c in a["citations"] if c["ok"]]
        f["model_reason"] = a["reason"]
    for fid in list(features):
        if fid in removed and features[fid]["sources"] == ["signal"]:
            features[fid]["removed"] = {"reason": removed[fid]["reason"], "citations": removed[fid]["citations"]}
    live = [f for f in features.values() if "removed" not in f]
    service = [f for f in live if f["id"] not in ("web-ui", "mobile-app")]
    ids = {f["id"] for f in live} | ({"common"} if service else set())
    listed = [d for d in duties if d["feature"] in ids]
    order = {fid: i for i, fid in enumerate(PRIORITY)}
    rest = {f["id"]: len(PRIORITY) + i for i, f in enumerate(spec["features"])}
    # 의무 표의 krcore 는 옛 정책 팩이 다루던 의무 8개다. 검토 후보(review_candidate)가 아닌 둘(pipa-26-2,
    # pipa-28-8-1)도 묻는다(묻는 의무 220개, 제재 표와 1:1)
    review = [d for d in listed if d["review_candidate"] or d.get("krcore")]
    goods, seen = _goods(), {g["id"] for g in prof.get("goods") or []}
    skipped = [d for d in review if d["id"] in goods and goods[d["id"]]["id"] not in seen]
    review = [d for d in review if d not in skipped]
    if not _present(features.get("genai")) and "ai-model" in {f["id"] for f in live}:
        # 분류·인식 모델만 있으면 AI 사전 고지·결과물 표시는 묻지 않고 해당 여부다. 생성형 AI 기능이 있으면(신호가
        # 프로필에 없어도) 묻고 조사 답을 따른다(_always)
        held = [by_id[d] for d in _generative()]
        listed += [d for d in held if d not in listed]
        skipped += held
    review.sort(key=lambda d: (order.get(d["feature"], rest.get(d["feature"], 99)), *core_key(d)))
    return list(features.values()), listed, review, skipped


def groups_of(review: list[dict], batch: str) -> list[list[dict]]:
    """질문 하나에 넣는 의무들. duty 는 하나씩, feature 는 기능마다(GROUP_MAX 까지), bundle 은 표의 묶음마다(묶음은
    첫 의무의 자리에서 묻는다. 표에 없는 의무는 하나씩)."""
    if batch == "duty":
        return [[d] for d in review]
    out: list[list[dict]] = []
    if batch == "bundle":
        of, at = _bundles(), {}
        for d in review:
            b = of.get(d["id"])
            if b is None:
                out.append([d])
            elif b in at:
                out[at[b]].append(d)
            else:
                at[b] = len(out)
                out.append([d])
        return out
    for d in review:
        if out and out[-1][0]["feature"] == d["feature"] and len(out[-1]) < GROUP_MAX:
            out[-1].append(d)
        else:
            out.append([d])
    return out


def parallel(fn: Callable, items: list, workers: int) -> list:
    """`items` 마다 `fn` 을 동시에 `workers` 개까지 돌려 순서대로 결과를 낸다(pool.map 과 같다). 일꾼은 데몬 스레드다:
    Ctrl+C·오류로 멈추면 남은 일은 꺼내지 않고, 대화 중인 요청을 기다리지 않고 끝난다(ThreadPoolExecutor 는 끝날 때
    남은 일과 진행 중인 요청을 모두 기다려 Ctrl+C 뒤에도 질문을 더 보냈다). 일 하나가 예외를 내면 그 예외를 낸다."""
    todo: queue.SimpleQueue = queue.SimpleQueue()
    for i, x in enumerate(items):
        todo.put((i, x))
    out: dict[int, tuple[bool, object]] = {}
    cv = threading.Condition()

    def worker() -> None:
        while True:
            try:
                i, x = todo.get_nowait()
            except queue.Empty:
                return
            try:
                r = (True, fn(x))
            except BaseException as e:  # noqa: BLE001 — 주 스레드에서 다시 낸다
                r = (False, e)
            with cv:
                out[i] = r
                cv.notify_all()

    for _ in range(min(max(1, workers), len(items))):
        threading.Thread(target=worker, daemon=True).start()
    results = []
    try:
        for i in range(len(items)):
            with cv:
                while i not in out:
                    cv.wait()
                ok, r = out.pop(i)
            if not ok:
                raise r
            results.append(r)
    finally:
        while True:  # 멈출 때 남은 일을 비운다(일꾼은 지금 일만 끝내고 나간다)
            try:
                todo.get_nowait()
            except queue.Empty:
                break
    return results


def plan(root: Path) -> dict:
    """모델을 부르지 않고 무엇을 물을지만 센다(비용 어림용)."""
    root = root.resolve()
    prof = profile(root)
    empty = {"summary": "", "added": [], "removed": []}
    features, listed, review, skipped = select(prof, empty)
    return {
        "features": [f["id"] for f in features],
        "listed": len(listed),
        "review": len(review),
        "goods_not_asked": sum(d["id"] in _goods() for d in skipped),
        "not_generative": sum(d["id"] not in _goods() for d in skipped),
        "questions": {b: len(groups_of(review, b)) for b in ("feature", "bundle", "duty")},
    }


def review(
    root: Path,
    investigator: AgentJudge,
    checker: AgentJudge,
    limits: Limits | None = None,
    throttles: tuple[Throttle, ...] = (),
    reuse: dict | None = None,
    progress: E.Sink = E.ignore,
) -> dict:
    """`reuse` 는 같은 저장소·커밋의 앞 review 결과다. 주면 이해 단계를 묻지 않고 그 결과를 쓴다. `progress` 는 진행
    사건(review/events)을 받는다. 사건은 결과에 영향을 주지 않는다."""
    limits = limits or Limits()
    root = root.resolve()
    t0 = time.monotonic()
    for j in (investigator, checker):
        j.deadline = t0 + limits.seconds
    run = Run(root, investigator, checker, limits, Spend(limits.usd), t0=t0, emit=progress)
    for t in throttles:
        t.listener = progress

    progress(E.Stage("profile", "start"))
    prof = profile(root)
    progress(E.Stage("profile", "end", {"features": len(prof["features"]), "platforms": prof.get("platforms", [])}))
    catalog = {f["id"]: f["name"] for f in load_features()["features"]}
    if reuse is not None:
        und = from_previous(root, reuse, catalog)
    else:
        progress(E.Stage("understand", "start"))
        progress(E.Planned(1))
        und = understand(run, prof, catalog)
    platforms, run.platforms_from = platforms_of(prof, und)
    run.lacks = lacks(root, platforms)
    features, listed, review_duties, skipped = select(prof, und)
    by_feature = {f["id"]: f for f in features}
    groups = groups_of(review_duties, limits.batch)
    plats = _platforms(platforms)
    detail = {**feature_counts(features), "nodes": len(und["nodes"]), "edges": len(und["edges"])}
    detail["answered"] = und["answered"]
    progress(E.Stage("understand", "skip" if reuse is not None else "end", {**detail, "why": "reused"}))

    lock, done = threading.Lock(), [0]

    def work(group: list[dict]) -> tuple[dict, dict]:
        feature = by_feature.get(group[0]["feature"])
        first = investigate(run, group, feature, und["summary"], plats)
        with lock:
            done[0] += 1
            last = done[0] == len(groups)
        if last:
            progress(E.Stage("investigate", "end"))
        return first, rebut(run, group, first, und["summary"], plats, feature)

    firsts: dict[str, dict] = {}
    checks: dict[str, dict] = {}
    if groups:
        progress(E.Planned(len(groups) * (2 if limits.rebut else 1)))
        progress(E.Stage("investigate", "start", {"questions": len(groups), "duties": len(review_duties)}))
    else:
        progress(E.Stage("investigate", "skip", {"why": "nothing"}))
    if not limits.rebut:
        progress(E.Stage("rebut", "skip", {"why": "off"}))
    try:
        for first, chk in parallel(work, groups, limits.concurrency):
            firsts |= first
            checks |= chk
    except BaseException:
        run.halt()
        raise
    for stage in ("rebut", "gate"):
        if f"stage-{stage}" in run._once:
            progress(E.Stage(stage, "end"))
        elif stage == "gate" or limits.rebut:
            progress(E.Stage(stage, "skip", {"why": "nothing"}))

    goods = _goods()
    checklist = arrange(
        [_item(d, firsts.get(d["id"], {}), checks.get(d["id"])) for d in review_duties]
        + [_goods_item(d, goods[d["id"]]) if d["id"] in goods else _not_generative_item(d) for d in skipped]
    )
    seconds = time.monotonic() - t0
    prof = {**prof, "platforms": platforms}
    return _report(run, prof, und, features, listed, checklist, seconds, throttles)


def _report(run: Run, prof, und, features, listed, checklist, seconds, throttles) -> dict:
    in_checklist = {c["duty"] for c in checklist}
    # 모델이 댄 인용만 센다(조건의 근거로 붙인 프로필 신호 why: profile 은 빼고)
    cites = [c for q in checklist for c in (q["first"] or {}).get("citations", []) if c["why"] != "profile"]
    searches = [s for q in checklist for s in (q["first"] or {}).get("searches", [])]
    searches += [s for q in checklist for s in q["verification"].get("searches", [])]
    cites += [c for q in checklist for c in q["verification"].get("citations", [])]
    for part in ("platforms", "nodes", "edges"):
        cites += [c for x in und[part] for c in x["citations"]]
    masked: dict[str, int] = {}
    refused: set[str] = set()
    for q in run.questions:
        for k, v in (q.get("sent") or {}).get("masked", {}).items():
            masked[k] = masked.get(k, 0) + v
        refused |= set((q.get("sent") or {}).get("refused", []))
    counts = {s: sum(1 for c in checklist if c["status"] == s) for s in P.ORDER}
    verdicts: dict[str, int] = {}
    for c in checklist:
        verdicts[c["verification"]["result"]] = verdicts.get(c["verification"]["result"], 0) + 1
    not_asked: dict[str, int] = {}
    for c in checklist:
        if c["status"] == "unknown" and c.get("not_answered"):
            not_asked[c["not_answered"]] = not_asked.get(c["not_answered"], 0) + 1
    return {
        "review_version": REVIEW_VERSION,
        "tool": {"name": "policyofficer", "version": __version__},
        "summary": {
            "counts": counts,
            "labels": P.STATUS_LABEL,
            "top": [c["duty"] for c in checklist[:5]],
            "groups": [
                {"id": "goods", "label": GOODS_LABEL, "status": "check-applicability", "duties": goods}
                for goods in [[c["duty"] for c in checklist if c.get("group") == "goods"]]
                if goods
            ],
        },
        "profile": {
            "commit": commit_of(run.root),
            "platforms": prof["platforms"],
            # signal: package.json 으로 가름, model: 가르지 못해 이해 단계가 인용과 함께 적은 것(platform_evidence),
            # none: 둘 다 없음
            "platforms_from": run.platforms_from,
            "platform_evidence": und["platforms"],
            "summary": und["summary"],
            "features": features,
            "test_only": prof["test_only"],
            "goods": prof.get("goods", []),
            "files": prof["files"],
        },
        "data_flow": {"nodes": und["nodes"], "edges": und["edges"]},
        "obligations": {
            "listed": [
                {
                    "id": d["id"],
                    "feature": d["feature"],
                    "law": d["law"],
                    "article": d["article"],
                    "title": d["title"],
                    "duty": d["duty"],
                    "url": d["url"],
                    "in_checklist": d["id"] in in_checklist,
                }
                for d in listed
            ],
            "status_only": sum(1 for d in load_duties() if d["feature"] == "status"),
        },
        "checklist": checklist,
        "run": {
            "models": {
                "investigate": run.investigator.model,
                "verify": run.checker.model if run.limits.rebut else "none",
            },
            "rebut": run.limits.rebut,
            "rebut_scope": run.limits.rebut_scope,
            "batch": run.limits.batch,
            # 저장소에 없는 쪽(screen: 서버만, server: 화면만). 그쪽 의무의 '코드에서 본 것'은 '저장소 밖'으로 옮긴다
            "lacks": run.lacks,
            "limits": {"usd": run.limits.usd, "seconds": run.limits.seconds, "concurrency": run.limits.concurrency},
            "seconds": round(seconds, 1),
            "calls": sum(q.get("calls", 0) for q in run.questions),
            "usage": run.spend.usage,
            "usd_estimate": round(run.spend.usd, 4),
            # 동시 요청 수. 429 를 받을 때마다 반으로 줄였다(판정기마다 하나)
            "concurrency": [{"start": t.start, "end": t.limit, "rate_limited": t.rate_limited} for t in throttles],
            "status_counts": counts,
            "verification_counts": verdicts,
            "citations": len(cites),
            "citations_rejected": sum(1 for c in cites if not c["ok"]),
            # 부재 주장의 검색. 관문이 다시 돌려 줄 수가 다른 것(mismatch 등)이 rejected 다
            "searches": len(searches),
            "searches_rejected": sum(1 for s in searches if not s["ok"]),
            "understanding": {
                "answered": und["answered"],
                "rejected_claims": und["rejected_claims"],
                "reused": und["reused"],
            },
            "not_asked": not_asked,
            "masked": masked,
            "refused": sorted(refused),
            "questions": run.questions,
        },
    }


def build_judge(spec: str, throttle: Throttle, env: dict | None = None) -> AgentJudge:
    """`anthropic:<모델>` → 동시 요청 수를 `throttle` 로 묶은 에이전트 판정기. 키는 ANTHROPIC_API_KEY 에서 읽는다."""
    import os

    from policyofficer.judge.http import http_transport

    kind, _, model = spec.partition(":")
    if kind != "anthropic" or not model:
        raise ValueError(f"판정기를 알 수 없습니다: {spec!r} (예: anthropic:claude-haiku-5-5)")
    key = (env if env is not None else os.environ).get("ANTHROPIC_API_KEY")
    if not key:
        raise ValueError("ANTHROPIC_API_KEY 가 없습니다")
    return AgentJudge(MODELS.get(model, model), throttle.wrap(http_transport(key, on_retry=throttle.saw)))
