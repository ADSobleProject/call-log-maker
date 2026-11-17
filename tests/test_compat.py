import unittest

from calllog import compat


def interp(version, bits, label=""):
    return compat.Interpreter(version=version, bits=bits, label=label)


class AudioReadyTest(unittest.TestCase):
    def test_64bit_supported_versions(self):
        for version in ((3, 9), (3, 10), (3, 11), (3, 12)):
            self.assertTrue(compat.is_audio_ready(version, 64), version)

    def test_32bit_is_never_ready(self):
        for version in ((3, 9), (3, 12), (3, 13)):
            self.assertFalse(compat.is_audio_ready(version, 32), version)

    def test_too_old_is_not_ready(self):
        self.assertFalse(compat.is_audio_ready((3, 8), 64))

    def test_newer_version_still_allowed(self):
        # 3.13 도 wheel 이 있으면 설치는 된다 → 막지는 않는다
        self.assertTrue(compat.is_audio_ready((3, 14), 64))


class RankTest(unittest.TestCase):
    def test_prefers_64bit_over_32bit(self):
        best = compat.choose_best([interp((3, 12), 32), interp((3, 10), 64)])
        self.assertEqual(best.bits, 64)
        self.assertEqual(best.version, (3, 10))

    def test_prefers_312_over_313(self):
        best = compat.choose_best([interp((3, 13), 64), interp((3, 12), 64)])
        self.assertEqual(best.version, (3, 12))

    def test_prefers_311_over_310(self):
        best = compat.choose_best([interp((3, 10), 64), interp((3, 11), 64)])
        self.assertEqual(best.version, (3, 11))

    def test_ignores_python_older_than_min(self):
        self.assertIsNone(compat.choose_best([interp((3, 8), 64), interp((2, 7), 64)]))

    def test_empty(self):
        self.assertIsNone(compat.choose_best([]))

    def test_dedupe_keeps_first_label(self):
        items = [interp((3, 12), 64, "py -3.12"), interp((3, 12), 64, "python")]
        self.assertEqual([i.label for i in compat.dedupe(items)], ["py -3.12"])


class VenvRebuildTest(unittest.TestCase):
    def test_missing_venv_is_built(self):
        self.assertTrue(compat.venv_needs_rebuild(None, interp((3, 12), 64)))

    def test_good_venv_is_reused(self):
        self.assertFalse(compat.venv_needs_rebuild(interp((3, 12), 64), interp((3, 12), 64)))

    def test_32bit_venv_rebuilt_when_64bit_available(self):
        self.assertTrue(compat.venv_needs_rebuild(interp((3, 12), 32), interp((3, 12), 64)))

    def test_32bit_venv_kept_when_nothing_better(self):
        # 32비트뿐인 PC: .txt 변환은 되므로 .venv 를 다시 만들지 않는다
        self.assertFalse(compat.venv_needs_rebuild(interp((3, 12), 32), interp((3, 12), 32)))

    def test_old_venv_rebuilt(self):
        self.assertTrue(compat.venv_needs_rebuild(interp((3, 8), 64), interp((3, 12), 64)))

    def test_13_venv_kept_if_audio_ready(self):
        self.assertFalse(compat.venv_needs_rebuild(interp((3, 13), 64), interp((3, 12), 64)))


class MessageTest(unittest.TestCase):
    def test_32bit_explains_onnxruntime(self):
        text = compat.describe_audio_problem(interp((3, 12), 32))
        self.assertIn("32비트", text)
        self.assertIn("onnxruntime", text)

    def test_new_version_warns_about_wheel(self):
        self.assertIn("wheel", compat.describe_audio_problem(interp((3, 13), 64)))

    def test_no_python_message(self):
        self.assertIn("찾지 못했습니다", compat.describe_audio_problem(None))

    def test_help_lines_have_winget_and_download_page(self):
        lines = "\n".join(compat.audio_help_lines(interp((3, 12), 32)))
        self.assertIn("winget install -e --id Python.Python.3.12", lines)
        self.assertIn("python.org", lines)
        self.assertIn("설치_점검.bat", lines)
        self.assertIn(".txt", lines)

    def test_describe_includes_bits(self):
        self.assertEqual(interp((3, 12), 32).describe(), "Python 3.12 (32비트)")


class PipFailureTest(unittest.TestCase):
    # 사용자가 실제로 본 오류 문구
    REAL_ERROR = (
        "ERROR: Cannot install faster-whisper==1.2.1 because these package versions have conflicting dependencies.\n"
        "The conflict is caused by:\n"
        "    faster-whisper 1.2.1 depends on onnxruntime<2 and >=1.14\n"
        "Additionally, some packages in these conflicts have no matching distributions available for your "
        "environment: onnxruntime\n"
        "ERROR: ResolutionImpossible\n"
        "  Building wheel for av (pyproject.toml) ... error\n"
    )

    def test_recognizes_missing_wheel(self):
        self.assertTrue(compat.looks_like_missing_wheel(self.REAL_ERROR))

    def test_network_error_is_not_a_wheel_problem(self):
        text = "ERROR: Could not install packages due to an OSError: [Errno 11001] getaddrinfo failed"
        self.assertFalse(compat.looks_like_missing_wheel(text))

    def test_extracts_offending_package(self):
        self.assertIn("onnxruntime", compat.missing_packages(self.REAL_ERROR))

    def test_extracts_package_from_could_not_find(self):
        text = "ERROR: Could not find a version that satisfies the requirement ctranslate2<5,>=4.0"
        self.assertIn("ctranslate2", compat.missing_packages(text))

    def test_summarize_keeps_relevant_lines_only(self):
        lines = compat.summarize_pip_failure(self.REAL_ERROR)
        joined = "\n".join(lines)
        self.assertIn("onnxruntime", joined)
        self.assertLessEqual(len(lines), 6)
        self.assertTrue(all(line.strip() for line in lines))

    def test_summarize_limits_lines(self):
        text = "\n".join(f"ERROR: line {i}" for i in range(20))
        self.assertEqual(len(compat.summarize_pip_failure(text, limit=3)), 3)


class AudioProbeTest(unittest.TestCase):
    """음성 변환 점검 결과 해석 (av 19 에서 metadata_errors 인자가 없어진 문제)."""

    def test_ok_when_both_parts_are_fine(self):
        probe = compat.parse_audio_probe(0, '{"faster_whisper": true, "av": "18.1.0", "av_open_ok": true, "error": ""}')
        self.assertTrue(probe.ok)
        self.assertFalse(probe.broken_av)
        self.assertEqual(probe.av_version, "18.1.0")
        self.assertEqual(compat.audio_probe_problem(probe), "")

    def test_broken_av_is_detected(self):
        probe = compat.parse_audio_probe(
            4, '{"faster_whisper": true, "av": "19.0.2", "av_open_ok": false, "error": "av 19.0.2 has no metadata_errors"}'
        )
        self.assertFalse(probe.ok)
        self.assertTrue(probe.broken_av)
        problem = compat.audio_probe_problem(probe)
        self.assertIn("av 19.0.2", problem)
        self.assertIn("metadata_errors", problem)

    def test_missing_package_is_detected(self):
        probe = compat.parse_audio_probe(3, '{"faster_whisper": false, "av": "", "av_open_ok": false, "error": "ModuleNotFoundError: no"}')
        self.assertFalse(probe.ok)
        self.assertFalse(probe.broken_av)
        self.assertIn("설치되어 있지 않습니다", compat.audio_probe_problem(probe))

    def test_json_after_other_output_is_found(self):
        output = "UserWarning: symlink ...\n{\"faster_whisper\": true, \"av\": \"16.1.0\", \"av_open_ok\": true}\n"
        probe = compat.parse_audio_probe(0, output)
        self.assertTrue(probe.ok)
        self.assertEqual(probe.av_version, "16.1.0")

    def test_unreadable_output_falls_back_to_exit_code(self):
        self.assertTrue(compat.parse_audio_probe(0, "").ok)
        failed = compat.parse_audio_probe(1, "Traceback ... TypeError: open() got an unexpected keyword argument 'metadata_errors'")
        self.assertFalse(failed.ok)
        self.assertIn("metadata_errors", failed.error)

    def test_probe_code_runs_without_imports_at_hand(self):
        # 점검 스크립트는 .venv 안에서 단독으로 돌아야 하므로 ASCII 만 쓴다
        self.assertTrue(compat.AUDIO_PROBE_CODE.isascii())
        self.assertIn("metadata_errors", compat.AUDIO_PROBE_CODE)


class InterpreterTableTest(unittest.TestCase):
    def test_table_is_empty_without_interpreters(self):
        self.assertEqual(compat.interpreter_table([]), [])

    def test_table_lists_descriptions(self):
        rows = compat.interpreter_table([interp((3, 12), 64), interp((3, 13), 32)])
        self.assertEqual(len(rows), 2)
        self.assertIn("64비트", rows[0])


if __name__ == "__main__":
    unittest.main()
