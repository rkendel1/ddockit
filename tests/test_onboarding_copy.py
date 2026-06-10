from pathlib import Path
from unittest import TestCase


class OnboardingCopyTests(TestCase):
    def test_readme_includes_evaluation_guidance(self) -> None:
        readme = Path(__file__).resolve().parents[1] / "README.md"
        text = readme.read_text(encoding="utf-8")
        self.assertIn("## How one-click evaluation works", text)
        self.assertIn("## Real evaluation examples", text)
        self.assertIn("open `http://127.0.0.1:8080/` in your browser", text.lower())
        self.assertIn("## The core value proposition", text)
        self.assertIn("## Who this is for", text)
        self.assertIn("## MVP roadmap", text)
        self.assertIn("## Hard problems to handle from day one", text)

    def test_ui_explains_one_click_and_ui_usage(self) -> None:
        app_main = Path(__file__).resolve().parents[1] / "trycontainer" / "__main__.py"
        text = app_main.read_text(encoding="utf-8")
        self.assertIn("How one-click works", text)
        self.assertIn("This page is the UI for launching and monitoring sessions.", text)
        self.assertIn("Safety. Speed. Zero setup. Zero commitment. Isolation. Curiosity.", text)
        self.assertIn("Find project -> Click Try -> Use immediately -> Destroy.", text)
