"""모바일 웹앱(docs/) 의 JS 라이브러리 테스트.

- `docs/assets/lib/*.js` 를 quickjs(작은 JS 엔진)로 실제 실행해 파서·포매터·OOXML 을 검증한다.
- PC 버전(Python)과 **같은 입력에 같은 Markdown** 이 나오는지 비교한다.
- 브라우저에서 만든 `.docx` 바이너리를 zipfile·python-docx 로 열어 유효한지 확인한다.
- app.js 는 가짜 DOM 위에서 돌려 화면 코드가 값을 제대로 채우는지 본다.

quickjs 는 선택 의존성이라 없으면 이 파일의 테스트는 건너뛴다:
    pip install quickjs
"""
from __future__ import annotations

import io
import json
import re
import unittest
import zipfile
from datetime import datetime
from pathlib import Path

try:  # 선택 의존성
    import quickjs
except ImportError:  # pragma: no cover - 설치 안 한 PC
    quickjs = None

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
LIB_DIR = DOCS / "assets" / "lib"
LIB_FILES = ["util.js", "filenames.js", "parsers.js", "analyze.js", "render.js", "docx.js", "build.js"]
NOW = datetime(2026, 11, 17, 21, 5, 0)
SAMPLE_FILES = [
    "통화 녹음 김지훈_261117_210000.txt",
    "클로바노트_예시.txt",
    "일반대화_예시.txt",
]
HEADINGS = ["📋 기본 정보", "🔑 키워드", "📌 핵심 요약", "💰 금액·일정", "✅ 후속 할 일", "💬 전체 대화 기록"]


def _context():
    ctx = quickjs.Context()
    for name in LIB_FILES:
        path = LIB_DIR / name
        if not path.exists():  # pragma: no cover - 소스가 없으면 테스트 의미 없음
            raise unittest.SkipTest(f"{path} 가 없습니다")
        ctx.eval(path.read_text(encoding="utf-8"))
    return ctx


def _json_value(ctx, expression):
    return json.loads(ctx.eval(f"JSON.stringify({expression})"))


def _run_with_input(ctx, body, payload):
    """payload 를 __IN__ 전역으로 넣고 body 를 실행한다."""
    # U+2028/2029 는 JS 문자열 리터럴에서 줄바꿈으로 읽히므로 미리 바꾼다
    data = (
        json.dumps(payload, ensure_ascii=False)
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )
    ctx.eval("var __IN__ = " + data + ";\n" + body)


def _python_document(path):
    from calllog.config import Config
    from calllog.pipeline import Processor

    config = Config.load(root=ROOT)
    processor = Processor(config, now=lambda: NOW)
    return processor._build_document(path)


def _js_build_call(file_name, text, variable="__doc"):
    """PC 버전과 같은 조건으로 JS 문서를 만들고 변수에 담는다."""
    return (
        f"var {variable} = CallLog.buildDocument({{ text: __IN__.text, fileName: __IN__.fileName,"
        " now: new Date(__IN__.now[0], __IN__.now[1] - 1, __IN__.now[2], __IN__.now[3], __IN__.now[4], 0) });"
    )


def _payload(text, file_name):
    return {
        "text": text,
        "fileName": file_name,
        "now": [NOW.year, NOW.month, NOW.day, NOW.hour, NOW.minute],
    }


@unittest.skipUnless(quickjs is not None, "웹앱 JS 테스트에는 quickjs 가 필요합니다 (pip install quickjs)")
class WebAppTest(unittest.TestCase):
    def setUp(self):
        self.ctx = _context()

    # ------------------------------------------------------------ 구성
    def test_sources_present(self):
        """index.html 이 참조하는 스크립트·스타일이 모두 있고, 바깥 CDN 을 쓰지 않는다."""
        html = (DOCS / "index.html").read_text(encoding="utf-8")

        for name in LIB_FILES + ["app.js"]:
            self.assertIn(name, html, f"index.html 에 {name} 연결 없음")

        scripts = re.findall(r'<script[^>]+src="([^"]+)"', html)
        styles = re.findall(r'<link[^>]+rel="stylesheet"[^>]+href="([^"]+)"', html)
        self.assertTrue(scripts, "스크립트 연결이 없습니다")
        versions = set()
        for ref in scripts + styles:
            self.assertFalse(
                ref.startswith(("http://", "https://", "//")),
                f"바깥 자원을 쓰면 오프라인에서 깨집니다: {ref}",
            )
            # 캐시를 비우려고 붙인 ?v=2 는 파일 경로가 아니다
            path = ref.split("?")[0].split("#")[0]
            self.assertTrue((DOCS / path).exists(), f"연결된 파일이 없습니다: {ref}")
            self.assertFalse(path.endswith(".mjs"), "file:// 로 열 때 모듈 스크립트는 막힙니다")
            if "?" in ref:
                versions.add(ref.split("?", 1)[1])
        self.assertLessEqual(len(versions), 1, f"자원마다 캐시 버전이 다릅니다: {sorted(versions)}")

        self.assertNotIn('type="module"', html, "모듈 스크립트는 file:// 에서 동작하지 않습니다")
        self.assertIn('id="text"', html)
        self.assertIn('id="title"', html)

    def test_app_ids_exist_in_page(self):
        """app.js 가 찾는 id 가 모두 index.html 에 있어야 한다 (오타로 조용히 죽지 않게)."""
        app_js = (DOCS / "assets" / "app.js").read_text(encoding="utf-8")
        html = (DOCS / "index.html").read_text(encoding="utf-8")
        ids = set(re.findall(r'getElementById\("([^"]+)"\)', app_js))
        self.assertTrue(ids)
        for element_id in sorted(ids):
            self.assertIn(f'id="{element_id}"', html, f"index.html 에 #{element_id} 가 없습니다")

    # ------------------------------------------------------------ JS 테스트 모음
    def test_js_suite(self):
        """브라우저 없이 돌리는 JS 테스트 모음이 모두 통과해야 한다."""
        self.ctx.eval((ROOT / "tests" / "web" / "run_js_tests.js").read_text(encoding="utf-8"))
        result = _json_value(self.ctx, "__jsTestResult")
        self.assertEqual(result["fail"], 0, result["message"])
        self.assertGreaterEqual(result["pass"], 100, result["message"])

    def test_app_smoke(self):
        """가짜 DOM 위에서 app.js 를 돌려 화면 코드가 제대로 값을 채우는지 본다."""
        self.ctx.eval((ROOT / "tests" / "web" / "dom_stub.js").read_text(encoding="utf-8"))
        self.ctx.eval((DOCS / "assets" / "app.js").read_text(encoding="utf-8"))
        self.ctx.eval((ROOT / "tests" / "web" / "app_smoke.js").read_text(encoding="utf-8"))
        result = _json_value(self.ctx, "__appSmokeResult")
        self.assertEqual(result["fail"], 0, result["message"])

    # ------------------------------------------------------------ PC 버전과 같아야 함
    def test_markdown_matches_pc_version(self):
        """PC 버전과 같은 입력 → 같은 통화록(Markdown)이 나와야 한다."""
        import difflib

        from calllog import render

        for name in SAMPLE_FILES:
            with self.subTest(sample=name):
                path = ROOT / "samples" / name
                expected_doc = _python_document(path)
                expected = render.to_markdown(expected_doc)

                _run_with_input(
                    self.ctx,
                    _js_build_call(name, path.read_text(encoding="utf-8")) + "__md = CallLog.render.toMarkdown(__doc);",
                    _payload(path.read_text(encoding="utf-8"), name),
                )
                actual = self.ctx.eval("__md")

                if actual != expected:
                    diff = "\n".join(
                        difflib.unified_diff(
                            expected.splitlines(),
                            actual.splitlines(),
                            "PC 버전",
                            "웹앱",
                            lineterm="",
                            n=2,
                        )
                    )
                    self.fail(f"{name}: PC 버전과 통화록이 다릅니다\n{diff}")
                self.assertTrue(actual.strip().startswith("# 📞 통화록 - "))

    def test_filename_parity_with_python(self):
        """파일명 해석은 PC 버전(filenames.py)과 결과가 같아야 한다."""
        from calllog.filenames import parse_filename

        names = [
            "통화 녹음 김지훈_261117_210000.txt",
            "통화녹음_01012345678_20231117_210000.txt",
            "녹음_20261117_1430.txt",
            "2026-11-17 14.30.txt",
            "통화 녹음 2026. 11. 17. 오후 9:00.txt",
            "2026년 11월 17일 오후 9시 30분.txt",
            "KakaoTalk_Audio_20261117_143000.txt",
            "회의 2026-11-17 14.30.txt",
            "그냥이름.txt",
        ]
        for name in names:
            with self.subTest(name=name):
                _run_with_input(
                    self.ctx,
                    "var __info = CallLog.filenames.parseFilename(__IN__.name);",
                    {"name": name},
                )
                actual = _json_value(
                    self.ctx,
                    "({ title: __info.title, when: __info.when ? __info.when.toISOString() : null })",
                )
                expected = parse_filename(name)
                self.assertEqual(actual["title"], expected.title, f"제목이 다릅니다: {name}")
                if expected.when is None:
                    self.assertIsNone(actual["when"], f"일시가 다릅니다: {name}")
                else:
                    # toISOString 은 UTC 기준이라 로컬 시각으로 되돌려 비교한다
                    stamp = datetime.fromisoformat(actual["when"].replace("Z", "+00:00")).astimezone()
                    self.assertEqual(
                        (stamp.year, stamp.month, stamp.day, stamp.hour, stamp.minute),
                        (
                            expected.when.year,
                            expected.when.month,
                            expected.when.day,
                            expected.when.hour,
                            expected.when.minute,
                        ),
                        f"일시가 다릅니다: {name}",
                    )

    # ------------------------------------------------------------ DOCX
    def _js_docx_bytes(self, text, file_name=None):
        body = _js_build_call(file_name or "", text) + "CallLog.util.toHex(CallLog.docx.build(__doc));"
        _run_with_input(self.ctx, body, _payload(text, file_name or ""))
        return bytes.fromhex(self.ctx.eval("CallLog.util.toHex(CallLog.docx.build(__doc))"))

    def test_docx_is_valid_ooxml(self):
        """브라우저에서 만든 .docx 가 실제로 열리는 파일인지 확인한다."""
        from docx import Document
        from xml.etree import ElementTree

        from calllog import render

        name = SAMPLE_FILES[0]
        path = ROOT / "samples" / name
        data = self._js_docx_bytes(path.read_text(encoding="utf-8"), name)

        self.assertEqual(data[:2], b"PK", "ZIP 시그니처가 없습니다")
        self.assertGreater(len(data), 3000)

        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            self.assertIsNone(archive.testzip(), "ZIP 안의 파일이 손상되었습니다")
            names = set(archive.namelist())
            for required in [
                "[Content_Types].xml",
                "_rels/.rels",
                "word/document.xml",
                "word/styles.xml",
                "word/_rels/document.xml.rels",
                "docProps/core.xml",
                "docProps/app.xml",
            ]:
                self.assertIn(required, names, f"{required} 가 없습니다 (실제: {sorted(names)})")

            document_xml = archive.read("word/document.xml").decode("utf-8")
            self.assertTrue(document_xml.startswith("<?xml"))
            self.assertIn("<w:document", document_xml)
            self.assertIn("</w:document>", document_xml)
            self.assertIn("통화록 - 김지훈 (2026-11-17 21:00)", document_xml)
            # XML 로 읽히는지 (깨진 태그가 있으면 여기서 실패한다)
            ElementTree.fromstring(document_xml)

        # python-docx 로 열어 내용까지 확인 (Word 가 읽는 경로와 같은 검사)
        docx_doc = Document(io.BytesIO(data))
        paragraphs = [p.text for p in docx_doc.paragraphs]
        self.assertEqual(paragraphs[0], "📞 통화록 - 김지훈 (2026-11-17 21:00)")
        self.assertIn("이미 텍스트로 변환된 기록을 정리한 통화록입니다.", paragraphs)

        headings = [
            text
            for text in paragraphs
            if text in {"📋 기본 정보", "🔑 주요 키워드", "📌 핵심 요약", "💰 금액·일정", "✅ 후속 할 일", "💬 전체 대화 기록"}
        ]
        self.assertEqual(
            headings,
            ["📋 기본 정보", "🔑 주요 키워드", "📌 핵심 요약", "💰 금액·일정", "✅ 후속 할 일", "💬 전체 대화 기록"],
        )

        expected_doc = _python_document(path)
        for segment in expected_doc.segments:
            self.assertIn(segment.text, paragraphs, f"본문이 빠졌습니다: {segment.text[:30]}")

        # 기본 정보 표: PC 버전과 같은 항목·값
        self.assertEqual(len(docx_doc.tables), 1)
        expected_rows = render._info_rows(expected_doc)
        actual_rows = [(row.cells[0].text, row.cells[1].text) for row in docx_doc.tables[0].rows]
        self.assertEqual(actual_rows, [(str(key), str(value)) for key, value in expected_rows])

    def test_docx_survives_odd_input(self):
        """제어문자·XML 특수문자가 섞여도 열리는 파일이 나와야 한다."""
        from docx import Document

        data = self._js_docx_bytes('화자 1: A&B <태그> "인용" \u0007\u0000 끝\n00:05 화자 2: 두 번째 줄')

        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            self.assertIsNone(archive.testzip())
            xml_text = archive.read("word/document.xml").decode("utf-8")
        self.assertIn("A&amp;B &lt;태그&gt;", xml_text)
        self.assertNotIn("\u0007", xml_text)

        joined = "\n".join(p.text for p in Document(io.BytesIO(data)).paragraphs)
        self.assertIn("A&B <태그>", joined)


if __name__ == "__main__":
    unittest.main()
