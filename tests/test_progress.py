"""review 의 진행 표시와 출력: 가짜 판정자(judge/fake.review_transport)로 CLI 를 끝까지 돌린다. 모델 호출 0회."""

from __future__ import annotations

import fcntl
import io
import json
import os
import re
import struct
import sys
import termios
import threading
from pathlib import Path

import pytest

from policyofficer import cli
from policyofficer import review as rv
from policyofficer.judge.agent import AgentJudge
from policyofficer.judge.fake import review_transport
from policyofficer.report import progress
from policyofficer.report.review_text import render
from policyofficer.review import events as E

FILES = {
    "package.json": json.dumps({"dependencies": {"express": "^4.0.0"}}),
    "src/routes/signup.ts": (
        'import express from "express";\n'
        "const router = express.Router();\n"
        'router.post("/signup", async (req, res) => {\n'
        "  const { email, name, birthDate } = req.body;\n"
        "  await db.user.create({ data: { email, name, birthDate } });\n"
        "});\n"
    ),
}
SGR = re.compile(r"\x1b\[[0-9;]*m")
ANSI = re.compile(r"\x1b\[[?0-9;]*[A-Za-z]")
HANGUL = re.compile("[가-힣]")


def _repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    for name, text in FILES.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(text, encoding="utf-8")
    return root


@pytest.fixture
def fake_judges(monkeypatch):
    """CLI 의 판정기를 가짜 전송으로 바꾼다(키·네트워크 없음)."""
    delay = {"s": 0.0}

    def build(spec, throttle, env=None):
        return AgentJudge(spec.partition(":")[2], throttle.wrap(review_transport(delay=delay["s"])))

    monkeypatch.setattr(rv, "build_judge", build)
    for k in ("CI", "NO_COLOR", "TERM", "COLUMNS", "LINES"):
        monkeypatch.delenv(k, raising=False)
    return delay


def _shape(x):
    """값을 지우고 키와 구조(순서 포함)만 남긴다."""
    if isinstance(x, dict):
        return [(k, _shape(v)) for k, v in x.items()]
    if isinstance(x, list):
        return [_shape(v) for v in x[:1]]
    return type(x).__name__


VOLATILE = re.compile(r'"(started|seconds)": [0-9.]+')


def test_a_piped_stdout_gets_the_same_json_and_plain_stderr_has_no_escape(tmp_path, capsys, fake_judges):
    root = _repo(tmp_path)
    assert cli.main(["review", str(root), "--model", "anthropic:m1", "--checker", "anthropic:m2"]) == 0
    out, err = capsys.readouterr()
    doc = json.loads(out)
    # 표시기를 거치지 않은 review 와 키·구조·순서가 같다(실행마다 다른 시각만 다를 수 있다)
    inv = AgentJudge("m1", review_transport())
    chk = AgentJudge("m2", review_transport())
    limits = rv.Limits(concurrency=6)
    direct = rv.review(root, inv, chk, limits, throttles=(rv.Throttle(6), rv.Throttle(6)))
    assert _shape(doc) == _shape(direct)
    assert list(doc) == ["review_version", "tool", "summary", "profile", "data_flow", "obligations", "checklist", "run"]
    assert VOLATILE.sub("", json.dumps(doc["checklist"])) == VOLATILE.sub("", json.dumps(direct["checklist"]))
    assert doc["run"]["calls"] == direct["run"]["calls"] and doc["summary"] == direct["summary"]
    # stderr 는 plain: 제어 문자가 하나도 없고, 사건마다 [mm:ss] 한 줄
    assert "\x1b" not in err
    lines = err.splitlines()
    assert lines[0].startswith("검토(anthropic:m1, 반박 anthropic:m2, 묶음 duty): 모델이 읽은 파일의 코드가 ")
    assert all(re.match(r"\[\d\d:\d\d\] ", ln) for ln in lines[1:])
    assert any("의무별 조사 시작" in ln for ln in lines) and any("반박 끝" in ln for ln in lines)
    usd = doc["run"]["usd_estimate"]
    assert lines[-1].endswith(f"검토 끝 · 질문 {len(doc['run']['questions'])}개 · 어림 ${usd:.2f}")


class _Pty:
    """pty 한 쌍. slave 를 글 스트림으로 주고, master 에서 나온 것을 모은다."""

    def __init__(self, cols: int = 80, rows: int = 24) -> None:
        self.master, self.slave = os.openpty()
        fcntl.ioctl(self.slave, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))
        attrs = termios.tcgetattr(self.slave)
        attrs[1] &= ~termios.ONLCR  # \n 을 \r\n 으로 바꾸지 않는다(받은 바이트를 그대로 본다)
        termios.tcsetattr(self.slave, termios.TCSANOW, attrs)
        self.stream = io.TextIOWrapper(os.fdopen(self.slave, "wb", buffering=0), encoding="utf-8", write_through=True)
        self.chunks: list[bytes] = []
        self._reader = threading.Thread(target=self._read, daemon=True)
        self._reader.start()

    def _read(self) -> None:
        while True:
            try:
                b = os.read(self.master, 65536)
            except OSError:
                return
            if not b:
                return
            self.chunks.append(b)

    def text(self) -> str:
        self.stream.close()
        self._reader.join(timeout=5)
        os.close(self.master)
        return b"".join(self.chunks).decode("utf-8")


def _frames(raw: str) -> list[list[str]]:
    """다시 그린 프레임마다 그 줄들(제어 문자를 뗀 글)."""
    out = []
    for part in raw.split("\x1b[J")[:-1]:
        rows = [ANSI.sub("", seg.split("\n")[0]) for seg in part.split("\x1b[2K")[1:]]
        if rows:
            out.append(rows)
    return out


def test_a_terminal_gets_frames_that_fit_80_columns_and_the_cursor_comes_back(tmp_path, monkeypatch, fake_judges):
    fake_judges["s"] = 0.12
    pty = _Pty(cols=80)
    monkeypatch.setattr(sys, "stderr", pty.stream)
    monkeypatch.setattr(sys, "stdout", io.StringIO())
    args = ["review", str(_repo(tmp_path)), "--concurrency", "3", "--model", "anthropic:m1"]
    assert cli.main(args) == 0
    raw = pty.text()
    doc = json.loads(sys.stdout.getvalue())  # stdout 이 터미널이 아니면 JSON
    assert raw.count("\x1b[?25l") == 1 and raw.rstrip("\n").rfind("\x1b[?25h") > raw.rfind("\x1b[2K")
    frames = _frames(raw)
    assert len(frames) >= 3
    rows = [r for f in frames for r in f]
    assert all(progress.width(r) <= 80 for r in rows), max(rows, key=progress.width)
    # 한글 제목이 든 질문 줄이 폭에 맞춰 잘렸다
    asked = [r for r in rows if r.startswith("  ● ") and HANGUL.search(r) and "…" in r]
    assert asked and max(progress.width(r) for r in asked) > 60
    assert any(r.lstrip().startswith("✓ 기능 신호") for r in rows) and any("질문 " in r and "/" in r for r in rows)
    # 끝: 진행 영역을 지우고(위로 올라가 아래를 지움) 커서를 되살린 뒤 끝 줄 하나
    end = raw[raw.rfind("\x1b[2K") :]
    assert re.search(r"\r\x1b\[\d+A\x1b\[J\x1b\[\?25h", end)
    last = ANSI.sub("", end.split("\x1b[?25h")[-1]).strip()
    assert last.startswith(f"✓ 검토 끝 · 질문 {len(doc['run']['questions'])}개")


def test_no_color_drops_only_the_colours_and_ci_means_plain(tmp_path, monkeypatch, fake_judges):
    fake_judges["s"] = 0.05
    monkeypatch.setenv("NO_COLOR", "1")
    pty = _Pty(cols=100)
    monkeypatch.setattr(sys, "stderr", pty.stream)
    monkeypatch.setattr(sys, "stdout", io.StringIO())
    assert cli.main(["review", str(_repo(tmp_path)), "--no-rebut"]) == 0
    raw = pty.text()
    assert "\x1b[2K" in raw and not SGR.search(raw)  # 다시 그리기는 하고 색은 없다
    summary = render(json.loads(sys.stdout.getvalue()), None, progress.color(), 80)
    assert not SGR.search(summary)

    tty = type("T", (), {"isatty": lambda self: True})()
    assert progress.choose("auto", tty, {"CI": "1"}) == "plain"
    assert progress.choose("auto", tty, {"CI": "true"}) == "plain"
    assert progress.choose("auto", tty, {"CI": "false"}) == "tty"
    assert progress.choose("auto", tty, {"CI": "0"}) == "tty"
    assert progress.choose("auto", tty, {"CI": ""}) == "tty"
    assert progress.choose("auto", tty, {"TERM": "dumb"}) == "plain"
    assert progress.choose("auto", io.StringIO(), {}) == "plain"
    assert progress.choose("none", tty, {}) == "none"


def test_ci_on_a_terminal_is_plain_end_to_end(tmp_path, monkeypatch, fake_judges):
    monkeypatch.setenv("CI", "1")
    pty = _Pty(cols=80)
    monkeypatch.setattr(sys, "stderr", pty.stream)
    monkeypatch.setattr(sys, "stdout", io.StringIO())
    assert cli.main(["review", str(_repo(tmp_path)), "--no-rebut"]) == 0
    raw = pty.text()
    assert "\x1b" not in raw and "[00:0" in raw


def test_korean_width_and_cutting():
    assert progress.width("개인정보 보호법") == 15
    assert progress.width("e\u0301") == 1  # 결합 문자는 0칸
    assert progress.width("\u1100\u1161") == 2  # NFD 자모는 모아서 센다(macOS 경로)
    cut = progress.fit("개인정보 보호법 제29조 안전조치", 12)
    assert progress.width(cut) <= 12 and cut.endswith("…")
    assert progress.fit_tail("src/main/java/User.java", 12).endswith("User.java")
    assert progress.clean("a\x1b[2Jb\u202e") == "a?[2Jb?"  # 저장소의 글이 터미널을 조작하지 못한다
    g = progress.Glyphs(progress.utf8(io.TextIOWrapper(io.BytesIO(), encoding="cp949")))
    assert (g.done, g.run, g.todo) == ("v", "*", "o")


def test_ctrl_c_clears_the_screen_and_says_where_it_stopped(tmp_path, monkeypatch, fake_judges):
    def interrupted(*a, progress, **kw):
        progress(E.Stage("profile", "start"))
        progress(E.Planned(21))
        for q in range(1, 15):
            progress(E.Asked(q, "investigate"))
            progress(E.Answered(q, "investigate", usd=0.005))
        raise KeyboardInterrupt

    monkeypatch.setattr(rv, "review", interrupted)
    pty = _Pty(cols=80)
    monkeypatch.setattr(sys, "stderr", pty.stream)
    monkeypatch.setattr(sys, "stdout", io.StringIO())
    assert cli.main(["review", str(_repo(tmp_path))]) == 130
    raw = pty.text()
    assert "\x1b[?25h" in raw and "Traceback" not in raw
    last = ANSI.sub("", raw.split("\x1b[?25h")[-1]).strip()
    assert re.fullmatch(r"■ 질문 21개 중 14개에서 멈춤 · 지금까지 \$0\.07 · \d+:\d\d", last), last
    assert sys.stdout.getvalue() == ""


def test_a_failing_worker_stops_the_rest_from_starting():
    started = []

    def work(i):
        started.append(i)
        if i == 0:
            raise RuntimeError("boom")
        threading.Event().wait(0.05)
        return i

    with pytest.raises(RuntimeError):
        rv.parallel(work, list(range(50)), 2)
    threading.Event().wait(0.2)
    assert len(started) < 10
    assert rv.parallel(lambda i: i * 2, [3, 1, 2], 2) == [6, 2, 4]


def test_output_also_writes_the_file_and_plain_shows_each_question(tmp_path, capsys, fake_judges):
    root = _repo(tmp_path)
    assert cli.main(["review", str(root), "-o", str(tmp_path / "r.json"), "--progress", "plain"]) == 0
    out, err = capsys.readouterr()
    saved = json.loads((tmp_path / "r.json").read_text(encoding="utf-8"))
    assert json.loads(out) == saved  # -o 는 파일에도 쓴다
    assert "\x1b" not in err
    n = len(saved["run"]["questions"])
    # 질문마다 보냄·끝이 한 줄씩
    assert sum("보냄 · " in ln for ln in err.splitlines()) == n
    assert sum(re.search(r"질문 \d+ 끝 · ", ln) is not None for ln in err.splitlines()) == n


def test_a_terminal_stdout_gets_a_summary_and_the_json_goes_to_the_cache(tmp_path, monkeypatch, fake_judges):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))

    class TtyOut(io.StringIO):
        def isatty(self):
            return True

    monkeypatch.setattr(sys, "stdout", TtyOut())
    monkeypatch.setattr(sys, "stderr", io.StringIO())
    root = _repo(tmp_path)
    assert cli.main(["review", str(root), "--no-rebut"]) == 0
    out = SGR.sub("", sys.stdout.getvalue())  # 터미널이면 색이 있다
    files = list((tmp_path / "cache" / "policyofficer" / "reviews").glob("repo-*.json"))
    assert len(files) == 1  # 분석하는 저장소에는 파일을 만들지 않는다
    assert sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()) == sorted(FILES)
    doc = json.loads(files[0].read_text(encoding="utf-8"))
    assert out.startswith("✓ 검토 끝 · ") and "전체 결과(JSON): " in out and not out.lstrip().startswith("{")
    todo = sum(doc["summary"]["counts"][s] for s in ("seen-in-code", "check-outside", "check-applicability"))
    rows = re.findall(r"^(?:!!|  )[ \d]\d  ", out, re.M)  # 목록 줄(징역·과징금은 '!!'로 시작)
    assert len(rows) == todo - sum(c.get("group") == "goods" for c in doc["checklist"])
    # --json 이면 터미널이어도 JSON
    monkeypatch.setattr(sys, "stdout", TtyOut())
    assert cli.main(["review", str(root), "--no-rebut", "--json"]) == 0
    assert json.loads(sys.stdout.getvalue())["review_version"] == 2
