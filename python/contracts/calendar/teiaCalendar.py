import smartpy as sp


@sp.module
def calendar_module():
    """Teia Calendar Contract.

    An on-chain registry of community calendar events, modelled directly on the
    Teia Wiki contract. Each event is identified on-chain solely by an
    auto-incrementing integer ``event_id``. All event details (title, start/end
    date, location, description, links, images) live off-chain in the event's
    IPFS content; the contract stores only the current CID and the hidden flag.
    Full version history is not kept on-chain: every mutation emits a complete
    version event (tag ``event_created`` / ``event_updated``) from which an
    indexer reconstructs the history, which avoids the unbounded storage burn of
    a per-version big_map.

    Access control (mirrors the wiki contract):
    - create_event:     moderators and multisig users
    - update_event:     moderators and multisig users
    - set_event_hidden: moderators and multisig users, plus the event's
      proposer (creator) for events they proposed — but once a moderator has
      hidden an event it becomes mod-locked and only moderators/multisig users
      can change its hidden flag again
    - propose_edit:     Teia token holders (propose an edit to an existing event)
    - propose_event:    Teia token holders (propose a brand new event)
    - approve_proposal / reject_proposal: moderators and multisig users
      (single approve/reject, no quorum)
    - governance (pause, addresses, fees, metadata): multisig vote required

    Per-action fees:
    - propose_edit charges propose_edit_fee, propose_event charges
      propose_event_fee. Both default to 0 (free) and are forwarded to
      fee_recipient. Each fee (and fee_recipient) is changed only through a
      governance proposal, matching the wiki / channels / comment contracts.

    Error codes:
    - CAL_NOT_AUTHORIZED: Caller is not authorized for this action
    - CAL_EVENT_NOT_FOUND: No event found for this event id
    - CAL_EMPTY_CID: CID cannot be empty
    - CAL_PAUSED: Contract is paused
    - CAL_TEZ_TRANSFER: Unexpected tez transfer
    - CAL_INCORRECT_FEE: Attached amount does not match the action fee
    - CAL_NO_PROPOSAL: Proposal ID does not exist
    - CAL_ALREADY_RESOLVED: Proposal has already been approved or rejected
    - CAL_MOD_LOCKED: Event is mod-locked; only a moderator/multisig user can
      change its hidden flag
    - CAL_NO_TOKENS: Caller does not hold Teia tokens
    - CAL_NO_GOV_PROPOSAL: Governance proposal ID does not exist
    - CAL_GOV_ALREADY_EXECUTED: Governance proposal already executed
    - CAL_GOV_NOT_ENOUGH_VOTES: Not enough votes to execute
    - CAL_GOV_EXPIRED: Governance proposal has expired
    """

    # =========================================================================
    # Types
    # =========================================================================

    # Version history is not stored on-chain. Instead every event mutation
    # emits one of these records (tag event_created for a brand-new event,
    # event_updated for a new version of an existing event). An indexer replays
    # these emitted events to reconstruct the full per-event version history.
    version_event_type: type = sp.record(
        event_id=sp.nat,
        cid=sp.string,
        hidden=sp.bool,
        version=sp.nat,
        editor=sp.address,
        proposer=sp.option[sp.address],
        timestamp=sp.timestamp,
    ).layout(
        (
            "event_id",
            (
                "cid",
                (
                    "hidden",
                    ("version", ("editor", ("proposer", "timestamp"))),
                ),
            ),
        )
    )

    # creator is the address that owns the event for hidden-flag purposes: the
    # moderator/multisig user who called create_event, or the proposer of an
    # approved new_event proposal. Being the creator grants set_event_hidden
    # rights even without moderator status (while the event is not mod-locked),
    # so a moderator who later loses their role keeps the ability to toggle the
    # hidden flag on events they created. mod_locked is set once a moderator
    # hides the event, after which only moderators/multisig users can change the
    # hidden flag (the creator can no longer toggle it).
    event_type: type = sp.record(
        current_cid=sp.string,
        hidden=sp.bool,
        version_count=sp.nat,
        creator=sp.option[sp.address],
        mod_locked=sp.bool,
    ).layout(
        (
            "current_cid",
            ("hidden", ("version_count", ("creator", "mod_locked"))),
        )
    )

    # Entrypoint parameter types
    update_event_params_type: type = sp.record(
        event_id=sp.nat,
        cid=sp.string,
    ).layout(("event_id", "cid"))

    set_event_hidden_params_type: type = sp.record(
        event_id=sp.nat,
        hidden=sp.bool,
    ).layout(("event_id", "hidden"))

    # Community proposal types (token holders propose event edits or new events)
    # Status: 0 = pending, 1 = approved, 2 = rejected
    # target.edit(event_id) -> proposes editing an existing event
    # target.new_event()    -> proposes creating a brand new event (the id is
    #                          assigned once the proposal is approved)
    proposal_target_type: type = sp.variant(
        edit=sp.nat,
        new_event=sp.unit,
    )

    # resolved_by / resolved_at are None while pending (status 0) and set to
    # the approver/rejecter and the resolution time when the proposal is
    # approved (status 1) or rejected (status 2).
    proposal_type: type = sp.record(
        target=proposal_target_type,
        proposed_cid=sp.string,
        proposer=sp.address,
        status=sp.nat,
        created_at=sp.timestamp,
        resolved_by=sp.option[sp.address],
        resolved_at=sp.option[sp.timestamp],
    ).layout(
        (
            "target",
            (
                "proposed_cid",
                (
                    "proposer",
                    ("status", ("created_at", ("resolved_by", "resolved_at"))),
                ),
            ),
        )
    )

    create_proposal_params_type: type = sp.record(
        event_id=sp.nat,
        proposed_cid=sp.string,
    ).layout(("event_id", "proposed_cid"))

    # Governance types (config changes require multisig vote)
    metadata_entry_type: type = sp.record(
        key=sp.string,
        value=sp.bytes,
    ).layout(("key", "value"))

    gov_action_type: type = sp.variant(
        set_pause=sp.bool,
        set_multisig_address=sp.address,
        set_moderator_address=sp.address,
        set_token_address=sp.address,
        set_token_id=sp.nat,
        set_fee_recipient=sp.address,
        set_propose_edit_fee=sp.mutez,
        set_propose_event_fee=sp.mutez,
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

    class Calendar(sp.Contract):
        def __init__(
            self,
            metadata,
            moderator_address,
            multisig_address,
            token_address,
            token_id,
            fee_recipient,
            propose_edit_fee,
            propose_event_fee,
            events,
            event_count,
            gov_counter,
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
            self.data.token_address = sp.cast(token_address, sp.address)
            self.data.token_id = sp.cast(token_id, sp.nat)
            self.data.paused = False

            # Per-action fees (forwarded to fee_recipient; 0 = free)
            self.data.fee_recipient = sp.cast(fee_recipient, sp.address)
            self.data.propose_edit_fee = sp.cast(propose_edit_fee, sp.mutez)
            self.data.propose_event_fee = sp.cast(propose_event_fee, sp.mutez)

            # Event storage. Events are keyed by an auto-incrementing integer id
            # (0..event_count-1, never deleted, so the id also enumerates
            # events). Seeded at origination if migrating; pass an empty big_map
            # and event_count 0 for a fresh deployment. Version history lives in
            # emitted events (see version_event_type), not in storage.
            self.data.events = sp.cast(events, sp.big_map[sp.nat, event_type])
            self.data.event_count = sp.cast(event_count, sp.nat)

            # Community proposal storage
            self.data.proposals = sp.cast(
                sp.big_map(), sp.big_map[sp.nat, proposal_type]
            )
            self.data.proposal_counter = sp.cast(sp.nat(0), sp.nat)

            # Governance storage
            self.data.gov_proposals = sp.cast(
                sp.big_map(), sp.big_map[sp.nat, gov_proposal_type]
            )
            self.data.gov_votes = sp.cast(
                sp.big_map(), sp.big_map[gov_vote_key_type, sp.bool]
            )
            self.data.gov_counter = sp.cast(gov_counter, sp.nat)

        # =====================================================================
        # Helper Methods
        # =====================================================================

        @sp.private(with_storage="read-only")
        def _check_not_paused(self):
            assert not self.data.paused, "CAL_PAUSED"

        @sp.private(with_storage="read-only")
        def _check_no_tez_transfer(self):
            assert sp.amount == sp.tez(0), "CAL_TEZ_TRANSFER"

        @sp.private(with_storage="read-only")
        def _check_is_multisig_user(self):
            """Checks that the sender is a multisig user."""
            is_user = sp.view(
                "is_user",
                self.data.multisig_address,
                sp.sender,
                sp.bool,
            ).unwrap_some(error="CAL_MULTISIG_VIEW_FAILED")
            assert is_user, "CAL_NOT_AUTHORIZED"

        @sp.private(with_storage="read-only")
        def _is_moderator_or_multisig(self):
            """Returns whether the sender is a moderator or multisig user.

            The multisig view is checked first so that a misconfigured
            moderator_address cannot lock multisig users out of the
            moderation entrypoints.
            """
            authorized = sp.view(
                "is_user",
                self.data.multisig_address,
                sp.sender,
                sp.bool,
            ).unwrap_some(error="CAL_MULTISIG_VIEW_FAILED")

            if not authorized:
                authorized = sp.view(
                    "is_moderator",
                    self.data.moderator_address,
                    sp.sender,
                    sp.bool,
                ).unwrap_some(error="CAL_MODERATOR_VIEW_FAILED")

            return authorized

        @sp.private(with_storage="read-only")
        def _check_is_moderator_or_multisig(self):
            """Asserts that the sender is a moderator or multisig user.

            Mirrors _is_moderator_or_multisig but fails with CAL_NOT_AUTHORIZED
            instead of returning a bool (SmartPy private methods cannot call
            other private methods, so the view block is duplicated).
            """
            authorized = sp.view(
                "is_user",
                self.data.multisig_address,
                sp.sender,
                sp.bool,
            ).unwrap_some(error="CAL_MULTISIG_VIEW_FAILED")

            if not authorized:
                authorized = sp.view(
                    "is_moderator",
                    self.data.moderator_address,
                    sp.sender,
                    sp.bool,
                ).unwrap_some(error="CAL_MODERATOR_VIEW_FAILED")

            assert authorized, "CAL_NOT_AUTHORIZED"

        @sp.private(with_storage="read-only")
        def _get_minimum_votes(self):
            return sp.view(
                "get_minimum_votes",
                self.data.multisig_address,
                (),
                sp.nat,
            ).unwrap_some(error="CAL_GET_MIN_VOTES_FAILED")

        @sp.private(with_storage="read-only")
        def _check_not_expired(self, timestamp):
            expiration_days = sp.view(
                "get_expiration_time",
                self.data.multisig_address,
                (),
                sp.nat,
            ).unwrap_some(error="CAL_GET_EXPIRATION_FAILED")

            expiration_seconds = sp.to_int(expiration_days * 86400)
            expiration_time = sp.add_seconds(timestamp, expiration_seconds)
            assert not (sp.now > expiration_time), "CAL_GOV_EXPIRED"

        @sp.private(with_storage="read-only")
        def _check_has_tokens(self):
            """Checks that the sender holds Teia tokens (balance > 0)."""
            balance = sp.view(
                "get_balance",
                self.data.token_address,
                sp.record(owner=sp.sender, token_id=self.data.token_id),
                sp.nat,
            ).unwrap_some(error="CAL_TOKEN_VIEW_FAILED")
            assert balance > 0, "CAL_NO_TOKENS"

        @sp.private(with_storage="read-only", with_operations=True)
        def _send_fee(self, fee):
            """Forwards the fee to fee_recipient (only when greater than 0)."""
            if fee > sp.mutez(0):
                sp.send(self.data.fee_recipient, fee)

        # =====================================================================
        # Event Entrypoints (moderators / multisig users)
        # =====================================================================

        @sp.entrypoint
        def create_event(self, cid):
            """Register a new event with its initial CID.

            Moderators and multisig users can create events. The event is
            assigned the next integer id, and the caller is recorded as its
            creator (which grants them set_event_hidden rights on the event even
            if they later lose moderator status). All event details live
            off-chain in the CID content.
            """
            sp.cast(cid, sp.string)
            self._check_not_paused()
            self._check_no_tez_transfer()
            self._check_is_moderator_or_multisig()

            assert sp.len(cid) > 0, "CAL_EMPTY_CID"

            event_id = self.data.event_count

            self.data.events[event_id] = sp.record(
                current_cid=cid,
                hidden=False,
                version_count=sp.nat(1),
                creator=sp.Some(sp.sender),
                mod_locked=False,
            )

            self.data.event_count += 1

            sp.emit(
                sp.cast(
                    sp.record(
                        event_id=event_id,
                        cid=cid,
                        hidden=False,
                        version=sp.nat(1),
                        editor=sp.sender,
                        proposer=sp.cast(None, sp.option[sp.address]),
                        timestamp=sp.now,
                    ),
                    version_event_type,
                ),
                tag="event_created",
            )

        @sp.entrypoint
        def update_event(self, params):
            """Update the current CID for an existing event.

            Only moderators and multisig users can update events directly.
            Events are addressed by their integer id.
            """
            sp.cast(params, update_event_params_type)
            self._check_not_paused()
            self._check_no_tez_transfer()
            self._check_is_moderator_or_multisig()

            assert sp.len(params.cid) > 0, "CAL_EMPTY_CID"
            assert params.event_id in self.data.events, "CAL_EVENT_NOT_FOUND"

            event = self.data.events[params.event_id]
            new_version = event.version_count + 1

            self.data.events[params.event_id] = sp.record(
                current_cid=params.cid,
                hidden=event.hidden,
                version_count=new_version,
                creator=event.creator,
                mod_locked=event.mod_locked,
            )

            sp.emit(
                sp.cast(
                    sp.record(
                        event_id=params.event_id,
                        cid=params.cid,
                        hidden=event.hidden,
                        version=new_version,
                        editor=sp.sender,
                        proposer=sp.cast(None, sp.option[sp.address]),
                        timestamp=sp.now,
                    ),
                    version_event_type,
                ),
                tag="event_updated",
            )

        @sp.entrypoint
        def set_event_hidden(self, params):
            """Set the hidden flag on an event.

            Moderators and multisig users can always hide/unhide any event; a
            moderator hiding an event mod-locks it, and unhiding it clears the
            lock. The event's proposer (creator) can also toggle the hidden
            flag on an event they proposed, but only while it is not mod-locked
            (a proposer action never changes the lock). Events are addressed by
            their integer id.
            """
            sp.cast(params, set_event_hidden_params_type)
            self._check_not_paused()
            self._check_no_tez_transfer()

            assert params.event_id in self.data.events, "CAL_EVENT_NOT_FOUND"

            event = self.data.events[params.event_id]

            is_owner = event.creator.is_some() and (
                event.creator.unwrap_some() == sp.sender
            )
            is_mod = self._is_moderator_or_multisig()

            if not is_mod:
                # Non-moderators must be the event's proposer, and the event
                # must not be mod-locked.
                assert is_owner, "CAL_NOT_AUTHORIZED"
                assert not event.mod_locked, "CAL_MOD_LOCKED"

            # A moderator hiding the event mod-locks it (and unhiding clears the
            # lock); a proposer action never changes the lock.
            new_mod_locked = is_mod and params.hidden

            self.data.events[params.event_id] = sp.record(
                current_cid=event.current_cid,
                hidden=params.hidden,
                version_count=event.version_count,
                creator=event.creator,
                mod_locked=new_mod_locked,
            )

            sp.emit(
                sp.record(
                    event_id=params.event_id,
                    hidden=params.hidden,
                    mod_locked=new_mod_locked,
                    editor=sp.sender,
                    timestamp=sp.now,
                ),
                tag="event_hidden_updated",
            )

        # =====================================================================
        # Community Proposal Entrypoints (Teia token holders)
        # =====================================================================

        @sp.entrypoint
        def propose_edit(self, params):
            """Submit a draft CID to edit an existing event.

            Caller must hold Teia tokens and attach exactly propose_edit_fee.
            The event is addressed by its integer id.
            """
            sp.cast(params, create_proposal_params_type)
            self._check_not_paused()
            assert sp.amount == self.data.propose_edit_fee, "CAL_INCORRECT_FEE"
            self._check_has_tokens()

            assert sp.len(params.proposed_cid) > 0, "CAL_EMPTY_CID"
            assert params.event_id in self.data.events, "CAL_EVENT_NOT_FOUND"

            self._send_fee(sp.amount)

            proposal_id = self.data.proposal_counter
            self.data.proposals[proposal_id] = sp.record(
                target=sp.variant.edit(params.event_id),
                proposed_cid=params.proposed_cid,
                proposer=sp.sender,
                status=sp.nat(0),
                created_at=sp.now,
                resolved_by=sp.cast(None, sp.option[sp.address]),
                resolved_at=sp.cast(None, sp.option[sp.timestamp]),
            )
            self.data.proposal_counter += 1

            sp.emit(
                sp.record(
                    proposal_id=proposal_id,
                    event_id=sp.Some(params.event_id),
                    proposed_cid=params.proposed_cid,
                    proposer=sp.sender,
                    is_new_event=False,
                    timestamp=sp.now,
                ),
                tag="proposal_created",
            )

        @sp.entrypoint
        def propose_event(self, cid):
            """Propose the creation of a brand new event.

            Caller must hold Teia tokens and attach exactly propose_event_fee.
            The event is only created (and assigned an id) once a
            moderator/multisig user approves the proposal.
            """
            sp.cast(cid, sp.string)
            self._check_not_paused()
            assert sp.amount == self.data.propose_event_fee, "CAL_INCORRECT_FEE"
            self._check_has_tokens()

            assert sp.len(cid) > 0, "CAL_EMPTY_CID"

            self._send_fee(sp.amount)

            proposal_id = self.data.proposal_counter
            self.data.proposals[proposal_id] = sp.record(
                target=sp.variant.new_event(()),
                proposed_cid=cid,
                proposer=sp.sender,
                status=sp.nat(0),
                created_at=sp.now,
                resolved_by=sp.cast(None, sp.option[sp.address]),
                resolved_at=sp.cast(None, sp.option[sp.timestamp]),
            )
            self.data.proposal_counter += 1

            sp.emit(
                sp.record(
                    proposal_id=proposal_id,
                    event_id=sp.cast(None, sp.option[sp.nat]),
                    proposed_cid=cid,
                    proposer=sp.sender,
                    is_new_event=True,
                    timestamp=sp.now,
                ),
                tag="proposal_created",
            )

        @sp.entrypoint
        def approve_proposal(self, proposal_id):
            """Approve a pending proposal and apply it to the calendar.

            Only moderators or multisig users can approve (single vote, no
            quorum). Sets status to 1 (approved). For an edit proposal this
            appends a new version to the existing event; for a new-event
            proposal this creates the event and assigns it the next integer id.
            """
            sp.cast(proposal_id, sp.nat)
            self._check_not_paused()
            self._check_no_tez_transfer()
            self._check_is_moderator_or_multisig()

            assert proposal_id in self.data.proposals, "CAL_NO_PROPOSAL"

            proposal = self.data.proposals[proposal_id]
            assert proposal.status == 0, "CAL_ALREADY_RESOLVED"

            proposal.status = sp.nat(1)
            proposal.resolved_by = sp.Some(sp.sender)
            proposal.resolved_at = sp.Some(sp.now)
            self.data.proposals[proposal_id] = proposal

            if proposal.target.is_variant.new_event():
                # Create the proposed event with a fresh integer id.
                event_id = self.data.event_count

                self.data.events[event_id] = sp.record(
                    current_cid=proposal.proposed_cid,
                    hidden=False,
                    version_count=sp.nat(1),
                    creator=sp.Some(proposal.proposer),
                    mod_locked=False,
                )

                self.data.event_count += 1

                sp.emit(
                    sp.cast(
                        sp.record(
                            event_id=event_id,
                            cid=proposal.proposed_cid,
                            hidden=False,
                            version=sp.nat(1),
                            editor=sp.sender,
                            proposer=sp.Some(proposal.proposer),
                            timestamp=sp.now,
                        ),
                        version_event_type,
                    ),
                    tag="event_created",
                )

                sp.emit(
                    sp.record(
                        proposal_id=proposal_id,
                        event_id=event_id,
                        proposed_cid=proposal.proposed_cid,
                        is_new_event=True,
                        approved_by=sp.sender,
                        timestamp=sp.now,
                    ),
                    tag="proposal_approved",
                )
            else:
                # Append a new version to the existing event.
                event_id = proposal.target.unwrap.edit()
                assert event_id in self.data.events, "CAL_EVENT_NOT_FOUND"

                event = self.data.events[event_id]
                new_version = event.version_count + 1

                self.data.events[event_id] = sp.record(
                    current_cid=proposal.proposed_cid,
                    hidden=event.hidden,
                    version_count=new_version,
                    creator=event.creator,
                    mod_locked=event.mod_locked,
                )

                # Emit the version event so an approved edit is captured in the
                # reconstructable history exactly like a direct update_event.
                sp.emit(
                    sp.cast(
                        sp.record(
                            event_id=event_id,
                            cid=proposal.proposed_cid,
                            hidden=event.hidden,
                            version=new_version,
                            editor=sp.sender,
                            proposer=sp.Some(proposal.proposer),
                            timestamp=sp.now,
                        ),
                        version_event_type,
                    ),
                    tag="event_updated",
                )

                sp.emit(
                    sp.record(
                        proposal_id=proposal_id,
                        event_id=event_id,
                        proposed_cid=proposal.proposed_cid,
                        is_new_event=False,
                        approved_by=sp.sender,
                        timestamp=sp.now,
                    ),
                    tag="proposal_approved",
                )

        @sp.entrypoint
        def reject_proposal(self, proposal_id):
            """Reject a pending proposal.

            Only moderators or multisig users can reject (single vote, no
            quorum). Sets status to 2 (rejected). The proposal data remains
            on-chain for transparency.
            """
            sp.cast(proposal_id, sp.nat)
            self._check_not_paused()
            self._check_no_tez_transfer()
            self._check_is_moderator_or_multisig()

            assert proposal_id in self.data.proposals, "CAL_NO_PROPOSAL"

            proposal = self.data.proposals[proposal_id]
            assert proposal.status == 0, "CAL_ALREADY_RESOLVED"

            proposal.status = sp.nat(2)
            proposal.resolved_by = sp.Some(sp.sender)
            proposal.resolved_at = sp.Some(sp.now)
            self.data.proposals[proposal_id] = proposal

            sp.emit(
                sp.record(
                    proposal_id=proposal_id,
                    rejected_by=sp.sender,
                    timestamp=sp.now,
                ),
                tag="proposal_rejected",
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
            assert vote.proposal_id in self.data.gov_proposals, "CAL_NO_GOV_PROPOSAL"

            proposal = self.data.gov_proposals[vote.proposal_id]
            assert not proposal.executed, "CAL_GOV_ALREADY_EXECUTED"
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
            assert proposal_id in self.data.gov_proposals, "CAL_NO_GOV_PROPOSAL"

            proposal = self.data.gov_proposals[proposal_id]
            assert not proposal.executed, "CAL_GOV_ALREADY_EXECUTED"
            minimum_votes = self._get_minimum_votes()
            assert proposal.positive_votes >= minimum_votes, "CAL_GOV_NOT_ENOUGH_VOTES"
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

            if proposal.action.is_variant.set_token_address():
                self.data.token_address = (
                    proposal.action.unwrap.set_token_address()
                )

            if proposal.action.is_variant.set_token_id():
                self.data.token_id = proposal.action.unwrap.set_token_id()

            if proposal.action.is_variant.set_fee_recipient():
                self.data.fee_recipient = (
                    proposal.action.unwrap.set_fee_recipient()
                )

            if proposal.action.is_variant.set_propose_edit_fee():
                self.data.propose_edit_fee = (
                    proposal.action.unwrap.set_propose_edit_fee()
                )

            if proposal.action.is_variant.set_propose_event_fee():
                self.data.propose_event_fee = (
                    proposal.action.unwrap.set_propose_event_fee()
                )

            if proposal.action.is_variant.update_metadata():
                entry = proposal.action.unwrap.update_metadata()
                self.data.metadata[entry.key] = entry.value

        # =====================================================================
        # Views
        # =====================================================================

        @sp.onchain_view()
        def get_event(self, event_id):
            """Returns the event record for a given event id."""
            sp.cast(event_id, sp.nat)
            assert event_id in self.data.events, "CAL_EVENT_NOT_FOUND"
            return self.data.events[event_id]

        @sp.onchain_view()
        def get_event_count(self):
            """Returns the total number of events."""
            return self.data.event_count

        @sp.onchain_view()
        def get_proposal(self, proposal_id):
            """Returns community proposal record by ID."""
            sp.cast(proposal_id, sp.nat)
            assert proposal_id in self.data.proposals, "CAL_NO_PROPOSAL"
            return self.data.proposals[proposal_id]

        @sp.onchain_view()
        def get_proposal_count(self):
            """Returns the total number of community proposals."""
            return self.data.proposal_counter

        @sp.onchain_view()
        def get_fees(self):
            """Returns the current per-action fees and fee recipient."""
            return sp.record(
                propose_edit_fee=self.data.propose_edit_fee,
                propose_event_fee=self.data.propose_event_fee,
                fee_recipient=self.data.fee_recipient,
            )

        @sp.onchain_view()
        def get_governance_proposal(self, proposal_id):
            """Get governance proposal by ID."""
            sp.cast(proposal_id, sp.nat)
            assert proposal_id in self.data.gov_proposals, "CAL_NO_GOV_PROPOSAL"
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
    scenario = sp.test_scenario("deploy_calendar", calendar_module)
    scenario.h1("Teia Calendar Contract — Deployment")

    # =========================================================================
    # DEPLOYMENT VALUES (Mainnet) — reuse the existing wiki/moderator wiring
    # =========================================================================
    # Teia Core Team multisig
    MULTISIG_ADDRESS = sp.address("KT1J9FYz29RBQi1oGLw8uXyACrzXzV1dHuvb")
    # Teia Moderator contract
    MODERATOR_ADDRESS = sp.address("KT1RbVvb4eZh618krF49abrpEmAdb3zK92v6")
    # Teia DAO token (NOT the distributor KT1NrfV...!)
    TOKEN_ADDRESS = sp.address("KT1QrtA753MSv8VGxkDrKKyJniG5JtuHHbtV")
    TOKEN_ID = sp.nat(0)
    # Per-action fees start at 0 (free); the multisig can raise them later.
    FEE_RECIPIENT = sp.address("KT1J9FYz29RBQi1oGLw8uXyACrzXzV1dHuvb")
    PROPOSE_EDIT_FEE = sp.mutez(0)
    PROPOSE_EVENT_FEE = sp.mutez(0)
    # =========================================================================

    contract_metadata = sp.big_map(
        {
            "": sp.scenario_utils.bytes_of_string(
                "ipfs://QmfLiUNMeLPM48Fgiwz3SmqiE63yU46dfXxNepkioyQzSN"
            ),
        }
    )

    contract = calendar_module.Calendar(
        metadata=contract_metadata,
        moderator_address=MODERATOR_ADDRESS,
        multisig_address=MULTISIG_ADDRESS,
        token_address=TOKEN_ADDRESS,
        token_id=TOKEN_ID,
        fee_recipient=FEE_RECIPIENT,
        propose_edit_fee=PROPOSE_EDIT_FEE,
        propose_event_fee=PROPOSE_EVENT_FEE,
        events=sp.big_map(),
        event_count=sp.nat(0),
        gov_counter=sp.nat(0),
    )
    scenario += contract

    scenario.h2("Contract deployed with:")
    scenario.show(MULTISIG_ADDRESS)
    scenario.show(MODERATOR_ADDRESS)
    scenario.show(TOKEN_ADDRESS)
