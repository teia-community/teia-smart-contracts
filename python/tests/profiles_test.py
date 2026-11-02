"""Unit tests for the Teia Profiles contract.

Run from the python/ directory with modern SmartPy (>= 0.17):

    cd python
    SMARTPY_OUTPUT_DIR=../output/tests/profiles PYTHONPATH=. \
        ~/smartpy-env/bin/python tests/profiles_test.py

The profiles contract depends on two external contracts via on-chain views
(multisig `is_user`/`get_minimum_votes`/`get_expiration_time`, moderator
`is_moderator`). As in the sibling registry tests, this file declares minimal
new-syntax mocks exposing the exact same view signatures, plus a MockTreasury
standing in for the DAO multisig as fee recipient (a KT1 with a `default`
entrypoint), so the tests prove the fee actually arrives.
"""

import smartpy as sp

# Import the contract under test. Run from the python/ dir with PYTHONPATH=.
from contracts.profiles.teiaProfiles import profiles_module


@sp.module
def mocks_module():
    """Stand-ins for the multisig, moderator and fee recipient."""

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

    class MockTreasury(sp.Contract):
        """Fee recipient with a `default` entrypoint, like the DAO multisig."""

        def __init__(self):
            self.data.received = sp.mutez(0)

        @sp.entrypoint
        def default(self):
            self.data.received += sp.amount


CID1 = "QmProf00000000000000000000000000000000000000001"
CID2 = "QmProf00000000000000000000000000000000000000002"
CID3 = "QmProf00000000000000000000000000000000000000003"


def _moderate(address, moderated):
    return sp.record(address=address, moderated=moderated)


def _block(handle, blocked):
    return sp.record(handle=handle, blocked=blocked)


def _get_profile(contract, address):
    return sp.View(contract, "get_profile")(address)


def _get_handle_owner(contract, handle):
    return sp.View(contract, "get_handle_owner")(handle)


def _get_fees(contract):
    return sp.View(contract, "get_fees")(())


def _get_gov_proposal(contract, proposal_id):
    return sp.View(contract, "get_governance_proposal")(proposal_id)


def _gov(contract, action, proposal_id, sender):
    """Submit, approve and execute a governance proposal as `sender`."""
    contract.submit_governance_proposal(action, _sender=sender)
    contract.vote_governance_proposal(
        sp.record(proposal_id=proposal_id, approval=True), _sender=sender
    )
    contract.execute_governance_proposal(proposal_id, _sender=sender)


@sp.add_test()
def test():
    scenario = sp.test_scenario(
        "profiles_test", [mocks_module, profiles_module]
    )
    scenario.h1("Teia Profiles — unit tests")

    # --- Accounts ---------------------------------------------------------
    multisig_user = sp.test_account("multisig_user")  # in multisig users set
    moderator = sp.test_account("moderator")          # in moderator set
    alice = sp.test_account("alice")
    bob = sp.test_account("bob")
    stranger = sp.test_account("stranger")            # never sets a profile

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

    treasury = mocks_module.MockTreasury()
    scenario += treasury

    # --- Profiles contract under test (both fees = 0) ---------------------
    c = profiles_module.Profiles(
        metadata=sp.big_map({"": sp.bytes("0x00")}),
        moderator_address=moderator_c.address,
        multisig_address=multisig.address,
        fee_recipient=treasury.address,
        profile_fee=sp.mutez(0),
        handle_fee=sp.mutez(0),
        blocked_handles=sp.big_map({"wiki": ()}),
    )
    scenario += c

    # =====================================================================
    # set_profile
    # =====================================================================
    scenario.h2("set_profile")

    # First call creates the profile, keyed by the caller's own address.
    c.set_profile(CID1, _sender=alice)
    p = _get_profile(c, alice.address)
    scenario.verify(p.current_cid == CID1)
    scenario.verify(p.handle == None)
    scenario.verify(p.moderated == False)
    scenario.verify(p.version_count == 1)

    # Later calls update it and bump the version.
    c.set_profile(CID2, _sender=alice)
    p = _get_profile(c, alice.address)
    scenario.verify(p.current_cid == CID2)
    scenario.verify(p.version_count == 2)

    # A second address gets its own, independent profile: there is no way to
    # write somebody else's (the entrypoint takes no address).
    c.set_profile(CID3, _sender=bob)
    scenario.verify(_get_profile(c, bob.address).current_cid == CID3)
    scenario.verify(_get_profile(c, bob.address).version_count == 1)
    scenario.verify(_get_profile(c, alice.address).current_cid == CID2)

    # Empty CID and unexpected tez (fee is 0) are rejected.
    c.set_profile("", _sender=alice, _valid=False, _exception="PRF_EMPTY_CID")
    c.set_profile(
        CID1, _sender=alice, _amount=sp.mutez(1),
        _valid=False, _exception="PRF_INCORRECT_FEE"
    )

    # No profile for an address that never set one.
    scenario.verify(
        sp.is_failing(_get_profile(c, stranger.address))
    )

    # =====================================================================
    # claim_handle
    # =====================================================================
    scenario.h2("claim_handle")

    # A profile is required before claiming a handle.
    c.claim_handle(
        "stranger", _sender=stranger,
        _valid=False, _exception="PRF_PROFILE_NOT_FOUND"
    )

    c.claim_handle("alice", _sender=alice)
    scenario.verify(_get_profile(c, alice.address).handle == sp.Some("alice"))
    scenario.verify(_get_handle_owner(c, "alice") == sp.Some(alice.address))
    scenario.verify(_get_handle_owner(c, "nobody") == None)

    # Claiming does not touch the CID or the version.
    scenario.verify(_get_profile(c, alice.address).current_cid == CID2)
    scenario.verify(_get_profile(c, alice.address).version_count == 2)

    # Handles are unique: nobody else can take it, and re-claiming one's own
    # handle is rejected too.
    c.claim_handle(
        "alice", _sender=bob, _valid=False, _exception="PRF_HANDLE_TAKEN"
    )
    c.claim_handle(
        "alice", _sender=alice, _valid=False, _exception="PRF_HANDLE_TAKEN"
    )

    # Every allowed character class, and the 32 character maximum.
    c.claim_handle("b0b_the-2nd", _sender=bob)
    c.claim_handle("a" * 32, _sender=bob)

    # Claiming a new handle released the previous one.
    scenario.verify(_get_profile(c, bob.address).handle == sp.Some("a" * 32))
    scenario.verify(_get_handle_owner(c, "b0b_the-2nd") == None)
    scenario.verify(_get_handle_owner(c, "a" * 32) == sp.Some(bob.address))

    # Invalid handles: empty, too long, uppercase, space, punctuation and the
    # characters just outside each allowed range.
    for bad in [
        "", "a" * 33, "Alice", "al ice", "alice.tez", "alice!", "@alice",
        "a/b", "a:b", "a`b", "a{b",
    ]:
        c.claim_handle(
            bad, _sender=bob, _valid=False, _exception="PRF_INVALID_HANDLE"
        )
    # A failed claim leaves the previous handle in place.
    scenario.verify(_get_profile(c, bob.address).handle == sp.Some("a" * 32))

    # Handles blocked at origination cannot be claimed.
    c.claim_handle(
        "wiki", _sender=bob, _valid=False, _exception="PRF_HANDLE_BLOCKED"
    )

    # Unexpected tez (fee is 0) is rejected.
    c.claim_handle(
        "bob", _sender=bob, _amount=sp.mutez(1),
        _valid=False, _exception="PRF_INCORRECT_FEE"
    )

    # =====================================================================
    # release_handle
    # =====================================================================
    scenario.h2("release_handle")

    c.release_handle(
        _sender=stranger, _valid=False, _exception="PRF_PROFILE_NOT_FOUND"
    )
    c.release_handle(
        _sender=bob, _amount=sp.mutez(1),
        _valid=False, _exception="PRF_TEZ_TRANSFER"
    )

    c.release_handle(_sender=bob)
    scenario.verify(_get_profile(c, bob.address).handle == None)
    scenario.verify(_get_handle_owner(c, "a" * 32) == None)

    # Nothing left to release.
    c.release_handle(_sender=bob, _valid=False, _exception="PRF_NO_HANDLE")

    # A released handle can be claimed by someone else; alice's is untouched.
    c.claim_handle("bob", _sender=bob)
    scenario.verify(_get_handle_owner(c, "bob") == sp.Some(bob.address))
    scenario.verify(_get_handle_owner(c, "alice") == sp.Some(alice.address))

    # =====================================================================
    # set_handle_blocked
    # =====================================================================
    scenario.h2("set_handle_blocked")

    # Only moderators / multisig users can block.
    for sender in [alice, bob, stranger]:
        c.set_handle_blocked(
            _block("bob", True), _sender=sender,
            _valid=False, _exception="PRF_NOT_AUTHORIZED"
        )
    c.set_handle_blocked(
        _block("bob", True), _sender=moderator, _amount=sp.mutez(1),
        _valid=False, _exception="PRF_TEZ_TRANSFER"
    )

    # Blocking a claimed handle releases it from its owner...
    c.set_handle_blocked(_block("bob", True), _sender=moderator)
    scenario.verify(_get_profile(c, bob.address).handle == None)
    scenario.verify(_get_handle_owner(c, "bob") == None)
    # ...leaves the rest of the profile alone...
    scenario.verify(_get_profile(c, bob.address).current_cid == CID3)
    # ...and nobody can claim it again, the previous owner included.
    c.claim_handle(
        "bob", _sender=bob, _valid=False, _exception="PRF_HANDLE_BLOCKED"
    )
    c.claim_handle(
        "bob", _sender=alice, _valid=False, _exception="PRF_HANDLE_BLOCKED"
    )

    # Blocking an unclaimed handle (multisig user this time).
    c.set_handle_blocked(_block("curations", True), _sender=multisig_user)
    c.claim_handle(
        "curations", _sender=bob,
        _valid=False, _exception="PRF_HANDLE_BLOCKED"
    )

    # Unblocking makes the handle claimable again but does not hand it back.
    c.set_handle_blocked(_block("bob", False), _sender=moderator)
    scenario.verify(_get_profile(c, bob.address).handle == None)
    c.claim_handle("bob", _sender=alice)
    scenario.verify(_get_handle_owner(c, "bob") == sp.Some(alice.address))
    scenario.verify(_get_handle_owner(c, "alice") == None)

    # Unblocking a handle that was never blocked is a no-op.
    c.set_handle_blocked(_block("never-blocked", False), _sender=moderator)

    # =====================================================================
    # set_profile_moderated
    # =====================================================================
    scenario.h2("set_profile_moderated")

    # Only moderators / multisig users — not even the owner.
    for sender in [alice, bob, stranger]:
        c.set_profile_moderated(
            _moderate(alice.address, True), _sender=sender,
            _valid=False, _exception="PRF_NOT_AUTHORIZED"
        )
    c.set_profile_moderated(
        _moderate(stranger.address, True), _sender=moderator,
        _valid=False, _exception="PRF_PROFILE_NOT_FOUND"
    )
    c.set_profile_moderated(
        _moderate(alice.address, True), _sender=moderator,
        _amount=sp.mutez(1), _valid=False, _exception="PRF_TEZ_TRANSFER"
    )

    c.set_profile_moderated(_moderate(alice.address, True), _sender=moderator)
    scenario.verify(_get_profile(c, alice.address).moderated == True)
    scenario.verify(_get_profile(c, bob.address).moderated == False)

    # The owner can still update a moderated profile, but that does not lift
    # the flag, and they cannot lift it themselves.
    c.set_profile(CID1, _sender=alice)
    p = _get_profile(c, alice.address)
    scenario.verify(p.current_cid == CID1)
    scenario.verify(p.version_count == 3)
    scenario.verify(p.moderated == True)
    scenario.verify(p.handle == sp.Some("bob"))
    c.set_profile_moderated(
        _moderate(alice.address, False), _sender=alice,
        _valid=False, _exception="PRF_NOT_AUTHORIZED"
    )

    # A multisig user lifts it.
    c.set_profile_moderated(
        _moderate(alice.address, False), _sender=multisig_user
    )
    scenario.verify(_get_profile(c, alice.address).moderated == False)

    # =====================================================================
    # Governance — access, fees, pause
    # =====================================================================
    scenario.h2("Governance")

    # Only multisig users can submit / vote / execute.
    for sender in [moderator, alice, stranger]:
        c.submit_governance_proposal(
            sp.variant.set_pause(True), _sender=sender,
            _valid=False, _exception="PRF_NOT_AUTHORIZED"
        )

    scenario.verify(_get_fees(c).profile_fee == sp.mutez(0))
    scenario.verify(_get_fees(c).handle_fee == sp.mutez(0))
    scenario.verify(_get_fees(c).fee_recipient == treasury.address)

    # Not enough votes: cannot execute before voting.
    c.submit_governance_proposal(
        sp.variant.set_profile_fee(sp.mutez(100000)), _sender=multisig_user
    )
    c.execute_governance_proposal(
        0, _sender=multisig_user,
        _valid=False, _exception="PRF_GOV_NOT_ENOUGH_VOTES"
    )
    c.vote_governance_proposal(
        sp.record(proposal_id=0, approval=True), _sender=alice,
        _valid=False, _exception="PRF_NOT_AUTHORIZED"
    )
    c.vote_governance_proposal(
        sp.record(proposal_id=0, approval=True), _sender=multisig_user
    )
    c.execute_governance_proposal(0, _sender=multisig_user)
    scenario.verify(_get_gov_proposal(c, 0).executed == True)
    c.execute_governance_proposal(
        0, _sender=multisig_user,
        _valid=False, _exception="PRF_GOV_ALREADY_EXECUTED"
    )
    c.execute_governance_proposal(
        99, _sender=multisig_user,
        _valid=False, _exception="PRF_NO_GOV_PROPOSAL"
    )

    _gov(c, sp.variant.set_handle_fee(sp.mutez(500000)), 1, multisig_user)
    scenario.verify(_get_fees(c).profile_fee == sp.mutez(100000))
    scenario.verify(_get_fees(c).handle_fee == sp.mutez(500000))

    # --- Fees are exact and forwarded to the recipient --------------------
    scenario.h3("Fees")
    c.set_profile(
        CID2, _sender=bob, _valid=False, _exception="PRF_INCORRECT_FEE"
    )
    c.set_profile(
        CID2, _sender=bob, _amount=sp.mutez(100001),
        _valid=False, _exception="PRF_INCORRECT_FEE"
    )
    c.set_profile(CID2, _sender=bob, _amount=sp.mutez(100000))
    scenario.verify(treasury.data.received == sp.mutez(100000))

    c.claim_handle(
        "robert", _sender=bob, _valid=False, _exception="PRF_INCORRECT_FEE"
    )
    c.claim_handle(
        "robert", _sender=bob, _amount=sp.mutez(100000),
        _valid=False, _exception="PRF_INCORRECT_FEE"
    )
    # A rejected claim (handle taken) does not collect the fee.
    c.claim_handle(
        "bob", _sender=bob, _amount=sp.mutez(500000),
        _valid=False, _exception="PRF_HANDLE_TAKEN"
    )
    c.claim_handle("robert", _sender=bob, _amount=sp.mutez(500000))
    scenario.verify(treasury.data.received == sp.mutez(600000))
    scenario.verify(treasury.balance == sp.mutez(600000))
    # The contract itself never holds tez.
    scenario.verify(c.balance == sp.mutez(0))

    # Releasing stays free.
    c.release_handle(_sender=bob)

    # --- Pause ------------------------------------------------------------
    scenario.h3("Pause")
    _gov(c, sp.variant.set_pause(True), 2, multisig_user)

    c.set_profile(
        CID3, _sender=bob, _amount=sp.mutez(100000),
        _valid=False, _exception="PRF_PAUSED"
    )
    c.claim_handle(
        "robert", _sender=bob, _amount=sp.mutez(500000),
        _valid=False, _exception="PRF_PAUSED"
    )
    c.release_handle(_sender=alice, _valid=False, _exception="PRF_PAUSED")
    c.set_profile_moderated(
        _moderate(bob.address, True), _sender=moderator,
        _valid=False, _exception="PRF_PAUSED"
    )
    c.set_handle_blocked(
        _block("robert", True), _sender=moderator,
        _valid=False, _exception="PRF_PAUSED"
    )

    # Governance still works while paused, so it can be unpaused.
    _gov(c, sp.variant.set_pause(False), 3, multisig_user)
    c.set_profile(CID3, _sender=bob, _amount=sp.mutez(100000))
    scenario.verify(_get_profile(c, bob.address).current_cid == CID3)

    # --- Remaining actions --------------------------------------------------
    scenario.h3("Addresses and metadata")
    new_mod = sp.test_account("new_mod")
    moderator_c2 = mocks_module.MockModerator(
        moderators=sp.set([new_mod.address])
    )
    scenario += moderator_c2
    _gov(
        c, sp.variant.set_moderator_address(moderator_c2.address),
        4, multisig_user,
    )
    c.set_profile_moderated(
        _moderate(bob.address, True), _sender=moderator,
        _valid=False, _exception="PRF_NOT_AUTHORIZED"
    )
    c.set_profile_moderated(_moderate(bob.address, True), _sender=new_mod)
    scenario.verify(_get_profile(c, bob.address).moderated == True)

    _gov(
        c, sp.variant.set_fee_recipient(alice.address), 5, multisig_user
    )
    scenario.verify(_get_fees(c).fee_recipient == alice.address)

    _gov(
        c,
        sp.variant.update_metadata(sp.record(key="", value=sp.bytes("0x01"))),
        6, multisig_user,
    )
    scenario.verify(c.data.metadata[""] == sp.bytes("0x01"))

    new_ms_user = sp.test_account("new_ms_user")
    multisig2 = mocks_module.MockMultisig(
        users=sp.set([new_ms_user.address]),
        minimum_votes=sp.nat(1),
        expiration_time=sp.nat(7),
    )
    scenario += multisig2
    _gov(
        c, sp.variant.set_multisig_address(multisig2.address),
        7, multisig_user,
    )
    c.submit_governance_proposal(
        sp.variant.set_pause(True), _sender=multisig_user,
        _valid=False, _exception="PRF_NOT_AUTHORIZED"
    )

    # --- Expiry -------------------------------------------------------------
    scenario.h3("Expiry")
    c.submit_governance_proposal(
        sp.variant.set_pause(True), _sender=new_ms_user, _now=sp.timestamp(0)
    )
    c.vote_governance_proposal(
        sp.record(proposal_id=8, approval=True), _sender=new_ms_user,
        _now=sp.timestamp(7 * 86400 + 1),
        _valid=False, _exception="PRF_GOV_EXPIRED"
    )
