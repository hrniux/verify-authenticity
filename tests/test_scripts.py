"""Regress shell orchestration with real historical Git objects and stubbed builds.

The normal verifier separately runs the real Maven build and Java program.
These fixtures vary terminal/HEAD conditions without creating or changing commits.
"""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


REPOSITORY = Path(__file__).resolve().parents[1]
COMMITS = (
    "416966f10555d78847e15616fb017095625b0127",
    "c3374b0cc26e00213c3d4f92017dc2b7a8257d8e",
    "d9aea3616ec78e9c239b989e0f5c1633a5f4c96a",
    "7a70ecf2a2c0c93dc3f27081b46143a95f1cbbe8",
    "cb1769eca11979f95ded56284e4b556e7e3571ae",
    "aa002fb59e5505e31143c1b98b29b4e9f55c8653",
)


class ScriptTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        shutil.copytree(REPOSITORY / "scripts", self.root / "scripts")
        binaries = self.root / "bin"
        binaries.mkdir()
        self.environment = dict(
            os.environ,
            PATH=str(binaries) + os.pathsep + os.environ["PATH"],
            VERIFY_REAL_GIT=shutil.which("git"),
            VERIFY_REPOSITORY=str(REPOSITORY),
        )
        self.environment.pop("TERM", None)
        for name, body in {
            "mvn": "exit 0\n",
            "java": "printf '%s\\n' '演示操作轮次=6' '源码中手工填写的创建人=张三2026' 'author_name=Maintenance Author' \"git_replacements_disabled=${GIT_NO_REPLACE_OBJECTS:-}\"\n",
            "git": '''if [[ "$1" == cat-file && "$2" == -p && "$3" == HEAD ]]; then
    printf 'author Maintenance Author <maintainer@example.invalid> 0 +0000\\n'
    exit 0
fi
exec "$VERIFY_REAL_GIT" -C "$VERIFY_REPOSITORY" "$@"
''',
        }.items():
            path = binaries / name
            path.write_text("#!/usr/bin/env bash\nset -euo pipefail\n" + body, encoding="utf-8")
            path.chmod(0o755)

    def run_script(self, name):
        return subprocess.run(
            ["bash", str(self.root / "scripts" / name)],
            env=self.environment, text=True, capture_output=True,
        )

    def test_historical_verification_survives_maintenance_head_author(self):
        result = self.run_script("verify.sh")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("验证通过", result.stdout)

    def test_operation_log_works_without_term_or_interactive_output(self):
        result = self.run_script("show-operation-log.sh")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("真实 Git 操作日志", result.stdout)
        self.assertIn("第 6 轮", result.stdout)
        self.assertIn("验证通过", result.stdout)

    def use_historical_checkout_with_replacement(self):
        checkout = self.root / "checkout"
        subprocess.run(
            [self.environment["VERIFY_REAL_GIT"], "clone", "--shared", "--quiet", "--no-checkout", str(REPOSITORY), str(checkout)],
            check=True, capture_output=True,
        )
        subprocess.run(
            [self.environment["VERIFY_REAL_GIT"], "-C", str(checkout), "replace", COMMITS[0], COMMITS[-1]],
            check=True, capture_output=True,
        )
        self.environment["VERIFY_REPOSITORY"] = str(checkout)

    def test_verification_reads_original_objects_despite_local_replacement(self):
        self.use_historical_checkout_with_replacement()
        result = self.run_script("verify.sh")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("验证通过", result.stdout)
        self.assert_replacement_preserved()

    def test_operation_rounds_use_original_objects_despite_local_replacement(self):
        self.use_historical_checkout_with_replacement()
        result = self.run_script("show-operation-log.sh")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("张三2026 -> 李四9527", next(line for line in result.stdout.splitlines() if "第 1 轮" in line))
        self.assert_replacement_preserved()

    def assert_replacement_preserved(self):
        result = subprocess.check_output(
            [self.environment["VERIFY_REAL_GIT"], "-C", self.environment["VERIFY_REPOSITORY"], "rev-parse", "refs/replace/" + COMMITS[0]],
            text=True,
        )
        self.assertEqual(result.strip(), COMMITS[-1])

    def test_java_subprocess_inherits_original_object_reads(self):
        result = self.run_script("verify.sh")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("git_replacements_disabled=1", result.stdout)

    def test_operation_rounds_identify_every_complete_anchored_commit(self):
        result = self.run_script("show-operation-log.sh")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for number, commit in enumerate(COMMITS, 1):
            with self.subTest(round=number):
                self.assertIn(f"第 {number} 轮 | {commit} |", result.stdout)


if __name__ == "__main__":
    unittest.main()
