/* app.js 가 공유(?shared=1)로 넘어온 내용을 제대로 채웠는지 관찰한 값을 모은다.
 *
 * 실행 순서: dom_stub.js → (공유 캐시 미리 담기) → docs/assets/app.js → 이 파일.
 * 판정은 tests/test_share_target.py 에서 한다.
 */
(function (root) {
  "use strict";

  var els = root.__dom.elements;

  var before = {
    text: els.text.value,
    title: els.title.value,
    date: els.date.value,
    time: els.time.value,
    fileHint: els["file-hint"].textContent,
    preview: els.preview.innerHTML,
    status: els.status.textContent,
    noticeHidden: els.notice.hidden !== false,
    noticeText: els.notice.textContent,
    noticeClass: els.notice.className,
    replacedUrl: root.__replacedUrl || null,
    cacheKeys: root.__caches.keys("call-log-maker-share"),
    copyDisabled: els.copy.disabled === true,
  };

  // 안내 띠가 떠 있을 때 "지우기"를 누르면 사라지는지
  els.clear.dispatch("click");
  root.__dom.flushTimers();

  root.__appShare = {
    before: before,
    afterClear: {
      text: els.text.value,
      noticeHidden: els.notice.hidden !== false,
      preview: els.preview.innerHTML,
    },
  };
})(typeof globalThis !== "undefined" ? globalThis : this);
