/* 텍스트 변환본(.txt) 파싱 — calllog/parsers.py 의 웹 버전.
 *
 * 삼성 음성 녹음 / 갤럭시 AI / 클로바 노트 / 에이닷 등에서 내보낸 txt 는
 * 화자 라벨과 타임스탬프 표기가 조금씩 다르다. 아래처럼 너그럽게 받아 준다.
 *
 *     00:00
 *     화자 1
 *     안녕하세요, 잘 지내셨어요?
 *
 *     00:05 화자 2: 네 덕분에 잘 지냈습니다.
 *
 *     [00:12] 참석자 1 - 그럼 내일 오후 세 시에 봬요.
 *     Speaker 2: OK, see you then.
 */
(function (global) {
  "use strict";

  var CallLog = (global.CallLog = global.CallLog || {});
  var findDatetime = CallLog.filenames.findDatetime;
  var cleanTitle = CallLog.filenames.cleanTitle;

  var TIMESTAMP = /^[[(]?(?<h>\d{1,3}):(?<mi>\d{2})(?::(?<s>\d{2}))?(?:[.,]\d{1,3})?[\])]?$/;
  var TS_ANY = "(?<ts>\\d{1,3}:\\d{2}(?::\\d{2})?(?:[.,]\\d{1,3})?)";
  var SPEAKER = "(?:화자|참석자|발화자|스피커|Speaker|SPEAKER)\\s*\\d+";
  var NAME_LABEL = "[^\\s:：\\[\\](){}]{1,12}";

  var TS_SPEAKER = new RegExp(
    "^[[(]?" + TS_ANY + "[\\])]?\\s*[,\\-–·|]?\\s*(?<spk>" + SPEAKER + ")\\s*[:：\\-–]?\\s*(?<text>.*)$",
    "i"
  );
  var SPEAKER_LINE = new RegExp("^[[(]?(?<spk>" + SPEAKER + ")[\\])]?\\s*[:：\\-–]?\\s*(?<text>.*)$", "i");
  var NAME_LINE = new RegExp("^[[(]?(?<spk>" + NAME_LABEL + ")[\\])]?\\s*[:：]\\s*(?<text>.+)$");
  var META_LINE = new RegExp(
    "^(?<key>녹음\\s*일시|통화\\s*일시|통화\\s*날짜|녹음\\s*날짜|일시|날짜|시각|시간|" +
      "제목|파일명|파일|상대방|통화\\s*상대|상대|연락처|전화번호|번호|" +
      "길이|재생\\s*시간|소요\\s*시간|통화\\s*시간|녹음\\s*시간|작성일|변환일|모델)" +
      "\\s*[:：]\\s*(?<value>.+)$"
  );
  var META_KEYS_SKIP_SPEAKER = [
    "금액", "날짜", "시간", "제목", "파일", "길이", "상대방", "장소", "내용",
    "비고", "요약", "메모", "일시", "연락처", "전화번호", "번호", "모델",
  ];
  var HEADER_NOISE =
    /^(음성\s*녹음|통화\s*녹음|녹음|음성\s*인식|자동\s*변환|텍스트\s*변환|STT|Transcript|Transcription|AI\s*음성\s*인식)\s*$/i;
  var DURATION_TEXT = /(?:(?<h>\d{1,2})\s*시간)?\s*(?:(?<m>\d{1,3})\s*분)?\s*(?:(?<s>\d{1,3})\s*초)?/;
  var DURATION_LINE = new RegExp(
    "^(?:길이|재생\\s*시간|소요\\s*시간|통화\\s*시간|녹음\\s*시간|duration|length)\\s*[:：]?\\s*" +
      "(?<value>\\d{1,2}:\\d{2}(?::\\d{2})?|\\d{1,2}\\s*시간.*|\\d{1,3}\\s*분.*|\\d{1,3}\\s*초.*)$",
    "i"
  );
  var TITLE_LINE = /^(?<kind>통화\s*녹음|음성\s*녹음|녹음|통화|회의\s*녹음)\s*[-–—:|]\s*(?<title>.+)$/;

  function segment(text, speaker, start) {
    return { text: text, speaker: speaker === undefined ? null : speaker, start: start === undefined ? null : start };
  }

  /** '00:12'(분:초), '1:02:03'(시:분:초) → 초 */
  function parseTimestamp(text) {
    var match = TIMESTAMP.exec(String(text == null ? "" : text).trim());
    if (!match) return null;
    var h = parseInt(match.groups.h, 10);
    var m = parseInt(match.groups.mi, 10);
    var s = match.groups.s;
    if (s === undefined) return h * 60 + m; // 두 토막이면 '분:초'
    return h * 3600 + m * 60 + parseInt(s, 10);
  }

  function formatTimestamp(seconds) {
    if (seconds === null || seconds === undefined || isNaN(seconds)) return "";
    var total = Math.round(seconds);
    var h = Math.floor(total / 3600);
    var rest = total - h * 3600;
    var m = Math.floor(rest / 60);
    var s = rest - m * 60;
    var pad = CallLog.util.pad2;
    if (h) return h + ":" + pad(m) + ":" + pad(s);
    return pad(m) + ":" + pad(s);
  }

  function parseDuration(text) {
    var value = String(text == null ? "" : text).trim();
    if (!value) return null;
    if (TIMESTAMP.test(value)) return parseTimestamp(value);
    var match = DURATION_TEXT.exec(value);
    if (!match) return null;
    var g = match.groups || {};
    var h = parseInt(g.h || "0", 10);
    var m = parseInt(g.m || "0", 10);
    var s = parseInt(g.s || "0", 10);
    if (h === 0 && m === 0 && s === 0) return null;
    return h * 3600 + m * 60 + s;
  }

  function normalizeSpeaker(label) {
    var text = String(label == null ? "" : label).trim().replace(/^[[\](){}]+|[[\](){}]+$/g, "").trim();
    text = text.replace(/\s{2,}/g, " ");
    if (text.toLowerCase().indexOf("speaker") === 0) {
      var digits = text.replace(/\D/g, "");
      return digits ? "화자 " + digits : "화자";
    }
    return text;
  }

  /**
   * @param {string} raw 텍스트 원문
   * @param {string} sourceName 원본 파일 이름 (없으면 "")
   */
  function parseText(raw, sourceName) {
    var text = String(raw == null ? "" : raw)
      .replace(/\ufeff/g, "")
      .replace(/\r\n/g, "\n")
      .replace(/\r/g, "\n");
    var lines = text.split("\n");
    var result = {
      segments: [],
      title: "",
      when: null,
      timeKnown: false,
      durationSec: null,
      warnings: [],
      sourceName: sourceName || "",
    };
    var segments = [];
    var current = null;
    var pendingSpeaker = null;
    var pendingTime = null;
    var paraBreak = true;
    var labelsUsed = false;

    function add(speaker, timestamp, body) {
      var clean = String(body == null ? "" : body).replace(/\s{2,}/g, " ").trim();
      if (!clean) return;
      if (current !== null && !paraBreak && current.speaker === speaker) {
        current.text = (current.text + " " + clean).trim();
        if (current.start === null && timestamp !== null) current.start = timestamp;
        return;
      }
      current = segment(clean, speaker, timestamp);
      segments.push(current);
    }

    for (var idx = 0; idx < lines.length; idx++) {
      var line = lines[idx].trim();
      if (!line) {
        paraBreak = true;
        current = null;
        continue;
      }

      // 1) 문서 머리말의 날짜/시각 줄
      var found = findDatetime(line);
      if (line.length <= 40 && (found.when !== null || HEADER_NOISE.test(line))) {
        if (found.when !== null && result.when === null) {
          result.when = found.when;
          result.timeKnown = found.timeKnown;
          continue;
        }
        if (HEADER_NOISE.test(line)) continue;
      }

      // 2) '제목: ...', '길이: 03:21' 같은 정보 줄
      var durationLine = DURATION_LINE.exec(line);
      if (durationLine) {
        var duration = parseDuration(durationLine.groups.value);
        if (duration && result.durationSec === null) result.durationSec = duration;
        continue;
      }
      var titleLine = TITLE_LINE.exec(line);
      if (titleLine && !result.title) {
        var candidate = cleanTitle(titleLine.groups.title, 40);
        if (candidate) {
          result.title = candidate;
          continue;
        }
      }
      var meta = META_LINE.exec(line);
      if (meta) {
        var key = meta.groups.key.replace(/\s+/g, "");
        var value = meta.groups.value.trim();
        if (key.indexOf("일시") >= 0 || key.indexOf("날짜") >= 0) {
          var parsed = findDatetime(value);
          if (parsed.when && result.when === null) {
            result.when = parsed.when;
            result.timeKnown = parsed.timeKnown;
          }
        } else if (["길이", "재생시간", "소요시간", "통화시간", "녹음시간"].indexOf(key) >= 0) {
          var metaDuration = parseDuration(value);
          if (metaDuration && result.durationSec === null) result.durationSec = metaDuration;
        } else if (["제목", "상대방", "통화상대", "상대"].indexOf(key) >= 0) {
          var title = cleanTitle(value, 40);
          if (title && !result.title) result.title = title;
        } else if (key === "시간" || key === "시각") {
          var whenResult = findDatetime(value);
          if (whenResult.when && result.when === null) {
            result.when = whenResult.when;
            result.timeKnown = whenResult.timeKnown;
          }
        }
        continue;
      }

      // 3) '00:05 화자 2: ...'
      var combo = TS_SPEAKER.exec(line);
      if (combo) {
        pendingTime = parseTimestamp(combo.groups.ts);
        var comboSpeaker = normalizeSpeaker(combo.groups.spk);
        labelsUsed = true;
        var comboBody = combo.groups.text;
        if (comboBody.trim()) {
          add(comboSpeaker, pendingTime, comboBody);
          pendingTime = null;
          paraBreak = false;
        } else {
          pendingSpeaker = comboSpeaker;
        }
        continue;
      }

      // 4) '화자 1' / '화자 1: ...' / '화자 1 (00:01)'
      var speakerLine = SPEAKER_LINE.exec(line);
      if (speakerLine) {
        var speaker = normalizeSpeaker(speakerLine.groups.spk);
        labelsUsed = true;
        var speakerBody = speakerLine.groups.text;
        // 삼성 통화녹음은 화자 라벨 줄 끝에 상대 시각을 붙여 내보낸다
        var speakerStamp = speakerBody.trim() ? parseTimestamp(speakerBody) : null;
        if (speakerStamp !== null) {
          pendingSpeaker = speaker;
          pendingTime = speakerStamp;
          continue;
        }
        if (speakerBody.trim()) {
          add(speaker, pendingTime, speakerBody);
          pendingTime = null;
          pendingSpeaker = null;
          paraBreak = false;
        } else {
          pendingSpeaker = speaker;
        }
        continue;
      }

      // 5) 타임스탬프만 있는 줄
      var timestamp = parseTimestamp(line);
      if (timestamp !== null) {
        pendingTime = timestamp;
        continue;
      }

      // 6) '[홍길동] ...' / '홍길동: ...' (일반 이름 라벨)
      var nameLine = NAME_LINE.exec(line);
      if (nameLine && META_KEYS_SKIP_SPEAKER.indexOf(nameLine.groups.spk.trim()) < 0) {
        var nameSpeaker = normalizeSpeaker(nameLine.groups.spk);
        labelsUsed = true;
        add(nameSpeaker, pendingTime, nameLine.groups.text);
        pendingTime = null;
        pendingSpeaker = null;
        paraBreak = false;
        continue;
      }

      // 7) 보통 문장 — 화자 라벨이 쓰인 파일이면 앞사람 말이 이어지는 것으로 본다
      var nextSpeaker = pendingSpeaker || (labelsUsed && current !== null ? current.speaker : null);
      add(nextSpeaker, pendingTime, line);
      pendingSpeaker = null;
      pendingTime = null;
      paraBreak = false;
    }

    result.segments = mergeSegments(segments);
    if (!result.segments.length) {
      result.warnings.push("읽을 수 있는 대화 내용을 찾지 못했습니다.");
    }
    return result;
  }

  /** 같은 화자가 이어서 말한 짧은 토막들을 한 문단으로 합친다. */
  function mergeSegments(segments) {
    var merged = [];
    for (var i = 0; i < segments.length; i++) {
      var seg = segments[i];
      var text = String(seg.text).replace(/\s{2,}/g, " ").trim();
      if (!text) continue;
      var prev = merged.length ? merged[merged.length - 1] : null;
      if (prev && prev.speaker && prev.speaker === seg.speaker) {
        if (!/[?!.…,]$/.test(prev.text) && prev.text.length > 20) {
          prev.text = (prev.text + ". " + text).trim();
        } else {
          prev.text = (prev.text + " " + text).trim();
        }
        continue;
      }
      merged.push({ text: text, speaker: seg.speaker, start: seg.start });
    }
    return merged;
  }

  CallLog.parsers = {
    parseText: parseText,
    parseTimestamp: parseTimestamp,
    formatTimestamp: formatTimestamp,
    parseDuration: parseDuration,
    normalizeSpeaker: normalizeSpeaker,
    mergeSegments: mergeSegments,
  };
})(typeof globalThis !== "undefined" ? globalThis : this);
