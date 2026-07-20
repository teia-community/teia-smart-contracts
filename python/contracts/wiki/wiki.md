# Wiki Contract

An on-chain registry for the **Teia community wiki**. Each page is identified
solely by an auto-incrementing integer `page_id` and stores its current IPFS/Arweave
**CID**, a `hidden` flag, and a full, append-only **version history**. Page
names/titles live off-chain inside the CID content, duplicate-name checks are the UI's
responsibility.

**Moderators** and **multisig users** can create, update, and hide pages directly, while
**Teia token holders** can submit proposals to edit an existing page or create a brand new
one. Governance (pause, linked addresses, fees, metadata) runs through the linked **Teia
multisig**.

## What it does

- Stores pages keyed by an auto-incrementing `page_id` (never deleted, so the id also
  enumerates every page), each with its `current_cid`, `hidden` flag, and `version_count`.
- Keeps the full version history per page in `versions`, keyed by `(page_id, version)`,
  every version records its CID, editor, optional proposer, and timestamp.
- Lets **moderators / multisig users** create, update, and hide pages directly.
- Lets **Teia token holders** propose an edit to an existing page (`create_proposal`) or a
  brand new page (`prop_new_page`); a single moderator/multisig approval applies it.
- Charges a per-action fee on the two community-proposal entrypoints (both default to 0,
  free) and forwards it to `fee_recipient`.
- Routes all config changes through a **governance** propose → vote → execute flow gated on
  the multisig, with the **minimum vote threshold** and **expiration time** fetched live
  from the multisig contract rather than stored locally.

## Storage

| Field               | Type                                       | Meaning                                                    |
| ------------------- | ------------------------------------------ | ---------------------------------------------------------- |
| `metadata`          | `big_map[string, bytes]`                   | TZIP-16 contract metadata.                                 |
| `moderator_address` | `address`                                  | Linked moderator contract (read via its `is_moderator` view). |
| `multisig_address`  | `address`                                  | The Teia multisig that governs this contract.              |
| `token_address`     | `address`                                  | Teia DAO token FA2 (read via its `get_balance` view).      |
| `token_id`          | `nat`                                      | Token id whose holders may submit proposals.               |
| `paused`            | `bool`                                     | Global pause flag (governance-set).                        |
| `fee_recipient`     | `address`                                  | Where per-action fees are forwarded.                       |
| `propose_edit_fee`  | `mutez`                                    | Fee attached to `create_proposal` (0 = free).              |
| `propose_page_fee`  | `mutez`                                    | Fee attached to `prop_new_page` (0 = free).                |
| `pages`             | `big_map[nat, page]`                       | Page records by id.                                        |
| `versions`          | `big_map[(page_id, version), version]`     | Full version history per page.                             |
| `page_count`        | `nat`                                      | Next page id / total pages.                                |
| `proposals`         | `big_map[nat, proposal]`                   | Community (token-holder) proposals by id.                  |
| `proposal_counter`  | `nat`                                      | Next community proposal id (auto-incrementing).            |
| `gov_proposals`     | `big_map[nat, gov_proposal]`               | Governance proposals by id.                                |
| `gov_votes`         | `big_map[(nat, address), bool]`            | A voter's current vote per governance proposal.            |
| `gov_counter`       | `nat`                                      | Next governance proposal id (auto-incrementing).           |

A `page` records its `current_cid`, `hidden` flag, and `version_count`.

A `version` records its `cid`, `editor`, optional `proposer` (set when the version came
from an approved community proposal), `ts`, and `version` index.

A `proposal` records its `target` (`edit(page_id)` or `new_page`), `proposed_cid`,
`proposer`, `status` (0 = pending, 1 = approved, 2 = rejected), `created_at`, and the
`resolved_by` / `resolved_at` fields (None while pending, set on approval/rejection).

A `gov_proposal` records its `action`, `executed` flag, `issuer`, `timestamp`,
`positive_votes`, and `negative_votes`.

## Who can do what

- **Moderators or multisig users** (moderator checked via the moderator contract's
  `is_moderator` view; multisig user checked via the multisig's `is_user` view — the
  multisig is checked first so a misconfigured moderator address can't lock multisig users
  out) may `create_page`, `update_page`, `set_page_hidden`, `approve_proposal`, and
  `reject_proposal`.
- **Teia token holders** (balance > 0 at `token_id`, verified live via the token's
  `get_balance` view) may `create_proposal` and `prop_new_page`, attaching exactly the
  matching fee.
- **Multisig users only** may `submit_governance_proposal`, `vote_governance_proposal`, and
  `execute_governance_proposal`.
- Anyone failing the relevant check is rejected with `WIKI_NOT_AUTHORIZED` (or `WIKI_NO_TOKENS`
  for the proposal entrypoints).

## Interaction flow

Direct moderation is a single call, `create_page` / `update_page` / `set_page_hidden` by a
moderator or multisig user applies immediately. The community path adds a review step:

```
token holder                 moderator / multisig user
     │                                 │
 create_proposal / prop_new_page       │
 (holds token, pays fee)  ──►  proposal stored, status = pending
     │                                 │
     │                approve_proposal ─► status = approved,
     │                                    edit → new version appended,
     │                                    new_page → page created + id assigned
     │                                 │
     │                 reject_proposal ─► status = rejected (kept on-chain)
```

Config changes use the governance flow, `submit_governance_proposal` → one or more
`vote_governance_proposal` → `execute_governance_proposal` once `positive_votes >=
minimum_votes` and the proposal has not expired.

### Page entrypoints (moderators / multisig users)

- `create_page(cid)` — registers a new page at the next integer id, seeds version 1. Emits
  `page_created`.
- `update_page({page_id, cid})` — appends a new version and updates `current_cid`. Emits
  `page_updated`.
- `set_page_hidden({page_id, hidden})` — flips the `hidden` flag. Emits `page_hidden_updated`.

### Community proposal entrypoints (Teia token holders)

- `create_proposal({page_id, proposed_cid})` — proposes editing an existing page; requires
  exactly `propose_edit_fee`. Emits `proposal_created` (`is_new_page = false`).
- `prop_new_page(cid)` — proposes a brand new page (the id is assigned only on approval);
  requires exactly `propose_page_fee`. Emits `proposal_created` (`is_new_page = true`).
- `approve_proposal(proposal_id)` — moderator/multisig user; applies the change. An `edit`
  appends a new version to the page; a `new_page` creates the page with a fresh id. Emits
  `page_created`/`page_updated` where relevant plus `proposal_approved`.
- `reject_proposal(proposal_id)` — moderator/multisig user; sets status to rejected. The
  proposal record stays on-chain for transparency. Emits `proposal_rejected`.

Both approve and reject require the proposal to still be pending, else `WIKI_ALREADY_RESOLVED`.

### Governance entrypoints (multisig users)

`submit_governance_proposal(action)` creates a proposal, `action` is a variant, exactly one
of:

| Variant                  | Payload          | Effect on execution                          |
| ------------------------ | ---------------- | -------------------------------------------- |
| `set_pause`              | `bool`           | Sets the global `paused` flag.               |
| `set_multisig_address`   | `address`        | Re-points governance to a new multisig.      |
| `set_moderator_address`  | `address`        | Re-points the linked moderator contract.     |
| `set_token_address`      | `address`        | Changes the gating token FA2 contract.       |
| `set_token_id`           | `nat`            | Changes the gating token id.                 |
| `set_fee_recipient`      | `address`        | Changes where fees are forwarded.            |
| `set_propose_edit_fee`   | `mutez`          | Sets the `create_proposal` fee.              |
| `set_propose_page_fee`   | `mutez`          | Sets the `prop_new_page` fee.                |
| `update_metadata`        | `{key, value}`   | Writes one metadata entry (`bytes`).         |

`vote_governance_proposal({proposal_id, approval})` casts (or changes) the sender's vote, a
previous vote is subtracted before the new one is applied, so the tallies always reflect
current standing. Voting on an executed proposal fails (`WIKI_GOV_ALREADY_EXECUTED`), and
voting past the expiration window fails (`WIKI_GOV_EXPIRED`).

`execute_governance_proposal(proposal_id)` applies the action. Requires `positive_votes >=
minimum_votes` (else `WIKI_GOV_NOT_ENOUGH_VOTES`), not already executed (else
`WIKI_GOV_ALREADY_EXECUTED`), and not expired (else `WIKI_GOV_EXPIRED`).

## Views (read-only, callable on-chain by other contracts)

| View                     | Input               | Returns                                        | Use                                          |
| ------------------------ | ------------------- | ---------------------------------------------- | -------------------------------------------- |
| `get_page`               | `nat`               | `page`                                         | Read a page's current CID / hidden / count.  |
| `get_version`            | `(page_id, version)`| `version`                                      | Read one historical version.                 |
| `get_page_count`         | —                   | `nat`                                          | Total number of pages.                       |
| `get_proposal`           | `nat`               | `proposal`                                     | Inspect a community proposal.                |
| `get_proposal_count`     | —                   | `nat`                                          | Total number of community proposals.         |
| `get_fees`               | —                   | `{propose_edit_fee, propose_page_fee, fee_recipient}` | Current per-action fees and recipient. |
| `get_governance_proposal`| `nat`               | `gov_proposal`                                 | Inspect a governance proposal.               |
| `get_governance_vote`    | `(nat, address)`    | `bool` (default `false`)                       | A voter's current vote on a gov proposal.    |

`get_page`, `get_version`, `get_proposal`, and `get_governance_proposal` fail if the id/key
is unknown (see the error reference).

## Dependency on the multisig (and other contracts)

The contract reads several external on-chain views; if any is missing or fails, the
corresponding entrypoint reverts:

- **Multisig** at `multisig_address`:
  - `is_user(address) → bool` — gate on moderation and governance entrypoints.
  - `get_minimum_votes() → nat` — vote threshold, read at governance execution.
  - `get_expiration_time() → nat` (days) — proposal lifetime, read when voting/executing.
- **Moderator** at `moderator_address`:
  - `is_moderator(address) → bool` — checked after the multisig for moderation entrypoints.
- **Token** at `token_address`:
  - `get_balance({owner, token_id}) → nat` — verifies a proposer holds the Teia token.

## Error reference

| Error                        | Cause                                                        |
| ---------------------------- | ----------------------------------------------------------- |
| `WIKI_NOT_AUTHORIZED`        | Caller is not a moderator / multisig user for this action.  |
| `WIKI_PAUSED`                | Contract is paused.                                         |
| `WIKI_TEZ_TRANSFER`          | Tez attached to an entrypoint that expects none.            |
| `WIKI_INCORRECT_FEE`         | Attached amount does not match the action fee.              |
| `WIKI_EMPTY_CID`             | CID cannot be empty.                                        |
| `WIKI_PAGE_NOT_FOUND`        | No page found for this page id.                             |
| `WIKI_VERSION_NOT_FOUND`     | No version found for this `(page_id, version)`.             |
| `WIKI_NO_PROPOSAL`           | Community proposal id does not exist.                       |
| `WIKI_ALREADY_RESOLVED`      | Community proposal was already approved or rejected.        |
| `WIKI_NO_TOKENS`             | Caller does not hold the Teia token.                        |
| `WIKI_NO_GOV_PROPOSAL`       | Governance proposal id does not exist.                      |
| `WIKI_GOV_ALREADY_EXECUTED`  | Governance proposal already executed.                       |
| `WIKI_GOV_NOT_ENOUGH_VOTES`  | `positive_votes < minimum_votes`.                           |
| `WIKI_GOV_EXPIRED`           | Past the multisig's expiration window.                      |
| `WIKI_MULTISIG_VIEW_FAILED`  | Multisig `is_user` view failed.                             |
| `WIKI_MODERATOR_VIEW_FAILED` | Moderator `is_moderator` view failed.                       |
| `WIKI_TOKEN_VIEW_FAILED`     | Token `get_balance` view failed.                            |
| `WIKI_GET_MIN_VOTES_FAILED`  | Multisig `get_minimum_votes` view failed.                   |
| `WIKI_GET_EXPIRATION_FAILED` | Multisig `get_expiration_time` view failed.                 |
