# Teia Messaging Network Token

Three smart contracts for on-chain messaging on Tezos. Channels has a full reference inline below; Token Gated Chat has a brief summary; Poll Comments has a full reference further down.

## Contracts at a glance

### 1. Channels (`channels.py`)

Public or private community channels with three-tier access control.

- Anyone can create a channel
- Three access modes:
  - **Unrestricted**, anyone can post
  - **Allowlist**, only addresses with a valid Merkle proof against `merkle_root` (scales to thousands)
  - **Closed**, only creator and admins; intended for DMs and small private rooms
- Channel creator can add admins; admins can configure access, update metadata, and post freely
- Message deletion: in `closed` channels, sender only; in `unrestricted`/`allowlist` channels, sender or creator
- Only the creator can add/remove admins or hide the channel (soft delete)
- Message replies via `parent_id`

Full reference: see [Channels v1, full reference](#channels) below.

### 2. Token Gated Chat (`token_gate.py`)

Chat rooms for FA2 token holders.

- Every token gets a chat room automatically (no need to create one)
- Room key = FA2 contract address + token ID
- To post, the contract checks if you hold the token via FA2 `balance_of` callback
- Rooms are created on first message
- Only the message sender can delete their own messages (moderation via multisig, maybe every multisig wallet can hide/delete messages and ban wallets)
- Message replies via `parent_id`

### 3. Poll Comments (`poll_comments.py`)

Comments on off-chain teia.art polls, gated by Teia FA2 token ownership.

- Anyone holding the configured Teia token (one FA2 contract + token_id, set in storage) can comment
- Polls live off-chain (e.g. teia.art/poll/49); the contract only stores comments and references each poll by `poll_id`
- Token check runs through FA2 `balance_of` callback, same flow as Token Gated Chat
- Senders can **edit** their own comments and **hide** them; each action carries its own configurable fee (`post_fee`, `edit_fee`, `hide_fee`), any of which may be set to 0 via governance. Every edit archives the prior version into an on-chain history big_map (`comment_history`) so the full edit history of any comment is queryable forever via the `get_comment_version` view.
- Moderation: any single multisig user can hide or un-hide any comment directly (no vote required, no fee) — fast take-down path
- Multisig also maintains a contract-wide **ban list**; banned wallets can't `post_comment` or `edit_comment` on any poll. Banning still requires a passed multisig proposal (vote-gated)
- Replies via `parent_id`; replies to hidden parents are rejected

Full reference: see [Poll Comments, full reference](#poll-comments) below.

## Shared features

All three contracts share:

- **Message fees**, configurable fee per message (settable to 0 via governance)
- **Multisig governance**, pause contract, change fees, update metadata
- **Events**, all state-changing actions emit typed events for indexing
- **Reply support**, messages/comments can reference a parent

## Build & test

```bash
source smartpy-env/bin/activate
python python/contracts/messages/channels.py
python python/contracts/messages/token_gate.py
python python/contracts/messages/poll_comments.py
```

Compiled artifacts (Michelson + initial storage) land in the corresponding deploy folders next to the repo root. To force an output directory:

```bash
SMARTPY_OUTPUT_DIR=output/poll_comments python python/contracts/messages/poll_comments.py
```

## Deployments

| Contract | Network | Address |
|---|---|---|
| Poll Comments | Mainnet | `KT1HjHTTVa7hc9C2NGQh6H3m2gNKRDZPtg86` |
| Poll Comments | Shadownet | `KT1G7UK1hvM7yVbGoL6h8uKLmcYGNKGqas1j` |

---

# Channels

On-chain community channels with three-tier access control and optional Merkle-tree allowlists. Implemented in SmartPy at [`channels.py`](./channels.py).

## Access model

Three roles, per channel:

| Role | Set by | What they can do |
|---|---|---|
| **Creator** | whoever calls `create_channel` (immutable) | everything below + `update_channel_admins`, `hide_channel` |
| **Admin** | creator, via `update_channel_admins` | `configure_channel`, `update_channel`, `delete_message`, post freely |
| **User** (Merkle member) | proof against `merkle_root` set by creator/admin | post in allowlist channels |

Three access modes:

- `unrestricted`, anyone may post
- `allowlist`, only creator, admins, or addresses with a valid Merkle proof against `channel.merkle_root`
- `closed`, only creator and admins; no Merkle path. Intended for DMs and small private peer rooms

`hide_channel` the channel record stays but `post_message` and `configure_channel` reject it.

### Closed mode and DMs

`closed` direct messages: a 2-person DM is created with `access_mode=closed`, no `merkle_root`, and the peer added as the single admin. Two semantics distinguish it from the others:

- **Posting** is restricted to the privileged set (creator + admins). Non-privileged callers get `NOT_AUTHORIZED` with no Merkle path to override it.
- **Deletion** is sender-only: the creator cannot delete an admin/peer's message in a closed channel. In `unrestricted` and `allowlist` channels, the creator retains delete power over any message (sender-or-creator rule).

Switching modes is allowed in both directions. Switching out of `closed` (e.g., to `allowlist`) re-grants the creator delete power over any prior peer message, by design, but worth communicating to participants.

## Storage

```
multisig_address     : address                                # governance contract
metadata             : big_map[string, bytes]                 # TZIP-16
paused               : bool                                   # global pause flag (governance-set)
channels             : big_map[nat, channel]                  # channel records
messages             : big_map[nat, message]                  # flat message store
channel_admins       : big_map[nat, set[address]]             # per-channel admin set (≤ 15 admins per channel)
channel_id_counter   : nat                                    # next channel_id (starts at 1)
message_id_counter   : nat                                    # next message_id (starts at 1)
message_fee          : mutez                                  # required tez on post_message
channel_fee          : mutez                                  # required tez on create_channel
fee_recipient        : address
proposals            : big_map[nat, proposal]                 # governance proposals
votes                : big_map[(nat, address), bool]          # governance votes
counter              : nat                                    # proposal counter
```

### `channel` record

```
creator        : address
metadata_uri   : bytes                  # e.g. IPFS
access_mode    : variant(unrestricted | allowlist | closed)
merkle_root    : option[bytes]          # required iff access_mode = allowlist
merkle_uri     : option[bytes]          # off-chain pointer to the full address list
message_count  : nat                    # incremented on post, decremented on delete
hidden         : bool
timestamp      : timestamp              # creation time
```

### `message` record

```
channel_id  : nat
sender      : address
content     : bytes                     # ≤ 32768 bytes (32 KiB)
parent_id   : option[nat]               # for threaded replies
timestamp   : timestamp
```

## Entrypoints

### Channel ops

#### `create_channel(metadata_uri, access_mode, merkle_root, merkle_uri, admins)`

| | |
|---|---|
| Caller | anyone |
| Tez | exactly `channel_fee` (or 0 if fee is 0) |
| Behavior | spawns a new channel with sender as creator, full config applied at creation, optional initial admin set written into `channel_admins` |
| Validation | `metadata_uri` non-empty; `access_mode = allowlist ⇔ merkle_root.is_some()` |
| Notes | `admins` is `list[address]`; pass `[]` for none |
| Event | `channel_created { channel_id, creator, metadata_uri, access_mode, merkle_root, merkle_uri, admins, timestamp }` |

#### `configure_channel(channel_id, access_mode, merkle_root, merkle_uri)`

| | |
|---|---|
| Caller | creator or admin |
| Tez | 0 |
| Behavior | updates the access mode, Merkle root and Merkle URI |
| Restrictions | rejects if channel is hidden |
| Event | `channel_configured { channel_id, access_mode, merkle_root, merkle_uri, configured_by }` |

#### `update_channel(channel_id, metadata_uri)`

| | |
|---|---|
| Caller | creator or admin |
| Tez | 0 |
| Behavior | replaces the channel `metadata_uri` |
| Validation | `metadata_uri` non-empty |
| Event | `channel_updated { channel_id, metadata_uri, updated_by }` |

#### `update_channel_admins(channel_id, to_add, to_remove)`

| | |
|---|---|
| Caller | creator only |
| Tez | 0 |
| Behavior | adds/removes addresses from the per-channel admin set |
| Event | `channel_admins_updated { channel_id, to_add, to_remove }` |

#### `hide_channel(channel_id)`

| | |
|---|---|
| Caller | creator only |
| Tez | 0 |
| Behavior | sets `hidden = true`; the channel becomes read-only |
| Event | `channel_hidden { channel_id, hidden_by }` |

### Message ops

#### `post_message(channel_id, content, proof, parent_id)`

| | |
|---|---|
| Caller | creator, admin, or any address (subject to `access_mode`) |
| Tez | exactly `message_fee` |
| Behavior | appends a message; if `parent_id` is set it must point to a message in the same channel |
| Access | unrestricted: anyone. allowlist: creator/admin bypass; everyone else must supply a valid `proof` against `channel.merkle_root`. closed: creator/admin only, all others rejected with `NOT_AUTHORIZED` |
| Validation | `1 ≤ len(content) ≤ 32768`; channel exists and is not hidden |
| Event | `message_posted { channel_id, message_id, sender, parent_id, timestamp }` (content is intentionally not emitted, read it from the `messages` big_map so `delete_message` actually deletes) |

#### `delete_message(message_id)`

| | |
|---|---|
| Caller | depends on the channel's `access_mode`: closed → message sender only; unrestricted/allowlist → message sender or channel creator |
| Tez | 0 |
| Behavior | deletes the message and decrements `channel.message_count` |
| Event | `message_deleted { channel_id, message_id, deleted_by }` |

### Governance (multisig users only)

The contract delegates user-management and quorum to the multisig at `multisig_address` via three views: `is_user`, `get_minimum_votes`, `get_expiration_time`.

#### `submit_proposal(action)`

`action` is a variant:

| Tag | Payload | Effect on execute |
|---|---|---|
| `set_pause` | `bool` | sets global `paused` |
| `set_message_fee` | `mutez` | updates `message_fee` |
| `set_channel_fee` | `mutez` | updates `channel_fee` |
| `set_fee_recipient` | `address` | updates `fee_recipient` |
| `update_multisig_address` | `address` | swaps the multisig governance contract |
| `update_metadata` | `{key: string, value: bytes}` | writes to TZIP-16 metadata big_map |

#### `vote_proposal(proposal_id, approval)`

Multisig users vote yes/no. Re-voting overwrites the previous vote (the prior tally is decremented before applying the new one).

#### `execute_proposal(proposal_id)`

Any multisig user. Requires `positive_votes ≥ get_minimum_votes()` from the multisig and the proposal not to be expired.

## Views (on-chain)

| View | Returns |
|---|---|
| `get_channel(channel_id: nat)` | `channel` record |
| `get_message(message_id: nat)` | `message` record |
| `get_message_fee()` | `mutez` |
| `get_channel_fee()` | `mutez` |
| `is_channel_admin({channel_id, address})` | `bool` (true for creator or admin) |
| `get_proposal(proposal_id: nat)` | `proposal` record |
| `get_vote((proposal_id, voter))` | `bool` (default false) |

## Building a Merkle proof (allowlist channels)

The on-chain leaf format is **`blake2b(pack(address))`**, keyed only on the address (no per-channel salt, no namespace).

Off-chain steps:

1. Collect the list of allowed addresses, deduplicate, and sort (any deterministic order works as long as the tree is rebuilt the same way every time).
2. Compute each leaf as `blake2b(pack(address))`. SmartPy's `pack` for an address produces the standard Michelson `0x05...` encoding, most Tezos client libraries expose this as `packAddress` or similar.
3. Build a binary Merkle tree using `blake2b(left || right)` for internal nodes. Pair from the bottom up; if a level has an odd count, duplicate the last node (or use whichever convention you prefer, just be consistent).
4. The **root** is the last remaining hash; store it on-chain via `merkle_root`. Publish the address list at `merkle_uri` (typically IPFS).
5. To prove inclusion of an address, walk from its leaf to the root and emit one `merkle_step` per level:
   - `direction = 0` if the **sibling** is on the **left** (so on-chain we compute `blake2b(sibling || computed)`)
   - `direction = 1` if the **sibling** is on the **right** (`blake2b(computed || sibling)`)
6. Submit `proof = [merkle_step, ...]` along with `post_message`.

Smallest case: a single-address tree has `merkle_root = blake2b(pack(address))` and the proof is `Some([])`, empty list.


## Error codes

See the module docstring at the top of [`channels.py`](./channels.py) for the full list, grouped by area:

- channel/message ops (`CONTRACT_PAUSED`, `INCORRECT_FEE`, `CHANNEL_NOT_FOUND`, `CHANNEL_HIDDEN`, `EMPTY_CONTENT`, `CONTENT_TOO_LARGE`, `PARENT_NOT_FOUND`, `PARENT_WRONG_CHANNEL`, `MESSAGE_NOT_FOUND`, `UNDERFLOW`, `EMPTY_METADATA`, `TEZ_TRANSFER`)
- authorization (`NOT_AUTHORIZED`, `NOT_CHANNEL_CREATOR`, `NOT_CHANNEL_ADMIN`)
- access config (`ALLOWLIST_NEEDS_ROOT`, `ROOT_NOT_ALLOWED`, `NO_MERKLE_ROOT`, `PROOF_REQUIRED`, `INVALID_MERKLE_PROOF`)
- governance (`CHANNELS_VIEW_FAILED`, `CHANNELS_NOT_MULTISIG_USER`, `CHANNELS_GET_MIN_VOTES_FAILED`, `CHANNELS_GET_EXPIRATION_FAILED`, `CHANNELS_PROPOSAL_EXPIRED`, `CHANNELS_NO_PROPOSAL`, `CHANNELS_ALREADY_EXECUTED`, `CHANNELS_NOT_ENOUGH_VOTES`)

## Indexer notes

Every state mutation emits a typed event, so events can be decoded directly from contract type info. The full set of event tags:

`channel_created`, `channel_configured`, `channel_updated`, `channel_admins_updated`, `channel_hidden`, `message_posted`, `message_deleted`.

`update_channel_admins` and `delete_message` are the only mutations that don't include the resulting state, for the admin set you must replay all `channel_admins_updated` events; for a deleted message, `messages[id]` will be absent in storage.

---

# Poll Comments

On-chain comments on off-chain teia.art polls, gated by ownership of the Teia FA2 token. Multisig governs moderation and parameter changes. Implemented in SmartPy at [`poll_comments.py`](./poll_comments.py).

## Model

- **Polls** are not stored on chain. The contract just records a `poll_id: nat` on each comment and trusts the off-chain poll system (teia.art) for the rest.
- **Token gating** happens through the FA2 `balance_of` callback: when someone calls `post_comment`, the contract stores a `pending_comment`, asks the configured FA2 for the sender's balance of the configured `token_id`, and only writes the comment once the callback confirms balance > 0.
- **Moderation** is one-flag (`hidden: bool`) on each comment. Three paths flip it: (a) the comment's sender via `set_own_comment_hidden`; (b) any multisig user via `moderate_comment_hidden` — no vote, just `is_user` check; (c) historically via proposal, but the `set_comment_hidden` action has been removed in favor of (b) for faster moderation. Hide is reversible from any of these paths. Nothing is ever hard-deleted.
- **Editing** is allowed for the sender only. Each edit archives the *current* version into the `comment_history` big_map at key `(comment_id, version)` before overwriting `content` in place; the live `version` counter is then incremented and `timestamp` is reset to `sp.now`. The full prior version (poll_id, sender, content, parent_id, timestamp) is preserved on chain forever and queryable via the `get_comment_version` view.
- **Ban list** is contract-wide (not per-poll). Multisig governance adds or removes addresses via the `set_user_banned` proposal action. A banned address is blocked from `post_comment` and `edit_comment` on every poll; it can still toggle `set_own_comment_hidden` on its existing comments.

## Storage

```
multisig_address     : address                                # governance contract
metadata             : big_map[string, bytes]                 # TZIP-16
paused               : bool                                   # global pause flag (governance-set)
fa2_address          : address                                # Teia token FA2 (governance-set)
token_id             : nat                                    # Teia token id (governance-set)
comments             : big_map[nat, comment]                  # flat comment store
comment_history      : big_map[(nat, nat), history_entry]     # archived prior versions, keyed by (comment_id, version)
banned               : big_map[address, unit]                 # contract-wide ban list (governance-set); presence = banned
pending_comment      : option[pending_comment]                # populated during a balance_of round-trip
comment_id_counter   : nat                                    # next comment_id (starts at 1)
post_fee             : mutez                                  # required tez on post_comment (may be 0)
edit_fee             : mutez                                  # required tez on edit_comment (may be 0)
hide_fee             : mutez                                  # required tez on set_own_comment_hidden (may be 0)
fee_recipient        : address
proposals            : big_map[nat, proposal]                 # governance proposals
votes                : big_map[(nat, address), bool]          # governance votes
counter              : nat                                    # proposal counter
```

### `comment` record

```
poll_id     : nat                       # off-chain reference (e.g. teia.art/poll/49 → 49)
sender      : address
content     : bytes                     # ≤ 32768 bytes (32 KiB)
parent_id   : option[nat]               # for threaded replies
hidden      : bool                      # set by sender or multisig
timestamp   : timestamp                 # when the *current* version became live (= post time at v1, reset to sp.now on each edit). Original post time is recoverable from `comment_history[(c, 1)].timestamp` once the comment has been edited at least once.
version     : nat                       # current version index — starts at 1 on post, +1 per edit. Archived versions live at `comment_history[(comment_id, 1..version-1)]` (empty for never-edited comments at version=1).
```

### `history_entry` record

```
poll_id     : nat                       # always the same as the live comment's poll_id (comments can't be moved between polls)
sender      : address                   # always the original sender (only the sender can edit)
content     : bytes                     # the content as it was at this version
parent_id   : option[nat]               # always the same as the live comment's parent_id (reparenting not supported)
timestamp   : timestamp                 # the moment this version became live (i.e. when it was posted or when the preceding edit happened)
```

## Entrypoints

### Comment ops

#### `post_comment(poll_id, content, parent_id)`

| | |
|---|---|
| Caller | anyone holding the configured Teia token at the configured `token_id`, not on the ban list |
| Tez | exactly `post_fee` |
| Behavior | stores `pending_comment` and calls FA2 `balance_of`; the comment is only written once `balance_callback` confirms a non-zero balance |
| Validation | `1 ≤ len(content) ≤ 32768`; no other `pending_comment` in flight; if `parent_id` set, parent must exist, be on the same poll, and not be hidden |
| Event | `comment_posted { poll_id, comment_id, sender, parent_id, timestamp }` (emitted from `balance_callback`; content is intentionally not in the event so that edit/hide are meaningful) |

#### `balance_callback(responses)`

Internal-facing — must be called by the configured FA2 contract as the response to `balance_of`. Writes the pending comment if a matching response shows balance > 0, sends the fee to `fee_recipient`, emits `comment_posted`, and clears `pending_comment`. Manual calls fail with `INVALID_CALLBACK_SENDER`.

#### `edit_comment(comment_id, content)`

| | |
|---|---|
| Caller | original sender only, not on the ban list |
| Tez | exactly `edit_fee` (may be 0) |
| Behavior | snapshots the current version (poll_id, sender, content, parent_id, timestamp) into `comment_history[(comment_id, version)]`, increments the live `version`, overwrites `content`, sets `timestamp = sp.now`. `parent_id` and `hidden` are unchanged. Forwards the fee to `fee_recipient`. |
| Validation | `1 ≤ len(content) ≤ 32768` |
| Event | `comment_edited { poll_id, comment_id, sender, parent_id, timestamp, version }` — `timestamp` is `sp.now` (the new live-since for this version); `version` is the new live version index; the just-archived snapshot is at `comment_history[(comment_id, version - 1)]` |
| Storage burn | each edit allocates a new big_map entry sized by the *prior* content (~250 mutez/byte). For a small text comment that's a few hundred mutez; for a 32 KiB max comment it's ~8 tez. Storage burn is paid directly by the editor on top of `edit_fee`. |

#### `set_own_comment_hidden(comment_id, hidden)`

| | |
|---|---|
| Caller | original sender only |
| Tez | exactly `hide_fee` (may be 0) |
| Behavior | flips the `hidden` flag on caller's own comment; forwards the fee to `fee_recipient` |
| Event | `comment_hidden_set { comment_id, hidden, updated_by }` |

#### `moderate_comment_hidden(comment_id, hidden)`

| | |
|---|---|
| Caller | any multisig user (checked via the multisig's `is_user` view); no vote required |
| Tez | 0 |
| Behavior | flips the `hidden` flag on any comment for fast moderation |
| Validation | comment exists |
| Event | `comment_moderated { comment_id, hidden, moderator }` |

### Governance (multisig users only)

The contract delegates user-management and quorum to the multisig at `multisig_address` via three views: `is_user`, `get_minimum_votes`, `get_expiration_time`.

#### `submit_proposal(action)`

`action` is a variant:

| Tag | Payload | Effect on execute |
|---|---|---|
| `set_pause` | `bool` | sets global `paused` |
| `set_post_fee` | `mutez` | updates `post_fee` |
| `set_edit_fee` | `mutez` | updates `edit_fee` |
| `set_hide_fee` | `mutez` | updates `hide_fee` |
| `set_fee_recipient` | `address` | updates `fee_recipient` |
| `update_multisig_address` | `address` | swaps the multisig governance contract |
| `update_metadata` | `{key: string, value: bytes}` | writes to TZIP-16 metadata big_map |
| `update_token_gate` | `{fa2_address: address, token_id: nat}` | swaps the FA2 contract + token id used for gating |
| `set_user_banned` | `{address: address, banned: bool}` | adds or removes an address from the contract-wide ban list (banned addresses can't `post_comment` or `edit_comment`) |

Note: hiding individual comments is **not** a proposal action — see `moderate_comment_hidden` above for the direct multisig-user path.

#### `vote_proposal(proposal_id, approval)`

Multisig users vote yes/no. Re-voting overwrites the previous vote (the prior tally is decremented before applying the new one).

#### `execute_proposal(proposal_id)`

Any multisig user. Requires `positive_votes ≥ get_minimum_votes()` from the multisig and the proposal not to be expired.

## Views (on-chain)

| View | Returns |
|---|---|
| `get_comment(comment_id: nat)` | `comment` record (live version) |
| `get_comment_version((comment_id, version): (nat, nat))` | `history_entry` record (an archived prior version). Errors with `VERSION_NOT_FOUND` if the slot is empty. |
| `get_comment_version_count(comment_id: nat)` | `nat` — total version count (= the live `version` field). Versions start at 1, so this returns 1 for a never-edited comment and `1 + number_of_edits` otherwise. Archived snapshots live at indices `1..count-1`; the live version (index = `count`) lives in `comments[comment_id]`. |
| `get_fees()` | `{post_fee: mutez, edit_fee: mutez, hide_fee: mutez}` |
| `get_token_gate()` | `{fa2_address: address, token_id: nat}` |
| `get_proposal(proposal_id: nat)` | `proposal` record |
| `get_vote((proposal_id, voter))` | `bool` (default false) |
| `is_banned(address: address)` | `bool` (true if the address is on the ban list) |

## Error codes

See the module docstring at the top of [`poll_comments.py`](./poll_comments.py) for the full list, grouped by area:

- comment ops (`CONTRACT_PAUSED`, `TEZ_TRANSFER`, `INCORRECT_FEE`, `EMPTY_CONTENT`, `CONTENT_TOO_LARGE`, `PARENT_NOT_FOUND`, `PARENT_WRONG_POLL`, `PARENT_HIDDEN`, `COMMENT_NOT_FOUND`, `NOT_AUTHORIZED`, `USER_BANNED`, `VERSION_NOT_FOUND`)
- token gate / FA2 (`PENDING_POST_EXISTS`, `NO_PENDING_POST`, `INVALID_CALLBACK_SENDER`, `EMPTY_BALANCE_RESPONSE`, `NOT_TOKEN_HOLDER`, `SELF_CALLBACK_ERROR`, `INVALID_FA2`)
- governance (`POLL_VIEW_FAILED`, `POLL_NOT_MULTISIG_USER`, `POLL_GET_MIN_VOTES_FAILED`, `POLL_GET_EXPIRATION_FAILED`, `POLL_PROPOSAL_EXPIRED`, `POLL_NO_PROPOSAL`, `POLL_ALREADY_EXECUTED`, `POLL_NOT_ENOUGH_VOTES`)

## Indexer notes

Event tags emitted by the contract:

Comment lifecycle:
- `comment_posted { poll_id, comment_id, sender, parent_id, timestamp }` — emitted from `balance_callback` after a successful post. New posts start at `version = 1`.
- `comment_edited { poll_id, comment_id, sender, parent_id, timestamp, version }` — emitted after a successful edit. `timestamp` is the moment the new version became live (i.e. `sp.now` at edit time, matching the new value of `comments[comment_id].timestamp`). `version` is the new live version index; the previous version is now archived at `comment_history[(comment_id, version - 1)]`. Content lives in the `comments` / `comment_history` big_maps, not the event.
- `comment_hidden_set { comment_id, hidden, updated_by }` — emitted by `set_own_comment_hidden`; `updated_by` is the comment's sender
- `comment_moderated { comment_id, hidden, moderator }` — emitted by `moderate_comment_hidden`; `moderator` is the multisig user who flipped the flag

Governance state changes emitted from `execute_proposal`:
- `pause_set { proposal_id, paused, updated_by }`
- `post_fee_set { proposal_id, post_fee, updated_by }`
- `edit_fee_set { proposal_id, edit_fee, updated_by }`
- `hide_fee_set { proposal_id, hide_fee, updated_by }`
- `fee_recipient_set { proposal_id, fee_recipient, updated_by }`
- `multisig_address_set { proposal_id, multisig_address, updated_by }`
- `metadata_updated { proposal_id, key, updated_by }` — value lives in the `metadata` big_map
- `token_gate_updated { proposal_id, fa2_address, token_id, updated_by }`
- `user_banned_set { proposal_id, address, banned, updated_by }`

`submit_proposal` and `vote_proposal` deliberately don't emit events — the `proposals` and `votes` big_maps are queryable via views and re-readable on every block. Subscribe to the per-action events above to react to executed proposals.

Because `edit_comment` overwrites content in place and `comment_edited` carries no content, indexers must re-read the live comment from the `comments` big_map on edit events. The just-archived prior version is available at `comment_history[(comment_id, version - 1)]` where `version` is the new live version index emitted on the event. The full chain of versions can be reconstructed by walking indices `1..version-1` in `comment_history` plus the live `comments[comment_id]` entry. Versions start at 1.

## Deployment

The file ships with two scenarios, `poll_comments_deploy_shadownet` and `poll_comments_deploy_mainnet`. They differ only in the multisig/fee_recipient and Teia FA2 addresses.

| Network | Multisig & fee_recipient | Teia FA2 | token_id | post_fee | edit_fee | hide_fee |
|---|---|---|---|---|---|---|
| Shadownet | `KT1KeGd4YtjcKqgyiXUPJQkm2iYA3fQwLGQP` | `KT1RHCCYWKDwMzmTZq7kG7H3brHAno3yfMQD` | `0` | `25000` mutez | `25000` mutez | `25000` mutez |
| Mainnet | `KT1J9FYz29RBQi1oGLw8uXyACrzXzV1dHuvb` | `KT1QrtA753MSv8VGxkDrKKyJniG5JtuHHbtV` | `0` | `25000` mutez | `25000` mutez | `25000` mutez |

To originate on Shadownet (assumes the compiled artifacts are in `output/poll_comments/poll_comments_deploy_shadownet/`):

```bash
STORAGE=$(cat output/poll_comments/poll_comments_deploy_shadownet/step_002_cont_0_storage.tz)
octez-client --endpoint https://rpc.shadownet.teztnets.com \
  originate contract poll_comments_v1 \
  transferring 0 from WALLET \
  running output/poll_comments/poll_comments_deploy_shadownet/step_002_cont_0_contract.tz \
  --init "$STORAGE" --burn-cap 10
```

Current Mainnet deployment: `KT1HjHTTVa7hc9C2NGQh6H3m2gNKRDZPtg86` (alias `poll_comments_mainnet_v1`). Metadata pinned at `ipfs://QmXfrEZmN6spvdoqrHvF6ZfhTrL8zfCSJ5nhc2drrn6Rm8`.

Current Shadownet deployment: `KT1G7UK1hvM7yVbGoL6h8uKLmcYGNKGqas1j` (alias `poll_comments_v3`; adds the direct-multisig-user moderation path via `moderate_comment_hidden`). Earlier shadownet deployments retained for reference: `KT1THhsqsBxRwy7LhrzNEuqYv1s171g3CcjJ` (v2, multisig-vote-only moderation), `KT1Fj15RVREYq8mvLgVpvoYM79cA2or9sPMp` (v1, pre-ban-list).
