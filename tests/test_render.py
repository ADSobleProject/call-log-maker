import unittest
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from docx import Document

from calllog import render
from calllog.models import ActionItem, CallDocument
from calllog.parsers import Segment


def sample_doc() -> CallDocument:
    return CallDocument(
        title="김지훈",
        when=datetime(2026, 11, 17, 21, 0),
        source_name="통화 녹음 김지훈_261117_210000.m4a",
        mode="음성→텍스트",
        engine="faster-whisper small",
        duration_sec=201,
        segments=[
            Segment(text="안녕하세요, 배너 인쇄 건으로 연락드렸습니다.", speaker="화자 1", start=0),
            Segment(text="네, 20일까지 납품 가능합니다.", speaker="화자 2", start=5),
        ],
        keywords=["시안", "납품", "계약금"],
        summary=["납기가 11월 20일까지 가능한지 확인했습니다."],
        actions=[ActionItem(text="발주서를 내일 오전까지 보내기", owner="화자 1", due="내일")],
        amounts=["350만 원"],
        dates=["11월 20일"],
        speakers=["화자 1", "화자 2"],
        created_at=datetime(2026, 11, 17, 21, 5),
    )


class MarkdownTest(unittest.TestCase):
    def setUp(self):
        self.md = render.to_markdown(sample_doc())

    def test_heading(self):
        self.assertIn("# 📞 통화록 - 김지훈 (2026-11-17 21:00)", self.md)

    def test_all_sections(self):
        for section in ("기본 정보", "주요 키워드", "핵심 요약", "금액·일정", "후속 할 일", "전체 대화 기록"):
            self.assertIn(section, self.md)

    def test_table_and_values(self):
        self.assertIn("| 일시 | 2026-11-17 (화) 21:00 |", self.md)
        self.assertIn("| 소요 시간 | 3분 21초 |", self.md)
        self.assertIn("| 변환 방식 | 음성→텍스트 (faster-whisper small) |", self.md)

    def test_checkbox(self):
        self.assertIn("- [ ] 발주서를 내일 오전까지 보내기", self.md)

    def test_transcript_with_time(self):
        self.assertIn("**화자 1** `00:00`", self.md)
        self.assertIn("**화자 2** `00:05`", self.md)

    def test_warning_section(self):
        doc = sample_doc()
        doc.warnings = ["일부 구간을 건너뛰었습니다."]
        self.assertIn("⚠️ 참고", render.to_markdown(doc))


class DocxTest(unittest.TestCase):
    def test_write_and_read_back(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "통화록.docx"
            render.write_docx(sample_doc(), path)
            self.assertTrue(path.exists())
            document = Document(str(path))
            text = "\n".join(p.text for p in document.paragraphs)
            self.assertIn("통화록 - 김지훈", text)
            self.assertIn("시안", text)
            self.assertIn("☐", text)
            self.assertIn("화자 1", text)
            self.assertEqual(len(document.tables), 1)
            table = document.tables[0]
            cells = [row.cells[1].text for row in table.rows]
            self.assertIn("김지훈", cells)
            self.assertIn("3분 21초", cells)

    def test_empty_transcript_does_not_crash(self):
        doc = sample_doc()
        doc.segments = []
        doc.summary = []
        doc.actions = []
        md = render.to_markdown(doc)
        self.assertIn("대화 내용이 없습니다", md)
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "빈.docx"
            render.write_docx(doc, path)
            self.assertTrue(path.exists())


if __name__ == "__main__":
    unittest.main()
