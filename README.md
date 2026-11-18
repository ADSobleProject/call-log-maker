# 🎙️ 통화록 변환기 (call-log-maker)

음성 녹음 파일이나 이미 텍스트로 변환된 기록을 넣으면 **깔끔한 통화록 문서**(`.md` + `.docx`)로
자동 정리해 주는 **무료·오프라인 Windows 프로그램**입니다.
인터넷 없이 내 PC 안에서만 돌아가고, 녹음 파일이 밖으로 나가지 않습니다.

결과 예시: [`docs/예시_통화록.md`](docs/예시_통화록.md) · [`docs/예시_통화록.docx`](docs/예시_통화록.docx)

> 📱 **휴대폰에서는 웹앱으로 바로:** <https://adsobleproject.github.io/call-log-maker/>
> 녹음 텍스트(.txt)를 고르거나 붙여넣으면 그 자리에서 통화록이 만들어집니다. 설치·로그인·API 키 없이,
> 파일이 휴대폰 밖으로 나가지 않습니다.

---

## ⚡ 3줄 사용법

1. 이 저장소를 내려받아 압축을 푼다 (초록색 **Code ▸ Download ZIP**)
2. `input` 폴더에 녹음 파일(`.m4a` `.mp3` `.wav` `.ogg` `.flac`) 또는 텍스트(`.txt`)를 넣는다
3. **`실행_통화록변환.bat`** 을 더블클릭한다 → `output` 폴더에 통화록이 생긴다

> **처음 한 번만** Python 환경과 필요한 패키지를 자동으로 준비합니다(인터넷 필요).
> 준비는 두 단계로 나뉩니다.
> - **필수 패키지**(`python-docx`) — `.txt` 통화록 변환에 필요. 금방 끝납니다.
> - **선택 패키지**(`faster-whisper`) — 녹음 파일을 글자로 옮길 때 필요. 몇 분 걸립니다.
>
> 그래서 **녹음 파일 변환이 안 되는 PC라도 `.txt` 변환은 바로 됩니다.**
> 준비가 끝나면 그 다음부터는 인터넷 없이도 변환됩니다.

---

## 📄 결과물에 담기는 것

`📞 통화록 - {상대방/제목} ({YYYY-MM-DD HH:MM})` 형식의 문서 하나에:

| 항목 | 내용 |
| --- | --- |
| **기본 정보 표** | 일시, 상대방/제목, 원본 파일명, 소요 시간, 변환 방식, 화자, 분량 |
| **주요 키워드** | 대화에서 자주 나온 핵심 단어 (조사·군더더기 제거) |
| **핵심 요약** | 금액·일정·요청·약속이 담긴 문장을 규칙으로 골라 5줄 발췌 |
| **금액·일정** | `350만 원`, `11월 20일`, `내일` 같은 표현을 모아서 표시 |
| **후속 할 일** | 요청·약속·기한 문장을 체크리스트(`☐`)로 추출, 가능하면 담당·기한 표시 |
| **전체 대화 기록** | 화자와 타임스탬프가 붙은 원문 전체 (생략 없음) |

결과 파일 이름: `20261117_2100_김지훈_통화록.md` / `.docx`

---

## 📱 휴대폰에서 쓰기 (웹앱)

**<https://adsobleproject.github.io/call-log-maker/>**

PC 없이 휴대폰 브라우저에서 바로 씁니다. 삼성 “음성녹음” 앱에서 녹음을 텍스트로 저장한 뒤:

1. 위 주소를 연다 → 크롬 우상단 **⋮ → 앱 설치**(또는 **홈 화면에 추가**)를 누르면 주소창 없는 앱으로 설치됩니다
   · 설치하면 첫 실행 뒤에는 **인터넷 없이도** 열립니다(파일은 폰 안에서만 처리)
2. **.txt 파일 고르기** 또는 내용 **붙여넣기**
3. 상대방·일시는 파일명/본문에서 **자동으로 채워집니다** — 필요하면 고치고
4. **복사하기**(Markdown) · **.md** · **.docx** 저장, 또는 휴대폰 공유 시트로 바로 보내기

| 항목 | 내용 |
| --- | --- |
| 서버 | 없음 — 모든 계산이 브라우저 안에서 끝납니다 (무료, API 키·로그인 불필요) |
| 파일 전송 | 없음 — 고른 파일은 휴대폰을 떠나지 않습니다 |
| 결과 양식 | PC 버전과 같은 통화록 (같은 입력이면 같은 Markdown 이 나오도록 테스트로 고정) |
| 오프라인 | 한 번 열어 두면 인터넷 없이도 동작 (`index.html` 을 직접 열어도 됨) |

> 웹앱은 **텍스트(.txt)** 만 다룹니다. 녹음 파일(.m4a)을 글자로 옮기는 음성인식은 PC 버전에서 하세요.

### 📲 다른 앱에서 바로 보내기 (안드로이드 공유 메뉴)

홈 화면에 **앱으로 설치**한 뒤에는, 통화 녹음·메시지·파일 앱에서 **공유 → 통화록 변환기**를 누르면
`.txt` 파일이나 고른 글이 앱으로 바로 넘어와 통화록이 만들어진다.

| 항목 | 내용 |
| --- | --- |
| 어떻게 | 매니페스트의 `share_target` — `POST ./share-target`(multipart/form-data) |
| 넘길 수 있는 것 | `.txt`/`text/plain` 파일(삼성 음성녹음이 `application/octet-stream` 으로 넘기는 `.txt` 포함), 고른 글(text), 링크(url) |
| 처리 | 서비스 워커가 요청을 가로채 임시 캐시(`call-log-maker-share`)에 담고 `./?shared=1` 로 303 되돌림 → 화면이 바로 변환 |
| 지움 | 앱이 한 번 읽으면 임시 캐시에서 바로 삭제 (기기에 통화 내용이 남지 않음) |
| 안 되는 것 | 음성 파일(`.m4a`)은 브라우저에서 글자로 옮길 수 없어 안내만 띄운다 — 삼성 녹음 앱에서 **텍스트(.txt)로 변환한 뒤 공유**하거나 PC 버전을 쓰면 된다 |
| 조건 | 크롬(안드로이드)에서 **홈 화면에 앱으로 설치한 상태**여야 공유 시트에 뜬다. iOS 사파리는 `share_target` 을 지원하지 않는다 |
| 이미 설치해 둔 경우 | 크롬은 **설치할 때** 매니페스트를 읽어 공유 대상으로 등록한다. 공유 목록에 `.txt` 가 안 보이거나 예전 매니페스트로 설치돼 있다면, 홈 화면 아이콘을 지우고 다시 설치하면 된다. GitHub Pages 는 매니페스트를 **약 10분** 캐시하므로, 새 매니페스트를 올린 뒤에는 10분쯤 지나서 다시 설치해야 확실하다 |

---

## 🖱️ 세 가지 실행 방법

| 파일 | 언제 쓰나 |
| --- | --- |
| **`실행_통화록변환.bat`** | `input` 폴더에 모아 둔 파일을 **한 번에 전부** 변환 |
| **`드래그해서_변환.bat`** | 녹음 파일 1개(또는 여러 개)를 이 파일 **위로 끌어다 놓으면** 바로 변환 |
| **`폴더감시_자동변환.bat`** | 켜 두면 `input` 폴더에 새 파일이 들어올 때마다 **3초 안에 자동 변환** (끄려면 창에서 `Ctrl+C`) |
| **`설치_점검.bat`** | 설치가 잘 안 되거나 음성 변환이 안 될 때 — 환경을 점검하고 다시 설치를 시도 |

변환이 끝나면 결과 폴더(`output`)가 자동으로 열립니다.

### macOS / Linux

```bash
./run.sh                        # input 폴더 일괄 변환
./drag_and_drop.sh 녹음.m4a      # 지정한 파일만 변환
./watch.sh                      # 폴더 감시 자동 변환
```

---

## 🏷️ 파일 이름만 보고 자동으로 채우는 정보

| 파일 이름 예 | 상대방/제목 | 일시 |
| --- | --- | --- |
| `통화 녹음 홍길동_261117_210000.m4a` | 홍길동 | 2026-11-17 21:00 |
| `통화녹음_01012345678_231117_210000.m4a` | 01012345678 | 2023-11-17 21:00 |
| `녹음_20261117_1430.m4a` | 통화 녹음 | 2026-11-17 14:30 |
| `KakaoTalk_Audio_20261117_143000.m4a` | 통화 녹음 | 2026-11-17 14:30 |
| `회의 2026-11-17 14.30.m4a` | 회의 | 2026-11-17 14:30 |
| `통화 녹음 2026. 11. 17. 오후 9:00.m4a` | 통화 녹음 | 2026-11-17 21:00 |
| `보고서.m4a` | 보고서 | 파일 수정 시각 |

날짜·시각이 파일 이름에 없으면 파일을 마지막으로 저장한 시각을 씁니다.
텍스트 파일 안에 `제목:`, `녹음 일시:`, `길이:` 같은 머리말이 있으면 그 값을 우선 사용합니다.

---

## 📝 텍스트(.txt) 파일도 그대로 지원

이미 음성인식으로 텍스트를 뽑아 둔 경우(삼성 음성 녹음·갤럭시 AI·클로바 노트·에이닷 등)
**전사 과정 없이 즉시** 통화록이 됩니다. 아래처럼 제각각인 표기를 알아서 읽습니다.

```
00:00
화자 1
안녕하세요, 잘 지내셨어요?

00:05 화자 2: 네 덕분에 잘 지냈습니다.

[00:12] 참석자 1 - 그럼 내일 오후 세 시에 봬요.
김진혁: 발주서는 내일 오전에 보내겠습니다.
```

- 화자 라벨: `화자 1` `참석자 1` `Speaker 1` `홍길동:` `[홍길동]`
- 타임스탬프: `00:12` `1:02:03` `[00:12]` `(00:12.400)` `화자 1 (00:12)`
- 머리말: `음성 녹음` `2026. 11. 17. 오후 9:00` `길이 03:21` `제목: ...`
- 파일 인코딩: **UTF-16LE · UTF-16BE**(BOM 있음/없음 모두) · UTF-8 · EUC-KR(CP949)
  — 삼성 통화녹음이 내보내는 UTF-16LE 파일을 UTF-8 로 잘못 읽어 글자가 깨지던 문제를 막았습니다.

> **음성 파일**은 `faster-whisper` 로컬 음성인식으로 글자만 옮깁니다.
> **누가 말했는지(화자 분리)는 자동으로 나누지 않습니다.** 화자 구분이 필요하면
> 폰에서 텍스트로 변환해 `.txt` 로 넣는 쪽이 더 정확합니다.

---

## ☁️ 구글 드라이브 폴더와 함께 쓰기

폰에서 구글 드라이브로 올린 녹음/텍스트를 PC에서 한 번에 처리할 수 있습니다.
`config.json` 의 경로만 바꿔 주세요. (역슬래시 대신 `/` 를 쓰면 편합니다)

```json
{
  "input_dir": "C:/Users/내이름/Google Drive/내 드라이브/ClaudeCode-봉봉이 작업허브/01_요청함 (To_봉봉이)",
  "output_dir": "C:/Users/내이름/Google Drive/내 드라이브/ClaudeCode-봉봉이 작업허브/02_결과함 (From_봉봉이)",
  "processed_dir": "C:/Users/내이름/Google Drive/내 드라이브/ClaudeCode-봉봉이 작업허브/99_처리완료"
}
```

- 구글 드라이브는 동기화가 끝난 뒤에 파일이 완성되므로, 변환은 동기화 후에 실행하세요.
- 처리한 원본은 `processed_dir` 로 옮겨져 같은 파일을 두 번 변환하지 않습니다.
  이동이 싫으면 `"archive_processed": false` 로 바꾸세요(해시 기록으로 중복은 계속 막습니다).

---

## ⚙️ 설정 (`config.json`)

| 키 | 기본값 | 설명 |
| --- | --- | --- |
| `input_dir` / `output_dir` / `processed_dir` | `input` / `output` / `processed` | 폴더 경로(상대·절대 모두 가능) |
| `archive_processed` | `true` | 변환한 원본을 `processed_dir` 로 이동 |
| `keep_raw_transcript` | `false` | 음성 전사 원문(`_전사원문.txt`)도 함께 저장 |
| `watch_interval_sec` | `1.5` | 폴더 감시 주기(초) |
| `max_keywords` | `10` | 키워드 개수 |
| `max_summary_sentences` | `5` | 핵심 요약 문장 수 |
| `max_action_items` | `8` | 후속 할 일 개수 |
| `document_formats` | `["md","docx"]` | 만들 결과 형식 |
| `transcribe.model` | `small` | `tiny`/`base`/`small`/`medium`/`large-v3` (클수록 정확·느림) |
| `transcribe.language` | `ko` | 인식 언어 |
| `transcribe.device` | `auto` | `cpu` / `cuda` / `auto` |
| `transcribe.vad_filter` | `true` | 무음 구간 건너뛰기(속도·정확도 향상) |

**모델 크기 선택 가이드** (CPU 기준 대략)

| 모델 | 크기 | 1시간 녹음 처리 시간 | 특징 |
| --- | --- | --- | --- |
| `base` | ~150MB | 10~25분 | 빠름, 받아쓰기 품질 보통 |
| `small` | ~500MB | 20~50분 | **기본값**, 한국어 무난 |
| `medium` | ~1.5GB | 60~120분 | 정확하지만 느림 |

모델 파일은 첫 변환 때 한 번만 내려받고, 그 다음부터는 오프라인으로 씁니다.

---

## 🛠️ 처음 실행할 때 알아둘 점

- **Python 3.12 (64비트)** 를 권장합니다. 없으면 `_setup.bat` 이 설치된 Python 을 찾아 쓰고,
  음성 변환만 건너뛰고 `.txt` 변환으로 계속 진행합니다. `설치_점검.bat` 은 64비트 3.12 설치를
  물어보고 대신 설치해 줍니다(winget).
  - 한 줄 설치: `winget install -e --id Python.Python.3.12`
  - 또는 [python.org Windows 다운로드](https://www.python.org/downloads/windows/) 에서 **Windows installer (64-bit)** 3.12
    (설치 화면에서 **“Add python.exe to PATH”** 체크)
- 첫 실행 시 `.venv` 폴더가 생기고 패키지를 내려받습니다. 그 뒤로는 실행이 빠릅니다.
- 이미 있던 `.venv` 가 쓸 수 없는 상태(파이썬 없음·32비트 등)면 지우지 않고 `.venv.broken-<시각>` 으로
  옮겨 둔 뒤 새로 만듭니다. (옮겨 둔 폴더는 지워도 됩니다)
- Windows SmartScreen 경고가 뜨면 **추가 정보 ▸ 실행**을 누르면 됩니다. (직접 받은 파일이라 안전)
- 한 번에 많은 파일을 돌리면 시간이 걸립니다. 창을 닫지 말고 기다려 주세요.
- 지원하지 않는 파일(예: `.pdf`)과 빈 파일은 건너뜁니다.

### 문제가 생기면

먼저 **`설치_점검.bat`** 을 실행해 보세요. 환경을 점검하고, `.venv` 가 깨졌으면 새로 만들고,
음성 패키지 설치를 다시 시도합니다. 이 PC 의 Python 으로는 음성 패키지를 쓸 수 없으면(예: 32비트)
**64비트 Python 3.12 를 지금 설치할지 물어보고**, 설치하면 그 Python 으로 다시 준비합니다.
원하지 않으면 `n` 을 누르면 되고, `.txt` 변환은 그대로 됩니다.

음성 패키지는 **설치된 상태인데도** `.m4a` 를 읽지 못하는 경우가 있습니다(아래 `metadata_errors` 줄).
이때는 `설치_점검.bat` 이 오디오 라이브러리(`av`) 버전만 맞는 것으로 바꿔 줍니다.
예전 버전으로 설치해 둔 폴더라면, **`실행_통화록변환.bat` 을 한 번 실행할 때 자동으로 점검·복구**하고
그 다음부터는 원래처럼 빠르게 시작합니다.

| 증상 | 해결 |
| --- | --- |
| `Python was not found` | Python 설치 후 다시 실행. 한 줄: `winget install -e --id Python.Python.3.12` |
| `faster-whisper ... depends on onnxruntime`, `no matching distributions available for your environment: onnxruntime` | **32비트 Python** 이면 음성 패키지가 없습니다. 64비트 Python 3.12 를 설치하고 `설치_점검.bat` 실행 |
| `av-12.3.0.tar.gz` 를 빌드하다가 멈춤 / 오래 걸림 | 같은 이유(맞는 wheel 없음). 소스 빌드를 막아 두었으니 64비트 3.12 설치가 정답 |
| `음성 파일을 읽지 못했습니다: open() got an unexpected keyword argument 'metadata_errors'` | 오디오 라이브러리(`av`)가 **19 이상**으로 깔려 생기는 문제입니다(PyAV 19 에서 `metadata_errors` 인자가 없어짐). `설치_점검.bat` 을 실행하면 `av<19` 로 자동 교체됩니다. 직접 하려면 `.venv\Scripts\python -m pip install --upgrade "av>=12,<19"` |
| `huggingface_hub` symlink `UserWarning` 이 길게 출력 | 모델을 처음 받을 때만 나오는 Windows 안내입니다. 이 프로그램은 `HF_HUB_DISABLE_SYMLINKS_WARNING=1` 로 꺼 두었고, 혹시 보이면 무시해도 됩니다 |
| Python 3.13/3.14 에서 설치 실패 | 이 버전용 wheel 이 아직 없을 수 있습니다. 64비트 3.12 를 함께 설치한 뒤 `설치_점검.bat` 을 실행하면 3.12 로 맞춰 다시 준비합니다 |
| 음성 파일이 변환되지 않음 | 위 안내대로 64비트 Python 3.12 설치 → `설치_점검.bat` → `.venv\Scripts\python -m calllog doctor` 로 확인 |
| `.txt` 는 되는데 음성만 안 됨 | 정상 동작입니다(선택 패키지 미설치). 그대로 `.txt` 를 쓰거나 위 방법으로 음성 변환을 켜면 됩니다 |
| 받아쓰기가 부정확 | `config.json` 에서 `model` 을 `medium` 으로, 조용한 녹음 사용 |
| 결과가 안 생김 | `input` 폴더 위치와 `config.json` 의 `input_dir` 가 같은지 확인 |
| 패키지가 꼬임 | `설치_점검.bat` 실행. 그래도 안 되면 `.venv` 폴더를 지우고 다시 실행(자동 재설치) |

---

## 🧑‍💻 개발자용

```
calllog/
  cli.py         명령줄(batch / files / watch / doctor / demo)
  compat.py      Python 버전·비트 판단, 음성 패키지 가능 여부, 안내 문구
  config.py      config.json 로드
  filenames.py   파일명 → 제목·일시
  parsers.py     txt 화자/타임스탬프 파싱
  transcribe.py  faster-whisper 전사(엔진 교체 가능)
  analyze.py     키워드·요약·할 일·금액/일정 추출
  render.py      .md / .docx 생성
  pipeline.py    중복 방지·결과 저장·원본 이동
  watcher.py     폴더 감시
docs/            휴대폰 웹앱 (GitHub Pages 로 그대로 배포 · 빌드 없음)
  index.html     화면
  manifest.json  PWA 매니페스트 — 홈 화면에 앱으로 설치 · 안드로이드 공유 메뉴(share_target)
  sw.js          서비스 워커 (네트워크 우선 · 오프라인 셸 캐시 'call-log-maker-v2' · POST ./share-target 처리)
  icons/         앱 아이콘 (icon.svg · 192 · 512 · maskable · 애플 180)
  assets/app.js  화면 조작 — 입력창은 다시 그리지 않는다(한글 조합 보호)
  assets/lib/    util.js(zip·crc32) · filenames.js · parsers.js · analyze.js · render.js · docx.js · build.js
                 ↑ PC 버전(calllog/*.py)을 그대로 옮긴 것 — 같은 결과가 나오는지 테스트로 비교
setup_env.py     환경 준비(.venv 생성·복구, 필수→선택 패키지 순서 설치)
requirements.txt        필수: python-docx
requirements-audio.txt  선택: faster-whisper + av<19 (음성 변환, PyAV 19 는 faster-whisper 와 비호환)
tests/           194개 자동화 테스트 (웹앱 JS · PWA · 공유 메뉴 테스트 포함)
  test_pwa.py           매니페스트·아이콘·서비스 워커 검사
  test_share_target.py  공유 메뉴: 매니페스트 스키마 · POST 가로채기 · ?shared=1 화면 처리
  web/run_js_tests.js   브라우저 없이 도는 JS 테스트 (Node 또는 quickjs)
  web/dom_stub.js       app.js 화면 점검용 최소 DOM
  web/sw_stub.js        sw.js 점검용 서비스 워커 흉내 (Response·caches·URL)
samples/         예시 txt 3종
```

```bash
python setup_env.py --check                 # 환경 상태만 확인(아무것도 바꾸지 않음)
python setup_env.py --core-only             # .txt 변환용 패키지만 설치
python setup_env.py --repair                # 음성 패키지 설치 다시 시도
python -m unittest discover -s tests -t .   # 테스트 (웹앱 JS 테스트는 quickjs 가 있을 때만 실행)
pip install quickjs                         # 웹앱 JS 테스트까지 돌릴 때 (없으면 그 22개는 건너뜀)
node tests/web/run_js_tests.js              # Node 가 있으면 JS 테스트만 따로
python -m calllog demo                      # 샘플로 결과 미리보기
python -m calllog doctor                    # 설치·설정 점검
python -m calllog batch --config 내설정.json
```

전사 엔진은 `Transcriber` 인터페이스로 분리되어 있어, 테스트에서는 모델 없이
`MockTranscriber` 로 파이프라인 전체를 검증합니다.

---

## 🔒 개인정보

- 모든 처리는 내 PC에서만 이루어집니다. 녹음 파일·결과물이 서버로 전송되지 않습니다.
- 휴대폰 웹앱(`docs/`)도 서버가 없습니다. 고른 파일은 브라우저 메모리에서만 읽고, 아무 곳에도 저장·전송하지 않습니다
  (입력 내용을 브라우저 저장소에도 남기지 않습니다).
- 공유 메뉴로 받은 내용은 **임시 캐시(`call-log-maker-share`)에 잠시만** 담고, 앱이 한 번 읽으면 바로 지웁니다(변환 후 남지 않음).
- 모델 최초 다운로드 때만 Hugging Face에 접속합니다.
- `input/`, `output/`, `processed/` 내용은 `.gitignore` 로 제외되어 GitHub에 올라가지 않습니다.
