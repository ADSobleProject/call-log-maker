/* 통화록을 Markdown / 미리보기 HTML 로 그린다. (calllog/render.py 의 웹 버전) */
(function (global) {
  "use strict";

  var CallLog = (global.CallLog = global.CallLog || {});
  var util = CallLog.util;

  var WEEKDAYS = ["월", "화", "수", "목", "금", "토", "일"];

  function weekdayIndex(date) {
    return (date.getDay() + 6) % 7; // 월=0 … 일=6
  }

  function dateTimeLabel(date) {
    if (!date) return "일시 미상";
    return (
      date.getFullYear() +
      "-" +
      util.pad2(date.getMonth() + 1) +
      "-" +
      util.pad2(date.getDate()) +
      " (" +
      WEEKDAYS[weekdayIndex(date)] +
      ") " +
      util.pad2(date.getHours()) +
      ":" +
      util.pad2(date.getMinutes())
    );
  }

  function stampLabel(date) {
    return (
      date.getFullYear() + util.pad2(date.getMonth() + 1) + util.pad2(date.getDate()) + "_" + util.pad2(date.getHours()) + util.pad2(date.getMinutes())
    );
  }

  function durationLabel(seconds) {
    if (!seconds) return "-";
    var total = Math.round(seconds);
    var h = Math.floor(total / 3600);
    var rest = total - h * 3600;
    var m = Math.floor(rest / 60);
    var s = rest - m * 60;
    if (h) return h + "시간 " + util.pad2(m) + "분 " + util.pad2(s) + "초";
    if (m) return m + "분 " + util.pad2(s) + "초";
    return s + "초";
  }

  function speakerLabel(doc, speaker) {
    return speaker ? speaker : "통화";
  }

  function infoRows(doc) {
    var speakers = doc.speakers && doc.speakers.length ? doc.speakers.join(", ") : "구분 없음";
    var engine = doc.engine || "-";
    return [
      ["일시", dateTimeLabel(doc.when)],
      ["상대방/제목", doc.title],
      ["원본 파일", doc.sourceName],
      ["소요 시간", durationLabel(doc.durationSec)],
      ["변환 방식", engine && engine !== "-" ? doc.mode + " (" + engine + ")" : doc.mode],
      ["화자", speakers],
      ["분량", util.groupDigits(doc.utteranceCount) + "개 발화 · " + util.groupDigits(doc.charCount) + "자"],
      ["작성", dateTimeLabel2(doc.createdAt)],
    ];
  }

  function dateTimeLabel2(date) {
    return date.getFullYear() + "-" + util.pad2(date.getMonth() + 1) + "-" + util.pad2(date.getDate()) + " " + util.pad2(date.getHours()) + ":" + util.pad2(date.getMinutes());
  }

  function heading(doc) {
    var when = doc.when ? dateTimeLabel2(doc.when) : "일시 미상";
    return "통화록 - " + doc.title + " (" + when + ")";
  }

  function introText(doc) {
    if (doc.mode && doc.mode.indexOf("음성") === 0) {
      return "음성 파일을 무료 로컬 음성인식(faster-whisper)으로 옮긴 통화록입니다.";
    }
    return "이미 텍스트로 변환된 기록을 정리한 통화록입니다.";
  }

  /* ---------------------------------------------------------------- Markdown */
  function toMarkdown(doc) {
    var lines = [];
    lines.push("# 📞 " + heading(doc));
    lines.push("");
    lines.push("> " + introText(doc));
    lines.push("");

    lines.push("## 📋 기본 정보");
    lines.push("");
    lines.push("| 항목 | 내용 |");
    lines.push("| --- | --- |");
    var rows = infoRows(doc);
    for (var r = 0; r < rows.length; r++) {
      lines.push("| " + rows[r][0] + " | " + String(rows[r][1]).replace(/\|/g, "\\|") + " |");
    }
    lines.push("");

    lines.push("## 🔑 주요 키워드");
    lines.push("");
    if (doc.keywords.length) {
      lines.push(
        doc.keywords
          .map(function (k) {
            return "`" + k + "`";
          })
          .join(" · ")
      );
    } else {
      lines.push("_추출된 키워드가 없습니다._");
    }
    lines.push("");

    lines.push("## 📌 핵심 요약");
    lines.push("");
    if (doc.summary.length) {
      for (var i = 0; i < doc.summary.length; i++) {
        lines.push(i + 1 + ". " + doc.summary[i]);
      }
    } else {
      lines.push("_요약할 문장을 찾지 못했습니다. 아래 전체 대화 기록을 확인해 주세요._");
    }
    lines.push("");

    if (doc.amounts.length || doc.dates.length) {
      lines.push("## 💰 금액·일정");
      lines.push("");
      if (doc.amounts.length) lines.push("- **금액**: " + doc.amounts.join(" · "));
      if (doc.dates.length) lines.push("- **일정**: " + doc.dates.join(" · "));
      lines.push("");
    }

    lines.push("## ✅ 후속 할 일");
    lines.push("");
    if (doc.actions.length) {
      for (var a = 0; a < doc.actions.length; a++) {
        var item = doc.actions[a];
        var extra = [];
        if (item.owner) extra.push(item.owner);
        if (item.due) extra.push(item.due);
        var suffix = extra.length ? "  _(" + extra.join(" · ") + ")_" : "";
        lines.push("- [ ] " + item.text + suffix);
      }
    } else {
      lines.push("_뚜렷한 요청·약속 문장이 없습니다._");
    }
    lines.push("");

    lines.push("## 💬 전체 대화 기록");
    lines.push("");
    if (!doc.segments.length) lines.push("_대화 내용이 없습니다._");
    for (var s = 0; s < doc.segments.length; s++) {
      var seg = doc.segments[s];
      var stamp = CallLog.parsers.formatTimestamp(seg.start);
      var head = "**" + speakerLabel(doc, seg.speaker) + "**";
      if (stamp) head += " `" + stamp + "`";
      lines.push(head);
      lines.push("");
      lines.push(seg.text);
      lines.push("");
    }

    if (doc.warnings.length) {
      lines.push("---");
      lines.push("");
      lines.push("## ⚠️ 참고");
      lines.push("");
      for (var w = 0; w < doc.warnings.length; w++) lines.push("- " + doc.warnings[w]);
      lines.push("");
    }

    lines.push("---");
    lines.push("");
    lines.push("*call-log-maker 로 자동 생성 · 내용은 원본 기록을 확인해 주세요.*");
    lines.push("");
    return lines.join("\n");
  }

  /* ---------------------------------------------------------------- 미리보기 */
  function escapeHtml(text) {
    return String(text == null ? "" : text)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  /** 통화록을 화면에 보여 줄 HTML 조각으로 만든다. (문구는 Markdown 과 같게) */
  function toPreviewHtml(doc) {
    var out = [];
    out.push('<h2 class="doc-title">📞 ' + escapeHtml(heading(doc)) + "</h2>");
    out.push('<p class="doc-note">' + escapeHtml(introText(doc)) + "</p>");

    out.push('<h3>📋 기본 정보</h3>');
    out.push('<table class="doc-table"><tbody>');
    var rows = infoRows(doc);
    for (var r = 0; r < rows.length; r++) {
      out.push(
        "<tr><th>" + escapeHtml(rows[r][0]) + "</th><td>" + escapeHtml(rows[r][1]) + "</td></tr>"
      );
    }
    out.push("</tbody></table>");

    out.push("<h3>🔑 주요 키워드</h3>");
    if (doc.keywords.length) {
      out.push(
        '<p class="doc-keywords">' +
          doc.keywords
            .map(function (k) {
              return "<code>" + escapeHtml(k) + "</code>";
            })
            .join(" · ") +
          "</p>"
      );
    } else {
      out.push('<p class="doc-empty">추출된 키워드가 없습니다.</p>');
    }

    out.push("<h3>📌 핵심 요약</h3>");
    if (doc.summary.length) {
      out.push("<ol>");
      for (var i = 0; i < doc.summary.length; i++) out.push("<li>" + escapeHtml(doc.summary[i]) + "</li>");
      out.push("</ol>");
    } else {
      out.push('<p class="doc-empty">요약할 문장을 찾지 못했습니다. 아래 전체 대화 기록을 확인해 주세요.</p>');
    }

    if (doc.amounts.length || doc.dates.length) {
      out.push("<h3>💰 금액·일정</h3>");
      out.push("<ul>");
      if (doc.amounts.length) out.push("<li><b>금액</b>: " + escapeHtml(doc.amounts.join(" · ")) + "</li>");
      if (doc.dates.length) out.push("<li><b>일정</b>: " + escapeHtml(doc.dates.join(" · ")) + "</li>");
      out.push("</ul>");
    }

    out.push("<h3>✅ 후속 할 일</h3>");
    if (doc.actions.length) {
      out.push('<ul class="doc-actions">');
      for (var a = 0; a < doc.actions.length; a++) {
        var item = doc.actions[a];
        var extra = [];
        if (item.owner) extra.push(item.owner);
        if (item.due) extra.push(item.due);
        out.push(
          "<li>☐ " +
            escapeHtml(item.text) +
            (extra.length ? ' <span class="doc-meta">(' + escapeHtml(extra.join(" · ")) + ")</span>" : "") +
            "</li>"
        );
      }
      out.push("</ul>");
    } else {
      out.push('<p class="doc-empty">뚜렷한 요청·약속 문장이 없습니다.</p>');
    }

    out.push("<h3>💬 전체 대화 기록</h3>");
    if (!doc.segments.length) out.push('<p class="doc-empty">대화 내용이 없습니다.</p>');
    for (var s = 0; s < doc.segments.length; s++) {
      var seg = doc.segments[s];
      var stamp = CallLog.parsers.formatTimestamp(seg.start);
      out.push(
        '<div class="doc-seg"><div class="doc-speaker">' +
          escapeHtml(speakerLabel(doc, seg.speaker)) +
          (stamp ? ' <span class="doc-stamp">' + escapeHtml(stamp) + "</span>" : "") +
          "</div><p>" +
          escapeHtml(seg.text) +
          "</p></div>"
      );
    }

    if (doc.warnings.length) {
      out.push("<h3>⚠️ 참고</h3><ul>");
      for (var w = 0; w < doc.warnings.length; w++) out.push("<li>" + escapeHtml(doc.warnings[w]) + "</li>");
      out.push("</ul>");
    }

    out.push('<p class="doc-foot">call-log-maker 로 자동 생성 · 내용은 원본 기록을 확인해 주세요.</p>');
    return out.join("");
  }

  CallLog.render = {
    WEEKDAYS: WEEKDAYS,
    heading: heading,
    infoRows: infoRows,
    dateTimeLabel: dateTimeLabel,
    durationLabel: durationLabel,
    stampLabel: stampLabel,
    toMarkdown: toMarkdown,
    toPreviewHtml: toPreviewHtml,
    escapeHtml: escapeHtml,
  };
})(typeof globalThis !== "undefined" ? globalThis : this);
