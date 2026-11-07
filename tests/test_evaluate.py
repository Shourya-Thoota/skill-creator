"""Contract tests using synthetic artifacts, not model-quality tests."""

import contextlib
import copy
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock


SKILL = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("saved_output_evaluator", SKILL / "scripts/evaluate.py")
ev = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ev)


class EvaluatorTests(unittest.TestCase):
    def setUp(self):
        # Keep test-generated evidence inside the candidate tree.
        self.temp = tempfile.TemporaryDirectory(prefix="test-run-", dir=SKILL / "tests")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.outputs = self.root / "outputs"
        self.case_path = self.outputs / "case1"
        self.case_path.mkdir(parents=True)
        (self.case_path / "output.txt").write_text("Hello Straße\ncreate-skill", encoding="utf-8")

    def suite(self, assertions=None):
        return {"schema_version": 1, "cases": [{
            "id": "case1", "prompt": "A realistic saved-output task",
            "assertions": assertions or [
                {"id": "contains", "type": "required_string",
                 "file": "output.txt", "value": "Hello"}]}]}

    def run_suite(self, assertions=None, outputs=None, manual=None):
        return ev.evaluate(self.suite(assertions), outputs or self.outputs, "candidate", manual)

    def assertion(self, kind, **kwargs):
        return {"id": "check", "type": kind, **kwargs}

    def status(self, assertion):
        return self.run_suite([assertion])["cases"][0]["assertions"][0]["status"]

    def manual(self, status="pass", reviewer="user", evidence="Observed output in saved run"):
        return {"schema_version": 1, "records": [{
            "case_id": "case1", "assertion_id": "check",
            "status": status, "reviewer": reviewer, "evidence": evidence}]}

    def test_required_string_pass_and_fail(self):
        self.assertEqual(self.status(self.assertion("required_string", file="output.txt", value="Hello")), "pass")
        self.assertEqual(self.status(self.assertion("required_string", file="output.txt", value="missing")), "fail")

    def test_forbidden_string_pass_and_fail(self):
        self.assertEqual(self.status(self.assertion("forbidden_string", file="output.txt", value="absent")), "pass")
        self.assertEqual(self.status(self.assertion("forbidden_string", file="output.txt", value="Hello")), "fail")

    def test_case_sensitive_default_and_unicode_casefold(self):
        a = self.assertion("required_string", file="output.txt", value="STRASSE")
        self.assertEqual(self.status(a), "fail")
        a["case_sensitive"] = False
        self.assertEqual(self.status(a), "pass")

    def test_missing_case_all_not_run_including_absence(self):
        assertions = [
            {"id": "required", "type": "required_file", "file": "output.txt"},
            {"id": "forbidden", "type": "forbidden_file", "file": "credentials.txt"},
            {"id": "text", "type": "forbidden_string", "file": "output.txt", "value": "bad"}]
        result = self.run_suite(assertions, self.root / "unexecuted")
        self.assertEqual(result["status"], "not_run")
        self.assertEqual(result["counts"]["not_run"], 3)
        self.assertEqual(result["counts"]["pass"], 0)
        self.assertIsNone(result["counts"]["pass_rate"])

    def test_file_checks_and_existing_directory(self):
        self.assertEqual(self.status(self.assertion("required_file", file="output.txt")), "pass")
        self.assertEqual(self.status(self.assertion("required_file", file="absent.txt")), "fail")
        self.assertEqual(self.status(self.assertion("forbidden_file", file="absent.txt")), "pass")
        self.assertEqual(self.status(self.assertion("forbidden_file", file="output.txt")), "fail")
        (self.case_path / "directory").mkdir()
        self.assertEqual(self.status(self.assertion("required_file", file="directory")), "fail")
        self.assertEqual(self.status(self.assertion("forbidden_file", file="directory")), "fail")

    def test_missing_string_evidence_is_not_run_not_pass(self):
        for kind in ev.STRING_TYPES:
            self.assertEqual(self.status(self.assertion(kind, file="absent.txt", value="bad")), "not_run")

    def test_directory_and_binary_text_are_not_run(self):
        (self.case_path / "directory").mkdir()
        (self.case_path / "binary").write_bytes(b"\xff\x00")
        for file in ("directory", "binary"):
            self.assertEqual(self.status(self.assertion("forbidden_string", file=file, value="bad")), "not_run")

    def test_oversized_text_not_run(self):
        with mock.patch.object(ev, "MAX_TEXT_BYTES", 2):
            self.assertEqual(self.status(self.assertion("required_string", file="output.txt", value="Hello")), "not_run")

    def test_unreadable_text_not_run(self):
        with mock.patch.object(Path, "open", side_effect=PermissionError("denied")):
            self.assertEqual(self.status(self.assertion("required_string", file="output.txt", value="Hello")), "not_run")

    def test_symlinks_not_followed(self):
        (self.case_path / "linked").symlink_to(self.case_path / "output.txt")
        (self.case_path / "broken").symlink_to(self.root / "missing")
        (self.case_path / "parent").symlink_to(self.root, target_is_directory=True)
        for file in ("linked", "broken", "parent/secret.txt"):
            for kind in ev.FILE_TYPES:
                self.assertEqual(self.status(self.assertion(kind, file=file)), "not_run")

    def test_symlink_case_and_root_not_run(self):
        linked_root = self.root / "linked-outputs"
        linked_root.symlink_to(self.outputs, target_is_directory=True)
        self.assertEqual(self.run_suite(outputs=linked_root)["status"], "not_run")
        other_root = self.root / "other"
        other_root.mkdir()
        (other_root / "case1").symlink_to(self.case_path, target_is_directory=True)
        self.assertEqual(self.run_suite(outputs=other_root)["status"], "not_run")

    def test_manual_types_never_inferred_from_prompt(self):
        for kind in ev.MANUAL_TYPES:
            suite = self.suite([self.assertion(kind)])
            suite["cases"][0]["should_trigger"] = True
            result = ev.evaluate(suite, self.outputs, "candidate")
            self.assertEqual(result["status"], "not_run")
            self.assertEqual(result["counts"]["pass"], 0)

    def test_manual_pass_and_fail_attributed(self):
        for status in ("pass", "fail"):
            result = self.run_suite([self.assertion("human_visual")], manual=self.manual(status))
            assertion = result["cases"][0]["assertions"][0]
            self.assertEqual(assertion["status"], status)
            self.assertEqual(assertion["reviewer"], "user")
            self.assertEqual(assertion["evidence_kind"], "manual")
            ev.validate_result(result)

    def test_manual_does_not_fill_missing_case(self):
        result = self.run_suite([self.assertion("execution")], outputs=self.root / "absent",
                                manual=self.manual())
        self.assertEqual(result["status"], "not_run")

    def test_invalid_manual_records_rejected(self):
        base = self.manual()
        bad_records = []
        for key, value in [("reviewer", ""), ("evidence", " "), ("status", "not_run"),
                           ("case_id", "unknown"), ("assertion_id", "unknown")]:
            bad = copy.deepcopy(base)
            bad["records"][0][key] = value
            bad_records.append(bad)
        bad = copy.deepcopy(base)
        bad["records"].append(copy.deepcopy(bad["records"][0]))
        bad_records.append(bad)
        bad = copy.deepcopy(base)
        bad["records"][0]["command"] = "never executed"
        bad_records.append(bad)
        for bad in bad_records:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                self.run_suite([self.assertion("execution")], manual=bad)

    def test_manual_cannot_override_deterministic(self):
        with self.assertRaises(ValueError):
            self.run_suite([self.assertion("required_file", file="output.txt")], manual=self.manual())

    def test_counts_coverage_and_overall(self):
        assertions = [
            {"id": "yes", "type": "required_file", "file": "output.txt"},
            {"id": "no", "type": "required_file", "file": "missing.txt"},
            {"id": "unknown", "type": "execution"}]
        result = self.run_suite(assertions)
        self.assertEqual(result["status"], "fail")
        self.assertEqual(result["counts"], {
            "pass": 1, "fail": 1, "not_run": 1, "total": 3, "checked": 2,
            "pass_rate": 0.5, "coverage": 2 / 3})
        assertions.pop(1)
        result = self.run_suite(assertions)
        self.assertEqual(result["status"], "not_run")
        self.assertEqual(result["counts"]["pass_rate"], 1.0)
        self.assertEqual(result["counts"]["coverage"], 0.5)

    def test_invalid_paths(self):
        for file in ("../secret", "/tmp/file", "a/../../b", "a//b", "a/./b",
                     "C:/file", "a\\b", "a/", "", ".", "..", "a/\x00bad", " space "):
            with self.subTest(file=file), self.assertRaises(ValueError):
                self.run_suite([self.assertion("required_file", file=file)])

    def test_invalid_schema_fields_versions_and_ids(self):
        bad_suites = []
        for value in (0, 2, True, "1"):
            bad = self.suite()
            bad["schema_version"] = value
            bad_suites.append(bad)
        for value in ([], None, {}):
            bad = self.suite()
            bad["cases"] = value
            bad_suites.append(bad)
        bad = self.suite()
        bad["cases"].append(copy.deepcopy(bad["cases"][0]))
        bad_suites.append(bad)
        bad = self.suite()
        bad["cases"][0]["assertions"] *= 2
        bad_suites.append(bad)
        bad = self.suite()
        bad["cases"][0]["id"] = "../invalid"
        bad_suites.append(bad)
        bad = self.suite()
        bad["command"] = "unsupported"
        bad_suites.append(bad)
        for bad in bad_suites:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                ev.validate_suite(bad)

    def test_unknown_or_malformed_assertions_rejected(self):
        for assertion in (
                {"id": "a", "type": "shell", "command": "not executable"},
                {"id": "a", "type": "required_string", "file": "output.txt"},
                {"id": "a", "type": "required_string", "file": "output.txt", "value": " "},
                {"id": "a", "type": "required_string", "file": "output.txt", "value": "Hello",
                 "case_sensitive": "false"},
                {"id": "a", "type": "execution", "command": "not executable"},
                {"id": "a", "type": []}):
            with self.subTest(assertion=assertion), self.assertRaises(ValueError):
                self.run_suite([assertion])

    def test_trigger_requires_expected_boolean(self):
        suite = self.suite([self.assertion("trigger")])
        with self.assertRaises(ValueError):
            ev.validate_suite(suite)
        suite["cases"][0]["should_trigger"] = "false"
        with self.assertRaises(ValueError):
            ev.validate_suite(suite)
        suite["cases"][0]["should_trigger"] = False
        ev.validate_suite(suite)

    def test_duplicate_json_keys_and_nonfinite_constants(self):
        path = self.root / "bad.json"
        for text in ('{"a":1,"a":2}', '{"x":NaN}', '{"x":Infinity}'):
            path.write_text(text, encoding="utf-8")
            with self.subTest(text=text), self.assertRaises(ValueError):
                ev.load_json(path)

    def test_comparison_pairs_only_mutually_checked(self):
        suite = self.suite([
            {"id": "text", "type": "required_string", "file": "output.txt", "value": "Hello"},
            {"id": "manual", "type": "execution"}])
        baseline = ev.evaluate(suite, self.outputs, "baseline")
        (self.case_path / "output.txt").write_text("wrong", encoding="utf-8")
        candidate = ev.evaluate(suite, self.outputs, "candidate")
        comparison = ev.compare(baseline, candidate)
        self.assertEqual(comparison["paired"]["checked"], 1)
        self.assertEqual(comparison["paired"]["pass_rate_delta"], -1.0)
        self.assertEqual(comparison["transitions"][1]["candidate"], "not_run")
        missing = ev.evaluate(suite, self.root / "absent", "candidate")
        comparison = ev.compare(baseline, missing)
        self.assertEqual(comparison["paired"]["checked"], 0)
        self.assertIsNone(comparison["paired"]["pass_rate_delta"])

    def test_comparison_rejects_changed_prompt_or_assertion_shape(self):
        baseline = self.run_suite()
        suite = self.suite()
        suite["cases"][0]["prompt"] += " changed"
        with self.assertRaises(ValueError):
            ev.compare(baseline, ev.evaluate(suite, self.outputs, "candidate"))
        candidate = copy.deepcopy(baseline)
        candidate["cases"][0]["assertions"][0]["id"] = "other"
        with self.assertRaises(ValueError):
            ev.compare(baseline, candidate)

    def test_tampered_result_counts_status_and_evidence_rejected(self):
        result = self.run_suite()
        bad_results = []
        bad = copy.deepcopy(result)
        bad["counts"]["pass"] = 100
        bad_results.append(bad)
        bad = copy.deepcopy(result)
        bad["cases"][0]["assertions"][0]["status"] = "maybe"
        bad_results.append(bad)
        bad = copy.deepcopy(result)
        bad["cases"][0]["assertions"][0]["evidence_kind"] = "manual"
        bad_results.append(bad)
        for bad in bad_results:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                ev.compare(result, bad)

    def test_repeat_summary_uses_only_observed_rates(self):
        first = self.run_suite()
        (self.case_path / "output.txt").write_text("wrong", encoding="utf-8")
        second = self.run_suite()
        missing = self.run_suite(outputs=self.root / "absent")
        summary = ev.summarize([first, second, missing])
        self.assertEqual(summary["run_count"], 3)
        self.assertEqual(summary["observed_rate_count"], 2)
        self.assertEqual(summary["mean_pass_rate"], 0.5)
        self.assertAlmostEqual(summary["sample_stddev_pass_rate"], 2 ** -0.5)
        self.assertEqual(summary["pooled_counts"]["not_run"], 1)
        single = ev.summarize([first])
        self.assertIsNone(single["sample_stddev_pass_rate"])
        unknown = ev.summarize([missing])
        self.assertIsNone(unknown["mean_pass_rate"])
        second["label"] = "baseline"
        with self.assertRaises(ValueError):
            ev.summarize([first, second])

    def test_cli_success_is_not_assertion_success(self):
        cases = self.root / "cases.json"
        cases.write_text(json.dumps(self.suite()), encoding="utf-8")
        result = self.root / "result.json"
        code = ev.main(["evaluate", "--cases", str(cases), "--outputs", str(self.root / "absent"),
                        "--label", "candidate", "--out", str(result)])
        self.assertEqual(code, 0)
        self.assertEqual(ev.load_json(result)["status"], "not_run")
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(ev.main(["compare", str(result), str(result)]), 0)
        self.assertIn('"paired"', output.getvalue())

    def test_cli_invalid_input_duplicate_repeat_and_overwrites_rejected(self):
        cases = self.root / "cases.json"
        cases.write_text(json.dumps(self.suite()), encoding="utf-8")
        result = self.root / "result.json"
        result.write_text(json.dumps(self.run_suite()), encoding="utf-8")
        commands = [
            ["evaluate", "--cases", str(cases), "--outputs", str(self.outputs), "--label", "x", "--out", str(cases)],
            ["evaluate", "--cases", str(cases), "--outputs", str(self.outputs), "--label", "x", "--out", str(self.outputs / "result.json")],
            ["summarize", str(result), str(result)],
            ["evaluate", "--cases", str(self.root / "missing.json"), "--outputs", str(self.outputs), "--label", "x"]]
        for command in commands:
            with self.subTest(command=command), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(ev.main(command), 2)

    def test_example_fixture_results_are_not_full_passes(self):
        suite = ev.load_json(SKILL / "examples/cases.json")
        baseline = ev.evaluate(suite, SKILL / "examples/baseline", "baseline")
        candidate = ev.evaluate(suite, SKILL / "examples/candidate", "candidate")
        self.assertEqual(baseline["counts"]["fail"], 3)
        self.assertEqual(candidate["counts"]["pass"], 6)
        self.assertEqual(candidate["counts"]["not_run"], 6)
        self.assertEqual(candidate["status"], "not_run")
        self.assertEqual(ev.compare(baseline, candidate)["paired"]["checked"], 6)

    def test_schema_json_is_readable_and_declares_supported_types(self):
        schema = ev.load_json(SKILL / "references/cases.schema.json")
        self.assertEqual(schema["properties"]["schema_version"]["const"], 1)
        kinds = set()
        for branch in schema["$defs"]["assertion"]["oneOf"]:
            kinds.update(branch["properties"]["type"]["enum"])
        self.assertEqual(kinds, ev.TYPES)

    def test_schema_path_pattern_agrees_with_runtime(self):
        schema = ev.load_json(SKILL / "references/cases.schema.json")
        pattern = schema["$defs"]["path"]["pattern"]
        for file in ("output.txt", "nested/artifact.docx", "with spaces/file.txt",
                     "../secret", "/absolute", "C:/file", "a\\b", "a//b", "a/./b",
                     "a/../b", "a/", ".", "..", "", " ", " space ", "a/\x00bad"):
            with self.subTest(file=file):
                self.assertEqual(bool(ev.re.search(pattern, file)), bool(ev.valid_path(file)))

    def test_arbitrary_command_text_is_checked_as_literal_only(self):
        literal = "__import__('os').system('never execute')"
        (self.case_path / "output.txt").write_text(literal, encoding="utf-8")
        with mock.patch("os.system", side_effect=AssertionError("Must not execute")):
            self.assertEqual(self.status(self.assertion(
                "required_string", file="output.txt", value=literal)), "pass")


if __name__ == "__main__":
    unittest.main()
