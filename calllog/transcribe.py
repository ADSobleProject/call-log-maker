"""음성 → 텍스트 전사.

faster-whisper(무료·로컬)를 기본으로 쓰되, 테스트에서는 엔진을 바꿔 끼울 수 있도록
`Transcriber` 인터페이스로 분리해 두었다. (네트워크·GPU 없이도 단위 테스트 가능)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Protocol

from .parsers import Segment


@dataclass
class TranscriptionResult:
    segments: list[Segment] = field(default_factory=list)
    duration_sec: float | None = None
    language: str | None = None
    engine: str = ""
    warnings: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        return " ".join(seg.text for seg in self.segments if seg.text.strip())


class TranscriptionError(RuntimeError):
    """전사 실패(패키지 없음, 디코딩 실패 등)."""


class Transcriber(Protocol):
    name: str

    def transcribe(self, path: Path) -> TranscriptionResult:  # pragma: no cover - 인터페이스
        ...


def audio_engine_available() -> bool:
    """음성 변환 엔진(faster-whisper)을 실제로 불러올 수 있는지.

    설치가 깨져 DLL 로딩에서 실패하는 경우(OSError)까지 실패로 본다.
    """
    try:
        import faster_whisper  # noqa: F401
    except Exception:
        return False
    return True


def _detect_device() -> str:
    try:
        import ctranslate2  # faster-whisper 의 의존성

        if ctranslate2.get_cuda_device_count() > 0:
            return "cuda"
    except Exception:  # pragma: no cover - 환경에 따라
        pass
    return "cpu"


class WhisperTranscriber:
    """faster-whisper 로컬 전사기 (모델은 한 번만 메모리에 올린다)."""

    _models: dict[tuple[str, str, str], Any] = {}

    def __init__(
        self,
        model_size: str = "small",
        language: str | None = "ko",
        device: str = "auto",
        compute_type: str = "auto",
        beam_size: int = 5,
        vad_filter: bool = True,
        initial_prompt: str | None = None,
        progress: Callable[[str], None] | None = None,
    ) -> None:
        self.model_size = model_size
        self.language = language or None
        self.device_setting = device
        self.compute_type_setting = compute_type
        self.beam_size = beam_size
        self.vad_filter = vad_filter
        self.initial_prompt = initial_prompt
        self.progress = progress or (lambda _msg: None)
        self.name = f"faster-whisper {model_size}"

    # ------------------------------------------------------------------ 모델
    def _resolve(self) -> tuple[str, str, str]:
        device = self.device_setting if self.device_setting in {"cpu", "cuda"} else _detect_device()
        compute = self.compute_type_setting
        if compute in {"auto", "", None}:
            compute = "float16" if device == "cuda" else "int8"
        return self.model_size, device, compute

    def _model(self) -> Any:
        key = self._resolve()
        if key in self._models:
            return self._models[key]
        try:
            from faster_whisper import WhisperModel
        except Exception as exc:  # 설치 안 됨 / 깨진 설치 (안내용)
            raise TranscriptionError(
                "음성 변환 패키지(faster-whisper)가 설치되어 있지 않습니다. "
                ".txt 통화록 변환은 그대로 됩니다. 음성 파일도 변환하려면 '설치_점검.bat' 을 실행하세요. "
                f"(원인: {type(exc).__name__}: {exc})"
            ) from exc
        model_size, device, compute = key
        try:
            model = WhisperModel(model_size, device=device, compute_type=compute)
        except Exception as exc:  # GPU 오류 등 → CPU 로 한 번 더 시도
            if device != "cpu":
                self.progress(f"  · {device} 로딩 실패({exc}) → CPU 로 다시 시도합니다.")
                model = WhisperModel(model_size, device="cpu", compute_type="int8")
                key = (model_size, "cpu", "int8")
            else:
                raise TranscriptionError(f"Whisper 모델을 불러오지 못했습니다: {exc}") from exc
        self._models[key] = model
        return model

    # ------------------------------------------------------------------ 전사
    def transcribe(self, path: Path) -> TranscriptionResult:
        path = Path(path)
        if not path.exists():
            raise TranscriptionError(f"파일이 없습니다: {path}")
        model = self._model()
        self.progress(f"  · 전사 중... ({path.name})")
        try:
            segments_iter, info = model.transcribe(
                str(path),
                language=self.language,
                beam_size=self.beam_size,
                vad_filter=self.vad_filter,
                initial_prompt=self.initial_prompt,
                condition_on_previous_text=False,
            )
        except Exception as exc:
            raise TranscriptionError(f"음성 파일을 읽지 못했습니다: {exc}") from exc

        warnings: list[str] = []
        segments: list[Segment] = []
        try:
            for item in segments_iter:
                text = (getattr(item, "text", "") or "").strip()
                if not text:
                    continue
                segments.append(
                    Segment(
                        text=text,
                        speaker=None,
                        start=float(getattr(item, "start", 0.0) or 0.0),
                    )
                )
                if len(segments) % 20 == 0:
                    self.progress(f"    ... {len(segments)}개 구간 처리")
        except Exception as exc:
            warnings.append(f"전사 도중 일부 구간을 건너뛰었습니다: {exc}")

        duration = getattr(info, "duration", None)
        language = getattr(info, "language", self.language)
        if not segments:
            warnings.append("음성에서 말소리를 찾지 못했습니다. (무음이거나 소리가 너무 작음)")
        return TranscriptionResult(
            segments=segments,
            duration_sec=float(duration) if duration else None,
            language=language,
            engine=self.name,
            warnings=warnings,
        )


class MockTranscriber:
    """테스트·데모용 전사기. 파일명에 맞춰 정해진 문장을 돌려준다."""

    name = "mock"

    def __init__(self, segments: list[Segment] | None = None, duration: float | None = 42.0) -> None:
        self._segments = segments or [
            Segment(text="안녕하세요, 통화 잘 들리시죠?", speaker=None, start=0.0),
            Segment(text="네 잘 들립니다. 예약 건으로 연락드렸어요.", speaker=None, start=3.2),
        ]
        self._duration = duration
        self.calls: list[Path] = []

    def transcribe(self, path: Path) -> TranscriptionResult:
        self.calls.append(Path(path))
        return TranscriptionResult(
            segments=[Segment(text=s.text, speaker=s.speaker, start=s.start) for s in self._segments],
            duration_sec=self._duration,
            language="ko",
            engine=self.name,
        )


def build_transcriber(config: Any, progress: Callable[[str], None] | None = None) -> WhisperTranscriber:
    t = config.transcribe
    return WhisperTranscriber(
        model_size=t.get("model", "small"),
        language=t.get("language", "ko"),
        device=t.get("device", "auto"),
        compute_type=t.get("compute_type", "auto"),
        beam_size=int(t.get("beam_size", 5)),
        vad_filter=bool(t.get("vad_filter", True)),
        initial_prompt=t.get("initial_prompt"),
        progress=progress,
    )
