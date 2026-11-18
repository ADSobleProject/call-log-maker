/* sw.js(서비스 워커)를 브라우저 없이 돌려 보기 위한 최소 환경.
 *
 * 서비스 워커 전역(self·location·registration)과 Response·URL·caches 만 흉내 낸다.
 * 실제 브라우저의 동작을 대신하지 않고, "POST ./share-target 을 가로채
 * formData 를 임시 캐시에 담고 303 으로 되돌리는지" 만 확인하려는 것.
 */
(function (root) {
  "use strict";

  root.self = root;

  /* --- URL: 상대 경로 해석만 되면 충분하다 --- */
  function URLStub(input, base) {
    var value = String(input == null ? "" : input);
    if (!/^[a-z][a-z0-9+.-]*:\/\//i.test(value)) {
      var baseStr = String(base == null ? "https://example.test/" : base);
      var match = /^([a-z][a-z0-9+.-]*:\/\/[^\/]*)(.*)$/i.exec(baseStr);
      if (!match) throw new Error("bad base url");
      var origin = match[1];
      var basePath = match[2] || "/";
      if (value.charAt(0) === "/") {
        value = origin + value;
      } else {
        var dir = basePath.slice(0, basePath.lastIndexOf("/") + 1);
        value = origin + dir + value;
        value = value.replace(/\/\.\//g, "/");
      }
    }
    this.href = value;
    var parts =
      /^([a-z][a-z0-9+.-]*:\/\/[^\/?#]*)([^?#]*)(\?[^#]*)?(#.*)?$/i.exec(value) || [];
    this.origin = parts[1] || "";
    this.pathname = parts[2] || "/";
    this.search = parts[3] || "";
    this.hash = parts[4] || "";
  }
  URLStub.prototype.toString = function () {
    return this.href;
  };
  root.URL = URLStub;

  /* --- Response --- */
  function ResponseStub(body, init) {
    this._body = body;
    this.headers = (init && init.headers) || {};
    this.status = 200;
    this.ok = true;
    this.url = "";
    this.redirected = false;
  }
  ResponseStub.prototype.clone = function () {
    var copy = new ResponseStub(this._body, { headers: this.headers });
    copy.status = this.status;
    copy.url = this.url;
    return copy;
  };
  ResponseStub.prototype.text = function () {
    var body = this._body;
    if (typeof body === "string") return Promise.resolve(body);
    return Promise.resolve("");
  };
  ResponseStub.prototype.arrayBuffer = function () {
    var body = this._body;
    if (body instanceof ArrayBuffer) return Promise.resolve(body);
    // Uint8Array 등은 정확한 구간만 복사한다
    if (body && typeof body.byteLength === "number" && body.buffer) {
      return Promise.resolve(body.buffer.slice(body.byteOffset, body.byteOffset + body.byteLength));
    }
    return Promise.resolve(new ArrayBuffer(0));
  };
  ResponseStub.prototype.json = function () {
    return this.text().then(function (raw) {
      return JSON.parse(raw);
    });
  };
  ResponseStub.redirect = function (url, status) {
    var response = new ResponseStub(null);
    response.url = String(url);
    response.status = status || 302;
    response.ok = false;
    response.redirected = true;
    return response;
  };
  ResponseStub.error = function () {
    var response = new ResponseStub(null);
    response.status = 0;
    response.ok = false;
    return response;
  };
  root.Response = ResponseStub;

  /* --- Cache API --- */
  var stores = {};

  function cacheStore(name) {
    return stores[name] || (stores[name] = {});
  }

  function cacheKeyName(key) {
    return String((key && key.url) || key || "");
  }

  function makeCache(name) {
    var store = cacheStore(name);
    return {
      put: function (key, response) {
        store[cacheKeyName(key)] = response;
        return Promise.resolve();
      },
      match: function (key) {
        return Promise.resolve(store[cacheKeyName(key)]);
      },
      delete: function (key) {
        var name2 = cacheKeyName(key);
        var had = Object.prototype.hasOwnProperty.call(store, name2);
        delete store[name2];
        return Promise.resolve(had);
      },
      keys: function () {
        return Promise.resolve(
          Object.keys(store).map(function (key) {
            return { url: key };
          })
        );
      },
      addAll: function () {
        return Promise.resolve();
      },
    };
  }

  root.caches = {
    open: function (name) {
      return Promise.resolve(makeCache(name));
    },
    delete: function (name) {
      delete stores[name];
      return Promise.resolve(true);
    },
    keys: function () {
      return Promise.resolve(Object.keys(stores));
    },
    match: function () {
      return Promise.resolve(undefined);
    },
  };

  /* --- 서비스 워커 전역 --- */
  root.location = {
    href: "https://example.test/call-log-maker/sw.js",
    origin: "https://example.test",
  };
  root.registration = { scope: "https://example.test/call-log-maker/" };
  root.clients = { claim: function () { return Promise.resolve(); } };
  root.skipWaiting = function () { return Promise.resolve(); };
  root.fetch = function () {
    return Promise.reject(new Error("네트워크는 이 테스트에서 쓰지 않습니다"));
  };

  var handlers = {};
  root.addEventListener = function (name, handler) {
    (handlers[name] = handlers[name] || []).push(handler);
  };

  root.__sw = {
    stores: stores,
    handlerNames: function () {
      return Object.keys(handlers).sort();
    },
    fire: function (name, event) {
      (handlers[name] || []).forEach(function (handler) {
        handler(event);
      });
    },
    cached: function (cacheName, key) {
      return cacheStore(cacheName)[key] || null;
    },
    cacheKeys: function (cacheName) {
      return Object.keys(cacheStore(cacheName)).sort();
    },
    reset: function () {
      Object.keys(stores).forEach(function (name) {
        delete stores[name];
      });
    },
  };
})(typeof globalThis !== "undefined" ? globalThis : this);
