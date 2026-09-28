# SOS69069 M3

**Permanent · public · owned by no one.**

SOS69069 M3 is a messaging layer with **no server**, **no deletion**, and **no central control** — only signed records on the ledger that anyone can read, sorted by time.

**Nav:** `MIND` · `CHAT` · `BOARD` · `SETUP`

---

## Tagline

> **SOS69069 M3 — owned by no one.**

---

## 1. Product (locked)

| Tab | Role |
|-----|------|
| **MIND** | Self-records for the connected wallet; optional bind of one other address; **time sort only**; bind **wiped when the app closes** |
| **CHAT** | Target address; all messages **to** that address; **short-code reply**; target **kept after restart** |
| **BOARD** | Many boards (SETUP + discovery); list sorted by message count; ENS allowed; **short-code reply** |
| **SETUP** | All settings (wallet, RPC, Etherscan, gas, board list, discovery codes) |

---

## 2. Files to change

| File | Action |
|------|--------|
| `app.py` | Major — new nav, three mode UIs, session rules |
| `message_engine.py` | Extend — `intended_to` argument (self / chat target / board) |
| `reader.py` | Extend — scan all posts to an address, board ranking, pagination |
| `conversation.py` | Split — Mind session bind vs durable chat target vs board list |
| `config.py` | App name, default discovery code (e.g. `M/list`) |
| `tests/*` | Match new APIs |

**Leave alone:** `abi.py`, `eip712.py`, `ethcrypto.py`, `etherscan.py`, `relayer.py`, `rpc.py`, `submission.py`, `tx.py`, `rlp.py`

---

## 3. Signing (`message_engine.py`)

Stop hard-coding self-only posts.

```python
def prepare_and_sign(key, plaintext, intended_to: str | None = None, reply_code: str = ""):
    # intended_to=None → self (MIND)
    # else → that address (CHAT / BOARD)
    target = intended_to or key.address
    signature = sign_record(key, target, payload_hash, metadata)
```

| Mode | `intended_to` |
|------|----------------|
| **MIND** | `None` → self |
| **CHAT** | chat target |
| **BOARD** | selected board |

Optional `#XXXX ` prefix only when `reply_code` is set (CHAT / BOARD).

---

## 4. Storage

| Store | Path | Survives restart? |
|-------|------|-------------------|
| Wallet key | `wallet.json` | Yes |
| Mind bind (other address) | memory only | **No — cleared on startup** |
| Chat target | `chat_target.json` | Yes |
| Board list | `settings.json` | Yes |
| Inbox caches | `inbox_mind.json`, `inbox_chat.json`, `inbox_board_<addr>.json` | Mind cache cleared with bind |

**On `startup()`:**

1. Load wallet, settings, chat target, board list  
2. Explicitly clear Mind bind + mind inbox  
3. Do **not** restore Other for MIND  

→ Closing the app wipes the Mind bind.

---

## 5. Reading the ledger (`reader.py`)

| Function | Use |
|----------|-----|
| `sync_mind` / pair-style scan | **MIND** — self-only per address, merge, time sort |
| `sync_to_address` | **CHAT / BOARD** — all logs with `intendedTo = target` (any signer) |
| Board counts / ranking | **BOARD** home list, sort by message count |
| Pagination | Max N locally; UI shows 10 per page |

- **CHAT / BOARD:** do **not** require `signer == intendedTo`  
- **MIND:** keep self-only filter  
- **Discovery:** scan metadata for codes like `M/list`; merge into known boards  
- **ENS:** resolve when possible; store `0x`, show name if available  

---

## 6. UI pages

### Nav

```text
MIND · CHAT · BOARD · SETUP
```

Compose on each mode page. Gas / submit live under **SETUP**.

### MIND

```text
Connected: 0xMy…
[ Other address ]  [ Bind ]  [ Clear bind ]
[ Refresh ]
Messages (paginated, time order)
[ message ]  [ SEND ]     ← no short-code field
```

- Refresh → scan My (+ optional Other) self-records  
- SEND → self-post → submit via relayer in SETUP  
- Clear / app start → wipe bind + mind inbox  

### CHAT

```text
Target: [ address ]   ← from chat_target.json
[ Save target ]  [ Refresh ]
Messages to target (everyone → target)
[ short code ] [ message ] [ SEND ]
```

- Refresh → all posts with `intendedTo = target`  
- SEND → directed post + optional reply code  
- Target file **persists after restart**  

### BOARD

**List (sorted by activity):**

```text
board1   120
board2    45
…
[ Refresh list ]
```

**One board:**

```text
Board: 0x… / name.eth
Messages…
[ short code ] [ message ] [ SEND ]
```

- List = SETUP boards ∪ discovered (`M/list`, …)  
- SEND → `intendedTo = selected board` + optional reply code  

### SETUP

- Wallet: generate / show address  
- RPC URL, Etherscan key, max gwei  
- Relayer: default or paste private key  
- Board addresses (multi-line; `0x` or ENS)  
- Discovery codes (e.g. `M/list`)  
- Save + Submit signed records  

No Mind bind on SETUP (bind only on MIND, session-only).

---

## 7. Old → new map

| Old | New |
|-----|-----|
| CHECK | **MIND / CHAT / BOARD** refresh + lists |
| SEND (self only) | Mode-specific SEND with correct `intendedTo` |
| RELAY | **SETUP** submit / gas |
| Durable pair.json | Chat target durable; Mind bind session-only |
| End conversation | MIND “Clear bind” + auto-clear on startup |

---

## 8. Implementation order

1. `message_engine` — add `intended_to` (default self)  
2. `reader` — `sync_to_address` + board counts; keep Mind self-scan  
3. Storage — chat target file; clear Mind bind on startup; boards in settings  
4. `app.py` — four tabs; MIND first  
5. CHAT page  
6. BOARD list + detail + discovery  
7. Network / relayer only in SETUP  
8. Tests for three `intendedTo` paths + persistence rules  

---

## 9. What stays the same

- SOS 69069 contract, EIP-712, ≤64-char metadata  
- Etherscan-first scans, RPC fallback  
- Gas via user-pasted or default relayer private key  
- Pagination / local cache caps  
- **No server required**  

---

## 10. Summary

Generalise `intendedTo` in signing and scanning; split the UI into **MIND** (session bind, self-streams), **CHAT** (persistent target, all posts to target + short codes), and **BOARD** (many addresses, ranked, short codes); put all settings in **SETUP**; wipe Mind bind on every app start.

**SOS69069 M3 — owned by no one.**
```