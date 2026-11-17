"""이 PC의 Python 이 '음성 변환'까지 감당할 수 있는지 판단하는 규칙.

Windows 에서 설치가 막히는 흔한 이유는 두 가지다.

1. **32비트 Python** — onnxruntime·ctranslate2·av 에는 32비트 wheel 이 없다.
   (`no matching distributions available for your environment: onnxruntime`)
2. **너무 새 버전(3.13+) 또는 free-threaded 빌드** — 일부 패키지의 wheel 이 아직 없다.
   wheel 이 없으면 pip 이 소스를 받아 직접 빌드하려 들고(`av-12.3.0.tar.gz`), 대개 실패한다.

그래서 이 프로그램은 **64비트 + Python 3.10~3.12** 를 권장하고, 그런 Python 이 없으면
`.txt` 통화록 변환만으로 계속 진행한다. (`.txt` 변환은 python-docx 만 있으면 된다)
"""
from __future__ import annotations

import re
import struct
import sys
from dataclasses import dataclass
from typing import Iterable, Sequence

# 프로그램 자체(텍스트 변환)의 최소 버전
MIN_PYTHON = (3, 9)
# 음성 변환(faster-whisper)의 최소 버전 — 64비트 조건은 따로 본다
AUDIO_MIN = (3, 9)
# 권장 순서: 앞에 있을수록 먼저 쓴다 (모델 파일이 잘 도는 조합)
PREFERRED_ORDER = ((3, 12), (3, 11), (3, 10))
# 안내에 쓰는 한 줄 해결책
WINGET_ID = "Python.Python.3.12"
PYTHON_DOWNLOADS = "https://www.python.org/downloads/windows/"

# pip 이 'wheel 이 없다'고 말할 때 쓰는 표현들
_MISSING_WHEEL_MARKERS = (
    "no matching distribution",
    "no matching distributions available for your environment",
    "could not find a version that satisfies",
    "resolutionimpossible",
    "has no matching distributions",
    "not supported on this platform",
    "requires a different python",
    "no available builds",
)
_PACKAGE_PATTERNS = (
    re.compile(r"for your environment:\s*([A-Za-z0-9_.\-]+)"),
    re.compile(r"Could not find a version that satisfies the requirement ([A-Za-z0-9_.\-]+)"),
    re.compile(r"No matching distribution found for ([A-Za-z0-9_.\-]+)"),
)

_BITS = struct.calcsize("P") * 8


@dataclass(frozen=True)
class Interpreter:
    """Python 실행 파일 하나의 정보."""

    version: tuple[int, int]
    bits: int
    label: str = ""
    path: str = ""
    command: tuple[str, ...] = ()

    @property
    def version_text(self) -> str:
        return f"{self.version[0]}.{self.version[1]}"

    @property
    def bits_text(self) -> str:
        return f"{self.bits}비트"

    def describe(self) -> str:
        who = f"Python {self.version_text} ({self.bits_text})"
        return f"{who} — {self.label}" if self.label and self.label not in who else who

    @property
    def argv(self) -> list[str]:
        """이 인터프리터를 실행하는 명령(공백 있는 경로도 안전하게)."""
        if self.command:
            return list(self.command)
        return [self.path or sys.executable]

    @classmethod
    def current(cls) -> "Interpreter":
        return cls(
            version=(sys.version_info[0], sys.version_info[1]),
            bits=_BITS,
            label=sys.executable,
            path=sys.executable,
            command=(sys.executable,),
        )


def current_interpreter() -> Interpreter:
    return Interpreter.current()


def is_audio_ready(version: tuple[int, int], bits: int) -> bool:
    """faster-whisper(음성 변환)를 설치할 수 있는 환경인가."""
    return bits == 64 and tuple(version) >= AUDIO_MIN


def _version_rank(version: tuple[int, int]) -> int:
    if version in PREFERRED_ORDER:
        return PREFERRED_ORDER.index(version)
    if version > (3, 12):
        # 3.13 이상: wheel 이 있을 때도 있지만 검증되지 않았다 → 권장 버전 다음 순위
        return len(PREFERRED_ORDER)
    return len(PREFERRED_ORDER) + 1  # 3.9 이하


def rank(interpreter: Interpreter) -> tuple:
    """작을수록 먼저 쓴다: 64비트 → 권장 버전 순 → 높은 버전."""
    return (0 if interpreter.bits == 64 else 1, _version_rank(interpreter.version), interpreter.version)


def choose_best(interpreters: Iterable[Interpreter]) -> Interpreter | None:
    """쓸 만한 Python 중 가장 좋은 것. 3.9 미만은 제외."""
    usable = [i for i in interpreters if tuple(i.version) >= MIN_PYTHON]
    if not usable:
        return None
    return sorted(usable, key=rank)[0]


def dedupe(interpreters: Iterable[Interpreter]) -> list[Interpreter]:
    """같은 버전·비트가 여러 번 잡히면 먼저 나온 것(더 구체적인 실행 방법)만 남긴다."""
    seen: set[tuple[tuple[int, int], int]] = set()
    out: list[Interpreter] = []
    for item in interpreters:
        key = (tuple(item.version), item.bits)
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def venv_needs_rebuild(venv: Interpreter | None, best: Interpreter | None) -> bool:
    """지금 `.venv` 를 새로 만들어야 하나.

    · 없거나 깨졌으면 새로 만든다.
    · 음성 변환이 안 되는 환경(32비트 등)으로 만들어졌는데 더 나은 Python 이 있으면 새로 만든다.
    · 이미 음성 변환이 되는 환경이면 그대로 쓴다(패키지를 다시 받지 않게).
    """
    if venv is None:
        return True
    if tuple(venv.version) < MIN_PYTHON:
        return True
    if is_audio_ready(venv.version, venv.bits):
        return False
    if best is not None and is_audio_ready(best.version, best.bits):
        return True
    return False


def describe_audio_problem(interpreter: Interpreter | None) -> str:
    """왜 음성 변환이 안 되는지 한 줄로."""
    if interpreter is None:
        return "이 PC 에서 Python 을 찾지 못했습니다."
    if interpreter.bits != 64:
        return f"{interpreter.describe()} — 32비트 Python 에는 음성 변환 패키지(onnxruntime)가 없습니다."
    if tuple(interpreter.version) < AUDIO_MIN:
        return f"{interpreter.describe()} — 음성 변환은 Python {AUDIO_MIN[0]}.{AUDIO_MIN[1]} 이상이 필요합니다."
    if tuple(interpreter.version) > (3, 12):
        return f"{interpreter.describe()} — 이 버전용 음성 변환 패키지(wheel)가 아직 없을 수 있습니다."
    return f"{interpreter.describe()} 에서는 음성 변환 패키지 설치가 실패했습니다."


def audio_help_lines(interpreter: Interpreter | None = None) -> list[str]:
    """음성 변환을 켜는 방법 안내(여러 줄)."""
    lines = ["[음성 파일도 변환하려면]"]
    if interpreter is not None:
        lines.append(f"  지금 Python: {interpreter.describe()}")
    lines.extend(
        [
            "  1) 64비트 Python 3.12 설치 (PowerShell/명령 프롬프트에서 한 줄):",
            f"       winget install -e --id {WINGET_ID}",
            "  2) winget 이 없으면 이 주소에서 'Windows installer (64-bit)' 3.12 를 받아 설치",
            f"       {PYTHON_DOWNLOADS}   (설치 화면에서 'Add python.exe to PATH' 체크)",
            "  3) 이 창을 닫고 '설치_점검.bat' 을 다시 실행",
            "  ※ .txt 통화록 변환은 지금도 그대로 됩니다.",
        ]
    )
    return lines


def looks_like_missing_wheel(output: str) -> bool:
    """pip 실패가 '이 환경에 wheel 이 없다' 때문인가(다시 시도해도 소용없음)."""
    text = (output or "").lower()
    return any(marker in text for marker in _MISSING_WHEEL_MARKERS)


def missing_packages(output: str) -> list[str]:
    """pip 출력에서 문제가 된 패키지 이름을 뽑는다(있으면)."""
    names: list[str] = []
    for pattern in _PACKAGE_PATTERNS:
        for found in pattern.findall(output or ""):
            name = found.strip()
            if name and name.lower() not in {n.lower() for n in names}:
                names.append(name)
    return names


def summarize_pip_failure(output: str, limit: int = 6) -> list[str]:
    """pip 출력에서 사용자에게 보여 줄 핵심 줄만."""
    keywords = ("error", "conflict", "depends on", "no matching", "could not find", "failed")
    picked: list[str] = []
    for raw in (output or "").splitlines():
        line = raw.strip()
        if not line or not any(k in line.lower() for k in keywords):
            continue
        if line in picked:
            continue
        picked.append(line[:200])
        if len(picked) >= limit:
            break
    return picked


def interpreter_table(interpreters: Sequence[Interpreter]) -> list[str]:
    """`doctor` 에서 보여 줄 '이 PC 의 Python' 목록."""
    if not interpreters:
        return []
    return [f"  · {item.describe()}" for item in dedupe(interpreters)]
