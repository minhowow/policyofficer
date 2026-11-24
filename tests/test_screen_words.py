"""기록 재생은 지금 표의 글(제재 label, 조문 표기)로 다시 그린다(2026-11-25). 판정과 인용은 파일 그대로다.
모델 호출 0회."""

from __future__ import annotations

import json
from pathlib import Path

from policyofficer import cli, profile
from policyofficer import review as rv
from policyofficer.judge.agent import AgentJudge
from policyofficer.judge.fake import review_transport
from policyofficer.report import progress
from policyofficer.review import events as E


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
    assert out.count("어기면 · ") > 0 and "질문 1 보냄 · 서비스 이해" in err
