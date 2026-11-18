/* sw.js 의 공유 받기(POST ./share-target) 처리 점검.
 *
 * 실행 순서: sw_stub.js → docs/sw.js → 이 파일.
 * __IN__ 으로 넘어온 바이트를 파일로 감싸 공유 이벤트를 만들고, 서비스 워커가
 *   - formData 를 읽어 임시 캐시에 담는지
 *   - 음성 파일은 바이트를 담지 않고 isAudio 로만 알리는지
 *   - 303 으로 ./?shared=1 에 되돌려 보내는지
 * 를 확인해 __swResults 에 담는다. (판정은 tests/test_share_target.py)
 *
 * 임시 캐시는 시나리오마다 같은 키를 쓰므로, 앞 시나리오의 결과를 다 읽은 뒤에
 * 다음 시나리오를 시작한다(한 줄로 세워 실행).
 */
(function (root) {
  "use strict";

  var SCOPE = "https://example.test/call-log-maker/";
  var META_KEY = SCOPE + "__shared.json";
  var FILE_KEY = SCOPE + "__shared.bin";
  var SHARE_URL = SCOPE + "share-target";

  var results = {};
  var queue = Promise.resolve();

  function toHex(bytes) {
    var hex = "";
    for (var i = 0; i < bytes.length; i++) {
      var part = bytes[i].toString(16);
      hex += part.length === 1 ? "0" + part : part;
    }
    return hex;
  }

  function makeFile(name, type, bytes) {
    var view = new Uint8Array(bytes || []);
    return {
      name: name,
      type: type,
      size: view.length,
      lastModified: 1763384400000,
      arrayBuffer: function () {
        var copy = new Uint8Array(view.length);
        for (var i = 0; i < view.length; i++) copy[i] = view[i];
        return Promise.resolve(copy.buffer);
      },
    };
  }

  function makeForm(fields, files) {
    var map = fields || {};
    return {
      get: function (name) {
        return Object.prototype.hasOwnProperty.call(map, name) ? map[name] : null;
      },
      getAll: function (name) {
        if (name === "files") return files || [];
        return Object.prototype.hasOwnProperty.call(map, name) ? [map[name]] : [];
      },
    };
  }

  function snapshot(store, response, error) {
    var meta = store[META_KEY];
    var file = store[FILE_KEY];
    return Promise.all([
      meta ? meta.text() : Promise.resolve(null),
      file ? file.arrayBuffer() : Promise.resolve(null),
    ]).then(function (values) {
      var parsed = null;
      if (values[0] !== null) {
        try {
          parsed = JSON.parse(values[0]);
        } catch (err) {
          parsed = { corrupt: String(values[0]) };
        }
      }
      return {
        responded: true,
        url: response ? response.url : null,
        status: response ? response.status : null,
        error: error || null,
        meta: parsed,
        fileHex: values[1] && values[1].byteLength ? toHex(new Uint8Array(values[1])) : null,
        cacheKeys: Object.keys(store).sort(),
      };
    });
  }

  function runOne(name, url, form) {
    root.__sw.reset();
    var store = root.__sw.stores["call-log-maker-share"] || (root.__sw.stores["call-log-maker-share"] = {});

    return new Promise(function (resolve) {
      var called = false;
      var response = null;
      var error = null;

      var event = {
        request: {
          method: "POST",
          url: url,
          mode: "navigate",
          formData: function () {
            return Promise.resolve(form);
          },
        },
        respondWith: function (promise) {
          called = true;
          Promise.resolve(promise).then(
            function (result) {
              response = result;
            },
            function (err) {
              error = String(err);
            }
          ).then(function () {
            return snapshot(store, response, error);
          }).then(function (snap) {
            snap.respondWithCalled = true;
            results[name] = snap;
            resolve();
          });
        },
      };

      root.__sw.fire("fetch", event);

      if (!called) {
        // 가로채지 않은 요청 — 브라우저 기본 동작(405 등)으로 넘어간다
        results[name] = { responded: false, respondWithCalled: false };
        resolve();
      }
    });
  }

  function scenario(name, url, form) {
    queue = queue.then(function () {
      return runOne(name, url, form);
    });
  }

  // 1) .txt 파일 공유 (삼성 통화녹음 UTF-16LE 도 함께)
  scenario(
    "textFile",
    SHARE_URL,
    makeForm(
      { title: "", text: "", url: "" },
      [makeFile("통화 녹음 김지훈_261117_210000.txt", "text/plain", root.__IN__.utf8Bytes)]
    )
  );

  // 2) 붙여넣은 글 공유 (파일 없음) — 앞 시나리오의 파일 바이트가 지워지는지도 확인
  scenario("textOnly", SHARE_URL, makeForm({ title: "", text: root.__IN__.sharedText, url: "" }, []));

  // 3) 음성 파일(.m4a) 공유 — 바이트는 담지 않고 안내용 표시만
  scenario(
    "audioFile",
    SHARE_URL,
    makeForm(
      { title: "", text: "", url: "" },
      [makeFile("통화 녹음 김지훈_261117_210000.m4a", "audio/mp4", root.__IN__.audioBytes)]
    )
  );

  // 4) UTF-16LE .txt 바이트도 그대로 담기는지 (디코딩은 화면 쪽에서)
  scenario(
    "utf16File",
    SHARE_URL,
    makeForm(
      { title: "", text: "" },
      [makeFile("통화 녹음 박동근_261117_143113_original.txt", "text/plain", root.__IN__.utf16Bytes)]
    )
  );

  // 5) 삼성 음성녹음이 .txt 를 application/octet-stream 으로 넘기는 경우 — 글 파일로 담아야 한다
  scenario(
    "octetStreamFile",
    SHARE_URL,
    makeForm(
      { title: "", text: "" },
      [makeFile("음성 녹음 김지훈_261117_210000.txt", "application/octet-stream", root.__IN__.utf8Bytes)]
    )
  );

  // 6) 확장자는 .m4a 인데 형식이 application/octet-stream 인 경우 — 이름을 보고 음성으로 알아본다
  scenario(
    "octetStreamAudio",
    SHARE_URL,
    makeForm(
      { title: "", text: "" },
      [makeFile("통화 녹음 김지훈_261117_210000.m4a", "application/octet-stream", root.__IN__.audioBytes)]
    )
  );

  // 7) 공유 지점이 아닌 POST 는 가로채지 않는다
  scenario("otherPost", SCOPE + "other-endpoint", makeForm({ text: "무시" }, []));

  queue.then(function () {
    root.__swResults = results;
  });
})(typeof globalThis !== "undefined" ? globalThis : this);
