"""
Every piece of text the app shows on screen, in one place. Pages (pages.py)
and the event handlers in app.py import names from here instead of writing
text inline — so wording changes are a one-line edit here, not a hunt
through the rest of the code.

Scope: this covers text the user reads (titles, labels, placeholders,
buttons, status/error messages). It does NOT cover:
  - the four tab names "MIND" / "CHAT" / "BOARD" / "SETUP" — these double as
    the dict keys the app switches on to show the right page, so moving
    them here would separate the display text from the logic that depends
    on it being exactly that string. They stay as literals in app.py/pages.py.
  - debug-log lines written via self.log.write(...) — those are developer
    diagnostics in debug.log, not something shown on a screen.
  - settings/storage dict keys ("rpc_url", "boards", ...) — internal data
    keys, not displayed text.

Dynamic messages are kept as Python str.format() templates (e.g.
MIND_SCAN_RESULT) and filled in where they're used.
"""

# ---------------------------------------------------------------- app identity
STARTUP_CRASH_TITLE = "Startup Crash"
STARTUP_CRASH_LABEL = "Startup crashed:"

# ---------------------------------------------------------------- shared / reused across pages
BTN_REFRESH = "Refresh"
BTN_SEND = "SEND"
BTN_PREV = "◀"
BTN_NEXT = "▶"
PLACEHOLDER_KEY = "My address private key"
PLACEHOLDER_SHORT_CODE = "Short code (optional reply)"
PLACEHOLDER_MESSAGE = "Message ≤{limit} chars"
PAGE_LABEL = "Page {page} / {pages}"
LIST_EMPTY = "No messages yet."
LIST_SEPARATOR = "────────────────────"
REPLY_BUTTON = "REPLY (start conv {rid})"
TX_RECEIVED = "TRUST Received 1 SOS · #{code}"
TX_PENDING = "⏳ NOT submitted yet"
TX_BLOCK_LINE = "· block {block} · {when}"

ERR_SIMPLE = "Error: {error}"
ERR_TYPED = "Error: {type}: {error}"

# ---------------------------------------------------------------- MIND page
MIND_TITLE = "MIND"
MIND_INTRO = "Self-records only. Optional bind is wiped when the app closes."
MIND_BIND_PLACEHOLDER = "Bind other address"
MIND_BOUND_OK = "Bound for this session only ✔"
MIND_BIND_CLEARED = "Bind cleared"
MIND_NEED_ADDRESS = "Paste an address to bind"
MIND_NEED_KEY = "Paste private key above or open SETUP"
MIND_ALREADY_SCANNING = "Already scanning…"
MIND_SCANNING = "Scanning…"
MIND_SCAN_RESULT = "{new} new · {total} total · via {name} · block {block}"
MIND_NEED_MESSAGE = "Type a message"

# ---------------------------------------------------------------- CHAT page
CHAT_TITLE = "CHAT"
CHAT_INTRO = "All messages intendedTo = target. Target is kept after restart."
CHAT_TARGET_PLACEHOLDER = "Chat target address (0x…)"
CHAT_REPLY_HEADER = "Reply / post to target"
CHAT_NEED_TARGET_ADDRESS = "Paste a target address"
CHAT_TARGET_SAVED = "Target saved (kept after restart) ✔"
CHAT_NEED_TARGET_FIRST = "Paste a target address first"
CHAT_SAVE_TARGET_FIRST = "Save a chat target first"
CHAT_REPLY_CODE_SET = "Reply code set — scroll to compose below ✔"
CHAT_NEED_MESSAGE = "Type a message"

# ---------------------------------------------------------------- BOARD page
BOARD_TITLE = "BOARD"
BOARD_SELECTED_HEADER = "Selected board messages"
BOARD_SELECT_FIRST = "Select a board first"
BOARD_SELECT_FROM_LIST = "Select a board from the list"
BOARD_READING_LEDGER = "Reading ledger {addr}…"
BOARD_READING = "Reading: {address}"
BOARD_SCANNING = "Scanning {addr}…"
BOARD_SCAN_RESULT = "Reading {addr}… · {new} new · {total} total · via {name}"
BOARD_COUNTING = "Counting messages…"
BOARD_COUNT_RESULT = "{count} boards"
BOARD_LABEL_LEDGER_PREFIX = "Ledger "
BOARD_LABEL = "{prefix}{addr}…  ({n} msgs)"
BOARD_LABEL_SELECTED_PREFIX = "● "
BOARD_REPLY_CODE_SET = "Reply code set — compose below ✔"
BOARD_NEED_MESSAGE = "Type a message"

# ---------------------------------------------------------------- SETUP page
SETUP_TITLE = "SETUP"
SETUP_TAGLINE = "{title} — {tagline}"
SETUP_BUILD_VERSION = "Build version {version}"
SETUP_README_LINK = "View README"
SETUP_ADDRESS_PLACEHOLDER = "Address"
BTN_APPLY = "Apply"
BTN_GENERATE = "Generate"
SETUP_NETWORK_HEADER = "Network"
SETUP_ETHERSCAN_LABEL = "Etherscan API key"
SETUP_RPC_LABEL = "RPC URL"
SETUP_MAXFEE_LABEL = "Max fee (gwei)"
SETUP_DISCOVERY_LABEL = "Discovery codes"
SETUP_DISCOVERY_PLACEHOLDER = "M3:1, M3:2"
SETUP_BOARDS_LABEL = "Board addresses"
SETUP_BOARDS_PLACEHOLDER = "Extra board addresses (one per line; ledger is separate)"
SETUP_RELAYER_HEADER = "Relayer / gas"
SETUP_RELAYER_PLACEHOLDER = "Relayer private key (64 hex) or leave default"
BTN_CHECK_BALANCE = "Check balance"
SETUP_REMEMBER_LABEL = "Remember on device"
BTN_SAVE_SETTINGS = "Save settings"

SETUP_KEY_APPLIED = "Key applied ✔"
SETUP_NEED_KEY = "Paste a 64-hex private key"
SETUP_NO_RELAYER_KEY = "No relayer key"
SETUP_NO_WALLET = "Generate a wallet in SETUP first"
SETUP_NO_ADDRESS_TO_COPY = "No address to copy"
SETUP_ADDRESS_COPIED = "Address copied ✔"
SETUP_COPY_FAILED = "Could not copy"
SETUP_WALLET_CREATED = "Wallet created ✔  Back it up offline if needed."
SETUP_CAP_MUST_BE_POSITIVE = "cap must be > 0"
SETUP_SAVED_KEPT = "Saved ✔  Data kept on device"
SETUP_SAVED_DEMO_ONLY = "Saved ✔  Demo defaults only"
SETUP_BALANCE_RESULT = "{eth:.6f} ETH\n{address}"
SETUP_SUBMITTING_WITH = "Submitting with {address}…"
SETUP_SENT = "Sent ✔\n{link}"
SETUP_SIGNED_SUBMITTING = "Signed #{code} — submitting…"
SETUP_SENT_WITH_CODE = "Sent ✔ #{code}\n{link}"
SETUP_SUBMIT_FAILED = "Signed #{code} but submit failed: {type}: {error}"
SETUP_LOCAL_SIG_CHECK_FAILED = "Local signature check failed"

# ---------------------------------------------------------------- README viewer
README_PAGE_TITLE = "README"
README_BACK_BUTTON = "Back"


# This is the plain-text twin of the README.md at the project root — same
# content, without markdown syntax, since it renders in a plain read-only
# text box rather than a markdown viewer. Reading the real repo-root file
# at runtime isn't reliable once the app is packaged (Android ships only
# what's bundled inside the app, not the repo tree), so this copy ships
# inside the app instead. Keep this in sync with README.md if you edit
# either one.
README_TEXT = """SOS69069 M3 — owned by no One

A small on-chain messaging app. Every message is a signed record posted
through a relayer, readable by anyone who knows where to look. Nothing is
stored on a server you don't control: your wallet key, your chat target,
and your settings live only on this device, and only if you turn on
Remember on device in SETUP.

THE FOUR TABS

MIND  — Self-records only. Messages you sign and post to yourself. An
        optional "bind" lets you view another address's self-records for
        this session; the bind is cleared whenever the app closes.
        Tapping Refresh applies the pasted key, applies the bind, and
        scans — all in one tap.

CHAT  — Direct messages to one target address. The target is saved and
        kept after you restart the app. Tapping Refresh saves whatever
        address is in the field and scans — no separate "Save target"
        step. Replies carry a short reply code so a conversation thread
        can be followed back.

BOARD — Public boards. The built-in ledger board is always available;
        add more board addresses in SETUP. Boards are ranked by how
        many messages they've received — tap a board to select and
        scan it. Short-code replies are allowed here too.

SETUP — Wallet (paste or generate a private key), network settings
        (RPC URL, Etherscan API key, max gas fee), the relayer that pays
        gas for your signed messages, extra board addresses, discovery
        codes, and the Remember on device switch.

REMEMBER ON DEVICE

Off by default. While off, the app runs on visible demo keys so you can
try everything without risking a real wallet. Turn it on and tap Save
settings to persist your own key, chat target, and relayer key to this
device instead.

TRANSACTION LINKS

Every signed message that reaches the chain shows a short "tx…" link.
Tapping it opens the transaction on Etherscan:
https://etherscan.io/

SOURCE

https://github.com/YOUR-USER/sos69069_msg
(update this link once the repository has a real home)

SAFETY NOTES

- Treat any private key you paste here the way you'd treat cash: anyone
  who has it can sign messages and spend gas as you.
- Remember on device writes your key to this device's private app
  storage. That protects it from other apps, but not from someone with
  physical access to an unlocked, rooted device.
"""
