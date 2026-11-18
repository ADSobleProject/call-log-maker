/* 웹앱(JS) 테스트 — 브라우저 없이 돌린다.
 *
 *   node tests/web/run_js_tests.js        (Node 가 있을 때)
 *   python3 tests/test_web_js.py          (quickjs 로 같은 파일을 실행)
 *
 * 두 경우 모두 같은 라이브러리(docs/assets/lib/*.js)를 읽어 검증한다.
 */
(function (root) {
  "use strict";

  var LIB_FILES = ["util.js", "filenames.js", "parsers.js", "analyze.js", "render.js", "docx.js", "build.js"];
  var isNode = typeof process !== "undefined" && process.versions && process.versions.node && typeof require === "function";

  if (isNode) {
    var fs = require("fs");
    var path = require("path");
    var vm = require("vm");
    var base = path.join(__dirname, "..", "..", "docs", "assets", "lib");
    LIB_FILES.forEach(function (name) {
      vm.runInThisContext(fs.readFileSync(path.join(base, name), "utf8"), { filename: name });
    });
  }

  var CallLog = root.CallLog;
  var pass = 0;
  var failures = [];

  function ok(condition, name, detail) {
    if (condition) {
      pass += 1;
      return true;
    }
    failures.push(name + (detail ? "\n    " + detail : ""));
    return false;
  }

  function eq(actual, expected, name) {
    var a = JSON.stringify(actual);
    var b = JSON.stringify(expected);
    return ok(a === b, name, "기대 " + b + "\n    실제 " + a);
  }

  function stamp(date) {
    if (!date) return null;
    var p = CallLog.util.pad2;
    return (
      date.getFullYear() + "-" + p(date.getMonth() + 1) + "-" + p(date.getDate()) +
      " " + p(date.getHours()) + ":" + p(date.getMinutes())
    );
  }

  /* ---------------------------------------------------------------- 샘플 원문 */
  var SAMPLE_CALL = [
    "음성 녹음",
    "2026. 11. 17. 오후 9:00",
    "길이 03:21",
    "",
    "00:00",
    "화자 1",
    "여보세요, 안녕하세요. JFC 마케팅팀 김진혁입니다.",
    "",
    "00:05",
    "화자 2",
    "네, 안녕하세요. 소블 매거진 김지훈 대리입니다. 문의 주신 매장 오픈 기념 배너 인쇄 건으로 연락드렸어요.",
    "",
    "00:12",
    "화자 1",
    "아 네, 지훈 대리님. 견적서 잘 받았습니다. 사이즈가 600 곱하기 1800으로 12개 맞죠?",
    "",
    "00:21",
    "화자 2",
    "네 맞습니다. 양면 인쇄에 후가공까지 포함해서 부가세 포함 350만 원으로 견적 드렸습니다.",
    "",
    "00:29",
    "화자 1",
    "금액은 예산 안에 들어오는데, 납기가 11월 20일까지 가능할까요? 다음 주 금요일이 오픈이라서요.",
    "",
    "00:37",
    "화자 2",
    "네, 20일 오전까지는 납품 가능합니다. 대신 시안 확정이 18일까지 되어야 일정이 안 밀려요.",
    "",
    "00:46",
    "화자 1",
    "알겠습니다. 그럼 제가 내일 오전까지 내부 결재 올려서 시안 수정 요청 드릴게요. 수정은 두 번까지 가능한 거죠?",
    "",
    "00:56",
    "화자 2",
    "네, 시안 수정 2회까지 포함입니다. 추가 수정은 건당 5만 원이에요.",
    "",
    "01:04",
    "화자 1",
    "좋습니다. 결제 조건은 어떻게 되나요?",
    "",
    "01:09",
    "화자 2",
    "계약금 50퍼센트 선입금, 잔금은 납품 확인 후 일주일 안에 결제해 주시면 됩니다. 세금계산서는 발행해 드릴게요.",
    "",
    "01:20",
    "화자 1",
    "네, 그럼 계약금은 175만 원이네요. 발주서는 내일 오전 중으로 보내드리고, 입금은 발주서 확인 후에 진행하겠습니다.",
    "",
    "01:31",
    "화자 2",
    "감사합니다. 그럼 18일까지 시안 확정해 주시면 20일 오전 설치까지 제가 챙기겠습니다.",
    "",
    "01:39",
    "화자 1",
    "네, 잘 부탁드립니다. 혹시 설치 기사님 오시는 시간은 몇 시쯤 될까요?",
    "",
    "01:45",
    "화자 2",
    "오전 10시 전후로 도착한다고 안내드렸는데, 확정되면 문자로 다시 알려드릴게요.",
    "",
    "01:52",
    "화자 1",
    "좋습니다. 그럼 내일 오전에 발주서와 시안 수정안 함께 보내겠습니다. 수고하셨습니다.",
    "",
    "01:58",
    "화자 2",
    "네, 진혁 팀장님. 좋은 저녁 되세요.",
  ].join("\n");

  var SAMPLE_CLOVA = [
    "통화 녹음 - 박서연 실장",
    "2026-11-17 14:30",
    "",
    "00:00:12 화자 1: 여보세요, 몽펠리에 박서연 실장님 맞으시죠? 저 김진혁입니다.",
    "00:00:18 화자 2: 네, 진혁님 안녕하세요. 예식 계약서 수정본 관련해서 연락드렸어요.",
    "00:00:25 화자 1: 아 네, 메일로 받았습니다. 보증 인원이 200명으로 바뀌었더라고요.",
    "00:00:33 화자 2: 네, 지난주 상담 때 말씀하신 대로 200명으로 조정했고, 1인당 식대는 8만 5천 원으로 계산했습니다.",
    "00:00:44 화자 1: 총액이 얼마로 나오나요?",
    "00:00:48 화자 2: 식대 포함 1억 7천만 원이고, 여기에 부가세 별도입니다. 계약금은 총액의 10퍼센트인 1,700만 원이에요.",
    "00:01:02 화자 1: 계약금 입금 기한이 언제까지였죠?",
    "00:01:07 화자 2: 이번 주 금요일까지입니다. 입금 확인되면 예식 날짜를 확정으로 잡아 드려요.",
    "00:01:15 화자 1: 알겠습니다. 금요일 오전에 입금하고 문자로 알려드릴게요. 혹시 계약서에 식대 인상 조항이 있나요?",
    "00:01:26 화자 2: 1년에 5퍼센트까지 인상 가능하다는 조항이 있는데, 2027년 5월 예식이면 내년 인상분만 적용돼서 실제로는 거의 영향 없습니다.",
    "00:01:38 화자 1: 다행이네요. 그럼 수정된 계약서는 언제 받을 수 있을까요?",
    "00:01:43 화자 2: 오늘 오후에 다시 보내드릴게요. 서명은 다음 주 월요일까지 주시면 됩니다.",
    "00:01:50 화자 1: 네, 확인하고 서명해서 보내드리겠습니다. 감사합니다.",
  ].join("\n");

  var SAMPLE_NAMES = [
    "녹음 일시: 2026년 11월 15일 오전 10시",
    "제목: 주말 매장 점검 회의",
    "길이: 3분 40초",
    "",
    "김진혁: 오늘 매장 오픈 준비 상황부터 보죠. 인력은 다 채워졌어요?",
    "",
    "이수민: 홀 직원은 세 명 확정됐고, 주방 보조 한 명은 다음 주 수요일 면접 봅니다.",
    "",
    "김진혁: 그럼 오픈일인 11월 28일 전에는 교육이 끝나나요?",
    "",
    "이수민: 주방 보조가 늦어도 11월 24일이면 들어올 수 있어서 이틀 교육은 가능합니다.",
    "",
    "김진혁: 다행이네요. 시식회는 12월 5일로 잡을까 하는데 예산은 얼마로 볼까요?",
    "",
    "이수민: 재료비 포함 120만 원 정도면 충분할 것 같습니다. 홍보물은 기존 디자인 재사용하면 추가 비용 없어요.",
    "",
    "김진혁: 좋아요. 그럼 시식회 예산은 120만 원으로 정리하고, 이수민 님이 11월 20일까지 참석자 명단 만들어 주세요.",
    "",
    "이수민: 네, 알겠습니다. 명단은 20일까지 정리해서 공유드릴게요.",
    "",
    "김진혁: 그리고 매장 오픈 당일 SNS 이벤트는 누가 맡죠?",
    "",
    "이수민: 제가 맡을게요. 오픈 하루 전까지 이미지 세 장 준비하겠습니다.",
    "",
    "김진혁: 좋습니다. 그럼 다음 회의는 11월 22일 오후 두 시에 하죠.",
    "",
  ].join("\n");

  /* ================================================================ 파일명 */
  (function testFilenames() {
    var cases = [
      ["통화 녹음 김지훈_261117_210000.txt", "김지훈", "2026-11-17 21:00", true],
      ["통화녹음_01012345678_20231117_210000.txt", "01012345678", "2023-11-17 21:00", true],
      ["녹음_20261117_1430.txt", "통화 녹음", "2026-11-17 14:30", true],
      ["2026-11-17 14.30.txt", "통화 녹음", "2026-11-17 14:30", true],
      ["통화 녹음 2026. 11. 17. 오후 9:00.txt", "통화 녹음", "2026-11-17 21:00", true],
      ["2026년 11월 17일 오후 9시 30분.txt", "통화 녹음", "2026-11-17 21:30", true],
      ["KakaoTalk_Audio_20261117_143000.txt", "통화 녹음", "2026-11-17 14:30", true],
      ["회의 2026-11-17 14.30.txt", "회의", "2026-11-17 14:30", true],
      ["그냥이름.txt", "그냥이름", null, false],
    ];
    cases.forEach(function (item) {
      var info = CallLog.filenames.parseFilename(item[0]);
      eq(info.title, item[1], "파일명 제목: " + item[0]);
      eq(stamp(info.when), item[2], "파일명 일시: " + item[0]);
      eq(info.timeKnown, item[3], "파일명 시각 여부: " + item[0]);
    });

    var titles = [
      ["통화 녹음", ""],
      ["김지훈_2", "김지훈"],
      ["20261117_2100", "20261117 2100"],
      ["회의", "회의"],
      ["회의 자료", "자료"],
      ["  __김지훈  대리__ ", "김지훈 대리"],
      ["voice recorder 2026-11-17", ""],
      ["새 녹음 (2)", "2"],
    ];
    titles.forEach(function (item) {
      eq(CallLog.filenames.cleanTitle(item[0]), item[1], "제목 다듬기: " + item[0]);
    });

    eq(CallLog.filenames.safeFilename("김지훈/대리: *통화*"), "김지훈 대리 통화", "파일 이름 안전 처리");
    eq(CallLog.filenames.safeFilename(""), "통화 녹음", "빈 파일 이름 대체");
  })();

  /* ================================================================ 파서 */
  (function testParser() {
    eq(CallLog.parsers.parseTimestamp("00:05"), 5, "타임스탬프 분:초");
    eq(CallLog.parsers.parseTimestamp("1:02:03"), 3723, "타임스탬프 시:분:초");
    eq(CallLog.parsers.parseTimestamp("[00:12]"), 12, "대괄호 타임스탬프");
    eq(CallLog.parsers.parseTimestamp("안녕"), null, "타임스탬프 아님");
    eq(CallLog.parsers.formatTimestamp(5), "00:05", "타임스탬프 출력");
    eq(CallLog.parsers.formatTimestamp(3723), "1:02:03", "타임스탬프 출력(시)");
    eq(CallLog.parsers.parseDuration("3분 40초"), 220, "소요 시간 한글");
    eq(CallLog.parsers.parseDuration("03:21"), 201, "소요 시간 시:분");

    var one = CallLog.parsers.parseText(SAMPLE_CALL, "통화 녹음 김지훈_261117_210000.txt");
    eq(one.segments.length, 16, "삼성 녹음: 발화 수");
    eq(one.segments[0].speaker, "화자 1", "삼성 녹음: 첫 화자");
    eq(one.segments[0].start, 0, "삼성 녹음: 첫 타임스탬프");
    eq(one.segments[one.segments.length - 1].start, 118, "삼성 녹음: 마지막 타임스탬프");
    eq(one.durationSec, 201, "삼성 녹음: 머리말 길이");
    eq(stamp(one.when), "2026-11-17 21:00", "삼성 녹음: 머리말 일시");
    eq(one.warnings.length, 0, "삼성 녹음: 경고 없음");

    var two = CallLog.parsers.parseText(SAMPLE_CLOVA, "클로바노트_예시.txt");
    eq(two.segments.length, 13, "클로바노트: 발화 수");
    eq(two.segments[0].start, 12, "클로바노트: 첫 타임스탬프");
    eq(two.segments[two.segments.length - 1].start, 110, "클로바노트: 마지막 타임스탬프");
    eq(two.title, "박서연 실장", "클로바노트: 머리말 제목");

    var three = CallLog.parsers.parseText(SAMPLE_NAMES, "일반대화_예시.txt");
    eq(three.segments.length, 11, "이름 라벨: 발화 수");
    eq(
      three.segments.filter(function (s) {
        return s.speaker === "이수민";
      }).length > 0,
      true,
      "이름 라벨: 화자 인식(이수민)"
    );
    eq(three.title, "주말 매장 점검 회의", "이름 라벨: 제목 줄");
    eq(stamp(three.when), "2026-11-15 10:00", "이름 라벨: 일시 줄");
    eq(three.durationSec, 220, "이름 라벨: 길이 줄");

    var bracket = CallLog.parsers.parseText("[00:12] 참석자 1 - 그럼 내일 오후 세 시에 봬요.\n\nSpeaker 2: OK, see you then.", "");
    eq(bracket.segments.length, 2, "대괄호+영문 라벨: 발화 수");
    eq(bracket.segments[0].speaker, "참석자 1", "대괄호 라벨 유지");
    eq(bracket.segments[1].speaker, "화자 2", "Speaker → 화자 변환");
    eq(bracket.segments[0].start, 12, "대괄호 타임스탬프 값");

    var plain = CallLog.parsers.parseText("그냥 대화를 적어 둔 문장입니다. 두 번째 문장도 있습니다.", "");
    eq(plain.segments.length, 1, "라벨 없는 글: 한 덩어리");
    eq(plain.segments[0].speaker, null, "라벨 없는 글: 화자 없음");

    var empty = CallLog.parsers.parseText("   \n\n  ", "");
    eq(empty.segments.length, 0, "빈 글: 발화 없음");
    eq(empty.warnings.length, 1, "빈 글: 경고 1건");

    // 삼성 통화녹음: '화자 1 (00:01)' 처럼 라벨 줄 끝에 시각이 붙는 형태
    var stamped = CallLog.parsers.parseText(
      "화자 1 (00:01)\n네, 안녕하세요. JFC 마케팅팀 김진혁입니다.\n\n화자 2 (00:14)\n네 안녕하세요, 박동근입니다.",
      ""
    );
    eq(stamped.segments.length, 2, "라벨+시각: 발화 수");
    eq(stamped.segments[0].speaker, "화자 1", "라벨+시각: 화자");
    eq(stamped.segments[0].start, 1, "라벨+시각: 시각 인식");
    eq(stamped.segments[0].text, "네, 안녕하세요. JFC 마케팅팀 김진혁입니다.", "라벨+시각: 시각이 본문에 남지 않음");
    eq(stamped.segments[1].start, 14, "라벨+시각: 두 번째 시각");
  })();

  /* ================================================================ 인코딩 */
  (function testDecodeTextBytes() {
    function utf16Bytes(str, bigEndian) {
      var bytes = [];
      for (var i = 0; i < str.length; i++) {
        var code = str.charCodeAt(i);
        if (bigEndian) bytes.push((code >> 8) & 0xff, code & 0xff);
        else bytes.push(code & 0xff, (code >> 8) & 0xff);
      }
      return bytes;
    }
    function withPrefix(prefix, bytes) {
      return new Uint8Array(prefix.concat(bytes));
    }
    function decode(bytes) {
      return CallLog.util.decodeTextBytes(new Uint8Array(bytes));
    }

    var sample = "AI 음성 인식\n2026. 11. 17. 오후 2:31\n길이 00:41\n\n화자 1 (00:01)\n네, 안녕하세요. JFC 마케팅팀 김진혁입니다.\n\n화자 2 (00:14)\n네 안녕하세요, 박동근입니다.";
    var le = utf16Bytes(sample, false);
    var be = utf16Bytes(sample, true);

    eq(decode([0xff, 0xfe].concat(le)), sample, "인코딩: UTF-16LE + BOM");
    eq(decode([0xfe, 0xff].concat(be)), sample, "인코딩: UTF-16BE + BOM");
    eq(decode(le), sample, "인코딩: UTF-16LE (BOM 없음)");
    eq(decode(be), sample, "인코딩: UTF-16BE (BOM 없음)");
    eq(decode(CallLog.util.utf8Encode(sample)), sample, "인코딩: UTF-8");
    eq(decode([0xef, 0xbb, 0xbf].concat(Array.prototype.slice.call(CallLog.util.utf8Encode(sample)))), sample, "인코딩: UTF-8 + BOM");

    // 녹음 앱이 섞어 넣는 널바이트는 결과에 남지 않아야 한다
    eq(decode([0xff, 0xfe].concat(le, [0x00, 0x00])).indexOf("\u0000") < 0, true, "인코딩: 널바이트 제거");
    eq(decode([0xff, 0xfe].concat(le)).charCodeAt(0), "A".charCodeAt(0), "인코딩: BOM 이 본문에 남지 않음");
    eq(decode([]), "", "인코딩: 빈 파일");

    // ASCII 위주 UTF-16LE 를 UTF-8 로 잘못 읽으면 나오던 깨진 글자(Tĭ 1 …)가 없어야 한다
    var asciiLe = utf16Bytes("화자 1 (00:01)\nhello", false);
    var fixed = decode(asciiLe);
    eq(fixed.indexOf("화자 1 (00:01)") >= 0, true, "인코딩: 한국어+ASCII 혼합 UTF-16LE");
    eq(fixed.indexOf("\u0590") < 0, true, "인코딩: 깨진 문자 없음");
  })();

  /* ================================================================ 분석 */
  (function testAnalyze() {
    var one = CallLog.parsers.parseText(SAMPLE_CALL, "통화 녹음 김지훈_261117_210000.txt");
    var text = one.segments.map(function (s) { return s.text; }).join("\n");
    var kws = CallLog.analyze.keywords(text, 10);
    eq(kws, ["시안", "수정", "계약금", "오픈", "인쇄", "납품", "확인", "설치", "마케팅팀", "JFC"], "키워드 추출");
    eq(CallLog.analyze.amountsIn(text), ["350만 원", "5만 원", "175만 원"], "금액 추출");
    eq(CallLog.analyze.datesIn(text), ["11월 20일", "다음 주", "금요일", "내일", "오전 10시"], "일정 추출");
    eq(CallLog.analyze.summarize(one.segments, 5, kws).length, 5, "요약 문장 수");
    var actions = CallLog.analyze.extractActions(one.segments, 8, ["화자 1", "화자 2"]);
    eq(actions.length, 8, "후속 할 일 수");
    eq(actions[0].text.indexOf("납기가 11월 20일까지") >= 0, true, "후속 할 일 첫 문장");
    eq(actions[0].due, "11월 20일까지", "후속 할 일 기한");
    eq(actions[1].owner, "화자 1", "후속 할 일 담당");
    eq(CallLog.analyze.stripJosa("계약금은"), "계약금", "조사 제거");

    var empty = CallLog.parsers.parseText("", "");
    eq(CallLog.analyze.keywords("", 10), [], "빈 글 키워드");
    eq(CallLog.analyze.summarize([], 5, []), [], "빈 글 요약");
    eq(CallLog.analyze.extractActions([], 8, []), [], "빈 글 할 일");
  })();

  /* ================================================================ 문서 */
  function buildSample() {
    return CallLog.buildDocument({
      text: SAMPLE_CALL,
      fileName: "통화 녹음 김지훈_261117_210000.txt",
      now: new Date(2026, 10, 17, 21, 5, 0),
    });
  }

  (function testDocument() {
    var doc = buildSample();
    eq(doc.title, "김지훈", "문서: 제목");
    eq(stamp(doc.when), "2026-11-17 21:00", "문서: 일시");
    eq(doc.sourceName, "통화 녹음 김지훈_261117_210000.txt", "문서: 원본 파일명");
    eq(doc.mode, "텍스트 변환본", "문서: 변환 방식");
    eq(doc.speakers, ["화자 1", "화자 2"], "문서: 화자 목록");
    eq(doc.utteranceCount, 16, "문서: 발화 수");
    eq(doc.warnings.length, 0, "문서: 경고 없음");
    eq(CallLog.outputName(doc, "md"), "20261117_2100_김지훈_통화록.md", "문서: 결과 파일명");

    var paste = CallLog.buildDocument({
      text: SAMPLE_CALL,
      now: new Date(2026, 10, 17, 21, 5, 0),
      title: "김지훈 대리",
      when: new Date(2026, 10, 17, 21, 0, 0),
    });
    eq(paste.sourceName, "붙여넣은 텍스트", "붙여넣기: 원본 표기");
    eq(paste.title, "김지훈 대리", "붙여넣기: 사용자가 고친 제목");
    eq(stamp(paste.when), "2026-11-17 21:00", "붙여넣기: 사용자가 고친 일시");

    var blank = CallLog.buildDocument({ text: "", now: new Date(2026, 10, 17, 9, 0, 0) });
    eq(blank.warnings.length, 2, "빈 문서: 경고 2건(파서+파이프라인)");
    eq(blank.title, "통화 녹음", "빈 문서: 기본 제목");
  })();

  /* ================================================================ Markdown */
  (function testMarkdown() {
    var doc = buildSample();
    var md = CallLog.render.toMarkdown(doc);

    ok(md.indexOf("# 📞 통화록 - 김지훈 (2026-11-17 21:00)\n") === 0, "Markdown: 제목 줄");
    ok(md.indexOf("> 이미 텍스트로 변환된 기록을 정리한 통화록입니다.") > 0, "Markdown: 안내 문구");
    ok(md.indexOf("## 📋 기본 정보") > 0, "Markdown: 기본 정보 절");
    ok(md.indexOf("| 일시 | 2026-11-17 (화) 21:00 |") > 0, "Markdown: 일시(요일) 표기");
    ok(md.indexOf("| 상대방/제목 | 김지훈 |") > 0, "Markdown: 상대방 행");
    ok(md.indexOf("| 분량 | 16개 발화 · 620자 |") > 0 || /\| 분량 \| 16개 발화 · [\d,]+자 \|/.test(md), "Markdown: 분량 행");
    ok(md.indexOf("| 작성 | 2026-11-17 21:05 |") > 0, "Markdown: 작성 시각");
    ok(md.indexOf("## 🔑 주요 키워드") > 0, "Markdown: 키워드 절");
    ok(md.indexOf("`시안`") > 0, "Markdown: 키워드 코드 표기");
    ok(md.indexOf("## 📌 핵심 요약") > 0, "Markdown: 요약 절");
    ok(md.indexOf("1. ") > 0, "Markdown: 요약 번호");
    ok(md.indexOf("## 💰 금액·일정") > 0, "Markdown: 금액·일정 절");
    ok(md.indexOf("- **금액**: 350만 원") > 0, "Markdown: 금액 줄");
    ok(md.indexOf("## ✅ 후속 할 일") > 0, "Markdown: 할 일 절");
    ok(md.indexOf("- [ ] ") > 0, "Markdown: 체크리스트");
    ok(md.indexOf("## 💬 전체 대화 기록") > 0, "Markdown: 전체 대화 절");
    ok(md.indexOf("**화자 1** `00:00`\n\n여보세요, 안녕하세요.") > 0, "Markdown: 화자·타임스탬프 머리");
    ok(md.indexOf("*call-log-maker 로 자동 생성 · 내용은 원본 기록을 확인해 주세요.*") > 0, "Markdown: 꼬리 문구");
    ok(md.trim().slice(-1) === "*", "Markdown: 문서 끝");

    var withPipe = CallLog.buildDocument({
      text: "화자 1: 파이프 | 기호가 있는 문장입니다.",
      fileName: "통화 녹음 테스트_261117_210000.txt",
      now: new Date(2026, 10, 17, 21, 5, 0),
      title: "테스트|상대",
    });
    ok(CallLog.render.toMarkdown(withPipe).indexOf("| 상대방/제목 | 테스트\\|상대 |") > 0, "Markdown: 파이프 이스케이프");

    var html = CallLog.render.toPreviewHtml(doc);
    ok(html.indexOf('class="doc-title"') > 0, "미리보기: 제목");
    ok(html.indexOf("<table") > 0, "미리보기: 정보 표");
    var xss = CallLog.buildDocument({ text: "화자 1: <script>alert(1)</script>", now: new Date() });
    ok(CallLog.render.toPreviewHtml(xss).indexOf("<script>") < 0, "미리보기: HTML 이스케이프");
  })();

  /* ================================================================ DOCX */
  (function testDocx() {
    var doc = buildSample();
    var bytes = CallLog.docx.build(doc);
    ok(bytes instanceof Uint8Array, "DOCX: Uint8Array 반환");
    ok(bytes.length > 3000, "DOCX: 크기 (" + bytes.length + " bytes)");
    eq(Array.from(bytes.slice(0, 4)), [0x50, 0x4b, 0x03, 0x04], "DOCX: ZIP 시그니처 PK\\x03\\x04");

    var entries;
    try {
      entries = CallLog.util.unzip(bytes);
    } catch (err) {
      ok(false, "DOCX: ZIP 읽기", String(err));
      return;
    }
    var names = entries.map(function (e) {
      return e.name;
    });
    eq(
      names.sort(),
      [
        "[Content_Types].xml",
        "_rels/.rels",
        "docProps/app.xml",
        "docProps/core.xml",
        "word/_rels/document.xml.rels",
        "word/document.xml",
        "word/styles.xml",
      ],
      "DOCX: 필요한 부품 목록"
    );

    entries.forEach(function (entry) {
      eq(CallLog.util.crc32(entry.data), entry.crc, "DOCX: CRC 일치 " + entry.name);
      var text = new CallLog.util.Utf8Decoder().decode(entry.data);
      ok(text.indexOf("<?xml") === 0, "DOCX: XML 선언 " + entry.name);
      ok(text.slice(-1) === ">", "DOCX: XML 끝맺음 " + entry.name);
    });

    var decoder = new CallLog.util.Utf8Decoder();
    var documentXml = decoder.decode(
      entries.filter(function (e) {
        return e.name === "word/document.xml";
      })[0].data
    );
    ok(documentXml.indexOf("<w:document") > 0, "DOCX: w:document 루트");
    ok(documentXml.indexOf("통화록 - 김지훈 (2026-11-17 21:00)") > 0, "DOCX: 제목 본문");
    ok(documentXml.indexOf("기본 정보") > 0, "DOCX: 기본 정보 머리");
    ok(documentXml.indexOf("전체 대화 기록") > 0, "DOCX: 전체 대화 머리");
    ok(documentXml.indexOf("<w:tbl>") > 0, "DOCX: 정보 표");
    ok(documentXml.indexOf("시안") > 0, "DOCX: 키워드 본문");
    ok(documentXml.indexOf("<w:sectPr>") > 0, "DOCX: 페이지 설정");

    var styles = decoder.decode(
      entries.filter(function (e) {
        return e.name === "word/styles.xml";
      })[0].data
    );
    ok(styles.indexOf('w:eastAsia="맑은 고딕"') > 0, "DOCX: 한글 글꼴");

    // XML 이 깨지지 않았는지: 태그 열고 닫음 수가 맞는지 대략 확인
    var opens = (documentXml.match(/<w:p>/g) || []).length;
    var closes = (documentXml.match(/<\/w:p>/g) || []).length;
    eq(opens, closes, "DOCX: 문단 태그 짝");

    // 특수문자 이스케이프
    var tricky = CallLog.buildDocument({ text: "화자 1: A&B <태그> \"인용\"", now: new Date() });
    var trickyXml = CallLog.docx.documentXml(tricky);
    ok(trickyXml.indexOf("A&amp;B &lt;태그&gt;") > 0, "DOCX: XML 이스케이프");
    ok(trickyXml.indexOf("<태그>") < 0, "DOCX: 원시 태그 없음");
  })();

  /* ================================================================ 결과 */
  var message = "JS 테스트: " + pass + "건 통과, " + failures.length + "건 실패";
  if (failures.length) message += "\n\n" + failures.join("\n");
  root.__jsTestResult = { pass: pass, fail: failures.length, failures: failures, message: message };

  if (typeof console !== "undefined" && console.log) console.log(message);
  if (isNode && failures.length) process.exitCode = 1;
})(typeof globalThis !== "undefined" ? globalThis : this);
