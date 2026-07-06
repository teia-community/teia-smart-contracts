import smartpy as sp


@sp.module
def token_comments_module():
    """Teia Token Comments Contract.

    Comments on Teia FA2 tokens, gated by ownership of the token being
    commented on. The token gate is dynamic — each post specifies the
    (fa2_address, token_id) it targets, and the caller must hold that
    token. Multisig-governed moderation (hide/unhide) and parameter changes.

    Error codes:

    Comment:
    - CONTRACT_PAUSED: Contract is globally paused
    - TEZ_TRANSFER: Unexpected tez transfer
    - INCORRECT_FEE: sp.amount does not match the required fee for the action
      (post_fee for post_comment, edit_fee for edit_comment, hide_fee for
      set_own_comment_hidden)
    - EMPTY_CONTENT: Comment content is empty
    - CONTENT_TOO_LARGE: Comment content exceeds 32 KiB
    - PARENT_NOT_FOUND: Reply target comment does not exist
    - PARENT_WRONG_TOKEN: Reply target is on a different token
      (fa2_address or token_id mismatch)
    - PARENT_HIDDEN: Reply target has been hidden
    - COMMENT_NOT_FOUND: Comment ID does not exist
    - NOT_AUTHORIZED: Caller cannot perform this action
    - USER_BANNED: Caller is on the ban list (blocks post_comment and edit_comment)
    - VERSION_NOT_FOUND: Requested historical version of a comment does not exist

    Token gate / FA2:
    - PENDING_POST_EXISTS: Another post_comment is mid-callback
    - NO_PENDING_POST: balance_callback called with no pending comment
    - INVALID_CALLBACK_SENDER: balance_callback sender is not the FA2
      that post_comment targeted
    - EMPTY_BALANCE_RESPONSE: FA2 returned no balance entries
    - NOT_TOKEN_HOLDER: Sender does not hold the targeted token
    - SELF_CALLBACK_ERROR: Could not resolve self balance_callback entrypoint
    - INVALID_FA2: Targeted FA2 contract has no balance_of entrypoint

    Governance (multisig-gated):
    - TC_VIEW_FAILED: is_user view on multisig failed
    - TC_NOT_MULTISIG_USER: Caller is not a multisig user
    - TC_GET_MIN_VOTES_FAILED: get_minimum_votes view failed
    - TC_GET_EXPIRATION_FAILED: get_expiration_time view failed
    - TC_PROPOSAL_EXPIRED: Proposal past expiration window
    - TC_NO_PROPOSAL: Proposal ID does not exist
    - TC_ALREADY_EXECUTED: Proposal already executed
    - TC_NOT_ENOUGH_VOTES: Positive votes below minimum
    """

    # ===========================================================================
    # Types
    # ===========================================================================

    # --- FA2 Types (TZIP-12 standard) ---

    balance_of_request_type: type = sp.record(
        owner=sp.address,
        token_id=sp.nat,
    ).layout(("owner", "token_id"))

    balance_of_response_type: type = sp.record(
        request=balance_of_request_type,
        balance=sp.nat,
    ).layout(("request", "balance"))

    balance_of_params_type: type = sp.record(
        callback=sp.contract[sp.list[balance_of_response_type]],
        requests=sp.list[balance_of_request_type],
    ).layout(("requests", "callback"))

    # --- Comment ---

    comment_type: type = sp.record(
        fa2_address=sp.address,
        token_id=sp.nat,
        sender=sp.address,
        content=sp.bytes,
        parent_id=sp.option[sp.nat],
        hidden=sp.bool,
        timestamp=sp.timestamp,
        version=sp.nat,
    )

    # --- Comment History ---
    # Snapshot of a prior version of a comment.
    # The live version lives in `comments`; `comment_history[(comment_id, n)]`
    # holds the n-th archived version. Versions start at 1; archived indices
    # 1..comment.version-1 are populated (empty for never-edited comments at
    # version=1).

    history_entry_type: type = sp.record(
        fa2_address=sp.address,
        token_id=sp.nat,
        sender=sp.address,
        content=sp.bytes,
        parent_id=sp.option[sp.nat],
        timestamp=sp.timestamp,
    )

    history_key_type: type = sp.pair[sp.nat, sp.nat]

    # --- Pending Post (for balance_of callback) ---

    pending_comment_type: type = sp.record(
        fa2_address=sp.address,
        token_id=sp.nat,
        sender=sp.address,
        content=sp.bytes,
        parent_id=sp.option[sp.nat],
        fee=sp.mutez,
    )

    # --- Entrypoint Params ---

    post_comment_params_type: type = sp.record(
        fa2_address=sp.address,
        token_id=sp.nat,
        content=sp.bytes,
        parent_id=sp.option[sp.nat],
    )

    edit_comment_params_type: type = sp.record(
        comment_id=sp.nat,
        content=sp.bytes,
    )

    set_own_comment_hidden_params_type: type = sp.record(
        comment_id=sp.nat,
        hidden=sp.bool,
    )

    # --- Storage Types ---

    comments_map_type: type = sp.big_map[sp.nat, comment_type]
    metadata_type: type = sp.big_map[sp.string, sp.bytes]

    # --- Governance Types ---

    metadata_entry_type: type = sp.record(
        key=sp.string,
        value=sp.bytes,
    ).layout(("key", "value"))

    user_banned_action_type: type = sp.record(
        address=sp.address,
        banned=sp.bool,
    ).layout(("address", "banned"))

    proposal_action_type: type = sp.variant(
        set_pause=sp.bool,
        set_post_fee=sp.mutez,
        set_edit_fee=sp.mutez,
        set_hide_fee=sp.mutez,
        set_fee_recipient=sp.address,
        update_multisig_address=sp.address,
        update_metadata=metadata_entry_type,
        set_user_banned=user_banned_action_type,
    )

    moderate_comment_hidden_params_type: type = sp.record(
        comment_id=sp.nat,
        hidden=sp.bool,
    )

    proposal_type: type = sp.record(
        action=proposal_action_type,
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

    vote_key_type: type = sp.pair[sp.nat, sp.address]

    vote_params_type: type = sp.record(
        proposal_id=sp.nat,
        approval=sp.bool,
    ).layout(("proposal_id", "approval"))

    # ===========================================================================
    # Contract
    # ===========================================================================

    class TokenComments(sp.Contract):
        """Teia Token Comments — FA2 holders can comment on the specific
        token they hold. Multisig governs moderation and parameter changes."""

        def __init__(self, multisig_address, fee_recipient, post_fee, edit_fee, hide_fee, metadata, counter):
            self.data.multisig_address = sp.cast(multisig_address, sp.address)
            self.data.metadata = sp.cast(metadata, metadata_type)
            self.data.paused = False
            self.data.comments = sp.cast(sp.big_map(), comments_map_type)
            self.data.comment_history = sp.cast(sp.big_map(), sp.big_map[history_key_type, history_entry_type])
            self.data.banned = sp.cast(sp.big_map(), sp.big_map[sp.address, sp.unit])
            self.data.pending_comment = sp.cast(None, sp.option[pending_comment_type])
            self.data.comment_id_counter = sp.nat(1)
            self.data.post_fee = sp.cast(post_fee, sp.mutez)
            self.data.edit_fee = sp.cast(edit_fee, sp.mutez)
            self.data.hide_fee = sp.cast(hide_fee, sp.mutez)
            self.data.fee_recipient = sp.cast(fee_recipient, sp.address)
            self.data.proposals = sp.cast(sp.big_map(), sp.big_map[sp.nat, proposal_type])
            self.data.votes = sp.cast(sp.big_map(), sp.big_map[vote_key_type, sp.bool])
            self.data.counter = sp.cast(counter, sp.nat)

        # =======================================================================
        # Private Helpers
        # =======================================================================

        @sp.private(with_storage="read-only")
        def _check_not_paused(self):
            assert not self.data.paused, "CONTRACT_PAUSED"

        @sp.private(with_storage="read-only")
        def _check_no_tez_transfer(self):
            assert sp.amount == sp.tez(0), "TEZ_TRANSFER"

        @sp.private(with_storage="read-only")
        def _check_not_banned(self):
            assert not (sp.sender in self.data.banned), "USER_BANNED"

        @sp.private(with_storage="read-only")
        def _check_is_user(self):
            is_user = sp.view(
                "is_user",
                self.data.multisig_address,
                sp.sender,
                sp.bool,
            ).unwrap_some(error="TC_VIEW_FAILED")
            assert is_user, "TC_NOT_MULTISIG_USER"

        @sp.private(with_storage="read-only")
        def _get_minimum_votes(self):
            return sp.view(
                "get_minimum_votes",
                self.data.multisig_address,
                (),
                sp.nat,
            ).unwrap_some(error="TC_GET_MIN_VOTES_FAILED")

        @sp.private(with_storage="read-only")
        def _check_not_expired(self, timestamp):
            expiration_days = sp.view(
                "get_expiration_time",
                self.data.multisig_address,
                (),
                sp.nat,
            ).unwrap_some(error="TC_GET_EXPIRATION_FAILED")

            expiration_seconds = sp.to_int(expiration_days * 86400)
            expiration_time = sp.add_seconds(timestamp, expiration_seconds)
            assert not (sp.now > expiration_time), "TC_PROPOSAL_EXPIRED"

        @sp.private(with_storage="read-write", with_operations=True)
        def _send_fee(self, fee):
            """Sends fee to fee_recipient if > 0."""
            if fee > sp.mutez(0):
                sp.send(self.data.fee_recipient, fee)

        # =======================================================================
        # Comment Entrypoints
        # =======================================================================

        @sp.entrypoint
        def post_comment(self, params):
            """Post a comment on a Teia FA2 token. Initiates FA2 balance check
            against the targeted (fa2_address, token_id)."""
            sp.cast(params, post_comment_params_type)
            self._check_not_paused()
            self._check_not_banned()

            assert sp.len(params.content) > 0, "EMPTY_CONTENT"
            assert sp.len(params.content) <= 32768, "CONTENT_TOO_LARGE"
            assert not self.data.pending_comment.is_some(), "PENDING_POST_EXISTS"

            assert sp.amount == self.data.post_fee, "INCORRECT_FEE"

            # Validate parent comment if replying
            if params.parent_id.is_some():
                parent_comment_id = params.parent_id.unwrap_some()
                assert parent_comment_id in self.data.comments, "PARENT_NOT_FOUND"
                parent_comment = self.data.comments[parent_comment_id]
                assert parent_comment.fa2_address == params.fa2_address, "PARENT_WRONG_TOKEN"
                assert parent_comment.token_id == params.token_id, "PARENT_WRONG_TOKEN"
                assert not parent_comment.hidden, "PARENT_HIDDEN"

            self.data.pending_comment = sp.Some(sp.record(
                fa2_address=params.fa2_address,
                token_id=params.token_id,
                sender=sp.sender,
                content=params.content,
                parent_id=params.parent_id,
                fee=sp.amount,
            ))

            callback = sp.contract(
                sp.list[balance_of_response_type],
                sp.self_address,
                entrypoint="balance_callback",
            ).unwrap_some(error="SELF_CALLBACK_ERROR")

            fa2_handle = sp.contract(
                balance_of_params_type,
                params.fa2_address,
                entrypoint="balance_of",
            ).unwrap_some(error="INVALID_FA2")

            sp.transfer(
                sp.record(
                    requests=[sp.record(owner=sp.sender, token_id=params.token_id)],
                    callback=callback,
                ),
                sp.tez(0),
                fa2_handle,
            )

        @sp.entrypoint
        def balance_callback(self, responses):
            """Callback from FA2 balance_of. Writes comment if balance > 0."""
            sp.cast(responses, sp.list[balance_of_response_type])

            pending = self.data.pending_comment.unwrap_some(error="NO_PENDING_POST")

            # Caller must be the FA2 contract that post_comment targeted
            assert sp.sender == pending.fa2_address, "INVALID_CALLBACK_SENDER"

            assert sp.len(responses) > 0, "EMPTY_BALANCE_RESPONSE"
            found_balance = sp.nat(0)
            for response in responses:
                if response.request.owner == pending.sender:
                    if response.request.token_id == pending.token_id:
                        found_balance = response.balance
            assert found_balance > 0, "NOT_TOKEN_HOLDER"

            comment_id = self.data.comment_id_counter
            self.data.comments[comment_id] = sp.record(
                fa2_address=pending.fa2_address,
                token_id=pending.token_id,
                sender=pending.sender,
                content=pending.content,
                parent_id=pending.parent_id,
                hidden=False,
                timestamp=sp.now,
                version=sp.nat(1),
            )

            self.data.comment_id_counter += 1

            self._send_fee(pending.fee)

            # Note: `content` is intentionally NOT emitted in the event
            sp.emit(
                sp.record(
                    fa2_address=pending.fa2_address,
                    token_id=pending.token_id,
                    comment_id=comment_id,
                    sender=pending.sender,
                    parent_id=pending.parent_id,
                    timestamp=sp.now,
                ),
                tag="comment_posted",
            )

            self.data.pending_comment = None

        @sp.entrypoint
        def edit_comment(self, params):
            """Edit a comment. Sender only. Archives the current version into
            comment_history before overwriting content."""
            sp.cast(params, edit_comment_params_type)
            self._check_not_paused()
            self._check_not_banned()

            assert sp.amount == self.data.edit_fee, "INCORRECT_FEE"

            assert params.comment_id in self.data.comments, "COMMENT_NOT_FOUND"
            comment = self.data.comments[params.comment_id]
            assert comment.sender == sp.sender, "NOT_AUTHORIZED"
            assert sp.len(params.content) > 0, "EMPTY_CONTENT"
            assert sp.len(params.content) <= 32768, "CONTENT_TOO_LARGE"

            self.data.comment_history[(params.comment_id, comment.version)] = sp.record(
                fa2_address=comment.fa2_address,
                token_id=comment.token_id,
                sender=comment.sender,
                content=comment.content,
                parent_id=comment.parent_id,
                timestamp=comment.timestamp,
            )

            new_version = comment.version + 1
            self.data.comments[params.comment_id] = sp.record(
                fa2_address=comment.fa2_address,
                token_id=comment.token_id,
                sender=comment.sender,
                content=params.content,
                parent_id=comment.parent_id,
                hidden=comment.hidden,
                timestamp=sp.now,
                version=new_version,
            )

            self._send_fee(sp.amount)

            sp.emit(
                sp.record(
                    fa2_address=comment.fa2_address,
                    token_id=comment.token_id,
                    comment_id=params.comment_id,
                    sender=comment.sender,
                    parent_id=comment.parent_id,
                    timestamp=sp.now,
                    version=new_version,
                ),
                tag="comment_edited",
            )

        @sp.entrypoint
        def set_own_comment_hidden(self, params):
            """Toggle hidden flag on caller's own comment."""
            sp.cast(params, set_own_comment_hidden_params_type)
            self._check_not_paused()

            assert sp.amount == self.data.hide_fee, "INCORRECT_FEE"

            assert params.comment_id in self.data.comments, "COMMENT_NOT_FOUND"
            comment = self.data.comments[params.comment_id]
            assert comment.sender == sp.sender, "NOT_AUTHORIZED"

            self.data.comments[params.comment_id] = sp.record(
                fa2_address=comment.fa2_address,
                token_id=comment.token_id,
                sender=comment.sender,
                content=comment.content,
                parent_id=comment.parent_id,
                hidden=params.hidden,
                timestamp=comment.timestamp,
                version=comment.version,
            )

            self._send_fee(sp.amount)

            sp.emit(
                sp.record(
                    comment_id=params.comment_id,
                    hidden=params.hidden,
                    updated_by=sp.sender,
                ),
                tag="comment_hidden_set",
            )

        @sp.entrypoint
        def moderate_comment_hidden(self, params):
            """Hide or unhide any comment. Any multisig user, no vote required."""
            sp.cast(params, moderate_comment_hidden_params_type)
            self._check_no_tez_transfer()
            self._check_is_user()

            assert params.comment_id in self.data.comments, "COMMENT_NOT_FOUND"
            comment = self.data.comments[params.comment_id]

            self.data.comments[params.comment_id] = sp.record(
                fa2_address=comment.fa2_address,
                token_id=comment.token_id,
                sender=comment.sender,
                content=comment.content,
                parent_id=comment.parent_id,
                hidden=params.hidden,
                timestamp=comment.timestamp,
                version=comment.version,
            )

            sp.emit(
                sp.record(
                    comment_id=params.comment_id,
                    hidden=params.hidden,
                    moderator=sp.sender,
                ),
                tag="comment_moderated",
            )

        # =======================================================================
        # Governance Entrypoints
        # =======================================================================

        @sp.entrypoint
        def submit_proposal(self, action):
            """Submit a new proposal."""
            sp.cast(action, proposal_action_type)
            self._check_no_tez_transfer()
            self._check_is_user()

            self.data.proposals[self.data.counter] = sp.record(
                action=action,
                executed=False,
                issuer=sp.sender,
                timestamp=sp.now,
                positive_votes=sp.nat(0),
                negative_votes=sp.nat(0),
            )
            self.data.counter += 1

        @sp.entrypoint
        def vote_proposal(self, vote):
            """Vote on an existing proposal."""
            sp.cast(vote, vote_params_type)
            self._check_no_tez_transfer()
            self._check_is_user()
            assert vote.proposal_id in self.data.proposals, "TC_NO_PROPOSAL"

            proposal = self.data.proposals[vote.proposal_id]
            assert not proposal.executed, "TC_ALREADY_EXECUTED"
            self._check_not_expired(proposal.timestamp)

            vote_key = (vote.proposal_id, sp.sender)

            if vote_key in self.data.votes:
                if self.data.votes[vote_key]:
                    proposal.positive_votes = sp.as_nat(proposal.positive_votes - 1)
                else:
                    proposal.negative_votes = sp.as_nat(proposal.negative_votes - 1)

            if vote.approval:
                proposal.positive_votes += 1
            else:
                proposal.negative_votes += 1

            self.data.votes[vote_key] = vote.approval
            self.data.proposals[vote.proposal_id] = proposal

        @sp.entrypoint
        def execute_proposal(self, proposal_id):
            """Execute an approved proposal."""
            sp.cast(proposal_id, sp.nat)
            self._check_no_tez_transfer()
            self._check_is_user()
            assert proposal_id in self.data.proposals, "TC_NO_PROPOSAL"

            proposal = self.data.proposals[proposal_id]
            assert not proposal.executed, "TC_ALREADY_EXECUTED"
            minimum_votes = self._get_minimum_votes()
            assert proposal.positive_votes >= minimum_votes, "TC_NOT_ENOUGH_VOTES"
            self._check_not_expired(proposal.timestamp)

            proposal.executed = True
            self.data.proposals[proposal_id] = proposal

            if proposal.action.is_variant.set_pause():
                self.data.paused = proposal.action.unwrap.set_pause()
                sp.emit(
                    sp.record(
                        proposal_id=proposal_id,
                        paused=self.data.paused,
                        updated_by=sp.sender,
                    ),
                    tag="pause_set",
                )

            if proposal.action.is_variant.set_post_fee():
                self.data.post_fee = proposal.action.unwrap.set_post_fee()
                sp.emit(
                    sp.record(
                        proposal_id=proposal_id,
                        post_fee=self.data.post_fee,
                        updated_by=sp.sender,
                    ),
                    tag="post_fee_set",
                )

            if proposal.action.is_variant.set_edit_fee():
                self.data.edit_fee = proposal.action.unwrap.set_edit_fee()
                sp.emit(
                    sp.record(
                        proposal_id=proposal_id,
                        edit_fee=self.data.edit_fee,
                        updated_by=sp.sender,
                    ),
                    tag="edit_fee_set",
                )

            if proposal.action.is_variant.set_hide_fee():
                self.data.hide_fee = proposal.action.unwrap.set_hide_fee()
                sp.emit(
                    sp.record(
                        proposal_id=proposal_id,
                        hide_fee=self.data.hide_fee,
                        updated_by=sp.sender,
                    ),
                    tag="hide_fee_set",
                )

            if proposal.action.is_variant.set_fee_recipient():
                self.data.fee_recipient = proposal.action.unwrap.set_fee_recipient()
                sp.emit(
                    sp.record(
                        proposal_id=proposal_id,
                        fee_recipient=self.data.fee_recipient,
                        updated_by=sp.sender,
                    ),
                    tag="fee_recipient_set",
                )

            if proposal.action.is_variant.update_multisig_address():
                self.data.multisig_address = proposal.action.unwrap.update_multisig_address()
                sp.emit(
                    sp.record(
                        proposal_id=proposal_id,
                        multisig_address=self.data.multisig_address,
                        updated_by=sp.sender,
                    ),
                    tag="multisig_address_set",
                )

            if proposal.action.is_variant.update_metadata():
                entry = proposal.action.unwrap.update_metadata()
                self.data.metadata[entry.key] = entry.value
                sp.emit(
                    sp.record(
                        proposal_id=proposal_id,
                        key=entry.key,
                        updated_by=sp.sender,
                    ),
                    tag="metadata_updated",
                )

            if proposal.action.is_variant.set_user_banned():
                ban = proposal.action.unwrap.set_user_banned()
                if ban.banned:
                    self.data.banned[ban.address] = ()
                else:
                    if ban.address in self.data.banned:
                        del self.data.banned[ban.address]
                sp.emit(
                    sp.record(
                        proposal_id=proposal_id,
                        address=ban.address,
                        banned=ban.banned,
                        updated_by=sp.sender,
                    ),
                    tag="user_banned_set",
                )

        # =======================================================================
        # Views
        # =======================================================================

        @sp.onchain_view()
        def get_comment(self, comment_id):
            """Get comment by ID."""
            sp.cast(comment_id, sp.nat)
            assert comment_id in self.data.comments, "COMMENT_NOT_FOUND"
            return self.data.comments[comment_id]

        @sp.onchain_view()
        def get_comment_version(self, key):
            """Get an archived version of a comment.

            `key` is `(comment_id, version)`. Returns the snapshot of the
            comment at that version. Live state lives in `comments`."""
            sp.cast(key, history_key_type)
            assert key in self.data.comment_history, "VERSION_NOT_FOUND"
            return self.data.comment_history[key]

        @sp.onchain_view()
        def get_comment_version_count(self, comment_id):
            """Get the total version count for a comment.

            Versions start at 1, so this returns 1 for a never-edited comment
            and `1 + number_of_edits` otherwise. Archived snapshots exist at
            `comment_history[(comment_id, 1..version-1)]`; the live version
            (index = `version`) lives in `comments[comment_id]`."""
            sp.cast(comment_id, sp.nat)
            assert comment_id in self.data.comments, "COMMENT_NOT_FOUND"
            return self.data.comments[comment_id].version

        @sp.onchain_view()
        def get_fees(self):
            """Get the current post/edit/hide fees."""
            return sp.record(
                post_fee=self.data.post_fee,
                edit_fee=self.data.edit_fee,
                hide_fee=self.data.hide_fee,
            )

        @sp.onchain_view()
        def get_proposal(self, proposal_id):
            """Get proposal by ID."""
            sp.cast(proposal_id, sp.nat)
            assert proposal_id in self.data.proposals, "TC_NO_PROPOSAL"
            return self.data.proposals[proposal_id]

        @sp.onchain_view()
        def get_vote(self, key):
            """Get vote by key (proposal_id, voter)."""
            sp.cast(key, vote_key_type)
            return self.data.votes.get(key, default=False)

        @sp.onchain_view()
        def is_banned(self, address):
            """Check if an address is on the ban list."""
            sp.cast(address, sp.address)
            return address in self.data.banned


# ==============================================================================
# Deployment Scenario
# ==============================================================================


@sp.add_test()
def token_comments_deploy_shadownet():
    """Deployment scenario."""
    scenario = sp.test_scenario("token_comments_deploy_shadownet", token_comments_module)
    scenario.h1("Token Comments - Deployment Shadownet")

    MULTISIG_ADDRESS = sp.address("KT1KeGd4YtjcKqgyiXUPJQkm2iYA3fQwLGQP")
    FEE_RECIPIENT_ADDRESS = sp.address("KT1KeGd4YtjcKqgyiXUPJQkm2iYA3fQwLGQP")
    POST_FEE = sp.mutez(25000)
    EDIT_FEE = sp.mutez(0)
    HIDE_FEE = sp.mutez(0)

    contract_metadata = sp.big_map(
        {
            "": sp.scenario_utils.bytes_of_string("ipfs://QmeNKK9t4xdeNo8NCyJtmmdEZ2p2CFzgnLyMmtoWzaCUWf"),
        }
    )

    contract = token_comments_module.TokenComments(
        multisig_address=MULTISIG_ADDRESS,
        fee_recipient=FEE_RECIPIENT_ADDRESS,
        post_fee=POST_FEE,
        edit_fee=EDIT_FEE,
        hide_fee=HIDE_FEE,
        metadata=contract_metadata,
        counter=sp.nat(0),
    )
    scenario += contract


@sp.add_test()
def token_comments_deploy_mainnet():
    """Deployment scenario for Tezos mainnet."""
    scenario = sp.test_scenario("token_comments_deploy_mainnet", token_comments_module)
    scenario.h1("Token Comments - Deployment Mainnet")

    MULTISIG_ADDRESS = sp.address("KT1J9FYz29RBQi1oGLw8uXyACrzXzV1dHuvb")
    FEE_RECIPIENT_ADDRESS = sp.address("KT1J9FYz29RBQi1oGLw8uXyACrzXzV1dHuvb")
    POST_FEE = sp.mutez(25000)
    EDIT_FEE = sp.mutez(0)
    HIDE_FEE = sp.mutez(0)

    contract_metadata = sp.big_map(
        {
            "": sp.scenario_utils.bytes_of_string("ipfs://QmeNKK9t4xdeNo8NCyJtmmdEZ2p2CFzgnLyMmtoWzaCUWf"),
        }
    )

    contract = token_comments_module.TokenComments(
        multisig_address=MULTISIG_ADDRESS,
        fee_recipient=FEE_RECIPIENT_ADDRESS,
        post_fee=POST_FEE,
        edit_fee=EDIT_FEE,
        hide_fee=HIDE_FEE,
        metadata=contract_metadata,
        counter=sp.nat(0),
    )
    scenario += contract
