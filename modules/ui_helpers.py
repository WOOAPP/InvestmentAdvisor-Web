"""
Shared UI helpers for InvestmentAdvisor:
  - Markdown renderer for Tkinter Text/ScrolledText
  - Click-to-focus binding for chat frames
  - Busy/spinner animation
"""

import re
import sys, os
import tkinter as tk
import webbrowser

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from constants import SPINNER_TICK_MS

# ── Theme colors (must match main.py) ──────────────────────────────
_BG = "#1e1e2e"
_BG2 = "#181825"
_FG = "#cdd6f4"
_ACCENT = "#89b4fa"
_GREEN = "#a6e3a1"
_YELLOW = "#f9e2af"
_GRAY = "#313244"
_CODE_BG = "#313244"

# ────────────────────────────────────────────────────────────────────
# TASK 3: Minimal Markdown renderer → Tkinter Text tags
# ────────────────────────────────────────────────────────────────────

def setup_markdown_tags(text_widget):
    """Configure the font/color tags needed for markdown rendering."""
    base_family = "Segoe UI"
    mono_family = "Consolas"

    text_widget.tag_configure("md_h1", font=(base_family, 14, "bold"),
                              foreground=_ACCENT, spacing1=6, spacing3=4)
    text_widget.tag_configure("md_h2", font=(base_family, 12, "bold"),
                              foreground=_ACCENT, spacing1=4, spacing3=3)
    text_widget.tag_configure("md_h3", font=(base_family, 11, "bold"),
                              foreground=_ACCENT, spacing1=3, spacing3=2)
    text_widget.tag_configure("md_bold", font=(base_family, 10, "bold"))
    text_widget.tag_configure("md_italic", font=(base_family, 10, "italic"))
    text_widget.tag_configure("md_bold_italic",
                              font=(base_family, 10, "bold italic"))
    text_widget.tag_configure("md_code", font=(mono_family, 9),
                              background=_CODE_BG, foreground=_YELLOW)
    text_widget.tag_configure("md_codeblock", font=(mono_family, 9),
                              background=_CODE_BG, foreground=_GREEN,
                              spacing1=4, spacing3=4, lmargin1=12,
                              lmargin2=12)
    text_widget.tag_configure("md_bullet", lmargin1=16, lmargin2=28)
    text_widget.tag_configure("md_link", foreground=_ACCENT,
                              underline=True)


# Regex patterns (compiled once)
_RE_HEADING = re.compile(r"^(#{1,3})\s+(.+)$")
_RE_BULLET = re.compile(r"^(\s*[-*]|\s*\d+\.)\s+(.+)$")
_RE_CODEBLOCK_START = re.compile(r"^```")
_RE_BOLD_ITALIC = re.compile(r"\*\*\*(.+?)\*\*\*")
_RE_BOLD = re.compile(r"\*\*(.+?)\*\*")
_RE_ITALIC = re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)")
_RE_INLINE_CODE = re.compile(r"`([^`]+)`")
_RE_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


def insert_markdown(text_widget, content, base_tag=""):
    """Parse markdown string and insert into text_widget with tags.

    base_tag: an additional tag applied to all text (e.g. "assistant").
    """
    lines = content.split("\n")
    in_codeblock = False
    i = 0

    while i < len(lines):
        line = lines[i]

        # ── Code block toggle ──
        if _RE_CODEBLOCK_START.match(line.strip()):
            if not in_codeblock:
                in_codeblock = True
                i += 1
                continue
            else:
                in_codeblock = False
                i += 1
                continue

        if in_codeblock:
            tags = ("md_codeblock",) + ((base_tag,) if base_tag else ())
            text_widget.insert("end", line + "\n", tags)
            i += 1
            continue

        # ── Heading ──
        m = _RE_HEADING.match(line)
        if m:
            level = len(m.group(1))
            tag = f"md_h{level}"
            tags = (tag,) + ((base_tag,) if base_tag else ())
            text_widget.insert("end", m.group(2) + "\n", tags)
            i += 1
            continue

        # ── Bullet / numbered list ──
        m = _RE_BULLET.match(line)
        if m:
            prefix = m.group(1).strip()
            body = m.group(2)
            tags = ("md_bullet",) + ((base_tag,) if base_tag else ())
            text_widget.insert("end", f"  {prefix} ", tags)
            _insert_inline(text_widget, body, base_tag, extra_tags=("md_bullet",))
            text_widget.insert("end", "\n", tags)
            i += 1
            continue

        # ── Normal line with inline formatting ──
        _insert_inline(text_widget, line, base_tag)
        text_widget.insert("end", "\n",
                           (base_tag,) if base_tag else ())
        i += 1


def _insert_inline(text_widget, text, base_tag="", extra_tags=()):
    """Handle inline markdown: bold, italic, code, links."""
    base = ((base_tag,) if base_tag else ()) + tuple(extra_tags)

    # Build a list of (start, end, tag, display_text) spans
    spans = []
    for m in _RE_BOLD_ITALIC.finditer(text):
        spans.append((m.start(), m.end(), "md_bold_italic", m.group(1)))
    for m in _RE_BOLD.finditer(text):
        if not _overlaps(spans, m.start(), m.end()):
            spans.append((m.start(), m.end(), "md_bold", m.group(1)))
    for m in _RE_ITALIC.finditer(text):
        if not _overlaps(spans, m.start(), m.end()):
            spans.append((m.start(), m.end(), "md_italic", m.group(1)))
    for m in _RE_INLINE_CODE.finditer(text):
        if not _overlaps(spans, m.start(), m.end()):
            spans.append((m.start(), m.end(), "md_code", m.group(1)))
    for m in _RE_LINK.finditer(text):
        if not _overlaps(spans, m.start(), m.end()):
            spans.append((m.start(), m.end(), "md_link", m.group(1),
                          m.group(2)))

    if not spans:
        text_widget.insert("end", text, base)
        return

    spans.sort(key=lambda s: s[0])
    pos = 0
    for span in spans:
        # Text before this span
        if span[0] > pos:
            text_widget.insert("end", text[pos:span[0]], base)
        tag = span[2]
        display = span[3]
        tags = (tag,) + base
        if tag == "md_link" and len(span) > 4:
            url = span[4]
            # Insert link text with a unique tag for click binding
            link_tag = f"_link_{id(span)}"
            text_widget.tag_configure(link_tag, foreground=_ACCENT,
                                      underline=True)
            text_widget.insert("end", display, (link_tag,) + base)
            text_widget.tag_bind(link_tag, "<Button-1>",
                                 lambda e, u=url: webbrowser.open(u))
            text_widget.tag_bind(link_tag, "<Enter>",
                                 lambda e: text_widget.configure(
                                     cursor="hand2"))
            text_widget.tag_bind(link_tag, "<Leave>",
                                 lambda e: text_widget.configure(
                                     cursor=""))
        else:
            text_widget.insert("end", display, tags)
        pos = span[1]

    # Remaining text after last span
    if pos < len(text):
        text_widget.insert("end", text[pos:], base)


def _overlaps(spans, start, end):
    """Check if [start, end) overlaps with any existing span."""
    for s in spans:
        if start < s[1] and end > s[0]:
            return True
    return False


# ────────────────────────────────────────────────────────────────────
# TASK 1: Click-to-focus for chat frames
# ────────────────────────────────────────────────────────────────────

def bind_chat_focus(frame, entry_widget):
    """Bind click anywhere in the chat frame to focus the entry widget.

    Works for LabelFrame, Frame, ScrolledText, Labels, etc.
    Does NOT steal focus when user is selecting text in the output.
    """
    def _focus_entry(event):
        entry_widget.focus_set()

    # Bind on the frame itself
    frame.bind("<Button-1>", _focus_entry, add="+")

    # Recursively bind on all children
    _bind_children_focus(frame, entry_widget)


def _bind_children_focus(widget, entry_widget):
    """Recursively bind <Button-1> on children to focus entry.

    Skip Entry/Button widgets (they have their own click behavior).
    For Text/ScrolledText: bind on the frame wrapper, not the text itself
    (to preserve text selection).
    """
    for child in widget.winfo_children():
        cls_name = child.winfo_class()
        # Skip interactive widgets
        if cls_name in ("Entry", "TEntry", "Button", "TButton",
                        "Checkbutton", "TCheckbutton"):
            continue
        # For Text widgets: only focus on empty area clicks
        if cls_name == "Text":
            # Don't bind on Text directly — would interfere with selection
            pass
        else:
            child.bind("<Button-1>", lambda e: entry_widget.focus_set(),
                       add="+")
        # Recurse
        _bind_children_focus(child, entry_widget)


# ────────────────────────────────────────────────────────────────────
# TASK 2: Busy/spinner animation
# ────────────────────────────────────────────────────────────────────

_SPINNER_FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"


class BusySpinner:
    """Animated text spinner for Tkinter.

    Usage:
        spinner = BusySpinner(root, label_widget)
        spinner.start("Analizuję…")
        # later...
        spinner.stop("Gotowy")
    """

    def __init__(self, root, label_widget):
        self._root = root
        self._label = label_widget
        self._running = False
        self._frame_idx = 0
        self._message = ""
        self._after_id = None

    def start(self, message="Pracuję…"):
        self._message = message
        self._running = True
        self._frame_idx = 0
        self._tick()

    def stop(self, final_message="Gotowy"):
        self._running = False
        if self._after_id is not None:
            try:
                self._root.after_cancel(self._after_id)
            except (tk.TclError, RuntimeError):
                pass  # widget already destroyed
            self._after_id = None
        try:
            self._label.configure(text=final_message)
        except (tk.TclError, RuntimeError):
            pass  # widget already destroyed

    def _tick(self):
        if not self._running:
            return
        char = _SPINNER_FRAMES[self._frame_idx % len(_SPINNER_FRAMES)]
        try:
            self._label.configure(text=f"{char}  {self._message}")
        except (tk.TclError, RuntimeError):
            self._running = False
            return
        self._frame_idx += 1
        self._after_id = self._root.after(SPINNER_TICK_MS, self._tick)


# ── Chat typing indicator ──────────────────────────────────
_TYPING_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
_TYPING_TICK_MS = 120


class ChatTypingIndicator:
    """Animated 'AI is thinking' indicator inside a ScrolledText chat widget."""

    def __init__(self, root, chat_widget):
        self._root = root
        self._widget = chat_widget
        self._running = False
        self._frame_idx = 0
        self._after_id = None
        self._mark = "typing_start"

    def start(self, message="AI analizuje"):
        if self._running:
            return
        self._message = message
        self._running = True
        self._frame_idx = 0
        try:
            self._widget.configure(state="normal")
            self._widget.mark_set(self._mark, "end-1c")
            self._widget.mark_gravity(self._mark, "left")
            self._widget.insert("end", "\n", "typing")
            self._widget.configure(state="disabled")
            self._widget.see("end")
        except (tk.TclError, RuntimeError):
            self._running = False
            return
        self._tick()

    def stop(self):
        self._running = False
        if self._after_id is not None:
            try:
                self._root.after_cancel(self._after_id)
            except (tk.TclError, RuntimeError):
                pass
            self._after_id = None
        try:
            self._widget.configure(state="normal")
            self._widget.delete(self._mark, "end")
            self._widget.configure(state="disabled")
        except (tk.TclError, RuntimeError):
            pass

    def _tick(self):
        if not self._running:
            return
        frame = _TYPING_FRAMES[self._frame_idx % len(_TYPING_FRAMES)]
        text = f"{frame}  {self._message}…"
        try:
            self._widget.configure(state="normal")
            self._widget.delete(self._mark, "end")
            self._widget.insert("end", f"\n{text}", "typing")
            self._widget.configure(state="disabled")
            self._widget.see("end")
        except (tk.TclError, RuntimeError):
            self._running = False
            return
        self._frame_idx += 1
        self._after_id = self._root.after(_TYPING_TICK_MS, self._tick)
