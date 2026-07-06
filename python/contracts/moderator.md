# Moderator Contract

An additional governance contract that maintains a **set of moderator addresses**. It does
not act on its own, it relies on the linked **Teia multisig** contract to decide who
is allowed to govern it. 
Moderators stored here are then read by other contracts (e.g.
the **wiki** contract) to authorize moderation actions.

## What it does

- Holds a `set` of moderator addresses (`data.moderators`).
- Lets **multisig users** propose changes (add/remove a moderator, change the linked
  multisig, or update contract metadata).
- Each proposal must collect enough **positive votes** before it can be executed.
- The **minimum vote threshold** and the **proposal expiration time** are not stored
  locally — they are fetched live from the multisig contract via on-chain views, so the
  moderator contract always follows the multisig's current rules.

## Storage

| Field               | Type                                | Meaning                                            |
| ------------------- | ----------------------------------- | -------------------------------------------------- |
| `metadata`          | `big_map[string, bytes]`            | TZIP-16 contract metadata.                         |
| `multisig_address`  | `address`                           | The Teia multisig that governs this contract.      |
| `moderators`        | `set[address]`                      | Current moderators.                                |
| `proposals`         | `big_map[nat, proposal]`            | All proposals by id.                               |
| `votes`             | `big_map[(nat, address), bool]`     | A voter's current vote per proposal.               |
| `counter`           | `nat`                               | Next proposal id (auto-incrementing).              |

A `proposal` records its `action`, `executed` flag, `issuer`, `timestamp`,
`positive_votes`, and the `minimum_votes` snapshotted at submission time.

## Who can do what

- **Multisig users** (verified live through the multisig's `is_user` view) may
  `submit_proposal`, `vote_proposal`, and `execute_proposal`.
- Anyone failing that check is rejected with `MOD_NOT_MULTISIG_USER`.
- There is **no admin** — every change goes through the propose → vote → execute flow.

## Interaction flow

```
multisig user                multisig user(s)             multisig user
     │                              │                           │
 submit_proposal  ──►  proposal stored, votes = 0               │
     │                              │                           │
     │              vote_proposal (approval=true) ─► positive_votes++
     │                              │                           │
     │                              │            execute_proposal ─► action applied,
     │                              │                              proposal marked executed
```

### 1. `submit_proposal(action)`

Creates a new proposal. `action` is a variant, exactly one of:

| Variant                   | Payload            | Effect on execution                          |
| ------------------------- | ------------------ | -------------------------------------------- |
| `add_moderator`           | `address`          | Adds the address to the moderators set.      |
| `remove_moderator`        | `address`          | Removes the address from the moderators set. |
| `update_multisig_address` | `address`          | Re-points governance to a new multisig.      |
| `update_metadata`         | `{key, value}`     | Writes one metadata entry (`bytes`).         |

The proposal starts with `positive_votes = 0` and snapshots the current
`minimum_votes` from the multisig. Emits `proposal_submitted`.

### 2. `vote_proposal({proposal_id, approval})`

Casts (or changes) the sender's vote on a proposal.

- A voter can change their mind: a previous positive vote is subtracted before the new
  vote is applied, so `positive_votes` always reflects current standing.
- Voting on an already-executed proposal fails (`MOD_ALREADY_EXECUTED`).
- Emits `proposal_voted` with the running `positive_votes` count.

### 3. `execute_proposal(proposal_id)`

Applies the proposal's action. Requires:

- `positive_votes >= minimum_votes` → else `MOD_NOT_ENOUGH_VOTES`.
- Not already executed → else `MOD_ALREADY_EXECUTED`.
- Not expired: `now <= timestamp + (expiration_days * 86400)`, where `expiration_days`
  comes from the multisig's `get_expiration_time` view → else `MOD_PROPOSAL_EXPIRED`.

On success it marks the proposal executed, applies the action, and emits an
action-specific event (`moderator_added`, `moderator_removed`,
`multisig_address_updated`, or `metadata_updated`) plus `proposal_executed`.

## Views (read-only, callable on-chain by other contracts)

| View             | Input              | Returns        | Use                                              |
| ---------------- | ------------------ | -------------- | ------------------------------------------------ |
| `is_moderator`   | `address`          | `bool`         | How the wiki (etc.) checks a caller's authority. |
| `get_moderators` | —                  | `set[address]` | List all moderators.                             |
| `get_proposal`   | `nat`              | `proposal`     | Inspect a proposal (fails if id unknown).        |
| `get_vote`       | `(nat, address)`   | `bool`         | A voter's current vote on a proposal.            |

## Dependency on the multisig

The contract calls three multisig on-chain views; if any is missing or fails, the
corresponding entrypoint reverts:

- `is_user(address) → bool` — gate on every entrypoint.
- `get_minimum_votes() → nat` — vote threshold, read at submission.
- `get_expiration_time() → nat` (days) — proposal lifetime, read at execution.

## Error reference

| Error                       | Cause                                             |
| --------------------------- | ------------------------------------------------- |
| `MOD_NOT_MULTISIG_USER`     | Sender is not a multisig user.                    |
| `MOD_VIEW_FAILED`           | Multisig `is_user` view failed.                   |
| `MOD_GET_MIN_VOTES_FAILED`  | Multisig `get_minimum_votes` view failed.         |
| `MOD_GET_EXPIRATION_FAILED` | Multisig `get_expiration_time` view failed.       |
| `MOD_NO_PROPOSAL`           | Proposal id does not exist.                       |
| `MOD_ALREADY_EXECUTED`      | Proposal already executed.                        |
| `MOD_NOT_ENOUGH_VOTES`      | `positive_votes < minimum_votes`.                 |
| `MOD_PROPOSAL_EXPIRED`      | Past the multisig's expiration window.            |

