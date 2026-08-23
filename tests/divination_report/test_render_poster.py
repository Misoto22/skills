from __future__ import annotations

import copy
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COMPONENT = ROOT / "shared" / "divination-report"
SCRIPT = COMPONENT / "render_poster.py"
TEMPLATE = COMPONENT / "templates" / "ink-wash-poster.html"
FIXTURE = Path(__file__).parent / "fixtures" / "poster.example.json"


def load_script():
    spec = importlib.util.spec_from_file_location("render_poster", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MODULE = load_script()
PAYLOAD = json.loads(FIXTURE.read_text(encoding="utf-8"))


def render(payload):
    return MODULE.render(TEMPLATE.read_text(encoding="utf-8"), MODULE.validate(payload))


class TemplateRenderingTests(unittest.TestCase):
    def test_the_fixture_renders_with_no_tag_left_behind(self):
        document = render(copy.deepcopy(PAYLOAD))
        self.assertNotIn("{{", document)
        self.assertNotIn("}}", document)

    def test_every_section_the_payload_supplies_appears(self):
        document = render(copy.deepcopy(PAYLOAD))
        for heading in (
            "基本信息",
            "核心指标",
            "主轴",
            "五行分布",
            "倾向与张力",
            "领域对照",
            "分歧披露",
            "观察提示",
            "置信度",
        ):
            self.assertIn(heading, document)

    def test_an_omitted_block_drops_its_whole_section(self):
        payload = copy.deepcopy(PAYLOAD)
        for field in ("distribution", "conflicts", "reflection", "confidence", "tendencies", "domains"):
            payload.pop(field)
        document = render(payload)
        self.assertNotIn("分歧披露", document)
        self.assertNotIn("五行分布", document)
        self.assertNotIn("倾向与张力", document)
        self.assertIn("核心指标", document)

    def test_the_limitation_footer_always_survives(self):
        document = render(copy.deepcopy(PAYLOAD))
        self.assertIn(PAYLOAD["footer"]["limitation"][:20], document)

    def test_ratios_become_bar_widths(self):
        document = render(copy.deepcopy(PAYLOAD))
        self.assertIn("width:38%", document)
        self.assertIn("width:100%", document)

    def test_scalar_list_items_render_one_per_entry(self):
        document = render(copy.deepcopy(PAYLOAD))
        for prompt in PAYLOAD["reflection"]["items"]:
            self.assertIn(prompt, document)

    def test_page_carries_both_theme_definitions(self):
        document = render(copy.deepcopy(PAYLOAD))
        self.assertIn("prefers-color-scheme: dark", document)
        self.assertIn('[data-theme="dark"]', document)

    def test_the_page_reaches_no_external_host(self):
        document = render(copy.deepcopy(PAYLOAD))
        for scheme in ("http://", "https://", "//fonts.", "src=", "@import"):
            self.assertNotIn(scheme, document, scheme)


class EscapingTests(unittest.TestCase):
    def test_model_supplied_text_cannot_inject_markup(self):
        payload = copy.deepcopy(PAYLOAD)
        payload["meta"]["archetype"] = "<script>alert(1)</script>"
        payload["narrative"]["paragraphs"][0] = 'a "quoted" & <b>bold</b> claim'
        document = render(payload)
        self.assertNotIn("<script>alert(1)</script>", document)
        self.assertIn("&lt;script&gt;", document)
        self.assertIn("&lt;b&gt;bold&lt;/b&gt;", document)

    def test_a_class_field_cannot_break_out_of_its_attribute(self):
        payload = copy.deepcopy(PAYLOAD)
        payload["consistency"]["verdict_class"] = 'x" onload="evil()'
        document = render(payload)
        self.assertNotIn('onload="evil()"', document)
        self.assertIn("&quot;", document)


class ValidationTests(unittest.TestCase):
    def missing(self, field):
        payload = copy.deepcopy(PAYLOAD)
        payload.pop(field)
        return payload

    def test_every_required_block_is_enforced(self):
        for field in ("meta", "identity", "core_metrics", "axes", "narrative", "footer"):
            with self.assertRaises(MODULE.PosterError, msg=field):
                MODULE.validate(self.missing(field))

    def test_a_missing_limitation_is_refused(self):
        payload = copy.deepcopy(PAYLOAD)
        payload["footer"].pop("limitation")
        with self.assertRaises(MODULE.PosterError):
            MODULE.validate(payload)

    def test_every_meta_field_is_enforced(self):
        for field in ("archetype", "one_line", "subject", "system_label", "seal"):
            payload = copy.deepcopy(PAYLOAD)
            payload["meta"].pop(field)
            with self.assertRaises(MODULE.PosterError, msg=field):
                MODULE.validate(payload)

    def test_an_out_of_range_ratio_is_refused(self):
        for bad in (-1, 101, "80", True):
            payload = copy.deepcopy(PAYLOAD)
            payload["core_metrics"][1]["ratio"] = bad
            with self.assertRaises(MODULE.PosterError, msg=repr(bad)):
                MODULE.validate(payload)

    def test_too_many_metric_cards_are_refused(self):
        payload = copy.deepcopy(PAYLOAD)
        payload["core_metrics"] = payload["core_metrics"] * 3
        with self.assertRaises(MODULE.PosterError):
            MODULE.validate(payload)

    def test_all_faults_are_reported_in_one_round_trip(self):
        payload = copy.deepcopy(PAYLOAD)
        payload.pop("axes")
        payload["meta"].pop("seal")
        with self.assertRaises(MODULE.PosterError) as caught:
            MODULE.validate(payload)
        self.assertIn("axes", str(caught.exception))
        self.assertIn("meta.seal", str(caught.exception))


class CommandLineTests(unittest.TestCase):
    def run_cli(self, payload, destination):
        with tempfile.TemporaryDirectory() as directory:
            data = Path(directory) / "payload.json"
            data.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            out, err = io.StringIO(), io.StringIO()
            argv = sys.argv
            sys.argv = ["render_poster.py", "--data", str(data), "--out", str(destination)]
            try:
                with redirect_stdout(out), redirect_stderr(err):
                    code = MODULE.main()
            finally:
                sys.argv = argv
            return code, out.getvalue().strip(), err.getvalue()

    def test_a_valid_payload_writes_one_file_and_prints_its_path(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "poster.html"
            code, printed, _ = self.run_cli(copy.deepcopy(PAYLOAD), destination)
            self.assertEqual(code, 0)
            self.assertEqual(printed, str(destination.resolve()))
            self.assertIn("<!DOCTYPE html>", destination.read_text(encoding="utf-8"))

    def test_an_invalid_payload_exits_two_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "poster.html"
            code, printed, error = self.run_cli(self.broken(), destination)
            self.assertEqual(code, 2)
            self.assertEqual(printed, "")
            self.assertIn("error:", error)
            self.assertFalse(destination.exists())

    def broken(self):
        payload = copy.deepcopy(PAYLOAD)
        payload.pop("footer")
        return payload


if __name__ == "__main__":
    unittest.main()
