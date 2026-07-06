import smartpy as sp


@sp.module
def moderator_module():
    """Moderator management contract.

    Multisig wallet users can propose to add or remove wallet addresses as
    moderators. Proposals require a minimum number of votes from multisig
    users to be executed. The minimum votes threshold and proposal expiration
    time are fetched from the linked multisig contract.

    Moderators are stored in a set.
    """

    # =========================================================================
    # Types
    # =========================================================================

    # Metadata entry type for update_metadata proposals
    metadata_entry_type: type = sp.record(
        key=sp.string,
        value=sp.bytes,
    ).layout(("key", "value"))

    # Proposal action variant
    proposal_action_type: type = sp.variant(
        add_moderator=sp.address,
        remove_moderator=sp.address,
        update_multisig_address=sp.address,
        update_metadata=metadata_entry_type,
    )

    # Proposal record type
    proposal_type: type = sp.record(
        action=proposal_action_type,
        executed=sp.bool,
        issuer=sp.address,
        timestamp=sp.timestamp,
        positive_votes=sp.nat,
        minimum_votes=sp.nat,
    ).layout(
        (
            "action",
            (
                "executed",
                (
                    "issuer",
                    ("timestamp", ("positive_votes", "minimum_votes")),
                ),
            ),
        )
    )

    # Key type for votes big map
    vote_key_type: type = sp.pair[sp.nat, sp.address]

    # Vote proposal params
    vote_params_type: type = sp.record(
        proposal_id=sp.nat,
        approval=sp.bool,
    ).layout(("proposal_id", "approval"))

    # =========================================================================
    # Contract
    # =========================================================================

    class Moderator(sp.Contract):
        def __init__(self, metadata, multisig_address, counter):
            # The Contract metadata
            self.data.metadata = sp.cast(
                metadata, sp.big_map[sp.string, sp.bytes]
            )
            # The Multisig Address
            self.data.multisig_address = sp.cast(multisig_address, sp.address)
            # Moderators Set
            self.data.moderators = sp.cast(set(), sp.set[sp.address])
            # Proposals
            self.data.proposals = sp.cast(
                sp.big_map(), sp.big_map[sp.nat, proposal_type]
            )
            # Votes on proposals
            self.data.votes = sp.cast(
                sp.big_map(), sp.big_map[vote_key_type, sp.bool]
            )
            # Proposal Counter
            self.data.counter = sp.cast(counter, sp.nat)

        # =====================================================================
        # Helper Methods
        # =====================================================================

        @sp.private(with_storage="read-only")
        def check_is_user(self):
            """Checks that the sender is a multisig user."""
            is_user = sp.view(
                "is_user",
                self.data.multisig_address,
                sp.sender,
                sp.bool,
            ).unwrap_some(error="MOD_VIEW_FAILED")
            assert is_user, "MOD_NOT_MULTISIG_USER"

        @sp.private(with_storage="read-only")
        def get_minimum_votes(self):
            """Gets the minimum votes required from multisig."""
            return sp.view(
                "get_minimum_votes",
                self.data.multisig_address,
                (),
                sp.nat,
            ).unwrap_some(error="MOD_GET_MIN_VOTES_FAILED")

        # =====================================================================
        # Entrypoints
        # =====================================================================

        @sp.entrypoint
        def submit_proposal(self, action):
            """Submit a new proposal."""
            sp.cast(action, proposal_action_type)

            self.check_is_user()
            minimum_votes = self.get_minimum_votes()

            proposal_id = self.data.counter
            self.data.proposals[proposal_id] = sp.record(
                action=action,
                executed=False,
                issuer=sp.sender,
                timestamp=sp.now,
                positive_votes=sp.nat(0),
                minimum_votes=minimum_votes,
            )
            self.data.counter += 1

            sp.emit(
                sp.record(
                    proposal_id=proposal_id,
                    action=action,
                    issuer=sp.sender,
                    timestamp=sp.now,
                ),
                tag="proposal_submitted",
            )

        @sp.entrypoint
        def vote_proposal(self, vote):
            """Vote on an existing proposal."""
            sp.cast(vote, vote_params_type)

            self.check_is_user()
            assert vote.proposal_id in self.data.proposals, "MOD_NO_PROPOSAL"

            proposal = self.data.proposals[vote.proposal_id]
            assert not proposal.executed, "MOD_ALREADY_EXECUTED"

            vote_key = (vote.proposal_id, sp.sender)

            # Subtract previous positive vote if exists
            if self.data.votes.get(vote_key, default=False):
                proposal.positive_votes = sp.as_nat(proposal.positive_votes - 1)

            # Add to positive votes if approved
            if vote.approval:
                proposal.positive_votes += 1

            # Save vote and proposal
            self.data.votes[vote_key] = vote.approval
            self.data.proposals[vote.proposal_id] = proposal

            sp.emit(
                sp.record(
                    proposal_id=vote.proposal_id,
                    voter=sp.sender,
                    approval=vote.approval,
                    positive_votes=proposal.positive_votes,
                ),
                tag="proposal_voted",
            )

        @sp.entrypoint
        def execute_proposal(self, proposal_id):
            """Execute an approved proposal."""
            sp.cast(proposal_id, sp.nat)

            self.check_is_user()
            assert proposal_id in self.data.proposals, "MOD_NO_PROPOSAL"

            proposal = self.data.proposals[proposal_id]
            assert not proposal.executed, "MOD_ALREADY_EXECUTED"
            assert proposal.positive_votes >= proposal.minimum_votes, "MOD_NOT_ENOUGH_VOTES"

            # Check expiration
            expiration_days = sp.view(
                "get_expiration_time",
                self.data.multisig_address,
                (),
                sp.nat,
            ).unwrap_some(error="MOD_GET_EXPIRATION_FAILED")

            expiration_seconds = sp.to_int(expiration_days * 86400)
            expiration_time = sp.add_seconds(proposal.timestamp, expiration_seconds)
            assert not (sp.now > expiration_time), "MOD_PROPOSAL_EXPIRED"

            # Mark as executed
            proposal.executed = True
            self.data.proposals[proposal_id] = proposal

            # Apply proposal based on action
            if proposal.action.is_variant.add_moderator():
                moderator_address = proposal.action.unwrap.add_moderator()
                self.data.moderators.add(moderator_address)
                sp.emit(
                    sp.record(moderator=moderator_address),
                    tag="moderator_added",
                )

            if proposal.action.is_variant.remove_moderator():
                moderator_address = proposal.action.unwrap.remove_moderator()
                self.data.moderators.remove(moderator_address)
                sp.emit(
                    sp.record(moderator=moderator_address),
                    tag="moderator_removed",
                )

            if proposal.action.is_variant.update_multisig_address():
                new_address = proposal.action.unwrap.update_multisig_address()
                self.data.multisig_address = new_address
                sp.emit(
                    sp.record(multisig_address=new_address),
                    tag="multisig_address_updated",
                )

            if proposal.action.is_variant.update_metadata():
                entry = proposal.action.unwrap.update_metadata()
                self.data.metadata[entry.key] = entry.value
                sp.emit(
                    sp.record(key=entry.key, value=entry.value),
                    tag="metadata_updated",
                )

            sp.emit(
                sp.record(
                    proposal_id=proposal_id,
                    executed_by=sp.sender,
                    timestamp=sp.now,
                ),
                tag="proposal_executed",
            )

        # =====================================================================
        # Views
        # =====================================================================

        @sp.onchain_view
        def is_moderator(self, address):
            """Check if the given address is a moderator."""
            sp.cast(address, sp.address)
            return address in self.data.moderators

        @sp.onchain_view
        def get_moderators(self):
            """Return the set of all moderator addresses."""
            return self.data.moderators

        @sp.onchain_view
        def get_proposal(self, proposal_id):
            """Get proposal by ID."""
            sp.cast(proposal_id, sp.nat)
            assert proposal_id in self.data.proposals, "MOD_NO_PROPOSAL"
            return self.data.proposals[proposal_id]

        @sp.onchain_view
        def get_vote(self, key):
            """Get vote by key (proposal_id, voter)."""
            sp.cast(key, vote_key_type)
            return self.data.votes.get(key, default=False)


# =============================================================================
# Deployment Scenario
# =============================================================================


@sp.add_test()
def moderator_deploy_shadonet():
    """
    Deployment scenario - generates compiled Michelson for origination.
    """
    scenario = sp.test_scenario("moderator_deploy_shadonet", moderator_module)
    scenario.h1("Moderator Contract - Deployment")

    # =========================================================================
    # MODERATOR DEPLOYMENT VALUES
    # =========================================================================
    MULTISIG_ADDRESS = sp.address("KT1KeGd4YtjcKqgyiXUPJQkm2iYA3fQwLGQP")
    # =========================================================================

    contract_metadata = sp.big_map(
        {
            "": sp.scenario_utils.bytes_of_string(
                "ipfs://bafkreidemc23sjtbinvljtm32bsflb2hvnvjzkdn57g5ndldoyxfapcopi"
            ),
        }
    )

    contract = moderator_module.Moderator(
        metadata=contract_metadata,
        multisig_address=MULTISIG_ADDRESS,
        counter=sp.nat(0),
    )
    scenario += contract

    scenario.h2("Contract deployed with multisig:")
    scenario.show(MULTISIG_ADDRESS)
