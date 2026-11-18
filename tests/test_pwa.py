"""모바일 웹앱(docs/) 의 PWA 구성 검사.

홈 화면에 추가(설치)가 되려면 매니페스트·아이콘·서비스 워커가 서로 맞아야 한다.
여기서는 브라우저 없이 확인할 수 있는 것만 본다:

- `docs/manifest.json` 이 유효한 JSON 이고 필수 항목(이름·시작 주소·표시 방식·색·아이콘)을 갖췄는지
- 매니페스트가 가리키는 아이콘 파일이 실제로 있고, 선언한 크기(size)와 PNG 헤더가 일치하는지
- `docs/index.html` 이 매니페스트·아이콘·서비스 워커를 제대로 연결했는지 (테마 색은 매니페스트와 같은지)
- `docs/sw.js` 가 캐시 이름·앱 셸 목록을 갖고, 셸에 적은 파일이 모두 존재하는지
"""

from __future__ import annotations

import json
import re
import struct
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
MANIFEST = DOCS / "manifest.json"
ICONS = DOCS / "icons"
CACHE_NAME = "call-log-maker-v2"


def _png_size(path: Path) -> tuple[int, int]:
    """PNG IHDR 에서 (width, height) 만 읽는다 — Pillow 없이 검사하려고."""
    data = path.read_bytes()[:24]
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise AssertionError(f"PNG 시그니처가 아닙니다: {path.name}")
    if data[12:16] != b"IHDR":
        raise AssertionError(f"IHDR 청크가 없습니다: {path.name}")
    return struct.unpack(">II", data[16:24])


class PwaTest(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.html = (DOCS / "index.html").read_text(encoding="utf-8")

    # ------------------------------------------------------------ 매니페스트
    def test_manifest_required_fields(self):
        m = self.manifest
        for key in ("name", "short_name", "start_url", "scope", "display",
                    "theme_color", "background_color", "icons"):
            self.assertIn(key, m, f"manifest.json 에 {key} 가 없습니다")

        self.assertEqual(m["name"], "통화록 변환기")
        self.assertEqual(m["short_name"], "통화록")
        self.assertEqual(m["start_url"], "./")
        self.assertEqual(m["scope"], "./")
        self.assertEqual(m["display"], "standalone")
        self.assertRegex(m["theme_color"], r"^#[0-9a-fA-F]{6}$")
        self.assertRegex(m["background_color"], r"^#[0-9a-fA-F]{6}$")
        self.assertLessEqual(len(m["short_name"]), 12, "홈 화면 이름이 너무 깁니다")

    def test_manifest_icons_match_files(self):
        icons = self.manifest["icons"]
        kinds = set()
        sizes = set()
        for icon in icons:
            src = icon["src"]
            self.assertNotRegex(src, r"^(https?:)?//", f"바깥 아이콘은 오프라인에서 깨집니다: {src}")
            path = DOCS / src.lstrip("./")
            self.assertTrue(path.exists(), f"매니페스트가 가리키는 아이콘이 없습니다: {src}")
            kinds.add(icon["type"])
            purpose = icon.get("purpose", "any")

            if icon["type"] == "image/svg+xml":
                self.assertEqual(icon["sizes"], "any")
                ET.parse(path)  # 깨진 SVG 면 여기서 실패
            elif icon["type"] == "image/png":
                declared = icon["sizes"]
                match = re.fullmatch(r"(\d+)x(\d+)", declared)
                self.assertIsNotNone(match, f"PNG 아이콘 크기 형식이 이상합니다: {declared}")
                self.assertEqual(_png_size(path), (int(match.group(1)), int(match.group(2))),
                                 f"{src} 의 실제 크기가 선언({declared})과 다릅니다")
                if purpose == "any":
                    sizes.add(declared)
            else:
                self.fail(f"지원하지 않는 아이콘 형식: {icon['type']} ({src})")

        self.assertIn("image/svg+xml", kinds, "벡터 아이콘(icon.svg)이 필요합니다")
        self.assertIn("image/png", kinds, "PNG 아이콘(192·512)이 필요합니다")
        self.assertTrue({"192x192", "512x512"} <= sizes, f"192·512 PNG 아이콘이 없습니다: {sorted(sizes)}")

    def test_icons_are_square_and_not_tiny(self):
        for path in ICONS.glob("*.png"):
            width, height = _png_size(path)
            self.assertEqual(width, height, f"{path.name} 이 정사각형이 아닙니다")
            self.assertGreaterEqual(width, 180, f"{path.name} 이 너무 작습니다")
            self.assertLess(path.stat().st_size, 200_000, f"{path.name} 이 너무 큽니다")

    def test_svg_icon_is_scalable(self):
        root = ET.parse(ICONS / "icon.svg").getroot()
        self.assertEqual(root.get("viewBox"), "0 0 512 512")
        self.assertTrue(len(root) > 3, "icon.svg 가 비어 있습니다")

    # ------------------------------------------------------------ 페이지 연결
    def test_index_links_manifest_and_icons(self):
        self.assertIn('rel="manifest"', self.html)
        self.assertIn('href="./manifest.json"', self.html)

        hrefs = re.findall(r'<link[^>]+rel="(?:icon|apple-touch-icon)"[^>]+href="([^"]+)"', self.html)
        self.assertTrue(hrefs, "index.html 에 아이콘 연결이 없습니다")
        for href in hrefs:
            self.assertNotRegex(href, r"^(https?:)?//", f"바깥 아이콘을 쓰면 오프라인에서 깨집니다: {href}")
            self.assertTrue((DOCS / href.lstrip("./")).exists(), f"연결된 아이콘이 없습니다: {href}")
        self.assertTrue(any(h.endswith(".svg") for h in hrefs), "SVG 아이콘 연결이 없습니다")
        self.assertTrue(any(h.endswith("192.png") for h in hrefs), "192 PNG 아이콘 연결이 없습니다")

    def test_index_meta_matches_manifest(self):
        match = re.search(r'<meta name="theme-color" content="([^"]+)"', self.html)
        self.assertIsNotNone(match, "theme-color 메타태그가 없습니다")
        self.assertEqual(match.group(1).lower(), self.manifest["theme_color"].lower(),
                         "주소창 색(theme-color)이 매니페스트와 다릅니다")
        self.assertIn('name="apple-mobile-web-app-capable" content="yes"', self.html)
        self.assertIn('rel="apple-touch-icon"', self.html)

    def test_index_registers_service_worker(self):
        flat = re.sub(r"\s+", " ", self.html)
        self.assertIn("serviceWorker", flat)
        self.assertIn("register('./sw.js')", flat)
        self.assertIn("'serviceWorker' in navigator", flat, "지원하지 않는 브라우저 보호가 없습니다")

    # ------------------------------------------------------------ 서비스 워커
    def test_service_worker_shell(self):
        sw = (DOCS / "sw.js").read_text(encoding="utf-8")
        self.assertIn(f"var CACHE = '{CACHE_NAME}'", sw)
        for hook in ("'install'", "'activate'", "'fetch'", "skipWaiting", "clients.claim"):
            self.assertIn(hook, sw, f"sw.js 에 {hook} 처리가 없습니다")

        shell_src = re.search(r"var SHELL = \[(.*?)\];", sw, re.S)
        self.assertIsNotNone(shell_src, "sw.js 에 캐시할 파일 목록(SHELL)이 없습니다")
        shell = re.findall(r"'([^']+)'", shell_src.group(1))
        self.assertTrue(shell)

        for ref in shell:
            path = ref.split("?")[0].split("#")[0].lstrip("./") or "index.html"
            self.assertTrue((DOCS / path).exists(), f"sw.js 셸에 적힌 파일이 없습니다: {ref}")

        for needed in ("index.html", "manifest.json", "app.js", "app.css",
                       "icons/icon-192.png", "icons/icon-512.png"):
            self.assertTrue(any(needed in ref for ref in shell), f"셸 캐시에 {needed} 가 없습니다")

    def test_service_worker_asset_versions_match_page(self):
        sw = (DOCS / "sw.js").read_text(encoding="utf-8")
        page_refs = re.findall(r'(?:href|src)="(assets/[^"]+)"', self.html)
        self.assertTrue(page_refs)
        shell = re.search(r"var SHELL = \[(.*?)\];", sw, re.S).group(1)
        for ref in page_refs:
            self.assertIn(f"./{ref}", shell, f"sw.js 셸 목록에 페이지 자원이 빠졌습니다: {ref}")

        versions = {ref.split("?")[1] for ref in page_refs if "?" in ref}
        self.assertEqual(versions, {"v=4"}, f"페이지 자원의 캐시 버전이 하나가 아닙니다: {sorted(versions)}")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
