/* 아주 작은 가짜 DOM — app.js 를 브라우저 없이 실행해 보기 위한 것.
 * (실제 화면 테스트가 아니라 "화면 코드가 터지지 않고 값을 제대로 채우는지" 확인용)
 */
(function (root) {
  "use strict";

  var timers = [];
  var timerId = 0;

  function makeElement(id) {
    var listeners = {};
    var classes = {};
    return {
      id: id,
      tagName: "DIV",
      value: "",
      textContent: "",
      innerHTML: "",
      hidden: false,
      disabled: false,
      files: null,
      _listeners: listeners,
      classList: {
        add: function (name) { classes[name] = true; },
        remove: function (name) { delete classes[name]; },
        toggle: function (name, on) {
          if (on === undefined ? !classes[name] : on) classes[name] = true;
          else delete classes[name];
        },
        contains: function (name) { return !!classes[name]; },
      },
      addEventListener: function (name, handler) {
        (listeners[name] = listeners[name] || []).push(handler);
      },
      dispatch: function (name) {
        (listeners[name] || []).forEach(function (handler) {
          handler({ target: this, preventDefault: function () {} });
        }, this);
      },
      setAttribute: function () {},
      removeAttribute: function () {},
      appendChild: function () {},
      removeChild: function () {},
      scrollIntoView: function () {},
      focus: function () {},
      querySelector: function () { return null; },
      style: {},
    };
  }

  var elements = {};
  ["file", "file-hint", "text", "title", "date", "time", "preview", "status",
    "notice", "clear", "copy", "save-md", "save-docx", "share", "example"].forEach(function (id) {
    elements[id] = makeElement(id);
  });
  // index.html 의 안내 띠는 hidden 속성으로 시작한다
  elements.notice.hidden = true;

  var body = makeElement("body");

  root.document = {
    body: body,
    getElementById: function (id) {
      return elements[id] || null;
    },
    querySelector: function () {
      return null;
    },
    createElement: function (tag) {
      return makeElement("created-" + tag);
    },
    addEventListener: function () {},
    execCommand: function () { return true; },
  };

  root.window = root;
  root.navigator = {};
  root.location = {
    search: "",
    pathname: "/call-log-maker/",
    hash: "",
    href: "https://example.test/call-log-maker/",
    origin: "https://example.test",
  };
  root.history = {
    replaceState: function (state, title, url) {
      root.__replacedUrl = url;
    },
  };
  root.URL = {
    createObjectURL: function () {
      return "blob:stub";
    },
    revokeObjectURL: function () {},
  };
  root.Blob = function (parts, options) {
    this.parts = parts;
    this.type = options && options.type;
  };
  root.File = function (parts, name, options) {
    this.parts = parts;
    this.name = name;
    this.type = options && options.type;
  };

  // TextDecoder: UTF-8 만 실제로 디코딩한다 (나머지는 미지원으로 흉내)
  root.TextDecoder = function (label) {
    this.label = String(label || "utf-8").toLowerCase();
  };
  root.TextDecoder.prototype.decode = function (bytes) {
    if (this.label !== "utf-8" && this.label !== "utf8") throw new Error("unsupported encoding");
    return new root.CallLog.util.Utf8Decoder().decode(bytes);
  };

  root.FileReader = function () {
    this.result = null;
    this.onload = null;
    this.onerror = null;
  };
  root.FileReader.prototype.readAsArrayBuffer = function (file) {
    this.result = file._buffer;
    if (this.onload) this.onload();
  };

  root.setTimeout = function (fn) {
    timerId += 1;
    timers.push({ id: timerId, fn: fn, cleared: false });
    return timerId;
  };
  root.clearTimeout = function (id) {
    timers.forEach(function (timer) {
      if (timer.id === id) timer.cleared = true;
    });
  };
  root.fetch = function () {
    return Promise.reject(new Error("fetch 는 이 테스트에서 쓰지 않습니다"));
  };

  /* Cache API 흉내 — app.js 가 공유받은 내용을 꺼내는지 보려면 필요하다.
   * (실제 저장은 sw.js 가 하고, 여기서는 미리 담아 둔 상태를 만들어 준다) */
  var cacheStores = {};

  function cacheKeyName(key) {
    return String((key && key.url) || key || "");
  }

  function makeCachedResponse(entry) {
    return {
      ok: true,
      headers: entry.headers || {},
      text: function () {
        return Promise.resolve(entry.body == null ? "" : String(entry.body));
      },
      arrayBuffer: function () {
        return Promise.resolve(entry.buffer || new ArrayBuffer(0));
      },
    };
  }

  function makeCache(name) {
    var store = cacheStores[name] || (cacheStores[name] = {});
    return {
      put: function (key, response) {
        store[cacheKeyName(key)] = response;
        return Promise.resolve();
      },
      match: function (key) {
        var entry = store[cacheKeyName(key)];
        return Promise.resolve(entry ? makeCachedResponse(entry) : undefined);
      },
      delete: function (key) {
        var key2 = cacheKeyName(key);
        var had = Object.prototype.hasOwnProperty.call(store, key2);
        delete store[key2];
        return Promise.resolve(had);
      },
      keys: function () {
        return Promise.resolve(Object.keys(store).map(function (key) {
          return { url: key };
        }));
      },
    };
  }

  root.caches = {
    open: function (name) {
      return Promise.resolve(makeCache(name));
    },
    delete: function (name) {
      var had = Object.prototype.hasOwnProperty.call(cacheStores, name);
      delete cacheStores[name];
      return Promise.resolve(had);
    },
    keys: function () {
      return Promise.resolve(Object.keys(cacheStores));
    },
    match: function () {
      return Promise.resolve(undefined);
    },
  };

  root.__caches = {
    stores: cacheStores,
    seed: function (cacheName, entryName, entry) {
      var store = cacheStores[cacheName] || (cacheStores[cacheName] = {});
      store[entryName] = entry;
    },
    keys: function (cacheName) {
      return Object.keys(cacheStores[cacheName] || {});
    },
    clear: function () {
      Object.keys(cacheStores).forEach(function (name) {
        delete cacheStores[name];
      });
    },
  };

  root.__dom = {
    elements: elements,
    body: body,
    flushTimers: function () {
      var pending = timers.filter(function (timer) {
        return !timer.cleared;
      });
      timers = [];
      pending.forEach(function (timer) {
        timer.fn();
      });
    },
    resetTimers: function () {
      timers = [];
    },
  };
})(typeof globalThis !== "undefined" ? globalThis : this);
