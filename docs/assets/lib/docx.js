/* 통화록을 .docx(OOXML) 로 만든다 — 서버 없이 브라우저에서 바로.
 *
 * 외부 라이브러리 없이 ZIP 컨테이너를 직접 조립하므로,
 * 만들어진 파일이 실제로 열리는지 테스트(tests/web)에서 검증한다.
 * 문서 구성은 PC 버전(render.write_docx)과 같은 순서·문구를 따른다.
 */
(function (global) {
  "use strict";

  var CallLog = (global.CallLog = global.CallLog || {});
  var util = CallLog.util;

  var FONT = "맑은 고딕";
  var NS_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main";
  var NS_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships";

  var XML_HEAD = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n';

  function attr(name, value) {
    return " " + name + '="' + util.xmlEscape(value) + '"';
  }

  /**
   * run: { text, bold, italic, size(half-point), color, mono }
   */
  function runXml(run) {
    var props = [];
    if (run.font) {
      props.push(
        "<w:rFonts" +
          attr("w:ascii", run.font) +
          attr("w:eastAsia", run.font) +
          attr("w:hAnsi", run.font) +
          "/>"
      );
    }
    if (run.mono) props.push('<w:rFonts w:ascii="Consolas" w:hAnsi="Consolas"/>');
    if (run.bold) props.push("<w:b/>");
    if (run.italic) props.push("<w:i/>");
    if (run.color) props.push('<w:color w:val="' + run.color + '"/>');
    if (run.size) props.push('<w:sz w:val="' + run.size + '"/><w:szCs w:val="' + run.size + '"/>');
    var text = String(run.text == null ? "" : run.text);
    var body = text
      .split("\n")
      .map(function (line, index) {
        var piece = index > 0 ? "<w:br/>" : "";
        if (!line) return piece;
        var preserve = /^\s|\s$/.test(line) ? ' xml:space="preserve"' : "";
        return piece + "<w:t" + preserve + ">" + util.xmlEscape(line) + "</w:t>";
      })
      .join("");
    return "<w:r>" + (props.length ? "<w:rPr>" + props.join("") + "</w:rPr>" : "") + body + "</w:r>";
  }

  /**
   * opts: { style, align, after, before, left, hanging, line, keepNext, runs }
   */
  function paraXml(runs, opts) {
    var o = opts || {};
    var list = Array.isArray(runs) ? runs : [runs];
    var props = [];
    if (o.style) props.push("<w:pStyle" + attr("w:val", o.style) + "/>");
    if (o.keepNext) props.push("<w:keepNext/>");
    var spacing = [];
    if (o.before !== undefined) spacing.push(attr("w:before", String(o.before)));
    if (o.after !== undefined) spacing.push(attr("w:after", String(o.after)));
    if (o.line !== undefined) {
      spacing.push(attr("w:line", String(o.line)));
      spacing.push(attr("w:lineRule", "auto"));
    }
    if (spacing.length) props.push("<w:spacing" + spacing.join("") + "/>");
    if (o.left !== undefined || o.hanging !== undefined) {
      var ind = [];
      if (o.left !== undefined) ind.push(attr("w:left", String(o.left)));
      if (o.hanging !== undefined) ind.push(attr("w:hanging", String(o.hanging)));
      props.push("<w:ind" + ind.join("") + "/>");
    }
    if (o.align) props.push("<w:jc" + attr("w:val", o.align) + "/>");
    var body = list
      .filter(function (run) {
        return run && run.text !== undefined && run.text !== null && run.text !== "";
      })
      .map(runXml)
      .join("");
    return "<w:p>" + (props.length ? "<w:pPr>" + props.join("") + "</w:pPr>" : "") + body + "</w:p>";
  }

  function headingXml(text, level) {
    return paraXml({ text: text }, { style: level === 1 ? "Heading1" : "Heading2", keepNext: true });
  }

  var TABLE_BORDERS =
    "<w:tblBorders>" +
    ["top", "left", "bottom", "right", "insideH", "insideV"]
      .map(function (side) {
        return (
          "<w:" + side + ' w:val="single" w:sz="4" w:space="0" w:color="C9CDD4"/>'
        );
      })
      .join("") +
    "</w:tblBorders>";

  var LABEL_WIDTH = 1814; // 3.2cm
  var VALUE_WIDTH = 6797; // 12.0cm

  function cellXml(runs, width, fill) {
    var tcPr = ["<w:tcW" + attr("w:w", String(width)) + attr("w:type", "dxa") + "/>"];
    if (fill) tcPr.push('<w:shd w:val="clear" w:color="auto"' + attr("w:fill", fill) + "/>");
    var paragraphs = (Array.isArray(runs) ? runs : [runs])
      .map(function (item) {
        return paraXml(item, { after: 0, line: 264 });
      })
      .join("");
    return "<w:tc><w:tcPr>" + tcPr.join("") + "</w:tcPr>" + paragraphs + "</w:tc>";
  }

  function tableXml(rows) {
    var grid =
      "<w:tblGrid><w:gridCol" +
      attr("w:w", String(LABEL_WIDTH)) +
      "/><w:gridCol" +
      attr("w:w", String(VALUE_WIDTH)) +
      "/></w:tblGrid>";
    var body = rows
      .map(function (row) {
        return (
          "<w:tr><w:trPr><w:cantSplit/></w:trPr>" +
          cellXml({ text: row[0], bold: true }, LABEL_WIDTH, "F2F4F7") +
          cellXml({ text: row[1] }, VALUE_WIDTH, null) +
          "</w:tr>"
        );
      })
      .join("");
    return (
      "<w:tbl><w:tblPr>" +
      '<w:tblW w:w="8611" w:type="dxa"/>' +
      '<w:tblLayout w:type="fixed"/>' +
      TABLE_BORDERS +
      '<w:tblCellMar><w:top w:w="57" w:type="dxa"/><w:left w:w="113" w:type="dxa"/><w:bottom w:w="57" w:type="dxa"/><w:right w:w="113" w:type="dxa"/></w:tblCellMar>' +
      "</w:tblPr>" +
      grid +
      body +
      "</w:tbl>" +
      paraXml({ text: "" }, { after: 0, line: 120 })
    );
  }

  function documentXml(doc) {
    var render = CallLog.render;
    var parts = [];
    var rows = render.infoRows(doc);

    parts.push(
      paraXml({ text: "📞 " + render.heading(doc) }, { style: "Title", after: 120 })
    );
    parts.push(
      paraXml(
        {
          text:
            doc.mode && doc.mode.indexOf("음성") === 0
              ? "음성 파일을 무료 로컬 음성인식(faster-whisper)으로 옮긴 통화록입니다."
              : "이미 텍스트로 변환된 기록을 정리한 통화록입니다.",
          size: 18,
          color: "666666",
        },
        { after: 240 }
      )
    );

    parts.push(headingXml("📋 기본 정보", 1));
    parts.push(tableXml(rows));

    parts.push(headingXml("🔑 주요 키워드", 1));
    if (doc.keywords.length) {
      parts.push(paraXml({ text: doc.keywords.join(" · "), bold: true }, {}));
    } else {
      parts.push(paraXml({ text: "추출된 키워드가 없습니다." }, {}));
    }

    parts.push(headingXml("📌 핵심 요약", 1));
    if (doc.summary.length) {
      doc.summary.forEach(function (sentence, index) {
        parts.push(
          paraXml(
            [
              { text: String(index + 1) + ". " },
              { text: sentence },
            ],
            { left: 340, hanging: 340, after: 60 }
          )
        );
      });
    } else {
      parts.push(paraXml({ text: "요약할 문장을 찾지 못했습니다. 아래 전체 대화 기록을 확인해 주세요." }, {}));
    }

    if (doc.amounts.length || doc.dates.length) {
      parts.push(headingXml("💰 금액·일정", 1));
      if (doc.amounts.length) {
        parts.push(
          paraXml([{ text: "• " }, { text: "금액", bold: true }, { text: ": " + doc.amounts.join(" · ") }], {
            left: 340,
            hanging: 340,
            after: 60,
          })
        );
      }
      if (doc.dates.length) {
        parts.push(
          paraXml([{ text: "• " }, { text: "일정", bold: true }, { text: ": " + doc.dates.join(" · ") }], {
            left: 340,
            hanging: 340,
            after: 60,
          })
        );
      }
    }

    parts.push(headingXml("✅ 후속 할 일", 1));
    if (doc.actions.length) {
      doc.actions.forEach(function (item) {
        var runs = [{ text: "☐ ", font: "Segoe UI Symbol" }, { text: item.text }];
        var extra = [item.owner, item.due].filter(function (value) {
          return !!value;
        });
        if (extra.length) {
          runs.push({ text: "  (" + extra.join(" · ") + ")", italic: true, size: 18, color: "777777" });
        }
        parts.push(paraXml(runs, { left: 340, hanging: 340, after: 60 }));
      });
    } else {
      parts.push(paraXml({ text: "뚜렷한 요청·약속 문장이 없습니다." }, {}));
    }

    parts.push(headingXml("💬 전체 대화 기록", 1));
    if (!doc.segments.length) parts.push(paraXml({ text: "대화 내용이 없습니다." }, {}));
    doc.segments.forEach(function (seg) {
      var stamp = CallLog.parsers.formatTimestamp(seg.start);
      var head = [{ text: seg.speaker ? seg.speaker : "통화", bold: true }];
      if (stamp) head.push({ text: "  " + stamp, size: 17, color: "888888" });
      parts.push(paraXml(head, { after: 0, before: 60, keepNext: true }));
      parts.push(paraXml({ text: seg.text }, { after: 160 }));
    });

    if (doc.warnings.length) {
      parts.push(headingXml("⚠️ 참고", 1));
      doc.warnings.forEach(function (warning) {
        parts.push(paraXml([{ text: "• " }, { text: warning }], { left: 340, hanging: 340, after: 60 }));
      });
    }

    parts.push(
      paraXml({ text: "call-log-maker 로 자동 생성 · 내용은 원본 기록을 확인해 주세요.", italic: true, size: 16, color: "999999" }, {
        before: 240,
      })
    );

    var sectPr =
      "<w:sectPr>" +
      '<w:pgSz w:w="11906" w:h="16838"/>' +
      '<w:pgMar w:top="1440" w:right="1134" w:bottom="1440" w:left="1134" w:header="720" w:footer="720" w:gutter="0"/>' +
      "</w:sectPr>";

    return (
      XML_HEAD +
      '<w:document xmlns:w="' +
      NS_W +
      '" xmlns:r="' +
      NS_R +
      '"><w:body>' +
      parts.join("") +
      sectPr +
      "</w:body></w:document>"
    );
  }

  function stylesXml() {
    var fonts =
      '<w:rFonts w:ascii="' +
      FONT +
      '" w:eastAsia="' +
      FONT +
      '" w:hAnsi="' +
      FONT +
      '" w:cs="' +
      FONT +
      '"/>';
    return (
      XML_HEAD +
      '<w:styles xmlns:w="' +
      NS_W +
      '">' +
      "<w:docDefaults><w:rPrDefault><w:rPr>" +
      fonts +
      '<w:sz w:val="21"/><w:szCs w:val="21"/><w:lang w:val="ko-KR" w:eastAsia="ko-KR"/>' +
      "</w:rPr></w:rPrDefault>" +
      '<w:pPrDefault><w:pPr><w:spacing w:after="120" w:line="276" w:lineRule="auto"/></w:pPr></w:pPrDefault>' +
      "</w:docDefaults>" +
      '<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:qFormat/></w:style>' +
      '<w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/>' +
      '<w:pPr><w:spacing w:before="0" w:after="120"/></w:pPr><w:rPr><w:b/><w:sz w:val="44"/><w:szCs w:val="44"/></w:rPr></w:style>' +
      '<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/>' +
      '<w:pPr><w:keepNext/><w:spacing w:before="280" w:after="120"/><w:outlineLvl w:val="0"/></w:pPr>' +
      '<w:rPr><w:b/><w:sz w:val="28"/><w:szCs w:val="28"/></w:rPr></w:style>' +
      '<w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/>' +
      '<w:pPr><w:keepNext/><w:spacing w:before="200" w:after="100"/><w:outlineLvl w:val="1"/></w:pPr>' +
      '<w:rPr><w:b/><w:sz w:val="24"/><w:szCs w:val="24"/></w:rPr></w:style>' +
      "</w:styles>"
    );
  }

  function contentTypesXml() {
    return (
      XML_HEAD +
      '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">' +
      '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>' +
      '<Default Extension="xml" ContentType="application/xml"/>' +
      '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>' +
      '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>' +
      '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>' +
      '<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>' +
      "</Types>"
    );
  }

  function rootRelsXml() {
    return (
      XML_HEAD +
      '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' +
      '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>' +
      '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>' +
      '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>' +
      "</Relationships>"
    );
  }

  function documentRelsXml() {
    return (
      XML_HEAD +
      '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' +
      '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>' +
      "</Relationships>"
    );
  }

  function coreXml(doc) {
    var created = w3cDate(doc.createdAt || new Date());
    return (
      XML_HEAD +
      '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" ' +
      'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" ' +
      'xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">' +
      "<dc:title>" +
      util.xmlEscape(CallLog.render.heading(doc)) +
      "</dc:title>" +
      "<dc:subject>통화록</dc:subject>" +
      "<dc:creator>call-log-maker</dc:creator>" +
      "<cp:keywords>" +
      util.xmlEscape(doc.keywords.join(", ")) +
      "</cp:keywords>" +
      "<cp:lastModifiedBy>call-log-maker</cp:lastModifiedBy>" +
      '<dcterms:created xsi:type="dcterms:W3CDTF">' +
      created +
      "</dcterms:created>" +
      '<dcterms:modified xsi:type="dcterms:W3CDTF">' +
      created +
      "</dcterms:modified>" +
      "</cp:coreProperties>"
    );
  }

  function appXml() {
    return (
      XML_HEAD +
      '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" ' +
      'xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">' +
      "<Application>call-log-maker (web)</Application>" +
      "</Properties>"
    );
  }

  function w3cDate(date) {
    var d = date instanceof Date && !isNaN(date.getTime()) ? date : new Date();
    return (
      d.getUTCFullYear() +
      "-" +
      util.pad2(d.getUTCMonth() + 1) +
      "-" +
      util.pad2(d.getUTCDate()) +
      "T" +
      util.pad2(d.getUTCHours()) +
      ":" +
      util.pad2(d.getUTCMinutes()) +
      ":" +
      util.pad2(d.getUTCSeconds()) +
      "Z"
    );
  }

  /** 통화록 doc → .docx 바이너리(Uint8Array) */
  function build(doc) {
    var now = doc.createdAt instanceof Date ? doc.createdAt : new Date();
    var entries = [
      { name: "[Content_Types].xml", data: contentTypesXml() },
      { name: "_rels/.rels", data: rootRelsXml() },
      { name: "docProps/core.xml", data: coreXml(doc) },
      { name: "docProps/app.xml", data: appXml() },
      { name: "word/document.xml", data: documentXml(doc) },
      { name: "word/styles.xml", data: stylesXml() },
      { name: "word/_rels/document.xml.rels", data: documentRelsXml() },
    ];
    entries.forEach(function (entry) {
      entry.date = now;
    });
    return util.zip(entries);
  }

  CallLog.docx = {
    build: build,
    documentXml: documentXml,
    stylesXml: stylesXml,
    contentTypesXml: contentTypesXml,
  };
})(typeof globalThis !== "undefined" ? globalThis : this);
