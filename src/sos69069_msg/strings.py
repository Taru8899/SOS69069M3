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

The README is stored as README_BLOCKS — a list of (kind, text) tuples —
rather than one big string, so pages.py can render it as styled widgets
(headings, bullets, dividers) instead of dumping plain Markdown into a
text box. Keep this list in sync with README.md at the repo root.
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
BOARD_LABEL = "{prefix}{addr}… ({n} msgs)"
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
SETUP_WALLET_CREATED = "Wallet created ✔ Back it up offline if needed."
SETUP_CAP_MUST_BE_POSITIVE = "cap must be > 0"
SETUP_SAVED_KEPT = "Saved ✔ Data kept on device"
SETUP_SAVED_DEMO_ONLY = "Saved ✔ Demo defaults only"
SETUP_BALANCE_RESULT = "{eth:.6f} ETH\n{address}"
SETUP_SUBMITTING_WITH = "Submitting with {address}…"
SETUP_SENT = "Sent ✔\n{link}"
SETUP_SIGNED_SUBMITTING = "Signed #{code} — submitting…"
SETUP_SENT_WITH_CODE = "Sent ✔ #{code}\n{link}"
SETUP_SUBMIT_FAILED = "Signed #{code} but submit failed: {type}: {error}"
SETUP_LOCAL_SIG_CHECK_FAILED = "Local signature check failed"

# ---------------------------------------------------------------- README page
README_PAGE_TITLE = "README"
README_BACK_BUTTON = "Back"

# Structured README content, rendered as styled widgets by pages.py.
# Each item is (kind, text). kind is one of:
#   "h1"     — page title
#   "h2"     — section heading
#   "h3"     — sub-heading (used inside "The four tabs")
#   "p"      — paragraph
#   "bullet" — bulleted line (a "•  " is prepended at render time)
#   "quote"  — emphasised closing line
#   "code"   — monospace-ish muted line
#   "hr"     — horizontal divider (text ignored)
#
# This is the in-app twin of README.md at the project root. Reading the
# real repo-root file at runtime isn't reliable once the app is packaged
# (Android ships only what's bundled inside the app, not the repo tree),
# so this copy ships inside the app instead. Keep this in sync with
# README.md if you edit either one.
README_BLOCKS = [
    ("h1", "SOS69069 M3"),
    ("p",  "Permanent · public · owned by no One."),
    ("p",  "SOS69069 M3 is an on-chain messaging app. There is no chat server, "
           "no account signup, and no central delete button — only signed records "
           "on Ethereum that anyone can read, ordered by time."),
    ("p",  "You use it to post short public messages (up to 64 characters of "
           "metadata) through the SOS 69069 contract, paid in gas by a relayer "
           "key you control (or the demo key while you try the app)."),

    ("hr", ""),
    ("h2", "Contract you interact with"),
    ("p",  "SOS ledger (contract):  0x7373DBC24Dcd785896E8Ac3d5372c6ced9B75a8A"),
    ("p",  "Network:  Ethereum mainnet"),
    ("p",  "Explorer:  etherscan.io/address/0x7373DBC24Dcd785896E8Ac3d5372c6ced9B75a8A"),
    ("p",  "That address is the built-in BOARD ledger. Extra boards are optional "
           "addresses you add in SETUP."),
    ("p",  "Source:  github.com/Taru8899/SOS69069M3"),

    ("hr", ""),
    ("h2", "What the app is for"),
    ("bullet", "Read a public message board — BOARD tab → ledger (and extra boards)"),
    ("bullet", "Hold a chat around one address — CHAT tab → set a target, refresh, reply"),
    ("bullet", "Keep self-notes / a private stream to yourself — MIND tab"),
    ("bullet", "Pay gas without a backend — SETUP → relayer private key signs the submit"),

    ("hr", ""),
    ("h2", "The four tabs"),
    ("p",  "Order in the app:  BOARD · CHAT · MIND · SETUP"),
    ("h3", "BOARD"),
    ("p",  "Public boards. The SOS ledger contract is always available. Add more "
           "board addresses in SETUP. Boards are listed by activity; tap one to "
           "select and load messages. Short-code replies are supported."),
    ("h3", "CHAT"),
    ("p",  "Messages to one target address (anyone can post to that target). "
           "Refresh saves the address in the field and scans. Replies can include "
           "a short code so threads stay followable."),
    ("h3", "MIND"),
    ("p",  "Self-records only (you sign messages intended for yourself). Optional "
           "bind of another address for this session, cleared when the app closes."),
    ("h3", "SETUP"),
    ("p",  "Wallet, RPC, Etherscan API key, max gas fee, relayer key, extra board "
           "addresses, discovery codes, and Save my data on device."),

    ("hr", ""),
    ("h2", "Save my data on device"),
    ("bullet", "Off by default — safe demo defaults so you can try the app."),
    ("bullet", "While off, demo keys may be shown; overrides you type are session-only."),
    ("bullet", "Turn the switch on, then tap Save settings, to keep your key, chat "
               "target, and relayer key on this phone."),
    ("bullet", "Turn it off and Save settings again to stop persisting those overrides."),

    ("hr", ""),
    ("h2", "Transaction links"),
    ("p",  "When a message is on-chain, the app shows a short tx… line. Tap it to "
           "open the transaction on Etherscan:  etherscan.io"),

    ("hr", ""),
    ("h2", "How a message works"),
    ("bullet", "You write text (≤ 64 characters in the on-chain metadata field)."),
    ("bullet", "Your wallet signs an EIP-712 record for the SOS 69069 contract."),
    ("bullet", "A relayer key submits the transaction and pays gas."),
    ("bullet", "Anyone can read that record from the chain (via Etherscan API / RPC)."),
    ("p",  "intendedTo depends on the mode:  MIND → yourself · CHAT → chat target · "
           "BOARD → selected board address."),

    ("hr", ""),
    ("h2", "Safety"),
    ("bullet", "Treat any private key you paste like cash: it can sign and spend gas."),
    ("bullet", "Save my data on device writes secrets into this app's private storage. "
               "That is not shared with other apps, but not safe against physical access."),
    ("bullet", "Demo keys are for exploration only — do not fund them with money you "
               "cannot lose."),

    ("hr", ""),
    ("quote", "SOS69069 M3 — owned by no One."),
]
