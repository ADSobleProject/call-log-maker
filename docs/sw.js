/* 통화록 변환기 · 서비스 워커
   네트워크 우선(항상 최신 파일), 오프라인일 때만 캐시로 동작합니다.
   통화 내용은 브라우저 안에서만 처리되고, 이 워커는 파일을 밖으로 보내지 않습니다.

   안드로이드 공유 메뉴(공유 → 통화록 변환기)로 들어온 POST ./share-target 은
   여기서 가로채 formData 를 읽고, 공유받은 내용을 잠깐 Cache API 에 담아 둔 뒤
   ./?shared=1 로 되돌려 보냅니다(303). 화면(app.js)이 그 내용을 꺼내 바로 변환합니다.
   담아 둔 내용은 앱이 한 번 읽으면 지웁니다. */
var CACHE = 'call-log-maker-v2';

/* 공유받은 내용을 잠깐 두는 임시 캐시 (읽은 뒤 app.js 가 지운다) */
var SHARE_CACHE = 'call-log-maker-share';
var SHARE_META_PATH = './__shared.json';
var SHARE_FILE_PATH = './__shared.bin';

var SHELL = [
  './',
  './index.html',
  './manifest.json',
  './assets/app.css?v=4',
  './assets/app.js?v=4',
  './assets/lib/util.js?v=4',
  './assets/lib/filenames.js?v=4',
  './assets/lib/parsers.js?v=4',
  './assets/lib/analyze.js?v=4',
  './assets/lib/render.js?v=4',
  './assets/lib/docx.js?v=4',
  './assets/lib/build.js?v=4',
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
    return Promise.all(keys.filter(function (k) { return k !== CACHE && k !== SHARE_CACHE; }).map(function (k) {
      return caches.delete(k);
    }));
  }).then(function () { return self.clients.claim(); }));
});

/* ---------------------------------------------------------------- 공유 받기 */
function appUrl(path) {
  var base = (self.registration && self.registration.scope) || self.location.href;
  try {
    return new URL(path, base).href;
  } catch (err) {
    return path;
  }
}

function isShareTarget(href) {
  var clean = String(href || '').split('?')[0].split('#')[0];
  return clean === appUrl('./share-target');
}

function field(form, name) {
  try {
    if (!form || !form.get) return '';
    var value = form.get(name);
    return value == null ? '' : String(value);
  } catch (err) {
    return '';
  }
}

/* 공유된 파일 목록에서 실제 파일 하나를 고른다 (없으면 null) */
function pickFile(form) {
  var files = [];
  try {
    if (form.getAll) files = form.getAll('files') || [];
    else if (form.get && form.get('files')) files = [form.get('files')];
  } catch (err) {
    files = [];
  }
  for (var i = 0; i < files.length; i++) {
    var file = files[i];
    if (file && typeof file === 'object' && (file.size || file.name)) return file;
  }
  return null;
}

/* 음성·영상 녹음 파일 — 브라우저에서 글자로 옮길 수 없으므로 안내만 한다 */
function isAudioFile(file) {
  var name = String((file && file.name) || '').toLowerCase();
  var type = String((file && file.type) || '').toLowerCase();
  if (type.indexOf('audio/') === 0) return true;
  if (/^(video|application)\/(mp4|3gpp|quicktime|x-m4a)/.test(type)) return true;
  return /\.(m4a|m4b|mp3|wav|ogg|oga|opus|flac|aac|amr|wma|3gp|mp4)$/.test(name);
}

function noop() {}

function storeShared(meta, bytes) {
  return caches.open(SHARE_CACHE).then(function (cache) {
    var metaUrl = appUrl(SHARE_META_PATH);
    var fileUrl = appUrl(SHARE_FILE_PATH);
    // 이전 공유가 남아 있으면 먼저 지운다 (파일이 없는 공유에 옛 파일이 섞이지 않게)
    return Promise.resolve(cache.delete(fileUrl)).catch(noop).then(function () {
      if (!bytes) return null;
      return cache.put(fileUrl, new Response(bytes, {
        headers: { 'Content-Type': 'application/octet-stream' }
      }));
    }).then(function () {
      return cache.put(metaUrl, new Response(JSON.stringify(meta), {
        headers: { 'Content-Type': 'application/json; charset=utf-8' }
      }));
    });
  });
}

function handleShareTarget(req) {
  var reading;
  try {
    reading = req.formData();
  } catch (err) {
    reading = Promise.reject(err);
  }
  if (!reading || typeof reading.then !== 'function') reading = Promise.reject(new Error('no formData'));

  return reading.then(function (form) {
    var meta = {
      sharedAt: Date.now(),
      title: field(form, 'title'),
      text: field(form, 'text'),
      url: field(form, 'url'),
      fileName: '',
      fileType: '',
      fileSize: 0,
      modifiedAt: 0,
      isAudio: false,
      error: ''
    };
    var file = pickFile(form);
    if (!file) return { meta: meta, bytes: null };

    meta.fileName = String(file.name || '');
    meta.fileType = String(file.type || '');
    meta.fileSize = Number(file.size || 0);
    meta.modifiedAt = Number(file.lastModified || 0);

    if (isAudioFile(file)) {
      // 음성 파일 바이트는 담지 않는다 — 화면에서 안내만 띄운다
      meta.isAudio = true;
      return { meta: meta, bytes: null };
    }

    return file.arrayBuffer().then(function (buffer) {
      return { meta: meta, bytes: buffer };
    }, function () {
      meta.error = 'unreadable';
      return { meta: meta, bytes: null };
    });
  }).then(function (result) {
    return storeShared(result.meta, result.bytes).catch(noop);
  }).then(function () {
    return Response.redirect(appUrl('./?shared=1'), 303);
  }).catch(function () {
    // 읽지 못해도 앱으로는 돌려보낸다 (화면이 안내 문구를 띄운다)
    return Response.redirect(appUrl('./?shared=1'), 303);
  });
}

/* ---------------------------------------------------------------- 요청 처리 */
self.addEventListener('fetch', function (e) {
  var req = e.request;

  if (req.method === 'POST') {
    if (isShareTarget(req.url)) e.respondWith(handleShareTarget(req));
    return; // 공유 지점이 아닌 POST 는 건드리지 않는다
  }
  if (req.method !== 'GET') return;

  var url = new URL(req.url);
  if (url.origin !== self.location.origin) return; // 바깥 자원은 건드리지 않습니다

  e.respondWith(
    fetch(req).then(function (res) {
      if (res && res.ok && url.search.indexOf('shared=') < 0) {
        // 공유 복귀 페이지(?shared=1)는 캐시에 남기지 않는다
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
