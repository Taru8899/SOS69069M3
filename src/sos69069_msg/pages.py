"""
Every page's layout, in one file. Each _build_* method constructs the
widgets for one screen and returns the finished Box — the same job they
did inline inside app.py's App class before this split.

This is a mixin (PagesMixin), not a standalone class: the widgets built
here are wired to handler methods (self.mind_refresh, self.chat_send, ...)
that live in app.py, and they read/write instance state (self.wallet,
self.settings, self.chat_target, ...) that app.py's startup sets up. The
App class in app.py inherits from PagesMixin so `self._build_mind()` etc.
still work exactly as before — only the method bodies moved.

The README page's body is loaded at runtime from README.md inside this
package (src/sos69069_msg/README.md) and parsed into styled widgets —
so the README has a single source of truth (the markdown file) that also
ships inside the app bundle.

The README page is reached only via the "View README" link on SETUP. It
is not a tab, but app.py registers it in self.pages / self.scrollers the
same way it registers the four tab pages, so _show_page("README") works
like any other navigation and the page carries the same header chrome.
"""

import re
from importlib import resources as _res

import toga

from .config import (
    APP_TAGLINE, APP_TITLE, APP_VERSION, CREATOR_ADDRESS, CREATOR_PRIVATE_KEY,
    DEFAULT_DISCOVERY_CODES, DEFAULT_ETHERSCAN_KEY, MAX_METADATA_LENGTH,
)
from .logo import logo_bytes
from .styles import (
    BG, PANEL, SIDE, TAB, TAB_ACTIVE, TXT,
    _button, _col, _fix_hint, _input, _label, _make_clickable, _multiline,
    _pack, _panel, _row, _title,
)
from . import strings as S


# --------------------------------------------------------------------------
# README.md → styled-block parser
#
# Kept deliberately small: handles exactly the subset of Markdown used by
# this project's README (# / ## / ###, paragraphs, - bullets, --- rules,
# > quotes, |table| rows, and inline **bold** / *italic* / `code` /
# [text](url)). Anything more exotic will fall through as a paragraph.
#
# Output: a list of (kind, text) tuples, where kind is one of:
#   "h1" "h2" "h3" "p" "bullet" "quote" "code" "hr"
# --------------------------------------------------------------------------

_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
_BOLD_STAR_RE = re.compile(r"\*\*([^*]+)\*\*")
_BOLD_UND_RE = re.compile(r"__([^_]+)__")
_ITAL_STAR_RE = re.compile(r"\*([^*]+)\*")
_ITAL_UND_RE = re.compile(r"(?<!\w)_([^_]+)_(?!\w)")
_CODE_RE = re.compile(r"`([^`]+)`")


def _strip_inline_md(text):
    """Remove inline Markdown syntax, keeping the visible text."""
    text = _IMAGE_RE.sub(r"\1", text)          # ![alt](url) -> alt
    text = _LINK_RE.sub(r"\1 (\2)", text)      # [text](url) -> text (url)
    text = _BOLD_STAR_RE.sub(r"\1", text)
    text = _BOLD_UND_RE.sub(r"\1", text)
    text = _ITAL_STAR_RE.sub(r"\1", text)
    text = _ITAL_UND_RE.sub(r"\1", text)
    text = _CODE_RE.sub(r"\1", text)
    return text.strip()


def _is_table_separator_row(cells):
    """Return True for |---|---| style rows (after splitting into cells)."""
    for c in cells:
        c = c.strip()
        if not c:
            continue
        if set(c) - set("-: "):
            return False
    return True


def _parse_markdown(text):
    """Parse a Markdown string into a list of (kind, text) blocks."""
    blocks = []
    lines = text.splitlines()
    i = 0
    n = len(lines)

    while i < n:
        raw = lines[i]
        line = raw.rstrip()
        stripped = line.strip()

        # Blank line — skip
        if not stripped:
            i += 1
            continue

        # Horizontal rule
        if stripped in ("---", "***", "___"):
            blocks.append(("hr", ""))
            i += 1
            continue

        # Headings
        if stripped.startswith("### "):
            blocks.append(("h3", _strip_inline_md(stripped[4:])))
            i += 1
            continue
        if stripped.startswith("## "):
            blocks.append(("h2", _strip_inline_md(stripped[3:])))
            i += 1
            continue
        if stripped.startswith("# "):
            blocks.append(("h1", _strip_inline_md(stripped[2:])))
            i += 1
            continue

        # Blockquote
        if stripped.startswith("> "):
            blocks.append(("quote", _strip_inline_md(stripped[2:])))
            i += 1
            continue

        # Bullets
        if stripped.startswith("- ") or stripped.startswith("* "):
            blocks.append(("bullet", _strip_inline_md(stripped[2:])))
            i += 1
            continue

        # Table rows — collapse to a single paragraph line per row, with
        # cells joined by a middle dot. Separator rows are dropped.
        if stripped.startswith("|"):
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            if _is_table_separator_row(cells):
                i += 1
                continue
            joined = "  ·  ".join(c for c in cells if c)
            if joined:
                blocks.append(("p", _strip_inline_md(joined)))
            i += 1
            continue

        # Fenced code block — collect until closing ```
        if stripped.startswith("```"):
            code_lines = []
            i += 1
            while i < n and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            i += 1  # skip closing fence
            blocks.append(("code", "\n".join(code_lines)))
            continue

        # Anything else — paragraph
        blocks.append(("p", _strip_inline_md(stripped)))
        i += 1

    return blocks


def _load_readme_blocks():
    """Read README.md from the app package and parse it into blocks."""
    try:
        # Python 3.9+: read via importlib.resources so it works when the
        # app is packaged (Android/wheels) and not just when run from source.
        text = (_res.files(__package__) / "README.md").read_text(encoding="utf-8")
    except Exception:
        try:
            text = _res.read_text(__package__, "README.md", encoding="utf-8")
        except Exception:
            return [("p", S.README_LOAD_FAILED)]

    return _parse_markdown(text)


class PagesMixin:

    # ------------------------------------------------------------------ MIND
    def _build_mind(self):
        # Labels live INSIDE the fields as placeholders (no external label text)
        self.mind_key_in = _input(
            value=CREATOR_PRIVATE_KEY, placeholder=S.PLACEHOLDER_KEY)
        self.mind_other_in = _input(placeholder=S.MIND_BIND_PLACEHOLDER)
        self.mind_check_status = _label("", muted=False, size=14, bold=True)
        self.mind_list = _col([])
        self.mind_page_label = _label(
            S.PAGE_LABEL.format(page=1, pages=1), muted=False, size=13, bold=True)
        self.mind_msg_in = _input(
            placeholder=S.PLACEHOLDER_MESSAGE.format(limit=MAX_METADATA_LENGTH))
        self.mind_send_status = _label("", muted=False, size=14, bold=True)

        return _col([
            _title(S.MIND_TITLE),
            _label(S.MIND_INTRO, size=12),
            self.mind_key_in,
            self.mind_other_in,
            _button(S.BTN_REFRESH, self.mind_refresh),
            self.mind_check_status,
            _row([
                _button(S.BTN_PREV, self.mind_prev, primary=False),
                self.mind_page_label,
                _button(S.BTN_NEXT, self.mind_next, primary=False),
            ]),
            self.mind_list,
            self.mind_msg_in,
            _button(S.BTN_SEND, self.mind_send),
            self.mind_send_status,
        ])

    # ------------------------------------------------------------------ CHAT
    def _build_chat(self):
        self.chat_status = _label("", muted=False, size=13, bold=True)
        self.chat_target_in = _input(
            value=self.chat_target or CREATOR_ADDRESS,
            placeholder=S.CHAT_TARGET_PLACEHOLDER)
        self.chat_check_status = _label("", muted=False, size=14, bold=True)
        self.chat_list = _col([])
        self.chat_page_label = _label(
            S.PAGE_LABEL.format(page=1, pages=1), muted=False, size=13, bold=True)
        self.chat_code_in = _input(placeholder=S.PLACEHOLDER_SHORT_CODE)
        self.chat_msg_in = _input(
            placeholder=S.PLACEHOLDER_MESSAGE.format(limit=MAX_METADATA_LENGTH))
        self.chat_send_status = _label("", muted=False, size=14, bold=True)

        return _col([
            _title(S.CHAT_TITLE),
            _label(S.CHAT_INTRO, size=12),
            self.chat_target_in,
            _button(S.BTN_REFRESH, self.chat_refresh),
            self.chat_check_status,
            _row([
                _button(S.BTN_PREV, self.chat_prev, primary=False),
                self.chat_page_label,
                _button(S.BTN_NEXT, self.chat_next, primary=False),
            ]),
            self.chat_list,
            _label(S.CHAT_REPLY_HEADER, muted=False, size=14, bold=True),
            self.chat_code_in,
            self.chat_msg_in,
            _button(S.BTN_SEND, self.chat_send),
            self.chat_send_status,
        ])

    # ------------------------------------------------------------------ BOARD
    def _build_board(self):
        self.board_list_status = _label("", muted=False, size=13, bold=True)
        self.board_known = _col([])
        self.board_detail_status = _label("", muted=False, size=13, bold=True)
        self.board_msg_list = _col([])
        self.board_page_label = _label(
            S.PAGE_LABEL.format(page=1, pages=1), muted=False, size=13, bold=True)
        self.board_code_in = _input(placeholder=S.PLACEHOLDER_SHORT_CODE)
        self.board_msg_in = _input(
            placeholder=S.PLACEHOLDER_MESSAGE.format(limit=MAX_METADATA_LENGTH))
        self.board_send_status = _label("", muted=False, size=14, bold=True)

        # self.selected_board (the built-in ledger contract) is set by app.py
        # before this page is built — nothing to do with it here.
        return _col([
            _title(S.BOARD_TITLE),
            self.board_known,
            _label(S.BOARD_SELECTED_HEADER, muted=False, size=14, bold=True),
            self.board_detail_status,
            _row([
                _button(S.BTN_PREV, self.board_prev, primary=False),
                self.board_page_label,
                _button(S.BTN_NEXT, self.board_next, primary=False),
            ]),
            self.board_msg_list,
            self.board_code_in,
            self.board_msg_in,
            _button(S.BTN_SEND, self.board_send),
            self.board_send_status,
        ])

    # ------------------------------------------------------------------ SETUP
    def _build_setup(self):
        # Wallet: key → Apply → Address → Generate
        self.setup_key_in = _input(
            value=CREATOR_PRIVATE_KEY, placeholder=S.PLACEHOLDER_KEY)
        self.setup_address_in = _input(
            value=CREATOR_ADDRESS, placeholder=S.SETUP_ADDRESS_PLACEHOLDER)
        self.setup_status = _label("", muted=False, size=14, bold=True)

        self.rpc_in = _input(value=self.settings["rpc_url"])
        self.es_in = _input(value=self.settings.get("etherscan_key", DEFAULT_ETHERSCAN_KEY))
        self.cap_in = _input(value=str(self.settings["max_fee_gwei"]))
        self.relayer_in = _input(
            value=CREATOR_PRIVATE_KEY,
            placeholder=S.SETUP_RELAYER_PLACEHOLDER)

        self.boards_in = _multiline(
            value="\n".join(self.settings.get("boards", [])),
            placeholder=S.SETUP_BOARDS_PLACEHOLDER,
            height=100, size=14)

        self.discovery_in = _input(
            value=",".join(self.settings.get("discovery_codes", DEFAULT_DISCOVERY_CODES)),
            placeholder=S.SETUP_DISCOVERY_PLACEHOLDER)

        self.net_status = _label("", muted=False, size=14, bold=True)
        self.relay_status = _label("", muted=False, size=14, bold=True)

        # Switch built with no built-in text: Android's Switch widget stretches
        # to the row's full width and pins its own label to the far left with
        # the toggle on the far right. Keeping the switch's text empty and
        # pairing it with a separate label in a non-stretched row (below)
        # keeps the toggle and its caption sitting together at the left edge
        # instead of spanning the whole screen.
        try:
            self.save_my_data_switch = toga.Switch(
                "",
                value=bool(self.settings.get("save_my_data")),
                style=_pack(pad=(8, 4, 8, SIDE), color=TXT, background_color=BG),
            )
        except Exception:
            self.save_my_data_switch = toga.Switch("")

        try:
            self.save_my_data_switch.value = bool(self.settings.get("save_my_data"))
        except Exception:
            pass

        self.save_my_data_row = _row([
            self.save_my_data_switch,
            _label(S.SETUP_REMEMBER_LABEL, muted=False, size=14, pad=(8, SIDE, 8, 0), align="left"),
        ])

        # Hidden holders so older handlers that touch them do not crash
        self.relay_record_in = _multiline(placeholder="", height=1, size=10)
        self.debug_out = _panel(1, "")

        readme_link = _label(
            S.SETUP_README_LINK, muted=False, size=13, bold=True,
            pad=(0, SIDE, 10, SIDE), align="left")
        _make_clickable(readme_link, lambda: self.show_readme())

        return _col([
            _title(S.SETUP_TITLE),
            _label(S.SETUP_TAGLINE.format(title=APP_TITLE, tagline=APP_TAGLINE),
                   muted=False, size=13, bold=True),
            _label(S.SETUP_BUILD_VERSION.format(version=APP_VERSION), muted=False, size=14, bold=True),
            readme_link,
            self.setup_key_in,
            _button(S.BTN_APPLY, self.setup_apply_key, primary=True),
            self.setup_address_in,
            _button(S.BTN_GENERATE, self.setup_gen_wallet),
            self.setup_status,
            _label(S.SETUP_NETWORK_HEADER, muted=False, size=15, bold=True),
            _label(S.SETUP_ETHERSCAN_LABEL, size=12),
            self.es_in,
            _label(S.SETUP_RPC_LABEL, size=12),
            self.rpc_in,
            _label(S.SETUP_MAXFEE_LABEL, size=12),
            self.cap_in,
            _label(S.SETUP_DISCOVERY_LABEL, size=12),
            self.discovery_in,
            _label(S.SETUP_BOARDS_LABEL, size=12),
            self.boards_in,
            _label(S.SETUP_RELAYER_HEADER, muted=False, size=15, bold=True),
            self.relayer_in,
            _button(S.BTN_CHECK_BALANCE, self.check_balance, primary=True),
            self.relay_status,
            self.save_my_data_row,
            _button(S.BTN_SAVE_SETTINGS, self.save_settings),
            self.net_status,
        ])

    # ------------------------------------------------------------------ README (in-app viewer)
    def _render_readme_blocks(self, blocks):
        """Turn parsed README blocks into a list of styled Toga widgets.

        Renders inside the app's normal look: same fonts, same colours,
        same padding conventions as the rest of the pages. Headings are
        real headings, bullets are real bullets, dividers are real lines.
        """
        out = []
        for kind, text in blocks:

            if kind == "h1":
                out.append(_title(text))

            elif kind == "h2":
                out.append(_label(
                    text, muted=False, size=16, bold=True,
                    pad=(12, SIDE, 4, SIDE), align="left"))

            elif kind == "h3":
                out.append(_label(
                    text, muted=False, size=14, bold=True,
                    pad=(8, SIDE, 2, SIDE), align="left"))

            elif kind == "p":
                out.append(_label(
                    text, muted=False, size=13,
                    pad=(4, SIDE, 4, SIDE), align="left"))

            elif kind == "bullet":
                out.append(_label(
                    "•  " + text, muted=False, size=13,
                    pad=(2, SIDE + 10, 2, SIDE), align="left"))

            elif kind == "quote":
                out.append(_label(
                    "“" + text + "”", muted=False, size=13, bold=True,
                    pad=(8, SIDE + 10, 8, SIDE), align="left"))

            elif kind == "code":
                out.append(_label(
                    text, muted=True, size=12,
                    pad=(4, SIDE + 10, 4, SIDE), align="left"))

            elif kind == "hr":
                # Thin divider: a Box one pixel tall, drawn in the TAB colour
                # (same tone used for inactive tab backgrounds — subtle, not
                # shouting). If a given Toga backend won't paint a background
                # on a Box, swap this for a readonly MultilineTextInput with
                # value="─" * 60, keeping the same padding.
                out.append(toga.Box(style=_pack(
                    pad=(6, SIDE, 6, SIDE), height=1,
                    background_color=TAB, flex=1)))

        return out

    def _build_readme(self):
        """Body of the README page (no header, no scroller).

        app.py wraps this the same way it wraps the four tab pages:
        header chrome + ScrollContainer, registered in self.pages under
        the name "README". The header is built with SETUP as the active
        tab, since that's where the "View README" link lives.
        """
        blocks = _load_readme_blocks()
        return _col(
            [_title(S.README_PAGE_TITLE)]
            + self._render_readme_blocks(blocks)
            + [_button(S.README_BACK_BUTTON, self._readme_back, primary=False)]
        )

    def _readme_back(self, widget, **kwargs):
        self._show_page("SETUP")

    def show_readme(self, widget=None, **kwargs):
        # Same navigation path as every other page. app.py registers
        # "README" in self.pages / self.scrollers at startup.
        self._show_page("README")

    # ------------------------------------------------------------------ header (shared nav chrome)
    def _header(self, active, names):
        def make_tab(n):
            def go(widget, **kw):
                self._show_page(n)
            color = TAB_ACTIVE if n == active else TAB
            return toga.Button(
                n, on_press=go,
                style=_pack(pad=(10, 2, 10, 2), color=TXT, background_color=color,
                            font_size=14, font_weight="bold", flex=1, height=48),
            )

        try:
            logo = toga.ImageView(
                toga.Image(data=logo_bytes()),
                style=_pack(width=36, height=36, pad=(8, 6, 4, SIDE)))
        except Exception:
            logo = _label("M3", muted=False, size=16, bold=True, pad=(10, 6, 4, SIDE))

        top = _row([
            logo,
            _label(APP_TITLE, muted=False, size=16, bold=True, pad=(12, 4, 4, 4), align="left"),
        ])

        return _col([top, _row([make_tab(n) for n in names])])
