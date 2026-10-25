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
            "java": "printf '%s\\n' '演示操作轮次=6' '源码中手工填写的创建人=张三2026' 'author_name=Maintenance Author'\n",
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


if __name__ == "__main__":
    unittest.main()
