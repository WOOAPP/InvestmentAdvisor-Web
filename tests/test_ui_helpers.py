"""Tests for modules/ui_helpers: markdown renderer, click-to-focus, BusySpinner."""

import unittest
import sys
import os
from unittest.mock import MagicMock, patch, call

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Mock tkinter + webbrowser before importing ui_helpers (CI has no display)
_tk_mock = MagicMock()
sys.modules.setdefault("tkinter", _tk_mock)
sys.modules.setdefault("webbrowser", MagicMock())


class FakeTextWidget:
    """Minimal mock for a Tkinter Text/ScrolledText widget."""

    def __init__(self):
        self.inserts = []  # list of (pos, text, tags)
        self.tags_configured = {}
        self.tag_bindings = {}
        self._cursor = ""

    def insert(self, pos, text, tags=None):
        self.inserts.append((pos, text, tags))

    def tag_configure(self, tag_name, **kwargs):
        self.tags_configured[tag_name] = kwargs

    def tag_bind(self, tag_name, event, callback):
        self.tag_bindings.setdefault(tag_name, {})[event] = callback

    def configure(self, **kwargs):
        if "cursor" in kwargs:
            self._cursor = kwargs["cursor"]

    def get_all_text(self):
        return "".join(t for _, t, _ in self.inserts)

    def get_inserts_with_tag(self, tag):
        return [(t, tags) for _, t, tags in self.inserts if tags and tag in tags]


class TestSetupMarkdownTags(unittest.TestCase):

    def test_creates_all_required_tags(self):
        from modules.ui_helpers import setup_markdown_tags
        w = FakeTextWidget()
        setup_markdown_tags(w)
        expected = {"md_h1", "md_h2", "md_h3", "md_bold", "md_italic",
                    "md_bold_italic", "md_code", "md_codeblock",
                    "md_bullet", "md_link"}
        self.assertTrue(expected.issubset(set(w.tags_configured.keys())))


class TestInsertMarkdown(unittest.TestCase):

    def test_plain_text(self):
        from modules.ui_helpers import insert_markdown
        w = FakeTextWidget()
        insert_markdown(w, "Hello world")
        text = w.get_all_text()
        self.assertIn("Hello world", text)

    def test_heading_h1(self):
        from modules.ui_helpers import insert_markdown
        w = FakeTextWidget()
        insert_markdown(w, "# Main Title")
        tagged = w.get_inserts_with_tag("md_h1")
        self.assertTrue(any("Main Title" in t for t, _ in tagged))

    def test_heading_h2(self):
        from modules.ui_helpers import insert_markdown
        w = FakeTextWidget()
        insert_markdown(w, "## Section")
        tagged = w.get_inserts_with_tag("md_h2")
        self.assertTrue(any("Section" in t for t, _ in tagged))

    def test_heading_h3(self):
        from modules.ui_helpers import insert_markdown
        w = FakeTextWidget()
        insert_markdown(w, "### Sub")
        tagged = w.get_inserts_with_tag("md_h3")
        self.assertTrue(any("Sub" in t for t, _ in tagged))

    def test_bold(self):
        from modules.ui_helpers import insert_markdown
        w = FakeTextWidget()
        insert_markdown(w, "Some **bold** text")
        tagged = w.get_inserts_with_tag("md_bold")
        self.assertTrue(any("bold" in t for t, _ in tagged))

    def test_italic(self):
        from modules.ui_helpers import insert_markdown
        w = FakeTextWidget()
        insert_markdown(w, "Some *italic* text")
        tagged = w.get_inserts_with_tag("md_italic")
        self.assertTrue(any("italic" in t for t, _ in tagged))

    def test_bold_italic(self):
        from modules.ui_helpers import insert_markdown
        w = FakeTextWidget()
        insert_markdown(w, "Some ***both*** text")
        tagged = w.get_inserts_with_tag("md_bold_italic")
        self.assertTrue(any("both" in t for t, _ in tagged))

    def test_inline_code(self):
        from modules.ui_helpers import insert_markdown
        w = FakeTextWidget()
        insert_markdown(w, "Use `print()` here")
        tagged = w.get_inserts_with_tag("md_code")
        self.assertTrue(any("print()" in t for t, _ in tagged))

    def test_code_block(self):
        from modules.ui_helpers import insert_markdown
        w = FakeTextWidget()
        insert_markdown(w, "```\ncode line\n```")
        tagged = w.get_inserts_with_tag("md_codeblock")
        self.assertTrue(any("code line" in t for t, _ in tagged))

    def test_bullet_list(self):
        from modules.ui_helpers import insert_markdown
        w = FakeTextWidget()
        insert_markdown(w, "- Item one\n- Item two")
        tagged = w.get_inserts_with_tag("md_bullet")
        text = "".join(t for t, _ in tagged)
        self.assertIn("Item one", text)
        self.assertIn("Item two", text)

    def test_numbered_list(self):
        from modules.ui_helpers import insert_markdown
        w = FakeTextWidget()
        insert_markdown(w, "1. First\n2. Second")
        tagged = w.get_inserts_with_tag("md_bullet")
        text = "".join(t for t, _ in tagged)
        self.assertIn("First", text)

    def test_link(self):
        from modules.ui_helpers import insert_markdown
        w = FakeTextWidget()
        insert_markdown(w, "Click [here](https://example.com)")
        text = w.get_all_text()
        self.assertIn("here", text)
        # Should have created a link tag
        link_tags = [k for k in w.tags_configured if k.startswith("_link_")]
        self.assertTrue(len(link_tags) >= 1)

    def test_base_tag_applied(self):
        from modules.ui_helpers import insert_markdown
        w = FakeTextWidget()
        insert_markdown(w, "Hello", base_tag="assistant")
        # Check that assistant tag is in some insert
        has_base = any(tags and "assistant" in tags
                       for _, _, tags in w.inserts)
        self.assertTrue(has_base)

    def test_mixed_content(self):
        from modules.ui_helpers import insert_markdown
        w = FakeTextWidget()
        content = "# Title\n\nSome **bold** text\n\n- item\n\n```\ncode\n```"
        insert_markdown(w, content)
        text = w.get_all_text()
        self.assertIn("Title", text)
        self.assertIn("bold", text)
        self.assertIn("item", text)
        self.assertIn("code", text)


class TestOverlaps(unittest.TestCase):

    def test_no_overlap(self):
        from modules.ui_helpers import _overlaps
        spans = [(0, 5, "bold", "abc")]
        self.assertFalse(_overlaps(spans, 5, 10))

    def test_overlap(self):
        from modules.ui_helpers import _overlaps
        spans = [(0, 5, "bold", "abc")]
        self.assertTrue(_overlaps(spans, 3, 8))


class TestBindChatFocus(unittest.TestCase):

    def test_binds_on_frame(self):
        """bind_chat_focus should bind <Button-1> on the frame."""
        from modules.ui_helpers import bind_chat_focus

        frame = MagicMock()
        frame.winfo_children.return_value = []
        entry = MagicMock()

        bind_chat_focus(frame, entry)
        frame.bind.assert_called_once()
        args = frame.bind.call_args
        self.assertEqual(args[0][0], "<Button-1>")

    def test_skips_entry_widgets(self):
        """Should not bind on Entry children."""
        from modules.ui_helpers import _bind_children_focus

        parent = MagicMock()
        child_entry = MagicMock()
        child_entry.winfo_class.return_value = "Entry"
        child_entry.winfo_children.return_value = []
        parent.winfo_children.return_value = [child_entry]
        entry = MagicMock()

        _bind_children_focus(parent, entry)
        child_entry.bind.assert_not_called()

    def test_binds_on_label(self):
        """Should bind on Label children."""
        from modules.ui_helpers import _bind_children_focus

        parent = MagicMock()
        child_label = MagicMock()
        child_label.winfo_class.return_value = "Label"
        child_label.winfo_children.return_value = []
        parent.winfo_children.return_value = [child_label]
        entry = MagicMock()

        _bind_children_focus(parent, entry)
        child_label.bind.assert_called_once()


class TestBusySpinner(unittest.TestCase):

    def test_start_sets_running(self):
        from modules.ui_helpers import BusySpinner
        root = MagicMock()
        label = MagicMock()
        spinner = BusySpinner(root, label)
        spinner.start("Working…")
        self.assertTrue(spinner._running)
        # Should have called root.after for animation
        root.after.assert_called()

    def test_stop_clears_running(self):
        from modules.ui_helpers import BusySpinner
        root = MagicMock()
        label = MagicMock()
        spinner = BusySpinner(root, label)
        spinner._running = True
        spinner._after_id = 42
        spinner.stop("Done")
        self.assertFalse(spinner._running)
        root.after_cancel.assert_called_with(42)
        label.configure.assert_called_with(text="Done")

    def test_stop_without_start(self):
        """stop() should be safe to call even if never started."""
        from modules.ui_helpers import BusySpinner
        root = MagicMock()
        label = MagicMock()
        spinner = BusySpinner(root, label)
        spinner.stop("Idle")
        label.configure.assert_called_with(text="Idle")

    def test_tick_updates_label(self):
        from modules.ui_helpers import BusySpinner, _SPINNER_FRAMES
        root = MagicMock()
        root.after.return_value = 99
        label = MagicMock()
        spinner = BusySpinner(root, label)
        spinner._running = True
        spinner._message = "Test"
        spinner._tick()
        expected_char = _SPINNER_FRAMES[0]
        label.configure.assert_called_with(text=f"{expected_char}  Test")


if __name__ == "__main__":
    unittest.main()
