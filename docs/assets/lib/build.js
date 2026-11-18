/* 텍스트 → 통화록 문서 만들기. (calllog/pipeline.py 의 _build_document 를 웹으로)
 *
 * PC 버전과 같은 순서로 처리한다:
 *   파일명 해석 → 본문 파싱 → (본문 머리말이 있으면 덮어쓰기) → 키워드·요약·할 일 추출
 * 사용자가 고친 상대방/일시는 마지막에 적용한다.
 */
(function (global) {
  "use strict";

  var CallLog = (global.CallLog = global.CallLog || {});

  var DEFAULTS = {
    maxKeywords: 10,
    maxSummarySentences: 5,
    maxActionItems: 8,
    titleMaxLen: 40,
  };

  /**
   * options: {
   *   text: string,             원문
   *   fileName?: string,        원본 파일 이름 (붙여넣기면 없음)
   *   modifiedAt?: Date|number, 파일 수정 시각 (파일을 골랐을 때)
   *   now?: Date,               작성 시각
   *   title?: string,           사용자가 고친 상대방/제목
   *   when?: Date|null,         사용자가 고친 일시
   * }
   */
  function buildDocument(options) {
    var opts = options || {};
    var cfg = {};
    for (var key in DEFAULTS) {
      if (Object.prototype.hasOwnProperty.call(DEFAULTS, key)) {
        cfg[key] = opts[key] !== undefined ? opts[key] : DEFAULTS[key];
      }
    }

    var fileName = opts.fileName || "";
    var info = CallLog.filenames.parseFilename(fileName, {
      maxLen: cfg.titleMaxLen,
      modifiedAt: opts.modifiedAt || null,
    });
    var parsed = CallLog.parsers.parseText(opts.text || "", fileName);

    var warnings = parsed.warnings.slice();
    var duration = parsed.durationSec;
    var when = info.when;
    var timeKnown = info.timeKnown;
    var title = info.title;

    // 본문 머리말의 일시·제목이 있으면 그쪽을 쓴다 (PC 버전과 같음)
    if (parsed.when) {
      when = parsed.when;
      if (parsed.timeKnown) timeKnown = true;
    }
    if (parsed.title) title = parsed.title;

    var segments = parsed.segments;
    if (duration === null || duration === undefined) {
      var stamps = segments
        .map(function (s) {
          return s.start;
        })
        .filter(function (value) {
          return !!value;
        });
      duration = stamps.length ? Math.max.apply(null, stamps) : null;
    }

    // 사용자가 직접 고친 값이 가장 우선
    if (opts.title !== undefined && opts.title !== null && String(opts.title).trim() !== "") {
      title = String(opts.title).trim();
    }
    if (opts.when instanceof Date && !isNaN(opts.when.getTime())) {
      when = opts.when;
      timeKnown = true;
    } else if (opts.when === null) {
      when = null;
      timeKnown = false;
    }

    var text = segments
      .map(function (s) {
        return s.text;
      })
      .join("\n");

    var kws = CallLog.analyze.keywords(text, cfg.maxKeywords);
    var summary = CallLog.analyze.summarize(segments, cfg.maxSummarySentences, kws);
    var speakers = [];
    segments.forEach(function (s) {
      if (s.speaker && speakers.indexOf(s.speaker) < 0) speakers.push(s.speaker);
    });
    var actions = CallLog.analyze.extractActions(segments, cfg.maxActionItems, speakers);

    var charCount = segments.reduce(function (total, s) {
      return total + s.text.length;
    }, 0);

    var doc = {
      title: title || "통화 녹음",
      when: when,
      timeKnown: timeKnown,
      sourceName: fileName || "붙여넣은 텍스트",
      mode: "텍스트 변환본",
      engine: "",
      durationSec: duration,
      segments: segments,
      keywords: kws,
      summary: summary,
      actions: actions,
      amounts: CallLog.analyze.amountsIn(text),
      dates: CallLog.analyze.datesIn(text),
      speakers: speakers,
      warnings: warnings,
      createdAt: opts.now instanceof Date ? opts.now : new Date(),
      charCount: charCount,
      utteranceCount: segments.length,
    };
    if (!segments.length) {
      doc.warnings.push("대화 내용을 정리하지 못했습니다. 원본 파일을 확인해 주세요.");
    }
    return doc;
  }

  /** 내려받을 파일 이름 (PC 버전과 같은 규칙: 20261117_2100_김지훈_통화록.md) */
  function outputName(doc, ext) {
    var stamp = doc.when ? CallLog.render.stampLabel(doc.when) : CallLog.render.stampLabel(doc.createdAt);
    var safe = CallLog.filenames.safeFilename(doc.title, 40);
    return stamp + "_" + safe + "_통화록." + ext;
  }

  CallLog.buildDocument = buildDocument;
  CallLog.outputName = outputName;
  CallLog.DEFAULTS = DEFAULTS;
})(typeof globalThis !== "undefined" ? globalThis : this);
