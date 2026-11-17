#!/usr/bin/env python3
"""call-log-maker 환경 준비.

하는 일
  1. 이 PC 에서 쓸 수 있는 Python 을 찾는다 (Windows 는 `py -3.12` → `py -3.11` → `py -3.10` 순).
  2. `.venv` 를 만든다. 이미 있는데 깨졌거나(파이썬 없음) 32비트처럼 못 쓸 환경이면
     지우지 않고 `.venv.broken-<시각>` 으로 옮겨 둔 뒤 새로 만든다.
  3. **필수 패키지**(python-docx)를 먼저 설치한다 → `.txt` 통화록 변환은 여기서 바로 가능해진다.
  4. **선택 패키지**(faster-whisper, 음성 파일 변환)는 따로 설치한다.
     실패해도 프로그램은 그대로 쓸 수 있고, 왜 안 되는지와 해결 방법을 알려 준다.

사용법
    python setup_env.py             # 필요한 것만 준비 (이미 되어 있으면 즉시 끝)
    python setup_env.py --repair    # 음성 변환 설치를 다시 시도
    python setup_env.py --ask-install   # 음성 패키지가 안 되면 64비트 3.12 설치를 물어본다
    python setup_env.py --install-python  # 64비트 3.12 설치를 바로 시도(winget)
    python setup_env.py --core-only # .txt 변환용 패키지만
    python setup_env.py --check     # 아무것도 바꾸지 않고 상태만 보기
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from calllog import compat  # noqa: E402  (패키지 설치 전에도 돌아야 하므로 stdlib 전용 모듈)

PROBE_CODE = (
    "import sys, struct; "
    "print('%d.%d %d' % (sys.version_info[0], sys.version_info[1], struct.calcsize('P') * 8))"
)
CORE_REQUIREMENTS = "requirements.txt"
AUDIO_REQUIREMENTS = "requirements-audio.txt"


class RunResult:
    """외부 명령 실행 결과."""

    __slots__ = ("code", "out")

    def __init__(self, code: int, out: str = "") -> None:
        self.code = code
        self.out = out or ""

    @property
    def ok(self) -> bool:
        return self.code == 0

    def __repr__(self) -> str:  # pragma: no cover - 디버그용
        return f"RunResult(code={self.code}, out={self.out[:80]!r})"


def run_command(cmd, cwd=None, timeout=None) -> RunResult:
    """명령을 실행하고 (종료코드, 출력)을 돌려준다. 실행 파일이 없어도 예외를 던지지 않는다."""
    try:
        proc = subprocess.run(
            list(cmd),
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        return RunResult(proc.returncode, (proc.stdout or "") + (proc.stderr or ""))
    except FileNotFoundError:
        return RunResult(127, f"실행 파일을 찾을 수 없습니다: {cmd[0]}")
    except subprocess.TimeoutExpired:
        return RunResult(124, "시간이 너무 오래 걸려 중단했습니다.")
    except OSError as exc:  # 권한 없음, 32비트/64비트 불일치 등
        return RunResult(126, str(exc))


def _fix_console() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except Exception:
            pass


class Setup:
    """환경 준비 한 판. 테스트에서는 runner/printer 를 바꿔 끼운다."""

    def __init__(self, root=None, runner=None, printer=None, windows=None, asker=None) -> None:
        self.root = Path(root).resolve() if root else PROJECT_ROOT
        self._runner = runner or run_command
        self._print = printer or print
        self._asker = asker if asker is not None else self._ask_yes
        self.windows = (os.name == "nt") if windows is None else bool(windows)
        self.venv = self.root / ".venv"
        self._candidates: list[compat.Interpreter] | None = None

    # ------------------------------------------------------------------ 경로
    @property
    def venv_python(self) -> Path:
        return self.venv / ("Scripts/python.exe" if self.windows else "bin/python")

    @property
    def deps_ok(self) -> Path:
        return self.venv / ".deps_ok"

    @property
    def audio_ok(self) -> Path:
        return self.venv / ".audio_ok"

    @property
    def audio_skip(self) -> Path:
        return self.venv / ".audio_skip"

    @property
    def info_path(self) -> Path:
        return self.venv / ".venv_info.json"

    def log(self, message: str = "") -> None:
        self._print(message)

    # ------------------------------------------------------------- 사용자 확인
    def can_ask(self) -> bool:
        """창에서 직접 물어볼 수 있는 상황인가(테스트·자동 실행에서는 물어보지 않는다)."""
        try:
            return bool(sys.stdin and sys.stdin.isatty())
        except (AttributeError, OSError):
            return False

    def ask(self, question: str) -> bool:
        return bool(self._asker(question))

    @staticmethod
    def _ask_yes(question: str) -> bool:
        try:
            answer = input(f"  {question} [y/N] ").strip().lower()
        except (EOFError, OSError, KeyboardInterrupt):
            return False
        return answer in {"y", "yes"}

    def _run(self, cmd, timeout=None) -> RunResult:
        return self._runner(list(cmd), timeout=timeout)

    # -------------------------------------------------------------- 인터프리터
    def probe(self, cmd) -> compat.Interpreter | None:
        """`cmd` 가 파이썬이면 버전·비트를 읽어 온다."""
        cmd = list(cmd)
        result = self._run(cmd + ["-c", PROBE_CODE], timeout=30)
        if not result.ok:
            return None
        match = re.search(r"(\d+)\.(\d+)\s+(\d+)", result.out)
        if not match:
            return None
        return compat.Interpreter(
            version=(int(match.group(1)), int(match.group(2))),
            bits=int(match.group(3)),
            label=" ".join(cmd),
            path=cmd[-1],
            command=tuple(cmd),
        )

    def candidates(self) -> list[compat.Interpreter]:
        if self._candidates is not None:
            return self._candidates
        if self.windows:
            commands = [
                ["py", "-3.12"],
                ["py", "-3.11"],
                ["py", "-3.10"],
                ["py", "-3.13"],
                ["py", "-3"],
                ["python"],
                ["python3"],
            ]
        else:
            commands = [["python3"], ["python"], ["python3.12"], ["python3.11"], ["python3.10"]]
        found: list[compat.Interpreter] = []
        for cmd in commands:
            interp = self.probe(cmd)
            if interp is not None:
                found.append(interp)
        # 이 스크립트를 돌리는 Python 도 후보에 넣는다(venv 안에서 실행해도 동작하도록)
        found.append(compat.current_interpreter())
        self._candidates = compat.dedupe([i for i in found if tuple(i.version) >= compat.MIN_PYTHON])
        return self._candidates

    def best(self) -> compat.Interpreter | None:
        return compat.choose_best(self.candidates())

    def venv_state(self) -> compat.Interpreter | None:
        if not self.venv_python.exists():
            return None
        return self.probe([str(self.venv_python)])

    # ------------------------------------------------------------------ .venv
    def quarantine(self) -> bool:
        """쓸 수 없는 .venv 를 지우지 않고 옆으로 옮긴다."""
        if not self.venv.exists():
            return True
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        target = self.root / f".venv.broken-{stamp}"
        index = 2
        while target.exists():
            target = self.root / f".venv.broken-{stamp}-{index}"
            index += 1
        try:
            self.venv.rename(target)
        except OSError as exc:
            self.log(f"  ! 기존 .venv 폴더를 정리하지 못했습니다: {exc}")
            self.log("    → 탐색기에서 .venv 폴더를 지운 뒤 다시 실행해 주세요. (지워도 되는 임시 폴더입니다)")
            return False
        self.log(f"  · 기존 .venv 를 '{target.name}' 으로 옮겨 두었습니다 (필요 없으면 지워도 됩니다)")
        return True

    def write_info(self, state: compat.Interpreter | None) -> None:
        if state is None:
            return
        data = {
            "python": state.version_text,
            "bits": state.bits,
            "executable": str(self.venv_python),
            "label": state.label,
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
        try:
            self.info_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError:
            pass

    def _skip_reason(self) -> str:
        try:
            return str(json.loads(self.audio_skip.read_text(encoding="utf-8")).get("reason") or "")
        except (OSError, ValueError):
            return ""

    def ensure_venv(self) -> bool:
        """.venv 가 쓸 수 있는 상태인지 확인하고, 필요하면 새로 만든다."""
        state = self.venv_state()
        best = self.best()
        rebuild = compat.venv_needs_rebuild(state, best)

        # 음성 패키지가 '이 Python 버전에는 wheel 이 없어서' 실패했었고,
        # 권장 버전(3.10~3.12) Python 이 준비되어 있으면 그 Python 으로 다시 만든다.
        if (
            state is not None
            and not rebuild
            and best is not None
            and tuple(best.version) != tuple(state.version)
            and tuple(best.version) in compat.PREFERRED_ORDER
            and self._skip_reason() == "wheel"
        ):
            rebuild = True
            self.log(
                f"  · 음성 변환 패키지가 Python {state.version_text} 과 맞지 않아 "
                f"Python {best.version_text} 로 .venv 를 다시 만듭니다"
            )

        if state is not None and not rebuild:
            self.log(f"  · .venv 사용: {state.describe()}")
            self.write_info(state)
            return True

        if self.venv.exists() and not self.quarantine():
            return False

        if best is None:
            self.log("  ✗ Python 3.9 이상을 찾지 못했습니다.")
            self._print_missing_python()
            return False

        self.log(f"  · 사용할 Python: {best.describe()}")
        self.log("  · .venv 를 새로 만듭니다 ...")
        result = self._run(best.argv + ["-m", "venv", str(self.venv)], timeout=600)
        if not result.ok:
            self.log("  ✗ .venv 를 만들지 못했습니다.")
            for line in compat.summarize_pip_failure(result.out):
                self.log("    " + line)
            self.log("    → Python 을 다시 설치한 뒤 실행해 주세요. (Windows: 설치 화면에서 Add to PATH 체크)")
            return False

        state = self.venv_state()
        if state is None:
            self.log("  ✗ .venv 안에 파이썬이 생기지 않았습니다. Python 설치 상태를 확인해 주세요.")
            return False
        self.write_info(state)
        self.log(f"  ✓ .venv 준비 완료: {state.describe()}")
        return True

    def _print_missing_python(self) -> None:
        self.log("    설치:  winget install -e --id " + compat.WINGET_ID)
        self.log("    또는 " + compat.PYTHON_DOWNLOADS + " 에서 'Windows installer (64-bit)' 3.12")
        self.log("    ※ 32비트가 아닌 64비트를 고르세요. 설치 화면에서 'Add python.exe to PATH' 체크.")

    # ------------------------------------------------------------ 파이썬 설치
    def install_python(self) -> bool:
        """winget 으로 64비트 Python 3.12 설치를 시도한다(사용자가 동의했을 때만 부른다)."""
        if not self.windows:
            self.log("  · 자동 설치은 Windows 에서만 됩니다. python.org 에서 설치해 주세요.")
            return False
        self.log("  · 64비트 Python 3.12 설치를 시작합니다 (winget, 몇 분 걸릴 수 있습니다) ...")
        result = self._run(
            [
                "winget",
                "install",
                "-e",
                "--id",
                compat.WINGET_ID,
                "--accept-source-agreements",
                "--accept-package-agreements",
                "--disable-interactivity",
            ],
            timeout=1800,
        )
        if not result.ok:
            self.log("  ! 자동 설치가 되지 않았습니다(winget 없음·인터넷 등). 화면 안내대로 직접 설치해 주세요.")
            return False
        self._candidates = None  # 새로 설치된 Python 을 다시 찾는다
        best = self.best()
        if best is not None and compat.is_audio_ready(best.version, best.bits):
            self.log(f"  ✓ Python 설치 완료: {best.describe()}")
            return True
        self.log("  ! 설치는 되었지만 새 Python 을 아직 찾지 못했습니다. 이 창을 닫고 '설치_점검.bat' 을 다시 실행해 주세요.")
        return False

    # ------------------------------------------------------------- 필수 패키지
    def check_core_import(self) -> bool:
        if not self.venv_python.exists():
            return False
        return self._run([str(self.venv_python), "-c", "import docx"], timeout=120).ok

    def install_core(self, force: bool = False) -> bool:
        if not force and self.deps_ok.exists() and self.check_core_import():
            self.log("  · 필수 패키지: 이미 설치됨")
            return True
        vpy = str(self.venv_python)
        self.log("  · 필수 패키지 설치 중 ... (통화록 .md/.docx 를 만드는 데 필요)")
        self._run([vpy, "-m", "pip", "install", "--upgrade", "pip", "--disable-pip-version-check", "--no-input"], timeout=900)
        result = self._run(
            [
                vpy,
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "--no-input",
                "-r",
                str(self.root / CORE_REQUIREMENTS),
            ],
            timeout=1800,
        )
        if not result.ok or not self.check_core_import():
            self.log("  ✗ 필수 패키지 설치에 실패했습니다.")
            for line in compat.summarize_pip_failure(result.out):
                self.log("    " + line)
            self.log("    · 인터넷 연결을 확인한 뒤 다시 실행해 주세요.")
            self.log(f"    · 직접 설치: \"{vpy}\" -m pip install -r {CORE_REQUIREMENTS}")
            return False
        try:
            self.deps_ok.write_text(
                json.dumps({"installed_at": datetime.now().isoformat(timespec="seconds")}, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError:
            pass
        self.log("  ✓ 필수 패키지 준비 완료 — .txt 통화록 변환을 바로 쓸 수 있습니다.")
        return True

    # -------------------------------------------------------------- 음성 패키지
    def probe_audio(self) -> compat.AudioProbe:
        """이 .venv 에서 음성 변환이 실제로 되는지 확인한다.

        `import faster_whisper` 만 보면 av 버전이 faster-whisper 와 맞지 않아도 통과해 버린다
        (PyAV 19 부터 av.open 의 metadata_errors 인자가 없어져 .m4a 디코딩에서 실패).
        그래서 .venv 안에서 av.open 을 그 인자로 직접 불러 보고, 짧은 wav 를
        decode_audio 로 디코딩해 보기까지 한다.
        """
        if not self.venv_python.exists():
            return compat.AudioProbe()
        result = self._run([str(self.venv_python), "-c", compat.AUDIO_PROBE_CODE], timeout=180)
        return compat.parse_audio_probe(result.code, result.out)

    def check_audio_runtime(self) -> bool:
        """음성 변환 패키지가 지금 상태로 쓸 수 있는가."""
        return self.probe_audio().ok

    def write_skip(self, reason: str, detail: str = "") -> None:
        payload = {
            "reason": reason,
            "detail": detail,
            "python": (self.venv_state() or compat.current_interpreter()).describe(),
            "at": datetime.now().isoformat(timespec="seconds"),
        }
        try:
            self.audio_skip.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError:
            pass

    def clear_skip(self) -> None:
        for path in (self.audio_skip,):
            try:
                if path.exists():
                    path.unlink()
            except OSError:
                pass

    def mark_audio_ok(self, av_version: str = "") -> None:
        self.clear_skip()
        try:
            self.audio_ok.write_text(
                json.dumps(
                    {
                        "ready_at": datetime.now().isoformat(timespec="seconds"),
                        # 이 표시가 없으면(옛 설치) 실행 .bat 이 '설치_점검' 을 한 번 돌려
                        # av 버전까지 확인해 준다.
                        "probe": True,
                        "av": av_version,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
        except OSError:
            pass

    def print_audio_help(self, interpreter: compat.Interpreter | None, detail=None) -> None:
        if detail:
            for line in detail:
                self.log("    " + line)
        self.log("")
        for line in compat.audio_help_lines(interpreter):
            self.log(line)
        self.log("")

    def ensure_audio(self, force: bool = False, core_only: bool = False) -> str:
        """음성 변환 패키지 상태. 'present' | 'installed' | 'skipped' | 'unsupported' | 'failed'"""
        if core_only:
            self.log("  · 음성 변환 패키지는 건너뜁니다 (--core-only)")
            return "skipped"

        state = self.venv_state()
        if state is None:
            return "failed"

        probe = self.probe_audio()
        if probe.ok:
            self.mark_audio_ok(probe.av_version)
            av = f", av {probe.av_version}" if probe.av_version else ""
            self.log(f"  · 음성 변환: 사용 가능 (faster-whisper{av} 설치됨)")
            return "present"

        # 패키지는 다 깔려 있는데 오디오 라이브러리(av)만 faster-whisper 와 안 맞는 경우
        # (예: av 19 이상이 함께 깔려 .m4a 를 읽지 못함) → 버전만 바로잡아 다시 설치한다.
        if probe.broken_av:
            self.log(f"  ! {compat.audio_probe_problem(probe)}")
            self.log("  · 맞는 버전(av<19)으로 다시 설치합니다 ...")
            force = True

        if not compat.is_audio_ready(state.version, state.bits):
            if force or not self.audio_skip.exists():
                self.write_skip("unsupported", compat.describe_audio_problem(state))
            self.log("  ! 이 Python 으로는 음성 변환 패키지를 설치할 수 없습니다.")
            self.print_audio_help(state)
            return "unsupported"

        if self.audio_skip.exists() and not force:
            blocked = self._skip_detail()
            self.log("  ! 음성 변환 패키지는 이전에 설치에 실패해 건너뜁니다. (.txt 변환은 정상)")
            if blocked:
                self.log("    " + blocked)
            self.log("    다시 시도하려면 '설치_점검.bat' 을 실행하세요.")
            return "skipped"

        vpy = str(self.venv_python)
        if probe.faster_whisper:
            self.log("  · 음성 변환 패키지의 오디오 라이브러리를 맞는 버전으로 교체합니다 ...")
        else:
            self.log("  · 음성 변환 패키지(faster-whisper) 설치 중 ... 처음 한 번만, 몇 분 걸릴 수 있습니다")
        result = self._run(
            [
                vpy,
                "-m",
                "pip",
                "install",
                # 이미 깔린 av 가 요구 버전(av<19)을 벗어나 있으면 이 옵션이 있어야 교체된다
                "--upgrade",
                # 소스를 받아 직접 빌드하지 않고, 미리 만들어진 wheel 만 쓴다
                # (av-*.tar.gz 빌드 시도로 몇십 분씩 걸리는 일을 막는다)
                "--only-binary=:all:",
                "--disable-pip-version-check",
                "--no-input",
                "-r",
                str(self.root / AUDIO_REQUIREMENTS),
            ],
            timeout=3600,
        )
        after = self.probe_audio()
        if result.ok and after.ok:
            self.mark_audio_ok(after.av_version)
            self.log("  ✓ 음성 변환 준비 완료 — 녹음 파일(.m4a/.mp3/...)도 변환됩니다.")
            return "installed"

        if result.ok and not after.ok:
            # 설치 명령은 성공했는데 실제 점검이 실패한 경우(드묾) — 이유를 그대로 보여 준다
            self.log("  ! 음성 패키지는 설치되었지만 점검을 통과하지 못했습니다.")
            self.log("    " + compat.audio_probe_problem(after))

        detail = compat.summarize_pip_failure(result.out)
        packages = compat.missing_packages(result.out)
        if compat.looks_like_missing_wheel(result.out):
            # 이 환경에는 맞는 wheel 이 없다 → 다음 실행에서 또 몇 분을 쓰지 않게 기록해 둔다
            self.write_skip("wheel", compat.describe_audio_problem(state) + (f" ({', '.join(packages)})" if packages else ""))
            self.log("  ! 이 환경에 맞는 음성 변환 패키지가 없습니다.")
        else:
            self.log("  ! 음성 변환 패키지 설치가 끝나지 않았습니다(인터넷 문제일 수 있습니다).")
        self.print_audio_help(state, detail)
        return "failed"

    def _skip_detail(self) -> str:
        try:
            data = json.loads(self.audio_skip.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return ""
        detail = str(data.get("detail") or "").strip()
        return detail

    # ------------------------------------------------------------------ 상태
    def status_lines(self) -> list[str]:
        lines = [f"  · 실행 중인 Python: {compat.current_interpreter().describe()}"]
        state = self.venv_state()
        if state is not None:
            lines.append(f"  · .venv: {state.describe()}")
        elif self.venv.exists():
            lines.append("  · .venv: 깨진 상태(파이썬 없음) — 다음 실행 때 새로 만듭니다")
        else:
            lines.append("  · .venv: 아직 없음 — 처음 실행 때 만듭니다")
        best = self.best()
        lines.append(f"  · 쓸 수 있는 Python 중 최적: {best.describe() if best else '없음(3.9 이상 필요)'}")
        lines.append(f"  · 필수 패키지(python-docx): {'설치됨' if self.deps_ok.exists() else '미설치'}")
        probe = self.probe_audio()
        if probe.ok:
            av = f" (av {probe.av_version})" if probe.av_version else ""
            lines.append(f"  · 음성 변환(faster-whisper): 사용 가능{av}")
            return lines
        lines.append("  · 음성 변환(faster-whisper): 미설치 — .txt 만 변환됩니다")
        if probe.broken_av:
            lines[-1] = "  · 음성 변환(faster-whisper): 지금은 쓸 수 없습니다 — .txt 만 변환됩니다"
            lines.append(f"    ! {compat.audio_probe_problem(probe)}")
            lines.append("    → '설치_점검.bat' 을 실행하면 맞는 버전으로 자동으로 고칩니다.")
        elif state is not None:
            lines.extend(["", *compat.audio_help_lines(state)])
        return lines

    # ------------------------------------------------------------------- 실행
    def _wants_install(self, install_python: bool, offer_install: bool) -> bool:
        """64비트 3.12 설치를 지금 할지. (--install-python 이면 바로, 아니면 물어보고)"""
        if install_python:
            return True
        return bool(
            offer_install
            and self.windows
            and self.can_ask()
            and self.ask("지금 64비트 Python 3.12 를 자동으로 설치할까요?")
        )

    def prepare(self, repair: bool = False, core_only: bool = False, install_python: bool = False, offer_install: bool = False) -> int:
        self.log("=" * 58)
        self.log("  통화록 변환기 — 환경 준비")
        self.log("=" * 58)
        if not self.ensure_venv():
            # 쓸 만한 Python 이 아예 없을 때도 설치를 권할 수 있다
            if not (self._wants_install(install_python, offer_install) and self.install_python() and self.ensure_venv()):
                return 1
        if not self.install_core(force=False):
            return 1
        status = self.ensure_audio(force=repair, core_only=core_only)

        # 음성 패키지가 '이 PC 의 Python' 때문에 막혔으면 64비트 3.12 설치를 권하고,
        # 사용자가 동의하면 바로 설치해 다시 준비한다.
        wheel_problem = status == "unsupported" or (status == "failed" and self._skip_reason() == "wheel")
        if wheel_problem and not core_only and self.windows:
            if self._wants_install(install_python, offer_install) and self.install_python():
                self.log("")
                self.log("  · 새 Python 으로 .venv 를 다시 준비합니다")
                if not self.ensure_venv():
                    return 1
                if not self.install_core(force=True):
                    return 1
                status = self.ensure_audio(force=True)

        self.log("")
        self.log("-" * 58)
        self.log("  [준비 완료] .txt 통화록 변환: 사용 가능")
        if status in {"present", "installed"}:
            self.log("             음성 파일 변환: 사용 가능")
        else:
            self.log("             음성 파일 변환: 사용 안 함 (위 안내를 참고해 주세요)")
        self.log("-" * 58)
        # 음성 변환이 안 되어도 프로그램(.txt 변환)은 바로 쓸 수 있으므로 성공으로 본다
        return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="setup_env",
        description="call-log-maker 의 .venv 와 패키지를 준비합니다.",
    )
    parser.add_argument("--repair", action="store_true", help="음성 변환 패키지 설치를 처음부터 다시 시도")
    parser.add_argument("--core-only", action="store_true", help=".txt 변환용 필수 패키지만 설치")
    parser.add_argument("--ask-install", action="store_true", help="음성 패키지가 안 되면 64비트 Python 3.12 설치를 물어본다")
    parser.add_argument("--install-python", action="store_true", help="64비트 Python 3.12 설치를 바로 시도(winget)")
    parser.add_argument("--check", action="store_true", help="아무것도 바꾸지 않고 상태만 확인")
    parser.add_argument("--root", help="프로젝트 폴더 (기본: 이 파일이 있는 폴더)")
    return parser


def main(argv=None, runner=None, printer=None, asker=None) -> int:
    _fix_console()
    args = build_parser().parse_args(argv)
    setup = Setup(root=args.root, runner=runner, printer=printer, asker=asker)
    if args.check:
        for line in setup.status_lines():
            setup.log(line)
        return 0
    return setup.prepare(
        repair=args.repair,
        core_only=args.core_only,
        install_python=args.install_python,
        offer_install=args.ask_install,
    )


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
