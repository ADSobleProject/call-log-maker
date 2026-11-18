/* 파일명에서 상대방/제목·날짜·시각을 뽑는다. (calllog/filenames.py 의 웹 버전)
 *
 * 삼성 통화 녹음 기본 이름 예:
 *   통화 녹음 홍길동_261117_210000.txt
 *   통화녹음_01012345678_20231117_210000.txt
 *   녹음_20261117_1430.txt
 *   통화 녹음 2026. 11. 17. 오후 9:00.txt
 */
(function (global) {
  "use strict";

  var CallLog = (global.CallLog = global.CallLog || {});

  var DEFAULT_TITLE = "통화 녹음";

  var PREFIXES = [
    "삼성 통화 녹음", "통화 녹음", "통화녹음", "음성 녹음", "음성녹음", "새 녹음", "새녹음",
    "voice recorder", "voice recording", "voice memo", "call recording", "call recorder",
    "kakaotalk_audio", "kakaotalk", "recording", "record", "audio", "voice", "memo",
    "통화", "녹음", "음성", "회의록", "회의", "녹취",
  ];
  var STOP_TITLES = ["", "-", "_", "new", "untitled", "제목 없음", "무제", "녹음", "통화", "음성"];
  var GENERIC_PREFIX = { "회의": true, "녹취": true, "통화": true, "녹음": true, "음성": true };
  var EDGE_CHARS = " _-\u2013\u2014.";
  var EDGE_ONLY = /^[ _\-\u2013\u2014.]+$/;

  var DATE_TIME_PATTERNS = [
    // 20261117_210000 / 20261117-2100-30 / 2026.11.17 21.00.00
    /(?<!\d)(?<y>20\d{2})(?<mo>\d{2})(?<d>\d{2})[_\-\s.]*(?<h>\d{2})[:\-.]?(?<mi>\d{2})[:\-.]?(?<s>\d{2})(?!\d)/g,
    // 20261117_2100
    /(?<!\d)(?<y>20\d{2})(?<mo>\d{2})(?<d>\d{2})[_\-\s.]*(?<h>\d{2})[:\-.]?(?<mi>\d{2})(?!\d)/g,
    // 261117_210000
    /(?<!\d)(?<y>\d{2})(?<mo>\d{2})(?<d>\d{2})[_\-\s.]*(?<h>\d{2})[:\-.]?(?<mi>\d{2})[:\-.]?(?<s>\d{2})(?!\d)/g,
    // 261117_2100
    /(?<!\d)(?<y>\d{2})(?<mo>\d{2})(?<d>\d{2})[_\-\s.]*(?<h>\d{2})[:\-.]?(?<mi>\d{2})(?!\d)/g,
    // 2026-11-17 21:00 / 2026. 11. 17. 오후 9:00 / 2026/11/17 21.00
    /(?<!\d)(?<y>20\d{2})\s*[-./]\s*(?<mo>\d{1,2})\s*[-./]\s*(?<d>\d{1,2})(?:\.)?[T\s_]*(?:(?<ampm>오전|오후|am|pm)\s*)?(?<h>\d{1,2})\s*[:.]\s*(?<mi>\d{2})(?:\s*[:.]\s*(?<s>\d{2}))?/g,
    // 2026년 11월 17일 오후 9시 30분
    /(?<!\d)(?<y>20\d{2})년\s*(?<mo>\d{1,2})월\s*(?<d>\d{1,2})일(?:\s*(?<ampm>오전|오후)\s*)?(?:\s*(?<h>\d{1,2})시(?:\s*(?<mi>\d{1,2})분?)?)?/g,
  ];

  var DATE_ONLY_PATTERNS = [
    /(?<!\d)(?<y>20\d{2})(?<mo>\d{2})(?<d>\d{2})(?!\d)/g,
    /(?<!\d)(?<y>20\d{2})\s*[-./]\s*(?<mo>\d{1,2})\s*[-./]\s*(?<d>\d{1,2})(?!\d)/g,
    /(?<!\d)(?<y>20\d{2})년\s*(?<mo>\d{1,2})월\s*(?<d>\d{1,2})일/g,
  ];

  function matchAll(pattern, text) {
    var re = new RegExp(pattern.source, pattern.flags.indexOf("g") >= 0 ? pattern.flags : pattern.flags + "g");
    var out = [];
    var m;
    while ((m = re.exec(text)) !== null) {
      out.push(m);
      if (m[0] === "") re.lastIndex += 1;
    }
    return out;
  }

  function yearOf(value) {
    var y = parseInt(value, 10);
    if (String(value).length === 2) return y < 70 ? 2000 + y : 1900 + y;
    return y;
  }

  function applyAmpm(hour, ampm) {
    if (!ampm) return hour;
    var token = String(ampm).toLowerCase();
    if ((token === "오후" || token === "pm") && hour < 12) return hour + 12;
    if ((token === "오전" || token === "am") && hour === 12) return 0;
    return hour;
  }

  function build(match, withTime) {
    var g = match.groups || {};
    var year, month, day;
    try {
      year = yearOf(g.y || "");
      month = parseInt(g.mo || "1", 10);
      day = parseInt(g.d || "1", 10);
    } catch (err) {
      return null;
    }
    if (!(month >= 1 && month <= 12 && day >= 1 && day <= 31)) return null;
    var hour = 0, minute = 0, second = 0;
    if (withTime) {
      hour = applyAmpm(parseInt(g.h || "0", 10), g.ampm);
      minute = parseInt(g.mi || "0", 10);
      second = parseInt(g.s || "0", 10);
      if (!(hour >= 0 && hour <= 23 && minute >= 0 && minute <= 59 && second >= 0 && second <= 59)) {
        return null;
      }
    }
    var date = new Date(year, month - 1, day, hour, minute, second, 0);
    // 2026-02-31 처럼 존재하지 않는 날짜는 파이썬 datetime 이 거부하므로 똑같이 버린다
    if (date.getFullYear() !== year || date.getMonth() !== month - 1 || date.getDate() !== day) {
      return null;
    }
    if (date.getHours() !== hour || date.getMinutes() !== minute) return null;
    return date;
  }

  /** @returns {{when: Date|null, timeKnown: boolean, matched: string}} */
  function findDatetime(text) {
    var stem = String(text == null ? "" : text);
    for (var i = 0; i < DATE_TIME_PATTERNS.length; i++) {
      var matches = matchAll(DATE_TIME_PATTERNS[i], stem);
      for (var j = 0; j < matches.length; j++) {
        var when = build(matches[j], true);
        if (when === null) continue;
        var hasTime = !!(matches[j].groups && matches[j].groups.h);
        return { when: when, timeKnown: hasTime, matched: matches[j][0] };
      }
    }
    for (var k = 0; k < DATE_ONLY_PATTERNS.length; k++) {
      var only = matchAll(DATE_ONLY_PATTERNS[k], stem);
      for (var n = 0; n < only.length; n++) {
        var date = build(only[n], false);
        if (date !== null) return { when: date, timeKnown: false, matched: only[n][0] };
      }
    }
    return { when: null, timeKnown: false, matched: "" };
  }

  function trimEdge(text) {
    return String(text == null ? "" : text).replace(/^[ _\-\u2013\u2014.]+|[ _\-\u2013\u2014.]+$/g, "").trim();
  }

  function cleanTitle(text, maxLen) {
    var limit = maxLen || 40;
    var title = String(text == null ? "" : text).trim();
    title = title.replace(/\.(m4a|mp3|wav|ogg|flac|aac|wma|opus|webm|m4b|txt)$/i, "");
    title = title.replace(/[\u200b\ufeff]/g, "");

    var changed = true;
    while (changed) {
      changed = false;
      var low = title.toLowerCase().replace(/^[ _\-\u2013\u2014.]+/, "");
      for (var i = 0; i < PREFIXES.length; i++) {
        var prefix = PREFIXES[i];
        if (low.indexOf(prefix) !== 0) continue;
        var cut = title.length - low.length + prefix.length;
        var rest = title.slice(cut);
        var restTrimmed = rest.replace(/^[ _\-\u2013\u2014.]+|[ _\-\u2013\u2014.]+$/g, "");
        if (GENERIC_PREFIX[prefix] && restTrimmed) {
          // 제목 자체일 수 있는 말이지만 뒤에 다른 글자가 있으면 군더더기로 보고 지운다
        } else if ((prefix === "회의" || prefix === "녹취") && !restTrimmed) {
          continue;
        }
        title = rest;
        changed = true;
        break;
      }
    }

    title = title.replace(/^[\s_\-\u2013\u2014.,:\[\]()]+/, "");
    title = title.replace(/[\s_\-\u2013\u2014.,:\[\]()]+$/, "");
    title = title.replace(/[_\s]{2,}/g, " ").replace(/_/g, " ");
    title = title.replace(/\s{2,}/g, " ");
    // '김지훈_2' 처럼 중복 표시로 붙은 꼬리 숫자
    title = title.replace(/\s\d{1,2}$/, "");
    var digitsOnly = /^[\d\s\-\u2013\u2014.]+$/.test(title);
    if (digitsOnly && [6, 8].indexOf(title.replace(/\D/g, "").length) >= 0 && title.length) {
      title = ""; // 날짜만 남은 제목
    }
    title = title.replace(/^[_\-\u2013\u2014]+/, "");
    if (STOP_TITLES.indexOf(title.toLowerCase()) >= 0) title = "";
    var chars = CallLog.util.chars(title);
    if (chars.length > limit) {
      title = chars.slice(0, limit).join("").replace(/[ _\-\u2013\u2014.,]+$/, "");
    }
    return title;
  }

  function stripExtension(name) {
    var text = String(name == null ? "" : name).replace(/^.*[\\/]/, "");
    var dot = text.lastIndexOf(".");
    if (dot <= 0) return text;
    return text.slice(0, dot);
  }

  /**
   * 파일명에서 제목과 일시를 뽑는다. 날짜가 없으면 modifiedAt 을 쓴다
   * (PC 버전은 파일 수정 시각, 웹은 브라우저가 알려 준 마지막 수정 시각).
   */
  function parseFilename(name, options) {
    var opts = options || {};
    var maxLen = opts.maxLen || 40;
    var stem = stripExtension(name);
    var found = findDatetime(stem);
    var when = found.when;
    var timeKnown = found.timeKnown;

    var titleSource = stem;
    if (found.matched) {
      var at = stem.indexOf(found.matched);
      if (at >= 0) titleSource = stem.slice(0, at) + " " + stem.slice(at + found.matched.length);
    }
    var title = cleanTitle(titleSource, maxLen);

    var modified = opts.modifiedAt ? new Date(opts.modifiedAt) : null;
    var modifiedValid = modified && !isNaN(modified.getTime());
    var fromMtime = false;

    if (when === null) {
      if (modifiedValid) {
        when = new Date(modified.getFullYear(), modified.getMonth(), modified.getDate(), modified.getHours(), modified.getMinutes(), 0, 0);
        timeKnown = true;
        fromMtime = true;
      }
    } else if (!timeKnown && modifiedValid) {
      // 날짜만 있으면 수정 시각의 '시:분'을 빌려 온다 (같은 날일 때만)
      if (
        modified.getFullYear() === when.getFullYear() &&
        modified.getMonth() === when.getMonth() &&
        modified.getDate() === when.getDate()
      ) {
        when = new Date(when.getFullYear(), when.getMonth(), when.getDate(), modified.getHours(), modified.getMinutes(), 0, 0);
      }
    }

    if (!title) title = DEFAULT_TITLE;
    return {
      title: title,
      when: when,
      timeKnown: timeKnown && !fromMtime,
      matched: found.matched,
      titleFromName: !!(title && title !== DEFAULT_TITLE),
    };
  }

  function safeFilename(text, maxLen) {
    var limit = maxLen || 40;
    var name = String(text == null ? "" : text)
      .replace(/[\\/:*?"<>|\r\n\t]+/g, " ")
      .replace(/\s{2,}/g, " ")
      .replace(/^[ ._-]+|[ ._-]+$/g, "");
    var chars = CallLog.util.chars(name);
    if (chars.length > limit) name = chars.slice(0, limit).join("").replace(/[ ._-]+$/, "");
    return name || DEFAULT_TITLE;
  }

  CallLog.filenames = {
    DEFAULT_TITLE: DEFAULT_TITLE,
    findDatetime: findDatetime,
    cleanTitle: cleanTitle,
    parseFilename: parseFilename,
    safeFilename: safeFilename,
    stripExtension: stripExtension,
  };
})(typeof globalThis !== "undefined" ? globalThis : this);
