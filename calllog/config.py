"""설정(config.json) 로드와 경로 해석.

config.json 의 경로는 프로젝트 폴더 기준 상대 경로로 적는 것이 기본이고,
`C:/Users/.../Google Drive/...` 같은 절대 경로도 그대로 쓸 수 있다.
"""
from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_NAME = "config.json"

DEFAULTS: dict[str, Any] = {
    "input_dir": "input",
    "output_dir": "output",
    "processed_dir": "processed",
    "archive_processed": True,
    "keep_raw_transcript": False,
    "watch_interval_sec": 3,
    "max_keywords": 10,
    "max_summary_sentences": 5,
    "max_action_items": 8,
    "title_max_len": 40,
    "document_formats": ["md", "docx"],
    "transcribe": {
        "model": "small",
        "language": "ko",
        "device": "auto",
        "compute_type": "auto",
        "beam_size": 5,
        "vad_filter": True,
        "initial_prompt": (
            "한국어 통화 내용입니다. 상대방 이름, 날짜, 금액, 약속, 요청 사항이 포함될 수 있습니다."
        ),
    },
}

_TEXT_KEYS = {"input_dir", "output_dir", "processed_dir"}


def _merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], value)
        else:
            out[key] = value
    return out


@dataclass
class Config:
    """해석이 끝난 설정. 모든 경로는 절대 경로(Path)다."""

    root: Path
    input_dir: Path
    output_dir: Path
    processed_dir: Path
    archive_processed: bool = True
    keep_raw_transcript: bool = False
    watch_interval_sec: float = 3.0
    max_keywords: int = 10
    max_summary_sentences: int = 5
    max_action_items: int = 8
    title_max_len: int = 40
    document_formats: list[str] = field(default_factory=lambda: ["md", "docx"])
    transcribe: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    # ---------------------------------------------------------------- 생성
    @classmethod
    def load(cls, path: str | Path | None = None, root: str | Path | None = None) -> "Config":
        root_path = Path(root).resolve() if root else PROJECT_ROOT
        config_path = Path(path) if path else root_path / CONFIG_NAME
        data: dict[str, Any] = {}
        warnings: list[str] = []
        if config_path.exists():
            try:
                data = json.loads(config_path.read_text(encoding="utf-8"))
                if not isinstance(data, dict):
                    warnings.append(f"{config_path.name} 형식이 올바르지 않아 기본 설정을 씁니다.")
                    data = {}
            except (OSError, json.JSONDecodeError) as exc:
                warnings.append(f"{config_path.name} 를 읽지 못해 기본 설정을 씁니다 ({exc}).")
                data = {}
        else:
            warnings.append(f"{config_path} 가 없어 기본 설정을 씁니다.")

        merged = _merge(DEFAULTS, data)
        base = root_path

        def resolve(value: Any, fallback: str) -> Path:
            raw = value if isinstance(value, str) and value.strip() else fallback
            p = Path(raw).expanduser()
            return p if p.is_absolute() else (base / p).resolve()

        transcribe = merged.get("transcribe") or {}
        if not isinstance(transcribe, dict):
            transcribe = {}
        formats = merged.get("document_formats") or ["md", "docx"]
        if isinstance(formats, str):
            formats = [formats]
        formats = [str(f).lower().lstrip(".") for f in formats if str(f).strip()]
        formats = [f for f in formats if f in {"md", "docx"}] or ["md", "docx"]

        cfg = cls(
            root=base,
            input_dir=resolve(merged.get("input_dir"), DEFAULTS["input_dir"]),
            output_dir=resolve(merged.get("output_dir"), DEFAULTS["output_dir"]),
            processed_dir=resolve(merged.get("processed_dir"), DEFAULTS["processed_dir"]),
            archive_processed=bool(merged.get("archive_processed", True)),
            keep_raw_transcript=bool(merged.get("keep_raw_transcript", False)),
            watch_interval_sec=float(merged.get("watch_interval_sec", 3) or 3),
            max_keywords=int(merged.get("max_keywords", 10) or 10),
            max_summary_sentences=int(merged.get("max_summary_sentences", 5) or 5),
            max_action_items=int(merged.get("max_action_items", 8) or 8),
            title_max_len=int(merged.get("title_max_len", 40) or 40),
            document_formats=formats,
            transcribe={
                "model": transcribe.get("model", DEFAULTS["transcribe"]["model"]),
                "language": transcribe.get("language", "ko"),
                "device": transcribe.get("device", "auto"),
                "compute_type": transcribe.get("compute_type", "auto"),
                "beam_size": int(transcribe.get("beam_size", 5) or 5),
                "vad_filter": bool(transcribe.get("vad_filter", True)),
                "initial_prompt": transcribe.get("initial_prompt", DEFAULTS["transcribe"]["initial_prompt"]),
            },
            raw=merged,
            warnings=warnings,
        )
        return cfg

    # ---------------------------------------------------------------- 보조
    def ensure_dirs(self) -> None:
        for d in (self.input_dir, self.output_dir, self.processed_dir):
            d.mkdir(parents=True, exist_ok=True)

    def describe(self) -> str:
        lines = [
            f"프로젝트 폴더 : {self.root}",
            f"입력 폴더     : {self.input_dir}",
            f"결과 폴더     : {self.output_dir}",
            f"처리 완료 폴더: {self.processed_dir} (이동: {'켜짐' if self.archive_processed else '꺼짐'})",
            f"전사 모델     : faster-whisper '{self.transcribe.get('model')}' "
            f"({self.transcribe.get('device')} / {self.transcribe.get('compute_type')})",
            f"결과 형식     : {', '.join(self.document_formats)}",
        ]
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return copy.deepcopy(self.raw)
