# Token Comments

On-chain comments on Teia FA2 tokens, gated by ownership of the specific token being commented on. Multisig governs moderation and parameter changes. Implemented in SmartPy at [`token_comments.py`](./token_comments.py).

## Model

- **Topic** of a comment is the pair `(fa2_address, token_id)`. There's no on-chain record of a "room" or "thread" — the topic is just two fields on each comment. Indexers can group by `(fa2_address, token_id)` from event data.
- **Token gating is dynamic, per call.** Each `post_comment` carries the `(fa2_address, token_id)` it targets. The contract asks *that* FA2 for the sender's balance via `balance_of`, and only writes the comment when the callback confirms balance > 0. No FA2 address is baked into storage; there's no `update_token_gate` proposal.
- **Replies** must match the parent's `(fa2_address, token_id)` — a comment on Teia token A can't be a reply to a comment on Teia token B. Hidden parents reject new replies.
- **Moderation** is one flag (`hidden: bool`) on each comment. Three paths flip it: (a) the comment's sender via `set_own_comment_hidden`; (b) any multisig user via `moderate_comment_hidden` — no vote, just `is_user` check; (c) the sender can always un-hide their own comment. Nothing is ever hard-deleted.
- **Editing** is allowed for the sender only. Each edit archives the *current* version into the `comment_history` big_map at key `(comment_id, version)` before overwriting `content` in place; the live `version` counter is then incremented and `timestamp` is reset to `sp.now`. The full prior version (`fa2_address`, `token_id`, `sender`, `content`, `parent_id`, `timestamp`) is preserved on chain forever and queryable via the `get_comment_version` view.
- **Ban list** is contract-wide (not per-token). Multisig governance adds or removes addresses via the `set_user_banned` proposal action. A banned address is blocked from `post_comment` and `edit_comment` on every token; it can still toggle `set_own_comment_hidden` on its existing comments.

## Storage

```
multisig_address     : address                                # governance contract
metadata             : big_map[string, bytes]                 # TZIP-16
paused               : bool                                   # global pause flag (governance-set)
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

There is **no** `fa2_address` or `token_id` in storage — the gate is per-call, set by the post_comment caller.

### `comment` record

```
fa2_address : address                   # the FA2 contract of the token being commented on
token_id    : nat                       # the token id within that FA2
sender      : address
content     : bytes                     # ≤ 32768 bytes (32 KiB)
parent_id   : option[nat]               # for threaded replies (must match this comment's (fa2_address, token_id))
hidden      : bool                      # set by sender or multisig
timestamp   : timestamp                 # when the *current* version became live (= post time at v1, reset to sp.now on each edit). Original post time is recoverable from `comment_history[(c, 1)].timestamp` once the comment has been edited at least once.
version     : nat                       # current version index — starts at 1 on post, +1 per edit. Archived versions live at `comment_history[(comment_id, 1..version-1)]` (empty for never-edited comments at version=1).
```

### `history_entry` record

```
fa2_address : address                   # always the same as the live comment's fa2_address (comments can't be moved between tokens)
token_id    : nat                       # always the same as the live comment's token_id
sender      : address                   # always the original sender (only the sender can edit)
content     : bytes                     # the content as it was at this version
parent_id   : option[nat]               # always the same as the live comment's parent_id (reparenting not supported)
timestamp   : timestamp                 # the moment this version became live (i.e. when it was posted or when the preceding edit happened)
```

## Entrypoints

### Comment ops

#### `post_comment(fa2_address, token_id, content, parent_id)`

| | |
|---|---|
| Caller | anyone holding `(fa2_address, token_id)` at post time, not on the ban list |
| Tez | exactly `post_fee` |
| Behavior | stores `pending_comment` and calls `balance_of` on the targeted FA2; the comment is only written once `balance_callback` confirms a non-zero balance |
| Validation | `1 ≤ len(content) ≤ 32768`; no other `pending_comment` in flight; if `parent_id` set, parent must exist, match this comment's `(fa2_address, token_id)`, and not be hidden |
| Event | `comment_posted { fa2_address, token_id, comment_id, sender, parent_id, timestamp }` (emitted from `balance_callback`; content is intentionally not in the event so that edit/hide are meaningful) |

#### `balance_callback(responses)`

Internal-facing — must be called by the FA2 contract that the pending `post_comment` targeted. Writes the pending comment if a matching response shows balance > 0, sends the fee to `fee_recipient`, emits `comment_posted`, and clears `pending_comment`. Manual calls fail with `INVALID_CALLBACK_SENDER`. The check is `sp.sender == pending.fa2_address` — not a fixed FA2 address — since the gate is dynamic.

#### `edit_comment(comment_id, content)`

| | |
|---|---|
| Caller | original sender only, not on the ban list |
| Tez | exactly `edit_fee` (may be 0) |
| Behavior | snapshots the current version (`fa2_address`, `token_id`, `sender`, `content`, `parent_id`, `timestamp`) into `comment_history[(comment_id, version)]`, increments the live `version`, overwrites `content`, sets `timestamp = sp.now`. `fa2_address`, `token_id`, `parent_id`, and `hidden` are unchanged. Forwards the fee to `fee_recipient`. |
| Validation | `1 ≤ len(content) ≤ 32768` |
| Event | `comment_edited { fa2_address, token_id, comment_id, sender, parent_id, timestamp, version }` — `timestamp` is `sp.now` (the new live-since for this version); `version` is the new live version index; the just-archived snapshot is at `comment_history[(comment_id, version - 1)]` |
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
| `set_user_banned` | `{address: address, banned: bool}` | adds or removes an address from the contract-wide ban list (banned addresses can't `post_comment` or `edit_comment`) |

Note: there is **no** `update_token_gate` action — the gate is per-call, not a contract-wide configuration. Hiding individual comments is also **not** a proposal action; see `moderate_comment_hidden` above for the direct multisig-user path.

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
| `get_proposal(proposal_id: nat)` | `proposal` record |
| `get_vote((proposal_id, voter))` | `bool` (default false) |
| `is_banned(address: address)` | `bool` (true if the address is on the ban list) |

There is **no** `get_token_gate()` view — every comment carries its own `(fa2_address, token_id)`, readable via `get_comment`.

## Error codes

See the module docstring at the top of [`token_comments.py`](./token_comments.py) for the full list, grouped by area:

- comment ops (`CONTRACT_PAUSED`, `TEZ_TRANSFER`, `INCORRECT_FEE`, `EMPTY_CONTENT`, `CONTENT_TOO_LARGE`, `PARENT_NOT_FOUND`, `PARENT_WRONG_TOKEN`, `PARENT_HIDDEN`, `COMMENT_NOT_FOUND`, `NOT_AUTHORIZED`, `USER_BANNED`, `VERSION_NOT_FOUND`)
- token gate / FA2 (`PENDING_POST_EXISTS`, `NO_PENDING_POST`, `INVALID_CALLBACK_SENDER`, `EMPTY_BALANCE_RESPONSE`, `NOT_TOKEN_HOLDER`, `SELF_CALLBACK_ERROR`, `INVALID_FA2`)
- governance (`TC_VIEW_FAILED`, `TC_NOT_MULTISIG_USER`, `TC_GET_MIN_VOTES_FAILED`, `TC_GET_EXPIRATION_FAILED`, `TC_PROPOSAL_EXPIRED`, `TC_NO_PROPOSAL`, `TC_ALREADY_EXECUTED`, `TC_NOT_ENOUGH_VOTES`)

`PARENT_WRONG_TOKEN` fires whenever the parent's `fa2_address` *or* `token_id` differs from the new comment's.

## Indexer notes

Event tags emitted by the contract:

Comment lifecycle:
- `comment_posted { fa2_address, token_id, comment_id, sender, parent_id, timestamp }` — emitted from `balance_callback` after a successful post. New posts start at `version = 1`. The `(fa2_address, token_id)` pair is the topic the comment belongs to.
- `comment_edited { fa2_address, token_id, comment_id, sender, parent_id, timestamp, version }` — emitted after a successful edit. `timestamp` is the moment the new version became live (i.e. `sp.now` at edit time, matching the new value of `comments[comment_id].timestamp`). `version` is the new live version index; the previous version is now archived at `comment_history[(comment_id, version - 1)]`. Content lives in the `comments` / `comment_history` big_maps, not the event.
- `comment_hidden_set { comment_id, hidden, updated_by }` — emitted by `set_own_comment_hidden`; `updated_by` is the comment's sender
- `comment_moderated { comment_id, hidden, moderator }` — emitted by `moderate_comment_hidden`; `moderator` is the multisig user who flipped the flag

Note: the hide/moderate events deliberately don't echo `(fa2_address, token_id)` since that's stable for the lifetime of the comment — re-read `comments[comment_id]` to recover it.

Governance state changes emitted from `execute_proposal`:
- `pause_set { proposal_id, paused, updated_by }`
- `post_fee_set { proposal_id, post_fee, updated_by }`
- `edit_fee_set { proposal_id, edit_fee, updated_by }`
- `hide_fee_set { proposal_id, hide_fee, updated_by }`
- `fee_recipient_set { proposal_id, fee_recipient, updated_by }`
- `multisig_address_set { proposal_id, multisig_address, updated_by }`
- `metadata_updated { proposal_id, key, updated_by }` — value lives in the `metadata` big_map
- `user_banned_set { proposal_id, address, banned, updated_by }`

There is **no** `token_gate_updated` event — there's no contract-wide token gate to update.

`submit_proposal` and `vote_proposal` deliberately don't emit events — the `proposals` and `votes` big_maps are queryable via views and re-readable on every block. Subscribe to the per-action events above to react to executed proposals.

Because `edit_comment` overwrites content in place and `comment_edited` carries no content, indexers must re-read the live comment from the `comments` big_map on edit events. The just-archived prior version is available at `comment_history[(comment_id, version - 1)]` where `version` is the new live version index emitted on the event. The full chain of versions can be reconstructed by walking indices `1..version-1` in `comment_history` plus the live `comments[comment_id]` entry. Versions start at 1.

To list all comments on a specific Teia token, index on `(fa2_address, token_id)` from `comment_posted` events (or scan the `comments` big_map). The pair is also a natural grouping key for reply threads.

## Deployment

The file ships with two scenarios, `token_comments_deploy_shadownet` and `token_comments_deploy_mainnet`. They differ only in the multisig/fee_recipient address. There is no Teia FA2 address in storage — the gate is per-call.

| Network | Multisig & fee_recipient | post_fee | edit_fee | hide_fee | metadata |
|---|---|---|---|---|---|
| Shadownet | `KT1KeGd4YtjcKqgyiXUPJQkm2iYA3fQwLGQP` | `25000` mutez | `0` | `0` | `ipfs://QmeNKK9t4xdeNo8NCyJtmmdEZ2p2CFzgnLyMmtoWzaCUWf` |
| Mainnet | `KT1J9FYz29RBQi1oGLw8uXyACrzXzV1dHuvb` | `25000` mutez | `0` | `0` | `ipfs://QmeNKK9t4xdeNo8NCyJtmmdEZ2p2CFzgnLyMmtoWzaCUWf` |

To compile:

```bash
SMARTPY_OUTPUT_DIR=output/token_comments python python/contracts/messages/token_comments.py
```

To originate on Shadownet (assumes the compiled artifacts are in `output/token_comments/token_comments_deploy_shadownet/`):

```bash
STORAGE=$(cat output/token_comments/token_comments_deploy_shadownet/step_002_cont_0_storage.tz)
octez-client --endpoint https://rpc.shadownet.teztnets.com \
  originate contract token_comments_v1 \
  transferring 0 from WALLET \
  running output/token_comments/token_comments_deploy_shadownet/step_002_cont_0_contract.tz \
  --init "$STORAGE" --burn-cap 5
```

Same shape on mainnet, swap the endpoint to `https://mainnet.api.tez.ie` and point at the `token_comments_deploy_mainnet` artifacts.

| Network | Address | Alias | Notes |
|---|---|---|---|
| Mainnet | `KT1FXFxUcZvne1ApoSaeZfvmDR73u2BsuFUP` | `token_comments_mainnet_v1` | post=25000 / edit=0 / hide=0, metadata pinned at `ipfs://QmeNKK9t4xdeNo8NCyJtmmdEZ2p2CFzgnLyMmtoWzaCUWf` |
| Shadownet | `KT1BGBMUQK6rvLvbrrPEMdeLGAWr2ymSmw73` | `token_comments_v1` | same config; originally deployed with placeholder metadata `ipfs://aaa`, swap via `update_metadata` proposal if you want to point it at the pinned CID |
