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
  function applyFile(file, asExample) {
    if (!file) return;
    var reader = new FileReader();
    reader.onload = function () {
      var text = decodeBytes(reader.result);
      state.fileName = asExample ? "" : file.name || "";
      state.modifiedAt = file.lastModified ? new Date(file.lastModified) : null;
      state.titleTouched = false;
      state.whenTouched = false;
      // 파일을 새로 고를 때만 입력값을 갱신한다 (타이핑 중에는 건드리지 않음)
      el.text.value = text;
      el.title.value = "";
      el.date.value = "";
      el.time.value = "";
      el.fileHint.textContent = state.fileName
        ? "📄 " + state.fileName + " 불러왔어요."
        : "예시 내용을 채웠어요.";
      render();
      el.preview.scrollIntoView({ behavior: "smooth", block: "start" });
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

  /* ---------------------------------------------------------------- 시작 */
  if (canShareFiles()) el.share.hidden = false;
  render();

  // 주소 끝에 ?example=1 로 열면 예시 내용이 채워진 상태로 시작한다 (안내용)
  if (/[?&]example=1/.test(location.search)) loadExample();

  // 앱이 화면에 돌아올 때 상태를 잃지 않게 입력값을 localStorage 에 보관하지는 않는다.
  // (통화 내용이 기기 브라우저 저장소에 남지 않도록)
})();
