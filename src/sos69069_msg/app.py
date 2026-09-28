"""
SOS69069 M3 — owned by no one.

Nav: MIND · CHAT · BOARD · SETUP

MIND  — self-records; optional session bind; time sort; bind wiped on app start
CHAT  — all posts to a target address; target survives restart; short-code reply
BOARD — many boards, ranked by activity; short-code reply
SETUP — wallet, network, relayer, board list, discovery codes
"""

import asyncio
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
    DEFAULT_DISCOVERY_CODES, DEFAULT_ETHERSCAN_KEY, DEFAULT_MAX_FEE_GWEI,
    DEFAULT_RPC, MAX_METADATA_LENGTH,
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
    return toga.Box(style=_pack(direction=COLUMN, background_color=BG, **kw), children=children)


def _row(children, **kw):
    return toga.Box(style=_pack(direction=ROW, background_color=BG, **kw), children=children)


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


def _input(value="", placeholder=""):
    """Editable field: white typed text + white Android hint when possible."""
    w = toga.TextInput(
        value=value if value is not None else "",
        placeholder=placeholder,
        style=_pack(
            pad=(4, SIDE, 6, SIDE),
            color="#FFFFFF",
            background_color="#1A2420",
            font_size=16,
            height=50,
        ),
    )
    _force_white_field_text(w)
    return w


def _multiline(value="", placeholder="", height=100, readonly=False):
    w = toga.MultilineTextInput(
        value=value if value is not None else "",
        placeholder=placeholder,
        readonly=readonly,
        style=_pack(
            pad=(6, SIDE, 6, SIDE),
            color="#FFFFFF",
            background_color="#1A2420" if not readonly else PANEL,
            font_size=14,
            height=height,
        ),
    )
    _force_white_field_text(w)
    return w


def _force_white_field_text(widget) -> None:
    """Android: force EditText text + hint (placeholder) to white."""
    try:
        from java import jclass
        Color = jclass("android.graphics.Color")
        white = Color.parseColor("#FFFFFF")
        hint = Color.parseColor("#CCFFFFFF")  # slightly soft white for hints
        native = widget._impl.native
        native.setTextColor(white)
        native.setHintTextColor(hint)
        try:
            native.setHighlightColor(Color.parseColor("#3305AA34"))
        except Exception:
            pass
    except Exception:
        pass


def _panel(height=120, placeholder=""):
    return toga.MultilineTextInput(
        readonly=True, value=placeholder,
        style=_pack(pad=(6, SIDE, 6, SIDE), color="#FFFFFF", background_color=PANEL,
                    font_size=14, height=height),
    )


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

    def _real_startup(self):
        self.data_dir = Path(self.paths.data)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.log = DebugLog(self.data_dir / "debug.log")
        self.log.write("app start version=" + APP_VERSION)

        self.wallet_store = WalletStore(self.data_dir / "wallet.json")
        self.chat_store = ChatTargetStore(self.data_dir / "chat_target.json")
        self.settings_file = self.data_dir / "settings.json"
        self.seed_file = self.data_dir / "seed.hex"

        self.wallet = self.wallet_store.load()
        self.mind_bind = MindBind()  # always empty on start — session only
        self.chat_target = self.chat_store.load()
        self.settings = self._load_settings()
        self.relayer = None
        self.last_tx_link = ""
        self._refreshing = False
        self._refresh_started = 0.0

        self.mind_inbox = Inbox(str(self.data_dir / "inbox_mind.json"))
        self.mind_inbox.clear()  # wipe mind cache on every start
        self.chat_inbox = Inbox(str(self.data_dir / "inbox_chat.json"))
        self.board_inbox = Inbox(str(self.data_dir / "inbox_board.json"))
        self.selected_board = None
        self.board_counts = {}  # addr -> count

        self.mind_page = self.chat_page = self.board_page = 1
        self._load_relayer_seed()

        mind = self._build_mind()
        chat = self._build_chat()
        board = self._build_board()
        setup = self._build_setup()

        bodies = {"MIND": mind, "CHAT": chat, "BOARD": board, "SETUP": setup}
        self.pages = {}
        for name, body in bodies.items():
            scroller = toga.ScrollContainer(
                content=body, horizontal=False,
                style=_pack(flex=1, background_color=BG))
            self.pages[name] = _col([self._header(name, list(bodies)), scroller], flex=1)

        self.main_window = toga.MainWindow(title=APP_TITLE)
        self.main_window.content = self.pages["MIND"] if self.wallet else self.pages["SETUP"]
        self.main_window.show()
        self._hide_title_bar()
        self._refresh_setup_labels()
        self._refresh_mind_status()
        self._refresh_chat_status()
        self._recolor_all_inputs()

    # ------------------------------------------------------------------ builders
    def _build_mind(self):
        self.mind_status = _label("", muted=False, size=13, bold=True)
        self.mind_other_in = _input(placeholder="Bind other address (session only)")
        self.mind_check_status = _label("", muted=False, size=14, bold=True)
        self.mind_list = _col([])
        self.mind_page_label = _label("Page 1 / 1", muted=False, size=13, bold=True)
        self.mind_msg_in = _input(placeholder=f"Message ≤{MAX_METADATA_LENGTH} chars")
        self.mind_send_status = _label("", muted=False, size=14, bold=True)
        return _col([
            _title("MIND"),
            _label("Self-records only. Optional bind is wiped when the app closes.", size=12),
            self.mind_status,
            _label("Other address to bind (session only)", size=13, muted=False),
            self.mind_other_in,
            _row([
                _button("Bind", self.mind_bind_other, primary=False),
                _button("Clear bind", self.mind_clear_bind, primary=False),
            ]),
            _button("Refresh", self.mind_refresh),
            self.mind_check_status,
            _row([
                _button("◀", self.mind_prev, primary=False),
                self.mind_page_label,
                _button("▶", self.mind_next, primary=False),
            ]),
            self.mind_list,
            _label("New self-message (no short-code reply)", muted=False, size=14, bold=True),
            _label("Type message here (max %d chars)" % MAX_METADATA_LENGTH, size=13, muted=False),
            self.mind_msg_in,
            _button("SEND", self.mind_send),
            self.mind_send_status,
        ])

    def _build_chat(self):
        self.chat_status = _label("", muted=False, size=13, bold=True)
        self.chat_target_in = _input(
            value=self.chat_target or "", placeholder="Chat target address (0x…)")
        self.chat_check_status = _label("", muted=False, size=14, bold=True)
        self.chat_list = _col([])
        self.chat_page_label = _label("Page 1 / 1", muted=False, size=13, bold=True)
        self.chat_code_in = _input(placeholder="Short code (optional reply)")
        self.chat_msg_in = _input(placeholder=f"Message ≤{MAX_METADATA_LENGTH} chars")
        self.chat_send_status = _label("", muted=False, size=14, bold=True)
        return _col([
            _title("CHAT"),
            _label("All messages intendedTo = target. Target is kept after restart.", size=12),
            self.chat_status,
            _label("Chat target address (0x…)", size=13, muted=False),
            self.chat_target_in,
            _button("Save target", self.chat_save_target, primary=False),
            _button("Refresh", self.chat_refresh),
            self.chat_check_status,
            _row([
                _button("◀", self.chat_prev, primary=False),
                self.chat_page_label,
                _button("▶", self.chat_next, primary=False),
            ]),
            self.chat_list,
            _label("Reply / post to target", muted=False, size=14, bold=True),
            _label("Short code (optional)", size=13, muted=False),
            self.chat_code_in,
            _label("Message text", size=13, muted=False),
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
        return _col([
            _title("BOARD"),
            _label("Public boards. Sorted by activity. Short-code replies allowed.", size=12),
            _button("Refresh board list", self.board_refresh_list),
            self.board_list_status,
            self.board_known,
            _label("Selected board messages", muted=False, size=14, bold=True),
            self.board_detail_status,
            _row([
                _button("◀", self.board_prev, primary=False),
                self.board_page_label,
                _button("▶", self.board_next, primary=False),
            ]),
            self.board_msg_list,
            _label("Short code (optional)", size=13, muted=False),
            self.board_code_in,
            _label("Message text", size=13, muted=False),
            self.board_msg_in,
            _button("SEND to board", self.board_send),
            self.board_send_status,
        ])

    def _build_setup(self):
        self.setup_wallet_out = _panel(70, "No wallet yet")
        self.setup_status = _label("", muted=False, size=14, bold=True)
        self.rpc_in = _input(value=self.settings["rpc_url"])
        self.es_in = _input(value=self.settings.get("etherscan_key", DEFAULT_ETHERSCAN_KEY))
        self.cap_in = _input(value=str(self.settings["max_fee_gwei"]))
        self.relayer_in = _input(placeholder="Relayer private key (64 hex) or leave default")
        self.boards_in = _multiline(
            value="\n".join(self.settings.get("boards", [])),
            placeholder="Board addresses (one per line, 0x or ENS)",
            height=100)
        self.discovery_in = _input(
            value=",".join(self.settings.get("discovery_codes", DEFAULT_DISCOVERY_CODES)))
        self.net_status = _label("", muted=False, size=14, bold=True)
        self.relay_status = _label("", muted=False, size=14, bold=True)
        self.debug_out = _panel(140, "(tap View log)")
        self.relay_record_in = _multiline(
            placeholder="Signed record JSON (from SEND)",
            height=120)
        return _col([
            _title("SETUP"),
            _label(f"{APP_TITLE} — {APP_TAGLINE}", muted=False, size=13, bold=True),
            _label(f"Build version {APP_VERSION}", muted=False, size=14, bold=True),
            _label("Wallet", muted=False, size=15, bold=True),
            self.setup_wallet_out,
            _button("Generate wallet", self.setup_gen_wallet),
            self.setup_status,
            _label("Network", muted=False, size=15, bold=True),
            _label("Etherscan API key", size=12),
            self.es_in,
            _label("RPC URL", size=12),
            self.rpc_in,
            _label("Max fee (gwei)", size=12),
            self.cap_in,
            _label("Board addresses (one per line)", size=12),
            self.boards_in,
            _label("Discovery codes (comma-separated, e.g. M/list)", size=12),
            self.discovery_in,
            _button("Save settings", self.save_settings, primary=False),
            self.net_status,
            _label("Relayer / gas", muted=False, size=15, bold=True),
            _label("Paste 64-hex private key to pay gas, or leave default.", size=13, muted=False),
            self.relayer_in,
            _button("Check balance", self.check_balance, primary=False),
            self.relay_status,
            _label("Submit signed record", muted=False, size=14, bold=True),
            self.relay_record_in,
            _button("Submit to Ethereum", self.submit_record),
            _label("Debug log (local)", muted=False, size=15, bold=True),
            _label("Stored on device only. No private keys.", size=12),
            self.debug_out,
            _row([
                _button("View log", self.debug_view, primary=False),
                _button("Copy log", self.debug_copy, primary=False),
                _button("Clear log", self.debug_clear, primary=False),
            ]),
        ])

    # ------------------------------------------------------------------ header
    def _header(self, active, names):
        def make_tab(n):
            def go(widget, **kw):
                self.main_window.content = self.pages[n]
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

    def _hide_title_bar(self):
        try:
            from java import jclass
            self._impl.native.getSupportActionBar().hide()
        except Exception:
            pass

    def _recolor_all_inputs(self):
        """Re-apply white text/hint after native widgets exist."""
        for name in (
            "mind_other_in", "mind_msg_in",
            "chat_target_in", "chat_code_in", "chat_msg_in",
            "board_code_in", "board_msg_in",
            "rpc_in", "es_in", "cap_in", "relayer_in", "discovery_in",
            "boards_in", "relay_record_in",
        ):
            w = getattr(self, name, None)
            if w is not None:
                _force_white_field_text(w)

    # ------------------------------------------------------------------ settings / rpc
    def _load_settings(self):
        s = {
            "rpc_url": DEFAULT_RPC,
            "max_fee_gwei": DEFAULT_MAX_FEE_GWEI,
            "etherscan_key": DEFAULT_ETHERSCAN_KEY,
            "boards": [],
            "discovery_codes": list(DEFAULT_DISCOVERY_CODES),
        }
        if self.settings_file.exists():
            try:
                s.update(json.loads(self.settings_file.read_text()))
            except Exception:
                pass
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
            self.settings.update({
                "rpc_url": self.rpc_in.value.strip(),
                "max_fee_gwei": cap,
                "etherscan_key": (self.es_in.value or "").strip() or DEFAULT_ETHERSCAN_KEY,
                "boards": boards,
                "discovery_codes": codes or list(DEFAULT_DISCOVERY_CODES),
            })
            self._save_settings_file()
            self.net_status.text = "Saved ✔"
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
        self.relayer = factory.relayer_key(0)
        if self.relayer:
            try:
                self.relayer_in.value = self.relayer.address
            except Exception:
                pass

    def _active_relayer(self) -> KeyPair:
        raw = (self.relayer_in.value or "").strip().removeprefix("0x")
        if len(raw) == 64:
            return KeyPair.from_private_key(bytes.fromhex(raw))
        if not self.relayer:
            raise ValueError("No relayer key")
        return self.relayer

    def _require_wallet(self) -> KeyPair:
        if not self.wallet:
            raise ValueError("Generate a wallet in SETUP first")
        return self.wallet

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
            card = _col([
                _clabel(e.get("text") or "", color=TXT, size=15, bold=True),
                _clabel(str(e.get("who") or e.get("address") or ""), color=GOLD, size=12, bold=True),
            ], background_color=PANEL)
            if e.get("address"):
                card.add(_clabel(e["address"], color=GOLD, size=11))
            if e.get("tx"):
                card.add(_clabel("tx" + e["tx"], color=BLUE, size=11))
            if e.get("block") or e.get("when"):
                card.add(_clabel(f"· block {e.get('block')} · {e.get('when')}", color=MUTED, size=11))
            if e.get("pending"):
                card.add(_clabel("⏳ NOT submitted yet", color=MUTED, size=12, bold=True))
            else:
                card.add(_clabel(f"TRUST Received 1 SOS · #{e.get('code')}", color=GREEN, size=12, bold=True))
            if on_reply and e.get("reply_id") and not e.get("pending"):
                rid = e["reply_id"]

                def make_handler(r=rid):
                    def handler(widget, **kw):
                        on_reply(r)
                    return handler

                card.add(_button(f"REPLY (start conv {rid})", make_handler(), primary=False))
            container.add(card)
            container.add(_label("────────────────────", size=10, pad=(4, SIDE, 4, SIDE)))
        return page

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
            self.setup_wallet_out.value = f"Address:\n{self.wallet.address}"
        else:
            self.setup_wallet_out.value = "No wallet — tap Generate wallet."

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
        if not self.wallet:
            self.mind_status.text = "No wallet — open SETUP"
            return
        other = self.mind_bind.other or "(none)"
        self.mind_status.text = f"My: {self.wallet.address[:12]}…\nBind: {other if other == '(none)' else other[:12] + '…'}"

    def mind_bind_other(self, widget, **kwargs):
        try:
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
        self.mind_page = 1
        self._fill_list(self.mind_list, [], 1, self.mind_page_label)
        self.log.write("mind bind cleared")
        self.mind_check_status.text = "Bind cleared"

    async def mind_refresh(self, widget, **kwargs):
        if not self.wallet:
            self.mind_check_status.text = "Generate wallet in SETUP"
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

    def mind_send(self, widget, **kwargs):
        try:
            text = (self.mind_msg_in.value or "").strip()
            if not text:
                raise ValueError("Type a message")
            code, _ = self._sign_and_queue(text, intended_to=None, inbox=self.mind_inbox)
            self.mind_send_status.text = f"Signed ✔ #{code} — open SETUP → Submit"
            self.mind_msg_in.value = ""
            self._show_mind_messages()
            self.main_window.content = self.pages["SETUP"]
        except Exception as e:
            self._log_err("mind_send", e)
            self.mind_send_status.text = f"Error: {e}"

    # ------------------------------------------------------------------ CHAT
    def _refresh_chat_status(self):
        t = self.chat_target or "(none)"
        self.chat_status.text = f"Target: {t if t == '(none)' else t}"

    def chat_save_target(self, widget, **kwargs):
        try:
            raw = (self.chat_target_in.value or "").strip()
            if not raw:
                raise ValueError("Paste a target address")
            self.chat_target = normalize_address(raw)
            self.chat_store.save(self.chat_target)
            self.chat_target_in.value = self.chat_target
            self._refresh_chat_status()
            self.log.write("chat target saved " + self.chat_target[:14])
            self.chat_check_status.text = "Target saved (kept after restart) ✔"
        except Exception as e:
            self._log_err("chat_save_target", e)
            self.chat_check_status.text = f"Error: {e}"

    async def chat_refresh(self, widget, **kwargs):
        if not self.chat_target:
            self.chat_check_status.text = "Save a target address first"
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

        self.chat_page = self._fill_list(
            self.chat_list, entries, self.chat_page, self.chat_page_label, on_reply=on_reply)

    def chat_prev(self, widget, **kwargs):
        if self.chat_page > 1:
            self.chat_page -= 1
            self._show_chat_messages()

    def chat_next(self, widget, **kwargs):
        self.chat_page += 1
        self._show_chat_messages()

    def chat_send(self, widget, **kwargs):
        try:
            if not self.chat_target:
                raise ValueError("Save a chat target first")
            text = (self.chat_msg_in.value or "").strip()
            if not text:
                raise ValueError("Type a message")
            code, _ = self._sign_and_queue(
                text, intended_to=self.chat_target,
                reply_code=self.chat_code_in.value or "",
                inbox=self.chat_inbox)
            self.chat_send_status.text = f"Signed ✔ #{code} — open SETUP → Submit"
            self.chat_msg_in.value = ""
            self.chat_code_in.value = ""
            self._show_chat_messages()
            self.main_window.content = self.pages["SETUP"]
        except Exception as e:
            self._log_err("chat_send", e)
            self.chat_send_status.text = f"Error: {e}"

    # ------------------------------------------------------------------ BOARD
    async def board_refresh_list(self, widget, **kwargs):
        boards = list(self.settings.get("boards") or [])
        if not boards:
            self.board_list_status.text = "Add board addresses in SETUP"
            return
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
            for addr, n in ranked:
                a = addr

                def make_open(address=a):
                    def handler(widget, **kw):
                        self.selected_board = address
                        self.board_detail_status.text = f"Board: {address}"
                        asyncio.create_task(self.board_refresh_messages())
                    return handler

                self.board_known.add(
                    _button(f"{addr[:12]}…  ({n} msgs)", make_open(), primary=False))
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
                        f"{self.selected_board[:12]}… · {new} new · {total} total · via {name}"
                    )
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

    def board_send(self, widget, **kwargs):
        try:
            if not self.selected_board:
                raise ValueError("Select a board first")
            text = (self.board_msg_in.value or "").strip()
            if not text:
                raise ValueError("Type a message")
            code, _ = self._sign_and_queue(
                text, intended_to=self.selected_board,
                reply_code=self.board_code_in.value or "",
                inbox=self.board_inbox)
            self.board_send_status.text = f"Signed ✔ #{code} — open SETUP → Submit"
            self.board_msg_in.value = ""
            self.board_code_in.value = ""
            self._show_board_messages()
            self.main_window.content = self.pages["SETUP"]
        except Exception as e:
            self._log_err("board_send", e)
            self.board_send_status.text = f"Error: {e}"


def main():
    return SOS69069MsgApp("sos69069 m3", "org.sos69069.m3")
