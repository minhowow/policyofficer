"""review 의 판정기가 쓰는 것: 외부 전송 통제(가리기·비밀 파일), 읽기 전용 도구, 모델과의 대화, 인용 관문, HTTP
전송, 파일 역할. 모델을 부르지 않는다(가짜 전송)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from policyofficer import review as rv
from policyofficer.egress import is_secret_file, mask
from policyofficer.evidence import gate
from policyofficer.judge.agent import AgentJudge, RepoTools
from policyofficer.judge.http import Unavailable
from policyofficer.roles import Role, classify


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "r"
    files = {
        "src/pages/Signup.tsx": (
            "import { AgeGate } from '../components/AgeGate'\n"
            "export default function Signup() {\n"
            "  return (<form><input name='birth' /><AgeGate /></form>)\n"
            "}\n"
        ),
        "src/components/AgeGate.tsx": (
            "export const AgeGate = () => {\n"
            "  // 만 14세 미만 차단\n"
            "  if (age < 14) throw new Error('만 14세 미만은 가입할 수 없습니다')\n"
            "  return null\n"
            "}\n"
        ),
        "src/chat/Chat.tsx": "export const Chat = () => <div>{answer}</div>\n",
        "src/config.ts": "export const apiKey = 'sk-proj-abcdefghijklmnopqrstuvwxyz123456'\n",
        ".env": "OPENAI_API_KEY=sk-live-should-never-leave-1234567890\n",
        ".env.example": "OPENAI_API_KEY=\n",
    }
    for rel, text in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    (tmp_path / "secret.txt").write_text("outside", encoding="utf-8")
    return root


def scripted(*turns):
    """turns: 응답 content 목록. 요청 본문은 sent 에 쌓인다."""
    sent = []
    queue = list(turns)

    def send(body):
        sent.append(body)
        content = queue.pop(0) if queue else [{"type": "text", "text": "{}"}]
        return {"content": content, "usage": {"input_tokens": 10, "output_tokens": 3}}

    send.sent = sent
    return send


def answer(*results):
    """results: (entry, verdict, citations[, line])"""
    docs = []
    for r in results:
        d = {"entry": r[0], "verdict": r[1], "citations": list(r[2]), "reason": "r"}
        if len(r) > 3:
            d["line"] = r[3]
        docs.append(d)
    return [{"type": "text", "text": json.dumps({"results": docs}, ensure_ascii=False)}]


def tool(name, **inp):
    return {"type": "tool_use", "id": f"t-{name}-{len(inp)}", "name": name, "input": inp}


AGE = {"file": "src/components/AgeGate.tsx", "line": 3, "text": "if (age < 14) throw"}
JWT = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"


# ── 외부 전송 통제 ────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("text", "kind"),
    [
        ("const k = 'AKIAABCDEFGHIJKLMNOP'", "aws-key"),
        ("token: ghp_abcdefghijklmnopqrstuvwxyz0123456789", "github-token"),
        ("ANTHROPIC = 'sk-ant-api03-abcdefghijklmnopqrstuvwx'", "api-key"),
        ("key=AIzaSyA1234567890abcdefghijklmnopqrstuv", "google-key"),
        ("-----BEGIN RSA PRIVATE KEY-----\nMIIE\n-----END RSA PRIVATE KEY-----", "private-key"),
        (f"Bearer {JWT}", "jwt"),
        ("const password = 'hunter2hunter2'", "secret-value"),
        ("주민번호 900101-1234567 입력", "rrn"),
        ("card 4111 1111 1111 1111", "card"),
    ],
)
def test_mask_kinds(text, kind):
    out, counts = mask(text)
    assert counts.get(kind) == 1 and "[가림:" in out


@pytest.mark.parametrize(
    "text",
    [
        "문의: 02-1234-5678, help@example.com",  # 광고 전송자 연락처는 이행 근거다. 가리지 않는다
        "const password = process.env.DB_PASSWORD",
        "const token = ''",
        "order 1234 5678 9012 3456",  # Luhn 실패
        "Date.now() === 1712345678901",
    ],
)
def test_mask_leaves_evidence_alone(text):
    assert mask(text) == (text, {})


def test_masking_keeps_the_line_count():
    key = "-----BEGIN RSA PRIVATE KEY-----\nMIIE\nabcd\n-----END RSA PRIVATE KEY-----\nnext()"
    out, counts = mask(key)
    assert counts == {"private-key": 1} and out.count("\n") == key.count("\n") and out.endswith("next()")


def test_tools_mask_the_whole_file_before_cutting(tmp_path):
    """읽는 구간만 가리면 개인키 블록의 중간부터 읽을 때 본문이 그대로 나갔다. 검색 결과에 BEGIN 줄이 있으면 그 뒤의
    검색 결과가 모두 지워졌다."""
    (tmp_path / "keys.ts").write_text(
        "export const pem = `\n-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBgkqhkiG9w0BAQEFAASC\n"
        "-----END PRIVATE KEY-----`;\nexport const other = 1;\n",
        encoding="utf-8",
    )
    (tmp_path / "z.ts").write_text("export const target = 2;\n", encoding="utf-8")
    t = RepoTools(tmp_path)
    out = t.call("read_file", {"path": "keys.ts", "start_line": 3})
    assert "MIIE" not in out and "5\texport const other = 1;" in out
    hits = t.search("export|BEGIN")
    assert "MIIE" not in hits and "z.ts:1: export const target = 2;" in hits and "keys.ts:5:" in hits
    assert t.masked == {"private-key": 1}  # 중간부터 읽은 구간에는 가린 자리 표시도 본문도 없다


def test_secret_files():
    assert is_secret_file(".env") and is_secret_file("apps/web/.env.local") and is_secret_file("certs/server.pem")
    assert not is_secret_file(".env.example") and not is_secret_file("src/env.ts") and not is_secret_file("key.ts")


def test_tools_stay_inside_and_mask(repo):
    t = RepoTools(repo)
    assert "저장소 밖" in t.call("read_file", {"path": "../secret.txt"})
    assert "outside" not in t.search("outside")
    assert "읽지 않는다" in t.call("read_file", {"path": ".env"})
    assert "should-never-leave" not in t.search("OPENAI")
    assert "OPENAI_API_KEY=" in t.search("OPENAI")  # .env.example 은 읽는다
    assert "[가림:api-key]" in t.call("read_file", {"path": "src/config.ts"})
    assert t.masked == {"api-key": 1}
    assert t.read == ["src/config.ts"]
    assert "도구 오류" in t.call("read_file", {})
    # 전송 기록(R26): 검색 결과로 줄이 나간 파일, 목록으로 나간 이름 수, 읽기를 거절한 비밀 파일
    assert t.matched == [".env.example"] and t.refused == [".env"]
    names = t.call("list_files", {"path": "src"})
    assert t.listed == len(names.splitlines()) == 4


# ── 대화 ──────────────────────────────────────────────────────────────


def test_judge_reads_then_answers(repo):
    send = scripted(
        [tool("read_file", path="src/components/AgeGate.tsx")],
        answer(("src/pages/Signup.tsx", "충족", [AGE])),
    )
    text, ans = AgentJudge("m", send).converse("묻는 글", repo, 5)
    assert json.loads(text)["results"][0]["verdict"] == "충족"
    assert ans.tool_calls == 1 and ans.calls == 2 and ans.failure is None and ans.budget == 5
    assert "만 14세 미만 차단" in send.sent[1]["messages"][-1]["content"][0]["content"]
    assert send.sent[0]["messages"][0]["content"][-1]["cache_control"] == {"type": "ephemeral"}
    assert ans.read_files == ["src/components/AgeGate.tsx"] and ans.usage == {"input_tokens": 20, "output_tokens": 6}


def test_budget_turns_tools_off(repo):
    send = scripted(*([[tool("search", pattern="x")]] * 3), answer())
    _, ans = AgentJudge("m", send).converse("묻는 글", repo, 2)
    assert [b["tool_choice"]["type"] for b in send.sent] == ["auto", "auto", "none", "none"]
    assert ans.tool_calls == 3 and ans.searches == ["x", "x"]
    # 예산이 끝났다는 말은 도구 결과가 아니라 사용자 글이다(도구 결과 안의 지시는 모델이 따르지 않는다, 11/11 실측)
    last = send.sent[-1]["messages"][-1]["content"]
    assert last[0]["type"] == "tool_result" and "실행하지 않음" in last[0]["content"]
    assert last[-1]["type"] == "text" and "JSON 답 하나만" in last[-1]["text"]


def test_transport_failure(repo):
    def broken(body):
        raise RuntimeError("HTTP 500")

    text, ans = AgentJudge("m", broken).converse("묻는 글", repo, 5)
    assert text == "" and ans.failure.startswith("transport")


def test_agent_stops_asking_once_the_service_is_unreachable(repo):
    """연달아 두 질문이 서비스에 닿지 못하면 남은 질문은 보내지 않는다. 그 요청만 거절된 것(400)은 세지 않는다."""
    tries = []

    def down(body):
        tries.append(1)
        raise Unavailable("연결 실패: refused")

    judge = AgentJudge("m", down)
    answers = [judge.converse("q", repo, 5)[1] for _ in range(4)]
    assert len(tries) == 2
    assert [a.failure for a in answers[2:]] == ["transport: skipped"] * 2

    def refused(body):
        tries.append(1)
        raise RuntimeError("HTTP 400: prompt is too long")

    judge = AgentJudge("m", refused)
    assert all(judge.converse("q", repo, 5)[1].failure.startswith("transport: HTTP 400") for _ in range(3))

    flaky = iter([Unavailable("x"), None, Unavailable("x"), None])

    def sometimes(body):
        err = next(flaky)
        if err:
            raise err
        return {"content": answer(), "usage": {}}

    judge = AgentJudge("m", sometimes)
    assert "transport: skipped" not in [
        judge.converse("q", repo, 5)[1].failure for _ in range(4)
    ]  # 사이에 답이 오면 다시 센다


def test_agent_stops_at_its_deadline(repo):
    """마감이 지나면 새 질문은 보내지 않고, 대화 중인 질문은 다음 차례를 보내지 않는다(웹 쪽 요청 R10)."""
    import time

    sent = []

    def slow(body):
        sent.append(1)
        return {"content": [tool("list_files")], "usage": {}}

    judge = AgentJudge("m", slow)
    judge.deadline = time.monotonic() - 1
    assert judge.converse("q", repo, 5)[1].failure == "time: skipped" and sent == []

    judge = AgentJudge("m", slow)
    judge.deadline = time.monotonic() + 0.05

    def tick(body):
        time.sleep(0.06)
        return slow(body)

    judge.transport = tick
    assert judge.converse("q", repo, 5)[1].failure == "time" and len(sent) == 1


def test_build_judge_needs_a_key_and_resolves_aliases():
    throttle = rv.Throttle(1)
    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
        rv.build_judge("anthropic:m", throttle, env={})
    with pytest.raises(ValueError, match="알 수 없습니다"):
        rv.build_judge("openai:m", throttle, env={"ANTHROPIC_API_KEY": "k"})
    assert rv.build_judge("anthropic:claude-x", throttle, env={"ANTHROPIC_API_KEY": "k"}).model == "claude-x"
    # 별칭을 풀어 부른다. 풀지 않으면 API 가 모델을 몰라 질문이 모두 실패했다(R7)
    assert rv.build_judge("anthropic:haiku", throttle, env={"ANTHROPIC_API_KEY": "k"}).model == "claude-haiku-5-5"


# ── 인용 관문 ─────────────────────────────────────────────────────────


def test_gate_puts_the_citation_on_the_line_where_it_is(repo):
    """줄 번호는 모델이 적은 값이다. 웹은 그 줄로 링크를 만든다(R25). 관문을 통과한 인용은 실제 줄로 맞추고, 다르면
    모델의 값을 line_model 에 남긴다. 맞으면 그대로 둔다. 통과하지 못한 인용은 손대지 않는다."""
    [wrong, right, multi, none, made_up] = gate(
        repo,
        [
            {"file": "src/components/AgeGate.tsx", "line": 1, "text": "if (age < 14) throw new Error"},
            {"file": "src/components/AgeGate.tsx", "line": 3, "text": "if (age < 14) throw new Error"},
            {"file": "src/pages/Signup.tsx", "line": 9, "text": "export default function Signup() { return (<form>"},
            {"file": "src/components/AgeGate.tsx", "text": "if (age < 14) throw new Error"},
            {"file": "src/components/AgeGate.tsx", "line": 7, "text": "if (age < 19) throw"},
        ],
    )
    assert (wrong["line"], wrong["line_model"]) == (3, 1)
    assert right["line"] == 3 and "line_model" not in right
    assert (multi["line"], multi["line_model"]) == (2, 9)  # 두 줄에 걸친 인용은 시작 줄
    assert (none["line"], none["line_model"]) == (3, None)
    assert not made_up["ok"] and made_up["line"] == 7 and "line_model" not in made_up


def test_gate_multi_file(repo):
    res = gate(
        repo,
        [
            {"file": "src/components/AgeGate.tsx", "line": 3, "text": "if (age < 14) throw new Error"},
            {"file": "src/components/AgeGate.tsx", "line": 2, "text": "// 만 14세 미만 차단"},
            {"file": "../secret.txt", "line": 1, "text": "outside"},
            {"file": "src/nope.ts", "line": 1, "text": "whatever code"},
            {"file": "src/chat/Chat.tsx", "line": 1, "text": "지어낸 줄 const x = 1"},
        ],
    )
    assert [(r["ok"], r["why"]) for r in res] == [
        (True, "grounded"),
        (False, "comment-only"),
        (False, "outside-repo"),
        (False, "no-such-file"),
        (False, "not-found"),
    ]


# ── HTTP 전송 ─────────────────────────────────────────────────────────


def test_http_endpoint_follows_base_url():
    from policyofficer.judge.http import endpoint

    assert endpoint({}) == "https://api.anthropic.com/v1/messages"
    assert endpoint({"ANTHROPIC_BASE_URL": "https://gw.example.com/anthropic/"}) == (
        "https://gw.example.com/anthropic/v1/messages"
    )


def test_http_transport_retries_dropped_connections(monkeypatch):
    import json as _json
    import urllib.request

    from policyofficer.judge.http import http_transport

    calls = []

    class Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return _json.dumps({"content": []}).encode()

    def fake(req, timeout):
        calls.append(1)
        if len(calls) < 3:
            raise ConnectionResetError(54, "Connection reset by peer")
        return Resp()

    monkeypatch.setattr(urllib.request, "urlopen", fake)
    assert http_transport("k", url="https://x", sleep=lambda s: None)({}) == {"content": []}
    assert len(calls) == 3

    def always(req, timeout):
        raise ConnectionResetError(54, "reset")

    monkeypatch.setattr(urllib.request, "urlopen", always)
    with pytest.raises(Unavailable, match="연결 실패"):
        http_transport("k", url="https://x", sleep=lambda s: None)({})


def test_http_transport_gives_up_after_two_timeouts(monkeypatch):
    import urllib.request

    from policyofficer.judge.http import http_transport

    calls = []

    def hang(req, timeout):
        calls.append(1)
        raise TimeoutError("timed out")

    monkeypatch.setattr(urllib.request, "urlopen", hang)
    with pytest.raises(Unavailable, match="시간 초과"):
        http_transport("k", url="https://x", timeout=1, sleep=lambda s: None)({})
    assert len(calls) == 2


@pytest.mark.parametrize(("code", "down"), [(400, False), (401, True), (404, True), (500, True), (529, True)])
def test_http_transport_tells_a_refused_request_from_an_unreachable_service(monkeypatch, code, down):
    """재시도를 다 쓴 429·5xx 와 다시 보내도 같은 401·403·404(키·권한·모델)는 서비스에 닿지 못한 것(Unavailable)이고,
    400 처럼 그 요청만 거절된 것은 아니다. 판정자와 에이전트는 Unavailable 만 세어 남은 질문을 그만 보낸다."""
    import io
    import urllib.error
    import urllib.request

    from policyofficer.judge.http import http_transport

    def refuse(req, timeout):
        raise urllib.error.HTTPError("https://x", code, "x", {}, io.BytesIO(b"no"))

    monkeypatch.setattr(urllib.request, "urlopen", refuse)
    with pytest.raises(RuntimeError, match=f"HTTP {code}") as e:
        http_transport("k", url="https://x", sleep=lambda s: None)({})
    assert isinstance(e.value, Unavailable) is down


# ── 파일 역할 ─────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("rel", "text", "role"),
    [
        ("src/a.test.ts", "expect(1)", Role.TEST),
        ("src/__tests__/b.tsx", "return (<div/>)", Role.TEST),
        ("src/Button.stories.tsx", "<Button/>", Role.TEST),
        ("next.config.js", "module.exports = {}", Role.CONFIG),
        (".eslintrc.cjs", "module.exports = {}", Role.CONFIG),
        ("pages/api/chat.ts", "export default function handler(req, res) {}", Role.SERVER),
        ("app/api/chat/route.ts", "export async function POST(req) {}", Role.SERVER),
        ("src/actions.ts", "'use server'\nexport async function save() {}", Role.SERVER),
        ("server/index.js", "const app = express();", Role.SERVER),
        ("src/pages/Signup.tsx", "export default function S() { return (<form/>) }", Role.SCREEN),
        ("src/components/Chat.jsx", "const C = () => <div>hi</div>", Role.SCREEN),
        ("src/utils/date.ts", "export const f = () => 1", Role.OTHER),
        ("src/api/client.ts", "export const get = () => fetch('/x')", Role.OTHER),
    ],
)
def test_roles(rel, text, role):
    assert classify(rel, text) is role


# ── 도구가 보는 파일: 이 프로젝트의 파일 ──────────────────────────────


def _git(root: Path, *args: str) -> None:
    import subprocess

    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


@pytest.fixture
def local(tmp_path: Path) -> Path:
    """로컬 체크아웃 같은 폴더: 추적 파일, 아직 add 하지 않은 새 파일, .gitignore 에 든 데이터·가상환경·로그."""
    root = tmp_path / "app"
    files = {
        ".gitignore": ".venv/\n*.log\ndata/\n",
        "src/signup.ts": "export const signup = (birth) => saveUser({ birth })\n",
        "src/new.ts": "export const fresh = 'not yet added'\n",
        ".venv/lib/site.py": "secret_password = 'hunter2hunter2'\n",
        "data/users.csv": "name,birth\nkim,2010-01-01\n",
        "server.log": "saveUser called\n",
        "node_modules/pkg/index.js": "module.exports = 'saveUser'\n",
    }
    for rel, text in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text, encoding="utf-8")
    (root / "src" / "logo.png").write_bytes(b"\x89PNG\r\n\x1a\n\xff\xfe\x00")
    (root / "src" / "link.ts").symlink_to(root / "src" / "signup.ts")
    _git(root, "init", "-q")
    _git(root, "add", ".gitignore", "src/signup.ts", "src/logo.png")
    return root


def test_tools_see_only_the_project_files(local):
    from policyofficer.discover import project_files

    assert project_files(local) == (".gitignore", "src/logo.png", "src/new.ts", "src/signup.ts")
    t = RepoTools(local)
    listed = t.call("list_files", {}).splitlines()
    assert listed == [".gitignore", "src/logo.png", "src/new.ts", "src/signup.ts"]
    hits = t.search("saveUser|password")
    assert hits.startswith("src/signup.ts:1:") and ".venv" not in hits and "server.log" not in hits
    assert "node_modules" not in hits and t.count("saveUser") == 1
    assert "이 프로젝트의 파일이 아니라" in t.call("read_file", {"path": "data/users.csv"})
    assert "이 프로젝트의 파일이 아니라" in t.call("read_file", {"path": ".venv/lib/site.py"})
    assert "fresh" in t.call("read_file", {"path": "src/new.ts"})  # 아직 add 하지 않은 새 파일은 읽는다
    assert "UTF-8 로 읽히지 않는" in t.call("read_file", {"path": "src/logo.png"})
    assert t.read == ["src/new.ts"]


def test_the_gate_refuses_citations_of_ignored_files(local):
    from policyofficer.discover import project_file_set

    cites = [
        {"file": "server.log", "line": 1, "text": "saveUser called"},
        {"file": "src/new.ts", "line": 1, "text": "export const fresh = 'not yet added'"},
        {"file": "src/signup.ts", "line": 1, "text": "export const signup = (birth) => saveUser({ birth })"},
    ]
    assert [(r["ok"], r["why"]) for r in gate(local, cites, project_file_set(local))] == [
        (False, "outside-repo"),
        (True, "grounded"),
        (True, "grounded"),
    ]
    assert [r["ok"] for r in rv.check(local, cites)] == [False, True, True]


def test_a_folder_that_is_not_a_git_repository_is_walked_without_generated_folders(tmp_path):
    from policyofficer.discover import project_files

    for rel in ("a.ts", "lib/b.ts", ".venv/x.py", "node_modules/m/i.js", "__pycache__/c.pyc", "build/out.js"):
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text("x\n", encoding="utf-8")
    assert project_files(tmp_path) == ("a.ts", "lib/b.ts")


def test_a_worktree_does_not_show_its_git_file(local, tmp_path):
    from policyofficer.discover import project_files

    _git(local, "-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-q", "-m", "x")
    wt = tmp_path / "wt"
    _git(local, "worktree", "add", "-q", str(wt))
    assert (wt / ".git").is_file() and ".git" not in project_files(wt)
    assert "src/signup.ts" in project_files(wt)


def test_the_set_is_computed_once_per_run(local):
    from policyofficer.discover import for_run, project_files

    with for_run(local):
        before = project_files(local)
        (local / "src" / "later.ts").write_text("x\n", encoding="utf-8")
        assert project_files(local) == before  # 한 번의 review 안에서는 같은 집합
    assert "src/later.ts" in project_files(local)
