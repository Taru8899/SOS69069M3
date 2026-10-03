SOS69069 M3

Permanent · public · owned by no One.

SOS69069 M3 is an on-chain messaging app. There is no chat server, no account signup, and no central delete button — only signed records on Ethereum that anyone can read, ordered by time.

You use it to post short public messages (up to 64 characters of metadata) through the SOS 69069 contract, paid in gas by a relayer key you control (or the demo key while you try the app).

----------------------------------------------------------------------------

CONTRACT YOU INTERACT WITH

Every message is a signed record on this contract:

  SOS ledger (contract):  0x7373DBC24Dcd785896E8Ac3d5372c6ced9B75a8A
  Network:                Ethereum mainnet
  Explorer:               https://etherscan.io/address/0x7373DBC24Dcd785896E8Ac3d5372c6ced9B75a8A

That address is the built-in BOARD ledger. Extra boards are optional addresses you add in SETUP.

Source code: https://github.com/Taru8899/SOS69069M3

----------------------------------------------------------------------------

WHAT THE APP IS FOR

  Read a public message board
    -> BOARD tab: ledger (and any extra boards)

  Hold a chat around one address
    -> CHAT tab: set a target, refresh, reply with short codes

  Keep self-notes / a private stream to yourself
    -> MIND tab: messages you post to yourself; optional bind of one other address for this session only

  Pay gas without a backend
    -> SETUP: relayer private key signs the on-chain submit

Nothing important is stored on a server you do not control. Keys and settings stay on this device, and only if you turn on Save my data on device (or Remember on device) in SETUP.

----------------------------------------------------------------------------

THE FOUR TABS

Order in the app: BOARD · CHAT · MIND · SETUP

BOARD
  Public boards. The SOS ledger contract is always available. Add more board addresses in SETUP. Boards are listed by activity; tap one to select and load messages. Short-code replies are supported.

CHAT
  Messages to one target address (anyone can post to that target).
  Refresh saves the address in the field and scans. Replies can include a short code so threads stay followable. Target can be kept after restart when device save is enabled.

MIND
  Self-records only (you sign messages intended for yourself).
  Optional bind of another address for this session (cleared when the app closes).
  Refresh applies the pasted key, applies the bind, and scans in one step.

SETUP
  Wallet (paste or generate a private key), RPC, Etherscan API key, max gas fee, relayer key, extra board addresses, discovery codes, and Save my data on device.

----------------------------------------------------------------------------

SAVE MY DATA ON DEVICE

  - Off by default (safe demo defaults so you can try the app).
  - While off, demo keys may be shown; overrides you type are session-only.
  - Turn the switch on, then tap Save settings, to keep your own key, chat target, and relayer key on this phone.
  - Turn it off and Save settings again to stop persisting those overrides.

Board message caches are local read caches of chain data (capped per board), not a substitute for the ledger itself.

----------------------------------------------------------------------------

TRANSACTION LINKS

When a message is on-chain, the app shows a short tx… line. Tap it to open the transaction on Etherscan:

  https://etherscan.io/

----------------------------------------------------------------------------

HOW A MESSAGE WORKS (SIMPLE)

  1. You write text (up to 64 characters in the on-chain metadata field).
  2. Your wallet signs an EIP-712 record for the SOS 69069 contract.
  3. A relayer key submits the transaction and pays gas.
  4. Anyone can read that record from the chain (via Etherscan API / RPC in the app).

  Mode     Who the record is aimed at (intendedTo)
  -----    ---------------------------------------
  MIND     Yourself
  CHAT     Chat target address
  BOARD    Selected board address (ledger or extra)

----------------------------------------------------------------------------

SAFETY

  - Treat any private key you paste like cash: it can sign messages and spend gas.
  - Save my data on device writes secrets into this app's private storage. That is not shared with other apps, but it is not safe against physical access to an unlocked or compromised device.
  - Demo keys in the app are for exploration only — do not fund them with money you cannot lose.

----------------------------------------------------------------------------

TAGLINE

  SOS69069 M3 — owned by no One.
