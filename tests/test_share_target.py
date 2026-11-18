"""안드로이드 공유 메뉴(share_target)로 통화록 변환기에 .txt·텍스트 넘기기 검사.

휴대폰에서 "공유 → 통화록 변환기"를 누르면 크롬이 매니페스트의 share_target 대로
`POST ./share-target`(multipart/form-data)을 보낸다. 이 요청은 서비스 워커가
가로채 임시 캐시에 담아 두고 `./?shared=1` 로 되돌려 보내야 하고, 화면(app.js)이
그 내용을 꺼내 통화록을 바로 만들어야 한다.

여기서 보는 것 (브라우저 없이 확인 가능한 범위):

- `docs/manifest.json` 의 share_target 스키마 (action·method·enctype·params·accept)
- `docs/sw.js` 가 POST ./share-target 을 가로채 파일/텍스트를 담고 303 으로 되돌리는지
  (음성 파일은 바이트를 담지 않고 isAudio 로만 알리는지 · 남은 임시 캐시가 지워지는지)
- `docs/assets/app.js` 가 `?shared=1` 로 열렸을 때 입력창·미리보기를 채우고
  임시 캐시를 지우며 주소를 깔끔히 되돌리는지 · 음성 파일에는 안내를 띄우는지

sw.js·app.js 는 quickjs(작은 JS 엔진)로 실제 실행한다. quickjs 가 없으면 그 부분은 건너뛴다:
    pip install quickjs
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

try:  # 선택 의존성
    import quickjs
except ImportError:  # pragma: no cover - 설치 안 한 PC
    quickjs = None

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
WEB = ROOT / "tests" / "web"
LIB_FILES = ["util.js", "filenames.js", "parsers.js", "analyze.js", "render.js", "docx.js", "build.js"]

SCOPE = "https://example.test/call-log-maker/"
META_KEY = SCOPE + "__shared.json"
FILE_KEY = SCOPE + "__shared.bin"
SHARE_URL = SCOPE + "share-target"
REDIRECT_URL = SCOPE + "?shared=1"

SAMPLE_TEXT = (
    "00:00\n화자 1\n여보세요, JFC 마케팅팀 김진혁입니다.\n\n"
    "00:05 화자 2: 네, 소블 매거진 김지훈입니다. 내일 오전까지 발주서 보내 주세요.\n"
)
SAMPLE_NAME = "통화 녹음 김지훈_261117_210000.txt"
UTF16_TEXT = (
    "AI 음성 인식\n2026. 11. 17. 오후 2:31\n길이 00:41\n\n"
    "화자 1 (00:01)\n네, 안녕하세요. JFC 마케팅팀 김진혁입니다.\n\n"
    "화자 2 (00:14)\n네 안녕하세요, 박동근입니다."
)
UTF16_NAME = "통화 녹음 박동근_261117_143113_original.txt"


def _drain(ctx, limit: int = 500) -> None:
    """quickjs 의 마이크로태스크(Promise)를 끝까지 돌린다."""
    for _ in range(limit):
        if not ctx.execute_pending_job():
            return
    raise AssertionError("프로미스가 끝나지 않았습니다")


def _utf16le(text: str) -> bytes:
    return b"\xff\xfe" + text.encode("utf-16-le")


def _hex(data: bytes) -> str:
    return data.hex()


class ManifestShareTargetTest(unittest.TestCase):
    """매니페스트에 share_target 이 계약대로 적혀 있는지."""

    def setUp(self):
        self.manifest = json.loads((DOCS / "manifest.json").read_text(encoding="utf-8"))

    def test_share_target_declared(self):
        share = self.manifest.get("share_target")
        self.assertIsNotNone(share, "manifest.json 에 share_target 이 없습니다")
        self.assertEqual(share["action"], "./share-target")
        self.assertEqual(share["method"], "POST", "파일을 받으려면 POST 여야 합니다")
        self.assertEqual(share["enctype"], "multipart/form-data")

    def test_action_is_inside_scope(self):
        share = self.manifest["share_target"]
        action = share["action"]
        self.assertFalse(
            action.startswith(("http://", "https://", "//")),
            f"action 은 앱과 같은 출처의 상대 경로여야 합니다: {action}",
        )
        self.assertTrue(action.startswith("./"), f"action 은 scope 안이어야 합니다: {action}")
        self.assertEqual(self.manifest["scope"], "./", "share_target action 은 scope 안에 있어야 가로챌 수 있습니다")

    def test_params_title_text_url(self):
        params = self.manifest["share_target"]["params"]
        self.assertEqual(params["title"], "title")
        self.assertEqual(params["text"], "text")
        self.assertEqual(params["url"], "url")

    def test_params_files(self):
        files = self.manifest["share_target"]["params"]["files"]
        self.assertIsInstance(files, list)
        self.assertEqual(len(files), 1, "files 는 하나의 항목이어야 합니다")
        entry = files[0]
        self.assertEqual(entry["name"], "files")
        self.assertIsInstance(entry["accept"], list)
        for needed in ("text/plain", ".txt", "audio/*", ".m4a"):
            self.assertIn(needed, entry["accept"], f"accept 에 {needed} 가 없습니다")

    def test_page_has_notice_and_share_hint(self):
        html = (DOCS / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="notice"', html, "공유 안내를 띄울 자리(#notice)가 없습니다")
        self.assertIn("공유 → 통화록 변환기", html, "공유 메뉴로 받는 방법 안내가 없습니다")
        self.assertIn("홈 화면에 앱으로 설치한 상태", html, "설치해야 공유 메뉴에 뜬다는 안내가 없습니다")

    def test_service_worker_cache_version_bumped(self):
        sw = (DOCS / "sw.js").read_text(encoding="utf-8")
        self.assertIn("var CACHE = 'call-log-maker-v2'", sw)
        self.assertIn("call-log-maker-share", sw, "공유 임시 캐시가 없습니다")


@unittest.skipUnless(quickjs is not None, "share_target 테스트에는 quickjs 가 필요합니다 (pip install quickjs)")
class ServiceWorkerShareTargetTest(unittest.TestCase):
    """sw.js 가 POST ./share-target 을 실제로 어떻게 처리하는지."""

    @classmethod
    def setUpClass(cls):
        ctx = quickjs.Context()
        ctx.set_memory_limit(64 * 1024 * 1024)
        ctx.eval((WEB / "sw_stub.js").read_text(encoding="utf-8"))
        ctx.eval((DOCS / "sw.js").read_text(encoding="utf-8"))
        payload = {
            "utf8Bytes": list(SAMPLE_TEXT.encode("utf-8")),
            "utf16Bytes": list(_utf16le(UTF16_TEXT)),
            "audioBytes": list(b"\x00\x00\x00\x20ftypM4A " + b"\x00" * 24),
            "sharedText": "김지훈: 내일 오전까지 발주서 보내 드릴게요.",
        }
        ctx.eval("var __IN__ = " + json.dumps(payload, ensure_ascii=False) + ";")
        ctx.eval((WEB / "sw_share.js").read_text(encoding="utf-8"))
        _drain(ctx)
        cls.ctx = ctx
        cls.results = json.loads(ctx.eval("JSON.stringify(__swResults)"))

    def test_handlers_registered(self):
        names = json.loads(self.ctx.eval("JSON.stringify(__sw.handlerNames())"))
        for hook in ("activate", "fetch", "install"):
            self.assertIn(hook, names)

    def test_share_target_redirects_to_app(self):
        for scenario in ("textFile", "textOnly", "audioFile", "utf16File"):
            with self.subTest(scenario=scenario):
                result = self.results[scenario]
                self.assertTrue(result["respondWithCalled"], f"{scenario}: 공유 요청을 가로채지 않았습니다")
                self.assertIsNone(result["error"], f"{scenario}: 처리 중 오류 — {result['error']}")
                self.assertEqual(result["url"], REDIRECT_URL, f"{scenario}: 되돌려 보낸 주소가 다릅니다")
                self.assertEqual(result["status"], 303, "303(See Other)로 보내야 POST 본문이 다시 전송되지 않습니다")

    def test_text_file_is_stored(self):
        result = self.results["textFile"]
        meta = result["meta"]
        self.assertIsNotNone(meta, "공유 메타가 캐시에 없습니다")
        self.assertFalse(meta["isAudio"])
        self.assertEqual(meta["fileName"], SAMPLE_NAME)
        self.assertEqual(meta["fileType"], "text/plain")
        self.assertEqual(meta["fileSize"], len(SAMPLE_TEXT.encode("utf-8")))
        self.assertEqual(result["fileHex"], _hex(SAMPLE_TEXT.encode("utf-8")), "파일 바이트가 그대로 담기지 않았습니다")

    def test_utf16le_file_bytes_are_kept(self):
        result = self.results["utf16File"]
        self.assertEqual(result["meta"]["fileName"], UTF16_NAME)
        self.assertEqual(result["fileHex"], _hex(_utf16le(UTF16_TEXT)))

    def test_shared_text_without_file(self):
        result = self.results["textOnly"]
        meta = result["meta"]
        self.assertIsNotNone(meta)
        self.assertEqual(meta["text"], "김지훈: 내일 오전까지 발주서 보내 드릴게요.")
        self.assertEqual(meta["fileName"], "")
        self.assertIsNone(result["fileHex"], "파일이 없는데 파일 바이트가 남았습니다")
        self.assertEqual(result["cacheKeys"], [META_KEY], "이전 공유 파일이 지워지지 않았습니다")

    def test_audio_file_is_not_stored(self):
        result = self.results["audioFile"]
        meta = result["meta"]
        self.assertIsNotNone(meta)
        self.assertTrue(meta["isAudio"], "음성 파일은 isAudio 로 알려야 합니다")
        self.assertEqual(meta["fileName"], "통화 녹음 김지훈_261117_210000.m4a")
        self.assertIsNone(result["fileHex"], "음성 파일 바이트는 담지 않아야 합니다(용량·의미 없음)")
        self.assertEqual(result["cacheKeys"], [META_KEY])

    def test_other_post_is_not_intercepted(self):
        result = self.results["otherPost"]
        self.assertFalse(result["respondWithCalled"], "공유 지점이 아닌 POST 는 건드리지 않아야 합니다")


@unittest.skipUnless(quickjs is not None, "share_target 테스트에는 quickjs 가 필요합니다 (pip install quickjs)")
class SharedPageTest(unittest.TestCase):
    """app.js 가 ?shared=1 로 열렸을 때 화면을 채우는지."""

    def _run(self, meta=None, file_bytes=None, relative_keys=True, search="?shared=1"):
        ctx = quickjs.Context()
        ctx.set_memory_limit(64 * 1024 * 1024)
        for name in LIB_FILES:
            ctx.eval((DOCS / "assets" / "lib" / name).read_text(encoding="utf-8"))
        ctx.eval((WEB / "dom_stub.js").read_text(encoding="utf-8"))

        seed = {
            "meta": meta,
            "bytes": list(file_bytes) if file_bytes is not None else None,
            "relative": relative_keys,
        }
        ctx.eval("var __SEED__ = " + json.dumps(seed, ensure_ascii=False) + ";")
        ctx.eval(
            """
            (function () {
              var base = __SEED__.relative ? "./" : "https://example.test/call-log-maker/";
              if (__SEED__.meta !== null) {
                __caches.seed("call-log-maker-share", base + "__shared.json", {
                  body: JSON.stringify(__SEED__.meta)
                });
              }
              if (__SEED__.bytes) {
                var bytes = new Uint8Array(__SEED__.bytes);
                __caches.seed("call-log-maker-share", base + "__shared.bin", { buffer: bytes.buffer });
              }
            })();
            """
        )
        ctx.eval(f"location.search = {json.dumps(search)};")
        ctx.eval((DOCS / "assets" / "app.js").read_text(encoding="utf-8"))
        _drain(ctx)
        ctx.eval((WEB / "app_share.js").read_text(encoding="utf-8"))
        _drain(ctx)
        return json.loads(ctx.eval("JSON.stringify(__appShare)"))

    # ------------------------------------------------------------ .txt 파일
    def test_text_file_fills_and_renders(self):
        state = self._run(
            meta={"fileName": SAMPLE_NAME, "fileType": "text/plain", "isAudio": False,
                  "modifiedAt": 1763384400000, "text": "", "title": ""},
            file_bytes=SAMPLE_TEXT.encode("utf-8"),
        )
        before = state["before"]
        self.assertEqual(before["text"], SAMPLE_TEXT, "공유받은 본문이 입력창에 들어가지 않았습니다")
        self.assertIn("📞 통화록 -", before["preview"])
        self.assertIn("김지훈", before["preview"], "파일명에서 상대방을 찾아 미리보기를 만들지 못했습니다")
        self.assertIn("소블 매거진 김지훈", before["preview"])
        self.assertEqual(before["title"].strip(), "김지훈", "파일명에서 상대방이 자동으로 채워져야 합니다")
        self.assertTrue(before["noticeHidden"], "성공했는데 경고 띠가 떠 있습니다")
        self.assertEqual(before["cacheKeys"], [], "읽은 공유 내용이 캐시에 남아 있습니다")
        self.assertEqual(before["replacedUrl"], "/call-log-maker/", "주소창의 ?shared=1 을 지우지 않았습니다")

    def test_utf16_file_is_decoded(self):
        state = self._run(
            meta={"fileName": UTF16_NAME, "fileType": "text/plain", "isAudio": False,
                  "modifiedAt": 0, "text": "", "title": ""},
            file_bytes=_utf16le(UTF16_TEXT),
        )
        before = state["before"]
        self.assertEqual(before["text"], UTF16_TEXT, "UTF-16LE 공유 파일이 깨졌습니다")
        self.assertNotIn("Tĭ", before["text"])
        self.assertIn("박동근", before["preview"])

    def test_shared_data_found_even_with_absolute_keys(self):
        """설치본 주소가 달라 캐시 키 모양이 어긋나도 찾아내야 한다."""
        state = self._run(
            meta={"fileName": SAMPLE_NAME, "fileType": "text/plain", "isAudio": False,
                  "modifiedAt": 0, "text": "", "title": ""},
            file_bytes=SAMPLE_TEXT.encode("utf-8"),
            relative_keys=False,
        )
        self.assertEqual(state["before"]["text"], SAMPLE_TEXT)
        self.assertEqual(state["before"]["cacheKeys"], [], "어긋난 키의 임시 캐시도 지워야 합니다")

    # ------------------------------------------------------------ 붙여넣은 글
    def test_shared_text_fills_textarea(self):
        shared = "김지훈: 내일 오전까지 발주서 보내 드릴게요.\n김진혁: 네, 확인하겠습니다."
        state = self._run(meta={"fileName": "", "isAudio": False, "text": shared, "title": ""})
        before = state["before"]
        self.assertEqual(before["text"], shared)
        self.assertIn("발주서", before["preview"])
        self.assertIn("📞 통화록 -", before["preview"])
        self.assertTrue(before["noticeHidden"])
        self.assertEqual(before["cacheKeys"], [])

    # ------------------------------------------------------------ 음성 파일
    def test_audio_file_shows_guidance(self):
        state = self._run(
            meta={"fileName": "통화 녹음 김지훈_261117_210000.m4a", "fileType": "audio/mp4",
                  "isAudio": True, "text": "", "title": ""},
            file_bytes=None,
        )
        before = state["before"]
        self.assertFalse(before["noticeHidden"], "음성 파일 안내가 뜨지 않았습니다")
        self.assertIn("음성 파일", before["noticeText"])
        self.assertIn(".txt", before["noticeText"], "텍스트로 변환해 공유하라는 안내가 없습니다")
        self.assertIn("PC 버전", before["noticeText"])
        self.assertEqual(before["text"], "", "음성 파일을 글자로 채우려 해서는 안 됩니다")
        self.assertEqual(before["cacheKeys"], [], "음성 파일 메타가 캐시에 남아 있습니다")
        self.assertTrue(
            state["afterClear"]["noticeHidden"], "지우기를 누르면 안내 띠가 사라져야 합니다"
        )

    # ------------------------------------------------------------ 평소 실행
    def test_normal_open_clears_leftover_share(self):
        """공유를 읽지 못한 채 남아 있어도, 평소에 앱을 열면 지운다."""
        state = self._run(
            meta={"fileName": SAMPLE_NAME, "isAudio": False, "text": "남아 있던 내용", "title": ""},
            file_bytes=SAMPLE_TEXT.encode("utf-8"),
            search="",
        )
        self.assertEqual(state["before"]["text"], "", "평소 실행에는 공유 내용을 채우지 않아야 합니다")
        self.assertEqual(state["before"]["cacheKeys"], [], "평소 실행 때 임시 캐시를 지워야 합니다")
        self.assertTrue(state["before"]["noticeHidden"])

    # ------------------------------------------------------------ 빈 공유
    def test_missing_share_data_shows_notice(self):
        state = self._run(meta=None)
        before = state["before"]
        self.assertFalse(before["noticeHidden"])
        self.assertIn("찾지 못했", before["noticeText"])
        self.assertEqual(before["text"], "")
        self.assertEqual(before["replacedUrl"], "/call-log-maker/")


class ShareTargetDocsTest(unittest.TestCase):
    """README·화면이 설치 조건과 한계를 안내하는지."""

    def test_readme_explains_share_menu(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("공유 → 통화록 변환기", readme)
        self.assertIn("share_target", readme)
        self.assertIn("홈 화면에 앱으로 설치", readme)
        self.assertIn(".m4a", readme)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
