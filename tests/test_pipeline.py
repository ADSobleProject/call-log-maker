import json
import shutil
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from calllog.config import Config
from calllog.parsers import Segment
from calllog.pipeline import Processor
from calllog.transcribe import MockTranscriber, Transcriber, TranscriptionError, TranscriptionResult

SAMPLES = Path(__file__).resolve().parent.parent / "samples"


def make_project(tmp: Path, **overrides) -> Config:
    (tmp / "input").mkdir(parents=True, exist_ok=True)
    (tmp / "output").mkdir(parents=True, exist_ok=True)
    (tmp / "processed").mkdir(parents=True, exist_ok=True)
    data = {
        "input_dir": "input",
        "output_dir": "output",
        "processed_dir": "processed",
        "archive_processed": True,
        "document_formats": ["md", "docx"],
    }
    data.update(overrides)
    (tmp / "config.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return Config.load(tmp / "config.json", root=tmp)


class PipelineTest(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.cfg = make_project(self.tmp)

    def tearDown(self):
        self._tmp.cleanup()

    def test_text_file_end_to_end(self):
        src = self.tmp / "input" / "통화 녹음 김지훈_261117_210000.txt"
        shutil.copy(SAMPLES / "통화 녹음 김지훈_261117_210000.txt", src)
        result = Processor(self.cfg).process_file(src)
        self.assertTrue(result.ok, result.error)
        names = sorted(p.name for p in result.outputs)
        self.assertEqual(
            names,
            ["20261117_2100_김지훈_통화록.docx", "20261117_2100_김지훈_통화록.md"],
        )
        md = (self.cfg.output_dir / names[1]).read_text(encoding="utf-8")
        self.assertIn("통화록 - 김지훈", md)
        self.assertIn("텍스트 변환본", md)
        self.assertIn("발주서", md)
        # 원본은 processed/ 로 이동
        self.assertFalse(src.exists())
        self.assertTrue((self.cfg.processed_dir / src.name).exists())

    def test_audio_uses_injected_transcriber(self):
        src = self.tmp / "input" / "통화 녹음 홍길동_261117_210000.m4a"
        src.write_bytes(b"fake audio bytes")
        mock = MockTranscriber(
            segments=[
                Segment(text="네, 예약 가능합니다.", start=0.0),
                Segment(text="그럼 내일 오후 세 시로 잡아 주세요.", start=3.0),
            ],
            duration=12.0,
        )
        result = Processor(self.cfg, transcriber=mock).process_file(src)
        self.assertTrue(result.ok, result.error)
        self.assertEqual(len(mock.calls), 1)
        md_text = (self.cfg.output_dir / "20261117_2100_홍길동_통화록.md").read_text(encoding="utf-8")
        self.assertIn("음성→텍스트", md_text)
        self.assertIn("예약 가능합니다", md_text)

    def test_duplicate_content_is_skipped(self):
        first = self.tmp / "input" / "통화 녹음 홍길동_261117_210000.m4a"
        first.write_bytes(b"same bytes")
        cfg = self.cfg
        processor = Processor(cfg, transcriber=MockTranscriber())
        self.assertTrue(processor.process_file(first).ok)
        second = self.tmp / "input" / "다른이름_261117_210000.m4a"
        second.write_bytes(b"same bytes")
        result = Processor(cfg, transcriber=MockTranscriber()).process_file(second)
        self.assertTrue(result.skipped)
        self.assertIn("중복", result.reason)
        self.assertTrue(second.exists())

    def test_unsupported_and_empty_files(self):
        pdf = self.tmp / "input" / "문서.pdf"
        pdf.write_bytes(b"%PDF")
        self.assertIn("지원하지 않는", Processor(self.cfg).process_file(pdf).reason)
        empty = self.tmp / "input" / "빈파일.txt"
        empty.write_bytes(b"")
        self.assertTrue(Processor(self.cfg).process_file(empty).skipped)

    def test_archive_off_keeps_source(self):
        cfg = make_project(Path(self._tmp.name + "_b"), archive_processed=False)
        try:
            src = cfg.input_dir / "메모 20261117_1200.txt"
            src.write_text("화자 1: 안녕하세요\n화자 2: 네", encoding="utf-8")
            result = Processor(cfg).process_file(src)
            self.assertTrue(result.ok, result.error)
            self.assertTrue(src.exists())
        finally:
            shutil.rmtree(cfg.root, ignore_errors=True)

    def test_name_collision_gets_suffix(self):
        src = self.tmp / "input" / "통화 녹음 김지훈_261117_210000.txt"
        shutil.copy(SAMPLES / "통화 녹음 김지훈_261117_210000.txt", src)
        self.assertTrue(Processor(self.cfg).process_file(src).ok)
        again = self.tmp / "input" / "통화 녹음 김지훈_261117_210000_2.txt"
        content = (SAMPLES / "통화 녹음 김지훈_261117_210000.txt").read_text(encoding="utf-8")
        again.write_text(content + "\n화자 1: 추가 문장입니다.", encoding="utf-8")
        result = Processor(self.cfg).process_file(again)
        self.assertTrue(result.ok, result.error)
        names = [p.name for p in result.outputs]
        self.assertIn("20261117_2100_김지훈_통화록_2.md", names)

    def test_only_markdown_format(self):
        cfg = make_project(Path(self._tmp.name + "_c"), document_formats=["md"])
        try:
            src = cfg.input_dir / "통화 녹음 김지훈_261117_210000.txt"
            shutil.copy(SAMPLES / "통화 녹음 김지훈_261117_210000.txt", src)
            result = Processor(cfg).process_file(src)
            self.assertEqual([p.suffix for p in result.outputs], [".md"])
        finally:
            shutil.rmtree(cfg.root, ignore_errors=True)

    def test_raw_transcript_option(self):
        cfg = make_project(Path(self._tmp.name + "_d"), keep_raw_transcript=True)
        try:
            src = cfg.input_dir / "통화 녹음 김지훈_261117_210000.txt"
            shutil.copy(SAMPLES / "통화 녹음 김지훈_261117_210000.txt", src)
            result = Processor(cfg).process_file(src)
            self.assertTrue(any(p.name.endswith("_전사원문.txt") for p in result.outputs))
        finally:
            shutil.rmtree(cfg.root, ignore_errors=True)

    def test_transcription_failure_is_reported_and_not_archived(self):
        class Broken:
            name = "broken"

            def transcribe(self, path):
                raise TranscriptionError("디코딩 실패")

        src = self.tmp / "input" / "통화 녹음 실패_261117_210000.m4a"
        src.write_bytes(b"bad")
        result = Processor(self.cfg, transcriber=Broken()).process_file(src)
        self.assertFalse(result.ok)
        self.assertIn("디코딩 실패", result.error)
        self.assertTrue(src.exists())
        self.assertEqual(Processor(self.cfg).registry.entries, {})

    def test_process_folder_scans_and_skips_processed(self):
        shutil.copy(SAMPLES / "일반대화_예시.txt", self.cfg.input_dir / "일반대화_예시.txt")
        processor = Processor(self.cfg)
        results = processor.process_folder()
        self.assertEqual(len(results), 1)
        self.assertTrue(results[0].ok)
        self.assertEqual(processor.process_folder(), [])


if __name__ == "__main__":
    unittest.main()
