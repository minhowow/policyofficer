"""포스터·영상에 실리는 화면의 말(2026-11-25): 단계 이름, 머리 세 줄, 검색 낱말, 바닥 줄, 기능 파악 줄, 기록 재생이
쓰는 표의 글. 화면만 바뀌고 JSON 은 그대로다. 모델 호출 0회."""

from __future__ import annotations

import io
import json
import re
from pathlib import Path

import pytest

from policyofficer import cli, profile
from policyofficer import review as rv
from policyofficer.judge.agent import AgentJudge
from policyofficer.judge.fake import review_transport
from policyofficer.report import progress
from policyofficer.review import events as E
from policyofficer.review import replay

ANSI = re.compile(r"\x1b\[[?0-9;]*[A-Za-z]")
BEGIN = E.Begin(
    repo="someone__jobtalk",
    commit="bbfb3ab14534907ff4618c563ff92a6354da97a1",
    model="anthropic:claude-haiku-5-5",
    checker="anthropic:claude-sonnet-5-5(found)",
    batch="bundle",
    usd=0.5,
    seconds=360,
    concurrency=6,
    egress="https://api.anthropic.com/v1/messages",
)


def test_the_stages_have_the_names_the_poster_uses():
    assert list(E.STAGES) == ["profile", "static", "understand", "investigate", "rebut", "gate"]  # 키는 그대로
    assert list(E.STAGES.values()) == ["기능 신호", "정적 규칙", "기능 파악", "의무별 조사", "반박", "직접 대조"]


@pytest.fixture
def tty(monkeypatch):
    def make(cols: int = 80, rows: int = 24, clock: float = 12.0) -> tuple[progress.Tty, io.StringIO]:
        monkeypatch.setenv("COLUMNS", str(cols))
        monkeypatch.setenv("LINES", str(rows))
        monkeypatch.setenv("NO_COLOR", "1")
        buf = io.StringIO()
        return progress.Tty(buf, clock_=lambda: clock), buf

    return make


def _header(d: progress.Tty, buf: io.StringIO, b: E.Begin) -> list[str]:
    d.begin(b)
    d._stop.set()  # 시계로 그리지 않는다
    return buf.getvalue().split("\x1b[?25l")[0].splitlines()


def test_the_header_is_three_short_lines(tty):
    d, buf = tty()
    with d:
        head = _header(d, buf, BEGIN)
    assert head == [
        "policyofficer review · jobtalk @ bbfb3ab",
        "조사 Claude Haiku 5.5 · 반박 Claude Sonnet 5.5",
        "읽은 코드가 api.anthropic.com 으로 나감 · 비밀값 가림 · .env 등 안 읽음",
        "",
    ]


def test_a_replay_header_keeps_its_first_line_and_has_no_egress_line(tty):
    d, buf = tty()
    with d:
        head = _header(d, buf, E.Begin(**{**BEGIN.__dict__, "egress": None, "replay": 155.1, "checker": None}))
    assert head[:3] == [
        "기록 재생 · 모델 호출 없음 · 원래 2:35",
        "policyofficer review · jobtalk @ bbfb3ab",
        "조사 Claude Haiku 5.5 · 반박 끔",
    ]
    assert len(head) == 4


@pytest.mark.parametrize(
    ("pattern", "words"),
    [
        (r"생년|birth|나이|\bage\b|14세", ["생년", "birth", "나이", "age", "14세"]),
        (r"https://|axios|fetch\(", ["https://", "axios", "fetch("]),
        (r"\.env|process\.env\.[A-Z_]+", [".env", "process.env"]),
        (r"(?i)consent|(?:동의)\s*여부|consent", ["consent", "동의 여부"]),
        (r"[가-힣]{2,4}", []),
    ],
)
def test_a_search_pattern_reads_as_words(pattern, words):
    assert progress.search_words(pattern) == words


def test_words_are_cut_between_words():
    words = ["생년", "birth", "나이", "14세", "age"]
    assert progress.fit_words(words, 40, " · ", "…") == "생년 · birth · 나이 · 14세 · age"
    assert progress.fit_words(words, 26, " · ", "…") == "생년 · birth · 나이 …"
    assert progress.fit_words(["아주긴낱말하나뿐"], 8, " · ", "…") == "아주긴…"


def _duty(i: int) -> E.Duty:
    return E.Duty(f"d{i}", "개인정보 보호법", f"제{i}조", "만 14세 미만 아동은 법정대리인 동의를 받는다")


def test_the_frame_says_what_was_chosen_and_searches_in_words(tty):
    d, buf = tty(cols=81)
    with d:
        d.begin(BEGIN)
        d._stop.set()
        done = {"features": 6, "signals": 7, "removed": 2, "added": 1, "nodes": 6, "answered": True}
        d.emit(E.Stage("understand", "end", done))
        d.emit(E.Planned(5))
        d.emit(E.Stage("investigate", "start", {"questions": 4, "duties": 9}))
        d.emit(E.Asked(1, "investigate", (_duty(22),)))
        d.emit(E.Tool(1, "search", r"생년|birth|나이|\bage\b|14세|법정대리인|guardian"))
        d.emit(E.Asked(2, "investigate", (_duty(29),)))
        d.emit(E.Tool(2, "read_file", "backend/src/controllers/authController.ts"))
        rows = ["".join(t for t, _ in segs) for segs in d.frame(80, 24)]
    text = "\n".join(rows)
    assert "기능 6개(신호 7개 중 2개 뺌 · 1개 더함) · 개인정보 흐름 6칸" in text
    assert "의무 9개를 골라 질문 0/4" in text
    search = next(r for r in rows if "검색" in r and "●" in r)
    assert "검색 생년 · birth · 나이" in search and "|" not in search and "\\b" not in search
    assert rows[-1].strip() == "0:12 / 6:00 · 어림 $0.00 / $0.50 · 전체 질문 0/5"
    assert all(progress.width(r) <= 80 for r in rows)


def test_understood_counts_what_the_model_took_out_and_added():
    sep = " · "
    assert progress.understood({"features": 6, "signals": 7, "removed": 2, "added": 1, "nodes": 6}, sep) == (
        "기능 6개(신호 7개 중 2개 뺌 · 1개 더함) · 개인정보 흐름 6칸"
    )
    same = {"features": 7, "signals": 7, "removed": 0, "added": 0}
    assert progress.understood(same, sep) == "기능 7개(신호 7개 그대로)"
    assert progress.understood({"features": 8, "signals": 7, "added": 1, "nodes": 2}, sep) == (
        "기능 8개(신호 7개에 1개 더함) · 개인정보 흐름 2칸"
    )
    # 신호 수가 없는 사건(옛 판의 기록)은 기능 수만
    assert progress.understood({"features": 3}, sep) == "기능 3개"
    features = [{"sources": ["signal", "model"]}] * 4 + [{"sources": ["signal"], "removed": {}}] * 2
    features += [{"sources": ["signal"]}, {"sources": ["model"]}]
    assert rv.feature_counts(features) == {"features": 6, "signals": 7, "removed": 2, "added": 1, "static_added": 0}


def _repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "src").mkdir(parents=True)
    (root / "package.json").write_text(json.dumps({"dependencies": {"express": "^4.0.0"}}), encoding="utf-8")
    (root / "src" / "signup.ts").write_text(
        'router.post("/signup", async (req, res) => {\n  const { email, name, birthDate } = req.body;\n});\n',
        encoding="utf-8",
    )
    return root


def _review(tmp_path: Path, events: list | None = None) -> dict:
    inv, chk = AgentJudge("claude-haiku-5-5", review_transport()), AgentJudge("claude-sonnet-5-5", review_transport())
    sink = events.append if events is not None else E.ignore
    return rv.review(_repo(tmp_path), inv, chk, rv.Limits(concurrency=4), use_static=False, progress=sink)


def test_replay_counts_the_understanding_the_same_way_as_the_run(tmp_path):
    seen: list = []
    doc = _review(tmp_path, seen)
    live = next(e for e in seen if isinstance(e, E.Stage) and e.stage == "understand" and e.state == "end").detail
    _, timeline = replay.timeline(doc)
    again = next(e for _, e in timeline if isinstance(e, E.Stage) and e.stage == "understand" and e.state == "end")
    keys = ("features", "signals", "removed", "added", "static_added", "nodes", "answered")
    assert {k: live[k] for k in keys} == {k: again.detail[k] for k in keys}


def test_replay_draws_old_results_with_todays_table(tmp_path, monkeypatch, capsys):
    """11/24 에 고친 표의 글(제재 label, 겹친 '시행령')이 옛 결과 파일을 재생해도 나오지 않는다."""
    doc = _review(tmp_path)
    duties = {d["id"]: d for d in profile.load_duties()}
    decree = duties["aiact-decree-27-1"]
    old = {**doc["checklist"][0], "duty": decree["id"], "status": "check-applicability", "rank": 99}
    doc["checklist"].append(old)
    for c in doc["checklist"]:
        c["article"] = "시행령 " + duties[c["duty"]]["article"]  # 옛 표의 모양
        c["sanction"] = {**c.get("sanction", {}), "class": "명령", "label": "시정명령을 어기면 과태료 3천만원"}
    (tmp_path / "old.json").write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    monkeypatch.delenv("CI", raising=False)
    assert cli.main(["replay", str(tmp_path / "old.json"), "--speed", "1000", "--progress", "plain"]) == 0
    out, err = capsys.readouterr()
    for text in (out, err):
        assert "시정명령을 어기면" not in text and "시행령 시행령" not in text
    assert f"{decree['law_short']} {progress.article(decree['article'])}" in out
    assert out.count("어기면 · ") > 0 and "질문 1 보냄 · 기능 파악" in err
