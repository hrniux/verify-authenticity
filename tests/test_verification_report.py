"""Check reports using real historical objects and isolated altered checkouts."""

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


REPOSITORY = Path(__file__).resolve().parents[1]
COMMAND = REPOSITORY / "scripts/verification_report.py"
SOURCE = Path("src/main/java/com/example/verify/AuthenticityDemo.java")
FIRST = "416966f10555d78847e15616fb017095625b0127"
SIXTH = "aa002fb59e5505e31143c1b98b29b4e9f55c8653"


class VerificationReportTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "checkout"
        subprocess.run(
            ["git", "clone", "--shared", "--quiet", "--no-checkout", str(REPOSITORY), str(self.root)],
            check=True, capture_output=True,
        )
        subprocess.run(["git", "-C", str(self.root), "checkout", "--quiet", "HEAD", "--", "."], check=True)

    def run_report(self, *extra):
        result = subprocess.run(
            [sys.executable, "-B", str(COMMAND), "--repo", str(self.root), *map(str, extra)],
            text=True, capture_output=True,
        )
        self.assertIn(result.returncode, (0, 1), result.stdout + result.stderr)
        self.assertEqual(result.stderr, "", result.stderr)
        return result, json.loads(result.stdout) if result.stdout else None

    def test_report_verifies_all_rounds_and_screenshots_from_real_objects(self):
        result, report = self.run_report()
        self.assertEqual(result.returncode, 0, report)
        self.assertTrue(report["ok"])
        self.assertEqual(report["schema_version"], 1)
        self.assertEqual(report["errors"], [])
        self.assertEqual([r["round"] for r in report["historical_rounds"]], list(range(1, 7)))
        first = report["historical_rounds"][0]
        self.assertEqual(first["commit"], FIRST)
        self.assertEqual(first["actual"]["author"], "张三2026 <zhangsan2026@example.invalid>")
        self.assertEqual(first["actual"]["source_created_by"], "李四9527")
        self.assertEqual(first["actual"]["date"], "2026-07-21T12:18:19+08:00")
        self.assertEqual(first["actual"]["signature"], "N")
        self.assertEqual(len(report["screenshots"]), 3)
        self.assertTrue(all(r["ok"] for r in report["historical_rounds"]))
        self.assertTrue(all(r["actual_sha256"] == r["expected_sha256"] for r in report["screenshots"]))
        self.assertIn("real-world identity", " ".join(report["limitations"]))

    def test_log_creator_mismatch_is_detected_against_historical_source(self):
        log = self.root / "evidence/operation-log.txt"
        log.write_text(log.read_text(encoding="utf-8").replace("source_created_by=李四9527", "source_created_by=Altered", 1), encoding="utf-8")
        result, report = self.run_report()
        self.assertEqual(result.returncode, 1)
        first = report["historical_rounds"][0]
        self.assertFalse(first["ok"])
        self.assertEqual(first["expected"]["source_created_by"], "Altered")
        self.assertEqual(first["actual"]["source_created_by"], "李四9527")
        self.assertIn("source_created_by", " ".join(first["errors"]))

    def test_each_logged_metadata_field_is_compared_to_objects(self):
        log = self.root / "evidence/operation-log.txt"
        original = log.read_text(encoding="utf-8")
        for key in ("author", "committer", "date", "signature", "subject"):
            with self.subTest(key=key):
                lines = original.splitlines()
                index = next(i for i, line in enumerate(lines) if line.startswith(key + "="))
                lines[index] = key + "=Altered"
                log.write_text("\n".join(lines) + "\n", encoding="utf-8")
                result, report = self.run_report()
                self.assertEqual(result.returncode, 1)
                self.assertIn(key, " ".join(report["historical_rounds"][0]["errors"]))

    def test_log_cannot_redirect_anchored_commits(self):
        log = self.root / "evidence/operation-log.txt"
        log.write_text(log.read_text(encoding="utf-8").replace(FIRST, SIXTH), encoding="utf-8")
        result, report = self.run_report()
        self.assertEqual(result.returncode, 1)
        self.assertIn("anchored commit", " ".join(report["errors"]))

    def test_missing_historical_objects_produce_failing_json(self):
        shutil.rmtree(self.root / ".git")
        subprocess.run(["git", "init", "--quiet", str(self.root)], check=True)
        result, report = self.run_report()
        self.assertEqual(result.returncode, 1)
        self.assertEqual(len(report["historical_rounds"]), 6)
        self.assertIn("unavailable", " ".join(report["historical_rounds"][0]["errors"]))
        self.assertFalse(report["ok"])

    def test_modified_and_missing_screenshots_are_detected(self):
        image = self.root / "evidence/screenshots/terminal-operation-log.png"
        image.write_bytes(b"controlled altered copy")
        result, report = self.run_report()
        self.assertEqual(result.returncode, 1)
        item = next(x for x in report["screenshots"] if x["path"].endswith(image.name))
        self.assertFalse(item["ok"])
        self.assertNotEqual(item["actual_sha256"], item["expected_sha256"])
        image.unlink()
        result, report = self.run_report()
        self.assertEqual(result.returncode, 1)
        item = next(x for x in report["screenshots"] if x["path"].endswith(image.name))
        self.assertIsNone(item["actual_sha256"])
        self.assertIn("missing", " ".join(item["errors"]))

    def test_current_checkout_context_is_separate_from_historical_rounds(self):
        source = self.root / SOURCE
        source.write_text(source.read_text(encoding="utf-8").replace("张三2026", "CurrentEditor"), encoding="utf-8")
        result, report = self.run_report()
        self.assertEqual(result.returncode, 0, report)
        self.assertTrue(report["current_checkout"]["dirty"])
        self.assertEqual(report["current_checkout"]["source_created_by"], "CurrentEditor")
        self.assertEqual(report["historical_rounds"][-1]["actual"]["source_created_by"], "张三2026")
        self.assertEqual(report["current_checkout"]["commit"], self.git("rev-parse", "HEAD").strip())
        self.assertNotEqual(report["current_checkout"]["commit"], SIXTH)

    def test_replace_refs_cannot_substitute_another_historical_object(self):
        self.git("replace", FIRST, SIXTH)
        result, report = self.run_report()
        self.assertEqual(result.returncode, 0, report)
        self.assertEqual(report["historical_rounds"][0]["actual"]["source_created_by"], "李四9527")

    def test_empty_checksum_manifest_fails(self):
        (self.root / "evidence/screenshots/SHA256SUMS.txt").write_text("", encoding="utf-8")
        result, report = self.run_report()
        self.assertEqual(result.returncode, 1)
        self.assertIn("checksum", " ".join(report["errors"]))

    def test_output_file_contains_report_without_stdout_noise(self):
        output = Path(self.temporary.name) / "report.json"
        result, report = self.run_report("--output", output)
        self.assertEqual(result.returncode, 0)
        self.assertIsNone(report)
        self.assertTrue(json.loads(output.read_text(encoding="utf-8"))["ok"])

    def test_non_repository_has_controlled_json_error(self):
        shutil.rmtree(self.root / ".git")
        result, report = self.run_report()
        self.assertEqual(result.returncode, 1)
        self.assertFalse(report["ok"])
        self.assertIn("Git", " ".join(report["errors"]))

    def git(self, *arguments):
        return subprocess.check_output(["git", "-C", str(self.root), *arguments], text=True)


if __name__ == "__main__":
    unittest.main()
