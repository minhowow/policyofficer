"""명령줄 진입점.

종료 코드: 0 끝까지 돌았다 · 2 도구 오류(폴더가 없음, 인자가 잘못됨, 키가 없음 등) · 130 Ctrl+C.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback
from pathlib import Path

from policyofficer import __version__
from policyofficer.errors import EXIT_ERROR, EXIT_OK, ConfigError, PolicyofficerError


class _Parser(argparse.ArgumentParser):
    """명령줄 오류도 다른 오류처럼 '오류: …' 로 알리고 2로 끝낸다. argparse 의 영어 문구는 그대로 둔다."""

    def error(self, message: str):
        self.print_usage(sys.stderr)
        self.exit(EXIT_ERROR, f"오류: {message}\n")


def build_parser() -> argparse.ArgumentParser:
    p = _Parser(prog="policyofficer", description="국내 법·정책 관점 코드 검토")
    p.add_argument("--version", action="version", version=f"policyofficer {__version__}")
    sub = p.add_subparsers(dest="command", metavar="<명령>", parser_class=_Parser)

    pr = sub.add_parser(
        "profile", help="저장소가 하는 일(기능)과 그 기능에 걸릴 수 있는 의무를 JSON 으로 낸다 (모델 호출 0회)"
    )
    pr.add_argument("path", help="저장소 폴더")

    rv = sub.add_parser(
        "review",
        help="저장소를 읽어 서비스·개인정보 흐름·걸리는 의무를 정리하고, 의무마다 근거를 찾아 체크리스트를 낸다(JSON)",
    )
    rv.add_argument("path", help="저장소 폴더")
    rv.add_argument("--model", default="anthropic:claude-haiku-5-5", help="이해·근거 찾기 모델")
    rv.add_argument("--checker", default="anthropic:claude-sonnet-5-5", help="반박 검증 모델(다른 모델을 쓴다)")
    rv.add_argument(
        "--no-rebut", action="store_true", help="반박 검증을 묻지 않는다(결과의 run.rebut 이 false, 비용이 약 절반)"
    )
    rv.add_argument(
        "--rebut-scope",
        default="all",
        choices=["all", "found"],
        help="반박할 항목. all(기본): 코드에서 본 것·저장소 밖·충족·해당 없음·걸리지 않는 듯, "
        "found: 코드에서 본 것·충족 근거 있음만(나머지는 verification not-run, why rebut-scope)",
    )
    rv.add_argument(
        "--batch",
        default="duty",
        choices=["duty", "feature", "bundle"],
        help="질문 하나에 의무 하나(기본), 기능 하나(의무 8개까지), 또는 표의 묶음(같은 기능·같은 코드 범위를 보는 "
        "의무 "
        "4개까지, 답과 관문은 의무마다). 11/11 실측: duty 가 feature 보다 인용이 많고 비용은 1.8배",
    )
    rv.add_argument("--max-usd", type=float, default=5.0, help="저장소 한 번의 어림 금액 상한(공식 단가, 기본 5)")
    rv.add_argument("--time-limit", type=float, default=360.0, help="저장소 한 번의 시간 상한(초, 기본 360)")
    rv.add_argument("--concurrency", type=int, default=6, help="동시에 묻는 질문 수(429 를 받으면 줄인다, 기본 6)")
    rv.add_argument("--plan", action="store_true", help="모델을 부르지 않고 물을 의무와 질문 수만 낸다")
    rv.add_argument(
        "--reuse",
        default=None,
        metavar="REVIEW_JSON",
        help="같은 저장소·커밋의 앞 review 결과. 이해 단계(서비스 요약·기능·개인정보 흐름)를 묻지 않고 그대로 쓴다",
    )
    _progress_args(rv)
    rv.add_argument(
        "-o",
        "--output",
        default=None,
        metavar="FILE",
        help="결과 JSON 을 이 파일에도 쓴다. 기본: stdout 이 터미널이면 "
        "${XDG_CACHE_HOME:-~/.cache}/policyofficer/reviews/<저장소>-<커밋 12자>.json, 아니면 쓰지 않는다",
    )
    rv.add_argument("--json", action="store_true", help="stdout 이 터미널이어도 요약 대신 JSON 을 낸다")

    rp = sub.add_parser("replay", help="저장된 review 결과로 진행 화면을 다시 그린다(모델·네트워크 호출 0회)")
    rp.add_argument("file", help="review 결과 JSON")
    rp.add_argument("--speed", type=float, default=4.0, help="원래보다 몇 배 빠르게(기본 4)")
    _progress_args(rp)
    return p


def _progress_args(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--progress",
        default="auto",
        choices=["auto", "tty", "plain", "none"],
        help="진행 표시(stderr). auto(기본): 터미널이면 tty(제자리에서 다시 그림), CI·파이프·파일이면 plain(사건마다 "
        "한 줄, 제어 문자 없음). none: 그리지 않는다. NO_COLOR 가 있으면 색만 끈다",
    )


def _redact(value: str) -> str:
    """주소에 붙은 계정·토큰(user:pass@, ?key=)은 CI 로그에 남기지 않는다. 목적지(scheme://host:port/path)만 적는다.
    주소로 읽지 못하면 값을 싣지 않는다 — 알림 한 줄 때문에 검사가 멈추면 안 된다."""
    from urllib.parse import urlsplit

    try:
        parts = urlsplit(value)
    except ValueError:
        return "(주소를 읽지 못함)"
    if not parts.scheme or not parts.netloc:
        return "(주소를 읽지 못함)" if "@" in value or "?" in value else value
    return f"{parts.scheme}://{parts.netloc.rpartition('@')[2]}{parts.path}"


# ── profile · review · replay ──────────────────────────────────────────────


def cmd_profile(args) -> int:
    from policyofficer.profile import profile

    root = Path(args.path)
    if not root.is_dir():
        raise ConfigError(f"폴더가 아닙니다: {args.path}")
    print(json.dumps(profile(root.resolve()), ensure_ascii=False, indent=2))
    return EXIT_OK


def cmd_review(args) -> int:
    from policyofficer import review as rv

    root = Path(args.path)
    if not root.is_dir():
        raise ConfigError(f"폴더가 아닙니다: {args.path}")
    if args.plan:
        print(json.dumps(rv.plan(root), ensure_ascii=False, indent=2))
        return EXIT_OK
    if args.max_usd <= 0 or args.time_limit <= 0 or args.concurrency < 1:
        raise ConfigError("--max-usd·--time-limit 는 0 보다, --concurrency 는 1 이상이어야 합니다")
    throttles = (rv.Throttle(args.concurrency), rv.Throttle(args.concurrency))
    try:
        investigator = rv.build_judge(args.model, throttles[0])
        checker = investigator if args.no_rebut else rv.build_judge(args.checker, throttles[1])
    except ValueError as e:
        raise ConfigError(str(e)) from e
    from policyofficer.judge.http import endpoint
    from policyofficer.report import progress
    from policyofficer.review.events import Begin

    reuse = None
    if args.reuse:
        try:
            reuse = json.loads(Path(args.reuse).read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            raise ConfigError(f"--reuse 파일을 읽지 못했습니다: {e}") from e
        before, now = (reuse.get("profile") or {}).get("commit"), rv.commit_of(root.resolve())
        if before and now and before != now:
            print(f"알림: --reuse 의 커밋({before[:12]})과 지금 커밋({now[:12]})이 다릅니다", file=sys.stderr)
    limits = rv.Limits(
        args.max_usd,
        args.time_limit,
        args.concurrency,
        args.batch,
        rebut=not args.no_rebut,
        rebut_scope=args.rebut_scope,
    )
    begin = Begin(
        repo=root.resolve().name,
        commit=rv.commit_of(root.resolve()),
        model=args.model,
        checker=None
        if args.no_rebut
        else args.checker + ("" if args.rebut_scope == "all" else f"({args.rebut_scope})"),
        batch=args.batch,
        usd=args.max_usd,
        seconds=args.time_limit,
        concurrency=args.concurrency,
        egress=_redact(endpoint()),
    )
    summary = sys.stdout.isatty() and not args.json
    with progress.make(args.progress, sys.stderr) as shown:
        shown.begin(begin)
        try:
            doc = rv.review(
                root,
                investigator,
                checker,
                limits,
                throttles=throttles,
                reuse=reuse,
                progress=shown.emit,
            )
        except KeyboardInterrupt:
            if shown.interrupted():
                return 130
            raise
        shown.finish(line=not summary)
    _display_error(shown)
    text = json.dumps(doc, ensure_ascii=False, indent=2)
    saved = Path(args.output) if args.output else (_review_path(root.resolve(), doc) if summary else None)
    if saved is not None:
        try:
            saved.parent.mkdir(parents=True, exist_ok=True)
            saved.write_text(text + "\n", encoding="utf-8")
        except OSError as e:
            print(f"알림: 결과를 {saved} 에 쓰지 못했습니다({e}). stdout 에 JSON 으로 냅니다.", file=sys.stderr)
            saved, summary = None, False
    if summary:
        _print_summary(doc, saved)
    else:
        print(text)
    return EXIT_OK


def _review_path(root: Path, doc: dict) -> Path:
    """터미널에서 돌린 review 의 결과를 둘 곳. 분석하는 저장소 안에는 파일을 만들지 않는다."""
    commit = (doc.get("profile") or {}).get("commit")
    tag = commit[:12] if commit else time.strftime("%Y%m%d-%H%M%S")
    cache = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(cache) / "policyofficer" / "reviews" / f"{root.name}-{tag}.json"


def _print_summary(doc: dict, saved: Path | None) -> None:
    from policyofficer.report import progress
    from policyofficer.report.review_text import render

    tty = sys.stdout.isatty()
    cols = progress.size(sys.stdout)[0] - 1 if tty else None
    sys.stdout.write(render(doc, saved, tty and progress.color(), cols, progress.utf8(sys.stdout)))
    sys.stdout.flush()


def _display_error(shown) -> None:
    if shown.error is not None:
        print(
            f"알림: 진행 표시를 그리다 오류가 나 표시를 껐습니다({shown.error!r}). 결과에는 영향이 없습니다.",
            file=sys.stderr,
        )


def cmd_replay(args) -> int:
    """저장된 review 결과로 진행 사건을 다시 만들어 같은 표시기로 그린다. 모델·네트워크를 부르지 않는다."""
    import dataclasses

    from policyofficer.report import progress
    from policyofficer.review import replay

    path = Path(args.file)
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise ConfigError(f"review 결과를 읽지 못했습니다: {e}") from e
    if not isinstance(doc, dict) or "checklist" not in doc or "run" not in doc:
        raise ConfigError(f"review 결과가 아닙니다(checklist·run 이 없음): {args.file}")
    if not args.speed > 0:
        raise ConfigError("--speed 는 0 보다 커야 합니다")
    from policyofficer.profile import load_duties
    from policyofficer.review import with_tables

    duties = {d["id"]: d for d in load_duties()}
    for c in doc["checklist"]:
        with_tables(c, duties)  # 제재·조문 표기는 지금 표의 글로 다시 그린다(판정과 인용은 파일 그대로)
    begin, events = replay.timeline(doc)
    begin = dataclasses.replace(begin, repo=_replay_name(path, begin.commit))
    total = float(doc["run"].get("seconds") or 0.0)
    start = [0.0]
    shown = progress.make(args.progress, sys.stderr, clock_=lambda: (time.monotonic() - start[0]) * args.speed)
    with shown:
        start[0] = time.monotonic()
        shown.begin(begin)
        try:
            replay.play(events, shown.emit, args.speed, total)
        except KeyboardInterrupt:
            if shown.interrupted():
                return 130
            raise
        shown.finish(line=not sys.stdout.isatty())
    _display_error(shown)
    _print_summary(doc, path)
    return EXIT_OK


def _replay_name(path: Path, commit: str | None) -> str:
    """결과 파일 이름에서 저장소 이름. review 가 두는 '<저장소>-<커밋 12자>.json' 의 커밋과 '<이름>.review.json' 의
    '.review' 를 뗀다."""
    name = path.stem.removesuffix(".review")
    if commit and name.endswith(f"-{commit[:12]}"):
        name = name[: -len(commit[:12]) - 1]
    return name or path.stem


COMMANDS = {
    "profile": cmd_profile,
    "review": cmd_review,
    "replay": cmd_replay,
}


def _sigterm_exits():
    """SIGTERM 을 정상 종료로 바꾼다. 기본 SIGTERM 은 finally 와 atexit 를 돌리지 않아, CI 취소나 `timeout` 으로
    끝날 때 정리(숨긴 커서 되살리기 등)를 건너뛴다. 주 스레드에서만 걸 수 있다. 원래 처리기를 돌려준다."""
    import signal
    import threading

    if threading.current_thread() is not threading.main_thread():
        return None
    return signal.signal(signal.SIGTERM, lambda signum, _frame: sys.exit(128 + signum))


def main(argv: list[str] | None = None) -> int:
    previous = _sigterm_exits()
    try:
        return _main(argv)
    except KeyboardInterrupt:
        # 진행 표시의 finally 가 이미 터미널을 되돌렸다. 파이썬 traceback 대신 한 줄로 알린다
        print("\n중단했습니다.", file=sys.stderr)
        return 130
    finally:
        if previous is not None:
            import signal

            signal.signal(signal.SIGTERM, previous)


def _main(argv: list[str] | None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return EXIT_ERROR
    try:
        return COMMANDS[args.command](args)
    except PolicyofficerError as e:
        print(f"오류: {e}", file=sys.stderr)
        return e.exit_code
    except Exception:  # noqa: BLE001
        # 처리하지 못한 예외로 파이썬이 1로 끝나면 CI 는 "검토할 것이 있다"로 읽는다. 도구 오류는 2다.
        traceback.print_exc()
        print("오류: policyofficer 내부 오류입니다. 위 내용을 붙여 알려 주세요.", file=sys.stderr)
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
