"""먼저 볼 것(review.highlights): 고르는 규칙, JSON 의 summary.highlights, 터미널 요약.
모델 호출 0회."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema

from policyofficer import review as rv
from policyofficer.judge.agent import AgentJudge
from policyofficer.judge.fake import review_transport
from policyofficer.report.review_text import NOTE, render

SCHEMA = json.loads((Path(__file__).resolve().parents[1] / "schemas" / "review-2.json").read_text(encoding="utf-8"))


def _item(rank: int, feature: str, cls: str = "과태료", won: int | None = 1, verdict: str = "upheld", **kw) -> dict:
    return {
        "duty": f"d{rank}",
        "feature": feature,
        "law": "개인정보 보호법",
        "article": f"제{rank}조",
        "title": f"의무 {rank}",
        "status": "seen-in-code",
        "rank": rank,
        "citations": [
            {"file": f"src/f{rank}.ts", "line": rank, "text": f"code line {rank}", "ok": True, "why": "grounded"}
        ],
        "verification": {"result": verdict},
        "sanction": {"class": cls, "label": cls, "max_won": won, "items": [], "note": None, "as_of": "2026-11-25"},
        "missing": f"없는 처리 {rank}",
        "question": f"물어볼 것 {rank}",
        **kw,
    }


def _duties(items: list[dict]) -> list[str]:
    return [h["duty"] for h in rv.highlights(items)]


def test_upheld_comes_first_then_the_heavier_sanction():
    items = [_item(1, "a", "과태료"), _item(2, "b", "징역", verdict="not-run"), _item(3, "c", "과징금")]
    assert _duties(items) == ["d3", "d1", "d2"]  # 반박을 견딘 것이 먼저, 그 안에서 과징금 > 과태료


def test_the_same_class_goes_by_the_larger_amount_then_the_checklist_order():
    items = [_item(1, "a", won=10), _item(2, "b", won=30), _item(3, "c", won=30)]
    assert _duties(items) == ["d2", "d3", "d1"]


def test_one_per_feature_before_filling():
    items = [_item(1, "a", "징역"), _item(2, "a", "징역"), _item(3, "b", "과태료"), _item(4, "c", "없음", None)]
    assert _duties(items) == ["d1", "d3", "d4"]  # a 의 두 번째(d2)보다 다른 기능이 먼저
    assert _duties(items[:3]) == ["d1", "d2", "d3"]  # 기능이 둘뿐이면 남은 후보로 채운다(순서대로 놓는다)


def test_only_seen_in_code_with_a_model_citation_counts():
    profile_only = _item(1, "a", "징역")
    profile_only["citations"] = [{"file": "package.json", "line": 3, "text": "express", "ok": True, "why": "profile"}]
    refused = _item(2, "b", "징역")
    refused["citations"][0]["ok"] = False
    goods = _item(3, "c", "징역", group="goods")
    outside = _item(4, "d", "징역", status="check-outside")
    kept = _item(5, "e", "과태료")
    assert _duties([profile_only, refused, goods, outside, kept]) == ["d5"]
    assert rv.highlights([profile_only, refused]) == []  # 후보가 없으면 비운다
    assert rv.highlights([kept]) == [{"duty": "d5", "file": "src/f5.ts", "line": 5, "text": "code line 5"}]


def test_the_terminal_shows_them_above_the_tool_check_with_the_list_number():
    items = [_item(1, "a", "과태료"), _item(2, "b", "징역"), _item(3, "a", "과징금")]
    doc = {"run": {"seconds": 10, "usd_estimate": 0.01, "questions": []}, "checklist": items}
    out = render(doc, None, False, 80)
    tail = out[out.index("먼저 볼 3건") :]
    assert tail.index("!! 1  개인정보 보호법 제2조") < tail.index("!! 2  개인정보 보호법 제3조")
    assert "      src/f2.ts:2" in tail and "│ code line 2" in tail
    assert "없는 것: 없는 처리 2" in tail and "물어볼 것: 물어볼 것 2" in tail
    assert tail.index("물어볼 것 1") < tail.index(NOTE)
    assert "먼저 볼" not in render({**doc, "checklist": [{**items[0], "status": "not-applicable"}]}, None, False, 80)


def _repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "src").mkdir(parents=True)
    (root / "package.json").write_text(json.dumps({"dependencies": {"express": "^4.0.0"}}), encoding="utf-8")
    (root / "src" / "signup.ts").write_text(
        'router.post("/signup", async (req, res) => {\n  const { email, name } = req.body;\n});\n', encoding="utf-8"
    )
    return root


def test_the_json_carries_them_and_matches_the_schema(tmp_path):
    inv, chk = AgentJudge("claude-haiku-5-5", review_transport()), AgentJudge("claude-sonnet-5-5", review_transport())
    doc = rv.review(_repo(tmp_path), inv, chk, rv.Limits(concurrency=2))
    assert list(doc["summary"]) == ["counts", "labels", "top", "groups", "highlights"]
    assert doc["summary"]["highlights"] == rv.highlights(doc["checklist"])
    assert not list(jsonschema.Draft202012Validator(SCHEMA).iter_errors(doc))
    old = {**doc, "summary": {k: v for k, v in doc["summary"].items() if k != "highlights"}}
    assert not list(jsonschema.Draft202012Validator(SCHEMA).iter_errors(old))  # 옛 결과도 통과한다
