import unittest
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from calllog.parsers import (
    format_timestamp,
    parse_duration,
    parse_timestamp,
    parse_text,
    parse_text_file,
)

SAMPLES = Path(__file__).resolve().parent.parent / "samples"


class TimestampTest(unittest.TestCase):
    def test_mm_ss(self):
        self.assertEqual(parse_timestamp("00:05"), 5)
        self.assertEqual(parse_timestamp("[00:12.400]"), 12)
        self.assertEqual(parse_timestamp("02:03"), 123)

    def test_hh_mm_ss(self):
        self.assertEqual(parse_timestamp("1:02:03"), 3723)

    def test_format(self):
        self.assertEqual(format_timestamp(5), "00:05")
        self.assertEqual(format_timestamp(3723), "1:02:03")
        self.assertEqual(format_timestamp(None), "")

    def test_duration(self):
        self.assertEqual(parse_duration("03:21"), 201)
        self.assertEqual(parse_duration("3분 21초"), 201)
        self.assertEqual(parse_duration("1시간 2분"), 3720)
        self.assertIsNone(parse_duration("없음"))


class SamsungStyleTest(unittest.TestCase):
    def setUp(self):
        self.parsed = parse_text_file(SAMPLES / "통화 녹음 김지훈_261117_210000.txt")

    def test_header_metadata(self):
        self.assertEqual(self.parsed.when, datetime(2026, 11, 17, 21, 0))
        self.assertEqual(self.parsed.duration_sec, 201)

    def test_speakers_and_segments(self):
        self.assertEqual(self.parsed.speakers, ["화자 1", "화자 2"])
        self.assertGreaterEqual(len(self.parsed.segments), 10)
        first = self.parsed.segments[0]
        self.assertEqual(first.speaker, "화자 1")
        self.assertEqual(first.start, 0)
        self.assertIn("김진혁", first.text)
        # 헤더 줄이 대화 내용으로 새어 들어가면 안 된다
        self.assertNotIn("음성 녹음", self.parsed.full_text)
        self.assertNotIn("길이", self.parsed.full_text)

    def test_timestamp_seconds(self):
        starts = [s.start for s in self.parsed.segments if s.start is not None]
        self.assertIn(5, starts)
        self.assertIn(12, starts)


class ClovaStyleTest(unittest.TestCase):
    def test_inline_timestamp_and_speaker(self):
        parsed = parse_text_file(SAMPLES / "클로바노트_예시.txt")
        self.assertEqual(parsed.title, "박서연 실장")
        self.assertEqual(parsed.when, datetime(2026, 11, 17, 14, 30))
        self.assertEqual(parsed.speakers, ["화자 1", "화자 2"])
        self.assertEqual(parsed.segments[0].start, 12)
        self.assertIn("김진혁", parsed.segments[0].text)


class PlainNameLabelTest(unittest.TestCase):
    def test_name_labels_and_meta(self):
        parsed = parse_text_file(SAMPLES / "일반대화_예시.txt")
        self.assertEqual(parsed.title, "주말 매장 점검 회의")
        self.assertEqual(parsed.when, datetime(2026, 11, 15, 10, 0))
        self.assertEqual(parsed.duration_sec, 220)
        self.assertEqual(parsed.speakers, ["김진혁", "이수민"])
        self.assertIn("매장 오픈", parsed.segments[0].text)


class ToleranceTest(unittest.TestCase):
    def test_plain_paragraphs_without_labels(self):
        raw = "오늘 통화 내용을 정리합니다.\n\n다음 주에 다시 연락드리기로 했습니다."
        parsed = parse_text(raw)
        self.assertEqual(len(parsed.segments), 2)
        self.assertEqual(parsed.speakers, [])

    def test_multi_line_utterance_is_joined(self):
        raw = "화자 1: 안녕하세요\n반갑습니다\n화자 2: 네 안녕하세요"
        parsed = parse_text(raw)
        self.assertEqual(len(parsed.segments), 2)
        self.assertEqual(parsed.segments[0].text, "안녕하세요 반갑습니다")

    def test_bracket_timestamp_and_label(self):
        raw = "[00:12] 참석자 1 - 그럼 내일 봬요."
        parsed = parse_text(raw)
        self.assertEqual(parsed.segments[0].speaker, "참석자 1")
        self.assertEqual(parsed.segments[0].start, 12)
        self.assertEqual(parsed.segments[0].text, "그럼 내일 봬요.")

    def test_empty_file_warns(self):
        parsed = parse_text("   \n\n ")
        self.assertEqual(parsed.segments, [])
        self.assertTrue(parsed.warnings)

    def test_cp949_file_is_readable(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "메모.txt"
            path.write_bytes("화자 1: 안녕하세요\n화자 2: 네".encode("cp949"))
            parsed = parse_text_file(path)
            self.assertEqual(len(parsed.segments), 2)


SAMSUNG_UTF16_TEXT = (
    "AI 음성 인식\n"
    "2026. 11. 17. 오후 2:31\n"
    "길이 00:41\n"
    "\n"
    "화자 1 (00:01)\n"
    "네, 안녕하세요. JFC 마케팅팀 김진혁입니다.\n"
    "\n"
    "화자 2 (00:14)\n"
    "네 안녕하세요, 박동근입니다. 잘 지내셨어요?\n"
    "\n"
    "화자 1 (00:17)\n"
    "네 덕분에 잘 지냅니다. 오늘 통화는 매장 오픈 건으로 드렸습니다.\n"
)


class EncodingTest(unittest.TestCase):
    """삼성 통화녹음이 내보내는 UTF-16 .txt 를 제대로 읽는지."""

    def _parse_bytes(self, data: bytes) -> "object":
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "통화 녹음 제이에프씨 박동근 부대표님_261117_143113_original.txt"
            path.write_bytes(data)
            return parse_text_file(path)

    def _assert_clean(self, parsed, where: str) -> None:
        self.assertEqual(parsed.speakers, ["화자 1", "화자 2"], where)
        self.assertEqual(len(parsed.segments), 3, where)
        self.assertEqual(parsed.segments[0].start, 1, where)
        self.assertIn("JFC 마케팅팀 김진혁입니다", parsed.segments[0].text, where)
        self.assertIn("박동근입니다", parsed.segments[1].text, where)
        self.assertEqual(parsed.duration_sec, 41, where)
        self.assertNotIn("\x00", parsed.full_text, where)
        self.assertNotIn("\ufeff", parsed.full_text, where)

    def test_utf16le_with_bom(self):
        self._assert_clean(
            self._parse_bytes(b"\xff\xfe" + SAMSUNG_UTF16_TEXT.encode("utf-16-le")),
            "UTF-16LE+BOM",
        )

    def test_utf16be_with_bom(self):
        self._assert_clean(
            self._parse_bytes(b"\xfe\xff" + SAMSUNG_UTF16_TEXT.encode("utf-16-be")),
            "UTF-16BE+BOM",
        )

    def test_utf16le_without_bom(self):
        self._assert_clean(self._parse_bytes(SAMSUNG_UTF16_TEXT.encode("utf-16-le")), "UTF-16LE")

    def test_utf16be_without_bom(self):
        self._assert_clean(self._parse_bytes(SAMSUNG_UTF16_TEXT.encode("utf-16-be")), "UTF-16BE")

    def test_utf8_and_utf8_bom_still_work(self):
        self._assert_clean(self._parse_bytes(SAMSUNG_UTF16_TEXT.encode("utf-8")), "UTF-8")
        self._assert_clean(self._parse_bytes(b"\xef\xbb\xbf" + SAMSUNG_UTF16_TEXT.encode("utf-8")), "UTF-8+BOM")

    def test_utf16_korean_only_without_ascii(self):
        """타임스탬프·공백 없이 한글만 이어진 UTF-16 도 깨지지 않아야 한다."""
        text = "화자 1: 안녕하세요\n화자 2: 네 안녕하세요\n"
        for encoding in ("utf-16-le", "utf-16-be"):
            with self.subTest(encoding=encoding):
                parsed = self._parse_bytes(text.encode(encoding))
                self.assertIn("안녕하세요", parsed.full_text)
                self.assertEqual(parsed.speakers, ["화자 1", "화자 2"])


if __name__ == "__main__":
    unittest.main()
