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


if __name__ == "__main__":
    unittest.main()
