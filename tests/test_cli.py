"""한 줄 명령 `policyofficer [폴더]`: 명령과 폴더를 가르고, 이 꼴에서만 기본값 셋이 다르다. 모델 호출 0회(가짜 전송)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from policyofficer import cli
from policyofficer import review as rv
from policyofficer.judge.agent import AgentJudge
from policyofficer.judge.fake import review_transport


def _repo(root: Path) -> Path:
    (root / "src").mkdir(parents=True)
    (root / "package.json").write_text(json.dumps({"dependencies": {"express": "^4.0.0"}}), encoding="utf-8")
    (root / "src" / "signup.ts").write_text(
        'router.post("/signup", async (req, res) => {\n  const { email, name } = req.body;\n});\n', encoding="utf-8"
    )
    return root


@pytest.fixture
def fake(monkeypatch):
    def build(spec, throttle, env=None):
        return AgentJudge(spec.partition(":")[2], throttle.wrap(review_transport()))

    monkeypatch.setattr(rv, "build_judge", build)
    for k in ("CI", "NO_COLOR", "TERM", "COLUMNS", "LINES"):
        monkeypatch.delenv(k, raising=False)


def _run(capsys, *argv: str) -> tuple[int, dict | None, str]:
    code = cli.main(list(argv))
    out, err = capsys.readouterr()
    try:
        return code, json.loads(out), err
    except ValueError:
        return code, None, err + out


def test_no_argument_reviews_the_current_folder_with_the_one_line_defaults(tmp_path, monkeypatch, capsys, fake):
    monkeypatch.chdir(_repo(tmp_path / "app"))
    for argv in ((), (".",)):
        code, doc, _ = _run(capsys, *argv, "--progress", "none")
        assert code == 0 and doc["run"]["batch"] == "bundle" and doc["run"]["rebut_scope"] == "found"
        assert doc["run"]["limits"]["usd"] == 2.0 and doc["run"]["rebut"]


def test_the_one_line_form_takes_review_options(tmp_path, capsys, fake):
    app = _repo(tmp_path / "app")
    code, doc, _ = _run(capsys, str(app), "--no-rebut", "--max-usd", "0.5", "--progress", "none")
    assert code == 0 and not doc["run"]["rebut"] and doc["run"]["limits"]["usd"] == 0.5
    assert doc["run"]["batch"] == "bundle"
    code, plan, _ = _run(capsys, str(app), "--plan")
    assert code == 0 and set(plan) >= {"features", "listed", "review", "questions"}


def test_review_keeps_its_defaults(tmp_path, capsys, fake):
    """웹 실행기가 쓰는 `policyofficer review` 의 기본값은 그대로다."""
    code, doc, _ = _run(capsys, "review", str(_repo(tmp_path / "app")), "--progress", "none")
    assert code == 0 and doc["run"]["batch"] == "duty" and doc["run"]["rebut_scope"] == "all"
    assert doc["run"]["limits"]["usd"] == 5.0


def test_a_command_name_is_a_command_and_a_folder_needs_a_path(tmp_path, monkeypatch, capsys, fake):
    monkeypatch.chdir(tmp_path)
    code, _, err = _run(capsys, "scan", ".")
    assert code == 2 and "scan: 명령도 폴더도 아닙니다" in err and "(명령: profile · review)" in err
    code, _, err = _run(capsys, "replay", "r.json")  # 11/25 에 뺀 명령
    assert code == 2 and "replay: 명령도 폴더도 아닙니다" in err
    _repo(tmp_path / "scan")
    code, doc, _ = _run(capsys, "./scan", "--progress", "none")
    assert code == 0 and doc["run"]["batch"] == "bundle"
    _repo(tmp_path / "review")
    code, doc, _ = _run(capsys, "./review", "--progress", "none")  # 명령과 같은 이름의 폴더
    assert code == 0 and doc["run"]["batch"] == "bundle"
    with pytest.raises(SystemExit) as e:
        cli.main(["review"])  # 명령 review 에 폴더가 없다
    assert e.value.code == 2


def test_a_file_or_a_missing_folder_is_a_clear_error(tmp_path, capsys, fake):
    (tmp_path / "a.ts").write_text("x\n", encoding="utf-8")
    code, _, err = _run(capsys, str(tmp_path / "a.ts"))
    assert code == 2 and "폴더를 주세요" in err and "파일 하나는 검토하지 않습니다" in err
    code, _, err = _run(capsys, "--plan", str(tmp_path / "nope"))
    assert code == 2 and "폴더가 없습니다" in err


def test_version_and_help(capsys):
    with pytest.raises(SystemExit) as e:
        cli.main(["--version"])
    assert e.value.code == 0 and capsys.readouterr().out.strip().startswith("policyofficer ")
    with pytest.raises(SystemExit) as e:
        cli.main(["-h"])
    out = capsys.readouterr().out
    assert e.value.code == 0 and out.startswith("usage: policyofficer [폴더] [옵션]")
    assert out.index("policyofficer [폴더]   폴더를 검토한다") < out.index("profile")
    assert "저장소" not in out and "replay" not in out


def test_without_a_key_the_error_points_at_plan(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    code, _, err = _run(capsys, str(_repo(tmp_path / "app")))
    assert code == 2 and "ANTHROPIC_API_KEY 가 없습니다" in err and "--plan" in err
