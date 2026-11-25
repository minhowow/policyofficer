"""의무별 제재 표(profile/sanctions.jsonl): 불러올 때의 검사, review 결과의 sanction, 요약의 정렬·표지, 기록 재생."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

import jsonschema
import pytest

from policyofficer import cli, profile
from policyofficer import review as rv
from policyofficer.judge.agent import AgentJudge
from policyofficer.judge.fake import review_transport
from policyofficer.report import progress
from policyofficer.report.review_text import SANCTION_NOTE, render

SCHEMA = json.loads((Path(__file__).resolve().parents[1] / "schemas" / "review-2.json").read_text(encoding="utf-8"))


def test_the_table_has_one_record_for_each_duty_the_review_asks():
    table = profile.load_sanctions()
    asked = {d["id"] for d in profile.load_duties() if d.get("addressee")}
    assert set(table) == asked and len(table) == 220
    assert {s["class"] for s in table.values()} <= set(profile.SANCTION_CLASSES)
    assert all(i["quote"].strip() for s in table.values() for i in s["items"])
    assert all("duty" not in s for s in table.values())
    # 화면은 '어기면 · {label}' 이라 label 안에 '어기면'이 또 있으면 두 번 읽힌다(11/24 jobtalk 실행 화면)
    assert not [d for d, s in table.items() if "어기면" in s["label"]]


def test_an_asked_decree_duty_does_not_repeat_the_decree_in_its_article():
    """'인공지능기본법 시행령 시행령 제27조제1항' 처럼 짧은 법 이름과 조문에 '시행령'이 겹치지 않는다(11/24 화면)."""
    doubled = [
        d["id"]
        for d in profile.load_duties()
        if d.get("addressee") and d["law_short"].endswith("시행령") and d["article"].startswith("시행령")
    ]
    assert doubled == []


@pytest.fixture
def table_dir(tmp_path, monkeypatch):
    """표를 tmp 로 옮겨 고쳐 본다. 끝나면 캐시를 비운다."""
    shutil.copy(profile.HERE / "duties.jsonl", tmp_path / "duties.jsonl")
    rows = [json.loads(x) for x in (profile.HERE / "sanctions.jsonl").read_text(encoding="utf-8").splitlines()]
    monkeypatch.setattr(profile, "HERE", tmp_path)
    profile.load_sanctions.cache_clear()

    def write(rows_: list[dict]) -> None:
        text = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows_)
        (tmp_path / "sanctions.jsonl").write_text(text, encoding="utf-8")
        profile.load_sanctions.cache_clear()

    yield rows, write
    profile.load_sanctions.cache_clear()


@pytest.mark.parametrize("broken", ["missing", "twice", "extra", "class", "quote"])
def test_a_broken_table_is_refused_when_loaded(table_dir, broken):
    rows, write = table_dir
    rows = json.loads(json.dumps(rows))
    with_item = next(r for r in rows if r["items"])
    if broken == "missing":
        rows = rows[1:]
    elif broken == "twice":
        rows.append(rows[0])
    elif broken == "extra":
        rows.append({**rows[0], "duty": "no-such-duty"})
    elif broken == "class":
        rows[0]["class"] = "사형"
    else:
        with_item["items"][0]["quote"] = "  "
    write(rows)
    with pytest.raises(ValueError, match="sanctions.jsonl"):
        profile.load_sanctions()


def _repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "src").mkdir(parents=True)
    (root / "package.json").write_text(json.dumps({"dependencies": {"express": "^4.0.0"}}), encoding="utf-8")
    (root / "src" / "signup.ts").write_text(
        'router.post("/signup", async (req, res) => {\n  const { email, name } = req.body;\n});\n', encoding="utf-8"
    )
    return root


def test_every_checklist_item_carries_its_sanction_and_matches_the_schema(tmp_path):
    inv, chk = AgentJudge("claude-haiku-5-5", review_transport()), AgentJudge("claude-sonnet-5-5", review_transport())
    doc = rv.review(_repo(tmp_path), inv, chk, rv.Limits(concurrency=4))
    table = profile.load_sanctions()
    assert doc["checklist"]
    for c in doc["checklist"]:
        assert c["sanction"] == table[c["duty"]]
        assert list(c)[: list(c).index("sanction") + 1][-2:] == ["quote", "sanction"]
    errors = list(jsonschema.Draft202012Validator(SCHEMA).iter_errors(doc))
    assert not errors, [f"{list(e.path)}: {e.message[:200]}" for e in errors[:5]]


def _item(rank: int, cls: str, won: int | None, status: str = "seen-in-code") -> dict:
    label = {"징역": "징역 5년", "과징금": "과징금 매출 3%", "과태료": "과태료 3천만원"}.get(cls, "벌칙·과태료 없음")
    return {
        "duty": f"d{rank}",
        "law": "개인정보 보호법",
        "article": f"제{rank}조",
        "title": f"의무 {rank} 수집·이용 동의 때 목적·항목·보유기간·거부권 고지",
        "status": status,
        "rank": rank,
        "citations": [{"file": "src/a.ts", "line": rank, "ok": True}],
        "sanction": {"class": cls, "label": label, "max_won": won, "items": [], "note": None, "as_of": "2026-11-24"},
    }


def test_the_summary_puts_heavier_sanctions_first_and_marks_prison_and_fines():
    items = [_item(1, "과태료", 30_000_000), _item(2, "징역", 50_000_000), _item(3, "과징금", 1_000_000_000)]
    items += [_item(4, "없음", None), _item(5, "과태료", 50_000_000), _item(6, "징역", 10_000_000, "check-outside")]
    doc = {"run": {"seconds": 10, "usd_estimate": 0.01, "questions": []}, "checklist": items}
    for cols in (None, 140, 80):
        out = render(doc, None, False, cols)
        rows = [ln for ln in out.splitlines() if re.match(r"^(!!|  )[ \d]\d  ", ln)]
        assert [re.search(r"제(\d)조", r).group(1) for r in rows] == ["2", "3", "5", "1", "4", "6"]
        assert [r.startswith("!!") for r in rows] == [True, True, False, False, False, True]
        assert out.count(SANCTION_NOTE.split(".")[0]) == 1 and "어기면 · 징역 5년" in out
        if cols:
            assert all(progress.width(ln) <= cols for ln in out.splitlines())
    long_ = _item(7, "명령", 30_000_000, "check-applicability")
    long_["sanction"]["label"] = "시정명령 불이행 시 과태료 3천만원 · 악의적이면 징역 3년"
    doc["checklist"].append(long_)
    narrow, wide = render(doc, None, False, 80), render(doc, None, False, 140)
    assert re.search(r"^      어기면 · 시정명령 불이행 시 과태료 3천만원", narrow, re.M)  # 좁으면 다음 줄로 내린다
    assert re.search(r"제7조 · .+  어기면 · 시정명령 불이행 시", wide)
    assert SANCTION_NOTE.replace(" ", "") in render(doc, None, False, 80).replace("\n", "").replace(" ", "")


def test_replay_shows_sanctions_for_a_result_made_before_the_table(tmp_path, monkeypatch, capsys):
    inv, chk = AgentJudge("claude-haiku-5-5", review_transport()), AgentJudge("claude-sonnet-5-5", review_transport())
    doc = rv.review(_repo(tmp_path), inv, chk, rv.Limits(concurrency=4))
    for c in doc["checklist"]:
        c.pop("sanction")
    (tmp_path / "old.json").write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    monkeypatch.delenv("CI", raising=False)
    assert cli.main(["replay", str(tmp_path / "old.json"), "--speed", "1000", "--progress", "none"]) == 0
    out = capsys.readouterr().out
    listed = [c for c in doc["checklist"] if c["status"] in ("seen-in-code", "check-outside", "check-applicability")]
    assert out.count("어기면 · ") == len([c for c in listed if c.get("group") != "goods"]) > 0
    assert SANCTION_NOTE in out
