"""Test setup: lets the tests import reconcile.py, and prints a plain-English
line per rule at the end of the run (e.g. "R10 technician condition 1-10 to
1-5: 16 cases passed")."""

import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

RULE_NAMES = {
    "R1": "load technician file",
    "R2": "load partner file",
    "R3": "count rows in",
    "R4": "building names",
    "R5": "asset types",
    "R6": "manufacturer spellings",
    "R7": "model and serial as captured",
    "R8": "location as captured",
    "R9": "install years",
    "R10": "technician condition 1-10 to 1-5",
    "R11": "partner condition text to 1-5",
    "R12": "nameplate or serial missing",
    "R13": "serial rounded by Excel",
    "R14": "one row, several units",
    "R15": "notes keywords",
    "R16": "finding duplicates",
    "R17": "filling in a merged row",
    "R18": "install year in a merged row",
    "R19": "condition in a merged row",
    "R20": "status and reasons",
    "R21": "row accounting",
    "R22": "outputs",
    "UNSEEN": "full run on a made-up unseen file",
}

passed = Counter()
failed = Counter()


def rule_of(nodeid):
    """Find the rule ID in a test name, e.g. test_R10_... -> R10."""
    match = re.search(r"test_(R\d+|UNSEEN)_", nodeid)
    return match.group(1) if match else "other"


def pytest_runtest_logreport(report):
    if report.when == "call":
        if report.passed:
            passed[rule_of(report.nodeid)] += 1
        elif report.failed:
            failed[rule_of(report.nodeid)] += 1
    elif report.failed:
        failed[rule_of(report.nodeid)] += 1


def pytest_terminal_summary(terminalreporter):
    terminalreporter.section("Results by rule")
    for rule, name in RULE_NAMES.items():
        line = f"{rule} {name}: {passed[rule]} cases passed"
        if failed[rule]:
            line += f", {failed[rule]} FAILED"
        if passed[rule] or failed[rule]:
            terminalreporter.write_line(line)
        else:
            terminalreporter.write_line(f"{rule} {name}: no tests")
