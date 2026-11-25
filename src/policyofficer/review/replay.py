"""기록 재생(`policyofficer replay`): 저장된 review 결과로 진행 사건을 다시 만들어 같은 표시기로 그린다.
모델과 네트워크를 한 번도 부르지 않는다.

쓰는 것: run.questions(stage·duties·started·seconds·usd·failure·tool_calls·sent.read·sent.searches·repaired)와
checklist(조사 답 first, 반박 verification). 결과에 없는 것은 이렇게 채운다.
  - 기능 신호의 시간: 기록에 없다. 0초에 시작해 첫 질문 앞에 끝난 것으로 그린다(옛 결과의 그 사이에는 이제 없는
    단계의 시간도 들어 있다).
  - 도구 호출의 순서: 기록은 읽은 파일과 검색어를 따로 모은다(같은 파일을 두 번 읽은 것은 하나). 둘을 번갈아 질문의
    시간 안에 고르게 놓는다.
  - 상한에 걸려 보내지 않은 질문: 기록에 시각이 없어 바로 앞 질문이 끝난 때에 놓는다.
  - 429 로 동시 수를 줄인 것: 시각이 없어 의무별 조사가 시작할 때 한 번 알린다.
"""

from __future__ import annotations

import time
from collections.abc import Callable

from policyofficer.review import events as E
from policyofficer.review import feature_counts, first_cite
from policyofficer.review.prompts import STATUS_LABEL

STAGE_OF = {"understand": "understand", "investigate": "investigate", "rebut": "rebut"}


def _duties(ids: list[str], items: dict[str, dict], short: dict[str, str]) -> tuple[E.Duty, ...]:
    out = []
    for did in ids:
        c = items.get(did, {})
        out.append(E.Duty(did, short.get(did) or c.get("law", ""), c.get("article", ""), c.get("title", "")))
    return tuple(out)


def _tools(rec: dict) -> list[tuple[str, str]]:
    sent = rec.get("sent") or {}
    reads = [("read_file", p) for p in sent.get("read", [])]
    finds = [("search", p) for p in sent.get("searches", [])]
    out = []
    for i in range(max(len(reads), len(finds))):
        out += [x[i] for x in (finds, reads) if i < len(x)]
    return out


def _status(status: str | None) -> str:
    return status if status in STATUS_LABEL else "unknown"


def timeline(doc: dict, short: dict[str, str] | None = None) -> tuple[E.Begin, list[tuple[float, E.Event]]]:
    """(머리, [(원래 실행의 초, 사건)]). 사건은 시각 순이고, 같은 시각이면 만든 순서다."""
    from policyofficer.profile import load_duties

    short = short if short is not None else {d["id"]: d.get("law_short") or d["law"] for d in load_duties()}
    run, prof = doc.get("run", {}), doc.get("profile", {})
    items = {c["duty"]: c for c in doc.get("checklist", [])}
    qs = list(run.get("questions", []))
    limits = run.get("limits", {})
    models = run.get("models", {})
    rebut_on = run.get("rebut", True)
    begin = E.Begin(
        repo="",
        commit=prof.get("commit"),
        model=models.get("investigate", ""),
        checker=models.get("verify") if rebut_on and models.get("verify") not in (None, "none") else None,
        batch=run.get("batch", ""),
        usd=limits.get("usd", 0.0),
        seconds=limits.get("seconds", 0.0),
        concurrency=limits.get("concurrency", 1),
        replay=run.get("seconds", 0.0),
    )
    out: list[tuple[float, int, E.Event]] = []

    def at(t: float, ev: E.Event) -> None:
        out.append((t, len(out), ev))

    timed = [q for q in qs if "started" in q]
    first_q = min((q["started"] for q in timed), default=run.get("seconds", 0.0))
    signal = sum(1 for f in prof.get("features", []) if "signal" in f.get("sources", []))
    at(0.0, E.Stage("profile", "start"))
    at(first_q, E.Stage("profile", "end", {"features": signal, "platforms": prof.get("platforms", [])}))

    und = run.get("understanding", {})
    flow = doc.get("data_flow", {})
    detail = {**feature_counts(prof.get("features", [])), "nodes": len(flow.get("nodes", []))}
    detail["answered"] = und.get("answered", True)
    inv = [q for q in qs if q.get("stage") == "investigate"]
    reb = [q for q in qs if q.get("stage") == "rebut"]
    if und.get("reused"):
        at(first_q, E.Stage("understand", "skip", {**detail, "why": "reused"}))
    else:
        at(first_q, E.Stage("understand", "start"))
        at(first_q, E.Planned(1))
    inv_start = min((q["started"] for q in inv if "started" in q), default=None)
    if inv:
        t = inv_start if inv_start is not None else first_q
        at(t, E.Planned(len(inv) + len(reb)))
        duties_n = len({d for q in inv for d in q.get("duties", [])})
        at(t, E.Stage("investigate", "start", {"questions": len(inv), "duties": duties_n}))
        for c in run.get("concurrency", [])[:1]:
            if c.get("rate_limited"):
                at(t, E.Notice("throttle", status=429, before=c.get("start"), after=c.get("end")))
    if not rebut_on:
        at(inv_start or first_q, E.Stage("rebut", "skip", {"why": "off"}))

    last = first_q
    once: set[str] = set()
    ends = {"understand": None, "investigate": None, "rebut": None, "gate": None}
    for i, rec in enumerate(qs, 1):
        stage = rec.get("stage", "investigate")
        duties = _duties(rec.get("duties", []), items, short)
        failure = rec.get("failure")
        if "started" not in rec:  # 상한에 걸려 보내지 않은 질문
            if failure in ("cost-cap", "time-cap") and failure not in once:
                once.add(failure)
                at(last, E.Notice(failure))
            at(last, E.Answered(i, stage, failure=failure, duties=duties))
            if stage == "understand":
                at(last, E.Stage("understand", "end", {**detail, "answered": False}))
            continue
        start, end = rec["started"], rec["started"] + rec.get("seconds", 0.0)
        if stage == "rebut" and "rebut" not in once:
            once.add("rebut")
            at(start, E.Stage("rebut", "start"))
        at(start, E.Asked(i, stage, duties))
        tools = _tools(rec)
        for k, (name, target) in enumerate(tools, 1):
            at(start + (end - start) * k / (len(tools) + 1), E.Tool(i, name, target))
        results, cites, searches = [], [], []
        for d in duties:
            c = items.get(d.id, {})
            first = c.get("first") or {}
            if stage == "rebut":
                v = c.get("verification", {})
                turned = v.get("result") == "overturned"
                status = _status(c.get("status") if turned else first.get("status"))
                cs = v.get("citations", [])
                results.append(
                    E.Result(d.id, status, first_cite(cs if turned else first.get("citations", [])), v.get("result"))
                )
                cites += cs
                searches += v.get("searches", [])
            else:
                results.append(E.Result(d.id, _status(first.get("status")), first_cite(first.get("citations", []))))
                cites += first.get("citations", [])
                searches += first.get("searches", [])
        cites = [c for c in cites if c.get("why") != "profile"]
        if cites or searches:
            if "gate" not in once:
                once.add("gate")
                at(end, E.Stage("gate", "start"))
            ok_c = sum(1 for c in cites if c.get("ok"))
            at(end, E.Checked(i, len(cites), ok_c, len(searches), sum(1 for s in searches if s.get("ok"))))
            ends["gate"] = end
        if rec.get("repaired") is not None:
            at(end, E.Notice("repair", q=i))
        if failure in ("time-cap",) and failure not in once:
            once.add(failure)
            at(end, E.Notice(failure))
        at(
            end,
            E.Answered(
                i,
                stage,
                rec.get("usd", 0.0),
                rec.get("seconds", 0.0),
                failure,
                duties,
                tuple(results),
                rec.get("tool_calls", 0),
            ),
        )
        ends[stage] = max(ends[stage] or 0.0, end)
        if stage == "understand":
            at(end, E.Stage("understand", "end", detail))
        last = max(last, end)

    total = max(run.get("seconds", 0.0), last)
    if inv:
        at(ends["investigate"] or total, E.Stage("investigate", "end"))
    else:
        at(first_q, E.Stage("investigate", "skip", {"why": "nothing"}))
    if rebut_on:
        at(total, E.Stage("rebut", "end") if reb else E.Stage("rebut", "skip", {"why": "nothing"}))
    at(total, E.Stage("gate", "end") if ends["gate"] is not None else E.Stage("gate", "skip", {"why": "nothing"}))
    out.sort(key=lambda x: (x[0], x[1]))
    return begin, [(t, ev) for t, _, ev in out]


def play(
    events: list[tuple[float, E.Event]],
    emit: E.Sink,
    speed: float,
    total: float,
    now: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> None:
    """사건을 원래 시각의 1/speed 로 낸다. 마지막 사건 뒤에는 원래 걸린 시간(`total`)까지 기다린다."""
    t0 = now()
    for t, ev in [*events, (total, None)]:
        wait = t / speed - (now() - t0)
        if wait > 0:
            sleep(wait)
        if ev is not None:
            emit(ev)
