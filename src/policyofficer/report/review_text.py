"""review 결과(JSON)의 사람이 읽는 요약. stdout 이 터미널일 때 JSON 대신 낸다(전체 JSON 은 파일로 저장한다).

상태별 개수, '확인할 것' 목록(법·조문·제목·인용 file:line), 걸린 시간, 어림 금액, 저장한 JSON 의 경로. 목록은 갈래
(코드에서 본 것 → 저장소 밖 → 해당 여부) 안에서 제재 등급 순(SANCTION_ORDER), 같은 등급이면 정액 상한(max_won)이 큰
것이 먼저다. 항목에 제재(sanction)가 없으면 체크리스트 순서(rank) 그대로다.

제재가 있으면 줄 끝에 "어기면 · {label}"을 붙이고(어느 줄이든 제목이 TITLE_MIN 칸보다 좁아지면 모두 다음 줄로
내린다), 징역·과징금은 강조한다. 색이 없어도 알아보게 번호 앞에 "!!"를 붙인다. 주의 문구(SANCTION_NOTE)는 요약
아래에 한 번 둔다. 각주 바로 위에는 도구가 모델의 인용·'없다' 검색을 다시 대조한 결과를 한 줄로 둔다(tool_check).
"""

from __future__ import annotations

import os
from pathlib import Path

from policyofficer.report.progress import SGR, Glyphs, article, clean, clock, fit, fit_tail, pad, title, width, wrap
from policyofficer.review.prompts import ORDER, STATUS_LABEL

TO_CHECK = ("seen-in-code", "check-outside", "check-applicability")
SANCTION_ORDER = ("징역", "과징금", "벌금", "과태료", "명령", "없음")
"""제재 등급(의무별 제재 표의 class)의 무거운 순서."""
NOTE = "법률 자문이 아닙니다. 검토가 필요한 곳을 고를 뿐입니다."
SANCTION_NOTE = "법에 적힌 최대 제재입니다. 위반 판정이 아니며, 실제 부과는 위반 사실과 규모에 따라 다릅니다."
HEAVY = ("징역", "과징금")
TITLE_MIN = 16
"""제목에 남기는 가장 작은 폭. '어기면 · …'을 붙여 이보다 좁아지면 그것을 다음 줄로 내린다(80칸 창)."""
GOODS = "특정 품목을 판다면 확인할 것"
CITE_WHY = {
    "test-file": "테스트 파일",
    "too-short": "너무 짧음",
    "not-found": "파일에 없음",
    "no-such-file": "없는 파일",
    "comment-only": "주석만",
    "trailing-comment": "줄 끝 주석",
    "bare-word": "낱말 하나",
    "empty": "빈 인용",
    "outside-repo": "저장소 밖",
    "not-entry-file": "다른 파일",
}
"""관문이 인용을 받지 않은 까닭(why)의 이름."""
SEARCH_WHY = {
    "mismatch": ("달라", "결과가 다름"),
    "bad-pattern": ("검색식이 틀려", "검색식 오류"),
    "outside-repo": ("저장소 밖이라", "저장소 밖"),
    "no-count": ("수를 대지 않아", "수 없음"),
}
"""'없다' 검색을 근거로 쓰지 않은 까닭(why): (까닭이 하나일 때의 말, 여럿일 때의 이름)."""


def order_key(c: dict) -> tuple:
    """같은 갈래 안의 순서: 제재 등급, 정액 상한이 큰 것, 체크리스트 순서."""
    s = c.get("sanction") or {}
    cls = s.get("class")
    heavy = SANCTION_ORDER.index(cls) if cls in SANCTION_ORDER else len(SANCTION_ORDER)
    return (heavy, -(s.get("max_won") or 0), c.get("rank", 0))


def law_short(c: dict) -> str:
    """의무 표의 짧은 법 이름(law_short). 표에 없으면 결과의 법 이름."""
    from policyofficer.profile import load_duties

    global _SHORT
    if _SHORT is None:
        _SHORT = {d["id"]: d.get("law_short") or d["law"] for d in load_duties()}
    return _SHORT.get(c["duty"]) or c.get("law", "")


_SHORT: dict[str, str] | None = None


def _gated(doc: dict) -> tuple[list[dict], list[dict]]:
    """(모델이 댄 인용, '없다' 검색). review 의 run.citations·run.searches 가 센 것과 같은 범위다: 조사 답(프로필 신호
    why: profile 은 빼고)과 반박 답, 기능 파악의 흐름 마디·잇기·플랫폼 근거."""
    cl = doc.get("checklist", [])
    cites = [c for q in cl for c in (q.get("first") or {}).get("citations", []) if c.get("why") != "profile"]
    cites += [c for q in cl for c in (q.get("verification") or {}).get("citations", [])]
    flow = doc.get("data_flow", {})
    cites += [c for part in ("nodes", "edges") for x in flow.get(part, []) for c in x.get("citations", [])]
    cites += [c for x in doc.get("profile", {}).get("platform_evidence", []) for c in x.get("citations", [])]
    searches = [s for q in cl for s in (q.get("first") or {}).get("searches", [])]
    searches += [s for q in cl for s in (q.get("verification") or {}).get("searches", [])]
    return cites, searches


def _top(counts: dict[str, int], names: dict[str, str], dot: str) -> str:
    """거절 까닭을 많은 순으로 둘까지. 더 있으면 '등'."""
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    text = dot.join(f"{names.get(k, k)} {n}" for k, n in ranked[:2])
    return text + (" 등" if len(ranked) > 2 else "")


def tool_check(doc: dict, dot: str = " · ") -> list[str]:
    """'도구 대조 · 인용 54건 중 53건 받음(1건: 너무 짧음) · '없다' 검색 57건 중 51건 같음(6건은 달라 근거로 안 씀)'
    의 조각들('도구 대조' 뒤). 대조한 것이 없으면 빈 목록. 수는 run.citations·citations_rejected·searches·
    searches_rejected, 까닭은 결과에 남은 인용·검색의 why 에서 센다."""
    from collections import Counter

    run = doc.get("run", {})
    cites, searches = _gated(doc)
    parts = []
    n = run.get("citations", len(cites))
    bad = run.get("citations_rejected", sum(1 for c in cites if not c.get("ok")))
    if n:
        why = Counter(c.get("why") or "?" for c in cites if not c.get("ok"))
        if not bad:
            parts.append(f"인용 {n}건 모두 받음")
        else:
            k = next(iter(why))
            reason = CITE_WHY.get(k, k) if len(why) == 1 else _top(why, CITE_WHY, dot)
            parts.append(f"인용 {n}건 중 {n - bad}건 받음({bad}건: {reason})")
    n = run.get("searches", len(searches))
    bad = run.get("searches_rejected", sum(1 for x in searches if not x.get("ok")))
    if n:
        why = Counter(x.get("why") or "?" for x in searches if not x.get("ok"))
        if not bad:
            parts.append(f"'없다' 검색 {n}건 모두 같음")
        elif len(why) == 1:
            k = next(iter(why))
            phrase = SEARCH_WHY[k][0] if k in SEARCH_WHY else f"{k}(으)로"
            parts.append(f"'없다' 검색 {n}건 중 {n - bad}건 같음({bad}건은 {phrase} 근거로 안 씀)")
        else:
            names = {k: v[1] for k, v in SEARCH_WHY.items()}
            parts.append(f"'없다' 검색 {n}건 중 {n - bad}건 같음({bad}건은 근거로 안 씀: {_top(why, names, dot)})")
    return parts


def home(path: str | Path) -> str:
    p, h = str(path), str(Path.home())
    return "~" + p[len(h) :] if p == h or p.startswith(h + os.sep) else p


def render(doc: dict, saved: str | Path | None, color: bool, cols: int | None, unicode: bool = True) -> str:
    """`cols` 가 None 이면 줄을 자르지 않는다(stdout 이 터미널이 아닐 때)."""
    g = Glyphs(unicode)
    dot = f" {g.dot} "
    run = doc.get("run", {})
    checklist = doc.get("checklist", [])
    lines: list[tuple[str, str | None]] = []

    def add(text: str = "", style: str | None = None, lead: str | None = None) -> None:
        """`lead` 가 있으면 그 뒤의 글(경로)은 앞을 잘라 끝(파일 이름)을 남긴다."""
        if lead is not None:
            text = lead + (fit_tail(text, cols - width(lead), g.more) if cols is not None else text)
        elif cols is not None:
            text = fit(text, cols, g.more)
        lines.append((text, style))

    def note(text: str) -> None:
        """자르지 않고 폭에 맞춰 줄을 나눈다(주의 문구)."""
        for line in wrap(text, cols) if cols is not None else [text]:
            lines.append((line, "dim"))

    asked = len(run.get("questions", []))
    usd = run.get("usd_estimate", 0)
    todo_n = sum(1 for c in checklist if c["status"] in TO_CHECK)
    heavy_n = sum(
        1
        for c in checklist
        if c["status"] in TO_CHECK and c.get("group") != "goods" and (c.get("sanction") or {}).get("class") in HEAVY
    )
    found = f"확인할 것 {todo_n}건" + (f"({'·'.join(HEAVY)} {heavy_n}건)" if heavy_n else "")
    head = f"{g.done} 검토 끝{dot}{found}{dot}{clock(run.get('seconds', 0))}{dot}어림 ${usd:.2f}{dot}질문 {asked}개"
    add(head, "bold")
    add()
    counts = {s: sum(1 for c in checklist if c["status"] == s) for s in ORDER}
    label_w = max(width(STATUS_LABEL[s]) for s in ORDER if counts[s]) if any(counts.values()) else 0
    for s in ORDER:
        if counts[s]:
            add(f"  {pad(STATUS_LABEL[s], label_w)}  {counts[s]:>3}", "bold" if s in TO_CHECK else None)
    todo = [c for c in checklist if c["status"] in TO_CHECK]
    sections, n = [], 0
    for s in TO_CHECK:
        items = sorted((c for c in todo if c["status"] == s and c.get("group") != "goods"), key=order_key)
        goods = [c for c in todo if c["status"] == s and c.get("group") == "goods"]
        rows = []
        for c in items:
            n += 1
            sanction = c.get("sanction")
            heavy = bool(sanction) and sanction.get("class") in HEAVY
            head = f"{'!!' if heavy else '  '}{n:>2}  {clean(law_short(c))} {article(c.get('article', ''))}{dot}"
            tail = f"  어기면{dot}{clean(sanction['label'])}" if sanction else ""
            rows.append((c, head, clean(title(c.get("title", ""))), tail, "heavy" if heavy else None))
        if rows or goods:
            sections.append((s, rows, goods))
    # '어기면 · …'은 모든 줄에 제목이 TITLE_MIN 칸 넘게 남을 때만 줄 끝에 둔다. 아니면 모두 다음 줄(한 모양으로)
    rows_ = [r for _, rows, _ in sections for r in rows if r[3]]
    inline = cols is None or all(cols - width(head) - width(tail) >= TITLE_MIN for _, head, _, tail, _ in rows_)
    for s, rows, goods in sections:
        add()
        add(f"{STATUS_LABEL[s]} ({len(rows) + len(goods)})", "bold")
        for c, head, name, tail, style in rows:
            if inline:
                room = None if cols is None else cols - width(head) - width(tail)
                add(head + (name if room is None else fit(name, room, g.more)) + tail, style)
            else:
                add(head + name, style)
                if tail:
                    add(f"      {tail.strip()}", style)
            cite = next((x for x in c.get("citations", []) if x.get("ok")), None)
            if cite:
                where = f"{cite['file']}:{cite['line']}" if cite.get("line") else cite["file"]
                add(clean(where), "dim", lead="      ")
        if goods:
            add(f"   {g.more} {GOODS} {len(goods)}개", "dim")
    add()
    if saved:
        add(home(saved), lead="전체 결과(JSON): ")
    checked = tool_check(doc, dot)
    if checked:
        # 좁으면 ' · ' 사이에서 나누고 이어지는 줄은 첫 조각 밑에 맞춘다
        lead = f"도구 대조{dot}"
        ind = " " * width(lead)
        groups, cur = [], lead + checked[0]
        for part in checked[1:]:
            if cols is None or width(cur + dot + part) <= cols:
                cur += dot + part
            else:
                groups.append(cur)
                cur = ind + part
        groups.append(cur)
        for line in groups:
            if cols is None or width(line) <= cols:
                lines.append((line, None))
                continue
            # 조각 하나가 폭을 넘으면 빈칸에서 나눈다(자르지 않는다)
            first, *rest = wrap(line.removeprefix(ind), max(cols - width(ind), 10))
            lines.append(((ind if line.startswith(ind) else "") + first, None))
            lines += [(ind + piece, None) for piece in rest]
    if any(c.get("sanction") for c in todo):
        note(SANCTION_NOTE)
    note(NOTE)
    return "".join((f"\x1b[{SGR[s]}m{t}\x1b[0m" if color and s and t else t) + "\n" for t, s in lines)
