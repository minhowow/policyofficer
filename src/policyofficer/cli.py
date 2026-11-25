"""명령줄 진입점. `policyofficer [폴더]` 는 그 폴더를 검토하고(review 와 같고 기본값 셋이 다르다), 첫 인자가 명령
이름이면 그 명령이다(profile · review · replay).

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


QUICK = {"batch": "bundle", "rebut_scope": "found", "max_usd": 2.0}
"""한 줄 명령(`policyofficer [폴더]`)에서만 다른 기본값. 11/24 jobtalk 실제 실행(haiku 조사 + sonnet 반박, 묶음·found)이
155초, $0.47 이었다. `policyofficer review` 의 기본값은 그대로다(웹 실행기가 쓴다)."""

USAGE = "policyofficer [폴더] [옵션]\n       policyofficer <명령> ..."
DESCRIPTION = """폴더의 코드를 AI 가 읽어, 걸릴 수 있는 국내 법 의무마다 근거(파일:줄)와 법에 적힌 제재를 낸다.

  policyofficer [폴더]   폴더를 검토한다(기본: 지금 폴더). 터미널이면 요약, 파이프면 JSON.
                         review 의 옵션을 받고 기본값만 다르다: --batch bundle · --rebut-scope found · --max-usd 2
                         옵션 보기: policyofficer . -h"""


def build_parser() -> argparse.ArgumentParser:
    p = _Parser(
        prog="policyofficer", usage=USAGE, description=DESCRIPTION, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--version", action="version", version=f"policyofficer {__version__}")
    sub = p.add_subparsers(dest="command", metavar="<명령>", title="명령", parser_class=_Parser)

    pr = sub.add_parser(
        "profile", help="폴더가 하는 일(기능)과 그 기능에 걸릴 수 있는 의무를 JSON 으로 낸다(모델 호출 0회)"
    )
    pr.add_argument("path", help="폴더")

    rv = sub.add_parser(
        "review",
        help="폴더의 코드를 읽어 의무마다 근거를 찾아 체크리스트를 낸다(한 줄 명령과 같고 기본값이 다르다)",
    )
    _review_args(rv, quick=False)

    rp = sub.add_parser("replay", help="저장된 review 결과로 진행 화면을 다시 그린다(모델·네트워크 호출 0회)")
    rp.add_argument("file", help="review 결과 JSON")
    rp.add_argument("--speed", type=float, default=4.0, help="원래보다 몇 배 빠르게(기본 4)")
    _progress_args(rp)
    return p


def quick_parser() -> argparse.ArgumentParser:
    q = _Parser(prog="policyofficer", usage="policyofficer [폴더] [옵션]", description=DESCRIPTION.split("\n")[0])
    _review_args(q, quick=True)
    return q


def _review_args(p: argparse.ArgumentParser, quick: bool) -> None:
    """review 의 인자. 한 줄 명령(`quick`)은 폴더를 빼도 되고(지금 폴더) 기본값 셋이 다르다(QUICK)."""
    if quick:
        p.add_argument("path", nargs="?", default=".", help="검토할 폴더(기본: 지금 폴더)")
    else:
        p.add_argument("path", help="검토할 폴더")
    batch = QUICK["batch"] if quick else "duty"
    scope = QUICK["rebut_scope"] if quick else "all"
    usd = QUICK["max_usd"] if quick else 5.0
    p.add_argument("--model", default="anthropic:claude-haiku-5-5", help="기능 파악·의무별 조사 모델")
    p.add_argument("--checker", default="anthropic:claude-sonnet-5-5", help="반박 모델(다른 모델을 쓴다)")
    p.add_argument(
        "--no-rebut", action="store_true", help="반박을 묻지 않는다(결과의 run.rebut 이 false, 비용이 약 절반)"
    )
    p.add_argument(
        "--rebut-scope",
        default=scope,
        choices=["all", "found"],
        help=f"반박할 항목(기본 {scope}). all: 코드에서 본 것·저장소 밖·충족·해당 없음·걸리지 않는 듯, "
        "found: 코드에서 본 것·충족 근거 있음만(나머지는 verification not-run, why rebut-scope)",
    )
    p.add_argument(
        "--batch",
        default=batch,
        choices=["duty", "feature", "bundle"],
        help=f"질문 하나에 넣는 의무(기본 {batch}). duty: 하나, feature: 기능 하나(8개까지), bundle: 표의 묶음(같은 "
        "기능·같은 코드 범위를 보는 의무 4개까지). 답과 관문은 어느 쪽이든 의무마다다",
    )
    p.add_argument("--max-usd", type=float, default=usd, help=f"한 번의 어림 금액 상한(공식 단가, 기본 {usd:g})")
    p.add_argument("--time-limit", type=float, default=360.0, help="한 번의 시간 상한(초, 기본 360)")
    p.add_argument("--concurrency", type=int, default=6, help="동시에 묻는 질문 수(429 를 받으면 줄인다, 기본 6)")
    p.add_argument("--plan", action="store_true", help="모델을 부르지 않고 물을 의무와 질문 수만 낸다")
    p.add_argument(
        "--reuse",
        default=None,
        metavar="REVIEW_JSON",
        help="같은 폴더·커밋의 앞 review 결과. 기능 파악(서비스 요약·기능·개인정보 흐름)을 묻지 않고 그대로 쓴다",
    )
    _progress_args(p)
    p.add_argument(
        "-o",
        "--output",
        default=None,
        metavar="FILE",
        help="결과 JSON 을 이 파일에도 쓴다. 기본: stdout 이 터미널이면 "
        "${XDG_CACHE_HOME:-~/.cache}/policyofficer/reviews/<폴더>-<커밋 12자>.json, 아니면 쓰지 않는다",
    )
    p.add_argument("--json", action="store_true", help="stdout 이 터미널이어도 요약 대신 JSON 을 낸다")


def _progress_args(p: argparse.ArgumentParser) -> None:
    from policyofficer.report.progress import MODES

    p.add_argument(
        "--progress",
        default="auto",
        choices=list(MODES),
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


def _folder(path: str) -> Path:
    root = Path(path)
    if root.is_dir():
        return root
    if root.exists():
        raise ConfigError(f"폴더를 주세요. {path} 는 파일입니다(파일 하나는 검토하지 않습니다)")
    raise ConfigError(f"폴더가 없습니다: {path}")


def cmd_profile(args) -> int:
    from policyofficer.profile import profile

    root = _folder(args.path)
    print(json.dumps(profile(root.resolve()), ensure_ascii=False, indent=2))
    return EXIT_OK


def cmd_review(args) -> int:
    from policyofficer import review as rv

    root = _folder(args.path)
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
        hint = "(키 없이는 --plan 으로 물을 의무와 질문 수를 볼 수 있습니다)" if "ANTHROPIC_API_KEY" in str(e) else ""
        raise ConfigError(f"{e}{hint}") from e
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
    """터미널에서 돌린 review 의 결과를 둘 곳. 검토하는 폴더 안에는 파일을 만들지 않는다."""
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
    from policyofficer.review import with_highlights, with_tables

    duties = {d["id"]: d for d in load_duties()}
    for c in doc["checklist"]:
        with_tables(c, duties)  # 제재·조문 표기는 지금 표의 글로 다시 그린다(판정과 인용은 파일 그대로)
    with_highlights(doc)  # 먼저 볼 것이 없는 옛 결과에도 같은 함수로
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


def _quick_args(argv: list[str]) -> argparse.Namespace:
    """`policyofficer [폴더] [옵션]`. 첫 인자가 옵션이 아니면 폴더여야 한다(같은 이름의 폴더는 `./review` 처럼 준다)."""
    first = argv[0] if argv and not argv[0].startswith("-") else None
    if first is not None and not Path(first).exists():
        raise ConfigError(f"{first}: 명령도 폴더도 아닙니다(명령: {' · '.join(COMMANDS)}). 폴더라면 경로를 확인하세요")
    args = quick_parser().parse_args(argv)
    args.command = "review"
    return args


def _main(argv: list[str] | None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        if argv and (argv[0] in COMMANDS or argv[0] in ("-h", "--help", "--version")):
            args = build_parser().parse_args(argv)
            if args.command is None:
                return EXIT_ERROR
        else:
            args = _quick_args(argv)
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
