import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

import setup_env
from calllog import compat

REAL_ERROR = (
    "ERROR: Cannot install faster-whisper==1.2.1 because these package versions have conflicting dependencies.\n"
    "    faster-whisper 1.2.1 depends on onnxruntime<2 and >=1.14\n"
    "Additionally, some packages in these conflicts have no matching distributions available for your "
    "environment: onnxruntime\n"
    "ERROR: ResolutionImpossible\n"
)


class FakeRunner:
    """실제 프로세스를 띄우지 않고 setup_env 의 판단 흐름만 검증한다."""

    def __init__(
        self,
        venv=(3, 12, 64),
        interpreters=None,
        audio_pip=(0, ""),
        core_pip=(0, ""),
        docx=True,
        whisper=False,
        venv_python_name="bin/python",
    ):
        self.venv = venv
        self.interpreters = interpreters if interpreters is not None else {"python3": (3, 12, 64)}
        self.audio_pip = audio_pip
        self.core_pip = core_pip
        self.docx = docx
        self.whisper = whisper
        self.venv_python_name = venv_python_name
        self.venv_path = None
        self.calls = []
        self.audio_attempted = False

    # ------------------------------------------------------------------ util
    @staticmethod
    def _fmt(spec):
        return "%d.%d %d" % spec

    def pip_calls(self, need=None):
        found = [c for c in self.calls if "install" in c and "-m" in c and "pip" in c]
        if need:
            found = [c for c in found if any(need in part for part in c)]
        return found

    def venv_creations(self):
        return [c for c in self.calls if "-m" in c and "venv" in c]

    # --------------------------------------------------------------- runner
    def __call__(self, cmd, timeout=None):
        cmd = [str(part) for part in cmd]
        self.calls.append(cmd)

        if cmd[-1] == setup_env.PROBE_CODE:
            if self.venv_path and cmd[0] == self.venv_path:
                if self.venv is None:
                    return setup_env.RunResult(1, "")
                return setup_env.RunResult(0, self._fmt(self.venv))
            spec = self.interpreters.get(" ".join(cmd[:-2]))
            if spec is None:
                return setup_env.RunResult(1, "not found")
            return setup_env.RunResult(0, self._fmt(spec))

        if "-m" in cmd and "venv" in cmd:
            target = Path(cmd[cmd.index("venv") + 1])
            python = target / self.venv_python_name
            python.parent.mkdir(parents=True, exist_ok=True)
            python.write_text("")
            return setup_env.RunResult(0, "")

        if cmd[-1] == "import docx":
            return setup_env.RunResult(0, "") if self.docx else setup_env.RunResult(1, "ModuleNotFoundError: docx")

        if cmd[-1] == "import faster_whisper":
            ok = self.whisper or self.audio_attempted
            return setup_env.RunResult(0, "") if ok else setup_env.RunResult(1, "ModuleNotFoundError")

        if "install" in cmd:
            if any(part.endswith("requirements-audio.txt") for part in cmd):
                self.audio_attempted = True
                return setup_env.RunResult(*self.audio_pip)
            if any(part.endswith("requirements.txt") for part in cmd):
                return setup_env.RunResult(*self.core_pip)
            return setup_env.RunResult(0, "")  # pip upgrade 등

        return setup_env.RunResult(0, "")


class SetupTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "requirements.txt").write_text("python-docx>=1.1.0,<2\n", encoding="utf-8")
        (self.root / "requirements-audio.txt").write_text(
            "-r requirements.txt\nfaster-whisper>=1.1.0,<2\n", encoding="utf-8"
        )
        self.lines = []

    def tearDown(self):
        self._tmp.cleanup()

    def make(self, runner, windows=False):
        runner.venv_python_name = "Scripts/python.exe" if windows else "bin/python"
        setup = setup_env.Setup(
            root=self.root,
            runner=runner,
            printer=self.lines.append,
            windows=windows,
        )
        runner.venv_path = str(setup.venv_python)
        return setup

    def output(self):
        return "\n".join(self.lines)

    def make_existing_venv(self, windows=False):
        python = self.root / ".venv" / ("Scripts/python.exe" if windows else "bin/python")
        python.parent.mkdir(parents=True, exist_ok=True)
        python.write_text("")
        return python


class ProbeTest(SetupTestCase):
    def test_reads_version_and_bits(self):
        runner = FakeRunner(interpreters={"py -3.12": (3, 12, 64)})
        setup = self.make(runner)
        found = setup.probe(["py", "-3.12"])
        self.assertEqual(found.version, (3, 12))
        self.assertEqual(found.bits, 64)
        self.assertEqual(found.argv, ["py", "-3.12"])

    def test_missing_interpreter_returns_none(self):
        setup = self.make(FakeRunner())
        self.assertIsNone(setup.probe(["py", "-3.99"]))

    def test_windows_tries_py_launcher_first(self):
        runner = FakeRunner(interpreters={"py -3.12": (3, 12, 64), "py -3": (3, 13, 32)})
        setup = self.make(runner, windows=True)
        with mock.patch.object(compat, "current_interpreter", lambda: compat.Interpreter((3, 13), 32, "boot")):
            candidates = setup.candidates()
        self.assertEqual(candidates[0].label, "py -3.12")
        self.assertEqual(setup.best().version, (3, 12))


class VenvTest(SetupTestCase):
    def test_creates_venv_when_missing(self):
        runner = FakeRunner()
        setup = self.make(runner)
        self.assertTrue(setup.ensure_venv())
        self.assertEqual(len(runner.venv_creations()), 1)
        self.assertTrue(setup.venv_python.exists())
        self.assertTrue(setup.info_path.exists())
        self.assertIn("준비 완료", self.output())

    def test_broken_venv_is_moved_aside_not_deleted(self):
        broken = self.root / ".venv"
        (broken).mkdir()
        (broken / "leftover.txt").write_text("보존", encoding="utf-8")
        runner = FakeRunner()
        setup = self.make(runner)
        self.assertTrue(setup.ensure_venv())
        self.assertTrue(broken.exists(), "새 .venv 가 만들어졌다")
        saved = list(self.root.glob(".venv.broken-*"))
        self.assertEqual(len(saved), 1)
        self.assertTrue((saved[0] / "leftover.txt").exists(), "옛 .venv 내용은 보존된다")
        self.assertEqual(len(runner.venv_creations()), 1)

    def test_good_venv_is_reused(self):
        self.make_existing_venv()
        runner = FakeRunner(venv=(3, 12, 64))
        setup = self.make(runner)
        self.assertTrue(setup.ensure_venv())
        self.assertEqual(runner.venv_creations(), [])

    def test_32bit_venv_rebuilt_when_64bit_python_exists(self):
        self.make_existing_venv()
        runner = FakeRunner(venv=(3, 12, 32), interpreters={"python3": (3, 12, 64)})
        setup = self.make(runner)
        with mock.patch.object(compat, "current_interpreter", lambda: compat.Interpreter((3, 12), 64, "boot")):
            self.assertTrue(setup.ensure_venv())
        self.assertEqual(len(runner.venv_creations()), 1)

    def test_32bit_only_pc_keeps_venv(self):
        self.make_existing_venv()
        runner = FakeRunner(venv=(3, 12, 32), interpreters={"python3": (3, 12, 32)})
        setup = self.make(runner)
        with mock.patch.object(compat, "current_interpreter", lambda: compat.Interpreter((3, 12), 32, "boot")):
            self.assertTrue(setup.ensure_venv())
        self.assertEqual(runner.venv_creations(), [])

    def test_wheel_skipped_venv_switches_to_312_when_available(self):
        # 3.13 으로 만든 .venv 에서 음성 패키지가 wheel 문제로 실패해 두었다면,
        # 3.12 가 설치된 뒤에는 3.12 로 다시 만든다.
        self.make_existing_venv()
        runner = FakeRunner(venv=(3, 13, 64), interpreters={"python3": (3, 12, 64)})
        setup = self.make(runner)
        setup.write_skip("wheel", "onnxruntime wheel 없음")
        self.assertTrue(setup.ensure_venv())
        self.assertEqual(len(runner.venv_creations()), 1)
        self.assertIn("다시 만듭니다", self.output())

    def test_network_skipped_venv_is_not_rebuilt(self):
        self.make_existing_venv()
        runner = FakeRunner(venv=(3, 13, 64), interpreters={"python3": (3, 12, 64)})
        setup = self.make(runner)
        setup.write_skip("network", "연결 실패")
        self.assertTrue(setup.ensure_venv())
        self.assertEqual(runner.venv_creations(), [])

    def test_no_usable_python_fails_with_help(self):
        runner = FakeRunner(interpreters={})
        setup = self.make(runner)
        with mock.patch.object(compat, "current_interpreter", lambda: compat.Interpreter((3, 6), 64, "boot")):
            self.assertFalse(setup.ensure_venv())
        self.assertIn("winget install", self.output())


class CorePackagesTest(SetupTestCase):
    def test_installs_core_and_writes_marker(self):
        runner = FakeRunner(docx=True)
        setup = self.make(runner)
        setup.ensure_venv()
        self.assertTrue(setup.install_core())
        self.assertTrue(setup.deps_ok.exists())
        self.assertEqual(len(runner.pip_calls("requirements.txt")), 1)

    def test_skips_when_already_installed(self):
        runner = FakeRunner(docx=True)
        setup = self.make(runner)
        setup.ensure_venv()
        setup.install_core()
        runner.calls.clear()
        self.assertTrue(setup.install_core())
        self.assertEqual(runner.pip_calls(), [])

    def test_repairs_when_marker_exists_but_import_fails(self):
        runner = FakeRunner(docx=False)
        setup = self.make(runner)
        setup.ensure_venv()
        setup.deps_ok.write_text("{}", encoding="utf-8")
        self.assertFalse(setup.install_core())
        self.assertEqual(len(runner.pip_calls("requirements.txt")), 1)

    def test_core_failure_stops_prepare(self):
        runner = FakeRunner(docx=False, core_pip=(1, "ERROR: Could not install packages due to an OSError"))
        setup = self.make(runner)
        self.assertEqual(setup.prepare(), 1)
        self.assertIn("인터넷", self.output())


class AudioPackagesTest(SetupTestCase):
    def test_present_engine_is_detected(self):
        runner = FakeRunner(whisper=True)
        setup = self.make(runner)
        setup.ensure_venv()
        self.assertEqual(setup.ensure_audio(), "present")
        self.assertTrue(setup.audio_ok.exists())
        self.assertEqual(runner.pip_calls("requirements-audio.txt"), [])

    def test_32bit_environment_is_unsupported_and_continues(self):
        self.make_existing_venv()
        runner = FakeRunner(venv=(3, 12, 32), whisper=False, interpreters={"python3": (3, 12, 32)})
        setup = self.make(runner)
        with mock.patch.object(compat, "current_interpreter", lambda: compat.Interpreter((3, 12), 32, "boot")):
            setup.install_core()
            status = setup.ensure_audio()
        self.assertEqual(status, "unsupported")
        self.assertTrue(setup.audio_skip.exists())
        self.assertEqual(runner.pip_calls("requirements-audio.txt"), [])
        text = self.output()
        self.assertIn("32비트", text)
        self.assertIn("winget install -e --id Python.Python.3.12", text)

    def test_missing_wheel_failure_is_recorded_and_does_not_block(self):
        runner = FakeRunner(venv=(3, 12, 64), audio_pip=(1, REAL_ERROR), whisper=False)
        setup = self.make(runner)
        setup.ensure_venv()
        setup.install_core()
        status = setup.ensure_audio()
        self.assertEqual(status, "failed")
        self.assertTrue(setup.audio_skip.exists())
        payload = setup.audio_skip.read_text(encoding="utf-8")
        self.assertIn("wheel", payload)
        self.assertIn("onnxruntime", self.output())
        self.assertFalse(setup.audio_ok.exists())

    def test_network_failure_is_not_recorded_as_unsupported(self):
        runner = FakeRunner(audio_pip=(1, "ERROR: Could not install packages due to an OSError"))
        setup = self.make(runner)
        setup.ensure_venv()
        setup.install_core()
        self.assertEqual(setup.ensure_audio(), "failed")
        self.assertFalse(setup.audio_skip.exists(), "인터넷 문제는 다음에 다시 시도한다")

    def test_audio_success_marks_ready(self):
        runner = FakeRunner(audio_pip=(0, ""), whisper=False)
        setup = self.make(runner)
        setup.ensure_venv()
        setup.install_core()
        self.assertEqual(setup.ensure_audio(), "installed")
        self.assertTrue(setup.audio_ok.exists())
        self.assertFalse(setup.audio_skip.exists())
        self.assertIn("--only-binary=:all:", " ".join(runner.pip_calls("requirements-audio.txt")[0]))

    def test_previous_failure_skips_retry(self):
        runner = FakeRunner(venv=(3, 12, 64), audio_pip=(0, ""), whisper=False)
        setup = self.make(runner)
        setup.ensure_venv()
        setup.install_core()
        setup.write_skip("wheel", "onnxruntime 없음")
        runner.calls.clear()
        self.assertEqual(setup.ensure_audio(), "skipped")
        self.assertEqual(runner.pip_calls("requirements-audio.txt"), [])
        self.assertIn("설치_점검.bat", self.output())

    def test_repair_retries_after_failure(self):
        runner = FakeRunner(venv=(3, 12, 64), audio_pip=(0, ""), whisper=False)
        setup = self.make(runner)
        setup.ensure_venv()
        setup.install_core()
        setup.write_skip("wheel", "onnxruntime 없음")
        runner.calls.clear()
        self.assertEqual(setup.ensure_audio(force=True), "installed")
        self.assertEqual(len(runner.pip_calls("requirements-audio.txt")), 1)
        self.assertTrue(setup.audio_ok.exists())
        self.assertFalse(setup.audio_skip.exists(), "성공하면 건너뜀 기록을 지운다")

    def test_core_only_mode(self):
        runner = FakeRunner()
        setup = self.make(runner)
        setup.ensure_venv()
        setup.install_core()
        self.assertEqual(setup.ensure_audio(core_only=True), "skipped")
        self.assertEqual(runner.pip_calls("requirements-audio.txt"), [])


class PrepareTest(SetupTestCase):
    def test_prepare_succeeds_in_text_only_mode(self):
        self.make_existing_venv()
        runner = FakeRunner(venv=(3, 12, 32), whisper=False, interpreters={"python3": (3, 12, 32)})
        setup = self.make(runner)
        with mock.patch.object(compat, "current_interpreter", lambda: compat.Interpreter((3, 12), 32, "boot")):
            code = setup.prepare()
        self.assertEqual(code, 0, "음성 패키지가 없어도 .txt 변환은 쓸 수 있어야 한다")
        self.assertTrue(setup.deps_ok.exists())
        text = self.output()
        self.assertIn(".txt 통화록 변환: 사용 가능", text)
        self.assertIn("음성 파일 변환: 사용 안 함", text)

    def test_second_run_does_no_work(self):
        runner = FakeRunner(whisper=True)
        setup = self.make(runner)
        self.assertEqual(setup.prepare(), 0)
        runner.calls.clear()
        self.assertEqual(setup.prepare(), 0)
        self.assertEqual(runner.pip_calls(), [])
        self.assertEqual(runner.venv_creations(), [])

    def test_check_mode_changes_nothing(self):
        runner = FakeRunner()
        code = setup_env.main(["--root", str(self.root), "--check"], runner=runner, printer=self.lines.append)
        self.assertEqual(code, 0)
        self.assertFalse((self.root / ".venv").exists())
        self.assertEqual(runner.pip_calls(), [])
        self.assertIn("실행 중인 Python", self.output())

    def test_check_reports_text_only_mode(self):
        self.make_existing_venv()
        runner = FakeRunner(venv=(3, 12, 64), whisper=False)
        runner.venv_path = str(self.root / ".venv" / "bin" / "python")
        code = setup_env.main(["--root", str(self.root), "--check"], runner=runner, printer=self.lines.append)
        self.assertEqual(code, 0)
        text = self.output()
        self.assertIn(".venv:", text)
        self.assertIn("winget install", text)


if __name__ == "__main__":
    unittest.main()
