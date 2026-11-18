/* 공용 도구: UTF-8 인코딩, CRC32, ZIP 쓰기, XML 이스케이프.
 *
 * 브라우저(TextEncoder)·Node·quickjs 어디서든 같은 결과가 나오도록
 * 인코딩은 직접 구현한다. (테스트와 실제 화면이 같은 코드를 쓰게 하기 위함)
 */
(function (global) {
  "use strict";

  var CallLog = (global.CallLog = global.CallLog || {});

  function utf8Encode(text) {
    var str = String(text == null ? "" : text);
    var bytes = [];
    for (var i = 0; i < str.length; i++) {
      var code = str.charCodeAt(i);
      // 서로게이트 쌍을 합쳐 코드 포인트로 만든다
      if (code >= 0xd800 && code <= 0xdbff && i + 1 < str.length) {
        var next = str.charCodeAt(i + 1);
        if (next >= 0xdc00 && next <= 0xdfff) {
          code = ((code - 0xd800) << 10) + (next - 0xdc00) + 0x10000;
          i += 1;
        }
      }
      if (code < 0x80) {
        bytes.push(code);
      } else if (code < 0x800) {
        bytes.push(0xc0 | (code >> 6), 0x80 | (code & 0x3f));
      } else if (code < 0x10000) {
        bytes.push(0xe0 | (code >> 12), 0x80 | ((code >> 6) & 0x3f), 0x80 | (code & 0x3f));
      } else {
        bytes.push(
          0xf0 | (code >> 18),
          0x80 | ((code >> 12) & 0x3f),
          0x80 | ((code >> 6) & 0x3f),
          0x80 | (code & 0x3f)
        );
      }
    }
    return new Uint8Array(bytes);
  }

  function concatBytes(chunks) {
    var total = 0;
    for (var i = 0; i < chunks.length; i++) total += chunks[i].length;
    var out = new Uint8Array(total);
    var at = 0;
    for (var j = 0; j < chunks.length; j++) {
      out.set(chunks[j], at);
      at += chunks[j].length;
    }
    return out;
  }

  var CRC_TABLE = (function () {
    var table = new Uint32Array(256);
    for (var n = 0; n < 256; n++) {
      var c = n;
      for (var k = 0; k < 8; k++) {
        c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
      }
      table[n] = c >>> 0;
    }
    return table;
  })();

  function crc32(bytes) {
    var crc = 0xffffffff;
    for (var i = 0; i < bytes.length; i++) {
      crc = CRC_TABLE[(crc ^ bytes[i]) & 0xff] ^ (crc >>> 8);
    }
    return (crc ^ 0xffffffff) >>> 0;
  }

  function toHex(bytes) {
    var out = "";
    for (var i = 0; i < bytes.length; i++) {
      var h = bytes[i].toString(16);
      out += h.length === 1 ? "0" + h : h;
    }
    return out;
  }

  function fromHex(hex) {
    var text = String(hex || "").replace(/[^0-9a-fA-F]/g, "");
    if (text.length % 2) throw new Error("hex 문자열 길이가 홀수입니다.");
    var out = new Uint8Array(text.length / 2);
    for (var i = 0; i < out.length; i++) {
      out[i] = parseInt(text.substr(i * 2, 2), 16);
    }
    return out;
  }

  /* ---------------------------------------------------------------- ZIP
   * OOXML(.docx)은 ZIP 컨테이너면 충분하므로 무압축(store) 방식으로 쓴다.
   * 외부 라이브러리 없이 브라우저에서 바로 만들 수 있고, 규격상 유효하다.
   */

  function dosDateTime(date) {
    var d = date instanceof Date && !isNaN(date.getTime()) ? date : new Date(1980, 0, 1);
    var year = d.getFullYear();
    if (year < 1980) return { time: 0, date: (1 << 5) | 1 };
    var time = ((d.getHours() & 0x1f) << 11) | ((d.getMinutes() & 0x3f) << 5) | ((d.getSeconds() / 2) & 0x1f);
    var day = ((year - 1980) << 9) | (((d.getMonth() + 1) & 0x0f) << 5) | (d.getDate() & 0x1f);
    return { time: time & 0xffff, date: day & 0xffff };
  }

  function u16(value) {
    return new Uint8Array([value & 0xff, (value >>> 8) & 0xff]);
  }

  function u32(value) {
    var v = value >>> 0;
    return new Uint8Array([v & 0xff, (v >>> 8) & 0xff, (v >>> 16) & 0xff, (v >>> 24) & 0xff]);
  }

  /**
   * entries: [{ name: "word/document.xml", data: Uint8Array|string, date?: Date }]
   * → Uint8Array (ZIP 바이너리)
   */
  function zip(entries) {
    var chunks = [];
    var central = [];
    var offset = 0;

    for (var i = 0; i < entries.length; i++) {
      var entry = entries[i];
      var nameBytes = utf8Encode(entry.name);
      var data =
        typeof entry.data === "string" ? utf8Encode(entry.data) : entry.data || new Uint8Array(0);
      var stamp = dosDateTime(entry.date);
      var crc = crc32(data);

      var local = concatBytes([
        u32(0x04034b50), // local file header
        u16(20), // version needed
        u16(0x0800), // flag: UTF-8 이름
        u16(0), // method: store
        u16(stamp.time),
        u16(stamp.date),
        u32(crc),
        u32(data.length),
        u32(data.length),
        u16(nameBytes.length),
        u16(0), // extra length
        nameBytes,
      ]);
      chunks.push(local, data);

      central.push(
        concatBytes([
          u32(0x02014b50), // central directory header
          u16(20), // version made by
          u16(20), // version needed
          u16(0x0800),
          u16(0),
          u16(stamp.time),
          u16(stamp.date),
          u32(crc),
          u32(data.length),
          u32(data.length),
          u16(nameBytes.length),
          u16(0), // extra
          u16(0), // comment
          u16(0), // disk number
          u16(0), // internal attrs
          u32(0), // external attrs
          u32(offset),
          nameBytes,
        ])
      );
      offset += local.length + data.length;
    }

    var centralBytes = concatBytes(central);
    var end = concatBytes([
      u32(0x06054b50), // end of central directory
      u16(0),
      u16(0),
      u16(entries.length),
      u16(entries.length),
      u32(centralBytes.length),
      u32(offset),
      u16(0),
    ]);
    return concatBytes(chunks.concat([centralBytes, end]));
  }

  /* ZIP 바이너리를 읽어 항목 이름과 바이트를 돌려준다 (테스트·검증용). */
  function unzip(bytes) {
    var view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
    var eocd = -1;
    for (var i = bytes.length - 22; i >= 0; i--) {
      if (view.getUint32(i, true) === 0x06054b50) {
        eocd = i;
        break;
      }
    }
    if (eocd < 0) throw new Error("ZIP 끝 레코드(EOCD)를 찾지 못했습니다.");
    var count = view.getUint16(eocd + 10, true);
    var cursor = view.getUint32(eocd + 16, true);
    var out = [];
    var decoder = new Utf8Decoder();
    for (var n = 0; n < count; n++) {
      if (view.getUint32(cursor, true) !== 0x02014b50) {
        throw new Error("중앙 디렉터리 서명이 올바르지 않습니다.");
      }
      var method = view.getUint16(cursor + 10, true);
      var crc = view.getUint32(cursor + 16, true);
      var compSize = view.getUint32(cursor + 20, true);
      var nameLen = view.getUint16(cursor + 28, true);
      var extraLen = view.getUint16(cursor + 30, true);
      var commentLen = view.getUint16(cursor + 32, true);
      var localOffset = view.getUint32(cursor + 42, true);
      var name = decoder.decode(bytes.subarray(cursor + 46, cursor + 46 + nameLen));
      cursor += 46 + nameLen + extraLen + commentLen;

      if (view.getUint32(localOffset, true) !== 0x04034b50) {
        throw new Error("로컬 헤더 서명이 올바르지 않습니다: " + name);
      }
      var localNameLen = view.getUint16(localOffset + 26, true);
      var localExtraLen = view.getUint16(localOffset + 28, true);
      var dataStart = localOffset + 30 + localNameLen + localExtraLen;
      var raw = bytes.subarray(dataStart, dataStart + compSize);
      if (method !== 0) throw new Error("무압축(store) 항목만 읽을 수 있습니다: " + name);
      out.push({ name: name, data: raw, crc: crc });
    }
    return out;
  }

  /* UTF-8 바이트 → 문자열 (TextDecoder 가 없는 환경용) */
  function Utf8Decoder() {}
  Utf8Decoder.prototype.decode = function (bytes) {
    var out = "";
    for (var i = 0; i < bytes.length; i++) {
      var b = bytes[i];
      if (b < 0x80) {
        out += String.fromCharCode(b);
      } else if (b < 0xe0) {
        out += String.fromCharCode(((b & 0x1f) << 6) | (bytes[++i] & 0x3f));
      } else if (b < 0xf0) {
        out += String.fromCharCode(((b & 0x0f) << 12) | ((bytes[++i] & 0x3f) << 6) | (bytes[++i] & 0x3f));
      } else {
        var cp =
          ((b & 0x07) << 18) |
          ((bytes[++i] & 0x3f) << 12) |
          ((bytes[++i] & 0x3f) << 6) |
          (bytes[++i] & 0x3f);
        cp -= 0x10000;
        out += String.fromCharCode(0xd800 + (cp >> 10), 0xdc00 + (cp & 0x3ff));
      }
    }
    return out;
  };

  function xmlEscape(text) {
    return String(text == null ? "" : text)
      // XML 1.0 에서 쓸 수 없는 제어 문자는 미리 지운다
      .replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f]/g, "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function pad2(n) {
    return (n < 10 ? "0" : "") + n;
  }

  function groupDigits(n) {
    return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  }

  function chars(text) {
    // 코드 포인트 단위 길이/자르기 (이모지가 섞여도 안전)
    return Array.from(String(text == null ? "" : text));
  }

  CallLog.util = {
    utf8Encode: utf8Encode,
    concatBytes: concatBytes,
    crc32: crc32,
    toHex: toHex,
    fromHex: fromHex,
    zip: zip,
    unzip: unzip,
    Utf8Decoder: Utf8Decoder,
    xmlEscape: xmlEscape,
    pad2: pad2,
    groupDigits: groupDigits,
    chars: chars,
    dosDateTime: dosDateTime,
  };
})(typeof globalThis !== "undefined" ? globalThis : this);
