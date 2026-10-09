"""The shared gate command line, and the six skill scripts reduced to declaring it.

Behaviour as a skill runs it is held by the subprocess tests beside this one.
These hold the shape: one implementation, and scripts that only say which kind
of artifact they check, which skill their stop line names, and their help text.
"""

from __future__ import annotations

import ast
import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "plugins" / "chinese-metaphysics"
sys.path.insert(0, str(PLUGIN / "shared"))

from bazi.engine import build_chart
from bazi.gate import cli_main
from bazi.validation import CHART

from bazi_skill.ephemeris_double import MeanSolarEphemeris

SINGLE_ARTIFACT_GATES = (
    "bazi-chart",
    "bazi-reading",
    "bazi-compatibility",
    "bazi-compatibility-reading",
    "ziwei-chart",
    "ziwei-reading",
)


def gate(skill: str) -> Path:
    return PLUGIN / "skills" / skill / "scripts" / "validate_artifact.py"


def chart() -> dict:
    return build_chart(
        {
            "name": "Subject A",
            "birth_place": "Greenwich, United Kingdom",
            "birth_date": "1990-03-14",
            "birth_time": "12:00",
            "calendar": "gregorian",
            "timezone": "UTC",
            "latitude": 51.48,
            "longitude": 0.0,
        },
        MeanSolarEphemeris(),
    )


def invoke(stdin: str, **declared: str) -> tuple[int, str, str]:
    stdout, stderr = io.StringIO(), io.StringIO()
    with patch("sys.stdin", io.StringIO(stdin)), redirect_stdout(stdout), redirect_stderr(stderr):
        code = cli_main(CHART, description=None, source_help="source", argv=["-"], **declared)
    return code, stdout.getvalue(), stderr.getvalue()


class CliMainTests(unittest.TestCase):
    def test_a_sound_chart_passes_and_names_its_subject(self) -> None:
        envelope = chart()
        code, stdout, stderr = invoke(json.dumps(envelope, ensure_ascii=False), route_to="bazi-chart")
        self.assertEqual(code, 0, stderr)
        self.assertEqual(stdout, f"valid: Subject A, checksum {envelope['checksum']}\n")

    def test_a_reading_gate_routes_the_defect_back(self) -> None:
        code, stdout, stderr = invoke("[1]", route_to="bazi-chart")
        self.assertEqual((code, stdout), (2, ""))
        self.assertEqual(
            stderr,
            "error: expected one JSON object\n"
            "stop: name this defect and route the source back to `bazi-chart`\n",
        )

    def test_a_calculator_gate_withholds_the_hand_off(self) -> None:
        code, _, stderr = invoke("{nope", hands_off_to="bazi-reading")
        self.assertEqual(code, 2)
        self.assertTrue(
            stderr.endswith("stop: do not invoke `bazi-reading` and do not repair the artifact by hand\n")
        )

    def test_a_gate_names_exactly_one_next_step(self) -> None:
        for declared in ({}, {"route_to": "bazi-chart", "hands_off_to": "bazi-reading"}):
            with self.subTest(declared=sorted(declared)), self.assertRaises(ValueError):
                invoke("{}", **declared)


class ShimTests(unittest.TestCase):
    def test_every_single_artifact_gate_delegates_to_the_shared_command(self) -> None:
        for skill in SINGLE_ARTIFACT_GATES:
            tree = ast.parse(gate(skill).read_text(encoding="utf-8"))
            imported = {
                alias.name
                for node in ast.walk(tree)
                if isinstance(node, ast.ImportFrom) and node.module == "bazi.gate"
                for alias in node.names
            }
            modules = {
                alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names
            }
            with self.subTest(skill=skill):
                self.assertEqual(imported, {"cli_main"})
                self.assertFalse({"argparse", "json"} & modules, "parsing belongs to bazi.gate")
                functions = [node.name for node in tree.body if isinstance(node, ast.FunctionDef)]
                self.assertEqual(functions, ["main"])

    def test_a_gate_runs_from_a_lone_copy_of_its_skill(self) -> None:
        """An installer copies the skill directory and nothing beside it."""

        with tempfile.TemporaryDirectory() as directory:
            skill = Path(directory) / "bazi-reading"
            shutil.copytree(
                PLUGIN / "skills" / "bazi-reading", skill, ignore=shutil.ignore_patterns("__pycache__")
            )
            result = subprocess.run(
                [sys.executable, "-E", "-s", str(skill / "scripts" / "validate_artifact.py"), "-"],
                capture_output=True,
                text=True,
                input=json.dumps(chart(), ensure_ascii=False),
                check=False,
                cwd=directory,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(result.stdout.startswith("valid: Subject A, checksum "))


if __name__ == "__main__":
    unittest.main()
