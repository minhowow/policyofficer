# 출력 계약 — review·profile 의 JSON

웹 서비스(`policyofficer-web`)가 읽는 `policyofficer review`·`policyofficer profile` 의 약속이다. review 의 스키마는
[`schemas/review-2.json`](../schemas/review-2.json)(JSON Schema 2020-12, 손으로 쓴다)이고, `tests/test_review.py` 가 가짜
답으로 끝까지 돌린 결과로 검사한다.

## 웹이 고정할 판

- 11/24: 태그 `handoff-w13-3`. 제품 이름이 policypack 에서 policyofficer 로 바뀌었다(아래 '이름 바꾸기').
- 11/25: 태그 `handoff-w13-4`. scan 과 정책 팩을 걷어 냈다(아래 '걷어 낸 것').

## 걷어 낸 것 (`handoff-w13-4`, 2026-11-25)

오너 지시로 제품을 review 하나로 줄였다. 되돌릴 자리는 태그 `static-final` 이다. 웹이 맞출 것:

- **명령**: `scan`·`validate`·`test`·`schema`·`doctor`·`hook` 이 없다. 남은 명령은 `profile`·`review`·`replay` 다.
  `review` 의 `--no-static` 도 없다(웹 실행기는 넘기지 않았다). `review`·`profile` 의 다른 인자와 기본값은 그대로다.
- **review JSON**: `checklist[].static`·`checklist[].krcore`·`run.static` 을 내지 않는다. `profile.features[].sources` 에
  `static` 이 나오지 않는다. 그 밖의 키와 값은 그대로이고, 가짜 판정자로 견주면 이 키들 말고는 바이트까지 같다.
  `review_version` 은 2 그대로다(웹이 2 만 받으므로). `schemas/review-2.json` 은 셋을 선택 키로 바꿔 옛 결과도
  통과한다. 웹의 스키마 사본이 셋을 필수로 두었다면 빼야 한다.
- **review --plan JSON**: `static_error` 가 없다.
- **진행 화면·기록 재생**: '정적 규칙' 단계가 없다(단계 다섯). plain 기록에도 그 줄이 없다.
- **저장소의 파일**: `policies/kr-core/`(정책 팩·조문 원문·픽스처), `schemas/policy-pack-0.4.json`·
  `schemas/policy-test-0.1.json`·`schemas/report-1.json`, `.pre-commit-hooks.yaml`, `examples/` 가 없다. 웹의 pack-meta
  내보내기와 의무 지도 내보내기가 `policies/kr-core/pack.yaml` 을 읽었다면 더는 읽을 곳이 없다. 의무 표
  (`src/policyofficer/profile/duties.jsonl`)의 `krcore` 칸은 그대로 두었다(묻는 의무 220개 = `review_candidate` 218개
  + `krcore` 이면서 후보가 아닌 2개).
- **설치**: 실행 의존성이 ruamel.yaml 하나다(Semgrep·pydantic 을 뺐다). 설치가 훨씬 가볍다.

## 이름 바꾸기 (`handoff-w13-3`, 2026-11-24)

제품 이름을 policypack 에서 policyofficer 로 바꿨다(오너 결정). 옛 이름의 별칭(옛 명령·옛 값)은 두지 않는다.
남은 명령에 해당하는 것만 적는다(scan 의 값은 위에서 걷어 냈다).

| 무엇 | 전 | 후 |
|---|---|---|
| 설치 이름(배포 이름) | `policypack` | `policyofficer` (예: `policyofficer @ git+https://github.com/minhowow/policyofficer@<커밋>`) |
| 명령 | `policypack <명령>` | `policyofficer <명령>`. `--version` 의 첫 낱말도 `policyofficer` |
| profile·review 의 JSON `tool.name` | `"policypack"` | `"policyofficer"` |
| review 스키마의 `$id` | `https://policypack.dev/schemas/review-2.json` | `https://github.com/minhowow/policyofficer/schemas/review-2.json` |
| review 스키마 `tool.name` 의 `const` | `"policypack"` | `"policyofficer"` |
| review 결과를 두는 곳(stdout 이 터미널일 때) | `${XDG_CACHE_HOME:-~/.cache}/policypack/reviews/` | `${XDG_CACHE_HOME:-~/.cache}/policyofficer/reviews/` |
| 소스 안의 표 경로 | `src/policypack/profile/{duties.jsonl,features.yaml,sanctions.jsonl}` | `src/policyofficer/profile/…` |

## 판 올리기

- 키를 더할 때는 `review_version`·`profile_version` 을 올리지 않는다. 그래서 받는 쪽은 **모르는 키를 무시**한다.
  스키마는 이 CLI 판이 내는 키를 모두 적고 그 밖의 키를 막는데, 그것은 CLI 의 시험이 스키마를 함께 고치게 하려는
  것이다. 웹이 이 스키마로 엄격하게 검사하면 CLI 가 키를 더할 때 깨진다.
- 파일 경로는 모두 검토하는 폴더(git 저장소면 그 뿌리)에서의 상대 경로다.

## 저장소 프로필(`policyofficer profile <폴더>`, 11/11 부터)

모델을 부르지 않는다. 저장소가 하는 일(기능)과 그 기능에 걸릴 수 있는 의무를 낸다. 판단은 하지 않는다(목록 층).
`profile_version` 은 1 이다.

| 키 | 뜻 |
|---|---|
| `features[]` | 감지된 기능(`id`, `name`). `evidence[]` 는 근거 파일·줄·신호 종류(`package`·`import`·`call`·`url`·`path`·`screens`. `call` 은 문자열·주석 밖의 코드에서만, `url` 은 문자열이 그 주소로 시작할 때만 센다)·본 것, 앞의 5개만 싣고 전체 수는 `evidence_total` |
| `features[].duties` | 그 기능에 붙은 의무 `count`, 검토 층 후보 수 `review_candidates`, `items[]`(id, 법, 조문, 제목, 의무 한 줄, 법제처 링크, 후보 여부, 조문 인용 대조 결과) |
| `service_features` | 화면·앱(`web-ui`·`mobile-app`)을 뺀 기능 수. 0 이면 `note` 가 그 사실을 적고 `common` 이 없다 |
| `common` | 거의 모든 서비스에 걸리는 의무(처리방침·안전조치 등). 서비스 기능이 하나라도 있을 때만 |
| `status` | 운영 주체의 지위(공공기관·금융회사 등)로 걸리는 의무 수. 코드로 가리지 않아 목록은 싣지 않는다 |
| `test_only[]` | 시험·픽스처·설정 파일에서만 본 기능 신호. 기능으로 세지 않는다 |
| `files`, `totals` | 본 파일 수(서비스 코드 / 시험·설정, package.json), 기능·의무·후보 합계 |
| `platforms` | web·mobile·server. 모바일 앱 틀(react-native·expo 등)만 있으면 화면 파일이 있어도 웹이 아니어서 `web-ui` 기능이 없다 |
| `goods[]` | 특정 품목(주류·도서·안경·전기용품·농수산물·청소년유해약물)의 신호(경로 낱말, 소스 글의 낱말 `word`)와 그 품목에만 걸리는 의무 id(`duties`). 11/12 부터 |

기능과 신호는 `src/policyofficer/profile/features.yaml`, 기능–의무 표는 `src/policyofficer/profile/duties.jsonl`(만드는 법은
`scripts/lawmap_table.py`)에 있다.

## 저장소 검토(`policyofficer review <폴더>`, 11/11 부터)

한 줄 명령 `policyofficer [폴더]`(11/25)는 같은 검토이고 같은 JSON 을 낸다. 기본값 셋만 다르다(`--batch bundle`,
`--rebut-scope found`, `--max-usd 2`). 웹 실행기는 `policyofficer review` 를 그대로 쓴다.

스키마는 [`schemas/review-2.json`](../schemas/review-2.json), `review_version` 은 2 다(1 에서 '확인할 것'을 세 갈래로 나누고
부재 증명을 더해 판을 올렸다. 키를 더할 때는 그대로).
조사 모델(`--model`, 기본 haiku)이 저장소를 읽고, 다른 모델(`--checker`, 기본 sonnet)이 반박한다. 질문은 기본으로
의무 하나씩이다(`--batch duty`; `feature` 는 기능 하나에 의무 8개까지, `bundle` 은 표(`features.yaml` 의 `bundles`:
같은 기능·같은 코드 범위를 보는 의무 4개까지)의 묶음마다 묻는다. 답과 관문은 묶어도 의무마다다). `--rebut-scope found` 는
반박을 '코드에서 본 것'·'충족 근거 있음'에만 건다(기본 all). 기능은 이해 단계가 기능 목록의 기능마다 인용과 함께 정한다
(언어와 상관없이. JS·TS 신호는 단서다). 모델이 읽은 파일의 코드가 밖으로
나간다(비밀값은 가리고 .env 등은 읽지 않는다). `--plan` 은 모델 없이 물을 의무와 질문 수만 낸다. `--reuse <앞 결과>` 는
같은 저장소·커밋의 앞 결과에서 이해 단계(요약·기능·개인정보 흐름)를 되살려 묻지 않는다(인용은 관문에 다시 건다).

어디로 나가는지(11/24 부터): stdout 이 터미널이 아니면(웹 실행기, 파이프, 파일) 전과 같은 JSON 이다. 터미널이면 JSON
대신 사람이 읽는 요약(상태별 수, '확인할 것' 목록과 인용, 걸린 시간, 어림 금액)을 내고 JSON 은
`${XDG_CACHE_HOME:-~/.cache}/policyofficer/reviews/<저장소>-<커밋 12자>.json` 에 둔다(분석하는 저장소에는 쓰지 않는다).
`-o FILE` 은 JSON 을 그 파일에도 쓰고, `--json` 은 터미널이어도 stdout 에 JSON 을 낸다. 진행은 stderr 에 그린다
(`--progress auto|tty|plain|none`, 기본 auto): stderr 가 터미널이고 CI 가 아니고 TERM 이 dumb 가 아니면 제자리에서 다시
그리고(tty), 그 밖에는 사건마다 `[mm:ss] …` 한 줄이고 제어 문자가 없다(plain). `NO_COLOR` 는 색만 끈다. Ctrl+C 는 멈춘
곳 한 줄을 남기고 130 으로 끝난다. `policyofficer replay <결과.json> [--speed N]`(기본 4배)은 저장된 결과의 질문 기록으로
같은 진행 화면을 다시 그린다(모델·네트워크 호출 0회). 기록 재생은 지금 표의 글로 다시 그린다: 제재(`sanction`)는 지금의
`profile/sanctions.jsonl` 값으로 덮어쓰고 조문 표기는 지금 의무 표의 `article` 을 먼저 쓴다(표에 없는 의무만 파일의 값.
판정과 인용은 파일 그대로, 11/25). 화면에만 쓰이는 일이라 JSON 은 바뀌지 않는다. 터미널 요약의 첫 줄은 확인할 것의 수와
그 가운데 징역·과징금의 수를 적고, 각주 바로 위의 '도구 대조' 한 줄은 `run.citations`·`citations_rejected`·`searches`·
`searches_rejected` 와 거절 까닭(인용·검색의 `why`)을 많은 순으로 둘까지 적는다(11/25).

| 키 | 뜻 |
|---|---|
| `summary` | 체크리스트의 갈래별 수(`counts`), 갈래 이름(`labels`), 맨 위 다섯 건의 의무 id(`top`), 한 줄로 묶어 보일 항목(`groups`: 품목 신호가 없어 묻지 않은 품목 의무, `id` goods), 먼저 볼 것(`highlights`, 11/25 덧붙임, 아래) |
| `profile` | 커밋(`commit`), 플랫폼(`platforms`: web·mobile·server, 출처 `platforms_from`: signal 은 package.json, model 은 package.json 으로 가르지 못해 이해 단계가 인용과 함께 적은 것 `platform_evidence`), 서비스 요약, 기능(`sources`: signal·model, 모델이 더한 근거 `model_citations`, 인용과 함께 뺀 것은 `removed`. 11/25 전의 결과에는 static 도 있다), 품목 신호(`goods`) |
| `data_flow` | 개인정보 흐름. `nodes[]`(input·server·store·external, 다루는 항목 `data`, 인용) 와 `edges[]`(from→to). 인용이 관문을 통과한 것만 |
| `obligations.listed[]` | 목록 층: 감지된 기능과 거의 모든 서비스에 걸릴 수 있는 의무. `in_checklist` 는 검토 층에 들었는지 |
| `checklist[]` | 검토 층. 이미 갈래 순으로 늘어서 있고 `rank` 가 1 부터다. 의무마다 `status`·`status_label`, 인용 `citations`, 부재를 보인 검색 `searches`, 개발자에게 물을 `question`, 조사 모델의 첫 답 `first`, 반박 `verification`(upheld · overturned · overturn-ungrounded · not-run, 조문 밖 요건이었는지 `off_quote`), 어기면 법에 적힌 최대 제재 `sanction`(11/24 덧붙임, 아래), 조건은 있는데 없는 지킨 처리 `missing`(예: "약관 고지 화면이 없음"), 묻지 않은 품목 의무의 묶음 `group`(goods) |
| `first`·`verification` 의 덧붙임(11/12) | 답이 적은 걸리는 조건 `applies`(예·아니오·모름)·`condition`, 없는 것 `missing`, 충족 인용의 성격 `shows`(행위·이름·기본값), 관문이 답을 바꾼 까닭 `gate`(`why`: condition-present · no-condition · name-or-default · audience · missing-check · applies-unknown · free-input · other-side · prohibition · same-model, `note` 는 `reason` 앞에도 붙는다). '해당 없음'의 근거 `basis`(처리 없음·확인 장치 없음, 같은 날 덧붙임). 걸리는 조건을 본 곳 `trigger`(입력란·처리·저장 · 자유 입력 추측, 11/13 덧붙임). `shows` 의 `금지 행위` 는 금지 의무(의무 표의 `prohibition`)에서 금지된 행위 자체를, `빈틈` 은 '코드에서 본 것'의 인용이 빈틈 자체(상수로 고정된 로그인 검사, 평문 저장 등)를 보인다는 표시다. 반박의 뒤집기는 자유 입력 관문이 옮긴 항목이면 그 정보를 받는 입력란·필드·저장의 인용(applies 예)이, 금지 의무면 금지 행위의 인용이 있어야 받고, 조사와 반박이 같은 모델이면 '충족'으로 올리는 뒤집기는 받지 않는다(`gate` same-model). '충족'이라 답할 때 적는 남은 부족한 점 `remaining`(없으면 '없음', 11/15 덧붙임)이 있으면 '코드에서 본 것'이다(`gate` remaining-gap). '금지 행위'·'빈틈' 표시는 관문을 통과한 인용이 있을 때만 받는다. 인용의 `why` 가 `profile` 이면 모델의 인용이 아니라 기능이 있다는 프로필 신호(걸리는 조건의 근거)다. `config-value` 면 설정 파일의 줄이지만 주소·호스트 값이 있어 받은 인용이다 |
| `run` | 모델, 반박을 물었는지(`rebut`, false 면 `models.verify` 는 none 이고 반박할 항목은 not-run why rebut-off), 반박할 항목(`rebut_scope`: all · found, found 면 나머지는 not-run why rebut-scope), 묶음(`batch`: duty · feature · bundle), 저장소에 없는 쪽(`lacks`: screen 이면 서버만, server 면 화면만), 상한, 시간, 호출 수, 사용량, 어림 금액(공식 단가를 호출마다 매겨 더한 값), 상태·반박 결과별 수, 인용과 관문이 거절한 수, 검색과 다시 돌려 맞지 않은 수, 못 물은 의무(`not_asked`), 가린 비밀값, 읽지 않은 비밀 파일, 질문마다의 기록 |

`highlights`(11/25): 먼저 볼 것 세 건까지. 건마다 `{"duty", "file", "line", "text"}`(의무 id 와 보일 인용 하나)이다. 후보는
'코드에서 본 것'이고 품목 묶음이 아니고 모델이 댄 인용(`why` 가 profile 이 아닌 것)이 관문을 통과한 항목이다. 반박을 견딘
것(`verification.result` upheld) → 제재 등급 → 정액 상한 → 체크리스트 순서로 늘어놓고, 기능마다 하나씩 먼저 고른 뒤 모자라면
남은 후보로 채운다. 후보가 없으면 빈 목록이다. 터미널 요약은 같은 함수(review.highlights)로 각주 위에 '먼저 볼 N건'을 보이고,
`replay` 는 이 키가 없는 옛 결과에도 붙인다. 예(jobtalk):
`{"duty": "pipa-28-8-1", "file": "backend/src/controllers/chatController.ts", "line": 135, "text": "const response = await openai.responses.create({"}`.

`sanction`(11/24): 의무별 제재 표(`src/policyofficer/profile/sanctions.jsonl`, AI 검토가 묻는 의무 220개와 1:1)의 레코드에서
`duty` 를 뺀 것이다. 등급 `class` 는 무거운 순서로 징역 > 과징금 > 벌금 > 과태료 > 명령(시정명령 등을 어겨야 제재) >
없음이고 AI 판단이 아니라 법령 원문의 벌칙·과징금·과태료 조문으로 정했다. `label` 은 표지에 쓰는 짧은 말(화면에는
표지 그대로. 11/25 부터 앞에 '어기면'을 붙이지 않는다), `max_won` 은 같은 등급 안의 정렬에 쓰는 정액 상한(원), `items[]` 는 조문마다 `kind`·`via`(direct ·
order)·`condition`·`penalty`·`law`·`clause`·`url`·`quote`(법령 원문), `note`·`as_of`. 위반 판정이 아니다. 터미널 요약은
갈래 안에서 등급 순(같으면 `max_won` 큰 순)으로 늘어놓고 징역·과징금 앞에 `!!` 를 붙이며, 아래에 "법에 적힌 최대
제재입니다. 위반 판정이 아니며, 실제 부과는 위반 사실과 규모에 따라 다릅니다."를 한 번 적는다. 표는 불러올 때 1:1, 등급,
빈 인용을 검사한다. `replay` 는 표보다 앞선 결과에도 의무 id 로 지금 표의 제재를 붙여 보인다.

상태(갈래 순):

| status | 이름 | 받는 조건 |
|---|---|---|
| `seen-in-code` | 확인할 것 — 코드에서 본 것 | 걸리는 조건의 인용이 관문을 통과했다. 지킨 근거는 찾지 못했다(`missing`). 조건은 있는데 지킨 처리가 없다는 '해당 없음', 그 기능이 있으면 걸리는 의무(`features.yaml` 의 `whenever`)에 기능이 있는데 낸 '해당 없음', 이름·기본값뿐인 '충족', 남은 부족한 점을 적은 '충족'(`gate` remaining-gap), 금지 의무에서 금지된 행위가 일어나게 하는 빈틈을 인용한 답(`shows` 빈틈, 관문 통과), 그 기능이 있으면 걸리는 의무에 낸 '해당 여부' 가운데 조사 답이 그 기능의 처리가 저장소에 있다고 보고(`applies` 예) 인용한 것도 여기로 온다 |
| `check-outside` | 확인할 것 — 저장소 밖에서 | 배포 설정·처리방침·저장소에 없는 서버를 봐야 한다. 인용이 관문을 통과하지 못한 '코드에서 본 것'·'충족'도 여기로 온다. 저장소가 서버만 또는 화면만이면(`run.lacks`) 반대쪽이 하는 의무(`features.yaml` 의 `sides`)의 '코드에서 본 것'도 여기다(`gate` other-side). 답이 이 저장소의 줄을 인용해 빈틈 자체를 보였으면(`shows` 빈틈·금지 행위) 옮기지 않는다 |
| `check-applicability` | 확인할 것 — 해당 여부부터 | 걸리는지가 사업자의 판단이다(고영향 AI, 사내 도구, 업종). 반박하지 않는다. 걸리는 조건이 없다는 말 없이 낸 '해당 없음', 걸리는지 모른다고 한(`applies` 모름) '확인할 것'(그 기능이 있으면 걸리는 의무는 빼고), 나이·본인·지역을 확인하는 장치가 없다는 것을 근거로 든 '해당 없음'(`basis` 확인 장치 없음)과 이용자가 누구인지에 걸리는 의무(`features.yaml` 의 `audience`: 아동·미성년자·청소년)의 '해당 없음', 품목 신호가 없어 묻지 않은 품목 의무(`not_answered` goods-not-detected, 갈래의 맨 뒤), 생성형 AI 기능 없이 분류·인식 모델만 있어 묻지 않은 AI 사전 고지·결과물 표시(`not_answered` not-generative)도 여기다. 생성형 AI 기능이 있으면 묻고 조사 답을 따른다. 그 기능이 있으면 걸리는 의무로 고정하는 것은 프로필의 생성형 신호(SDK 꾸러미·import·호출·주소)가 있을 때만이다 |
| `unknown` | 모름(묻지 못함) | 상한·실패로 답이 없다. `not_answered` 에 까닭 |
| `evidence-found` | 충족 근거 있음 | 조문이 요구하는 행위 자체를 보이는 줄(`shows` 행위)의 인용이 관문을 통과했다 |
| `likely-not-applicable` | 걸리지 않는 것으로 보임(확인 안 됨) | 걸리는 조건 자체가 없다고 했지만(`applies` 아니오·`condition`·`basis` 처리 없음) 검색 증명이 없거나 맞지 않았다. 걸리는 조건이 이용자가 자유 입력·사진에 넣을 수 있다는 추측뿐인 '코드에서 본 것'(`trigger` 자유 입력 추측, `applies` 모름이 아닐 때)도, 그 정보를 받는 입력란·필드·저장이 없다는 검색이 맞으면 여기다(맞지 않으면 '해당 여부부터'). 그 추측으로 반박이 뒤집으려 하면 받지 않는다. 금지 의무인데 금지된 행위 자체나 그 빈틈을 인용하지 않은 '코드에서 본 것'(막는 장치가 없다는 답)도 여기다(검색이 맞으면 '해당 없음', `gate` prohibition). 확인 목록에 올리지 않는다 |
| `not-applicable` | 해당 없음(검색으로 확인) | 걸리는 조건 자체가 없다고 했고(`applies` 아니오·`condition`·`basis` 처리 없음), 그 조건을 찾은 검색(정규식·줄 수)을 도구가 저장소에서 다시 돌려 줄 수가 같았다 |

- 인용은 시험·설정 파일의 줄이면 받지 않는다. 질문에 넣는 요건은 조문 인용에 있는 것만이다.
- 반박이 뒤집을 때도 같은 조건(있다는 말은 인용, 없다는 말은 걸리는 조건이 없다는 답과 검색, 충족은 행위 자체의 인용)을
  넘어야 받는다.
- 묻는 순서와 체크리스트의 같은 갈래 안 순서: 기능은 거의 모든 서비스·가입·AI·외부 전송이 먼저, 기능 안에서는 일반 범위 →
  그 기능이 있으면 걸리는 의무 → 흔한 것(의무 표의 `freq`) → 확신 높은 것이고 품목 의무가 맨 뒤다. 금액 상한에 걸려도
  핵심 의무는 묻는다.
- 검색 도구는 결과를 60줄에서 잘라 보여 줄 때 맞는 줄의 전체 수를 함께 알려 주고, 관문은 그 전체 수와 맞춰 본다.
- 모델의 도구(목록·읽기·검색)와 인용 관문은 "이 프로젝트의 파일"만 본다(11/25): git 저장소면 git 이 아는 파일(추적
  파일과 무시되지 않은 새 파일)에서 node_modules·dist·build 등을 뺀 것, 아니면 폴더를 걷되 그 폴더들과 .venv 등을 뺀
  것이다. `.gitignore` 에 든 파일의 인용은 `why` outside-repo 로 받지 않는다. UTF-8 로 읽히지 않는 파일은 읽지 않는다.
  깨끗한 클론에서는 전과 같은 집합이다(공개 저장소 41곳에서 확인).

## 아직 없는 것

- 결과에 실린 CLI 커밋·검토 시각.
