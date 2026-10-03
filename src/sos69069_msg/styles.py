"""
All visual styling for SOS69069 M3 in one place: colors, spacing, and the
small widget-builder helpers every page uses (_col, _row, _label, _input,
_button, ...). Pages (pages.py) and app.py import from here instead of
defining their own look — change a color or a field's border here and it
changes everywhere.
"""

import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW

# ---------------------------------------------------------------- palette
BG = "#090E0A"
FIELD = "#1A2420"
PANEL = "#141A16"
GREEN = "#05AA34"
GREY = "#2F3B35"
TAB = "#3A4540"
TAB_ACTIVE = "#05AA34"
TXT = "#FFFFFF"
MUTED = "#A8B5B0"
GOLD = "#E8C547"
BLUE = "#4FA3D1"
HINT = "#9DB0A6"   # light grey-green: readable hint text on the dark fields

SIDE = 14


# ---------------------------------------------------------------- layout helpers
def _pack(pad=None, **kw):
    if pad is not None:
        for key in ("margin", "padding"):
            try:
                return Pack(**{key: pad}, **kw)
            except Exception:
                continue
    return Pack(**kw)


def _col(children, **kw):
    kw.setdefault("background_color", BG)
    return toga.Box(style=_pack(direction=COLUMN, **kw), children=children)


def _row(children, **kw):
    kw.setdefault("background_color", BG)
    return toga.Box(style=_pack(direction=ROW, **kw), children=children)


def _label(text="", muted=True, size=14, bold=False, pad=(8, SIDE, 4, SIDE), align="center", **kw):
    extra = {"font_weight": "bold"} if bold else {}
    try:
        return toga.Label(
            text,
            style=_pack(pad=pad, color=MUTED if muted else TXT, background_color=BG,
                        font_size=size, text_align=align, **extra, **kw),
        )
    except Exception:
        return toga.Label(
            text,
            style=_pack(pad=pad, color=MUTED if muted else TXT, background_color=BG,
                        font_size=size, **extra, **kw),
        )


def _clabel(text="", color=TXT, size=13, bold=False, pad=(2, SIDE, 2, SIDE), **kw):
    extra = {"font_weight": "bold"} if bold else {}
    try:
        return toga.Label(
            text,
            style=_pack(pad=pad, color=color, background_color=PANEL,
                        font_size=size, text_align="left", **extra, **kw),
        )
    except Exception:
        return toga.Label(
            text,
            style=_pack(pad=pad, color=color, background_color=PANEL,
                        font_size=size, **extra, **kw),
        )


def _title(text):
    return _label(text, muted=False, size=20, bold=True, pad=(16, SIDE, 6, SIDE))


# ---------------------------------------------------------------- Android-only fixups
def _fix_hint(widget, text_color="#FFFFFF", hint_color=HINT):
    """Android: Pack `color` does not colour the placeholder (hint), which stays
    dark on our dark fields. Set hint + text colour on the native EditText."""
    try:
        from android.graphics import Color  # Chaquopy; absent on desktop
        impl = widget._impl
        for name in ("_textview", "_edittext", "native"):
            native = getattr(impl, name, None)
            if native is not None and hasattr(native, "setHintTextColor"):
                native.setHintTextColor(Color.parseColor(hint_color))
                native.setTextColor(Color.parseColor(text_color))
                break
    except Exception:
        pass  # desktop / different backend: leave defaults
    return widget


_BORDERED = []   # (widget, background) pairs that get a blue border on Android


def _apply_borders():
    """Blue rounded border on every editable field (Android only; Pack has no borders).
    Safe to call repeatedly."""
    try:
        from android.graphics import Color
        from android.graphics.drawable import GradientDrawable
    except Exception:
        return
    for widget, bg in _BORDERED:
        try:
            native = widget._impl.native
            dens = native.getContext().getResources().getDisplayMetrics().density
            d = GradientDrawable()
            d.setColor(Color.parseColor(bg))
            d.setStroke(int(2 * dens), Color.parseColor(BLUE))
            d.setCornerRadius(8 * dens)
            native.setBackground(d)
            px_h, px_v = int(12 * dens), int(8 * dens)
            native.setPadding(px_h, px_v, px_h, px_v)
        except Exception:
            pass


def _bordered(widget, bg="#1A2420"):
    _BORDERED.append((widget, bg))
    return widget


def _make_clickable(widget, on_tap):
    """Wire a real Android OnClickListener onto the widget's native view.

    toga.Label silently accepts an `on_press` kwarg on some backend versions
    (no TypeError raised) but never actually calls it, so links built that
    way looked right but did nothing when tapped. Attaching the listener to
    the native view directly is reliable regardless of Toga/Label quirks."""
    try:
        from java import dynamic_proxy
        from android.view import View

        class _Click(dynamic_proxy(View.OnClickListener)):
            def onClick(self, view):
                try:
                    on_tap()
                except Exception:
                    pass

        native = widget._impl.native
        native.setOnClickListener(_Click())
        native.setClickable(True)
        native.setFocusable(True)
    except Exception:
        pass
    return widget


# ---------------------------------------------------------------- field builders
def _multiline(value="", placeholder="", height=100, size=14, readonly=False):
    return _bordered(_fix_hint(toga.MultilineTextInput(
        value=value, placeholder=placeholder, readonly=readonly,
        style=_pack(pad=(6, SIDE, 6, SIDE), color="#FFFFFF", background_color="#1A2420",
                    font_size=size, height=height))))


def _input(value="", placeholder=""):
    """Editable field: white text on dark background (readable on Android)."""
    return _bordered(_fix_hint(toga.TextInput(
        value=value if value is not None else "",
        placeholder=placeholder,
        style=_pack(
            pad=(4, SIDE, 6, SIDE),
            color="#FFFFFF",
            background_color="#1A2420",
            font_size=16,
            height=50,
        ),
    )))


def _panel(height=120, placeholder=""):
    return _fix_hint(toga.MultilineTextInput(
        readonly=True, value=placeholder,
        style=_pack(pad=(6, SIDE, 6, SIDE), color="#FFFFFF", background_color=PANEL,
                    font_size=14, height=height),
    ))


def _button(text, handler, primary=True):
    bg = GREEN if primary else GREY
    return toga.Button(
        text, on_press=handler,
        style=_pack(pad=(10, SIDE, 10, SIDE), color=TXT, background_color=bg,
                    font_size=16, font_weight="bold", height=52),
    )
