import unittest
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from calllog.filenames import parse_filename, safe_filename, clean_title


class FilenameParseTest(unittest.TestCase):
    def test_samsung_call_recording(self):
        info = parse_filename("통화 녹음 홍길동_261117_210000.m4a")
        self.assertEqual(info.title, "홍길동")
        self.assertEqual(info.when, datetime(2026, 11, 17, 21, 0, 0))
        self.assertTrue(info.time_known)

    def test_two_digit_year_and_phone_title(self):
        info = parse_filename("통화녹음_01012345678_231117_210000.m4a")
        self.assertEqual(info.title, "01012345678")
        self.assertEqual(info.when, datetime(2023, 11, 17, 21, 0, 0))

    def test_date_time_without_title_falls_back(self):
        info = parse_filename("녹음_20261117_1430.m4a")
        self.assertEqual(info.when, datetime(2026, 11, 17, 14, 30))
        self.assertIn(info.title, {"통화 녹음"})

    def test_kakaotalk_style(self):
        info = parse_filename("KakaoTalk_Audio_20261117_143000.m4a")
        self.assertEqual(info.when, datetime(2026, 11, 17, 14, 30, 0))

    def test_dotted_date_with_korean_ampm(self):
        info = parse_filename("통화 녹음 2026. 11. 17. 오후 9:00.m4a")
        self.assertEqual(info.when, datetime(2026, 11, 17, 21, 0))

    def test_hyphen_date_and_meeting_title(self):
        info = parse_filename("회의 2026-11-17 14.30.m4a")
        self.assertEqual(info.title, "회의")
        self.assertEqual(info.when, datetime(2026, 11, 17, 14, 30))

    def test_uses_mtime_when_no_date(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "보고서.m4a"
            path.write_bytes(b"x")
            info = parse_filename(path)
            self.assertEqual(info.title, "보고서")
            self.assertIsNotNone(info.when)
            self.assertFalse(info.time_known)

    def test_invalid_date_is_ignored(self):
        info = parse_filename("통화 녹음 2026-13-45 99:99.m4a")
        self.assertIsNone(info.when)

    def test_clean_title_removes_noise(self):
        self.assertEqual(clean_title("통화녹음_김철수_"), "김철수")
        self.assertEqual(clean_title("Voice Recorder 20261117"), "")
        self.assertEqual(clean_title("회의"), "회의")

    def test_safe_filename(self):
        self.assertEqual(safe_filename('김철수/이영희:*?"<>|'), "김철수 이영희")
        self.assertEqual(safe_filename(""), "통화 녹음")
        self.assertLessEqual(len(safe_filename("가" * 100, 20)), 20)


if __name__ == "__main__":
    unittest.main()
