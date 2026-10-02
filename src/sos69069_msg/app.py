"""
SOS69069 M3 — owned by no one.

Nav: MIND · CHAT · BOARD · SETUP

MIND  — self-records; optional session bind; time sort; bind wiped on app start
CHAT  — all posts to a target address; target survives restart; short-code reply
BOARD — many boards, ranked by activity; short-code reply
SETUP — wallet, network, relayer, board list, discovery codes
"""

import asyncio
import webbrowser
import json
import time
import traceback
from pathlib import Path

import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW

from .address_factory import AddressFactory, generate_seed
from .config import (
    APP_TAGLINE, APP_TITLE, APP_VERSION, CHAIN_ID, CONTRACT_ADDRESS,
    CREATOR_ADDRESS, CREATOR_PRIVATE_KEY, LEDGER_BOARD,
    DEFAULT_DISCOVERY_CODES, DEFAULT_ETHERSCAN_KEY, DEFAULT_MAX_FEE_GWEI,
    DEFAULT_RPC, LEGACY_DISCOVERY_CODES, MAX_METADATA_LENGTH,
)
from .conversation import ChatTargetStore, MindBind, WalletStore, random_wallet
from .debug_log import DebugLog
from .eip712 import verify_record
from .etherscan import EtherscanClient
from .logo import logo_bytes
from .message_engine import prepare_and_sign, short_code
from .reader import Inbox, PAGE_SIZE, count_to_address, sync_mind, sync_to_address
from .relayer import parse_record, submit
from .rpc import RpcClient
from .submission import build_record_signature_call
from .ethcrypto import KeyPair, normalize_address

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
SIDE = 14


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


HINT = "#9DB0A6"   # light grey-green: readable hint text on the dark fields


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


def _hex(b: bytes) -> str:
    return "0x" + b.hex()


def _from_hex(s: str) -> bytes:
    return bytes.fromhex(s.strip().removeprefix("0x"))


class SOS69069MsgApp(toga.App):
    def startup(self):
        try:
            self._real_startup()
        except Exception:
            err = traceback.format_exc()
            try:
                log = Path(getattr(self.paths, "data", ".") or ".") / "crash.txt"
                log.parent.mkdir(parents=True, exist_ok=True)
                log.write_text(err)
                DebugLog(log.parent / "debug.log").write("startup crash: " + err[:2000])
            except Exception:
                pass
            self.main_window = toga.MainWindow(title="Startup Crash")
            box = toga.Box(style=_pack(direction=COLUMN, margin=12))
            box.add(toga.Label("Startup crashed:"))
            box.add(toga.MultilineTextInput(value=err, readonly=True,
                                            style=_pack(flex=1, height=420)))
            self.main_window.content = box
            self.main_window.show()

    def _save_my_data(self) -> bool:
        return bool(self.settings.get("save_my_data"))

    def _creator_key(self) -> KeyPair:
        raw = CREATOR_PRIVATE_KEY.strip().removeprefix("0x")
        return KeyPair.from_private_key(bytes.fromhex(raw))

    def _persist_wallet(self, kp: KeyPair) -> None:
        """Only write wallet to disk when user opted in via Save settings."""
        if self._save_my_data():
            self.wallet_store.save(kp)

    def _persist_relayer(self, kp: KeyPair) -> None:
        if self._save_my_data():
            self.relayer_store.save(kp)

    def _apply_demo_defaults(self) -> None:
        """Creator key/address visible; non-saved user overrides discarded."""
        self.wallet = self._creator_key()
        self.relayer_custom = None
        self.chat_target = CREATOR_ADDRESS
        try:
            if getattr(self, "setup_key_in", None) is not None:
                self.setup_key_in.value = CREATOR_PRIVATE_KEY
            if getattr(self, "setup_address_in", None) is not None:
                self.setup_address_in.value = CREATOR_ADDRESS
            if getattr(self, "relayer_in", None) is not None:
                self.relayer_in.value = CREATOR_PRIVATE_KEY
            if getattr(self, "mind_key_in", None) is not None:
                self.mind_key_in.value = CREATOR_PRIVATE_KEY
            if getattr(self, "chat_target_in", None) is not None:
                self.chat_target_in.value = CREATOR_ADDRESS
        except Exception:
            pass

    def _real_startup(self):
        self.data_dir = Path(self.paths.data)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.log = DebugLog(self.data_dir / "debug.log")
        self.log.write("app start version=" + APP_VERSION)

        self.wallet_store = WalletStore(self.data_dir / "wallet.json")
        self.relayer_store = WalletStore(self.data_dir / "relayer_key.json")
        self.chat_store = ChatTargetStore(self.data_dir / "chat_target.json")
        self.settings_file = self.data_dir / "settings.json"
        self.seed_file = self.data_dir / "seed.hex"

        self.settings = self._load_settings()
        self.mind_bind = MindBind()  # always empty on start — session only
        self.relayer = None
        self.last_tx_link = ""
        self._refreshing = False
        self._refresh_started = 0.0
        self.relayer_custom = None

        # Board inboxes: keep on disk (not cleared). Mind/chat session lists reset.
        self.mind_inbox = Inbox(str(self.data_dir / "inbox_mind.json"))
        self.mind_inbox.clear()
        self.chat_inbox = Inbox(str(self.data_dir / "inbox_chat.json"))
        self.chat_inbox.clear()
        # ledger + extra board inboxes loaded per board address; default ledger inbox
        self.board_inbox = Inbox(
            str(self.data_dir / ("inbox_board_" + LEDGER_BOARD[2:12].lower() + ".json")))
        self.selected_board = LEDGER_BOARD
        self.board_counts = {}

        self.mind_page = self.chat_page = self.board_page = 1

        if self._save_my_data():
            self.wallet = self.wallet_store.load() or self._creator_key()
            self.chat_target = self.chat_store.load() or CREATOR_ADDRESS
            self.relayer_custom = self.relayer_store.load()
        else:
            # Drop any previously saved user overrides when flag is off
            try:
                self.wallet_store.clear()
            except Exception:
                pass
            try:
                self.relayer_store.clear()
            except Exception:
                pass
            try:
                self.chat_store.clear()
            except Exception:
                pass
            self.wallet = self._creator_key()
            self.chat_target = CREATOR_ADDRESS
            self.relayer_custom = None

        mind = self._build_mind()
        chat = self._build_chat()
        board = self._build_board()
        setup = self._build_setup()
        self._load_relayer_seed()

        # Prefill visible demo keys after widgets exist
        if not self._save_my_data():
            self._apply_demo_defaults()
        else:
            try:
                if self.wallet:
                    self.setup_address_in.value = self.wallet.address
                    # show key only if we still have creator as wallet (demo)
                    if self.wallet.address.lower() == CREATOR_ADDRESS.lower():
                        self.setup_key_in.value = CREATOR_PRIVATE_KEY
                        self.mind_key_in.value = CREATOR_PRIVATE_KEY
                        self.relayer_in.value = CREATOR_PRIVATE_KEY
                if self.chat_target:
                    self.chat_target_in.value = self.chat_target
            except Exception:
                pass

        bodies = {"BOARD": board, "CHAT": chat, "MIND": mind, "SETUP": setup}
        self.pages = {}
        self.scrollers = {}
        for name, body in bodies.items():
            scroller = toga.ScrollContainer(
                content=body, horizontal=False,
                style=_pack(flex=1, background_color=BG))
            self.scrollers[name] = scroller
            self.pages[name] = _col([self._header(name, list(bodies)), scroller], flex=1)

        self.main_window = toga.MainWindow(title=APP_TITLE)
        # Always open BOARD (ledger); user goes to SETUP themselves
        self.main_window.content = self.pages["BOARD"]
        self.main_window.show()
        self._hide_title_bar()
        _apply_borders()
        self._refresh_setup_labels()
        self._refresh_mind_status()
        self._refresh_chat_status()
        # Load board list + ledger messages in background
        try:
            import asyncio as _aio
            async def _boot_board():
                await self.board_refresh_list()
                await self.board_refresh_messages()
            try:
                _aio.get_event_loop().create_task(_boot_board())
            except Exception:
                _aio.create_task(_boot_board())
        except Exception:
            pass

    # ------------------------------------------------------------------ builders
    def _build_mind(self):
        # Labels live INSIDE the fields as placeholders (no external label text)
        self.mind_key_in = _input(
            value=CREATOR_PRIVATE_KEY, placeholder="My address private key")
        self.mind_other_in = _input(placeholder="Bind other address")
        self.mind_check_status = _label("", muted=False, size=14, bold=True)
        self.mind_list = _col([])
        self.mind_page_label = _label("Page 1 / 1", muted=False, size=13, bold=True)
        self.mind_msg_in = _input(placeholder=f"Message ≤{MAX_METADATA_LENGTH} chars")
        self.mind_send_status = _label("", muted=False, size=14, bold=True)
        return _col([
            _title("MIND"),
            _label("Self-records only. Optional bind is wiped when the app closes.", size=12),
            self.mind_key_in,
            self.mind_other_in,
            _button("Refresh", self.mind_refresh),
            self.mind_check_status,
            _row([
                _button("◀", self.mind_prev, primary=False),
                self.mind_page_label,
                _button("▶", self.mind_next, primary=False),
            ]),
            self.mind_list,
            self.mind_msg_in,
            _button("SEND", self.mind_send),
            self.mind_send_status,
        ])

    def _build_chat(self):
        self.chat_status = _label("", muted=False, size=13, bold=True)
        self.chat_target_in = _input(
            value=self.chat_target or CREATOR_ADDRESS,
            placeholder="Chat target address (0x…)")
        self.chat_check_status = _label("", muted=False, size=14, bold=True)
        self.chat_list = _col([])
        self.chat_page_label = _label("Page 1 / 1", muted=False, size=13, bold=True)
        self.chat_code_in = _input(placeholder="Short code (optional reply)")
        self.chat_msg_in = _input(placeholder=f"Message ≤{MAX_METADATA_LENGTH} chars")
        self.chat_send_status = _label("", muted=False, size=14, bold=True)
        return _col([
            _title("CHAT"),
            _label("All messages intendedTo = target. Target is kept after restart.", size=12),
            self.chat_target_in,
            _button("Refresh", self.chat_refresh),
            self.chat_check_status,
            _row([
                _button("◀", self.chat_prev, primary=False),
                self.chat_page_label,
                _button("▶", self.chat_next, primary=False),
            ]),
            self.chat_list,
            _label("Reply / post to target", muted=False, size=14, bold=True),
            self.chat_code_in,
            self.chat_msg_in,
            _button("SEND", self.chat_send),
            self.chat_send_status,
        ])

    def _build_board(self):
        self.board_list_status = _label("", muted=False, size=13, bold=True)
        self.board_known = _col([])
        self.board_detail_status = _label("", muted=False, size=13, bold=True)
        self.board_msg_list = _col([])
        self.board_page_label = _label("Page 1 / 1", muted=False, size=13, bold=True)
        self.board_code_in = _input(placeholder="Short code (optional reply)")
        self.board_msg_in = _input(placeholder=f"Message ≤{MAX_METADATA_LENGTH} chars")
        self.board_send_status = _label("", muted=False, size=14, bold=True)
        # Built-in ledger (contract) — not from SETUP
        self.selected_board = LEDGER_BOARD
        return _col([
            _title("BOARD"),
            self.board_known,
            _label("Selected board messages", muted=False, size=14, bold=True),
            self.board_detail_status,
            _row([
                _button("◀", self.board_prev, primary=False),
                self.board_page_label,
                _button("▶", self.board_next, primary=False),
            ]),
            self.board_msg_list,
            self.board_code_in,
            self.board_msg_in,
            _button("SEND", self.board_send),
            self.board_send_status,
        ])

    def _build_setup(self):
        # Wallet: key → Apply → Address → Copy → Generate
        self.setup_key_in = _input(
            value=CREATOR_PRIVATE_KEY, placeholder="My address private key")
        self.setup_address_in = _input(
            value=CREATOR_ADDRESS, placeholder="Address")
        self.setup_status = _label("", muted=False, size=14, bold=True)
        self.rpc_in = _input(value=self.settings["rpc_url"])
        self.es_in = _input(value=self.settings.get("etherscan_key", DEFAULT_ETHERSCAN_KEY))
        self.cap_in = _input(value=str(self.settings["max_fee_gwei"]))
        self.relayer_in = _input(
            value=CREATOR_PRIVATE_KEY,
            placeholder="Relayer private key (64 hex) or leave default")
        self.boards_in = _multiline(
            value="\n".join(self.settings.get("boards", [])),
            placeholder="Extra board addresses (one per line; ledger is separate)",
            height=100, size=14)
        self.discovery_in = _input(
            value=",".join(self.settings.get("discovery_codes", DEFAULT_DISCOVERY_CODES)),
            placeholder="M3:1, M3:2")
        self.net_status = _label("", muted=False, size=14, bold=True)
        self.relay_status = _label("", muted=False, size=14, bold=True)
        try:
            self.save_my_data_switch = toga.Switch(
                "Save my data on device",
                value=bool(self.settings.get("save_my_data")),
                # Fixed width so the switch doesn't stretch full-width and
                # center itself; it sits at the left edge like a normal row.
                style=_pack(pad=(8, SIDE, 8, SIDE), color=TXT, background_color=BG, width=260),
            )
        except Exception:
            self.save_my_data_switch = toga.Switch("Save my data on device")
            try:
                self.save_my_data_switch.value = bool(self.settings.get("save_my_data"))
            except Exception:
                pass
        # Hidden holders so older handlers that touch them do not crash
        self.relay_record_in = _multiline(placeholder="", height=1, size=10)
        self.debug_out = _panel(1, "")
        return _col([
            _title("SETUP"),
            _label(f"{APP_TITLE} — {APP_TAGLINE}", muted=False, size=13, bold=True),
            _label(f"Build version {APP_VERSION}", muted=False, size=14, bold=True),
            self.setup_key_in,
            _button("Apply", self.setup_apply_key, primary=True),
            self.setup_address_in,
            _button("Generate", self.setup_gen_wallet),
            self.setup_status,
            _label("Network", muted=False, size=15, bold=True),
            _label("Etherscan API key", size=12),
            self.es_in,
            _label("RPC URL", size=12),
            self.rpc_in,
            _label("Max fee (gwei)", size=12),
            self.cap_in,
            _label("Discovery codes", size=12),
            self.discovery_in,
            _label("Board addresses", size=12),
            self.boards_in,
            _label("Relayer / gas", muted=False, size=15, bold=True),
            self.relayer_in,
            _button("Check balance", self.check_balance, primary=False),
            self.relay_status,
            self.save_my_data_switch,
            _button("Save settings", self.save_settings),
            self.net_status,
        ])


    # ------------------------------------------------------------------ header
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

    def _show_page(self, name):
        self.main_window.content = self.pages[name]
        _apply_borders()

    def _hide_title_bar(self):
        try:
            from java import jclass
            self._impl.native.getSupportActionBar().hide()
        except Exception:
            pass

    # ------------------------------------------------------------------ settings / rpc
    def _load_settings(self):
        s = {
            "rpc_url": DEFAULT_RPC,
            "max_fee_gwei": DEFAULT_MAX_FEE_GWEI,
            "etherscan_key": DEFAULT_ETHERSCAN_KEY,
            "boards": [],
            "save_my_data": False,
            "discovery_codes": list(DEFAULT_DISCOVERY_CODES),
        }
        if self.settings_file.exists():
            try:
                s.update(json.loads(self.settings_file.read_text()))
            except Exception:
                pass
        # migrate the untouched old default (M/list) to the new M3:<n> format
        if list(s.get("discovery_codes") or []) == list(LEGACY_DISCOVERY_CODES):
            s["discovery_codes"] = list(DEFAULT_DISCOVERY_CODES)
        return s

    def _save_settings_file(self):
        self.settings_file.write_text(json.dumps(self.settings, indent=2))

    def save_settings(self, widget, **kwargs):
        try:
            RpcClient(self.rpc_in.value)
            cap = float(self.cap_in.value)
            if cap <= 0:
                raise ValueError("cap must be > 0")
            boards = []
            for line in (self.boards_in.value or "").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    boards.append(normalize_address(line))
                except Exception:
                    boards.append(line)  # ENS or raw — resolve later
            codes = [c.strip() for c in (self.discovery_in.value or "").split(",") if c.strip()]
            if not codes:  # empty -> one code per board in order: M3:1, M3:2, ...
                codes = [f"M3:{i}" for i in range(1, max(1, len(boards)) + 1)]
            save_flag = False
            try:
                save_flag = bool(self.save_my_data_switch.value)
            except Exception:
                save_flag = bool(self.settings.get("save_my_data"))
            # Extras only — strip ledger contract if user pasted it
            boards = [b for b in boards if str(b).lower() != LEDGER_BOARD.lower()]
            self.settings.update({
                "rpc_url": self.rpc_in.value.strip(),
                "max_fee_gwei": cap,
                "etherscan_key": (self.es_in.value or "").strip() or DEFAULT_ETHERSCAN_KEY,
                "boards": boards,
                "discovery_codes": codes,
                "save_my_data": save_flag,
            })
            self._save_settings_file()
            if save_flag:
                if self.wallet:
                    self.wallet_store.save(self.wallet)
                if self.chat_target:
                    self.chat_store.save(self.chat_target)
                # relayer field if 64 hex
                try:
                    raw = (self.relayer_in.value or "").strip().removeprefix("0x")
                    if len(raw) == 64:
                        self.relayer_store.save(KeyPair.from_private_key(bytes.fromhex(raw)))
                except Exception:
                    pass
                self.net_status.text = "Saved ✔  Data kept on device"
            else:
                try:
                    self.wallet_store.clear()
                    self.relayer_store.clear()
                    self.chat_store.clear()
                except Exception:
                    pass
                self.net_status.text = "Saved ✔  Demo defaults only (no user key storage)"
        except Exception as e:
            self._log_err("save_settings", e)
            self.net_status.text = f"Error: {e}"

    def _rpc(self):
        return RpcClient(self.settings["rpc_url"])

    def _backends(self):
        out = []
        key = (self.settings.get("etherscan_key") or "").strip()
        if key:
            try:
                out.append(("etherscan", EtherscanClient(key, CHAIN_ID)))
            except Exception:
                pass
        out.append(("rpc", self._rpc()))
        return out

    def _load_relayer_seed(self):
        if not self.seed_file.exists():
            self.seed_file.write_text(generate_seed().hex())
        seed = _from_hex(self.seed_file.read_text())
        factory = AddressFactory(seed, str(self.data_dir / "signer_counter.json"))
        self.relayer = factory.relayer_key(0)  # deterministic default (persisted via seed.hex)

        custom = self.relayer_store.load()
        if custom:
            self.relayer_custom = custom
            try:
                self.relayer_in.value = custom.private_key.hex()
            except Exception:
                pass
        elif self.relayer:
            self.relayer_custom = None
            try:
                self.relayer_in.value = self.relayer.address
            except Exception:
                pass

    def _active_relayer(self) -> KeyPair:
        raw = (self.relayer_in.value or "").strip().removeprefix("0x")
        if len(raw) == 64:
            kp = KeyPair.from_private_key(bytes.fromhex(raw))
            # Persist a custom relayer key locally so it survives restarts.
            if not (self.relayer_custom and self.relayer_custom.private_key == kp.private_key):
                self.relayer_store.save(kp)
                self.relayer_custom = kp
            return kp
        # Field cleared back to the default relayer's address (or emptied):
        # drop any saved custom override so the deterministic default returns.
        if self.relayer_custom is not None:
            self.relayer_store.clear()
            self.relayer_custom = None
        if not self.relayer:
            raise ValueError("No relayer key")
        return self.relayer

    def _require_wallet(self) -> KeyPair:
        if not self.wallet:
            raise ValueError("Generate a wallet in SETUP first")
        return self.wallet


    def _wire_click(self, widget, handler) -> None:
        """Make a Label/Button reliably tappable on Android; disable ALL CAPS on buttons."""
        try:
            native = widget._impl.native
            try:
                # Material buttons force uppercase — turns tx0x into TX0X
                native.setAllCaps(False)
            except Exception:
                pass
            try:
                from java import dynamic_proxy
                from android.view import View

                class Click(dynamic_proxy(View.OnClickListener)):
                    def onClick(self, v):
                        handler()

                native.setClickable(True)
                native.setFocusable(True)
                native.setOnClickListener(Click())
            except Exception:
                try:
                    from java import jclass
                    # fallback: keep on_press only
                    native.setAllCaps(False)
                except Exception:
                    pass
        except Exception:
            pass

    def _open_tx(self, tx_hash: str) -> None:
        """Open transaction on Etherscan (browser / system handler)."""
        h = (tx_hash or "").strip()
        if not h:
            return
        if not h.startswith("0x"):
            h = "0x" + h
        url = "https://etherscan.io/tx/" + h
        self.log.write("open tx " + h[:18])
        try:
            webbrowser.open(url)
            return
        except Exception:
            pass
        try:
            from java import jclass
            Intent = jclass("android.content.Intent")
            Uri = jclass("android.net.Uri")
            intent = Intent(Intent.ACTION_VIEW, Uri.parse(url))
            self._impl.native.startActivity(intent)
        except Exception as e:
            self.log.write("open tx failed: " + str(e))

    def _focus_reply_form(self, code_widget, msg_widget=None, page_name=None) -> None:
        """After REPLY: scroll the page to the BOTTOM (compose card), not the top."""
        async def _go():
            await asyncio.sleep(0.1)
            for w in (code_widget, msg_widget):
                if w is None:
                    continue
                try:
                    w.focus()
                except Exception:
                    pass
            await asyncio.sleep(0.05)
            sc = None
            if page_name and getattr(self, "scrollers", None):
                sc = self.scrollers.get(page_name)
            if sc is not None:
                try:
                    sc.vertical_position = 10 ** 9
                except Exception:
                    pass
            try:
                from java import jclass
                View = jclass("android.view.View")
                natives = []
                for w in (msg_widget, code_widget, sc):
                    if w is None:
                        continue
                    try:
                        natives.append(w._impl.native)
                    except Exception:
                        pass
                for native in natives:
                    parent = native
                    for _ in range(24):
                        try:
                            if hasattr(parent, "fullScroll"):
                                try:
                                    parent.fullScroll(View.FOCUS_DOWN)
                                except Exception:
                                    pass
                                try:
                                    child = parent.getChildAt(0)
                                    parent.scrollTo(0, max(0, child.getHeight() - parent.getHeight()))
                                except Exception:
                                    pass
                            parent = parent.getParent()
                        except Exception:
                            break
                if msg_widget is not None:
                    try:
                        msg_widget._impl.native.requestFocus()
                    except Exception:
                        pass
            except Exception:
                pass
        try:
            asyncio.get_event_loop().create_task(_go())
        except Exception:
            try:
                asyncio.create_task(_go())
            except Exception:
                pass


    # ------------------------------------------------------------------ card list helper
    def _fill_list(self, container, entries, page, page_label, on_reply=None):
        while container.children:
            container.remove(container.children[0])
        pages = max(1, -(-len(entries) // PAGE_SIZE))
        page = max(1, min(page, pages))
        start = (page - 1) * PAGE_SIZE
        slice_ = entries[start:start + PAGE_SIZE]
        page_label.text = f"Page {page} / {pages}"
        if not slice_:
            container.add(_clabel("No messages yet.", color=MUTED, size=13))
            return page
        for e in slice_:
            # Build every card child upfront, then construct the Box once.
            # Appending children with .add() to an already-built Box can
            # leave later children laid out incorrectly on Android (visible
            # as overlapping/clipped text) — building the full list first
            # avoids that class of layout bug entirely.
            children = [
                _clabel(e.get("text") or "", color=TXT, size=15, bold=True),
                _clabel(str(e.get("who") or e.get("address") or ""), color=GOLD, size=12, bold=True),
            ]
            if e.get("address"):
                children.append(_clabel(e["address"], color=GOLD, size=11))
            if e.get("tx"):
                txh = e["tx"]
                raw = txh if str(txh).startswith("0x") else ("0x" + str(txh))
                if len(raw) > 18:
                    shown = "tx" + raw[:10] + "…" + raw[-6:]
                else:
                    shown = "tx" + raw
                # Plain coloured text, made clickable via a native click listener
                # (see _make_clickable — Label's on_press kwarg is unreliable).
                link = _clabel(shown, color=BLUE, size=11)
                _make_clickable(link, lambda h=raw: self._open_tx(h))
                children.append(link)
            if e.get("block") or e.get("when"):
                children.append(_clabel(f"· block {e.get('block')} · {e.get('when')}", color=MUTED, size=11))
            if e.get("pending"):
                children.append(_clabel("⏳ NOT submitted yet", color=MUTED, size=12, bold=True))
            else:
                children.append(_clabel(f"TRUST Received 1 SOS · #{e.get('code')}", color=GREEN, size=12, bold=True))
            if on_reply and e.get("reply_id") and not e.get("pending"):
                rid = e["reply_id"]

                def make_handler(r=rid):
                    def handler(widget, **kw):
                        on_reply(r)
                    return handler

                children.append(_button(f"REPLY (start conv {rid})", make_handler(), primary=False))

            card = _col(children)
            # Panel look without double-passing background_color into _pack
            try:
                card.style.background_color = PANEL
            except Exception:
                pass
            container.add(card)
            container.add(_label("────────────────────", size=10, pad=(4, SIDE, 4, SIDE)))
        return page


    async def _sign_and_submit(self, text, intended_to=None, reply_code="", inbox=None, status_label=None):
        """Sign self/directed post and broadcast with active relayer (no separate Submit page)."""
        code, record = self._sign_and_queue(text, intended_to=intended_to, reply_code=reply_code, inbox=inbox)
        if status_label is not None:
            status_label.text = f"Signed #{code} — submitting…"
        try:
            relayer = self._active_relayer()
            rec = parse_record(record)
            tx = await asyncio.to_thread(
                submit, self._rpc(), relayer, rec, float(self.settings["max_fee_gwei"]))
            self.last_tx_link = f"https://etherscan.io/tx/{tx}"
            ph = rec.get("payload_hash") or rec.get("payloadHash") or ""
            if isinstance(ph, bytes):
                ph = "0x" + ph.hex()
            elif isinstance(ph, str) and ph and not ph.startswith("0x"):
                ph = "0x" + ph
            if inbox is not None and ph:
                inbox.mark_submitted(ph, tx)
            self.log.write("submit ok " + tx)
            if status_label is not None:
                status_label.text = f"Sent ✔ #{code}\n{self.last_tx_link}"
                _make_clickable(status_label, lambda h=tx: self._open_tx(h))
            return code, tx
        except Exception as e:
            self._log_err("submit", e)
            if status_label is not None:
                status_label.text = f"Signed #{code} but submit failed: {type(e).__name__}: {e}"
            raise

    def _sign_and_queue(self, text, intended_to=None, reply_code="", inbox=None):
        key = self._require_wallet()
        ph, meta, sig = prepare_and_sign(key, text, intended_to=intended_to, reply_code=reply_code)
        target = intended_to or key.address
        if not verify_record(key.address, target, ph, meta, sig):
            raise RuntimeError("Local signature check failed")
        call = build_record_signature_call(key.address, target, ph, sig, meta)
        record = json.dumps({
            "to": call["to"], "chainId": CHAIN_ID, "function": call["function"],
            "signer": call["args"][0], "intendedTo": call["args"][1],
            "payloadHash": _hex(ph), "signature": _hex(sig), "metadata": meta,
        }, indent=2)
        self.relay_record_in.value = record
        if inbox is not None:
            inbox.add_pending(_hex(ph), meta)
        code = short_code(_hex(ph))
        tgt = (intended_to or "self")
        self.log.write("signed #" + code + " intendedTo=" + str(tgt)[:14])
        return code, record

    # ------------------------------------------------------------------ SETUP
    def _refresh_setup_labels(self):
        if self.wallet:
            self.setup_address_in.value = self.wallet.address
            key_hex = self.wallet.private_key.hex()
            self.setup_key_in.value = key_hex
            if getattr(self, "mind_key_in", None) is not None:
                self.mind_key_in.value = key_hex
        else:
            self.setup_address_in.value = ""
            self.setup_key_in.value = ""
            if getattr(self, "mind_key_in", None) is not None:
                self.mind_key_in.value = ""

    def _copy(self, text: str) -> bool:
        try:
            self.clipboard.set_text(text)
            return True
        except Exception:
            pass
        try:
            from java import jclass
            Context = jclass("android.content.Context")
            ClipData = jclass("android.content.ClipData")
            cm = self._impl.native.getSystemService(Context.CLIPBOARD_SERVICE)
            cm.setPrimaryClip(ClipData.newPlainText("sos69069", text))
            return True
        except Exception:
            return False

    def _log_err(self, where: str, e: BaseException) -> None:
        """Always persist error text to the local debug log."""
        try:
            self.log.write("%s error: %s: %s" % (where, type(e).__name__, e))
        except Exception:
            pass

    def debug_view(self, widget, **kwargs):

        self.debug_out.value = self.log.read_tail()
        self.log.write("view log")

    def debug_copy(self, widget, **kwargs):
        text = self.log.read_tail(50_000)
        ok = self._copy(text)
        self.debug_out.value = "Copied log ✔" if ok else "Could not copy"
        self.log.write("copy log")

    def debug_clear(self, widget, **kwargs):
        self.log.clear()
        self.debug_out.value = "(empty log)"
        self.log.write("log cleared")


    def _mind_apply_key_if_any(self):
        """If MIND key field has 64 hex chars, use it as the active wallet."""
        raw = (getattr(self, "mind_key_in", None) and self.mind_key_in.value or "").strip().removeprefix("0x")
        if len(raw) == 64:
            self.wallet = KeyPair.from_private_key(bytes.fromhex(raw))
            self._persist_wallet(self.wallet)
            self._refresh_setup_labels()
            self.log.write("mind key applied " + self.wallet.address[:12])

    def setup_apply_key(self, widget, **kwargs):
        try:
            raw = (self.setup_key_in.value or "").strip().removeprefix("0x")
            if len(raw) != 64:
                raise ValueError("Paste a 64-hex private key")
            self.wallet = KeyPair.from_private_key(bytes.fromhex(raw))
            self._persist_wallet(self.wallet)
            self.setup_address_in.value = self.wallet.address
            self.log.write("setup key applied " + self.wallet.address[:12])
            msg = "Key applied ✔"
            if not self._save_my_data():
                msg += " (session only — enable Save my data + Save settings to keep)"
            self.setup_status.text = msg
        except Exception as e:
            self._log_err("setup_apply_key", e)
            self.setup_status.text = f"Error: {e}"

    def setup_copy_address(self, widget, **kwargs):
        addr = (self.setup_address_in.value or "").strip()
        if not addr and self.wallet:
            addr = self.wallet.address
        if not addr:
            self.setup_status.text = "No address to copy"
            return
        ok = self._copy(addr)
        self.setup_status.text = "Address copied ✔" if ok else "Could not copy"
        self.log.write("copy address")

    def setup_gen_wallet(self, widget, **kwargs):
        try:
            self.wallet = random_wallet()
            self.wallet_store.save(self.wallet)
            self._refresh_setup_labels()
            self._refresh_mind_status()
            self.log.write("wallet generated " + self.wallet.address[:12])
            self.setup_status.text = "Wallet created ✔  Back it up offline if needed."
        except Exception as e:
            self._log_err("setup_gen_wallet", e)
            self.setup_status.text = f"Error: {e}"

    async def check_balance(self, widget, **kwargs):
        try:
            relayer = self._active_relayer()
            wei = await asyncio.to_thread(self._rpc().balance, relayer.address)
            self.relay_status.text = f"{wei / 1e18:.6f} ETH\n{relayer.address}"
        except Exception as e:
            self._log_err("check_balance", e)
            self.relay_status.text = f"Error: {type(e).__name__}: {e}"

    async def submit_record(self, widget, **kwargs):
        try:
            relayer = self._active_relayer()
            rec = parse_record(self.relay_record_in.value)
            self.relay_status.text = f"Submitting with {relayer.address[:12]}…"
            tx = await asyncio.to_thread(
                submit, self._rpc(), relayer, rec, float(self.settings["max_fee_gwei"]))
            self.last_tx_link = f"https://etherscan.io/tx/{tx}"
            self.relay_status.text = f"Sent ✔\n{self.last_tx_link}"
            _make_clickable(self.relay_status, lambda h=tx: self._open_tx(h))
            self.log.write("submit ok " + tx)
            ph = rec.get("payload_hash") or rec.get("payloadHash") or ""
            if isinstance(ph, bytes):
                ph = "0x" + ph.hex()
            elif isinstance(ph, str) and ph and not ph.startswith("0x"):
                ph = "0x" + ph
            for inbox in (self.mind_inbox, self.chat_inbox, self.board_inbox):
                if ph:
                    inbox.mark_submitted(ph, tx)
        except Exception as e:
            self._log_err("submit", e)
            self.relay_status.text = f"Error: {type(e).__name__}: {e}"

    # ------------------------------------------------------------------ MIND
    def _refresh_mind_status(self):
        # No external My/Bind status labels — key + bind live in the input placeholders
        if self.mind_bind.other:
            self.mind_other_in.value = self.mind_bind.other
        # Keep mind_key_in as user-entered; do not auto-fill private key

    def mind_bind_other(self, widget, **kwargs):
        try:
            self._mind_apply_key_if_any()
            raw = (self.mind_other_in.value or "").strip()
            if not raw:
                raise ValueError("Paste an address to bind")
            self.mind_bind.set(raw)
            self._refresh_mind_status()
            self.log.write("mind bind " + (self.mind_bind.other or "")[:14])
            self.mind_check_status.text = "Bound for this session only ✔"
        except Exception as e:
            self._log_err("mind_bind", e)
            self.mind_check_status.text = f"Error: {e}"

    def mind_clear_bind(self, widget, **kwargs):
        self.mind_bind.clear()
        self.mind_inbox.clear()
        self.mind_other_in.value = ""
        self._refresh_mind_status()
        # mind_key_in left as-is so user can keep the same key
        self.mind_page = 1
        self._fill_list(self.mind_list, [], 1, self.mind_page_label)
        self.log.write("mind bind cleared")
        self.mind_check_status.text = "Bind cleared"

    async def mind_refresh(self, widget, **kwargs):
        try:
            self._mind_apply_key_if_any()
            # Refresh also binds "other" from the field (session only; cleared on app kill)
            raw = (self.mind_other_in.value or "").strip()
            if raw:
                self.mind_bind.set(raw)
                self.mind_other_in.value = self.mind_bind.other or raw
        except Exception as e:
            self._log_err("mind_refresh_prep", e)
            self.mind_check_status.text = f"Error: {e}"
            return
        if not self.wallet:
            self.mind_check_status.text = "Paste private key above or open SETUP"
            return
        if self._refreshing and time.monotonic() - self._refresh_started < 90:
            self.mind_check_status.text = "Already scanning…"
            return
        self._refreshing = True
        self._refresh_started = time.monotonic()
        self.mind_check_status.text = "Scanning…"
        loop = asyncio.get_running_loop()

        def progress(msg):
            loop.call_soon_threadsafe(lambda: setattr(self.mind_check_status, "text", msg))

        try:
            self.mind_inbox.last_block = None
            last_err = None
            for name, client in self._backends():
                try:
                    new = await asyncio.to_thread(
                        sync_mind, client, self.wallet.address,
                        self.mind_bind.other, self.mind_inbox, None, progress)
                    self.mind_page = 1
                    self._show_mind_messages()
                    total = len(self.mind_inbox.messages) + len(self.mind_inbox.pending())
                    self.mind_check_status.text = (
                        f"{new} new · {total} total · via {name} · block {self.mind_inbox.last_block}"
                    )
                    self.log.write(f"mind refresh via {name}: {new} new, {total} total")
                    return
                except Exception as e:
                    last_err = e
            self._log_err("mind_refresh", last_err)
            self.mind_check_status.text = f"Error: {type(last_err).__name__}: {last_err}"
        finally:
            self._refreshing = False

    def _show_mind_messages(self):
        entries = self.mind_inbox.entries(self.wallet.address if self.wallet else "")
        self.mind_page = self._fill_list(
            self.mind_list, entries, self.mind_page, self.mind_page_label, on_reply=None)

    def mind_prev(self, widget, **kwargs):
        if self.mind_page > 1:
            self.mind_page -= 1
            self._show_mind_messages()

    def mind_next(self, widget, **kwargs):
        self.mind_page += 1
        self._show_mind_messages()

    async def mind_send(self, widget, **kwargs):
        try:
            self._mind_apply_key_if_any()
            text = (self.mind_msg_in.value or "").strip()
            if not text:
                raise ValueError("Type a message")
            await self._sign_and_submit(
                text, intended_to=None, inbox=self.mind_inbox,
                status_label=self.mind_send_status)
            self.mind_msg_in.value = ""
            self._show_mind_messages()
        except Exception as e:
            self._log_err("mind_send", e)
            self.mind_send_status.text = f"Error: {e}"

    # ------------------------------------------------------------------ CHAT
    def _refresh_chat_status(self):
        # Target is shown only inside the input field (no external "Target: 0x…" label)
        pass

    def chat_save_target(self, widget, **kwargs):
        try:
            raw = (self.chat_target_in.value or "").strip()
            if not raw:
                raise ValueError("Paste a target address")
            self.chat_target = normalize_address(raw)
            if self._save_my_data():
                self.chat_store.save(self.chat_target)
            self.chat_target_in.value = self.chat_target
            self._refresh_chat_status()
            self.log.write("chat target saved " + self.chat_target[:14])
            self.chat_check_status.text = "Target saved (kept after restart) ✔"
        except Exception as e:
            self._log_err("chat_save_target", e)
            self.chat_check_status.text = f"Error: {e}"

    async def chat_refresh(self, widget, **kwargs):
        # Refresh also saves the target from the input field
        try:
            raw = (self.chat_target_in.value or "").strip()
            if raw:
                self.chat_target = normalize_address(raw)
                if self._save_my_data():
                    self.chat_store.save(self.chat_target)
                self.chat_target_in.value = self.chat_target
        except Exception as e:
            self.chat_check_status.text = f"Error: {e}"
            return
        if not self.chat_target:
            self.chat_check_status.text = "Paste a target address first"
            return
        if self._refreshing and time.monotonic() - self._refresh_started < 90:
            self.chat_check_status.text = "Already scanning…"
            return
        self._refreshing = True
        self._refresh_started = time.monotonic()
        loop = asyncio.get_running_loop()

        def progress(msg):
            loop.call_soon_threadsafe(lambda: setattr(self.chat_check_status, "text", msg))

        try:
            self.chat_inbox.last_block = None
            last_err = None
            for name, client in self._backends():
                try:
                    new = await asyncio.to_thread(
                        sync_to_address, client, self.chat_target,
                        self.chat_inbox, None, progress)
                    self.chat_page = 1
                    self._show_chat_messages()
                    total = len(self.chat_inbox.messages) + len(self.chat_inbox.pending())
                    self.chat_check_status.text = (
                        f"{new} new · {total} total · via {name} · block {self.chat_inbox.last_block}"
                    )
                    self.log.write(f"chat refresh via {name}: {new} new, {total} total")
                    return
                except Exception as e:
                    last_err = e
            self._log_err("chat_refresh", last_err)
            self.chat_check_status.text = f"Error: {type(last_err).__name__}: {last_err}"
        finally:
            self._refreshing = False

    def _show_chat_messages(self):
        my = self.wallet.address if self.wallet else ""
        entries = self.chat_inbox.entries(my)

        def on_reply(rid):
            self.chat_code_in.value = rid
            self._focus_reply_form(self.chat_code_in, self.chat_msg_in, page_name="CHAT")
            self.chat_check_status.text = "Reply code set — scroll to compose below ✔"

        self.chat_page = self._fill_list(
            self.chat_list, entries, self.chat_page, self.chat_page_label, on_reply=on_reply)

    def chat_prev(self, widget, **kwargs):
        if self.chat_page > 1:
            self.chat_page -= 1
            self._show_chat_messages()

    def chat_next(self, widget, **kwargs):
        self.chat_page += 1
        self._show_chat_messages()

    async def chat_send(self, widget, **kwargs):
        try:
            if not self.chat_target:
                raise ValueError("Save a chat target first")
            text = (self.chat_msg_in.value or "").strip()
            if not text:
                raise ValueError("Type a message")
            await self._sign_and_submit(
                text, intended_to=self.chat_target,
                reply_code=self.chat_code_in.value or "",
                inbox=self.chat_inbox, status_label=self.chat_send_status)
            self.chat_msg_in.value = ""
            self.chat_code_in.value = ""
            self._show_chat_messages()
        except Exception as e:
            self._log_err("chat_send", e)
            self.chat_send_status.text = f"Error: {e}"

    # ------------------------------------------------------------------ BOARD

    def board_select_ledger(self, widget, **kwargs):
        self.selected_board = LEDGER_BOARD
        self.board_detail_status.text = f"Reading ledger {LEDGER_BOARD[:12]}…"
        try:
            self.board_detail_status.style.color = GREEN
        except Exception:
            pass
        self.board_inbox = Inbox(
            str(self.data_dir / ("inbox_board_" + LEDGER_BOARD[2:12].lower() + ".json")))
        self._paint_board_list()
        try:
            import asyncio
            asyncio.create_task(self.board_refresh_messages())
        except Exception:
            pass

    def _paint_board_list(self):
        """Ledger first (design), then SETUP extras; selected = green."""
        ranked = getattr(self, "_ranked_boards", []) or []
        while self.board_known.children:
            self.board_known.remove(self.board_known.children[0])
        sel = (self.selected_board or LEDGER_BOARD).lower()

        def add_btn(addr, n, label_prefix=""):
            is_sel = addr.lower() == sel
            label = f"{label_prefix}{addr[:12]}…  ({n} msgs)"
            if is_sel:
                label = "● " + label

            def make_open(address=addr):
                def handler(widget, **kw):
                    self.selected_board = address
                    self.board_detail_status.text = f"Reading: {address}"
                    try:
                        self.board_detail_status.style.color = GREEN
                    except Exception:
                        pass
                    self.board_inbox = Inbox(
                        str(self.data_dir / (
                            "inbox_board_" + address[2:12].lower() + ".json")))
                    self._paint_board_list()
                    import asyncio
                    asyncio.create_task(self.board_refresh_messages())
                return handler

            if is_sel:
                btn = toga.Button(
                    label, on_press=make_open(),
                    style=_pack(
                        pad=(10, SIDE, 10, SIDE), color=TXT, background_color=GREEN,
                        font_size=16, font_weight="bold", height=52),
                )
            else:
                btn = _button(label, make_open(), primary=False)
            self.board_known.add(btn)

        # Built-in ledger always first
        n_ledger = 0
        for a, n in ranked:
            if a.lower() == LEDGER_BOARD.lower():
                n_ledger = n
                break
        add_btn(LEDGER_BOARD, n_ledger, label_prefix="Ledger ")
        for addr, n in ranked:
            if addr.lower() == LEDGER_BOARD.lower():
                continue
            add_btn(addr, n)

    async def board_refresh_list(self, widget=None, **kwargs):
        extras = list(self.settings.get("boards") or [])
        boards = [LEDGER_BOARD] + [b for b in extras if str(b).lower() != LEDGER_BOARD.lower()]
        self.board_list_status.text = "Counting messages…"
        counts = {}
        try:
            client = self._backends()[0][1]
            for b in boards:
                try:
                    addr = normalize_address(b) if b.startswith("0x") else b
                    n = await asyncio.to_thread(count_to_address, client, addr)
                    counts[addr] = n
                except Exception:
                    counts[b] = 0
            self.board_counts = counts
            ranked = sorted(counts.items(), key=lambda x: -x[1])
            while self.board_known.children:
                self.board_known.remove(self.board_known.children[0])
            self._ranked_boards = ranked
            self._paint_board_list()
            self.board_list_status.text = f"{len(ranked)} boards"
        except Exception as e:
            self._log_err("board_list", e)
            self.board_list_status.text = f"Error: {type(e).__name__}: {e}"

    async def board_refresh_messages(self, widget=None, **kwargs):
        if not self.selected_board:
            self.board_detail_status.text = "Select a board from the list"
            return
        self.board_detail_status.text = f"Scanning {self.selected_board[:12]}…"
        try:
            self.board_inbox = Inbox(
                str(self.data_dir / f"inbox_board_{self.selected_board[2:12].lower()}.json"))
            self.board_inbox.last_block = None
            last_err = None
            for name, client in self._backends():
                try:
                    new = await asyncio.to_thread(
                        sync_to_address, client, self.selected_board,
                        self.board_inbox, None, None)
                    self.board_page = 1
                    self._show_board_messages()
                    total = len(self.board_inbox.messages)
                    self.board_detail_status.text = (
                        f"Reading {self.selected_board[:12]}… · {new} new · {total} total · via {name}"
                    )
                    try:
                        self.board_detail_status.style.color = GREEN
                    except Exception:
                        pass
                    return
                except Exception as e:
                    last_err = e
            if last_err is not None:
                self._log_err("board_refresh", last_err)
            self.board_detail_status.text = (
                f"Error: {type(last_err).__name__}: {last_err}" if last_err else "Error"
            )
        except Exception as e:
            self._log_err("board_refresh", e)
            self.board_detail_status.text = f"Error: {e}"

    def _show_board_messages(self):
        my = self.wallet.address if self.wallet else ""
        entries = self.board_inbox.entries(my)

        def on_reply(rid):
            self.board_code_in.value = rid
            self._focus_reply_form(self.board_code_in, self.board_msg_in, page_name="BOARD")
            self.board_detail_status.text = "Reply code set — compose below ✔"

        self.board_page = self._fill_list(
            self.board_msg_list, entries, self.board_page,
            self.board_page_label, on_reply=on_reply)

    def board_prev(self, widget, **kwargs):
        if self.board_page > 1:
            self.board_page -= 1
            self._show_board_messages()

    def board_next(self, widget, **kwargs):
        self.board_page += 1
        self._show_board_messages()

    async def board_send(self, widget, **kwargs):
        try:
            if not self.selected_board:
                raise ValueError("Select a board first")
            text = (self.board_msg_in.value or "").strip()
            if not text:
                raise ValueError("Type a message")
            await self._sign_and_submit(
                text, intended_to=self.selected_board,
                reply_code=self.board_code_in.value or "",
                inbox=self.board_inbox, status_label=self.board_send_status)
            self.board_msg_in.value = ""
            self.board_code_in.value = ""
            self._show_board_messages()
        except Exception as e:
            self._log_err("board_send", e)
            self.board_send_status.text = f"Error: {e}"


def main():
    return SOS69069MsgApp("sos69069 m3", "org.sos69069.m3")
