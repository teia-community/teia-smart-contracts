"""Unit tests for the Teia Events contract.

Run from the python/ directory with modern SmartPy (>= 0.17):

    cd python
    SMARTPY_OUTPUT_DIR=../output/tests/events PYTHONPATH=. \
        ~/smartpy-env/bin/python tests/events_test.py

The events contract depends on three external contracts via on-chain views
(multisig `is_user`/`get_minimum_votes`/`get_expiration_time`, moderator
`is_moderator`, FA2 token `get_balance`). Rather than wire up the real
old-syntax contracts, this file declares minimal new-syntax mocks exposing the
exact same view signatures, so the access-control logic can be exercised in
isolation.

A fourth mock stands in for the fee recipient: unlike the curations tests, which
send the fee to a plain tz account, the real deployment points fee_recipient at
the DAO multisig (a KT1 with a `default` entrypoint). MockTreasury reproduces
that so the tests prove the fee actually arrives rather than merely that the
transaction succeeds.
"""

import smartpy as sp

# Import the contract under test. Run from the python/ dir with PYTHONPATH=.
from contracts.events.teiaEvents import events_module


@sp.module
def mocks_module():
    """Stand-ins for the multisig, moderator, DAO token and fee recipient."""

    class MockMultisig(sp.Contract):
        def __init__(self, users, minimum_votes, expiration_time):
            self.data.users = sp.cast(users, sp.set[sp.address])
            self.data.minimum_votes = sp.cast(minimum_votes, sp.nat)
            self.data.expiration_time = sp.cast(expiration_time, sp.nat)

        @sp.onchain_view()
        def is_user(self, user):
            sp.cast(user, sp.address)
            return user in self.data.users

        @sp.onchain_view()
        def get_minimum_votes(self):
            return self.data.minimum_votes

        @sp.onchain_view()
        def get_expiration_time(self):
            return self.data.expiration_time

    class MockModerator(sp.Contract):
        def __init__(self, moderators):
            self.data.moderators = sp.cast(moderators, sp.set[sp.address])

        @sp.onchain_view()
        def is_moderator(self, address):
            sp.cast(address, sp.address)
            return address in self.data.moderators

    class MockToken(sp.Contract):
        def __init__(self, ledger):
            self.data.ledger = sp.cast(
                ledger, sp.big_map[sp.address, sp.nat]
            )

        @sp.onchain_view()
        def get_balance(self, params):
            sp.cast(
                params,
                sp.record(owner=sp.address, token_id=sp.nat).layout(
                    ("owner", "token_id")
                ),
            )
            return self.data.ledger.get(params.owner, default=sp.nat(0))

    class MockTreasury(sp.Contract):
        """Fee recipient with a `default` entrypoint, like the DAO multisig."""

        def __init__(self):
            self.data.received = sp.mutez(0)

        @sp.entrypoint
        def default(self):
            self.data.received += sp.amount


CID1 = "QmEvnt00000000000000000000000000000000000000001"
CID2 = "QmEvnt00000000000000000000000000000000000000002"
CID3 = "QmEvnt00000000000000000000000000000000000000003"
CID4 = "QmEvnt00000000000000000000000000000000000000004"


def _update(event_id, cid):
    return sp.record(event_id=event_id, cid=cid)


def _hidden(event_id, hidden):
    return sp.record(event_id=event_id, hidden=hidden)


def _get_event(contract, event_id):
    return sp.View(contract, "get_event")(event_id)


def _get_event_count(contract):
    return sp.View(contract, "get_event_count")(())


def _get_proposal(contract, proposal_id):
    return sp.View(contract, "get_proposal")(proposal_id)


def _get_proposal_count(contract):
    return sp.View(contract, "get_proposal_count")(())


def _get_fees(contract):
    return sp.View(contract, "get_fees")(())


def _get_gov_proposal(contract, proposal_id):
    return sp.View(contract, "get_governance_proposal")(proposal_id)


def _get_gov_vote(contract, key):
    return sp.View(contract, "get_governance_vote")(key)


@sp.add_test()
def test():
    scenario = sp.test_scenario(
        "events_test", [mocks_module, events_module]
    )
    scenario.h1("Teia Events — unit tests")

    # --- Accounts ---------------------------------------------------------
    multisig_user = sp.test_account("multisig_user")  # in multisig users set
    moderator = sp.test_account("moderator")          # in moderator set
    holder = sp.test_account("holder")                # holds TEIA tokens
    holder2 = sp.test_account("holder2")              # holds TEIA tokens
    stranger = sp.test_account("stranger")            # no role, no tokens

    # --- Mock dependencies ------------------------------------------------
    multisig = mocks_module.MockMultisig(
        users=sp.set([multisig_user.address]),
        minimum_votes=sp.nat(1),
        expiration_time=sp.nat(7),
    )
    scenario += multisig

    moderator_c = mocks_module.MockModerator(
        moderators=sp.set([moderator.address])
    )
    scenario += moderator_c

    # Note: neither the moderator nor the multisig user holds any tokens. That
    # is deliberate — it proves the proposal queue is gated on the token
    # balance independently of the caller's moderation role.
    token = mocks_module.MockToken(
        ledger=sp.big_map(
            {holder.address: sp.nat(5), holder2.address: sp.nat(3)}
        )
    )
    scenario += token

    treasury = mocks_module.MockTreasury()
    scenario += treasury

    # --- Events contract under test (propose_fee = 0) -------------------
    c = events_module.Events(
        metadata=sp.big_map({"": sp.bytes("0x00")}),
        moderator_address=moderator_c.address,
        multisig_address=multisig.address,
        token_address=token.address,
        token_id=sp.nat(0),
        fee_recipient=multisig_user.address,
        propose_fee=sp.mutez(0),
        events=sp.big_map(),
        event_count=sp.nat(0),
        gov_counter=sp.nat(0),
    )
    scenario += c

    # =====================================================================
    # create_event
    # =====================================================================
    scenario.h2("create_event")

    # A moderator creates the first event (id 0).
    c.create_event(CID1, _sender=moderator)
    scenario.verify(_get_event_count(c) == 1)
    scenario.verify(_get_event(c, 0).current_cid == CID1)
    scenario.verify(_get_event(c, 0).hidden == False)
    scenario.verify(_get_event(c, 0).version_count == 1)
    # Created directly, so there is no proposer to attribute it to.
    scenario.verify(c.data.events[0].proposer.is_none())

    # A multisig user can create too (id 1).
    c.create_event(CID2, _sender=multisig_user)
    scenario.verify(_get_event_count(c) == 2)
    scenario.verify(_get_event(c, 1).current_cid == CID2)

    # A mere token holder cannot create directly — this is the whole point of
    # the registry being DAO-curated. They must go through the proposal queue.
    c.create_event(
        CID3, _sender=holder, _valid=False, _exception="EVT_NOT_AUTHORIZED"
    )

    # Neither can somebody with no role and no tokens.
    c.create_event(
        CID3, _sender=stranger, _valid=False, _exception="EVT_NOT_AUTHORIZED"
    )

    # Empty CID is rejected.
    c.create_event(
        "", _sender=moderator, _valid=False, _exception="EVT_EMPTY_CID"
    )

    # Creating is free and takes no tez (D8: no create_fee exists).
    c.create_event(
        CID3, _sender=moderator, _amount=sp.tez(1),
        _valid=False, _exception="EVT_TEZ_TRANSFER"
    )
    scenario.verify(_get_event_count(c) == 2)

    # =====================================================================
    # update_event
    # =====================================================================
    scenario.h2("update_event")

    # A moderator updates event 0: new CID, bumped version, hidden flag and
    # proposer preserved.
    c.update_event(_update(0, CID2), _sender=moderator)
    scenario.verify(_get_event(c, 0).current_cid == CID2)
    scenario.verify(_get_event(c, 0).version_count == 2)
    scenario.verify(_get_event(c, 0).hidden == False)
    scenario.verify(c.data.events[0].proposer.is_none())

    # A multisig user can update any event too.
    c.update_event(_update(1, CID3), _sender=multisig_user)
    scenario.verify(_get_event(c, 1).current_cid == CID3)
    scenario.verify(_get_event(c, 1).version_count == 2)

    # Token holders and strangers cannot update.
    c.update_event(
        _update(0, CID1), _sender=holder,
        _valid=False, _exception="EVT_NOT_AUTHORIZED"
    )
    c.update_event(
        _update(0, CID1), _sender=stranger,
        _valid=False, _exception="EVT_NOT_AUTHORIZED"
    )

    # Unknown event id.
    c.update_event(
        _update(99, CID1), _sender=moderator,
        _valid=False, _exception="EVT_EVENT_NOT_FOUND"
    )

    # Empty CID is rejected.
    c.update_event(
        _update(0, ""), _sender=moderator,
        _valid=False, _exception="EVT_EMPTY_CID"
    )

    # Updating is free and takes no tez.
    c.update_event(
        _update(0, CID1), _sender=moderator, _amount=sp.tez(1),
        _valid=False, _exception="EVT_TEZ_TRANSFER"
    )
    scenario.verify(_get_event(c, 0).version_count == 2)

    # =====================================================================
    # set_event_hidden
    # =====================================================================
    scenario.h2("set_event_hidden")

    # A moderator hides event 0. Hiding is not a new version.
    c.set_event_hidden(_hidden(0, True), _sender=moderator)
    scenario.verify(_get_event(c, 0).hidden == True)
    scenario.verify(_get_event(c, 0).version_count == 2)
    scenario.verify(_get_event(c, 0).current_cid == CID2)

    # A multisig user can unhide it.
    c.set_event_hidden(_hidden(0, False), _sender=multisig_user)
    scenario.verify(_get_event(c, 0).hidden == False)

    # Token holders and strangers cannot.
    c.set_event_hidden(
        _hidden(0, True), _sender=holder,
        _valid=False, _exception="EVT_NOT_AUTHORIZED"
    )
    c.set_event_hidden(
        _hidden(0, True), _sender=stranger,
        _valid=False, _exception="EVT_NOT_AUTHORIZED"
    )

    # Unknown id, and no tez accepted.
    c.set_event_hidden(
        _hidden(99, True), _sender=moderator,
        _valid=False, _exception="EVT_EVENT_NOT_FOUND"
    )
    c.set_event_hidden(
        _hidden(0, True), _sender=moderator, _amount=sp.tez(1),
        _valid=False, _exception="EVT_TEZ_TRANSFER"
    )

    # =====================================================================
    # propose_event
    # =====================================================================
    scenario.h2("propose_event")

    # A token holder proposes a new event. Nothing is added to the registry
    # yet — a proposal is never shown on the events page.
    c.propose_event(CID3, _sender=holder)
    scenario.verify(_get_proposal_count(c) == 1)
    scenario.verify(_get_event_count(c) == 2)
    scenario.verify(_get_proposal(c, 0).proposed_cid == CID3)
    scenario.verify(_get_proposal(c, 0).proposer == holder.address)
    scenario.verify(_get_proposal(c, 0).status == 0)
    scenario.verify(c.data.proposals[0].resolved_by.is_none())
    scenario.verify(c.data.proposals[0].resolved_at.is_none())

    # Somebody holding no tokens cannot propose...
    c.propose_event(
        CID3, _sender=stranger, _valid=False, _exception="EVT_NO_TOKENS"
    )

    # ...and neither can a moderator who holds none: the queue is gated on the
    # token balance, not on the caller's role.
    c.propose_event(
        CID3, _sender=moderator, _valid=False, _exception="EVT_NO_TOKENS"
    )

    # Empty CID is rejected.
    c.propose_event(
        "", _sender=holder, _valid=False, _exception="EVT_EMPTY_CID"
    )

    # propose_fee is 0 here, so attaching tez is an incorrect fee.
    c.propose_event(
        CID3, _sender=holder, _amount=sp.tez(1),
        _valid=False, _exception="EVT_INCORRECT_FEE"
    )

    # =====================================================================
    # approve_proposal
    # =====================================================================
    scenario.h2("approve_proposal")

    # Neither the proposer nor a stranger can approve their own proposal.
    c.approve_proposal(
        0, _sender=holder, _valid=False, _exception="EVT_NOT_AUTHORIZED"
    )
    c.approve_proposal(
        0, _sender=stranger, _valid=False, _exception="EVT_NOT_AUTHORIZED"
    )

    # Unknown proposal id, and no tez accepted.
    c.approve_proposal(
        99, _sender=moderator, _valid=False, _exception="EVT_NO_PROPOSAL"
    )
    c.approve_proposal(
        0, _sender=moderator, _amount=sp.tez(1),
        _valid=False, _exception="EVT_TEZ_TRANSFER"
    )

    # A moderator approves: the proposal is resolved and the event is created
    # with the next id (2), recording the proposer for attribution.
    c.approve_proposal(0, _sender=moderator)
    scenario.verify(_get_proposal(c, 0).status == 1)
    scenario.verify(
        c.data.proposals[0].resolved_by == sp.Some(moderator.address)
    )
    scenario.verify(c.data.proposals[0].resolved_at.is_some())
    scenario.verify(_get_event_count(c) == 3)
    scenario.verify(_get_event(c, 2).current_cid == CID3)
    scenario.verify(_get_event(c, 2).hidden == False)
    scenario.verify(_get_event(c, 2).version_count == 1)
    scenario.verify(c.data.events[2].proposer == sp.Some(holder.address))

    # An already-resolved proposal cannot be approved again.
    c.approve_proposal(
        0, _sender=moderator, _valid=False, _exception="EVT_ALREADY_RESOLVED"
    )

    # =====================================================================
    # The proposer gains no rights over the approved entry
    # =====================================================================
    scenario.h2("Approved proposer has no rights over the entry")

    # This is the core access-control claim of the design: an entry that came
    # from a community proposal is still moderator-only, because its link
    # is embedded on teia.art.
    c.update_event(
        _update(2, CID4), _sender=holder,
        _valid=False, _exception="EVT_NOT_AUTHORIZED"
    )
    c.set_event_hidden(
        _hidden(2, True), _sender=holder,
        _valid=False, _exception="EVT_NOT_AUTHORIZED"
    )

    # A moderator can, and the proposer attribution survives the edit.
    c.update_event(_update(2, CID4), _sender=moderator)
    scenario.verify(_get_event(c, 2).current_cid == CID4)
    scenario.verify(_get_event(c, 2).version_count == 2)
    scenario.verify(c.data.events[2].proposer == sp.Some(holder.address))

    # =====================================================================
    # reject_proposal
    # =====================================================================
    scenario.h2("reject_proposal")

    # A second holder proposes (proposal 1).
    c.propose_event(CID1, _sender=holder2)
    scenario.verify(_get_proposal_count(c) == 2)
    scenario.verify(_get_proposal(c, 1).proposer == holder2.address)

    # Only moderators/multisig users can reject.
    c.reject_proposal(
        1, _sender=holder2, _valid=False, _exception="EVT_NOT_AUTHORIZED"
    )
    c.reject_proposal(
        99, _sender=moderator, _valid=False, _exception="EVT_NO_PROPOSAL"
    )
    c.reject_proposal(
        1, _sender=moderator, _amount=sp.tez(1),
        _valid=False, _exception="EVT_TEZ_TRANSFER"
    )

    # A multisig user rejects it: status 2, and no event is created.
    c.reject_proposal(1, _sender=multisig_user)
    scenario.verify(_get_proposal(c, 1).status == 2)
    scenario.verify(
        c.data.proposals[1].resolved_by == sp.Some(multisig_user.address)
    )
    scenario.verify(_get_event_count(c) == 3)

    # A rejected proposal cannot be approved afterwards.
    c.approve_proposal(
        1, _sender=moderator, _valid=False, _exception="EVT_ALREADY_RESOLVED"
    )
    c.reject_proposal(
        1, _sender=moderator, _valid=False, _exception="EVT_ALREADY_RESOLVED"
    )

    # =====================================================================
    # Fee — a separate instance with propose_fee > 0
    # =====================================================================
    scenario.h2("propose_fee")

    cf = events_module.Events(
        metadata=sp.big_map({"": sp.bytes("0x00")}),
        moderator_address=moderator_c.address,
        multisig_address=multisig.address,
        token_address=token.address,
        token_id=sp.nat(0),
        fee_recipient=treasury.address,
        propose_fee=sp.tez(1),
        events=sp.big_map(),
        event_count=sp.nat(0),
        gov_counter=sp.nat(0),
    )
    scenario += cf

    scenario.verify(_get_fees(cf).propose_fee == sp.tez(1))
    scenario.verify(_get_fees(cf).fee_recipient == treasury.address)

    # Attaching nothing, too little or too much all fail.
    cf.propose_event(
        CID1, _sender=holder, _valid=False, _exception="EVT_INCORRECT_FEE"
    )
    cf.propose_event(
        CID1, _sender=holder, _amount=sp.mutez(999999),
        _valid=False, _exception="EVT_INCORRECT_FEE"
    )
    cf.propose_event(
        CID1, _sender=holder, _amount=sp.tez(2),
        _valid=False, _exception="EVT_INCORRECT_FEE"
    )

    # The exact fee succeeds and actually reaches the fee recipient — the
    # recipient is a KT1 with a `default` entrypoint, as in production.
    cf.propose_event(CID1, _sender=holder, _amount=sp.tez(1))
    scenario.verify(_get_proposal_count(cf) == 1)
    scenario.verify(treasury.data.received == sp.tez(1))
    scenario.verify(treasury.balance == sp.tez(1))

    # Moderator actions stay free on this instance too.
    cf.create_event(
        CID2, _sender=moderator, _amount=sp.tez(1),
        _valid=False, _exception="EVT_TEZ_TRANSFER"
    )
    cf.create_event(CID2, _sender=moderator)
    scenario.verify(_get_event_count(cf) == 1)

    # Approving costs nothing regardless of what the proposer paid.
    cf.approve_proposal(0, _sender=moderator)
    scenario.verify(_get_event_count(cf) == 2)
    scenario.verify(treasury.data.received == sp.tez(1))

    # =====================================================================
    # Governance
    # =====================================================================
    scenario.h2("Governance — fee, votes and pause")

    # Only multisig users may submit, vote and execute.
    c.submit_governance_proposal(
        sp.variant.set_propose_fee(sp.tez(2)), _sender=moderator,
        _valid=False, _exception="EVT_NOT_AUTHORIZED"
    )
    c.submit_governance_proposal(
        sp.variant.set_propose_fee(sp.tez(2)), _sender=holder,
        _valid=False, _exception="EVT_NOT_AUTHORIZED"
    )

    # Governance proposal 0: raise propose_fee to 2 tez.
    c.submit_governance_proposal(
        sp.variant.set_propose_fee(sp.tez(2)), _sender=multisig_user
    )
    scenario.verify(_get_gov_proposal(c, 0).executed == False)
    scenario.verify(_get_gov_proposal(c, 0).positive_votes == 0)

    # Voting is multisig-only, and the proposal must exist.
    c.vote_governance_proposal(
        sp.record(proposal_id=0, approval=True), _sender=holder,
        _valid=False, _exception="EVT_NOT_AUTHORIZED"
    )
    c.vote_governance_proposal(
        sp.record(proposal_id=99, approval=True), _sender=multisig_user,
        _valid=False, _exception="EVT_NO_GOV_PROPOSAL"
    )

    c.vote_governance_proposal(
        sp.record(proposal_id=0, approval=True), _sender=multisig_user
    )
    scenario.verify(_get_gov_proposal(c, 0).positive_votes == 1)
    scenario.verify(_get_gov_vote(c, (0, multisig_user.address)) == True)

    c.execute_governance_proposal(0, _sender=multisig_user)
    scenario.verify(_get_gov_proposal(c, 0).executed == True)
    scenario.verify(_get_fees(c).propose_fee == sp.tez(2))

    # The new fee is live: the old (free) call now fails, the new one works.
    c.propose_event(
        CID2, _sender=holder, _valid=False, _exception="EVT_INCORRECT_FEE"
    )
    c.propose_event(CID2, _sender=holder, _amount=sp.tez(2))
    scenario.verify(_get_proposal_count(c) == 3)

    # Governance proposal 1: pause. Executing before it has the votes fails.
    c.submit_governance_proposal(
        sp.variant.set_pause(True), _sender=multisig_user
    )
    c.execute_governance_proposal(
        1, _sender=multisig_user,
        _valid=False, _exception="EVT_GOV_NOT_ENOUGH_VOTES"
    )

    c.vote_governance_proposal(
        sp.record(proposal_id=1, approval=True), _sender=multisig_user
    )
    c.execute_governance_proposal(1, _sender=multisig_user)
    scenario.verify(_get_gov_proposal(c, 1).executed == True)

    # Everything that mutates is blocked while paused.
    c.create_event(
        CID1, _sender=moderator, _valid=False, _exception="EVT_PAUSED"
    )
    c.update_event(
        _update(0, CID1), _sender=moderator,
        _valid=False, _exception="EVT_PAUSED"
    )
    c.set_event_hidden(
        _hidden(0, True), _sender=moderator,
        _valid=False, _exception="EVT_PAUSED"
    )
    c.propose_event(
        CID1, _sender=holder, _amount=sp.tez(2),
        _valid=False, _exception="EVT_PAUSED"
    )
    c.approve_proposal(
        2, _sender=moderator, _valid=False, _exception="EVT_PAUSED"
    )
    c.reject_proposal(
        2, _sender=moderator, _valid=False, _exception="EVT_PAUSED"
    )

    # An executed proposal cannot be executed or voted on again.
    c.execute_governance_proposal(
        1, _sender=multisig_user,
        _valid=False, _exception="EVT_GOV_ALREADY_EXECUTED"
    )
    c.vote_governance_proposal(
        sp.record(proposal_id=1, approval=False), _sender=multisig_user,
        _valid=False, _exception="EVT_GOV_ALREADY_EXECUTED"
    )

    # Governance itself keeps working while paused — otherwise a pause would be
    # irreversible. Proposal 2 unpauses the contract.
    c.submit_governance_proposal(
        sp.variant.set_pause(False), _sender=multisig_user
    )
    c.vote_governance_proposal(
        sp.record(proposal_id=2, approval=True), _sender=multisig_user
    )
    c.execute_governance_proposal(2, _sender=multisig_user)

    c.create_event(CID1, _sender=moderator)
    scenario.verify(_get_event_count(c) == 4)

    # =====================================================================
    # Remaining governance actions
    # =====================================================================
    scenario.h2("Governance — addresses, token and metadata")

    # Re-point the fee recipient at the treasury mock.
    c.submit_governance_proposal(
        sp.variant.set_fee_recipient(treasury.address), _sender=multisig_user
    )
    c.vote_governance_proposal(
        sp.record(proposal_id=3, approval=True), _sender=multisig_user
    )
    c.execute_governance_proposal(3, _sender=multisig_user)
    scenario.verify(_get_fees(c).fee_recipient == treasury.address)

    # The fee now lands in the treasury (it already held 1 tez from cf).
    c.propose_event(CID3, _sender=holder2, _amount=sp.tez(2))
    scenario.verify(treasury.data.received == sp.tez(3))

    # Token id / token address changes.
    c.submit_governance_proposal(
        sp.variant.set_token_id(sp.nat(1)), _sender=multisig_user
    )
    c.vote_governance_proposal(
        sp.record(proposal_id=4, approval=True), _sender=multisig_user
    )
    c.execute_governance_proposal(4, _sender=multisig_user)
    scenario.verify(c.data.token_id == 1)

    # The mock ledger ignores token_id, so holders still pass; restore it.
    c.submit_governance_proposal(
        sp.variant.set_token_id(sp.nat(0)), _sender=multisig_user
    )
    c.vote_governance_proposal(
        sp.record(proposal_id=5, approval=True), _sender=multisig_user
    )
    c.execute_governance_proposal(5, _sender=multisig_user)
    scenario.verify(c.data.token_id == 0)

    # Metadata update.
    c.submit_governance_proposal(
        sp.variant.update_metadata(
            sp.record(key="", value=sp.bytes("0x01"))
        ),
        _sender=multisig_user,
    )
    c.vote_governance_proposal(
        sp.record(proposal_id=6, approval=True), _sender=multisig_user
    )
    c.execute_governance_proposal(6, _sender=multisig_user)
    scenario.verify(c.data.metadata[""] == sp.bytes("0x01"))

    # Moderator / multisig address changes take effect immediately.
    c.submit_governance_proposal(
        sp.variant.set_moderator_address(moderator_c.address),
        _sender=multisig_user,
    )
    c.vote_governance_proposal(
        sp.record(proposal_id=7, approval=True), _sender=multisig_user
    )
    c.execute_governance_proposal(7, _sender=multisig_user)
    scenario.verify(c.data.moderator_address == moderator_c.address)

    # The remaining two variants are exercised as no-op re-sets to the same
    # addresses: pointing them elsewhere would sever the mocks the rest of the
    # scenario depends on, and the branch itself is what is under test.
    c.submit_governance_proposal(
        sp.variant.set_multisig_address(multisig.address),
        _sender=multisig_user,
    )
    c.vote_governance_proposal(
        sp.record(proposal_id=8, approval=True), _sender=multisig_user
    )
    c.execute_governance_proposal(8, _sender=multisig_user)
    scenario.verify(c.data.multisig_address == multisig.address)

    c.submit_governance_proposal(
        sp.variant.set_token_address(token.address), _sender=multisig_user
    )
    c.vote_governance_proposal(
        sp.record(proposal_id=9, approval=True), _sender=multisig_user
    )
    c.execute_governance_proposal(9, _sender=multisig_user)
    scenario.verify(c.data.token_address == token.address)

    # =====================================================================
    # Vote switching
    # =====================================================================
    scenario.h2("Governance — switching a vote")

    c.submit_governance_proposal(
        sp.variant.set_pause(True), _sender=multisig_user
    )
    c.vote_governance_proposal(
        sp.record(proposal_id=10, approval=True), _sender=multisig_user
    )
    scenario.verify(_get_gov_proposal(c, 10).positive_votes == 1)
    scenario.verify(_get_gov_proposal(c, 10).negative_votes == 0)

    # Switching to a negative vote moves the tally rather than double-counting.
    c.vote_governance_proposal(
        sp.record(proposal_id=10, approval=False), _sender=multisig_user
    )
    scenario.verify(_get_gov_proposal(c, 10).positive_votes == 0)
    scenario.verify(_get_gov_proposal(c, 10).negative_votes == 1)
    scenario.verify(_get_gov_vote(c, (10, multisig_user.address)) == False)

    # With the positive votes withdrawn it can no longer be executed, so the
    # contract is left unpaused.
    c.execute_governance_proposal(
        10, _sender=multisig_user,
        _valid=False, _exception="EVT_GOV_NOT_ENOUGH_VOTES"
    )
    scenario.verify(c.data.paused == False)

    # =====================================================================
    # Governance — expiry
    # =====================================================================
    scenario.h2("Governance — expiry")

    # The mock multisig reports an expiration_time of 7 days, so a proposal
    # submitted at t=0 is dead after 7*86400 seconds. Without this, a stale
    # proposal could be revived and executed years later.
    c.submit_governance_proposal(
        sp.variant.set_pause(True), _sender=multisig_user
    )

    # Voting after the deadline fails.
    c.vote_governance_proposal(
        sp.record(proposal_id=11, approval=True), _sender=multisig_user,
        _now=sp.timestamp(7 * 86400 + 1),
        _valid=False, _exception="EVT_GOV_EXPIRED"
    )
    scenario.verify(_get_gov_proposal(c, 11).positive_votes == 0)

    # Voting in time works, but executing after the deadline still fails — so
    # an approved-but-stale proposal cannot be cashed in later.
    c.vote_governance_proposal(
        sp.record(proposal_id=11, approval=True), _sender=multisig_user
    )
    c.execute_governance_proposal(
        11, _sender=multisig_user, _now=sp.timestamp(7 * 86400 + 1),
        _valid=False, _exception="EVT_GOV_EXPIRED"
    )
    scenario.verify(_get_gov_proposal(c, 11).executed == False)
    scenario.verify(c.data.paused == False)

    # =====================================================================
    # Views
    # =====================================================================
    scenario.h2("Views")

    scenario.verify(_get_event_count(c) == 4)
    scenario.verify(_get_proposal_count(c) == 4)
    scenario.verify(_get_fees(c).propose_fee == sp.tez(2))
    scenario.verify(_get_gov_vote(c, (0, stranger.address)) == False)
    scenario.verify(_get_event(c, 2).current_cid == CID4)
    scenario.verify(_get_proposal(c, 0).status == 1)
