"""통화록 문서 모델."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .parsers import Segment


@dataclass
class ActionItem:
    text: str
    owner: str = ""
    due: str = ""
    speaker: str = ""


@dataclass
class CallDocument:
    title: str
    when: datetime | None
    source_name: str
    mode: str                      # "음성→텍스트" / "텍스트 변환본"
    engine: str = ""
    duration_sec: float | None = None
    segments: list[Segment] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    summary: list[str] = field(default_factory=list)
    actions: list[ActionItem] = field(default_factory=list)
    amounts: list[str] = field(default_factory=list)
    dates: list[str] = field(default_factory=list)
    speakers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    source_path: Path | None = None

    @property
    def char_count(self) -> int:
        return sum(len(s.text) for s in self.segments)

    @property
    def utterance_count(self) -> int:
        return len(self.segments)

    def stamp(self) -> str:
        """결과 파일 이름 앞에 붙는 YYYYMMDD_HHMM."""
        if self.when:
            return self.when.strftime("%Y%m%d_%H%M")
        return self.created_at.strftime("%Y%m%d_%H%M")

    def heading(self) -> str:
        when = self.when.strftime("%Y-%m-%d %H:%M") if self.when else "일시 미상"
        return f"통화록 - {self.title} ({when})"
