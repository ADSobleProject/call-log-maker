import json
import shutil
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from calllog.cli import main

SAMPLES = Path(__file__).resolve().parent.parent / "samples"


def project(tmp: Path) -> None:
    for name in ("input", "output", "processed"):
        (tmp / name).mkdir()
    (tmp / "config.json").write_text(
        json.dumps({"input_dir": "input", "output_dir": "output", "processed_dir": "processed"}),
        encoding="utf-8",
    )


class CliTest(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        project(self.tmp)

    def tearDown(self):
        self._tmp.cleanup()

    def run_cli(self, *args) -> tuple[int, str]:
        buffer = StringIO()
        with redirect_stdout(buffer):
            code = main(["--root", str(self.tmp), *args])
        return code, buffer.getvalue()

    def test_batch_converts_and_archives(self):
        shutil.copy(SAMPLES / "클로바노트_예시.txt", self.tmp / "input" / "클로바노트_예시.txt")
        code, out = self.run_cli("batch")
        self.assertEqual(code, 0, out)
        self.assertIn("변환 완료 1개", out)
        self.assertEqual(len(list((self.tmp / "output").glob("*_통화록.md"))), 1)
        self.assertEqual(len(list((self.tmp / "processed").glob("*.txt"))), 1)

    def test_empty_input_is_friendly(self):
        code, out = self.run_cli("batch")
        self.assertEqual(code, 0)
        self.assertIn("변환할 파일이 없습니다", out)

    def test_files_command_keeps_source(self):
        src = self.tmp / "외부폴더" / "통화 녹음 홍길동_261117_210000.txt"
        src.parent.mkdir()
        shutil.copy(SAMPLES / "클로바노트_예시.txt", src)
        code, out = self.run_cli("files", str(src))
        self.assertEqual(code, 0, out)
        self.assertTrue(src.exists(), "드래그한 원본은 그 자리에 남아 있어야 한다")
        self.assertTrue((self.tmp / "output" / "20261117_1430_박서연 실장_통화록.md").exists())

    def test_missing_file_reports_and_fails(self):
        code, out = self.run_cli("files", str(self.tmp / "없는파일.m4a"))
        self.assertEqual(code, 1)
        self.assertIn("찾을 수 없습니다", out)

    def test_doctor_runs(self):
        code, out = self.run_cli("doctor")
        self.assertIn("Python", out)
        self.assertIn("점검", out)
        self.assertIn(code, (0, 1))

    def test_demo_does_not_move_sample(self):
        shutil.copytree(SAMPLES, self.tmp / "samples")
        sample = self.tmp / "samples" / "통화 녹음 김지훈_261117_210000.txt"
        code, out = self.run_cli("demo")
        self.assertEqual(code, 0, out)
        self.assertTrue(sample.exists())
        self.assertEqual(len(list((self.tmp / "output").glob("*.md"))), 1)


if __name__ == "__main__":
    unittest.main()
