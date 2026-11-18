/* 화면 조작 — 입력은 절대 다시 그리지 않고, 미리보기만 갱신한다.
 *
 * ⚠️ 한글 입력(IME) 주의:
 *   textarea/input 에 글자를 칠 때마다 그 노드를 다시 만들거나 value 를 다시 쓰면
 *   조합 중인 글자가 쪼개진다. 그래서
 *     - input 이벤트에서는 미리보기 영역(#preview)만 바꾼다
 *     - 사용자가 직접 친 값은 다른 이유로 덮어쓰지 않는다(파일을 새로 고를 때만)
 */
(function () {
  "use strict";

  var CallLog = window.CallLog;

  var el = {
    file: document.getElementById("file"),
    fileHint: document.getElementById("file-hint"),
    example: document.getElementById("example"),
    text: document.getElementById("text"),
    title: document.getElementById("title"),
    date: document.getElementById("date"),
    time: document.getElementById("time"),
    preview: document.getElementById("preview"),
    status: document.getElementById("status"),
    notice: document.getElementById("notice"),
    clear: document.getElementById("clear"),
    copy: document.getElementById("copy"),
    saveMd: document.getElementById("save-md"),
    saveDocx: document.getElementById("save-docx"),
    share: document.getElementById("share"),
  };

  var state = {
    fileName: "",
    modifiedAt: null,
    titleTouched: false,
    whenTouched: false,
    whenAuto: null,
    doc: null,
    markdown: "",
  };

  var renderTimer = null;

  /* ---------------------------------------------------------------- 도구 */
  function pad2(n) {
    return (n < 10 ? "0" : "") + n;
  }

  function noop() {}

  /* 주소의 물음표 값 하나를 읽는다 (?shared=1 · ?example=1) */
  function queryParam(name) {
    try {
      if (typeof URLSearchParams === "function") {
        return new URLSearchParams(location.search || "").get(name);
      }
    } catch (err) {
      // URLSearchParams 를 쓰지 못하는 환경은 아래 대체 경로로
    }
    var match = new RegExp("[?&]" + name + "=([^&#]*)").exec(location.search || "");
    if (!match) return null;
    try {
      return decodeURIComponent(match[1].replace(/\+/g, " "));
    } catch (err) {
      return match[1];
    }
  }

  function dateInputValue(date) {
    return date.getFullYear() + "-" + pad2(date.getMonth() + 1) + "-" + pad2(date.getDate());
  }

  function timeInputValue(date) {
    return pad2(date.getHours()) + ":" + pad2(date.getMinutes());
  }

  function parseDateInput(value) {
    var m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value || "");
    if (!m) return null;
    return new Date(parseInt(m[1], 10), parseInt(m[2], 10) - 1, parseInt(m[3], 10));
  }

  function parseTimeInput(value) {
    var m = /^(\d{1,2}):(\d{2})/.exec(value || "");
    if (!m) return null;
    return { hours: parseInt(m[1], 10), minutes: parseInt(m[2], 10) };
  }

  function toast(message) {
    var node = document.querySelector(".toast");
    if (!node) {
      node = document.createElement("div");
      node.className = "toast";
      node.setAttribute("role", "status");
      document.body.appendChild(node);
    }
    node.textContent = message;
    node.classList.add("show");
    clearTimeout(node._timer);
    node._timer = setTimeout(function () {
      node.classList.remove("show");
    }, 1900);
  }

  function flash(button, label) {
    var original = button.textContent;
    button.textContent = label;
    button.classList.add("done");
    setTimeout(function () {
      button.textContent = original;
      button.classList.remove("done");
    }, 1400);
  }

  /* 화면 위쪽 안내 띠 — 토스트와 달리 읽을 시간이 필요한 안내에 쓴다 */
  function showNotice(message, kind) {
    if (!el.notice) {
      toast(message);
      return;
    }
    el.notice.textContent = message;
    el.notice.className = kind ? "notice " + kind : "notice";
    el.notice.hidden = false;
  }

  function hideNotice() {
    if (!el.notice) return;
    el.notice.hidden = true;
    el.notice.textContent = "";
  }

  /* ---------------------------------------------------------------- 입력 해석 */
  function decodeBytes(buffer) {
    // UTF-16LE/BE(BOM 유무 모두) → UTF-8 → EUC-KR 순으로 판별한다 (lib/util.js)
    return CallLog.util.decodeTextBytes(new Uint8Array(buffer));
  }

  function currentWhen() {
    if (!state.whenTouched) return undefined; // 자동 값 그대로
    var date = parseDateInput(el.date.value);
    if (!date) return null;
    var time = parseTimeInput(el.time.value);
    if (time) date.setHours(time.hours, time.minutes, 0, 0);
    else date.setHours(0, 0, 0, 0);
    return date;
  }

  function build() {
    var options = {
      text: el.text.value,
      fileName: state.fileName,
      modifiedAt: state.modifiedAt,
      now: new Date(),
      when: currentWhen(),
    };
    if (state.titleTouched) options.title = el.title.value;
    return CallLog.buildDocument(options);
  }

  function scheduleRender() {
    if (renderTimer) clearTimeout(renderTimer);
    renderTimer = setTimeout(render, 180);
  }

  function render() {
    renderTimer = null;

    // 아직 아무것도 없으면 통화록 틀 대신 안내를 보여 준다
    if (!el.text.value.trim()) {
      state.doc = null;
      state.markdown = "";
      el.preview.innerHTML =
        '<p class="doc-empty">위에 .txt를 고르거나 내용을 붙여넣으면 여기에 통화록이 나타납니다.</p>';
      el.status.textContent = "내용을 붙여넣으면 바로 통화록이 만들어집니다.";
      el.status.classList.remove("warn");
      [el.copy, el.saveMd, el.saveDocx, el.share].forEach(function (button) {
        button.disabled = true;
      });
      return;
    }

    var doc = build();
    state.doc = doc;
    state.markdown = CallLog.render.toMarkdown(doc);

    el.preview.innerHTML = CallLog.render.toPreviewHtml(doc);

    // 자동으로 채운 값은 사용자가 건드리지 않았을 때만 반영한다
    if (!state.titleTouched) el.title.value = doc.title;
    if (!state.whenTouched) {
      state.whenAuto = doc.when;
      if (doc.when) {
        el.date.value = dateInputValue(doc.when);
        el.time.value = timeInputValue(doc.when);
      } else {
        el.date.value = "";
        el.time.value = "";
      }
    }

    var bits = [doc.utteranceCount + "개 발화", CallLog.util.groupDigits(doc.charCount) + "자"];
    if (doc.speakers.length) bits.push("화자 " + doc.speakers.join("·"));
    el.status.textContent = bits.join(" · ");
    el.status.classList.toggle("warn", doc.utteranceCount === 0);

    var empty = doc.utteranceCount === 0;
    [el.copy, el.saveMd, el.saveDocx].forEach(function (button) {
      button.disabled = empty;
    });
    el.share.hidden = !canShareFiles();
    el.share.disabled = empty;
  }

  /* ---------------------------------------------------------------- 파일 */
  /* 새 내용(파일·공유)을 입력창에 넣는다 — 사용자가 친 값은 이때만 갱신한다 */
  function applyText(text, fileName, modifiedAt, hintText) {
    state.fileName = fileName || "";
    state.modifiedAt = modifiedAt || null;
    state.titleTouched = false;
    state.whenTouched = false;
    el.text.value = text;
    el.title.value = "";
    el.date.value = "";
    el.time.value = "";
    el.fileHint.textContent = hintText;
    hideNotice();
    render();
    el.preview.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function applyFile(file, asExample) {
    if (!file) return;
    var reader = new FileReader();
    reader.onload = function () {
      var text = decodeBytes(reader.result);
      applyText(
        text,
        asExample ? "" : file.name || "",
        file.lastModified ? new Date(file.lastModified) : null,
        asExample
          ? "예시 내용을 채웠어요."
          : "📄 " + (file.name || "") + " 불러왔어요."
      );
    };
    reader.onerror = function () {
      el.fileHint.textContent = "파일을 읽지 못했어요. 다른 방법으로 붙여넣어 주세요.";
    };
    reader.readAsArrayBuffer(file);
  }

  el.file.addEventListener("change", function () {
    applyFile(el.file.files && el.file.files[0], false);
  });

  // PC에서 끌어다 놓기 (모바일에서는 쓰지 않지만 해가 없음)
  document.addEventListener("dragover", function (event) {
    if (event.dataTransfer && event.dataTransfer.types && event.dataTransfer.types.indexOf("Files") >= 0) {
      event.preventDefault();
    }
  });
  document.addEventListener("drop", function (event) {
    if (!event.dataTransfer || !event.dataTransfer.files || !event.dataTransfer.files.length) return;
    event.preventDefault();
    applyFile(event.dataTransfer.files[0], false);
  });

  /* ---------------------------------------------------------------- 텍스트/필드 */
  el.text.addEventListener("input", function () {
    // 입력 노드는 그대로 두고 미리보기만 갱신한다 (한글 조합 보호)
    scheduleRender();
  });

  el.title.addEventListener("input", function () {
    state.titleTouched = true;
    scheduleRender();
  });

  [el.date, el.time].forEach(function (input) {
    input.addEventListener("input", function () {
      state.whenTouched = true;
      scheduleRender();
    });
    input.addEventListener("change", function () {
      state.whenTouched = true;
      scheduleRender();
    });
  });

  el.clear.addEventListener("click", function () {
    state.fileName = "";
    state.modifiedAt = null;
    state.titleTouched = false;
    state.whenTouched = false;
    state.whenAuto = null;
    el.text.value = "";
    el.title.value = "";
    el.date.value = "";
    el.time.value = "";
    el.file.value = "";
    el.fileHint.textContent = "삼성 “음성녹음” 앱 → 녹음 선택 → 공유/저장 → 텍스트(.txt)";
    hideNotice();
    render();
    el.text.focus();
  });

  /* ---------------------------------------------------------------- 내보내기 */
  function downloadBlob(blob, fileName) {
    var url = URL.createObjectURL(blob);
    var link = document.createElement("a");
    link.href = url;
    link.download = fileName;
    link.rel = "noopener";
    document.body.appendChild(link);
    link.click();
    setTimeout(function () {
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    }, 1000);
  }

  function copyText(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      return navigator.clipboard.writeText(text);
    }
    return new Promise(function (resolve, reject) {
      var area = document.createElement("textarea");
      area.value = text;
      area.setAttribute("readonly", "");
      area.style.position = "fixed";
      area.style.top = "-1000px";
      document.body.appendChild(area);
      area.select();
      var ok = false;
      try {
        ok = document.execCommand("copy");
      } catch (err) {
        ok = false;
      }
      document.body.removeChild(area);
      ok ? resolve() : reject(new Error("복사 실패"));
    });
  }

  el.copy.addEventListener("click", function () {
    if (!state.markdown) return;
    copyText(state.markdown).then(
      function () {
        flash(el.copy, "복사했어요 ✓");
        toast("통화록을 Markdown으로 복사했어요");
      },
      function () {
        toast("복사가 막혀 있어요. .md로 저장해 주세요");
      }
    );
  });

  el.saveMd.addEventListener("click", function () {
    if (!state.doc) return;
    var blob = new Blob([state.markdown], { type: "text/markdown;charset=utf-8" });
    downloadBlob(blob, CallLog.outputName(state.doc, "md"));
  });

  function docxBytes() {
    return CallLog.docx.build(state.doc);
  }

  function docxFile() {
    var bytes = docxBytes();
    return new File([bytes], CallLog.outputName(state.doc, "docx"), {
      type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    });
  }

  el.saveDocx.addEventListener("click", function () {
    if (!state.doc) return;
    var bytes = docxBytes();
    var blob = new Blob([bytes], {
      type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    });
    downloadBlob(blob, CallLog.outputName(state.doc, "docx"));
    flash(el.saveDocx, "저장 ✓");
  });

  /* ---------------------------------------------------------------- 공유 */
  function canShareFiles() {
    try {
      if (!navigator.share || !navigator.canShare || typeof File !== "function") return false;
      return navigator.canShare({ files: [new File([new Uint8Array([1])], "a.docx")] });
    } catch (err) {
      return false;
    }
  }

  el.share.addEventListener("click", function () {
    if (!state.doc) return;
    var name = CallLog.outputName(state.doc, "docx");
    var file;
    try {
      file = docxFile();
    } catch (err) {
      toast("공유 파일을 만들지 못했어요");
      return;
    }
    navigator
      .share({
        files: [file],
        title: "통화록 - " + state.doc.title,
        text: "call-log-maker 로 만든 통화록입니다.",
      })
      .catch(function (err) {
        if (err && err.name === "AbortError") return;
        toast("공유를 열지 못했어요. .docx로 저장해 주세요");
      });
  });

  /* ---------------------------------------------------------------- 예시 */
  function loadExample() {
    fetch("assets/sample.txt")
      .then(function (response) {
        return response.ok ? response.text() : Promise.reject(new Error("no sample"));
      })
      .then(function (text) {
        state.fileName = "통화 녹음 김지훈_261117_210000.txt";
        state.modifiedAt = null;
        state.titleTouched = false;
        state.whenTouched = false;
        el.text.value = text;
        el.title.value = "";
        el.date.value = "";
        el.time.value = "";
        el.fileHint.textContent = "예시 내용을 채웠어요. 내 기록으로 바꾸려면 위에서 파일을 고르세요.";
        render();
        el.preview.scrollIntoView({ behavior: "smooth", block: "start" });
      })
      .catch(function () {
        toast("예시를 불러오지 못했어요 (인터넷 연결 필요)");
      });
  }

  if (el.example) el.example.addEventListener("click", loadExample);

  /* ---------------------------------------------------------------- 공유 메뉴로 받기
   * 안드로이드 공유 메뉴(공유 → 통화록 변환기)로 들어온 내용은 sw.js 가
   * POST ./share-target 을 가로채 임시 캐시에 담아 두고 ./?shared=1 로 되돌려 보낸다.
   * 여기서 그 내용을 꺼내 입력창을 채우고, 읽은 뒤에는 캐시를 지운다. */
  var SHARE_CACHE = "call-log-maker-share";
  var SHARE_META = "__shared.json";
  var SHARE_FILE = "__shared.bin";

  function shareKey(name) {
    try {
      return new URL("./" + name, location.href).href;
    } catch (err) {
      return "./" + name;
    }
  }

  /* 주소창에서 ?shared=1 을 지워 새로고침해도 같은 공유를 다시 읽지 않게 한다 */
  function cleanSharedUrl() {
    try {
      if (window.history && window.history.replaceState) {
        var rest = "";
        var query = String(location.search || "").replace(/^\?/, "").split("&");
        query = query.filter(function (pair) {
          return pair && pair.split("=")[0] !== "shared";
        });
        if (query.length) rest = "?" + query.join("&");
        window.history.replaceState(null, "", location.pathname + rest + (location.hash || ""));
      }
    } catch (err) {
      // 주소를 못 고쳐도 변환에는 지장이 없다
    }
  }

  /* 정해진 키로 먼저 찾고, 없으면 캐시 안에서 파일 이름으로 한 번 더 훑는다 */
  function findShared(cache, key, name) {
    return Promise.resolve(cache.match(key)).then(function (hit) {
      if (hit) return hit;
      if (!cache.keys) return null;
      return Promise.resolve(cache.keys()).then(function (requests) {
        for (var i = 0; i < requests.length; i++) {
          var href = String((requests[i] && requests[i].url) || requests[i] || "");
          if (href.split("?")[0].slice(-name.length) === name) return cache.match(href);
        }
        return null;
      });
    }).catch(function () {
      return null;
    });
  }

  /* 평소에 앱을 열었을 때 — 공유받은 채로 남은 임시 캐시를 지운다.
   * (통화 내용이 브라우저 저장소에 남지 않게. 읽고 지우는 것이 기본이고, 이게 마지막 안전장치) */
  function clearSharedCache() {
    if (typeof caches === "undefined" || !caches.delete) return Promise.resolve(false);
    try {
      return Promise.resolve(caches.delete(SHARE_CACHE)).catch(noop);
    } catch (err) {
      return Promise.resolve(false);
    }
  }

  function dropShared(cache) {
    var names = [SHARE_META, SHARE_FILE];
    try {
      Promise.resolve(cache.delete(shareKey(SHARE_META))).catch(noop);
      Promise.resolve(cache.delete(shareKey(SHARE_FILE))).catch(noop);
      // 키 모양이 어긋난 경우(주소가 달라진 설치본 등)까지 쓸어 둔다
      if (cache.keys) {
        Promise.resolve(cache.keys()).then(function (requests) {
          (requests || []).forEach(function (request) {
            var href = String((request && request.url) || request || "");
            var path = href.split("?")[0];
            for (var i = 0; i < names.length; i++) {
              if (path.slice(-names[i].length) === names[i]) {
                Promise.resolve(cache.delete(href)).catch(noop);
                break;
              }
            }
          });
        }).catch(noop);
      }
    } catch (err) {
      // 지우지 못해도 다음 공유가 덮어쓴다
    }
  }

  function applyShared(meta, buffer) {
    if (!meta) {
      showNotice("공유받은 내용을 읽지 못했어요. .txt 파일을 직접 골라 주세요.", "warn");
      return false;
    }

    // 음성 파일(.m4a 등)은 브라우저에서 글자로 옮길 수 없다 — 방법을 알려 준다
    if (meta.isAudio) {
      showNotice(
        "음성 파일(" + (meta.fileName || ".m4a") + ")은 브라우저에서 바로 변환할 수 없어요. " +
          "삼성 “음성녹음” 앱에서 텍스트(.txt)로 변환한 뒤 공유하거나 PC 버전을 이용해 주세요.",
        "warn"
      );
      toast("음성 파일은 .txt 로 변환해서 공유해 주세요");
      return false;
    }

    var fileName = String(meta.fileName || "");
    var modifiedAt = meta.modifiedAt ? new Date(meta.modifiedAt) : null;

    if (buffer && buffer.byteLength) {
      applyText(decodeBytes(buffer), fileName, modifiedAt, "📄 " + fileName + " 공유받았어요.");
      toast("공유받은 파일을 통화록으로 만들었어요");
      return true;
    }

    if (fileName && meta.error) {
      showNotice("공유받은 파일(" + fileName + ")을 읽지 못했어요. 파일을 직접 골라 주세요.", "warn");
      return false;
    }

    var body = String(meta.text || "");
    if (!body.trim() && meta.title) body = String(meta.title);
    if (!body.trim()) {
      showNotice("공유받은 내용이 비어 있어요. .txt 파일이나 대화 내용을 공유해 주세요.", "warn");
      return false;
    }

    applyText(body, "", null, "공유받은 내용을 채웠어요.");
    toast("공유받은 내용으로 통화록을 만들었어요");
    return true;
  }

  function consumeShared() {
    cleanSharedUrl();
    if (typeof caches === "undefined" || !caches.open) {
      showNotice("이 브라우저에서는 공유받은 내용을 읽을 수 없어요. 파일을 직접 골라 주세요.", "warn");
      return Promise.resolve(false);
    }

    var metaKey = shareKey(SHARE_META);
    var fileKey = shareKey(SHARE_FILE);

    return Promise.resolve(caches.open(SHARE_CACHE)).then(function (cache) {
      return findShared(cache, metaKey, SHARE_META).then(function (hit) {
        if (!hit) {
          dropShared(cache);
          showNotice(
            "공유받은 내용을 찾지 못했어요. 앱을 한 번 연 뒤 다시 공유하거나, .txt 파일을 직접 골라 주세요.",
            "warn"
          );
          return false;
        }
        return Promise.resolve(hit.text()).then(function (raw) {
          var meta = null;
          try {
            meta = JSON.parse(raw);
          } catch (err) {
            meta = null;
          }
          return findShared(cache, fileKey, SHARE_FILE).then(function (fileHit) {
            if (!fileHit || !fileHit.arrayBuffer) return applyShared(meta, null);
            return Promise.resolve(fileHit.arrayBuffer()).then(function (bytes) {
              return applyShared(meta, bytes);
            }, function () {
              return applyShared(meta, null);
            });
          });
        }).then(function (done) {
          dropShared(cache);
          return done;
        });
      });
    }).catch(function () {
      showNotice("공유받은 내용을 읽지 못했어요. 파일을 직접 골라 주세요.", "warn");
      return false;
    });
  }

  /* ---------------------------------------------------------------- 시작 */
  if (canShareFiles()) el.share.hidden = false;
  render();

  // 공유 메뉴로 넘어온 경우(?shared=1)에는 그 내용을 먼저 채운다
  if (queryParam("shared") === "1") {
    consumeShared();
  } else {
    // 평소 실행이면 지난번 공유가 남긴 임시 내용을 지운다
    clearSharedCache();
    if (/[?&]example=1/.test(location.search)) {
      // 주소 끝에 ?example=1 로 열면 예시 내용이 채워진 상태로 시작한다 (안내용)
      loadExample();
    }
  }

  // 앱이 화면에 돌아올 때 상태를 잃지 않게 입력값을 localStorage 에 보관하지는 않는다.
  // (통화 내용이 기기 브라우저 저장소에 남지 않도록)
})();
