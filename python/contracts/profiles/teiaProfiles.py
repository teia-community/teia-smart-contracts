import smartpy as sp


@sp.module
def profiles_module():
    """Teia Profiles Contract.

    An on-chain registry of Teia user profiles, modelled on the Teia Wiki,
    Calendar, Curations and Events contracts but keyed by the user's address
    instead of an auto-incrementing id: every address has at most one profile
    and writes it itself. The profile's display name, description, avatar,
    links and artist card configuration live off-chain in the profile's IPFS
    content; the contract stores only the current CID, the claimed handle and
    the moderation flag. Full version history is not kept on-chain: every CID
    change emits a complete version event (tag ``profile_created`` /
    ``profile_updated``) from which an indexer reconstructs the history.

    Handles:
    A profile can claim one unique handle — the on-chain name that resolves to
    its address, as a SUBJKT alias does. A handle is 1 to 32 characters from
    ``a-z``, ``0-9``, ``_`` and ``-``. The restricted, lowercase-only alphabet
    means two handles can never differ only by case or by look-alike
    characters, and the length limit means a handle can never be mistaken for
    a Tezos address (36 characters). The free-form display name lives in the
    IPFS content and is not unique. Claiming a new handle releases the
    previous one.

    Moderation:
    - ``moderated`` flags a profile as hidden from the public. The owner can
      still update a moderated profile but cannot lift the flag.
    - A blocked handle cannot be claimed by anyone. Blocking a handle that is
      currently claimed also releases it. This covers both impersonation /
      abuse and names reserved for front end routes.

    Access control:
    - set_profile / claim_handle / release_handle: any address, for its own
      profile only
    - set_profile_moderated / set_handle_blocked: moderators or multisig users
    - governance (pause, addresses, fees, metadata): multisig vote required

    Per-action fees:
    - set_profile charges profile_fee and claim_handle charges handle_fee.
      Both default to 0 (free) and are forwarded to fee_recipient. Each fee
      (and fee_recipient) is changed only through a governance proposal,
      matching the wiki / calendar / curations contracts.

    Error codes:
    - PRF_NOT_AUTHORIZED: Caller is not authorized for this action
    - PRF_PROFILE_NOT_FOUND: No profile found for this address
    - PRF_EMPTY_CID: CID cannot be empty
    - PRF_PAUSED: Contract is paused
    - PRF_TEZ_TRANSFER: Unexpected tez transfer
    - PRF_INCORRECT_FEE: Attached amount does not match the action fee
    - PRF_INVALID_HANDLE: Handle is empty, too long or has invalid characters
    - PRF_HANDLE_TAKEN: Handle is already claimed
    - PRF_HANDLE_BLOCKED: Handle is blocked and cannot be claimed
    - PRF_NO_HANDLE: Caller's profile has no handle to release
    - PRF_NO_GOV_PROPOSAL: Governance proposal ID does not exist
    - PRF_GOV_ALREADY_EXECUTED: Governance proposal already executed
    - PRF_GOV_NOT_ENOUGH_VOTES: Not enough votes to execute
    - PRF_GOV_EXPIRED: Governance proposal has expired
    """

    # =========================================================================
    # Types
    # =========================================================================

    # Version history is not stored on-chain. Instead every CID change emits
    # one of these records (tag profile_created for a brand-new profile,
    # profile_updated for a new version of an existing one). An indexer replays
    # these emitted events to reconstruct the full per-profile version history.
    version_event_type: type = sp.record(
        address=sp.address,
        cid=sp.string,
        version=sp.nat,
        timestamp=sp.timestamp,
    ).layout(("address", ("cid", ("version", "timestamp"))))

    # handle mirrors the handles big_map (handle -> address) so that a single
    # big_map read by address returns the whole profile.
    profile_type: type = sp.record(
        current_cid=sp.string,
        handle=sp.option[sp.string],
        moderated=sp.bool,
        version_count=sp.nat,
    ).layout(("current_cid", ("handle", ("moderated", "version_count"))))

    # Entrypoint parameter types
    set_profile_moderated_params_type: type = sp.record(
        address=sp.address,
        moderated=sp.bool,
    ).layout(("address", "moderated"))

    set_handle_blocked_params_type: type = sp.record(
        handle=sp.string,
        blocked=sp.bool,
    ).layout(("handle", "blocked"))

    # Governance types (config changes require multisig vote)
    metadata_entry_type: type = sp.record(
        key=sp.string,
        value=sp.bytes,
    ).layout(("key", "value"))

    gov_action_type: type = sp.variant(
        set_pause=sp.bool,
        set_multisig_address=sp.address,
        set_moderator_address=sp.address,
        set_fee_recipient=sp.address,
        set_profile_fee=sp.mutez,
        set_handle_fee=sp.mutez,
        update_metadata=metadata_entry_type,
    )

    gov_proposal_type: type = sp.record(
        action=gov_action_type,
        executed=sp.bool,
        issuer=sp.address,
        timestamp=sp.timestamp,
        positive_votes=sp.nat,
        negative_votes=sp.nat,
    ).layout(
        (
            "action",
            (
                "executed",
                (
                    "issuer",
                    ("timestamp", ("positive_votes", "negative_votes")),
                ),
            ),
        )
    )

    gov_vote_key_type: type = sp.pair[sp.nat, sp.address]

    gov_vote_params_type: type = sp.record(
        proposal_id=sp.nat,
        approval=sp.bool,
    ).layout(("proposal_id", "approval"))
    # =========================================================================
    # Contract
    # =========================================================================

    class Profiles(sp.Contract):
        def __init__(
            self,
            metadata,
            moderator_address,
            multisig_address,
            fee_recipient,
            profile_fee,
            handle_fee,
            blocked_handles,
        ):
            self.data.metadata = sp.cast(
                metadata, sp.big_map[sp.string, sp.bytes]
            )
            self.data.moderator_address = sp.cast(
                moderator_address, sp.address
            )
            self.data.multisig_address = sp.cast(
                multisig_address, sp.address
            )
            self.data.paused = False

            # Per-action fees (forwarded to fee_recipient; 0 = free)
            self.data.fee_recipient = sp.cast(fee_recipient, sp.address)
            self.data.profile_fee = sp.cast(profile_fee, sp.mutez)
            self.data.handle_fee = sp.cast(handle_fee, sp.mutez)

            # Profile storage, keyed by the owner's address. Version history
            # lives in emitted events (see version_event_type), not in storage.
            self.data.profiles = sp.cast(
                sp.big_map(), sp.big_map[sp.address, profile_type]
            )

            # Claimed handles (handle -> owner) and the handles nobody may
            # claim. blocked_handles is seeded at origination with the names
            # reserved for front end routes.
            self.data.handles = sp.cast(
                sp.big_map(), sp.big_map[sp.string, sp.address]
            )
            self.data.blocked_handles = sp.cast(
                blocked_handles, sp.big_map[sp.string, sp.unit]
            )

            # Governance storage
            self.data.gov_proposals = sp.cast(
                sp.big_map(), sp.big_map[sp.nat, gov_proposal_type]
            )
            self.data.gov_votes = sp.cast(
                sp.big_map(), sp.big_map[gov_vote_key_type, sp.bool]
            )
            self.data.gov_counter = sp.cast(sp.nat(0), sp.nat)

        # =====================================================================
        # Helper Methods
        # =====================================================================

        @sp.private(with_storage="read-only")
        def _check_not_paused(self):
            assert not self.data.paused, "PRF_PAUSED"

        @sp.private(with_storage="read-only")
        def _check_no_tez_transfer(self):
            assert sp.amount == sp.tez(0), "PRF_TEZ_TRANSFER"

        @sp.private(with_storage="read-only")
        def _check_is_multisig_user(self):
            """Checks that the sender is a multisig user."""
            is_user = sp.view(
                "is_user",
                self.data.multisig_address,
                sp.sender,
                sp.bool,
            ).unwrap_some(error="PRF_MULTISIG_VIEW_FAILED")
            assert is_user, "PRF_NOT_AUTHORIZED"

        @sp.private(with_storage="read-only")
        def _check_is_moderator_or_multisig(self):
            """Checks that the sender is a moderator or a multisig user.

            The multisig view is checked first so that a misconfigured
            moderator_address cannot lock multisig users out.
            """
            authorized = sp.view(
                "is_user",
                self.data.multisig_address,
                sp.sender,
                sp.bool,
            ).unwrap_some(error="PRF_MULTISIG_VIEW_FAILED")

            if not authorized:
                authorized = sp.view(
                    "is_moderator",
                    self.data.moderator_address,
                    sp.sender,
                    sp.bool,
                ).unwrap_some(error="PRF_MODERATOR_VIEW_FAILED")

            assert authorized, "PRF_NOT_AUTHORIZED"

        @sp.private(with_storage="read-only")
        def _get_minimum_votes(self):
            return sp.view(
                "get_minimum_votes",
                self.data.multisig_address,
                (),
                sp.nat,
            ).unwrap_some(error="PRF_GET_MIN_VOTES_FAILED")

        @sp.private(with_storage="read-only")
        def _check_not_expired(self, timestamp):
            expiration_days = sp.view(
                "get_expiration_time",
                self.data.multisig_address,
                (),
                sp.nat,
            ).unwrap_some(error="PRF_GET_EXPIRATION_FAILED")

            expiration_seconds = sp.to_int(expiration_days * 86400)
            expiration_time = sp.add_seconds(timestamp, expiration_seconds)
            assert not (sp.now > expiration_time), "PRF_GOV_EXPIRED"

        @sp.private(with_storage="read-only", with_operations=True)
        def _send_fee(self, fee):
            """Forwards the fee to fee_recipient (only when greater than 0)."""
            if fee > sp.mutez(0):
                sp.send(self.data.fee_recipient, fee)

        # =====================================================================
        # Profile Entrypoints
        # =====================================================================

        @sp.entrypoint
        def set_profile(self, cid):
            """Create or update the caller's own profile.

            Anyone can set their own profile; the caller's address is the key,
            so nobody can write another address's profile. The first call
            creates the profile, later calls bump version_count and emit the
            new version (the history itself is reconstructed off-chain from
            the emitted events). The handle and moderation flag are left
            untouched. Charges profile_fee (forwarded to fee_recipient).
            """
            sp.cast(cid, sp.string)
            self._check_not_paused()
            assert sp.amount == self.data.profile_fee, "PRF_INCORRECT_FEE"
            assert sp.len(cid) > 0, "PRF_EMPTY_CID"

            self._send_fee(sp.amount)

            if sp.sender in self.data.profiles:
                profile = self.data.profiles[sp.sender]
                profile.current_cid = cid
                profile.version_count += 1
                self.data.profiles[sp.sender] = profile

                sp.emit(
                    sp.cast(
                        sp.record(
                            address=sp.sender,
                            cid=cid,
                            version=profile.version_count,
                            timestamp=sp.now,
                        ),
                        version_event_type,
                    ),
                    tag="profile_updated",
                )
            else:
                self.data.profiles[sp.sender] = sp.record(
                    current_cid=cid,
                    handle=sp.cast(None, sp.option[sp.string]),
                    moderated=False,
                    version_count=sp.nat(1),
                )

                sp.emit(
                    sp.cast(
                        sp.record(
                            address=sp.sender,
                            cid=cid,
                            version=sp.nat(1),
                            timestamp=sp.now,
                        ),
                        version_event_type,
                    ),
                    tag="profile_created",
                )

        @sp.entrypoint
        def set_profile_moderated(self, params):
            """Set the moderation flag on any profile.

            Only moderators and multisig users can flag/unflag a profile as
            moderated (hidden from the public). The owner cannot change this
            flag. No tez transfer.
            """
            sp.cast(params, set_profile_moderated_params_type)
            self._check_not_paused()
            self._check_no_tez_transfer()
            self._check_is_moderator_or_multisig()

            assert (
                params.address in self.data.profiles
            ), "PRF_PROFILE_NOT_FOUND"

            profile = self.data.profiles[params.address]
            profile.moderated = params.moderated
            self.data.profiles[params.address] = profile

            sp.emit(
                sp.record(
                    address=params.address,
                    moderated=params.moderated,
                    editor=sp.sender,
                    timestamp=sp.now,
                ),
                tag="profile_moderated_updated",
            )

        # =====================================================================
        # Handle Entrypoints
        # =====================================================================

        @sp.entrypoint
        def claim_handle(self, handle):
            """Claim a unique handle for the caller's profile.

            The caller must already have a profile. The handle must be 1 to 32
            characters from a-z, 0-9, "_" and "-", not blocked and not claimed
            by anyone (including the caller). Any handle the caller held before
            is released. Charges handle_fee (forwarded to fee_recipient).
            """
            sp.cast(handle, sp.string)
            self._check_not_paused()
            assert sp.amount == self.data.handle_fee, "PRF_INCORRECT_FEE"
            assert sp.sender in self.data.profiles, "PRF_PROFILE_NOT_FOUND"

            length = sp.len(handle)
            assert length > 0 and length <= 32, "PRF_INVALID_HANDLE"
            for i in range(length):
                char = sp.slice(i, 1, handle).unwrap_some()
                assert (
                    (char >= "a" and char <= "z")
                    or (char >= "0" and char <= "9")
                    or char == "_"
                    or char == "-"
                ), "PRF_INVALID_HANDLE"

            assert not (
                handle in self.data.blocked_handles
            ), "PRF_HANDLE_BLOCKED"
            assert not (handle in self.data.handles), "PRF_HANDLE_TAKEN"

            self._send_fee(sp.amount)

            profile = self.data.profiles[sp.sender]
            if profile.handle.is_some():
                del self.data.handles[profile.handle.unwrap_some()]

            sp.emit(
                sp.record(
                    address=sp.sender,
                    handle=handle,
                    previous_handle=profile.handle,
                    timestamp=sp.now,
                ),
                tag="handle_claimed",
            )

            self.data.handles[handle] = sp.sender
            profile.handle = sp.Some(handle)
            self.data.profiles[sp.sender] = profile

        @sp.entrypoint
        def release_handle(self):
            """Release the caller's handle, making it claimable again.

            No tez transfer.
            """
            self._check_not_paused()
            self._check_no_tez_transfer()
            assert sp.sender in self.data.profiles, "PRF_PROFILE_NOT_FOUND"

            profile = self.data.profiles[sp.sender]
            handle = profile.handle.unwrap_some(error="PRF_NO_HANDLE")

            del self.data.handles[handle]
            profile.handle = None
            self.data.profiles[sp.sender] = profile

            sp.emit(
                sp.record(
                    address=sp.sender,
                    handle=handle,
                    released_by=sp.sender,
                    timestamp=sp.now,
                ),
                tag="handle_released",
            )

        @sp.entrypoint
        def set_handle_blocked(self, params):
            """Block or unblock a handle.

            Only moderators and multisig users can block handles. A blocked
            handle cannot be claimed; blocking a handle that is currently
            claimed also releases it from its owner. Unblocking makes the
            handle claimable again but does not hand it back. No tez transfer.
            """
            sp.cast(params, set_handle_blocked_params_type)
            self._check_not_paused()
            self._check_no_tez_transfer()
            self._check_is_moderator_or_multisig()

            if params.blocked:
                self.data.blocked_handles[params.handle] = ()

                if params.handle in self.data.handles:
                    owner = self.data.handles[params.handle]
                    del self.data.handles[params.handle]

                    profile = self.data.profiles[owner]
                    profile.handle = None
                    self.data.profiles[owner] = profile

                    sp.emit(
                        sp.record(
                            address=owner,
                            handle=params.handle,
                            released_by=sp.sender,
                            timestamp=sp.now,
                        ),
                        tag="handle_released",
                    )
            else:
                del self.data.blocked_handles[params.handle]

            sp.emit(
                sp.record(
                    handle=params.handle,
                    blocked=params.blocked,
                    editor=sp.sender,
                    timestamp=sp.now,
                ),
                tag="handle_blocked_updated",
            )

        # =====================================================================
        # Governance Entrypoints (multisig vote)
        # =====================================================================

        @sp.entrypoint
        def submit_governance_proposal(self, action):
            """Submit a new governance proposal for config changes."""
            sp.cast(action, gov_action_type)
            self._check_no_tez_transfer()
            self._check_is_multisig_user()

            self.data.gov_proposals[self.data.gov_counter] = sp.record(
                action=action,
                executed=False,
                issuer=sp.sender,
                timestamp=sp.now,
                positive_votes=sp.nat(0),
                negative_votes=sp.nat(0),
            )
            self.data.gov_counter += 1

        @sp.entrypoint
        def vote_governance_proposal(self, vote):
            """Vote on an existing governance proposal."""
            sp.cast(vote, gov_vote_params_type)

            self._check_no_tez_transfer()
            self._check_is_multisig_user()
            assert (
                vote.proposal_id in self.data.gov_proposals
            ), "PRF_NO_GOV_PROPOSAL"

            proposal = self.data.gov_proposals[vote.proposal_id]
            assert not proposal.executed, "PRF_GOV_ALREADY_EXECUTED"
            self._check_not_expired(proposal.timestamp)

            vote_key = (vote.proposal_id, sp.sender)

            if vote_key in self.data.gov_votes:
                if self.data.gov_votes[vote_key]:
                    proposal.positive_votes = sp.as_nat(
                        proposal.positive_votes - 1
                    )
                else:
                    proposal.negative_votes = sp.as_nat(
                        proposal.negative_votes - 1
                    )

            if vote.approval:
                proposal.positive_votes += 1
            else:
                proposal.negative_votes += 1

            self.data.gov_votes[vote_key] = vote.approval
            self.data.gov_proposals[vote.proposal_id] = proposal

        @sp.entrypoint
        def execute_governance_proposal(self, proposal_id):
            """Execute an approved governance proposal."""
            sp.cast(proposal_id, sp.nat)

            self._check_no_tez_transfer()
            self._check_is_multisig_user()
            assert (
                proposal_id in self.data.gov_proposals
            ), "PRF_NO_GOV_PROPOSAL"

            proposal = self.data.gov_proposals[proposal_id]
            assert not proposal.executed, "PRF_GOV_ALREADY_EXECUTED"
            minimum_votes = self._get_minimum_votes()
            assert (
                proposal.positive_votes >= minimum_votes
            ), "PRF_GOV_NOT_ENOUGH_VOTES"
            self._check_not_expired(proposal.timestamp)

            proposal.executed = True
            self.data.gov_proposals[proposal_id] = proposal

            if proposal.action.is_variant.set_pause():
                self.data.paused = proposal.action.unwrap.set_pause()

            if proposal.action.is_variant.set_multisig_address():
                self.data.multisig_address = (
                    proposal.action.unwrap.set_multisig_address()
                )

            if proposal.action.is_variant.set_moderator_address():
                self.data.moderator_address = (
                    proposal.action.unwrap.set_moderator_address()
                )

            if proposal.action.is_variant.set_fee_recipient():
                self.data.fee_recipient = (
                    proposal.action.unwrap.set_fee_recipient()
                )

            if proposal.action.is_variant.set_profile_fee():
                self.data.profile_fee = (
                    proposal.action.unwrap.set_profile_fee()
                )

            if proposal.action.is_variant.set_handle_fee():
                self.data.handle_fee = proposal.action.unwrap.set_handle_fee()

            if proposal.action.is_variant.update_metadata():
                entry = proposal.action.unwrap.update_metadata()
                self.data.metadata[entry.key] = entry.value

        # =====================================================================
        # Views
        # =====================================================================

        @sp.onchain_view()
        def get_profile(self, address):
            """Returns the profile record for a given address."""
            sp.cast(address, sp.address)
            assert address in self.data.profiles, "PRF_PROFILE_NOT_FOUND"
            return self.data.profiles[address]

        @sp.onchain_view()
        def get_handle_owner(self, handle):
            """Returns the address holding a handle, or None if unclaimed."""
            sp.cast(handle, sp.string)
            return self.data.handles.get_opt(handle)

        @sp.onchain_view()
        def get_fees(self):
            """Returns the current per-action fees and fee recipient."""
            return sp.record(
                profile_fee=self.data.profile_fee,
                handle_fee=self.data.handle_fee,
                fee_recipient=self.data.fee_recipient,
            )

        @sp.onchain_view()
        def get_governance_proposal(self, proposal_id):
            """Get governance proposal by ID."""
            sp.cast(proposal_id, sp.nat)
            assert (
                proposal_id in self.data.gov_proposals
            ), "PRF_NO_GOV_PROPOSAL"
            return self.data.gov_proposals[proposal_id]

        @sp.onchain_view()
        def get_governance_vote(self, key):
            """Get governance vote by key (proposal_id, voter)."""
            sp.cast(key, gov_vote_key_type)
            return self.data.gov_votes.get(key, default=False)

# =============================================================================
# Deployment Scenario
# =============================================================================


@sp.add_test()
def deploy():
    """Deployment scenario — generates compiled Michelson for origination."""
    scenario = sp.test_scenario("deploy_profiles", profiles_module)
    scenario.h1("Teia Profiles Contract — Deployment")

    # =========================================================================
    # DEPLOYMENT VALUES (Mainnet) — reuse the existing wiki/curations wiring
    # =========================================================================
    # Teia Core Team multisig
    MULTISIG_ADDRESS = sp.address("KT1J9FYz29RBQi1oGLw8uXyACrzXzV1dHuvb")
    # Teia Moderator contract
    MODERATOR_ADDRESS = sp.address("KT1RbVvb4eZh618krF49abrpEmAdb3zK92v6")
    # Both fees start at 0 (free); the multisig can raise them later.
    FEE_RECIPIENT = sp.address("KT1J9FYz29RBQi1oGLw8uXyACrzXzV1dHuvb")
    PROFILE_FEE = sp.mutez(0)
    HANDLE_FEE = sp.mutez(0)
    # PLACEHOLDER: handles reserved for front end routes. Replace with the
    # full list of top-level teia-ui routes before originating on mainnet.
    BLOCKED_HANDLES = sp.big_map({"teia": ()})
    # =========================================================================

    # TZIP-16 metadata: metadata/profiles.json, pinned as bafkreicxo77….
    contract_metadata = sp.big_map(
        {
            "": sp.scenario_utils.bytes_of_string(
                "ipfs://bafkreicxo77eypgxreydemjomatemvzu2yomiix4q4tmo5awdbth7zibom"
            ),
        }
    )

    contract = profiles_module.Profiles(
        metadata=contract_metadata,
        moderator_address=MODERATOR_ADDRESS,
        multisig_address=MULTISIG_ADDRESS,
        fee_recipient=FEE_RECIPIENT,
        profile_fee=PROFILE_FEE,
        handle_fee=HANDLE_FEE,
        blocked_handles=BLOCKED_HANDLES,
    )
    scenario += contract

    scenario.h2("Contract deployed with:")
    scenario.show(MULTISIG_ADDRESS)
    scenario.show(MODERATOR_ADDRESS)
