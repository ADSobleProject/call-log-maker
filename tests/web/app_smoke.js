/* 가짜 DOM 위에서 app.js 를 실제로 돌려 보는 점검.
 *
 * 확인하는 것:
 *   - 화면 코드가 로드되다 터지지 않는지
 *   - 파일을 고르면 파일명에서 상대방·일시가 자동으로 채워지는지
 *   - 붙여넣기(입력) 때 textarea 값을 건드리지 않는지 (한글 조합 보호)
 *   - 잘못된 일시를 지우면 "일시 미상"이 되는지
 *   - 미리보기 HTML 이 통화록 절을 모두 담는지
 *
 * 실행: tests/test_web_js.py (quickjs) 에서 dom_stub.js → app.js → 이 파일 순서로.
 */
(function (root) {
  "use strict";

  var pass = 0;
  var failures = [];
  var els = root.__dom.elements;

  function ok(condition, name, detail) {
    if (condition) {
      pass += 1;
      return;
    }
    failures.push(name + (detail ? "\n    " + detail : ""));
  }

  function flush() {
    root.__dom.flushTimers();
  }

  function typeInto(element, text) {
    // 사용자가 친 것처럼 값을 넣고 input 이벤트만 보낸다 (값을 되돌려 쓰지 않음)
    element.value = text;
    element.dispatch("input");
    flush();
  }

  // ---------------------------------------------------------------- 1) 첫 화면
  ok(els.preview.innerHTML.indexOf("통화록") >= 0, "첫 화면: 안내 문구 표시");
  ok(els.copy.disabled === true, "첫 화면: 복사 버튼 비활성");

  // ---------------------------------------------------------------- 2) 붙여넣기
  var text = "00:00\n화자 1\n여보세요, 잘 지내셨어요?\n\n00:05 화자 2: 네, 덕분에 잘 지냈습니다.\n";
  typeInto(els.text, text);
  ok(els.text.value === text, "붙여넣기: 입력값 그대로 유지 (조합 보호)");
  ok(els.preview.innerHTML.indexOf("📞 통화록 -") >= 0, "붙여넣기: 미리보기 제목");
  ok(els.preview.innerHTML.indexOf("전체 대화 기록") >= 0, "붙여넣기: 전체 대화 절");
  ok(els.preview.innerHTML.indexOf("여보세요, 잘 지내셨어요?") >= 0, "붙여넣기: 본문 표시");
  ok(els.status.textContent.indexOf("발화") >= 0, "붙여넣기: 상태 줄에 발화 수");
  ok(els.copy.disabled === false, "붙여넣기: 복사 버튼 활성");
  ok(els.preview.innerHTML.indexOf("일시 미상") >= 0, "붙여넣기: 날짜 없으면 일시 미상");

  // ---------------------------------------------------------------- 3) 이름 라벨 + 사용자 수정
  typeInto(els.text, "김진혁: 내일 오전까지 발주서 보내드릴게요.\n\n김지훈: 네, 확인하겠습니다.\n");
  ok(els.title.value === "통화 녹음", "이름 라벨: 기본 상대방 값");
  typeInto(els.title, "김지훈 대리");
  ok(els.preview.innerHTML.indexOf("김지훈 대리") >= 0, "사용자 수정: 미리보기에 반영");
  typeInto(els.text, "김진혁: 내일 오전까지 발주서 보내드릴게요.\n\n김지훈: 네, 확인하겠습니다. 추가 문장.\n");
  ok(els.title.value === "김지훈 대리", "사용자 수정: 본문을 고쳐도 제목 유지");

  // ---------------------------------------------------------------- 4) 파일 선택
  var sampleText = "음성 녹음\n2026. 11. 17. 오후 9:00\n길이 03:21\n\n00:00\n화자 1\n여보세요, JFC 마케팅팀 김진혁입니다.\n\n00:05\n화자 2\n네, 소블 매거진 김지훈 대리입니다.\n";
  function utf8Bytes(str) {
    return root.CallLog.util.utf8Encode(str);
  }
  els.file.files = [
    {
      name: "통화 녹음 김지훈_261117_210000.txt",
      lastModified: new Date(2026, 10, 17, 21, 30, 0).getTime(),
      _buffer: utf8Bytes(sampleText).buffer,
    },
  ];
  els.file.dispatch("change");
  flush();
  ok(els.text.value === sampleText, "파일: 본문이 입력창에 들어감");
  ok(els.title.value === "김지훈", "파일: 파일명에서 상대방 자동 추출");
  ok(els.date.value === "2026-11-17", "파일: 날짜 자동 입력");
  ok(els.time.value === "21:00", "파일: 시각 자동 입력");
  ok(els.preview.innerHTML.indexOf("2026-11-17 (화) 21:00") >= 0, "파일: 미리보기에 일시 반영");
  ok(els.preview.innerHTML.indexOf("소블 매거진 김지훈 대리") >= 0, "파일: 본문 파싱");

  // ---------------------------------------------------------------- 5) 일시 직접 고치기/지우기
  els.date.value = "2026-11-18";
  els.date.dispatch("input");
  flush();
  ok(els.preview.innerHTML.indexOf("2026-11-18 (수) 21:00") >= 0, "일시 수정: 날짜 변경 반영");

  els.date.value = "";
  els.date.dispatch("input");
  flush();
  ok(els.preview.innerHTML.indexOf("일시 미상") >= 0, "일시 수정: 비우면 일시 미상");

  // ---------------------------------------------------------------- 6) 지우기
  els.clear.dispatch("click");
  flush();
  ok(els.text.value === "", "지우기: 본문 비움");
  ok(els.preview.innerHTML.indexOf("위에 .txt를 고르거나") >= 0, "지우기: 안내로 복귀");
  ok(els.copy.disabled === true, "지우기: 복사 버튼 비활성");

  // ---------------------------------------------------------------- 7) 특수문자 안전
  typeInto(els.text, "화자 1: <img src=x onerror=alert(1)> & 끝\n");
  ok(els.preview.innerHTML.indexOf("<img") < 0, "미리보기: 태그 주입 차단");
  ok(els.preview.innerHTML.indexOf("&lt;img") >= 0, "미리보기: 태그는 글자로 표시");

  // ---------------------------------------------------------------- 8) UTF-16LE 파일 (삼성 통화녹음 내보내기)
  function utf16leBuffer(str) {
    var bytes = new Uint8Array(str.length * 2 + 2);
    bytes[0] = 0xff;
    bytes[1] = 0xfe;
    for (var i = 0; i < str.length; i++) {
      var code = str.charCodeAt(i);
      bytes[2 + i * 2] = code & 0xff;
      bytes[3 + i * 2] = (code >> 8) & 0xff;
    }
    return bytes.buffer;
  }
  var utf16Text =
    "AI 음성 인식\n2026. 11. 17. 오후 2:31\n길이 00:41\n\n화자 1 (00:01)\n네, 안녕하세요. JFC 마케팅팀 김진혁입니다.\n\n화자 2 (00:14)\n네 안녕하세요, 박동근입니다.";
  els.file.files = [
    {
      name: "통화 녹음 제이에프씨 박동근 부대표님_261117_143113_original.txt",
      lastModified: new Date(2026, 10, 17, 14, 31, 0).getTime(),
      _buffer: utf16leBuffer(utf16Text),
    },
  ];
  els.file.dispatch("change");
  flush();
  ok(els.text.value === utf16Text, "UTF-16 파일: 본문이 깨지지 않고 들어감");
  ok(els.text.value.indexOf("화자 1 (00:01)") >= 0, "UTF-16 파일: 화자 라벨 보임");
  ok(els.preview.innerHTML.indexOf("박동근") >= 0, "UTF-16 파일: 미리보기에 대화 내용");
  ok(els.preview.innerHTML.indexOf("Tĭ") < 0, "UTF-16 파일: 깨진 글자 없음");
  ok(els.title.value.indexOf("박동근") >= 0, "UTF-16 파일: 파일명에서 상대방 추출");


  var message = "화면 점검: " + pass + "건 통과, " + failures.length + "건 실패";
  if (failures.length) message += "\n\n" + failures.join("\n");
  root.__appSmokeResult = { pass: pass, fail: failures.length, failures: failures, message: message };
  if (typeof console !== "undefined" && console.log) console.log(message);
})(typeof globalThis !== "undefined" ? globalThis : this);
