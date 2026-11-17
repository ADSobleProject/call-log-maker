"""폴더 감시: 새 파일이 들어오면 자동으로 변환한다."""
from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .pipeline import ProcessResult, Processor


@dataclass
class _Seen:
    size: int
    mtime: float


class FolderWatcher:
    """input 폴더를 주기적으로 훑어 '안정된' 새 파일만 변환한다.

    - 파일 크기·수정시각이 지난번과 같아야 처리 → 복사 중인 파일을 건드리지 않는다.
    - 처리 완료 파일은 processed/ 로 옮겨지므로 같은 파일을 두 번 만들지 않는다.
    """

    def __init__(self, processor: Processor, interval: float = 3.0, log: Callable[[str], None] | None = None) -> None:
        self.processor = processor
        self.interval = max(1.0, float(interval or 3))
        self.log = log or (lambda _m: None)
        self._seen: dict[Path, _Seen] = {}
        self._first_scan = True

    def scan_once(self) -> list[ProcessResult]:
        results: list[ProcessResult] = []
        for path in self.processor.collect(self.processor.config.input_dir):
            try:
                stat = path.stat()
            except OSError:
                continue
            key = path.resolve()
            previous = self._seen.get(key)
            snapshot = _Seen(size=stat.st_size, mtime=stat.st_mtime)
            if previous is None:
                self._seen[key] = snapshot
                # 이미 오래된 파일(감시 시작 전부터 있던 파일)은 바로 처리
                if time.time() - stat.st_mtime >= self.interval:
                    results.append(self.processor.process_file(path))
                continue
            if previous.size != snapshot.size or abs(previous.mtime - snapshot.mtime) > 1e-6:
                self._seen[key] = snapshot
                continue
            results.append(self.processor.process_file(path))
            self._seen.pop(key, None)
        self._first_scan = False
        # 사라진 파일 정리
        existing = {p.resolve() for p in self.processor.config.input_dir.rglob("*") if p.is_file()}
        for key in list(self._seen):
            if key not in existing:
                self._seen.pop(key, None)
        return results

    def run(self, stop: Callable[[], bool] | None = None) -> None:  # pragma: no cover - 긴 실행 루프
        self.processor.config.ensure_dirs()
        self.log("폴더 감시를 시작합니다. (종료: Ctrl+C)")
        self.log(f"  · 감시 폴더: {self.processor.config.input_dir}")
        self.log(f"  · {self.interval:.0f}초마다 새 파일 확인")
        try:
            while True:
                if stop and stop():
                    break
                results = self.scan_once()
                for result in results:
                    if result.ok:
                        self.log(f"  ✓ 변환 완료: {result.source.name}")
                    elif not result.skipped:
                        self.log(f"  ✗ 실패: {result.source.name} ({result.error or result.reason})")
                time.sleep(self.interval)
        except KeyboardInterrupt:
            self.log("폴더 감시를 멈췄습니다.")
