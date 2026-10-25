#!/usr/bin/env python3
"""Report historical Git/log agreement and current screenshot checksum agreement.

The report describes this demonstration repository. It cannot establish a
real-world operator's identity or authenticate a screenshot's depicted events.
"""

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys


COMMITS = (
    "416966f10555d78847e15616fb017095625b0127",
    "c3374b0cc26e00213c3d4f92017dc2b7a8257d8e",
    "d9aea3616ec78e9c239b989e0f5c1633a5f4c96a",
    "7a70ecf2a2c0c93dc3f27081b46143a95f1cbbe8",
    "cb1769eca11979f95ded56284e4b556e7e3571ae",
    "aa002fb59e5505e31143c1b98b29b4e9f55c8653",
)
SOURCE = "src/main/java/com/example/verify/AuthenticityDemo.java"
SCREENSHOTS = (
    "terminal-operation-log.png",
    "github-commit-history.png",
    "github-current-java-file.png",
)
LOG_FIELDS = ("commit", "author", "committer", "date", "signature", "source_created_by", "subject")


class ReportError(ValueError):
    pass


def git(repo, *arguments):
    # Replacement refs are local overlays, not the anchored historical objects.
    result = subprocess.run(
        ["git", "--no-replace-objects", "-C", str(repo), *arguments],
        capture_output=True, encoding="utf-8", errors="strict",
    )
    if result.returncode:
        raise ReportError("Git object or repository unavailable")
    return result.stdout.rstrip("\n")


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def source_creator(source):
    comments = re.findall(r"<p>创建人：([^<\r\n]+)</p>", source)
    constants = re.findall(r'\bSOURCE_CREATED_BY\s*=\s*"([^"\r\n]+)"\s*;', source)
    if len(comments) != 1 or len(constants) != 1 or comments[0] != constants[0]:
        raise ReportError("source creator comment and constant must be unique and agree")
    return comments[0]


def read_contained(repo, relative):
    path = repo / relative
    try:
        path.resolve().relative_to(repo.resolve())
    except ValueError as error:
        raise ReportError("file outside repository: " + relative) from error
    try:
        return path.read_bytes()
    except OSError as error:
        raise ReportError("required file missing or unreadable: " + relative) from error


def parse_log(text):
    rounds = {}
    current = None
    for line in text.splitlines():
        match = re.fullmatch(r"ROUND ([1-6])", line)
        if match:
            current = int(match.group(1))
            if current in rounds:
                raise ReportError("duplicate operation-log round: " + str(current))
            rounds[current] = {}
        elif current is not None and re.match(r"^[a-z_]+=", line):
            key, value = line.split("=", 1)
            if key in rounds[current]:
                raise ReportError("duplicate operation-log field: " + key)
            rounds[current][key] = value
    if set(rounds) != set(range(1, 7)):
        raise ReportError("operation log requires exactly rounds 1 through 6")
    for number, record in rounds.items():
        for key in LOG_FIELDS:
            if not record.get(key):
                raise ReportError("operation-log round " + str(number) + " requires " + key)
    return rounds


def commit_metadata(repo, commit):
    fields = git(repo, "show", "--no-patch", "--no-show-signature", "--no-use-mailmap",
                 "--format=%H%x00%an <%ae>%x00%cn <%ce>%x00%aI%x00%cI%x00%G?%x00%s", commit, "--").split("\0")
    if len(fields) != 7 or fields[0] != commit:
        raise ReportError("Git returned unexpected commit metadata")
    return dict(zip(("commit", "author", "committer", "date", "committer_date", "signature", "subject"), fields))


def historical_round(repo, number, commit, expected):
    item = {"round": number, "commit": commit, "expected": expected, "actual": None, "ok": False, "errors": []}
    if expected.get("commit") != commit:
        item["errors"].append("operation log does not match anchored commit " + commit)
    try:
        actual = commit_metadata(repo, commit)
        source = git(repo, "cat-file", "blob", commit + ":" + SOURCE)
        actual["source_created_by"] = source_creator(source)
        actual["source_blob"] = git(repo, "rev-parse", commit + ":" + SOURCE)
        item["actual"] = actual
    except (ReportError, OSError, UnicodeError) as error:
        item["errors"].append("historical commit/source unavailable: " + commit + " (" + str(error) + ")")
    if item["actual"]:
        for key in LOG_FIELDS:
            if expected.get(key) != item["actual"][key]:
                item["errors"].append("historical " + key + " differs from operation log")
    item["ok"] = not item["errors"]
    return item


def screenshot_checks(repo, manifest):
    expected = {}
    errors = []
    for line in manifest.splitlines():
        if not line.strip():
            continue
        match = re.fullmatch(r"([a-fA-F0-9]{64}) [ *]([^/\\]+\.png)", line)
        if not match or match.group(2) not in SCREENSHOTS:
            errors.append("invalid screenshot checksum entry")
            continue
        digest, name = match.groups()
        if name in expected:
            errors.append("duplicate screenshot checksum entry: " + name)
        expected[name] = digest.lower()
    if set(expected) != set(SCREENSHOTS):
        errors.append("checksum manifest must list all three preserved screenshots")
    items = []
    for name in SCREENSHOTS:
        relative = "evidence/screenshots/" + name
        item = {"path": relative, "expected_sha256": expected.get(name), "actual_sha256": None, "ok": False, "errors": []}
        try:
            item["actual_sha256"] = sha256(read_contained(repo, relative))
        except ReportError as error:
            item["errors"].append(str(error))
        if name not in expected:
            item["errors"].append("missing checksum manifest entry")
        elif item["actual_sha256"] is not None and item["actual_sha256"] != expected[name]:
            item["errors"].append("screenshot SHA-256 differs from checksum manifest")
        item["ok"] = not item["errors"]
        items.append(item)
    return items, errors


def build_report(repo):
    report = {
        "schema_version": 1, "ok": False,
        "current_checkout": {"commit": None, "dirty": None, "source_created_by": None, "source_sha256": None, "errors": []},
        "operation_log": {"path": "evidence/operation-log.txt", "basis": "current checkout", "sha256": None},
        "checksum_manifest": {"path": "evidence/screenshots/SHA256SUMS.txt", "basis": "current checkout", "sha256": None},
        "historical_rounds": [], "screenshots": [], "errors": [],
        "limitations": [
            "Historical actual fields come from the six fixed Git commit/source objects with replacement refs disabled; expected fields come from the current operation log.",
            "Current checkout HEAD, dirty state and source are context only; later maintenance authors and current source edits do not change historical rounds.",
            "Screenshot hashes compare current file bytes with the current checksum manifest; agreement does not authenticate depicted events or provide tamper-evident custody.",
            "Git signature states describe this machine's Git verification result; names and creator text do not establish real-world identity.",
        ],
    }
    try:
        top = Path(git(repo, "rev-parse", "--show-toplevel")).resolve()
        if top != repo.resolve():
            raise ReportError("--repo must identify the Git repository root")
        current = report["current_checkout"]
        try:
            current["commit"] = git(repo, "rev-parse", "--verify", "HEAD^{commit}")
            current["metadata"] = commit_metadata(repo, current["commit"])
            current["dirty"] = bool(git(repo, "status", "--porcelain", "--untracked-files=normal"))
        except ReportError as error:
            current["errors"].append(str(error))
            report["errors"].append("current Git checkout unavailable")
        try:
            source = read_contained(repo, SOURCE)
            current["source_sha256"] = sha256(source)
            current["source_created_by"] = source_creator(source.decode("utf-8"))
        except (ReportError, UnicodeError) as error:
            current["errors"].append(str(error))
    except (ReportError, OSError, UnicodeError) as error:
        report["errors"].append(str(error))
        return report
    rounds = {}
    try:
        data = read_contained(repo, report["operation_log"]["path"])
        report["operation_log"]["sha256"] = sha256(data)
        rounds = parse_log(data.decode("utf-8"))
    except (ReportError, UnicodeError) as error:
        report["errors"].append(str(error))
    for number, commit in enumerate(COMMITS, 1):
        item = historical_round(repo, number, commit, rounds.get(number, {}))
        report["historical_rounds"].append(item)
        report["errors"].extend("round " + str(number) + ": " + error for error in item["errors"])
    try:
        data = read_contained(repo, report["checksum_manifest"]["path"])
        report["checksum_manifest"]["sha256"] = sha256(data)
        report["screenshots"], errors = screenshot_checks(repo, data.decode("utf-8"))
        report["errors"].extend(errors)
        for item in report["screenshots"]:
            report["errors"].extend(item["path"] + ": " + error for error in item["errors"])
    except (ReportError, UnicodeError) as error:
        report["errors"].append(str(error))
    report["ok"] = not report["errors"]
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1], help="repository root; full history required")
    parser.add_argument("--output", type=Path, help="write JSON to this file instead of stdout")
    args = parser.parse_args()
    report = build_report(args.repo.resolve())
    output = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        try:
            args.output.write_text(output, encoding="utf-8")
        except OSError as error:
            print("Cannot write report: " + str(error), file=sys.stderr)
            return 1
    else:
        print(output, end="")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
