"""review·replay 의 진행 표시. review 가 내는 사건(review/events)을 받아 stderr 에 그린다. 계산 코드와 섞지 않는다.

표시기 셋을 자동으로 고른다(`--progress auto`, docker build 와 같은 이름).
  tty    stderr 가 터미널이고, CI 가 아니고(CI 가 비어 있지 않고 false·0 이 아니면 CI), TERM 이 dumb 가 아닐 때. 진행
         영역을 제자리에서 다시 그린다(초당 10번 이하): 단계 목록(✓ 끝남 ● 진행 중 ○ 남음), 진행 중인 질문(동시
         질문 수만큼, 지금 읽는 파일·검색어), 끝난 질문의 수, 맨 아래 경과 시간·어림 금액·질문 k/N. 끝나면 진행
         영역을 지우고, 숨긴 커서는 어떻게 끝나든(정상, 오류, Ctrl+C) 되살린다.
  plain  그 밖의 모든 경우(CI, 웹 실행기, 파일로 받는 stderr). ANSI 제어 문자를 하나도 쓰지 않는다. 사건마다
         `[mm:ss] …` 한 줄. 질문 안의 도구 호출은 줄로 내지 않고 질문 끝 줄에 수만 적는다(웹 실행기는 stderr 의 끝
         2,000자만 남긴다).
  none   그리지 않는다. 코드가 나가는 곳 알림 한 줄만 전처럼 낸다.
NO_COLOR 가 있으면 색(SGR)만 끈다(report/text.py 와 같은 규칙). 뜻은 색만으로 전하지 않고 기호와 글자를 함께 쓴다.
한글은 두 칸(east_asian_width W·F), 결합 문자는 0칸으로 세어 터미널 폭(프레임마다 다시 읽음)을 넘는 줄은 "…"로 줄인다.
출력 인코딩이 UTF-8 이 아니면 ASCII 기호를 쓴다. 저장소에서 온 글(경로·검색어)의 제어 문자는 '?'로 바꿔 터미널에 그대로
보내지 않는다.
"""

from __future__ import annotations

import os
import re
import shutil
import threading
import time
import unicodedata
from collections import Counter
from contextlib import suppress

from policyofficer.review import events as E
from policyofficer.review.prompts import ORDER

MODES = ("auto", "tty", "plain", "none")
FPS = 10
SHORT = {
    "seen-in-code": "코드에서 본 것",
    "check-outside": "저장소 밖",
    "check-applicability": "해당 여부",
    "unknown": "모름",
    "evidence-found": "충족 근거",
    "likely-not-applicable": "걸리지 않는 듯",
    "not-applicable": "해당 없음",
}
VERDICT = {"upheld": "유지", "overturned": "뒤집음", "overturn-ungrounded": "뒤집기 안 받음", "not-run": "묻지 못함"}
DOING = {"read_file": "읽는 중", "search": "검색", "list_files": "목록"}
PLATFORM = {"web": "웹", "mobile": "모바일 앱", "server": "서버"}
PLAIN_LABEL, PLAIN_PATH = 60, 50
"""plain 한 줄에 싣는 법·조문·제목과 인용 경로의 폭. 로그 한 줄을 짧게 둔다."""


# ── 환경 ─────────────────────────────────────────────────────────────


def ci(env: dict | None = None) -> bool:
    """CI 변수가 비어 있지 않고 false·0 이 아니다(GitHub Actions·GitLab 은 true)."""
    return (os.environ if env is None else env).get("CI", "").strip().lower() not in ("", "false", "0")


def choose(mode: str, stream, env: dict | None = None) -> str:
    """auto 면 tty·plain 중 하나. 그 밖의 값은 그대로(덮어쓰기)."""
    if mode != "auto":
        return mode
    env = os.environ if env is None else env
    tty = bool(getattr(stream, "isatty", lambda: False)())
    return "tty" if tty and not ci(env) and env.get("TERM") != "dumb" else "plain"


def color(env: dict | None = None) -> bool:
    return not (os.environ if env is None else env).get("NO_COLOR")


def utf8(stream) -> bool:
    """출력 인코딩이 UTF-8 인가. 인코딩이 없는 글 스트림(StringIO)은 글자를 그대로 받으니 그렇다고 본다."""
    enc = getattr(stream, "encoding", None)
    return enc is None or enc.lower().replace("-", "").replace("_", "") in ("utf8", "utf8sig")


def size(stream) -> tuple[int, int]:
    """(칸, 줄). COLUMNS·LINES 가 있으면 그 값, 아니면 그 스트림의 터미널, 아니면 shutil.get_terminal_size(80×24).
    shutil 은 stdout 의 터미널을 재서, stdout 을 파이프로 받는 `review . | jq` 에서 stderr 의 폭을 모른다."""
    try:
        own = os.get_terminal_size(stream.fileno())
        cols, rows = own.columns, own.lines
    except (AttributeError, ValueError, OSError):
        cols, rows = shutil.get_terminal_size((80, 24))

    def env(name: str) -> int:
        v = os.environ.get(name, "")
        return int(v) if v.isdigit() else 0

    return env("COLUMNS") or cols or 80, env("LINES") or rows or 24


# ── 글자 폭 ──────────────────────────────────────────────────────────

_BIDI = re.compile("[‪-‮⁦-⁩]")


def clean(s: object) -> str:
    """제어 문자(ESC 포함)와 방향 바꾸기 문자는 '?'. 저장소의 파일 이름이나 모델이 낸 검색어가 터미널을 조작하지
    못하게 한다. 한글은 NFC 로 모은다(macOS 경로의 NFD 자모는 폭을 잘못 센다)."""
    s = unicodedata.normalize("NFC", str(s))
    return _BIDI.sub("?", "".join("?" if unicodedata.category(c) == "Cc" else c for c in s))


def cells(ch: str) -> int:
    if unicodedata.combining(ch) or unicodedata.category(ch) in ("Mn", "Me", "Cf"):
        return 0
    return 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1


def width(s: str) -> int:
    return sum(cells(c) for c in unicodedata.normalize("NFC", s))


def fit(s: str, w: int, more: str = "…") -> str:
    """폭 `w` 안으로. 넘치면 뒤를 잘라 `more` 를 붙인다."""
    s = unicodedata.normalize("NFC", s)
    if width(s) <= w:
        return s
    lim, out, used = w - width(more), [], 0
    if lim < 0:
        return ""
    for c in s:
        if used + cells(c) > lim:
            break
        out.append(c)
        used += cells(c)
    return "".join(out) + more


def fit_tail(s: str, w: int, more: str = "…") -> str:
    """폭 `w` 안으로. 넘치면 앞을 잘라 끝(파일 이름)을 남긴다."""
    s = unicodedata.normalize("NFC", s)
    if width(s) <= w:
        return s
    lim, out, used = w - width(more), [], 0
    if lim < 0:
        return ""
    for c in reversed(s):
        if used + cells(c) > lim:
            break
        out.append(c)
        used += cells(c)
    return more + "".join(reversed(out))


def pad(s: str, w: int) -> str:
    return s + " " * max(0, w - width(s))


def wrap(s: str, w: int) -> list[str]:
    """빈칸에서 줄을 나눠 폭 `w` 안으로(낱말 하나가 넘치면 그 낱말을 자른다)."""
    out, cur = [], ""
    for word in s.split(" "):
        nxt = f"{cur} {word}" if cur else word
        if width(nxt) <= w:
            cur = nxt
            continue
        if cur:
            out.append(cur)
        cur = fit(word, w)
    return [*out, cur] if cur else out


# ── 글 ───────────────────────────────────────────────────────────────


class Glyphs:
    UNICODE = {"done": "✓", "run": "●", "todo": "○", "fail": "✗", "skip": "–", "dot": "·", "more": "…", "stop": "■"}
    ASCII = {"done": "v", "run": "*", "todo": "o", "fail": "x", "skip": "-", "dot": "|", "more": "...", "stop": "#"}

    def __init__(self, unicode: bool) -> None:
        for k, v in (self.UNICODE if unicode else self.ASCII).items():
            setattr(self, k, v)


def dot_sep(g: Glyphs) -> str:
    return f" {g.dot} "


SGR = {"bold": "1", "dim": "2", "ok": "32", "run": "36", "warn": "33", "fail": "31", "heavy": "1;31"}


def clock(seconds: float) -> str:
    s = max(0, int(seconds))
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60}:{s % 60:02d}"


def model_name(spec: str | None) -> str:
    return (spec or "").removeprefix("anthropic:")


_MODEL = re.compile(r"claude-([a-z]+)-(\d+)(?:-(\d{1,2}))?(?:-\d{8})?")


def model_label(spec: str | None) -> str:
    """머리에 쓰는 모델 이름: 'anthropic:claude-haiku-5-5' → 'Claude Haiku 5.5'. 반박 범위 꼬리('(found)')는 뗀다.
    모르는 모양은 그대로."""
    name = re.sub(r"\(.*\)$", "", model_name(spec)).strip()
    m = _MODEL.fullmatch(name)
    if not m:
        return name
    family, major, minor = m.groups()
    return f"Claude {family.capitalize()} {major}" + (f".{minor}" if minor else "")


def repo_label(repo: str) -> str:
    """머리의 저장소 이름. 평가용 복제의 '소유자__저장소' 에서 소유자를 뗀다(GitHub 소유자 이름에는 '_' 가 없다)."""
    return re.sub(r"^[A-Za-z0-9-]+__(?=.)", "", repo)


def host(egress: str) -> str:
    """코드가 나가는 곳의 호스트(머리 한 줄). 주소로 읽지 못하면 받은 값 그대로."""
    from urllib.parse import urlsplit

    try:
        netloc = urlsplit(egress).netloc
    except ValueError:
        return egress
    return netloc.rsplit("@", 1)[-1] or egress


_RE_DROP = [
    (re.compile(r"\(\?[a-zA-Z]+\)|\(\?(?:[:=!]|<[=!]|P?<\w+>)"), ""),  # (?i) (?: (?= (?<name>
    (re.compile(r"\[[^\]]*\]"), " "),  # 문자 묶음 [A-Z_]
    (re.compile(r"\{\d*,?\d*\}"), ""),  # {2,3}
]


def search_words(pattern: str) -> list[str]:
    """검색 정규식을 사람이 읽는 낱말로: '|' 로 나누고 정규식 기호를 뗀다(같은 낱말은 한 번). 이스케이프한 글자
    ('\\.', '\\(')는 그 글자로, '\\b'·'\\s' 같은 것과 아무 글자 '.' 는 빈칸으로."""
    out: list[str] = []
    for part in re.split(r"(?<!\\)\|", pattern):
        for rx, to in _RE_DROP:
            part = rx.sub(to, part)
        buf, i = [], 0
        while i < len(part):
            ch = part[i]
            if ch == "\\" and i + 1 < len(part):
                nxt = part[i + 1]
                buf.append(" " if nxt in "bBdDsSwWAZ" else nxt)
                i += 2
                continue
            if ch not in "()^$*+?":
                buf.append(" " if ch == "." else ch)
            i += 1
        w = " ".join("".join(buf).split()).rstrip(".")
        if w and w not in out:
            out.append(w)
    return out


def fit_words(words: list[str], w: int, sep: str, more: str) -> str:
    """낱말을 `sep` 로 이어 폭 `w` 안으로. 모자라면 낱말 단위로 자르고 `more` 를 붙인다."""
    out = ""
    for i, word in enumerate(words):
        nxt = f"{out}{sep}{word}" if out else word
        tail = f" {more}" if i < len(words) - 1 else ""
        if width(nxt + tail) > w:
            return f"{out} {more}" if out else fit(word, w, more)
        out = nxt
    return out


def article(a: str) -> str:
    """'제29조(시행령 제30조제1항, …)' → '제29조'."""
    return a.split("(")[0].strip()


def title(t: str) -> str:
    """제목 끝의 [과태료 …] 꼬리를 뗀다."""
    return re.sub(r"\s*\[[^\]]*\]\s*$", "", t).strip()


def duty_label(duties: tuple[E.Duty, ...]) -> str:
    if not duties:
        return ""
    d = duties[0]
    more = f" 외 {len(duties) - 1}" if len(duties) > 1 else ""
    return clean(f"{d.law} {article(d.article)} {title(d.title)}{more}")


def failure_text(f: str | None) -> str:
    if not f:
        return ""
    if f == "transport: skipped":
        return "보내지 않음(서비스에 닿지 못함)"
    if f.startswith("transport"):
        return "연결 실패"
    return {"cost-cap": "금액 상한", "time-cap": "시간 상한", "parse": "답을 읽지 못함", "turns": "대화가 너무 김"}.get(
        f, f
    )


def understood(d: dict, sep: str) -> str:
    """기능 파악이 한 일: '기능 6개(신호 7개 중 2개 뺌 · 1개 더함) · 개인정보 흐름 6칸'. 신호 수가 없는 사건(옛 판)은
    기능 수만."""
    text = f"기능 {d.get('features', 0)}개"
    if "signals" in d:
        n, cut, add = d["signals"], d.get("removed", 0), d.get("added", 0)
        parts = [f"신호 {n}개 중 {cut}개 뺌"] if cut else []
        if add:
            parts.append(f"{add}개 더함" if cut else f"신호 {n}개에 {add}개 더함")
        text += f"({sep.join(parts)})" if parts else f"(신호 {n}개 그대로)"
    if d.get("nodes"):
        text += f"{sep}개인정보 흐름 {d['nodes']}칸"
    return text


class State:
    """사건을 모은 지금의 모습. 표시기가 이것으로 그린다."""

    def __init__(self) -> None:
        self.begin: E.Begin | None = None
        self.stages: dict[str, tuple[str, dict]] = {k: ("todo", {}) for k in E.STAGES}
        self.planned = self.done = self.tools = self.overturned = 0
        self.usd = 0.0
        self.active: dict[int, dict] = {}
        self.status: dict[str, str] = {}
        self.by_stage: Counter = Counter()
        self.cites = [0, 0]
        self.searches = [0, 0]
        self.notices: list[E.Notice] = []
        self.checks: dict[int, E.Checked] = {}

    def apply(self, ev: E.Event) -> None:
        if isinstance(ev, E.Stage):
            self.stages[ev.stage] = (ev.state, {**self.stages[ev.stage][1], **ev.detail})  # 시작의 수를 끝에도 쓴다
        elif isinstance(ev, E.Planned):
            self.planned += ev.delta
        elif isinstance(ev, E.Asked):
            self.active[ev.q] = {"stage": ev.stage, "duties": ev.duties, "doing": None}
        elif isinstance(ev, E.Tool):
            self.tools += 1
            if ev.q in self.active:
                self.active[ev.q]["doing"] = (ev.name, ev.target)
        elif isinstance(ev, E.Checked):
            self.checks[ev.q] = ev
            self.cites[0] += ev.citations_ok
            self.cites[1] += ev.citations
            self.searches[0] += ev.searches_ok
            self.searches[1] += ev.searches
        elif isinstance(ev, E.Answered):
            self.active.pop(ev.q, None)
            self.done += 1
            self.usd += ev.usd
            self.by_stage[ev.stage] += 1
            for r in ev.results:
                self.status[r.duty] = r.status
                self.overturned += r.verdict == "overturned"
        elif isinstance(ev, E.Notice):
            self.notices.append(ev)

    def running(self) -> str | None:
        return next((k for k, (s, _) in self.stages.items() if s == "start"), None)

    def tally(self, dot: str) -> str:
        n = Counter(self.status.values())
        return f" {dot} ".join(f"{SHORT[s]} {n[s]}" for s in ORDER if n[s])

    def stage_text(self, stage: str, dot: str) -> str:
        state, d = self.stages[stage]
        sep = f" {dot} "
        if state == "todo":
            return ""
        if state == "fail":
            return "실패" + (f"{sep}{clean(d.get('error', ''))}" if d.get("error") else "")
        if state == "skip":
            why = d.get("why")
            if why == "reused":
                return f"앞 결과를 씀{sep}기능 {d.get('features', 0)}개"
            return {"off": "끔", "nothing": "물을 것 없음" if stage != "gate" else "대조할 것 없음"}.get(why, "건너뜀")
        if stage == "profile" and state == "start":
            return "모델 호출 없음"
        if stage == "profile":
            plats = ", ".join(PLATFORM.get(p, p) for p in d.get("platforms", []))
            return f"기능 {d.get('features', 0)}개" + (f"{sep}{plats}" if plats else "")
        if stage == "understand":
            if state == "start":
                return "폴더를 읽는 중"
            if not d.get("answered"):
                return "답을 받지 못함"
            return understood(d, sep)
        if stage == "investigate":
            total = self.stages["investigate"][1].get("questions", 0)
            duties = self.stages["investigate"][1].get("duties", 0)
            return f"의무 {duties}개를 골라 질문 {self.by_stage['investigate']}/{total}"
        if stage == "rebut":
            return f"질문 {self.by_stage['rebut']}개{sep}뒤집음 {self.overturned}"
        if stage == "gate":
            parts = [f"인용 {self.cites[0]}/{self.cites[1]} 통과"] if self.cites[1] else []
            parts += [f"검색 {self.searches[0]}/{self.searches[1]} 맞음"] if self.searches[1] else []
            return sep.join(parts)
        return ""

    def notice_text(self, n: E.Notice) -> str:
        b = self.begin
        if n.kind == "cost-cap":
            cap = f"(${b.usd:g})" if b else ""
            return f"금액 상한{cap}에 걸려 남은 질문을 보내지 않습니다"
        if n.kind == "time-cap":
            cap = f"({clock(b.seconds)})" if b else ""
            return f"시간 상한{cap}에 걸려 남은 질문을 보내지 않습니다"
        if n.kind == "throttle":
            return f"{n.status} 을 받아 동시 질문을 {n.before}→{n.after}개로 줄였습니다"
        if n.kind == "retry":
            return f"서버가 {n.status} 로 답해 잠시 뒤 다시 보냅니다"
        if n.kind == "repair":
            return "답을 JSON 으로 읽지 못해 한 번 더 묻습니다" + (f"(질문 {n.q})" if n.q else "")
        if n.kind == "unreachable":
            return "서비스에 닿지 못해 남은 질문을 보내지 않습니다"
        return n.kind

    def stopped(self, elapsed: float, dot: str) -> str:
        """Ctrl+C 로 멈췄을 때 남기는 한 줄."""
        where = (
            f"질문 {max(self.planned, self.done)}개 중 {self.done}개에서 멈춤"
            if self.done
            else f"{E.STAGES.get(self.running() or '', '시작')}에서 멈춤"
        )
        return f"{where} {dot} 지금까지 ${self.usd:.2f} {dot} {clock(elapsed)}"


# ── 표시기 ───────────────────────────────────────────────────────────


class Display:
    """사건을 받아 그린다. 스레드 여럿이 사건을 낸다(질문마다 일꾼). 그리다 오류가 나면 검토를 멈추지 않고 표시를
    끈다(`error`). with 로 쓰면 어떻게 끝나든 터미널을 되돌린다."""

    mode = "none"

    def __init__(self, stream, clock_=None, env: dict | None = None) -> None:
        self.stream = stream
        self.g = Glyphs(utf8(stream))
        self.color = color(env)
        self.st = State()
        self._clock = clock_
        self._t0: float | None = None
        self._lock = threading.RLock()
        self.closed = False
        self.error: Exception | None = None

    # 바깥에서 부르는 것
    def elapsed(self) -> float:
        if self._clock:
            return self._clock()
        return time.monotonic() - self._t0 if self._t0 is not None else 0.0

    def begin(self, b: E.Begin) -> None:
        with self._lock:
            self._t0 = time.monotonic()
            self.st.begin = b
            self._guard(self._begin, b)

    def emit(self, ev: E.Event) -> None:
        with self._lock:
            if self.closed:
                return
            self.st.apply(ev)
            self._guard(self._on, ev)

    def finish(self, line: bool = True) -> None:
        """진행 영역을 지운다. `line` 이면 끝 줄을 남긴다(요약이 stdout 의 터미널로 따로 나가지 않을 때)."""
        with self._lock:
            if self.closed:
                return
            self._close()
            if line:
                self._guard(self._finish_line)

    def interrupted(self) -> bool:
        """Ctrl+C: 진행 영역을 지우고 멈춘 곳 한 줄을 남긴다. 남겼으면 True(none 은 남기지 않는다)."""
        with self._lock:
            was_open = not self.closed
            self._close()
            return was_open and self.mode != "none" and self._guard(self._stopped_line)

    def __enter__(self):
        return self

    def __exit__(self, *exc) -> None:
        with self._lock:
            self._close()

    # 표시기마다
    def _begin(self, b: E.Begin) -> None:
        if b.egress:
            self._write(header_line(b) + "\n")

    def _on(self, ev: E.Event) -> None:
        pass

    def _finish_line(self) -> None:
        pass

    def _stopped_line(self) -> None:
        pass

    def _close(self) -> None:
        self.closed = True

    # 돕는 것
    def _guard(self, fn, *args) -> bool:
        """그리기 하나. 오류가 나면 표시를 끄고(터미널은 되돌린다) False."""
        try:
            fn(*args)
        except Exception as e:  # noqa: BLE001 — 진행 표시 때문에 검토가 멈추면 안 된다
            self.error = e
            self._close()
            return False
        return True

    def _write(self, text: str) -> None:
        try:
            self.stream.write(text)
        except UnicodeEncodeError:
            enc = self.stream.encoding or "ascii"
            self.stream.write(text.encode(enc, "replace").decode(enc))
        self.stream.flush()

    def _style(self, text: str, style: str | None) -> str:
        if not style or not self.color or style not in SGR:
            return text
        return f"\x1b[{SGR[style]}m{text}\x1b[0m"


def header_line(b: E.Begin) -> str:
    """전에 review 가 시작할 때 내던 한 줄(plain·none). 웹 실행기의 로그에 남는다."""
    check = b.checker if b.checker else "끔"
    return (
        f"검토({b.model}, 반박 {check}, 묶음 {b.batch}): 모델이 읽은 파일의 코드가 {b.egress} 로 나갑니다"
        f"(비밀값은 가리고 .env 등은 읽지 않음). 상한 ${b.usd:g}·{b.seconds:g}초"
    )


class Plain(Display):
    mode = "plain"

    def _line(self, text: str) -> None:
        m, s = divmod(int(max(0.0, self.elapsed())), 60)
        self._write(f"[{m:02d}:{s:02d}] {text}\n")

    def _begin(self, b: E.Begin) -> None:
        if b.replay is not None:
            check = model_name(b.checker) if b.checker else "끔"
            self._write(
                f"기록 재생 {self.g.dot} 모델 호출 없음 {self.g.dot} 원래 {clock(b.replay)} {self.g.dot} "
                f"조사 {model_name(b.model)} {self.g.dot} 반박 {check}\n"
            )
        else:
            super()._begin(b)

    def _on(self, ev: E.Event) -> None:
        g, st = self.g, self.st
        dot = f" {g.dot} "
        if isinstance(ev, E.Stage):
            name = E.STAGES[ev.stage]
            word = {"start": "시작", "end": "끝", "skip": "건너뜀", "fail": "실패"}[ev.state]
            detail = ""
            if ev.state == "fail":
                detail = clean(ev.detail.get("error", ""))
            elif ev.state == "start" and ev.stage == "investigate":
                detail = f"의무 {ev.detail.get('duties', 0)}개를 골라 질문 {ev.detail.get('questions', 0)}개"
            elif ev.state != "start" or ev.stage == "profile":
                detail = st.stage_text(ev.stage, g.dot)
            self._line(f"{name} {word}" + (f"{dot}{detail}" if detail else ""))
        elif isinstance(ev, E.Asked):
            what = E.STAGES[ev.stage] + (f"{dot}{fit(duty_label(ev.duties), PLAIN_LABEL)}" if ev.duties else "")
            self._line(f"질문 {ev.q} 보냄{dot}{what}")
        elif isinstance(ev, E.Answered):
            self._line(self._answered(ev, dot))
        elif isinstance(ev, E.Notice):
            self._line(f"! {st.notice_text(ev)}")

    def _answered(self, ev: E.Answered, dot: str) -> str:
        if ev.failure and not ev.results or ev.failure in ("cost-cap", "time-cap") and not ev.seconds:
            label = duty_label(ev.duties) or E.STAGES[ev.stage]
            return f"질문 {ev.q} {failure_text(ev.failure)}{dot}{label}"
        parts = []
        if len(ev.results) == 1:
            r = ev.results[0]
            parts.append(f"{r.duty} " + (f"{VERDICT[r.verdict]} → " if r.verdict else "") + SHORT[r.status])
            if r.cite:
                parts.append(fit_tail(clean(r.cite), PLAIN_PATH))
        elif ev.results:
            n = Counter(r.status for r in ev.results)
            parts.append(", ".join(f"{SHORT[s]} {n[s]}" for s in ORDER if n[s]))
            if any(r.verdict for r in ev.results):
                v = Counter(r.verdict for r in ev.results if r.verdict)
                parts.append(", ".join(f"{VERDICT[k]} {c}" for k, c in v.items()))
        else:
            parts.append(E.STAGES[ev.stage])
        if ev.failure:
            parts.append(failure_text(ev.failure))
        c = self.st.checks.get(ev.q)
        if c and c.citations:
            parts.append(f"인용 {c.citations_ok}/{c.citations} 통과")
        parts += [f"도구 {ev.tools}번", f"{ev.seconds:.1f}초", f"${ev.usd:.3f}"]
        return f"질문 {ev.q} 끝{dot}" + dot.join(parts)

    def _finish_line(self) -> None:
        dot = f" {self.g.dot} "
        self._line(f"검토 끝{dot}질문 {self.st.done}개{dot}어림 ${self.st.usd:.2f}")

    def _stopped_line(self) -> None:
        self._line(self.st.stopped(self.elapsed(), self.g.dot))


class Tty(Display):
    """진행 영역을 제자리에서 다시 그린다. 머리(무엇을 어디로 보내는지)는 한 번 쓰고 남긴다."""

    mode = "tty"

    def __init__(self, stream, clock_=None, env: dict | None = None) -> None:
        super().__init__(stream, clock_, env)
        self._drawn = 0
        self._dirty = True
        self._sec = -1
        self._stop = threading.Event()
        self._ticker: threading.Thread | None = None
        self._hidden = False

    def _begin(self, b: E.Begin) -> None:
        cols = size(self.stream)[0] - 1
        dot = f" {self.g.dot} "
        rows: list[tuple[str, str | None]] = []
        if b.replay is not None:
            rows.append((f"기록 재생{dot}모델 호출 없음{dot}원래 {clock(b.replay)}", "bold"))
        commit = f" @ {b.commit[:7]}" if b.commit else ""
        repo = clean(repo_label(b.repo))
        rows.append((f"policyofficer review{dot}{repo}{commit}", None if b.replay is not None else "bold"))
        check = clean(model_label(b.checker)) if b.checker else "끔"
        rows.append((f"조사 {clean(model_label(b.model))}{dot}반박 {check}", "dim"))  # 상한은 바닥 줄에 있다
        if b.egress:
            rows.append((f"읽은 코드가 {clean(host(b.egress))} 으로 나감{dot}비밀값 가림{dot}.env 등 안 읽음", "dim"))
        text = "".join(self._style(line, style) + "\n" for t, style in rows for line in wrap(t, cols))
        self._write(text + "\n\x1b[?25l")
        self._hidden = True
        self._ticker = threading.Thread(target=self._tick, daemon=True)
        self._ticker.start()

    def _on(self, ev: E.Event) -> None:
        self._dirty = True

    def _tick(self) -> None:
        while not self._stop.wait(1 / FPS):
            with self._lock:
                if self.closed:
                    return
                sec = int(self.elapsed())
                if self._dirty or sec != self._sec:
                    self._dirty, self._sec = False, sec
                    self._guard(self._draw)

    def _draw(self) -> None:
        cols, rows = size(self.stream)
        lines = self.frame(cols - 1, rows)
        out = ["\r"]
        if self._drawn:
            out.append(f"\x1b[{self._drawn}A")
        for segs in lines:
            out.append("\x1b[2K" + "".join(self._style(t, s) for t, s in segs) + "\n")
        out.append("\x1b[J")
        self._write("".join(out))
        self._drawn = len(lines)

    def frame(self, cols: int, rows: int) -> list[list[tuple[str, str | None]]]:
        """진행 영역의 줄들(글, 꾸밈). 줄마다 폭 `cols` 안이고, 전체가 `rows - 1` 줄을 넘지 않는다."""
        st, g = self.st, self.g
        dot = f" {g.dot} "
        mark = {
            "todo": (g.todo, "dim"),
            "start": (g.run, "run"),
            "end": (g.done, "ok"),
            "skip": (g.skip, "dim"),
            "fail": (g.fail, "fail"),
        }
        name_w = max(width(n) for n in E.STAGES.values())
        lines: list[list] = []
        for k, name in E.STAGES.items():
            state = st.stages[k][0]
            glyph, style = mark[state]
            detail = st.stage_text(k, g.dot)
            lines.append([("  ", None), (glyph, style), (" ", None), (pad(name, name_w), None), ("  ", None)])
            lines[-1].append((detail, "dim" if state != "start" else None))
        tail: list[list] = []
        if st.done:
            tally = st.tally(g.dot)
            tail.append(
                [
                    ("  ", None),
                    (g.done, "ok"),
                    (f" 끝난 질문 {st.done}개", None),
                    ((dot + tally) if tally else "", "dim"),
                ]
            )
        tail += [[("  ", None), (f"! {st.notice_text(n)}", "warn")] for n in st.notices[-2:]]
        elapsed = self.elapsed()
        b = st.begin
        foot = clock(elapsed) + (f" / {clock(b.seconds)}" if b else "")
        foot += f"{dot}어림 ${st.usd:.2f}" + (f" / ${b.usd:.2f}" if b else "")
        foot += f"{dot}전체 질문 {st.done}/{max(st.planned, st.done)}"
        if b and b.replay is not None:
            foot += f"{dot}기록 재생"
        room = rows - 1 - len(lines) - len(tail) - 3
        active = sorted(st.active.items())
        body: list[list] = []
        if active:
            shown = active if len(active) <= max(room, 0) else active[: max(room - 1, 0)]
            label_w = max(width(self._label(a)) for _, a in shown)  # 하는 일의 칸을 줄끼리 맞춘다
            body = [self._question(a, cols, label_w) for _, a in shown]
            if len(shown) < len(active):
                body.append([("  ", None), (f"{g.more} 진행 중 질문 {len(active) - len(shown)}개 더", "dim")])
        out = [*lines, [], *body, *tail, [], [("  ", None), (foot, None)]]
        return [self._fit(segs, cols) for segs in out[-(rows - 1) :]]

    def _label(self, a: dict) -> str:
        if a["stage"] == "understand":
            return E.STAGES["understand"]
        return (f"반박{self.g.dot} " if a["stage"] == "rebut" else "") + duty_label(a["duties"])

    def _question(self, a: dict, cols: int, widest: int) -> list:
        """진행 중인 질문 한 줄: 법·조문·짧은 제목(왼쪽)과 지금 하는 일(오른쪽). 경로는 끝(파일 이름)을 남긴다."""
        g, label = self.g, self._label(a)
        avail = cols - 4
        label_w = min(widest, max(16, avail * 11 // 20))
        doing_w = avail - label_w - 2
        if doing_w < 10:
            label_w, doing_w = avail, 0
        segs = [("  ", None), (g.run, "run"), (" ", None), (pad(fit(label, label_w, g.more), label_w), None)]
        if not doing_w:
            return segs
        if not a["doing"]:
            doing = "묻는 중"
        else:
            name, target = a["doing"]
            verb = DOING.get(name, clean(name)) + " "
            if name == "search":  # 정규식 원문 대신 낱말로(plain 기록과 JSON 은 원문 그대로)
                words = search_words(clean(target)) or [clean(target)]
                doing = verb + fit_words(words, doing_w - width(verb), dot_sep(g), g.more)
            else:
                doing = verb + fit_tail(clean(target), doing_w - width(verb), g.more)
        return [*segs, ("  ", None), (fit(doing, doing_w, g.more), "dim")]

    def _fit(self, segs: list, cols: int) -> list:
        out, used = [], 0
        for t, s in segs:
            if used + width(t) <= cols:
                out.append((t, s))
                used += width(t)
                continue
            out.append((fit(t, cols - used, self.g.more), s))
            break
        return out

    def _clear(self) -> None:
        self._stop.set()
        text = ""
        if self._drawn:
            text += f"\r\x1b[{self._drawn}A\x1b[J"
            self._drawn = 0
        if self._hidden:
            text += "\x1b[?25h"
            self._hidden = False
        if text:
            with suppress(OSError, ValueError):  # 닫힌 터미널·파이프
                self._write(text)

    def _close(self) -> None:
        if not self.closed:
            self.closed = True
            self._clear()

    def _finish_line(self) -> None:
        dot = f" {self.g.dot} "
        st = self.st
        line = f"{self.g.done} 검토 끝{dot}질문 {st.done}개{dot}{clock(self.elapsed())}{dot}어림 ${st.usd:.2f}"
        self._write(self._style(fit(line, size(self.stream)[0] - 1, self.g.more), "ok") + "\n")

    def _stopped_line(self) -> None:
        line = f"{self.g.stop} " + self.st.stopped(self.elapsed(), self.g.dot)
        self._write(self._style(fit(line, size(self.stream)[0] - 1, self.g.more), "warn") + "\n")


def make(mode: str, stream, clock_=None, env: dict | None = None) -> Display:
    """`mode`(auto·tty·plain·none)에 맞는 표시기."""
    kind = choose(mode, stream, env)
    return {"tty": Tty, "plain": Plain}.get(kind, Display)(stream, clock_, env)
