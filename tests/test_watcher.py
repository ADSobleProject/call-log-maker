import json
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from calllog.config import Config
from calllog.pipeline import Processor
from calllog.watcher import FolderWatcher


class WatcherTest(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        for name in ("input", "output", "processed"):
            (self.tmp / name).mkdir()
        (self.tmp / "config.json").write_text(
            json.dumps({"input_dir": "input", "output_dir": "output", "processed_dir": "processed"}),
            encoding="utf-8",
        )
        self.cfg = Config.load(self.tmp / "config.json", root=self.tmp)

    def tearDown(self):
        self._tmp.cleanup()

    def test_new_file_is_processed_after_settling(self):
        watcher = FolderWatcher(Processor(self.cfg), interval=1.0)
        self.assertEqual(watcher.scan_once(), [])  # 첫 스캔은 파일만 기억

        path = self.cfg.input_dir / "통화 녹음 홍길동_261117_210000.txt"
        path.write_text("화자 1: 새로 들어온 파일입니다.\n화자 2: 확인했습니다.", encoding="utf-8")
        time.sleep(0.05)
        self.assertEqual(watcher.scan_once(), [])  # 크기·시각이 바뀌었으니 다음 스캔에서

        results = watcher.scan_once()
        self.assertEqual(len(results), 1)
        self.assertTrue(results[0].ok)
        self.assertTrue(any(p.suffix == ".md" for p in results[0].outputs))

    def test_same_file_is_not_processed_twice(self):
        path = self.cfg.input_dir / "메모_20261117_1200.txt"
        path.write_text("화자 1: 한 번만 처리되어야 합니다.", encoding="utf-8")
        # 감시 시작 전부터 있던 오래된 파일 → 첫 스캔에서 바로 처리
        old = time.time() - 10
        import os
        os.utime(path, (old, old))
        watcher = FolderWatcher(Processor(self.cfg), interval=1.0)
        first = watcher.scan_once()
        self.assertEqual(len(first), 1)
        self.assertTrue(first[0].ok)
        self.assertEqual(watcher.scan_once(), [])


if __name__ == "__main__":
    unittest.main()
