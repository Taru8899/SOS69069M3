"""
SOS69069 M3 — owned by no One.

Nav: MIND · CHAT · BOARD · SETUP

MIND  — self-records; optional session bind; time sort; bind wiped on app start
CHAT  — all posts to a target address; target survives restart; short-code reply
BOARD — many boards, ranked by activity; short-code reply
SETUP — wallet, network, relayer, board list, discovery codes

This file holds app lifecycle and all event-handler logic (refresh, sign,
submit, settings). Page layout lives in pages.py (PagesMixin, mixed in
below), visual styling in styles.py, and on-screen text in strings.py.

The README page is a non-tab page: it is registered in self.pages under
the name "README" the same way the four tab pages are, so _show_page()
and the header behave identically — but it is not part of the `bodies`
dict, so it never appears as a tab. It is reachable only via the
"View README" link on SETUP.
"""

import asyncio
import webbrowser
import json
import time
import traceback
from pathlib import Path

import toga
from toga.style.pack import COLUMN

from .address_factory import AddressFactory, generate_seed
from .config import (
    APP_TITLE, APP_VERSION, CHAIN_ID, CONTRACT_ADDRESS,
    CREATOR_ADDRESS, CREATOR_PRIVATE_KEY, LEDGER_BOARD,
    DEFAULT_DISCOVERY_CODES, DEFAULT_ETHERSCAN_KEY, DEFAULT_MAX_FEE_GWEI,
    DEFAULT_RPC,
)
from .conversation import ChatTargetStore, MindBind, WalletStore, random_wallet
from .debug_log import DebugLog
from .eip712 import verify_record
from .etherscan import EtherscanClient
from .message_engine import prepare_and_sign, short_code
from .pages import PagesMixin
from .reader import Inbox, PAGE_SIZE, count_to_address, sync_mind, sync_to_address
from .relayer import parse_record, submit
from .rpc import RpcClient
from .submission import build_record_signature_call
from .ethcrypto import KeyPair, normalize_address
from .styles import (
    BG, BLUE, GOLD, GREEN, MUTED, PANEL, SIDE, TXT,
    _apply_borders, _button, _clabel, _col, _label, _make_clickable, _pack,
)
from . import strings as S


def _hex(b: bytes) -> str:
    return "0x" + b.hex()


def _from_hex(s: str) -> bytes:
    return bytes.fromhex(s.strip().removeprefix("0x"))


class SOS69069MsgApp(toga.App, PagesMixin):
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
            self.main_window = toga.MainWindow(title=S.STARTUP_CRASH_TITLE)
            box = toga.Box(style=_pack(direction=COLUMN, margin=12))
            box.add(toga.Label(S.STARTUP_CRASH_LABEL))
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
        self.readme_page = self._build_readme()
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

        # README: a non-tab page reachable only via the "View README" link
        # on SETUP. Wrapped with the same header chrome as the four tab
        # pages, with SETUP highlighted as the active tab (that's where the
        # link lives). Not part of `bodies`, so it never appears as a tab.
        readme_scroller = toga.ScrollContainer(
            content=self.readme_page, horizontal=False,
            style=_pack(flex=1, background_color=BG))
        self.scrollers["README"] = readme_scroller
        self.pages["README"] = _col(
            [self._header("SETUP", list(bodies)), readme_scroller], flex=1)

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

    def _show_page(self, name):
        self.main_window.content = self.pages[name]
        _apply_borders()
        self._auto_load_page(name)

    def _auto_load_page(self, name):
        """Load messages as soon as a page is opened, same as BOARD does at startup."""
        try:
            import asyncio as _aio

            async def _boot_chat():
                await self.chat_refresh(None)

            async def _boot_mind():
                await self.mind_refresh(None)

            async def _boot_board_tab():
                await self.board_refresh_list(None)
                await self.board_refresh_messages()

            task = {
                "CHAT": _boot_chat,
                "MIND": _boot_mind,
                "BOARD": _boot_board_tab,
                # "README" and "SETUP" need no auto-load
            }.get(name)
            if task is None:
                return
            try:
                _aio.get_event_loop().create_task(task())
            except Exception:
                _aio.create_task(task())
        except Exception:
            pass

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
        return s

    def _save_settings_file(self):
        self.settings_file.write_text(json.dumps(self.settings, indent=2))

    def save_settings(self, widget, **kwargs):
        try:
            RpcClient(self.rpc_in.value)
            cap = float(self.cap_in.value)
            if cap <= 0:
                raise ValueError(S.SETUP_CAP_MUST_BE_POSITIVE)
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
                self.net_status.text = S.SETUP_SAVED_KEPT
            else:
                try:
                    self.wallet_store.clear()
                    self.relayer_store.clear()
                    self.chat_store.clear()
                except Exception:
                    pass
                self.net_status.text = S.SETUP_SAVED_DEMO_ONLY
        except Exception as e:
            self._log_err("save_settings", e)
            self.net_status.text = S.ERR_SIMPLE.format(error=e)

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
            raise ValueError(S.SETUP_NO_RELAYER_KEY)
        return self.relayer

    def _require_wallet(self) -> KeyPair:
        if not self.wallet:
            raise ValueError(S.SETUP_NO_WALLET)
        return self.wallet

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
        page_label.text = S.PAGE_LABEL.format(page=page, pages=pages)
        if not slice_:
            container.add(_clabel(S.LIST_EMPTY, color=MUTED, size=13))
            return page
        for e in slice_:
            card = _col([
                _clabel(e.get("text") or "", color=TXT, size=15, bold=True),
                _clabel(str(e.get("who") or e.get("address") or ""), color=GOLD, size=12, bold=True),
            ])
            # Panel look without double-passing background_color into _pack
            try:
                card.style.background_color = PANEL
            except Exception:
                pass
            if e.get("address"):
                card.add(_clabel(e["address"], color=GOLD, size=11))
            if e.get("tx"):
                txh = e["tx"]
                raw = txh if str(txh).startswith("0x") else ("0x" + str(txh))
                if len(raw) > 18:
                    shown = "tx" + raw[:10] + "…" + raw[-6:]
                else:
                    shown = "tx" + raw
                # Plain blue text (same as _clabel); click via native listener
                link = _clabel(shown, color=BLUE, size=11)
                _make_clickable(link, lambda h=raw: self._open_tx(h))
                card.add(link)
            if e.get("block") or e.get("when"):
                card.add(_clabel(
                    S.TX_BLOCK_LINE.format(block=e.get("block"), when=e.get("when")),
                    color=MUTED, size=11))
            if e.get("pending"):
                card.add(_clabel(S.TX_PENDING, color=MUTED, size=12, bold=True))
            else:
                card.add(_clabel(S.TX_RECEIVED.format(code=e.get("code")), color=GREEN, size=12, bold=True))
            if on_reply and e.get("reply_id") and not e.get("pending"):
                rid = e["reply_id"]

                def make_handler(r=rid):
                    def handler(widget, **kw):
                        on_reply(r)
                    return handler

                card.add(_button(S.REPLY_BUTTON.format(rid=rid), make_handler(), primary=False))
            container.add(card)
            container.add(_label(S.LIST_SEPARATOR, size=10, pad=(4, SIDE, 4, SIDE)))
        return page

    async def _sign_and_submit(self, text, intended_to=None, reply_code="", inbox=None, status_label=None):
        """Sign self/directed post and broadcast with active relayer (no separate Submit page)."""
        code, record = self._sign_and_queue(text, intended_to=intended_to, reply_code=reply_code, inbox=inbox)
        if status_label is not None:
            status_label.text = S.SETUP_SIGNED_SUBMITTING.format(code=code)
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
                status_label.text = S.SETUP_SENT_WITH_CODE.format(code=code, link=self.last_tx_link)
                _make_clickable(status_label, lambda h=tx: self._open_tx(h))
            return code, tx
        except Exception as e:
            self._log_err("submit", e)
            if status_label is not None:
                status_label.text = S.SETUP_SUBMIT_FAILED.format(
                    code=code, type=type(e).__name__, error=e)
            raise

    def _sign_and_queue(self, text, intended_to=None, reply_code="", inbox=None):
        key = self._require_wallet()
        ph, meta, sig = prepare_and_sign(key, text, intended_to=intended_to, reply_code=reply_code)
        target = intended_to or key.address
        if not verify_record(key.address, target, ph, meta, sig):
            raise RuntimeError(S.SETUP_LOCAL_SIG_CHECK_FAILED)
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
        self.debug_out.value = "Copied log ✔" if ok else S.SETUP_COPY_FAILED
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
                raise ValueError(S.SETUP_NEED_KEY)
            self.wallet = KeyPair.from_private_key(bytes.fromhex(raw))
            self._persist_wallet(self.wallet)
            self.setup_address_in.value = self.wallet.address
            self.log.write("setup key applied " + self.wallet.address[:12])
            self.setup_status.text = S.SETUP_KEY_APPLIED
        except Exception as e:
            self._log_err("setup_apply_key", e)
            self.setup_status.text = S.ERR_SIMPLE.format(error=e)

    def setup_copy_address(self, widget, **kwargs):
        addr = (self.setup_address_in.value or "").strip()
        if not addr and self.wallet:
            addr = self.wallet.address
        if not addr:
            self.setup_status.text = S.SETUP_NO_ADDRESS_TO_COPY
            return
        ok = self._copy(addr)
        self.setup_status.text = S.SETUP_ADDRESS_COPIED if ok else S.SETUP_COPY_FAILED
        self.log.write("copy address")

    def setup_gen_wallet(self, widget, **kwargs):
        try:
            self.wallet = random_wallet()
            self.wallet_store.save(self.wallet)
            self._refresh_setup_labels()
            self._refresh_mind_status()
            self.log.write("wallet generated " + self.wallet.address[:12])
            self.setup_status.text = S.SETUP_WALLET_CREATED
        except Exception as e:
            self._log_err("setup_gen_wallet", e)
            self.setup_status.text = S.ERR_SIMPLE.format(error=e)

    async def check_balance(self, widget, **kwargs):
        try:
            relayer = self._active_relayer()
            wei = await asyncio.to_thread(self._rpc().balance, relayer.address)
            self.relay_status.text = S.SETUP_BALANCE_RESULT.format(eth=wei / 1e18, address=relayer.address)
        except Exception as e:
            self._log_err("check_balance", e)
            self.relay_status.text = S.ERR_TYPED.format(type=type(e).__name__, error=e)

    async def submit_record(self, widget, **kwargs):
        try:
            relayer = self._active_relayer()
            rec = parse_record(self.relay_record_in.value)
            self.relay_status.text = S.SETUP_SUBMITTING_WITH.format(address=relayer.address[:12])
            tx = await asyncio.to_thread(
                submit, self._rpc(), relayer, rec, float(self.settings["max_fee_gwei"]))
            self.last_tx_link = f"https://etherscan.io/tx/{tx}"
            self.relay_status.text = S.SETUP_SENT.format(link=self.last_tx_link)
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
            self.relay_status.text = S.ERR_TYPED.format(type=type(e).__name__, error=e)

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
                raise ValueError(S.MIND_NEED_ADDRESS)
            self.mind_bind.set(raw)
            self._refresh_mind_status()
            self.log.write("mind bind " + (self.mind_bind.other or "")[:14])
            self.mind_check_status.text = S.MIND_BOUND_OK
        except Exception as e:
            self._log_err("mind_bind", e)
            self.mind_check_status.text = S.ERR_SIMPLE.format(error=e)

    def mind_clear_bind(self, widget, **kwargs):
        self.mind_bind.clear()
        self.mind_inbox.clear()
        self.mind_other_in.value = ""
        self._refresh_mind_status()
        # mind_key_in left as-is so user can keep the same key
        self.mind_page = 1
        self._fill_list(self.mind_list, [], 1, self.mind_page_label)
        self.log.write("mind bind cleared")
        self.mind_check_status.text = S.MIND_BIND_CLEARED

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
            self.mind_check_status.text = S.ERR_SIMPLE.format(error=e)
            return
        if not self.wallet:
            self.mind_check_status.text = S.MIND_NEED_KEY
            return
        if self._refreshing and time.monotonic() - self._refresh_started < 90:
            self.mind_check_status.text = S.MIND_ALREADY_SCANNING
            return
        self._refreshing = True
        self._refresh_started = time.monotonic()
        self.mind_check_status.text = S.MIND_SCANNING
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
                    self.mind_check_status.text = S.MIND_SCAN_RESULT.format(
                        new=new, total=total, name=name, block=self.mind_inbox.last_block)
                    self.log.write(f"mind refresh via {name}: {new} new, {total} total")
                    return
                except Exception as e:
                    last_err = e
            self._log_err("mind_refresh", last_err)
            self.mind_check_status.text = S.ERR_TYPED.format(type=type(last_err).__name__, error=last_err)
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
                raise ValueError(S.MIND_NEED_MESSAGE)
            await self._sign_and_submit(
                text, intended_to=None, inbox=self.mind_inbox,
                status_label=self.mind_send_status)
            self.mind_msg_in.value = ""
            self._show_mind_messages()
        except Exception as e:
            self._log_err("mind_send", e)
            self.mind_send_status.text = S.ERR_SIMPLE.format(error=e)

    # ------------------------------------------------------------------ CHAT
    def _refresh_chat_status(self):
        # Target is shown only inside the input field (no external "Target: 0x…" label)
        pass

    def chat_save_target(self, widget, **kwargs):
        try:
            raw = (self.chat_target_in.value or "").strip()
            if not raw:
                raise ValueError(S.CHAT_NEED_TARGET_ADDRESS)
            self.chat_target = normalize_address(raw)
            if self._save_my_data():
                self.chat_store.save(self.chat_target)
            self.chat_target_in.value = self.chat_target
            self._refresh_chat_status()
            self.log.write("chat target saved " + self.chat_target[:14])
            self.chat_check_status.text = S.CHAT_TARGET_SAVED
        except Exception as e:
            self._log_err("chat_save_target", e)
            self.chat_check_status.text = S.ERR_SIMPLE.format(error=e)

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
            self.chat_check_status.text = S.ERR_SIMPLE.format(error=e)
            return
        if not self.chat_target:
            self.chat_check_status.text = S.CHAT_NEED_TARGET_FIRST
            return
        if self._refreshing and time.monotonic() - self._refresh_started < 90:
            self.chat_check_status.text = S.MIND_ALREADY_SCANNING
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
                    self.chat_check_status.text = S.MIND_SCAN_RESULT.format(
                        new=new, total=total, name=name, block=self.chat_inbox.last_block)
                    self.log.write(f"chat refresh via {name}: {new} new, {total} total")
                    return
                except Exception as e:
                    last_err = e
            self._log_err("chat_refresh", last_err)
            self.chat_check_status.text = S.ERR_TYPED.format(type=type(last_err).__name__, error=last_err)
        finally:
            self._refreshing = False

    def _show_chat_messages(self):
        my = self.wallet.address if self.wallet else ""
        entries = self.chat_inbox.entries(my)

        def on_reply(rid):
            self.chat_code_in.value = rid
            self._focus_reply_form(self.chat_code_in, self.chat_msg_in, page_name="CHAT")
            self.chat_check_status.text = S.CHAT_REPLY_CODE_SET

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
                raise ValueError(S.CHAT_SAVE_TARGET_FIRST)
            text = (self.chat_msg_in.value or "").strip()
            if not text:
                raise ValueError(S.CHAT_NEED_MESSAGE)
            await self._sign_and_submit(
                text, intended_to=self.chat_target,
                reply_code=self.chat_code_in.value or "",
                inbox=self.chat_inbox, status_label=self.chat_send_status)
            self.chat_msg_in.value = ""
            self.chat_code_in.value = ""
            self._show_chat_messages()
        except Exception as e:
            self._log_err("chat_send", e)
            self.chat_send_status.text = S.ERR_SIMPLE.format(error=e)

    # ------------------------------------------------------------------ BOARD
    def board_select_ledger(self, widget, **kwargs):
        self.selected_board = LEDGER_BOARD
        self.board_detail_status.text = S.BOARD_READING_LEDGER.format(addr=LEDGER_BOARD[:12])
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
            label = S.BOARD_LABEL.format(prefix=label_prefix, addr=addr[:12], n=n)
            if is_sel:
                label = S.BOARD_LABEL_SELECTED_PREFIX + label

            def make_open(address=addr):
                def handler(widget, **kw):
                    self.selected_board = address
                    self.board_detail_status.text = S.BOARD_READING.format(address=address)
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
        add_btn(LEDGER_BOARD, n_ledger, label_prefix=S.BOARD_LABEL_LEDGER_PREFIX)
        for addr, n in ranked:
            if addr.lower() == LEDGER_BOARD.lower():
                continue
            add_btn(addr, n)

    async def board_refresh_list(self, widget=None, **kwargs):
        extras = list(self.settings.get("boards") or [])
        boards = [LEDGER_BOARD] + [b for b in extras if str(b).lower() != LEDGER_BOARD.lower()]
        self.board_list_status.text = S.BOARD_COUNTING
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
            self.board_list_status.text = S.BOARD_COUNT_RESULT.format(count=len(ranked))
        except Exception as e:
            self._log_err("board_list", e)
            self.board_list_status.text = S.ERR_TYPED.format(type=type(e).__name__, error=e)

    async def board_refresh_messages(self, widget=None, **kwargs):
        if not self.selected_board:
            self.board_detail_status.text = S.BOARD_SELECT_FROM_LIST
            return
        self.board_detail_status.text = S.BOARD_SCANNING.format(addr=self.selected_board[:12])
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
                    self.board_detail_status.text = S.BOARD_SCAN_RESULT.format(
                        addr=self.selected_board[:12], new=new, total=total, name=name)
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
                S.ERR_TYPED.format(type=type(last_err).__name__, error=last_err)
                if last_err else "Error"
            )
        except Exception as e:
            self._log_err("board_refresh", e)
            self.board_detail_status.text = S.ERR_SIMPLE.format(error=e)

    def _show_board_messages(self):
        my = self.wallet.address if self.wallet else ""
        entries = self.board_inbox.entries(my)

        def on_reply(rid):
            self.board_code_in.value = rid
            self._focus_reply_form(self.board_code_in, self.board_msg_in, page_name="BOARD")
            self.board_detail_status.text = S.BOARD_REPLY_CODE_SET

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
                raise ValueError(S.BOARD_SELECT_FIRST)
            text = (self.board_msg_in.value or "").strip()
            if not text:
                raise ValueError(S.BOARD_NEED_MESSAGE)
            await self._sign_and_submit(
                text, intended_to=self.selected_board,
                reply_code=self.board_code_in.value or "",
                inbox=self.board_inbox, status_label=self.board_send_status)
            self.board_msg_in.value = ""
            self.board_code_in.value = ""
            self._show_board_messages()
        except Exception as e:
            self._log_err("board_send", e)
            self.board_send_status.text = S.ERR_SIMPLE.format(error=e)


def main():
    return SOS69069MsgApp("sos69069 m3", "org.sos69069.m3")
