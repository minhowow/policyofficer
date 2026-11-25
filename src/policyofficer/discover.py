"""폴더에서 볼 파일을 고른다: 기능 신호를 찾을 JS·TS 파일(code_files)과 판정기의 도구가 보는 파일(project_files).

git 저장소면 git 이 아는 파일(추적 파일과 무시되지 않은 새 파일)을 쓰고 `.gitignore` 를 그대로 따른다. 아니면 폴더를
걷는다. 어느 쪽이든 생성물 디렉터리(SKIP_DIRS) 아래는 보지 않는다. **시험 디렉터리는 빼지 않는다.** 법 검토 도구가
사용자의 test 디렉터리를 말없이 건너뛰면 쓸모가 없다.
"""

from __future__ import annotations

import os
import subprocess
from contextlib import contextmanager
from pathlib import Path

#: 들어가 봐야 소용없는 디렉터리. 사용자 코드가 아니다.
SKIP_DIRS = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        "node_modules",
        ".venv",
        "venv",
        "__pycache__",
        "dist",
        "build",
        ".next",
        ".nuxt",
        ".output",
        "coverage",
        ".pytest_cache",
        ".ruff_cache",
        ".mypy_cache",
        "vendor",
        # Yarn Berry 가 만든 것(플러그인·릴리스·SDK·PnP 캐시). 사용자 코드가 아니다
        ".yarn",
    }
)

MAX_BYTES = 1_000_000
"""이보다 큰 파일은 건너뛴다. 대개 번들·생성물이다."""

#: 축소·번들된 생성물. 한 줄에 수만 자라 읽을 수도 고칠 수도 없고(고치려면 원본을 고친다), 1MB 미만인 것이 많아
#: MAX_BYTES 로는 걸러지지 않는다.
GENERATED_SUFFIXES = (
    ".min.js",
    ".min.mjs",
    ".min.cjs",
    ".bundle.js",
    ".min.jsx",
    ".min.ts",
    ".min.tsx",
    # Yarn Plug'n'Play 가 저장소 루트에 만드는 해석기. 사용자 코드가 아니다
    ".pnp.cjs",
    ".pnp.js",
    ".pnp.loader.mjs",
)

CODE_EXTS = (".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx")
"""기능 신호를 찾는 JS·TS 파일의 확장자(대소문자를 가린다)."""


def not_utf8(path: Path) -> bool:
    """UTF-8 로 읽히지 않는 파일인가(EUC-KR·CP949, 주석 속 Latin-1 한 바이트 등)."""
    try:
        path.read_bytes().decode("utf-8")
    except UnicodeDecodeError:
        return True
    except OSError:
        return False
    return False


def _git_files(root: Path) -> list[Path] | None:
    """git 저장소면 git 이 아는 파일 목록(추적 파일과 무시되지 않은 새 파일). 아니면 None.

    이름은 바이트로 받아 파일 시스템 인코딩으로 푼다. 로캘 인코딩으로 풀면 한글 파일 이름이 깨져서 말없이 빠진다.
    """
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
            capture_output=True,
            timeout=60,
        )
    except Exception:  # noqa: BLE001
        return None
    if out.returncode != 0:
        return None
    # 지운 채 커밋하지 않은 파일도 --cached 에 남는다. 쓰는 쪽이 있는지 본다.
    return [root / p for p in os.fsdecode(out.stdout).split("\0") if p]


def _admit(path: Path, root: Path) -> bool:
    """기능 신호를 찾을 JS·TS 파일인가. SKIP_DIRS 는 **폴더 아래의 상대 경로**로 본다(저장소가 `~/build/app` 에
    있다고 전체를 빼면 안 된다)."""
    if path.suffix not in CODE_EXTS:
        return False
    try:
        rel = path.relative_to(root) if path.is_absolute() == root.is_absolute() else path
    except ValueError:
        rel = path
    if SKIP_DIRS & set(rel.parts[:-1]) or path.name.endswith(GENERATED_SUFFIXES) or path.is_symlink():
        return False
    try:
        st = path.stat()
    except OSError:
        return False
    return path.is_file() and st.st_size <= MAX_BYTES and os.access(path, os.R_OK) and not not_utf8(path)


def code_files(root: Path) -> list[Path]:
    """폴더의 JS·TS 파일(기능 신호를 찾는 곳). 생성물·축소 파일·1MB 초과·심볼릭 링크·읽을 수 없거나 UTF-8 이 아닌
    파일은 뺀다."""
    candidates = _git_files(root)
    if candidates is None:
        candidates = [c for c in root.rglob("*") if c.is_symlink() or not c.is_dir()]
    out, seen = [], set()
    for child in candidates:
        if _admit(child, root) and child.resolve() not in seen:
            seen.add(child.resolve())
            out.append(child)
    return sorted(out)


# ── 판정기의 도구가 보는 파일 ──────────────────────────────────────────

TOOL_SKIP_DIRS = frozenset(
    {".git", "node_modules", "dist", "build", ".next", "out", "coverage", ".turbo", ".cache", "vendor", ".yarn"}
)
"""git 저장소 안에서 도구가 보지 않는 폴더. git 이 아는 파일이라도 이 아래는 뺀다(전과 같은 집합이 되게)."""

_RUN: dict[Path, tuple[tuple[str, ...], frozenset[str]]] = {}


def _walk_order(rel: str) -> tuple:
    """os.walk(이름순)와 같은 차례: 폴더마다 그 폴더의 파일이 먼저, 그다음 하위 폴더."""
    parts = rel.split("/")
    return (*((1, d) for d in parts[:-1]), (0, parts[-1]))


def _project_files(root: Path) -> tuple[str, ...]:
    listed = _git_files(root)
    out: set[str] = set()
    if listed is not None:
        for p in listed:
            rel = p.relative_to(root)
            if TOOL_SKIP_DIRS & set(rel.parts[:-1]) or p.is_symlink() or not p.is_file():
                continue
            out.add(rel.as_posix())
    else:
        skip = TOOL_SKIP_DIRS | SKIP_DIRS
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in skip]
            for name in filenames:
                f = Path(dirpath) / name
                if not f.is_symlink():
                    out.add(f.relative_to(root).as_posix())
    return tuple(sorted(out, key=_walk_order))


def project_files(root: Path) -> tuple[str, ...]:
    """판정기의 도구(목록·읽기·검색)와 인용 관문이 보는 "이 프로젝트의 파일"(폴더 기준 상대 경로, os.walk 차례).

    git 저장소 안이면 git 이 아는 파일(추적 파일과 무시되지 않은 새 파일) 가운데 TOOL_SKIP_DIRS 아래가 아닌 것이다.
    `.gitignore` 에 든 파일(.venv, 데이터, 로그, 생성물)은 보지 않는다. git 저장소가 아니면 폴더를 걷되
    TOOL_SKIP_DIRS 와 SKIP_DIRS 를 건너뛴다. 심볼릭 링크는 어느 쪽이든 뺀다. review 가 돌 때는(for_run) 저장소마다 한
    번만 구한다.
    """
    root = root.resolve()
    got = _RUN.get(root)
    return got[0] if got is not None else _project_files(root)


def project_file_set(root: Path) -> frozenset[str]:
    """project_files 를 집합으로(인용 관문이 파일마다 묻는다)."""
    root = root.resolve()
    got = _RUN.get(root)
    return got[1] if got is not None else frozenset(_project_files(root))


@contextmanager
def for_run(root: Path):
    """이 안에서는 project_files(root) 를 한 번 구해 둔 것으로 쓴다(review 한 번: 질문마다 도구를 새로 만든다)."""
    root = root.resolve()
    files = _project_files(root)
    _RUN[root] = (files, frozenset(files))
    try:
        yield
    finally:
        _RUN.pop(root, None)
