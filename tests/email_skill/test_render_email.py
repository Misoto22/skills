from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = ROOT / "skills" / "email" / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from render_email import normalize_text, render_html  # noqa: E402


class RenderEmailTests(unittest.TestCase):
    def test_normalize_text_joins_hard_wrapped_paragraph_lines(self) -> None:
        source = "Dear Sam,\r\n\r\nThis paragraph was hard\r\nwrapped by a tool.\r\n"

        self.assertEqual(
            normalize_text(source),
            "Dear Sam,\n\nThis paragraph was hard wrapped by a tool.\n",
        )

    def test_escapes_dynamic_html_and_preserves_paragraphs(self) -> None:
        actual = render_html("Dear Sam,\n\n5 < 7 & 8 > 3")

        self.assertIn("<p>Dear Sam,</p>", actual)
        self.assertIn("<p>5 &lt; 7 &amp; 8 &gt; 3</p>", actual)
        self.assertNotIn("<script", actual)

    def test_renders_unordered_bullets_semantically(self) -> None:
        actual = render_html("Items:\n\n- One\n- Two")

        self.assertIn("<ul><li>One</li><li>Two</li></ul>", actual)

    def test_renders_ordered_bullets_semantically(self) -> None:
        actual = render_html("Steps:\n\n1. First\n2. Second")

        self.assertIn("<ol><li>First</li><li>Second</li></ol>", actual)

    def test_escapes_markup_inside_list_items(self) -> None:
        actual = render_html("- <strong>unsafe</strong>")

        self.assertIn("<li>&lt;strong&gt;unsafe&lt;/strong&gt;</li>", actual)
        self.assertNotIn("<strong>unsafe</strong>", actual)

    def test_signature_requires_exact_text_at_end(self) -> None:
        with self.assertRaisesRegex(ValueError, "signature does not match"):
            render_html("Body\n\nChanged signature", "Expected signature")

    def test_signature_uses_deliberate_breaks(self) -> None:
        signature = "Regards,\nExample Sender"

        actual = render_html(f"Body\n\n{signature}", signature)

        self.assertIn(
            '<div class="signature">Regards,<br>Example Sender</div>',
            actual,
        )

    def test_output_has_no_centering_fixed_width_script_or_remote_image(self) -> None:
        actual = render_html("Body")

        for forbidden in (
            "margin: 0 auto",
            "max-width",
            "<script",
            "<img",
            "text-align:center",
            "text-align: center",
        ):
            self.assertNotIn(forbidden, actual)

    def test_nul_byte_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "NUL"):
            render_html("Body\x00hidden")

    def test_cli_writes_utf8_html(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            text_path = root / "body.txt"
            output_path = root / "body.html"
            text_path.write_text("Dear Renée,\n\nHello.", encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_DIR / "render_email.py"),
                    "--text",
                    str(text_path),
                    "--output",
                    str(output_path),
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Dear Renée,", output_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
