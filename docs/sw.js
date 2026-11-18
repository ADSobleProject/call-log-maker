/* 통화록 변환기 · 서비스 워커
   네트워크 우선(항상 최신 파일), 오프라인일 때만 캐시로 동작합니다.
   통화 내용은 브라우저 안에서만 처리되고, 이 워커는 파일을 밖으로 보내지 않습니다. */
var CACHE = 'call-log-maker-v1';
var SHELL = [
  './',
  './index.html',
  './manifest.json',
  './assets/app.css?v=3',
  './assets/app.js?v=3',
  './assets/lib/util.js?v=3',
  './assets/lib/filenames.js?v=3',
  './assets/lib/parsers.js?v=3',
  './assets/lib/analyze.js?v=3',
  './assets/lib/render.js?v=3',
  './assets/lib/docx.js?v=3',
  './assets/lib/build.js?v=3',
  './assets/sample.txt',
  './icons/icon.svg',
  './icons/icon-192.png',
  './icons/icon-512.png'
];

self.addEventListener('install', function (e) {
  e.waitUntil(caches.open(CACHE).then(function (c) {
    return c.addAll(SHELL);
  }).then(function () { return self.skipWaiting(); }));
});

self.addEventListener('activate', function (e) {
  e.waitUntil(caches.keys().then(function (keys) {
    return Promise.all(keys.filter(function (k) { return k !== CACHE; }).map(function (k) {
      return caches.delete(k);
    }));
  }).then(function () { return self.clients.claim(); }));
});

self.addEventListener('fetch', function (e) {
  var req = e.request;
  if (req.method !== 'GET') return;
  var url = new URL(req.url);
  if (url.origin !== self.location.origin) return; // 바깥 자원은 건드리지 않습니다

  e.respondWith(
    fetch(req).then(function (res) {
      if (res && res.ok) {
        var copy = res.clone();
        caches.open(CACHE).then(function (c) { c.put(req, copy); }).catch(function () {});
      }
      return res;
    }).catch(function () {
      return caches.match(req).then(function (hit) {
        if (hit) return hit;
        // 페이지 이동이면 앱 셸로, 나머지는 그대로 실패시킵니다
        if (req.mode === 'navigate') return caches.match('./index.html');
        return Response.error();
      });
    })
  );
});
