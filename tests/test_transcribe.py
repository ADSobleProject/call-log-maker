import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from calllog.config import Config
from calllog.transcribe import (
    MockTranscriber,
    TranscriptionError,
    WhisperTranscriber,
    audio_engine_available,
    audio_engine_problem,
    build_transcriber,
)


class TranscriberConfigTest(unittest.TestCase):
    def test_build_from_config(self):
        cfg = Config.load(root=Path(__file__).resolve().parent.parent)
        cfg.transcribe.update({"model": "base", "language": "ko", "device": "cpu", "compute_type": "int8"})
        transcriber = build_transcriber(cfg)
        self.assertIsInstance(transcriber, WhisperTranscriber)
        self.assertEqual(transcriber.name, "faster-whisper base")
        self.assertEqual(transcriber._resolve(), ("base", "cpu", "int8"))

    def test_auto_compute_type_on_cpu(self):
        transcriber = WhisperTranscriber(model_size="small", device="cpu")
        self.assertEqual(transcriber._resolve()[2], "int8")


class MockTranscriberTest(unittest.TestCase):
    def test_returns_segments(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "a.m4a"
            path.write_bytes(b"x")
            result = MockTranscriber().transcribe(path)
            self.assertEqual(result.language, "ko")
            self.assertTrue(result.segments)
            self.assertEqual(result.duration_sec, 42.0)


class MissingModelTest(unittest.TestCase):
    def test_missing_file_raises(self):
        with self.assertRaises(TranscriptionError):
            WhisperTranscriber(device="cpu").transcribe(Path("/nonexistent/audio.m4a"))


class BrokenAvTest(unittest.TestCase):
    """av 19 부터 metadata_errors 인자가 없어져 생기는 오류를 안내로 바꾸는지."""

    class _BrokenModel:
        def transcribe(self, *_args, **_kwargs):
            raise TypeError("open() got an unexpected keyword argument 'metadata_errors'")

    def test_error_explains_av_mismatch_and_repair(self):
        transcriber = WhisperTranscriber(device="cpu")
        transcriber._model = self._BrokenModel  # type: ignore[assignment]
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "a.m4a"
            path.write_bytes(b"x")
            with self.assertRaises(TranscriptionError) as caught:
                transcriber.transcribe(path)
        message = str(caught.exception)
        self.assertIn("metadata_errors", message)
        self.assertIn("설치_점검.bat", message)
        self.assertIn("av<19", message)

    def test_other_decoding_errors_stay_plain(self):
        class _Other:
            def transcribe(self, *_args, **_kwargs):
                raise OSError("Invalid data found when processing input")

        transcriber = WhisperTranscriber(device="cpu")
        transcriber._model = _Other  # type: ignore[assignment]
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "a.m4a"
            path.write_bytes(b"x")
            with self.assertRaises(TranscriptionError) as caught:
                transcriber.transcribe(path)
        self.assertNotIn("설치_점검.bat", str(caught.exception))

    def test_engine_problem_reports_missing_package(self):
        # 테스트 환경에는 faster-whisper 가 없으니 '설치 안 됨'으로 보인다
        self.assertIn("faster-whisper", audio_engine_problem())
        self.assertFalse(audio_engine_available())


if __name__ == "__main__":
    unittest.main()
