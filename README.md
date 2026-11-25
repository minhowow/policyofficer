# policyofficer — 국내 법·정책 관점 코드 검토

저장소를 읽고, 그 서비스에 걸릴 수 있는 국내 법 의무마다 코드에서 본 근거(파일:줄)와 법에 적힌 제재를 붙인 체크리스트를 내는 CLI.

**무엇을 내는가** — 공개 사례 jobtalk 의 체크리스트 한 항목(확인할 것 — 코드에서 본 것):

```text
!! 4  개인정보 보호법 제28조의8제1항 · 국외 제공·처리위탁·보관은 별도 동의·처리방침 공개 등 근거가 있을 때만
      과징금 매출 3%
      backend/src/controllers/chatController.ts:135
```

**빠른 시작** — Python 3.10 이상, Anthropic API 키(`ANTHROPIC_API_KEY`)가 필요하다.

```bash
uv tool install git+https://github.com/minhowow/policyofficer
cd <프로젝트 폴더> && policyofficer   # 이 폴더를 검토한다. 터미널이면 요약, 파이프면 JSON. 기본 상한 $2 · 6분
policyofficer replay <결과.json>     # 저장한 결과를 다시 그린다(모델 호출 없음)
```

**어떻게 동작하나** — 기능 파악 → 의무 고르기 → 의무별 조사 → 반박 → 직접 대조 → 체크리스트
1. **기능 파악.** 꾸러미·코드 신호로 잡은 기능(가입, 결제, 생성형 AI …)을 AI 가 코드를 읽고 빼거나 더한다.
2. **의무 고르기.** 법령 206개에서 코드에 흔적이 남는 의무 795개 가운데 그 기능에 걸릴 수 있는 것을 고른다. 코드 모양을
   맞추는 패턴 규칙만으로 가릴 수 있는 것은 11개(1.4%)뿐이라 AI 가 코드를 읽고 묻는다(220개).
3. **의무별 조사.** 의무마다 AI(조사 Claude Haiku 5.5)가 저장소를 검색하고 읽어, 코드 줄을 인용해 답한다.
4. **반박.** 다른 모델(Claude Sonnet 5.5)이 그 답을 뒤집을 수 있는지 다시 본다.
5. **직접 대조.** 도구가 인용이 코드에 글자 그대로 있는지, '없다'의 근거로 댄 검색이 같은 결과인지 다시 돌린다.
   맞지 않으면 근거로 쓰지 않는다.
6. **체크리스트.** 확인할 것을 갈래(코드에서 본 것 · 저장소 밖에서 · 해당 여부부터)와 제재 무게 순으로 낸다.

**41곳에 적용한 결과** — 공개 JS/TS 저장소 41곳, 2026-11-13, 조사 Claude Haiku 5.5, 반박 없이.
- AI 검토는 34곳에서 코드 줄 근거가 붙은 확인 항목을 냈다.
- 모델이 댄 인용 2,256건 중 도구가 받지 않은 것은 18건이다(테스트 파일 8 · 너무 짧음 6 · 파일에 없음 3 · 주석 1).
  '없다'의 근거로 댄 검색 3,195건 중 291건은 도구가 다시 돌린 결과와 달라 근거로 쓰지 않았다.
- 표본 40건을 조사에 쓰지 않은 모델(Claude Opus)이 검수했다. 사람이 본 것이 아니다. '코드에서 본 것' 20건 중
  13건 맞음(틀림 3 · 애매 4), '해당 없음' 20건 중 19건 맞음.
- 저장소당 조사 비용은 평균 $0.16(반박 없이), 걸린 시간은 2~5분.

**웹** https://plitsoft-sdp-web.vercel.app — 사례: [starthub-app](https://plitsoft-sdp-web.vercel.app/cases/starthub-app/) · [Excelerate](https://plitsoft-sdp-web.vercel.app/cases/excelerate/) ·
[jobtalk](https://plitsoft-sdp-web.vercel.app/cases/jobtalk/) · [medeasy-frontend](https://plitsoft-sdp-web.vercel.app/cases/medeasy-frontend/)

> 법률 자문이 아니며 위반 판정이 아니다. 검토가 필요한 곳과 근거 조문을 고를 뿐이다. 제재는 법에 적힌 최대치이고,
> 실제 부과는 위반 사실과 규모에 따라 다르다.

## 설치

아직 PyPI 에 올리지 않았다. 저장소에서 설치한다. 순수 파이썬이고 실행 의존성은 ruamel.yaml 하나다.

```bash
uv tool install git+https://github.com/minhowow/policyofficer   # 또는 클론한 폴더에서 uv tool install .
```

- **필요한 것**: Python 3.10 이상(macOS 기본 `python3` 은 3.9 라 안 된다. uv 를 쓰면 uv 가 알아서 받는다)과
  Anthropic API 키(`ANTHROPIC_API_KEY`). 키는 `review` 에만 필요하다.
- **플랫폼**: macOS·Linux 에서 돌린다. 윈도에서는 아직 돌려 보지 않았다.
- 이름만으로 설치하지 않는다(`pipx install policyofficer`). 아직 등록되지 않은 PyPI 이름이라, 누가 그 이름을 먼저
  등록하면 남의 패키지가 깔린다.

## 써 보기

```bash
export ANTHROPIC_API_KEY=...
policyofficer <폴더>                       # 체크리스트. 터미널이면 요약, 파이프면 JSON (폴더를 빼면 지금 폴더)
policyofficer <폴더> --plan                # 모델 호출 없이 물을 의무 수와 질문 수만 센다
policyofficer <폴더> --no-rebut --max-usd 1
policyofficer review <폴더>                # 같은 검토를 웹 실행기의 기본값으로(--batch duty --rebut-scope all --max-usd 5)
policyofficer replay <결과.json> --speed 4 # 저장한 결과를 다시 그린다(모델·네트워크 호출 없음)
policyofficer profile <폴더>               # 알아본 기능과 걸릴 수 있는 의무(JSON, 모델 호출 없음)
```

- **결과**: stdout 이 터미널이면 요약(갈래별 수, 확인할 것의 법·조문·인용·제재, 도구 대조, 주의 문구)을 내고 전체
  JSON 은 `${XDG_CACHE_HOME:-~/.cache}/policyofficer/reviews/<폴더>-<커밋 12자>.json` 에 둔다. 검토하는 폴더에는
  쓰지 않는다. 파이프·파일이면 JSON 을 낸다. `-o FILE` 은 JSON 을 그 파일에도 쓰고, `--json` 은 터미널이어도 JSON 이다.
  키와 값은 [docs/output.md](docs/output.md) 에 있다.
- **한 줄 명령과 review**: `policyofficer <폴더>` 는 `policyofficer review <폴더>` 와 같은 검토이고 기본값 셋만 다르다
  (`--batch bundle` 같은 코드 범위의 의무를 묶어 묻기, `--rebut-scope found` '코드에서 본 것'·'충족'만 반박,
  `--max-usd 2`). 명령과 같은 이름의 폴더는 `./review` 처럼 준다.
- **상한**: 한 번의 어림 금액(`--max-usd`, 한 줄 명령 2 · review 5)과 시간(`--time-limit`, 기본 360초). 상한에 걸려 묻지 못한 의무는
  '모름'으로 싣고 까닭을 적는다. 모델은 `--model`(조사, 기본 claude-haiku-5-5)과 `--checker`(반박, 기본
  claude-sonnet-5-5)로 고른다.
- **진행 화면**은 stderr 에 그린다(`--progress auto|tty|plain|none`). 터미널이면 제자리에서 다시 그리고, CI·파이프·
  파일이면 사건마다 `[mm:ss] …` 한 줄이다. `NO_COLOR` 는 색만 끈다. Ctrl+C 는 멈춘 곳 한 줄을 남긴다.
- **종료 코드**: `0` 끝까지 돌았다 · `2` 도구 오류(폴더가 없음, 인자가 잘못됨, 키가 없음) · `130` Ctrl+C.

## 외부 통신

`profile` 과 `replay` 는 아무것도 밖으로 보내지 않는다. `review` 는 모델(Anthropic API)에게 **모델이 도구로 고른
파일의 코드와 검색 결과의 줄**을 보낸다. 모델이 쓰는 도구는 읽기 전용 셋(파일 목록·읽기·검색)이고 폴더 밖은 읽지
못한다. 나가기 전에 이렇게 한다(`src/policyofficer/egress.py`).

- 개인키, 알려진 키 모양(AWS·GitHub·Slack·Google·`sk-…` 등), JWT, 비밀처럼 이름 붙은 변수의 긴 문자열,
  주민등록번호·카드 번호 모양을 `[가림:<종류>]` 로 바꾼다. 줄 수는 그대로 둔다.
- `.env`·`.env.local`·`*.pem`·`*.key`·`id_rsa` 같은 파일은 읽지 않는다(`.env.example` 은 읽는다).
- 질문마다 읽은 파일, 검색어, 검색 결과로 줄이 나간 파일, 가린 수, 읽지 않은 비밀 파일을 결과의
  `run.questions[].sent` 에 남긴다.
- 전화번호·이메일·회사 이름은 가리지 않는다. 광고 전송자 연락처처럼 의무를 지킨 근거라서다. 가리는 것도 모양으로
  찾는 것이라 빠지는 비밀값이 있을 수 있다.

`ANTHROPIC_BASE_URL` 이 있으면 그리로 보낸다(사내 게이트웨이). 진행 화면의 머리가 실제 목적지를 알린다.

## 저장소 구성

| 경로 | 내용 |
|---|---|
| `src/policyofficer/` | 제품 코드. `review/`(검토의 단계와 질문 글), `profile/`(기능 신호 표·의무 표·제재 표), `judge/`(모델과의 대화와 읽기 전용 도구), `report/`(진행 화면·터미널 요약) |
| `schemas/review-2.json` | review 결과 JSON 의 스키마(손으로 쓴다. [docs/output.md](docs/output.md)) |
| `tests/` | pytest. 모델을 부르지 않는다(가짜 전송) |
| `lawmap/`, `scripts/lawmap_table.py` | 국내 법 의무 지도에서 의무 표를 만드는 것([docs/lawmap](docs/lawmap/)) |
| `docs/` | 방향, 구조, 결정 기록, 결과 계약 ([docs/README.md](docs/README.md)) |

9/29 이전의 측정·연구 기록은 태그 `archive/research-2026-09-29` 에, 접은 정확도 실험의 설계는 태그
`eval-freeze-2026-11-03` 에, 2026-11-25 에 걷어 낸 `scan` 명령과 정책 팩 kr-core 는 태그 `static-final` 에 남아 있다.
결과를 보여 주는 웹 서비스는 별도 저장소(`policyofficer-web`)다.

## 자주 묻는 것

**JS·TS 가 아닌 저장소도 되나요?** 됩니다. 기능 신호(꾸러미·import·경로)는 JS·TS 만 보지만, 기능 파악 단계에서 AI 가
코드를 읽고 기능을 더하고, 의무별 조사도 언어를 가리지 않고 읽습니다.

**키 없이 볼 수 있는 것이 있나요?** `policyofficer <폴더> --plan` 은 모델을 부르지 않고 알아본 기능과 물을
의무·질문 수를 셉니다. `policyofficer profile <폴더>` 는 기능과 걸릴 수 있는 의무를 JSON 으로 냅니다.

## 라이선스

MIT(LICENSE). 의존성과 자료의 출처는 [NOTICE](NOTICE) 에 있다.

## 면책

이 도구는 법률 자문이 아니다. 검토가 필요한 지점을 식별할 뿐이고, 조문 해석과 최종 판단은
사람이 한다. 의무 표와 제재 표의 법 문구는 검토 중이다.

---

아주대학교 2026-2 자기주도프로젝트 · 플리트소프트 연계 과제.
