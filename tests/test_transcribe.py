import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from calllog.config import Config
from calllog.transcribe import (
    MockTranscriber,
    TranscriptionError,
    WhisperTranscriber,
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


if __name__ == "__main__":
    unittest.main()
