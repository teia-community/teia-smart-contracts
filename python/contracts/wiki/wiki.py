import smartpy as sp


@sp.module
def wiki_module():
    """Teia Wiki Contract.

    Each page is identified on-chain solely by an auto-incrementing
    integer ``page_id``. Page names/titles live off-chain in the page's
    IPFS/Arweave content; the contract stores only the current CID, the hidden
    flag and the full version history per page. Duplicate-name checks are the
    UI's responsibility. Token holders can propose page edits; moderators and
    multisig users can approve, reject, create, and update pages directly.

    Access control:
    - create_page: moderators and multisig users
    - update_page: moderators and multisig users
    - set_page_hidden: moderators and multisig users
    - create_proposal: Teia token holders (propose an edit to an existing page)
    - prop_new_page: Teia token holders (propose a brand new page)
    - approve_proposal / reject_proposal: moderators and multisig users
    - governance (pause, addresses, fees, metadata): multisig vote required

    Per-action fees:
    - create_proposal charges propose_edit_fee, prop_new_page charges
      propose_page_fee. Both default to 0 (free) and are forwarded to
      fee_recipient. Each fee (and fee_recipient) is changed only through a
      governance proposal, matching the channels / comment contracts.

    Error codes:
    - WIKI_NOT_AUTHORIZED: Caller is not authorized for this action
    - WIKI_PAGE_NOT_FOUND: No page found for this page id
    - WIKI_VERSION_NOT_FOUND: No version found for this (page id, version)
    - WIKI_EMPTY_CID: CID cannot be empty
    - WIKI_PAUSED: Contract is paused
    - WIKI_TEZ_TRANSFER: Unexpected tez transfer
    - WIKI_INCORRECT_FEE: Attached amount does not match the action fee
    - WIKI_NO_PROPOSAL: Proposal ID does not exist
    - WIKI_ALREADY_RESOLVED: Proposal has already been approved or rejected
    - WIKI_NO_TOKENS: Caller does not hold Teia tokens
    - WIKI_NO_GOV_PROPOSAL: Governance proposal ID does not exist
    - WIKI_GOV_ALREADY_EXECUTED: Governance proposal already executed
    - WIKI_GOV_NOT_ENOUGH_VOTES: Not enough votes to execute
    - WIKI_GOV_EXPIRED: Governance proposal has expired
    """

    # =========================================================================
    # Types
    # =========================================================================

    version_type: type = sp.record(
        cid=sp.string,
        editor=sp.address,
        proposer=sp.option[sp.address],
        ts=sp.timestamp,
        version=sp.nat,
    ).layout(("cid", ("editor", ("proposer", ("ts", "version")))))

    # Versions are keyed by the integer page id.
    version_key_type: type = sp.record(
        page_id=sp.nat,
        version=sp.nat,
    )

    page_type: type = sp.record(
        current_cid=sp.string,
        hidden=sp.bool,
        version_count=sp.nat,
    ).layout(("current_cid", ("hidden", "version_count")))

    # Entrypoint parameter types
    update_page_params_type: type = sp.record(
        page_id=sp.nat,
        cid=sp.string,
    ).layout(("page_id", "cid"))

    set_page_hidden_params_type: type = sp.record(
        page_id=sp.nat,
        hidden=sp.bool,
    ).layout(("page_id", "hidden"))

    # Community proposal types (token holders propose page edits or new pages)
    # Status: 0 = pending, 1 = approved, 2 = rejected
    # target.edit(page_id) -> proposes editing an existing page
    # target.new_page()    -> proposes creating a brand new page (the id is
    #                         assigned once the proposal is approved)
    proposal_target_type: type = sp.variant(
        edit=sp.nat,
        new_page=sp.unit,
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
        page_id=sp.nat,
        proposed_cid=sp.string,
    ).layout(("page_id", "proposed_cid"))

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
        set_propose_page_fee=sp.mutez,
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

    class Wiki(sp.Contract):
        def __init__(
            self,
            metadata,
            moderator_address,
            multisig_address,
            token_address,
            token_id,
            fee_recipient,
            propose_edit_fee,
            propose_page_fee,
            pages,
            versions,
            page_count,
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
            self.data.propose_page_fee = sp.cast(propose_page_fee, sp.mutez)

            # Page storage. Pages are keyed by an auto-incrementing integer id
            # (0..page_count-1, never deleted, so the id also enumerates pages).
            # Seeded at origination from the previous contract's pages/versions
            # (pass empty big_maps and page_count 0 for a fresh deployment).
            self.data.pages = sp.cast(pages, sp.big_map[sp.nat, page_type])
            self.data.versions = sp.cast(
                versions, sp.big_map[version_key_type, version_type]
            )
            self.data.page_count = sp.cast(page_count, sp.nat)

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
            assert not self.data.paused, "WIKI_PAUSED"

        @sp.private(with_storage="read-only")
        def _check_no_tez_transfer(self):
            assert sp.amount == sp.tez(0), "WIKI_TEZ_TRANSFER"

        @sp.private(with_storage="read-only")
        def _check_is_multisig_user(self):
            """Checks that the sender is a multisig user."""
            is_user = sp.view(
                "is_user",
                self.data.multisig_address,
                sp.sender,
                sp.bool,
            ).unwrap_some(error="WIKI_MULTISIG_VIEW_FAILED")
            assert is_user, "WIKI_NOT_AUTHORIZED"

        @sp.private(with_storage="read-only")
        def _check_is_moderator_or_multisig(self):
            """Checks that the sender is a moderator or multisig user.

            The multisig view is checked first so that a misconfigured
            moderator_address cannot lock multisig users out of the
            moderation entrypoints.
            """
            authorized = sp.view(
                "is_user",
                self.data.multisig_address,
                sp.sender,
                sp.bool,
            ).unwrap_some(error="WIKI_MULTISIG_VIEW_FAILED")

            if not authorized:
                authorized = sp.view(
                    "is_moderator",
                    self.data.moderator_address,
                    sp.sender,
                    sp.bool,
                ).unwrap_some(error="WIKI_MODERATOR_VIEW_FAILED")

            assert authorized, "WIKI_NOT_AUTHORIZED"

        @sp.private(with_storage="read-only")
        def _get_minimum_votes(self):
            return sp.view(
                "get_minimum_votes",
                self.data.multisig_address,
                (),
                sp.nat,
            ).unwrap_some(error="WIKI_GET_MIN_VOTES_FAILED")

        @sp.private(with_storage="read-only")
        def _check_not_expired(self, timestamp):
            expiration_days = sp.view(
                "get_expiration_time",
                self.data.multisig_address,
                (),
                sp.nat,
            ).unwrap_some(error="WIKI_GET_EXPIRATION_FAILED")

            expiration_seconds = sp.to_int(expiration_days * 86400)
            expiration_time = sp.add_seconds(timestamp, expiration_seconds)
            assert not (sp.now > expiration_time), "WIKI_GOV_EXPIRED"

        @sp.private(with_storage="read-only")
        def _check_has_tokens(self):
            """Checks that the sender holds Teia tokens (balance > 0)."""
            balance = sp.view(
                "get_balance",
                self.data.token_address,
                sp.record(owner=sp.sender, token_id=self.data.token_id),
                sp.nat,
            ).unwrap_some(error="WIKI_TOKEN_VIEW_FAILED")
            assert balance > 0, "WIKI_NO_TOKENS"

        @sp.private(with_storage="read-only", with_operations=True)
        def _send_fee(self, fee):
            """Forwards the fee to fee_recipient (only when greater than 0)."""
            if fee > sp.mutez(0):
                sp.send(self.data.fee_recipient, fee)

        # =====================================================================
        # Page Entrypoints
        # =====================================================================

        @sp.entrypoint
        def create_page(self, cid):
            """Register a new page with its initial CID.

            Moderators and multisig users can create pages. The page is
            assigned the next integer id. The page name/title lives off-chain
            in the CID content.
            """
            sp.cast(cid, sp.string)
            self._check_not_paused()
            self._check_no_tez_transfer()
            self._check_is_moderator_or_multisig()

            assert sp.len(cid) > 0, "WIKI_EMPTY_CID"

            page_id = self.data.page_count

            self.data.pages[page_id] = sp.record(
                current_cid=cid,
                hidden=False,
                version_count=sp.nat(1),
            )

            self.data.versions[
                sp.record(page_id=page_id, version=sp.nat(1))
            ] = sp.record(
                cid=cid,
                editor=sp.sender,
                proposer=sp.cast(None, sp.option[sp.address]),
                ts=sp.now,
                version=sp.nat(1),
            )

            self.data.page_count += 1

            sp.emit(
                sp.record(
                    page_id=page_id,
                    cid=cid,
                    hidden=False,
                    editor=sp.sender,
                    timestamp=sp.now,
                ),
                tag="page_created",
            )

        @sp.entrypoint
        def update_page(self, params):
            """Update the current CID for an existing page.

            Only moderators and multisig users can update pages directly.
            Pages are addressed by their integer id.
            """
            sp.cast(params, update_page_params_type)
            self._check_not_paused()
            self._check_no_tez_transfer()
            self._check_is_moderator_or_multisig()

            assert sp.len(params.cid) > 0, "WIKI_EMPTY_CID"
            assert params.page_id in self.data.pages, "WIKI_PAGE_NOT_FOUND"

            page = self.data.pages[params.page_id]
            new_version = page.version_count + 1

            self.data.versions[
                sp.record(page_id=params.page_id, version=new_version)
            ] = sp.record(
                cid=params.cid,
                editor=sp.sender,
                proposer=sp.cast(None, sp.option[sp.address]),
                ts=sp.now,
                version=new_version,
            )

            self.data.pages[params.page_id] = sp.record(
                current_cid=params.cid,
                hidden=page.hidden,
                version_count=new_version,
            )

            sp.emit(
                sp.record(
                    page_id=params.page_id,
                    cid=params.cid,
                    hidden=page.hidden,
                    version=new_version,
                    editor=sp.sender,
                    proposer=sp.cast(None, sp.option[sp.address]),
                    timestamp=sp.now,
                ),
                tag="page_updated",
            )

        @sp.entrypoint
        def set_page_hidden(self, params):
            """Set the hidden flag on a page.

            Only moderators and multisig users can hide/unhide pages.
            Pages are addressed by their integer id.
            """
            sp.cast(params, set_page_hidden_params_type)
            self._check_not_paused()
            self._check_no_tez_transfer()
            self._check_is_moderator_or_multisig()

            assert params.page_id in self.data.pages, "WIKI_PAGE_NOT_FOUND"

            page = self.data.pages[params.page_id]
            self.data.pages[params.page_id] = sp.record(
                current_cid=page.current_cid,
                hidden=params.hidden,
                version_count=page.version_count,
            )

            sp.emit(
                sp.record(
                    page_id=params.page_id,
                    hidden=params.hidden,
                    editor=sp.sender,
                    timestamp=sp.now,
                ),
                tag="page_hidden_updated",
            )

        # =====================================================================
        # Community Proposal Entrypoints
        # =====================================================================

        @sp.entrypoint
        def create_proposal(self, params):
            """Submit a draft CID to edit an existing page.

            Caller must hold Teia tokens and attach exactly propose_edit_fee.
            The page is addressed by its integer id.
            """
            sp.cast(params, create_proposal_params_type)
            self._check_not_paused()
            assert sp.amount == self.data.propose_edit_fee, "WIKI_INCORRECT_FEE"
            self._check_has_tokens()

            assert sp.len(params.proposed_cid) > 0, "WIKI_EMPTY_CID"
            assert params.page_id in self.data.pages, "WIKI_PAGE_NOT_FOUND"

            self._send_fee(sp.amount)

            proposal_id = self.data.proposal_counter
            self.data.proposals[proposal_id] = sp.record(
                target=sp.variant.edit(params.page_id),
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
                    page_id=sp.Some(params.page_id),
                    proposed_cid=params.proposed_cid,
                    proposer=sp.sender,
                    is_new_page=False,
                    timestamp=sp.now,
                ),
                tag="proposal_created",
            )

        @sp.entrypoint
        def prop_new_page(self, cid):
            """Propose the creation of a brand new page.

            Caller must hold Teia tokens and attach exactly propose_page_fee.
            The page is only created (and assigned an id) once a
            moderator/multisig user approves the proposal.
            """
            sp.cast(cid, sp.string)
            self._check_not_paused()
            assert sp.amount == self.data.propose_page_fee, "WIKI_INCORRECT_FEE"
            self._check_has_tokens()

            assert sp.len(cid) > 0, "WIKI_EMPTY_CID"

            self._send_fee(sp.amount)

            proposal_id = self.data.proposal_counter
            self.data.proposals[proposal_id] = sp.record(
                target=sp.variant.new_page(()),
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
                    page_id=sp.cast(None, sp.option[sp.nat]),
                    proposed_cid=cid,
                    proposer=sp.sender,
                    is_new_page=True,
                    timestamp=sp.now,
                ),
                tag="proposal_created",
            )

        @sp.entrypoint
        def approve_proposal(self, proposal_id):
            """Approve a pending proposal and apply it to the wiki.

            Only moderators or multisig users can approve. Sets status to 1
            (approved). For an edit proposal this appends a new version to the
            existing page; for a new-page proposal this creates the page and
            assigns it the next integer id.
            """
            sp.cast(proposal_id, sp.nat)
            self._check_not_paused()
            self._check_no_tez_transfer()
            self._check_is_moderator_or_multisig()

            assert proposal_id in self.data.proposals, "WIKI_NO_PROPOSAL"

            proposal = self.data.proposals[proposal_id]
            assert proposal.status == 0, "WIKI_ALREADY_RESOLVED"

            proposal.status = sp.nat(1)
            proposal.resolved_by = sp.Some(sp.sender)
            proposal.resolved_at = sp.Some(sp.now)
            self.data.proposals[proposal_id] = proposal

            if proposal.target.is_variant.new_page():
                # Create the proposed page with a fresh integer id.
                page_id = self.data.page_count

                self.data.pages[page_id] = sp.record(
                    current_cid=proposal.proposed_cid,
                    hidden=False,
                    version_count=sp.nat(1),
                )

                self.data.versions[
                    sp.record(page_id=page_id, version=sp.nat(1))
                ] = sp.record(
                    cid=proposal.proposed_cid,
                    editor=sp.sender,
                    proposer=sp.Some(proposal.proposer),
                    ts=sp.now,
                    version=sp.nat(1),
                )

                self.data.page_count += 1

                sp.emit(
                    sp.record(
                        page_id=page_id,
                        cid=proposal.proposed_cid,
                        hidden=False,
                        editor=sp.sender,
                        timestamp=sp.now,
                    ),
                    tag="page_created",
                )

                sp.emit(
                    sp.record(
                        proposal_id=proposal_id,
                        page_id=page_id,
                        proposed_cid=proposal.proposed_cid,
                        is_new_page=True,
                        approved_by=sp.sender,
                        timestamp=sp.now,
                    ),
                    tag="proposal_approved",
                )
            else:
                # Append a new version to the existing page.
                page_id = proposal.target.unwrap.edit()
                assert page_id in self.data.pages, "WIKI_PAGE_NOT_FOUND"

                page = self.data.pages[page_id]
                new_version = page.version_count + 1

                self.data.versions[
                    sp.record(page_id=page_id, version=new_version)
                ] = sp.record(
                    cid=proposal.proposed_cid,
                    editor=sp.sender,
                    proposer=sp.Some(proposal.proposer),
                    ts=sp.now,
                    version=new_version,
                )

                self.data.pages[page_id] = sp.record(
                    current_cid=proposal.proposed_cid,
                    hidden=page.hidden,
                    version_count=new_version,
                )

                sp.emit(
                    sp.record(
                        proposal_id=proposal_id,
                        page_id=page_id,
                        proposed_cid=proposal.proposed_cid,
                        is_new_page=False,
                        approved_by=sp.sender,
                        timestamp=sp.now,
                    ),
                    tag="proposal_approved",
                )

        @sp.entrypoint
        def reject_proposal(self, proposal_id):
            """Reject a pending proposal.

            Only moderators or multisig users can reject.
            Sets status to 2 (rejected). The proposal data remains on-chain
            for transparency.
            """
            sp.cast(proposal_id, sp.nat)
            self._check_not_paused()
            self._check_no_tez_transfer()
            self._check_is_moderator_or_multisig()

            assert proposal_id in self.data.proposals, "WIKI_NO_PROPOSAL"

            proposal = self.data.proposals[proposal_id]
            assert proposal.status == 0, "WIKI_ALREADY_RESOLVED"

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
        # Governance Entrypoints
        # =====================================================================

        @sp.entrypoint
        def submit_governance_proposal(self, action):
            """Submit a new governance proposal for config changes."""
            sp.cast(action, gov_action_type)
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

            self._check_is_multisig_user()
            assert vote.proposal_id in self.data.gov_proposals, "WIKI_NO_GOV_PROPOSAL"

            proposal = self.data.gov_proposals[vote.proposal_id]
            assert not proposal.executed, "WIKI_GOV_ALREADY_EXECUTED"
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

            self._check_is_multisig_user()
            assert proposal_id in self.data.gov_proposals, "WIKI_NO_GOV_PROPOSAL"

            proposal = self.data.gov_proposals[proposal_id]
            assert not proposal.executed, "WIKI_GOV_ALREADY_EXECUTED"
            minimum_votes = self._get_minimum_votes()
            assert proposal.positive_votes >= minimum_votes, "WIKI_GOV_NOT_ENOUGH_VOTES"
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

            if proposal.action.is_variant.set_propose_page_fee():
                self.data.propose_page_fee = (
                    proposal.action.unwrap.set_propose_page_fee()
                )

            if proposal.action.is_variant.update_metadata():
                entry = proposal.action.unwrap.update_metadata()
                self.data.metadata[entry.key] = entry.value

        # =====================================================================
        # Views
        # =====================================================================

        @sp.onchain_view()
        def get_page(self, page_id):
            """Returns the page record for a given page id."""
            sp.cast(page_id, sp.nat)
            assert page_id in self.data.pages, "WIKI_PAGE_NOT_FOUND"
            return self.data.pages[page_id]

        @sp.onchain_view()
        def get_version(self, key):
            """Returns a specific version of a page."""
            sp.cast(key, version_key_type)
            assert key in self.data.versions, "WIKI_VERSION_NOT_FOUND"
            return self.data.versions[key]

        @sp.onchain_view()
        def get_page_count(self):
            """Returns the total number of pages."""
            return self.data.page_count

        @sp.onchain_view()
        def get_proposal(self, proposal_id):
            """Returns community proposal record by ID."""
            sp.cast(proposal_id, sp.nat)
            assert proposal_id in self.data.proposals, "WIKI_NO_PROPOSAL"
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
                propose_page_fee=self.data.propose_page_fee,
                fee_recipient=self.data.fee_recipient,
            )

        @sp.onchain_view()
        def get_governance_proposal(self, proposal_id):
            """Get governance proposal by ID."""
            sp.cast(proposal_id, sp.nat)
            assert proposal_id in self.data.gov_proposals, "WIKI_NO_GOV_PROPOSAL"
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
    scenario = sp.test_scenario("deploy_wiki", wiki_module)
    scenario.h1("Teia Wiki Contract — Deployment")

    # =========================================================================
    # DEPLOYMENT VALUES (Mainnet)
    # =========================================================================
    # Teia Core Team multisig
    MULTISIG_ADDRESS = sp.address("KT1J9FYz29RBQi1oGLw8uXyACrzXzV1dHuvb")
    # Teia Moderator contract
    MODERATOR_ADDRESS = sp.address("KT1RbVvb4eZh618krF49abrpEmAdb3zK92v6")
    # Teia DAO token (NOT the distributor KT1NrfV...!)
    TOKEN_ADDRESS = sp.address(
        "KT1QrtA753MSv8VGxkDrKKyJniG5JtuHHbtV"
    )
    TOKEN_ID = sp.nat(0)
    # Per-action fees start at 0 (free); the multisig can raise them later.
    FEE_RECIPIENT = sp.address("KT1J9FYz29RBQi1oGLw8uXyACrzXzV1dHuvb")
    PROPOSE_EDIT_FEE = sp.mutez(0)
    PROPOSE_PAGE_FEE = sp.mutez(0)
    # =========================================================================

    # =========================================================================
    # MIGRATED PAGES (seeded into initial storage at origination)
    # =========================================================================
    # Copied verbatim from the previous slug-based wiki contract
    # KT1BpPYWmzJiLjcBTYod5yHudkZ8ehSw2b2Q. The integer page_id mirrors that
    # contract's page_slugs index (creation order), and the full version
    # history is preserved with original editor/proposer/timestamp.
    #   0 test-page                          5 z-test
    #   1 edit-test-page                      6 teia-events
    #   2 hide-test-page                      7 tezos-foundation-grant-events
    #   3 teia-smart-contract-fees-list-test
    #   4 alphabetical-test (hidden)
    # Page names/titles now live off-chain in the CID content; the UI keeps the
    # slug -> page_id mapping above.
    SEED_PAGES = sp.big_map(
        {
            0: sp.record(  # test-page
                current_cid="QmdCMH4o7ypRSqJUsKxfwdKMWzwU1PdHWUDGU9Vs5kE1rM",
                hidden=False,
                version_count=sp.nat(2),
            ),
            1: sp.record(  # edit-test-page
                current_cid="QmQCiAcytcSCXMxzLC5FyAttFYMCLycTJXvcpiKNazUoWX",
                hidden=False,
                version_count=sp.nat(5),
            ),
            2: sp.record(  # hide-test-page
                current_cid="QmeND5NzwoQJAtcJo1KydAFcU1HtbQEyS9gZbaomooUggD",
                hidden=False,
                version_count=sp.nat(2),
            ),
            3: sp.record(  # teia-smart-contract-fees-list-test
                current_cid="QmdrU1mD2MVvN34oTgTAbD76Pi936C439SDFcTuUtWmRnS",
                hidden=False,
                version_count=sp.nat(2),
            ),
            4: sp.record(  # alphabetical-test
                current_cid="QmTQuXoB5FNiFcCaGpzL8utM2JRz7M8GSVs5LnUDzKfb2R",
                hidden=True,
                version_count=sp.nat(1),
            ),
            5: sp.record(  # z-test
                current_cid="QmQdxBVm6ygPXS26YJGxpZWoaEpT5rv4NtYEaRC2r5WNwR",
                hidden=False,
                version_count=sp.nat(4),
            ),
            6: sp.record(  # teia-events
                current_cid="QmQ8sCNL2Hu287XBQnC2yigxdCTixW36iDfjEnQrZMHHD9",
                hidden=False,
                version_count=sp.nat(1),
            ),
            7: sp.record(  # tezos-foundation-grant-events
                current_cid="QmUpFF9jkerWKRtsYYRTCu1kKZgB1AjksSfdLVv3RszFB8",
                hidden=False,
                version_count=sp.nat(1),
            ),
        }
    )

    SEED_VERSIONS = sp.big_map(
        {
            sp.record(page_id=sp.nat(0), version=sp.nat(1)): sp.record(
                cid="QmVDFdpqLLN3YzwajJehE7edJh6WVksPV6oeNu4vxcfxig",
                editor=sp.address("tz1ZVzMVj6EjRoDNFMCguG7nGdqmD7aau9kS"),
                proposer=sp.Some(sp.address("tz1ZhteLTqobRVCYsPj44oFfom5BJ2SdGxeE")),
                ts=sp.timestamp(1781534341),
                version=sp.nat(1),
            ),  # test-page v1
            sp.record(page_id=sp.nat(0), version=sp.nat(2)): sp.record(
                cid="QmdCMH4o7ypRSqJUsKxfwdKMWzwU1PdHWUDGU9Vs5kE1rM",
                editor=sp.address("tz1ZVzMVj6EjRoDNFMCguG7nGdqmD7aau9kS"),
                proposer=sp.cast(None, sp.option[sp.address]),
                ts=sp.timestamp(1782222733),
                version=sp.nat(2),
            ),  # test-page v2
            sp.record(page_id=sp.nat(1), version=sp.nat(1)): sp.record(
                cid="QmUDV9VBEuRrDKywihiKyoR2aBGjHBbF4kekhFqvSjdXim",
                editor=sp.address("tz1ZVzMVj6EjRoDNFMCguG7nGdqmD7aau9kS"),
                proposer=sp.cast(None, sp.option[sp.address]),
                ts=sp.timestamp(1781534587),
                version=sp.nat(1),
            ),  # edit-test-page v1
            sp.record(page_id=sp.nat(1), version=sp.nat(2)): sp.record(
                cid="QmeJfgTagWtcYyjZHdzDzzNmYnTfnNZp4WxHZSPi2rqnwo",
                editor=sp.address("tz1ZVzMVj6EjRoDNFMCguG7nGdqmD7aau9kS"),
                proposer=sp.cast(None, sp.option[sp.address]),
                ts=sp.timestamp(1781534902),
                version=sp.nat(2),
            ),  # edit-test-page v2
            sp.record(page_id=sp.nat(1), version=sp.nat(3)): sp.record(
                cid="QmTQZ3LX3Zu2zCgdVzZnNxRceNPe4T9YCQUwNZptwMgLMo",
                editor=sp.address("tz1ZVzMVj6EjRoDNFMCguG7nGdqmD7aau9kS"),
                proposer=sp.Some(sp.address("tz1ZhteLTqobRVCYsPj44oFfom5BJ2SdGxeE")),
                ts=sp.timestamp(1782147358),
                version=sp.nat(3),
            ),  # edit-test-page v3
            sp.record(page_id=sp.nat(1), version=sp.nat(4)): sp.record(
                cid="QmZEQY36Cfn95PJvmcYqfBLDB7nVUFCuJw9VEib9dbhReh",
                editor=sp.address("tz1ZVzMVj6EjRoDNFMCguG7nGdqmD7aau9kS"),
                proposer=sp.cast(None, sp.option[sp.address]),
                ts=sp.timestamp(1782147400),
                version=sp.nat(4),
            ),  # edit-test-page v4
            sp.record(page_id=sp.nat(1), version=sp.nat(5)): sp.record(
                cid="QmQCiAcytcSCXMxzLC5FyAttFYMCLycTJXvcpiKNazUoWX",
                editor=sp.address("tz1ZVzMVj6EjRoDNFMCguG7nGdqmD7aau9kS"),
                proposer=sp.cast(None, sp.option[sp.address]),
                ts=sp.timestamp(1782221995),
                version=sp.nat(5),
            ),  # edit-test-page v5
            sp.record(page_id=sp.nat(2), version=sp.nat(1)): sp.record(
                cid="QmVxcPsNJKzRTCQ8NLHWtyEfm8u2YdbQUgmhQVje7V1AfR",
                editor=sp.address("tz1ZVzMVj6EjRoDNFMCguG7nGdqmD7aau9kS"),
                proposer=sp.cast(None, sp.option[sp.address]),
                ts=sp.timestamp(1781534734),
                version=sp.nat(1),
            ),  # hide-test-page v1
            sp.record(page_id=sp.nat(2), version=sp.nat(2)): sp.record(
                cid="QmeND5NzwoQJAtcJo1KydAFcU1HtbQEyS9gZbaomooUggD",
                editor=sp.address("tz1ZVzMVj6EjRoDNFMCguG7nGdqmD7aau9kS"),
                proposer=sp.cast(None, sp.option[sp.address]),
                ts=sp.timestamp(1782223063),
                version=sp.nat(2),
            ),  # hide-test-page v2
            sp.record(page_id=sp.nat(3), version=sp.nat(1)): sp.record(
                cid="QmPhUnVHu9i3F2krkds2mBmStFY39v3hnYagFSLC8iecqz",
                editor=sp.address("tz1ZVzMVj6EjRoDNFMCguG7nGdqmD7aau9kS"),
                proposer=sp.cast(None, sp.option[sp.address]),
                ts=sp.timestamp(1781535034),
                version=sp.nat(1),
            ),  # teia-smart-contract-fees-list-test v1
            sp.record(page_id=sp.nat(3), version=sp.nat(2)): sp.record(
                cid="QmdrU1mD2MVvN34oTgTAbD76Pi936C439SDFcTuUtWmRnS",
                editor=sp.address("tz1ZVzMVj6EjRoDNFMCguG7nGdqmD7aau9kS"),
                proposer=sp.cast(None, sp.option[sp.address]),
                ts=sp.timestamp(1782223297),
                version=sp.nat(2),
            ),  # teia-smart-contract-fees-list-test v2
            sp.record(page_id=sp.nat(4), version=sp.nat(1)): sp.record(
                cid="QmTQuXoB5FNiFcCaGpzL8utM2JRz7M8GSVs5LnUDzKfb2R",
                editor=sp.address("tz1ZVzMVj6EjRoDNFMCguG7nGdqmD7aau9kS"),
                proposer=sp.cast(None, sp.option[sp.address]),
                ts=sp.timestamp(1781535106),
                version=sp.nat(1),
            ),  # alphabetical-test v1
            sp.record(page_id=sp.nat(5), version=sp.nat(1)): sp.record(
                cid="Qmd8n9NcQVUeMb3DGKTyGGgdBHQG9i7Bs4j8N61a1DR8V2",
                editor=sp.address("tz1ZVzMVj6EjRoDNFMCguG7nGdqmD7aau9kS"),
                proposer=sp.cast(None, sp.option[sp.address]),
                ts=sp.timestamp(1781535148),
                version=sp.nat(1),
            ),  # z-test v1
            sp.record(page_id=sp.nat(5), version=sp.nat(2)): sp.record(
                cid="Qmed3kcUm9m4kyhL9mNy4eRpA2SueDhDtyLf44BMrY6ovx",
                editor=sp.address("tz1ZVzMVj6EjRoDNFMCguG7nGdqmD7aau9kS"),
                proposer=sp.Some(sp.address("tz1ZhteLTqobRVCYsPj44oFfom5BJ2SdGxeE")),
                ts=sp.timestamp(1782147463),
                version=sp.nat(2),
            ),  # z-test v2
            sp.record(page_id=sp.nat(5), version=sp.nat(3)): sp.record(
                cid="Qmf12ozyd94WYVqXNWpceRhGjebUtBXW4FNWuKBU1nLsUN",
                editor=sp.address("tz1ZVzMVj6EjRoDNFMCguG7nGdqmD7aau9kS"),
                proposer=sp.cast(None, sp.option[sp.address]),
                ts=sp.timestamp(1782147499),
                version=sp.nat(3),
            ),  # z-test v3
            sp.record(page_id=sp.nat(5), version=sp.nat(4)): sp.record(
                cid="QmQdxBVm6ygPXS26YJGxpZWoaEpT5rv4NtYEaRC2r5WNwR",
                editor=sp.address("tz1ZVzMVj6EjRoDNFMCguG7nGdqmD7aau9kS"),
                proposer=sp.cast(None, sp.option[sp.address]),
                ts=sp.timestamp(1782223561),
                version=sp.nat(4),
            ),  # z-test v4
            sp.record(page_id=sp.nat(6), version=sp.nat(1)): sp.record(
                cid="QmQ8sCNL2Hu287XBQnC2yigxdCTixW36iDfjEnQrZMHHD9",
                editor=sp.address("tz1ZVzMVj6EjRoDNFMCguG7nGdqmD7aau9kS"),
                proposer=sp.cast(None, sp.option[sp.address]),
                ts=sp.timestamp(1782169357),
                version=sp.nat(1),
            ),  # teia-events v1
            sp.record(page_id=sp.nat(7), version=sp.nat(1)): sp.record(
                cid="QmUpFF9jkerWKRtsYYRTCu1kKZgB1AjksSfdLVv3RszFB8",
                editor=sp.address("tz1ZVzMVj6EjRoDNFMCguG7nGdqmD7aau9kS"),
                proposer=sp.cast(None, sp.option[sp.address]),
                ts=sp.timestamp(1782312193),
                version=sp.nat(1),
            ),  # tezos-foundation-grant-events v1
        }
    )

    SEED_PAGE_COUNT = sp.nat(8)

    contract_metadata = sp.big_map(
        {
            "": sp.scenario_utils.bytes_of_string(
                "ipfs://QmYBKZjoqvi3qV8ZLaQpRPE5AacQLRoULaCnW613g9hzMG"
            ),
        }
    )

    contract = wiki_module.Wiki(
        metadata=contract_metadata,
        moderator_address=MODERATOR_ADDRESS,
        multisig_address=MULTISIG_ADDRESS,
        token_address=TOKEN_ADDRESS,
        token_id=TOKEN_ID,
        fee_recipient=FEE_RECIPIENT,
        propose_edit_fee=PROPOSE_EDIT_FEE,
        propose_page_fee=PROPOSE_PAGE_FEE,
        pages=SEED_PAGES,
        versions=SEED_VERSIONS,
        page_count=SEED_PAGE_COUNT,
        gov_counter=sp.nat(0),
    )
    scenario += contract

    scenario.h2("Contract deployed with:")
    scenario.show(MULTISIG_ADDRESS)
    scenario.show(MODERATOR_ADDRESS)
    scenario.show(TOKEN_ADDRESS)
