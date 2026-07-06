import smartpy as sp


@sp.module
def channels_module():
    """Teia Channels Contract.

    Three-tier access (creator > admin > merkle user) with optional allowlist gating.
    Per-action fees, edit history, hide/delete separation, per-channel and
    contract-wide ban lists, and channel + multisig moderation.

    Error codes:

    Channel / message:
    - CONTRACT_PAUSED: Contract is globally paused
    - TEZ_TRANSFER: Unexpected tez transfer
    - INCORRECT_FEE: sp.amount does not match the required fee
    - CHANNEL_NOT_FOUND: Channel ID does not exist
    - CHANNEL_HIDDEN: Channel has been hidden
    - EMPTY_METADATA: metadata_uri is empty
    - EMPTY_CONTENT: Message content is empty
    - CONTENT_TOO_LARGE: Message content exceeds 32 KiB
    - PARENT_NOT_FOUND: Reply target message does not exist
    - PARENT_WRONG_CHANNEL: Reply target is in a different channel
    - PARENT_HIDDEN: Reply target has been hidden
    - MESSAGE_NOT_FOUND: Message ID does not exist
    - UNDERFLOW: message_count would go negative

    Authorization:
    - NOT_AUTHORIZED: Caller cannot perform this action
    - NOT_CHANNEL_CREATOR: Caller is not the channel creator
    - NOT_CHANNEL_ADMIN: Caller is not creator or admin
    - TOO_MANY_ADMINS: Channel admin count would exceed 15

    Ban:
    - USER_BANNED: Caller is on the contract-wide ban list
    - USER_BANNED_IN_CHANNEL: Caller is banned from this channel
    - CANNOT_BAN_CREATOR: Cannot ban the channel creator

    Version history:
    - VERSION_NOT_FOUND: Requested version does not exist

    Access config / Merkle:
    - ALLOWLIST_NEEDS_ROOT: allowlist mode requires merkle_root
    - ROOT_NOT_ALLOWED: non-allowlist modes must not set merkle_root
    - NO_MERKLE_ROOT: Channel has no merkle_root configured
    - PROOF_REQUIRED: Caller must supply a merkle proof
    - INVALID_MERKLE_PROOF: Provided proof does not match merkle_root

    Governance (multisig-gated):
    - CHANNELS_VIEW_FAILED: is_user view on multisig failed
    - CHANNELS_NOT_MULTISIG_USER: Caller is not a multisig user
    - CHANNELS_GET_MIN_VOTES_FAILED: get_minimum_votes view failed
    - CHANNELS_GET_EXPIRATION_FAILED: get_expiration_time view failed
    - CHANNELS_PROPOSAL_EXPIRED: Proposal past expiration window
    - CHANNELS_NO_PROPOSAL: Proposal ID does not exist
    - CHANNELS_ALREADY_EXECUTED: Proposal already executed
    - CHANNELS_NOT_ENOUGH_VOTES: Positive votes below minimum
    """

    # ===========================================================================
    # Types
    # ===========================================================================

    # --- Access Control ---

    access_mode_type: type = sp.variant(
        unrestricted=sp.unit,
        allowlist=sp.unit,
        closed=sp.unit,
    )

    merkle_step_type: type = sp.record(
        hash=sp.bytes,
        direction=sp.nat,
    )

    # --- Channel ---

    channel_type: type = sp.record(
        creator=sp.address,
        metadata_uri=sp.bytes,
        access_mode=access_mode_type,
        merkle_root=sp.option[sp.bytes],
        merkle_uri=sp.option[sp.bytes],
        message_count=sp.nat,
        hidden=sp.bool,
        timestamp=sp.timestamp,
    )

    # --- Message ---

    message_type: type = sp.record(
        channel_id=sp.nat,
        sender=sp.address,
        content=sp.bytes,
        parent_id=sp.option[sp.nat],
        hidden=sp.bool,
        timestamp=sp.timestamp,
        version=sp.nat,
    )

    # --- Message History ---

    history_entry_type: type = sp.record(
        channel_id=sp.nat,
        sender=sp.address,
        content=sp.bytes,
        parent_id=sp.option[sp.nat],
        timestamp=sp.timestamp,
    )

    history_key_type: type = sp.pair[sp.nat, sp.nat]

    # --- Entrypoint Params ---

    post_message_params_type: type = sp.record(
        channel_id=sp.nat,
        content=sp.bytes,
        proof=sp.option[sp.list[merkle_step_type]],
        parent_id=sp.option[sp.nat],
    )

    create_channel_params_type: type = sp.record(
        metadata_uri=sp.bytes,
        access_mode=access_mode_type,
        merkle_root=sp.option[sp.bytes],
        merkle_uri=sp.option[sp.bytes],
        admins=sp.list[sp.address],
    )

    configure_channel_params_type: type = sp.record(
        channel_id=sp.nat,
        access_mode=access_mode_type,
        merkle_root=sp.option[sp.bytes],
        merkle_uri=sp.option[sp.bytes],
    )

    write_message_params_type: type = sp.record(
        channel_id=sp.nat,
        content=sp.bytes,
        parent_id=sp.option[sp.nat],
    )

    update_channel_admins_params_type: type = sp.record(
        channel_id=sp.nat,
        to_add=sp.list[sp.address],
        to_remove=sp.list[sp.address],
    )

    edit_message_params_type: type = sp.record(
        message_id=sp.nat,
        content=sp.bytes,
    )

    set_own_message_hidden_params_type: type = sp.record(
        message_id=sp.nat,
        hidden=sp.bool,
    )

    moderate_message_hidden_params_type: type = sp.record(
        message_id=sp.nat,
        hidden=sp.bool,
    )

    set_channel_banned_params_type: type = sp.record(
        channel_id=sp.nat,
        address=sp.address,
        banned=sp.bool,
    )

    # --- Storage Types ---

    channels_map_type: type = sp.big_map[sp.nat, channel_type]
    messages_map_type: type = sp.big_map[sp.nat, message_type]
    channel_admin_key_type: type = sp.record(channel_id=sp.nat, address=sp.address)
    channel_admins_map_type: type = sp.big_map[sp.nat, sp.set[sp.address]]
    channel_banned_key_type: type = sp.pair[sp.nat, sp.address]
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
        set_channel_fee=sp.mutez,
        set_fee_recipient=sp.address,
        update_multisig_address=sp.address,
        update_metadata=metadata_entry_type,
        set_user_banned=user_banned_action_type,
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

    class Channels(sp.Contract):
        """Teia Channels — three-tier access with hide/delete separation,
        edit history, per-action fees, ban lists, and multisig super moderation."""

        def __init__(self, multisig_address, fee_recipient, post_fee, edit_fee, hide_fee, channel_fee, metadata, counter):
            self.data.multisig_address = sp.cast(multisig_address, sp.address)
            self.data.metadata = sp.cast(metadata, metadata_type)
            self.data.paused = False
            self.data.channels = sp.cast(sp.big_map(), channels_map_type)
            self.data.messages = sp.cast(sp.big_map(), messages_map_type)
            self.data.message_history = sp.cast(sp.big_map(), sp.big_map[history_key_type, history_entry_type])
            self.data.channel_admins = sp.cast(sp.big_map(), channel_admins_map_type)
            self.data.channel_banned = sp.cast(sp.big_map(), sp.big_map[channel_banned_key_type, sp.unit])
            self.data.banned = sp.cast(sp.big_map(), sp.big_map[sp.address, sp.unit])
            self.data.channel_id_counter = sp.nat(1)
            self.data.message_id_counter = sp.nat(1)
            self.data.post_fee = sp.cast(post_fee, sp.mutez)
            self.data.edit_fee = sp.cast(edit_fee, sp.mutez)
            self.data.hide_fee = sp.cast(hide_fee, sp.mutez)
            self.data.channel_fee = sp.cast(channel_fee, sp.mutez)
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
        def _validate_access_config(self, params):
            sp.cast(params, sp.record(access_mode=access_mode_type, merkle_root=sp.option[sp.bytes]))
            if params.access_mode.is_variant.allowlist():
                assert params.merkle_root.is_some(), "ALLOWLIST_NEEDS_ROOT"
            else:
                assert not params.merkle_root.is_some(), "ROOT_NOT_ALLOWED"

        @sp.private(with_storage="read-only")
        def _check_no_tez_transfer(self):
            assert sp.amount == sp.tez(0), "TEZ_TRANSFER"

        @sp.private(with_storage="read-only")
        def _check_not_banned(self):
            assert not (sp.sender in self.data.banned), "USER_BANNED"

        @sp.private(with_storage="read-only")
        def _check_not_channel_banned(self, channel_id):
            sp.cast(channel_id, sp.nat)
            channel_ban_key = (channel_id, sp.sender)
            assert not (channel_ban_key in self.data.channel_banned), "USER_BANNED_IN_CHANNEL"

        @sp.private(with_storage="read-only")
        def _check_is_user(self):
            is_user = sp.view(
                "is_user",
                self.data.multisig_address,
                sp.sender,
                sp.bool,
            ).unwrap_some(error="CHANNELS_VIEW_FAILED")
            assert is_user, "CHANNELS_NOT_MULTISIG_USER"

        @sp.private(with_storage="read-only")
        def _get_minimum_votes(self):
            return sp.view(
                "get_minimum_votes",
                self.data.multisig_address,
                (),
                sp.nat,
            ).unwrap_some(error="CHANNELS_GET_MIN_VOTES_FAILED")

        @sp.private(with_storage="read-only")
        def _check_not_expired(self, timestamp):
            expiration_days = sp.view(
                "get_expiration_time",
                self.data.multisig_address,
                (),
                sp.nat,
            ).unwrap_some(error="CHANNELS_GET_EXPIRATION_FAILED")
            expiration_seconds = sp.to_int(expiration_days * 86400)
            expiration_time = sp.add_seconds(timestamp, expiration_seconds)
            assert not (sp.now > expiration_time), "CHANNELS_PROPOSAL_EXPIRED"

        @sp.private(with_storage="read-write", with_operations=True)
        def _send_fee(self, fee):
            if fee > sp.mutez(0):
                sp.send(self.data.fee_recipient, fee)

        @sp.private(with_storage="read-only")
        def _check_channel_admin(self, channel_id):
            sp.cast(channel_id, sp.nat)
            channel = self.data.channels[channel_id]
            assert channel.creator == sp.sender or sp.sender in self.data.channel_admins[channel_id], "NOT_CHANNEL_ADMIN"

        @sp.private(with_storage="read-write")
        def _write_message(self, params):
            sp.cast(params, write_message_params_type)
            message_id = self.data.message_id_counter
            self.data.messages[message_id] = sp.record(
                channel_id=params.channel_id,
                sender=sp.sender,
                content=params.content,
                parent_id=params.parent_id,
                hidden=False,
                timestamp=sp.now,
                version=sp.nat(1),
            )

            channel = self.data.channels[params.channel_id]
            self.data.channels[params.channel_id] = sp.record(
                creator=channel.creator,
                metadata_uri=channel.metadata_uri,
                access_mode=channel.access_mode,
                merkle_root=channel.merkle_root,
                merkle_uri=channel.merkle_uri,
                message_count=channel.message_count + 1,
                hidden=channel.hidden,
                timestamp=channel.timestamp,
            )

            self.data.message_id_counter += 1
            return message_id

        @sp.private(with_storage="read-only")
        def _check_can_post(self, params):
            sp.cast(params, sp.record(channel_id=sp.nat, proof=sp.option[sp.list[merkle_step_type]]))
            channel = self.data.channels[params.channel_id]
            is_privileged = channel.creator == sp.sender or sp.sender in self.data.channel_admins[params.channel_id]
            if not is_privileged:
                if channel.access_mode.is_variant.closed():
                    assert False, "NOT_AUTHORIZED"
                if channel.access_mode.is_variant.allowlist():
                    root = channel.merkle_root.unwrap_some(error="NO_MERKLE_ROOT")
                    proof = params.proof.unwrap_some(error="PROOF_REQUIRED")
                    computed = sp.blake2b(sp.pack(sp.sender))
                    for step in proof:
                        if step.direction == 0:
                            computed = sp.blake2b(step.hash + computed)
                        else:
                            computed = sp.blake2b(computed + step.hash)
                    assert computed == root, "INVALID_MERKLE_PROOF"

        # =======================================================================
        # Channel Entrypoints
        # =======================================================================

        @sp.entrypoint
        def create_channel(self, params):
            sp.cast(params, create_channel_params_type)
            self._check_not_paused()
            assert sp.len(params.metadata_uri) > 0, "EMPTY_METADATA"
            assert sp.amount == self.data.channel_fee, "INCORRECT_FEE"

            self._validate_access_config(sp.record(access_mode=params.access_mode, merkle_root=params.merkle_root))

            channel_id = self.data.channel_id_counter
            self.data.channels[channel_id] = sp.record(
                creator=sp.sender,
                metadata_uri=params.metadata_uri,
                access_mode=params.access_mode,
                merkle_root=params.merkle_root,
                merkle_uri=params.merkle_uri,
                message_count=sp.nat(0),
                hidden=False,
                timestamp=sp.now,
            )

            admins_set = sp.cast(set(), sp.set[sp.address])
            for addr in params.admins:
                admins_set.add(addr)
            assert sp.len(admins_set) <= sp.nat(15), "TOO_MANY_ADMINS"
            self.data.channel_admins[channel_id] = admins_set

            self.data.channel_id_counter += 1

            self._send_fee(self.data.channel_fee)

            sp.emit(
                sp.record(
                    channel_id=channel_id,
                    creator=sp.sender,
                    metadata_uri=params.metadata_uri,
                    access_mode=params.access_mode,
                    merkle_root=params.merkle_root,
                    merkle_uri=params.merkle_uri,
                    admins=params.admins,
                    timestamp=sp.now,
                ),
                tag="channel_created",
            )

        @sp.entrypoint
        def configure_channel(self, params):
            """Closed channels: creator only. Other modes: creator or admin."""
            sp.cast(params, configure_channel_params_type)
            self._check_not_paused()
            self._check_no_tez_transfer()

            assert params.channel_id in self.data.channels, "CHANNEL_NOT_FOUND"
            channel = self.data.channels[params.channel_id]
            assert not channel.hidden, "CHANNEL_HIDDEN"

            if channel.access_mode.is_variant.closed():
                assert channel.creator == sp.sender, "NOT_CHANNEL_CREATOR"
            else:
                self._check_channel_admin(params.channel_id)

            self._validate_access_config(sp.record(access_mode=params.access_mode, merkle_root=params.merkle_root))

            self.data.channels[params.channel_id] = sp.record(
                creator=channel.creator,
                metadata_uri=channel.metadata_uri,
                access_mode=params.access_mode,
                merkle_root=params.merkle_root,
                merkle_uri=params.merkle_uri,
                message_count=channel.message_count,
                hidden=channel.hidden,
                timestamp=channel.timestamp,
            )

            sp.emit(
                sp.record(
                    channel_id=params.channel_id,
                    access_mode=params.access_mode,
                    merkle_root=params.merkle_root,
                    merkle_uri=params.merkle_uri,
                    configured_by=sp.sender,
                ),
                tag="channel_configured",
            )

        @sp.entrypoint
        def update_channel(self, params):
            sp.cast(params, sp.record(channel_id=sp.nat, metadata_uri=sp.bytes))
            self._check_not_paused()
            self._check_no_tez_transfer()

            assert params.channel_id in self.data.channels, "CHANNEL_NOT_FOUND"
            channel = self.data.channels[params.channel_id]
            self._check_channel_admin(params.channel_id)
            assert sp.len(params.metadata_uri) > 0, "EMPTY_METADATA"

            self.data.channels[params.channel_id] = sp.record(
                creator=channel.creator,
                metadata_uri=params.metadata_uri,
                access_mode=channel.access_mode,
                merkle_root=channel.merkle_root,
                merkle_uri=channel.merkle_uri,
                message_count=channel.message_count,
                hidden=channel.hidden,
                timestamp=channel.timestamp,
            )

            sp.emit(
                sp.record(
                    channel_id=params.channel_id,
                    metadata_uri=params.metadata_uri,
                    updated_by=sp.sender,
                ),
                tag="channel_updated",
            )

        @sp.entrypoint
        def set_channel_hidden(self, params):
            sp.cast(params, sp.record(channel_id=sp.nat, hidden=sp.bool))
            self._check_not_paused()
            self._check_no_tez_transfer()

            assert params.channel_id in self.data.channels, "CHANNEL_NOT_FOUND"
            channel = self.data.channels[params.channel_id]
            assert channel.creator == sp.sender, "NOT_CHANNEL_CREATOR"

            self.data.channels[params.channel_id] = sp.record(
                creator=channel.creator,
                metadata_uri=channel.metadata_uri,
                access_mode=channel.access_mode,
                merkle_root=channel.merkle_root,
                merkle_uri=channel.merkle_uri,
                message_count=channel.message_count,
                hidden=params.hidden,
                timestamp=channel.timestamp,
            )

            sp.emit(
                sp.record(
                    channel_id=params.channel_id,
                    hidden=params.hidden,
                    updated_by=sp.sender,
                ),
                tag="channel_hidden_set",
            )

        @sp.entrypoint
        def update_channel_admins(self, params):
            sp.cast(params, update_channel_admins_params_type)
            self._check_not_paused()
            self._check_no_tez_transfer()

            assert params.channel_id in self.data.channels, "CHANNEL_NOT_FOUND"
            channel = self.data.channels[params.channel_id]
            assert channel.creator == sp.sender, "NOT_CHANNEL_CREATOR"

            for addr in params.to_remove:
                if addr in self.data.channel_admins[params.channel_id]:
                    self.data.channel_admins[params.channel_id].remove(addr)

            for addr in params.to_add:
                self.data.channel_admins[params.channel_id].add(addr)

            assert sp.len(self.data.channel_admins[params.channel_id]) <= sp.nat(15), "TOO_MANY_ADMINS"

            sp.emit(
                sp.record(
                    channel_id=params.channel_id,
                    to_add=params.to_add,
                    to_remove=params.to_remove,
                ),
                tag="channel_admins_updated",
            )

        @sp.entrypoint
        def set_channel_banned(self, params):
            sp.cast(params, set_channel_banned_params_type)
            self._check_not_paused()
            self._check_no_tez_transfer()

            assert params.channel_id in self.data.channels, "CHANNEL_NOT_FOUND"
            channel = self.data.channels[params.channel_id]
            self._check_channel_admin(params.channel_id)
            assert params.address != channel.creator, "CANNOT_BAN_CREATOR"

            if params.banned:
                self.data.channel_banned[(params.channel_id, params.address)] = ()
            else:
                if (params.channel_id, params.address) in self.data.channel_banned:
                    del self.data.channel_banned[(params.channel_id, params.address)]

            sp.emit(
                sp.record(
                    channel_id=params.channel_id,
                    address=params.address,
                    banned=params.banned,
                    updated_by=sp.sender,
                ),
                tag="channel_banned_set",
            )

        # =======================================================================
        # Message Entrypoints
        # =======================================================================

        @sp.entrypoint
        def post_message(self, params):
            sp.cast(params, post_message_params_type)
            self._check_not_paused()
            self._check_not_banned()

            assert sp.len(params.content) > 0, "EMPTY_CONTENT"
            assert sp.len(params.content) <= 32768, "CONTENT_TOO_LARGE"
            assert params.channel_id in self.data.channels, "CHANNEL_NOT_FOUND"

            channel = self.data.channels[params.channel_id]
            assert not channel.hidden, "CHANNEL_HIDDEN"

            if channel.creator != sp.sender:
                self._check_not_channel_banned(params.channel_id)

            if params.parent_id.is_some():
                parent_msg_id = params.parent_id.unwrap_some()
                assert parent_msg_id in self.data.messages, "PARENT_NOT_FOUND"
                parent_msg = self.data.messages[parent_msg_id]
                assert parent_msg.channel_id == params.channel_id, "PARENT_WRONG_CHANNEL"
                assert not parent_msg.hidden, "PARENT_HIDDEN"

            self._check_can_post(sp.record(channel_id=params.channel_id, proof=params.proof))

            assert sp.amount == self.data.post_fee, "INCORRECT_FEE"
            self._send_fee(self.data.post_fee)

            message_id = self._write_message(sp.record(channel_id=params.channel_id, content=params.content, parent_id=params.parent_id))

            sp.emit(
                sp.record(
                    channel_id=params.channel_id,
                    message_id=message_id,
                    sender=sp.sender,
                    parent_id=params.parent_id,
                    timestamp=sp.now,
                ),
                tag="message_posted",
            )

        @sp.entrypoint
        def edit_message(self, params):
            sp.cast(params, edit_message_params_type)
            self._check_not_paused()
            self._check_not_banned()

            assert sp.amount == self.data.edit_fee, "INCORRECT_FEE"

            assert params.message_id in self.data.messages, "MESSAGE_NOT_FOUND"
            message = self.data.messages[params.message_id]
            assert message.sender == sp.sender, "NOT_AUTHORIZED"
            assert sp.len(params.content) > 0, "EMPTY_CONTENT"
            assert sp.len(params.content) <= 32768, "CONTENT_TOO_LARGE"

            self.data.message_history[(params.message_id, message.version)] = sp.record(
                channel_id=message.channel_id,
                sender=message.sender,
                content=message.content,
                parent_id=message.parent_id,
                timestamp=message.timestamp,
            )

            new_version = message.version + 1
            self.data.messages[params.message_id] = sp.record(
                channel_id=message.channel_id,
                sender=message.sender,
                content=params.content,
                parent_id=message.parent_id,
                hidden=message.hidden,
                timestamp=sp.now,
                version=new_version,
            )

            self._send_fee(sp.amount)

            sp.emit(
                sp.record(
                    channel_id=message.channel_id,
                    message_id=params.message_id,
                    sender=message.sender,
                    parent_id=message.parent_id,
                    timestamp=sp.now,
                    version=new_version,
                ),
                tag="message_edited",
            )

        @sp.entrypoint
        def delete_message(self, message_id):
            """Sender-only hard delete, regardless of channel access mode."""
            sp.cast(message_id, sp.nat)
            self._check_not_paused()
            self._check_no_tez_transfer()

            assert message_id in self.data.messages, "MESSAGE_NOT_FOUND"
            message = self.data.messages[message_id]
            assert message.sender == sp.sender, "NOT_AUTHORIZED"

            assert message.channel_id in self.data.channels, "CHANNEL_NOT_FOUND"
            channel = self.data.channels[message.channel_id]

            self.data.channels[message.channel_id] = sp.record(
                creator=channel.creator,
                metadata_uri=channel.metadata_uri,
                access_mode=channel.access_mode,
                merkle_root=channel.merkle_root,
                merkle_uri=channel.merkle_uri,
                message_count=sp.as_nat(channel.message_count - 1, error="UNDERFLOW"),
                hidden=channel.hidden,
                timestamp=channel.timestamp,
            )

            del self.data.messages[message_id]

            sp.emit(
                sp.record(
                    channel_id=message.channel_id,
                    message_id=message_id,
                    deleted_by=sp.sender,
                ),
                tag="message_deleted",
            )

        @sp.entrypoint
        def set_own_message_hidden(self, params):
            sp.cast(params, set_own_message_hidden_params_type)
            self._check_not_paused()

            assert sp.amount == self.data.hide_fee, "INCORRECT_FEE"

            assert params.message_id in self.data.messages, "MESSAGE_NOT_FOUND"
            message = self.data.messages[params.message_id]
            assert message.sender == sp.sender, "NOT_AUTHORIZED"

            self.data.messages[params.message_id] = sp.record(
                channel_id=message.channel_id,
                sender=message.sender,
                content=message.content,
                parent_id=message.parent_id,
                hidden=params.hidden,
                timestamp=message.timestamp,
                version=message.version,
            )

            self._send_fee(sp.amount)

            sp.emit(
                sp.record(
                    message_id=params.message_id,
                    hidden=params.hidden,
                    updated_by=sp.sender,
                ),
                tag="message_hidden_set",
            )

        @sp.entrypoint
        def moderate_message_hidden(self, params):
            """Channel creator or admin can hide any message in their channel."""
            sp.cast(params, moderate_message_hidden_params_type)
            self._check_not_paused()
            self._check_no_tez_transfer()

            assert params.message_id in self.data.messages, "MESSAGE_NOT_FOUND"
            message = self.data.messages[params.message_id]

            assert message.channel_id in self.data.channels, "CHANNEL_NOT_FOUND"
            self._check_channel_admin(message.channel_id)

            self.data.messages[params.message_id] = sp.record(
                channel_id=message.channel_id,
                sender=message.sender,
                content=message.content,
                parent_id=message.parent_id,
                hidden=params.hidden,
                timestamp=message.timestamp,
                version=message.version,
            )

            sp.emit(
                sp.record(
                    channel_id=message.channel_id,
                    message_id=params.message_id,
                    hidden=params.hidden,
                    moderator=sp.sender,
                ),
                tag="message_moderated",
            )

        @sp.entrypoint
        def multisig_moderate_msg_hidden(self, params):
            """Any multisig user can hide any message in any channel."""
            sp.cast(params, moderate_message_hidden_params_type)
            self._check_no_tez_transfer()
            self._check_is_user()

            assert params.message_id in self.data.messages, "MESSAGE_NOT_FOUND"
            message = self.data.messages[params.message_id]

            self.data.messages[params.message_id] = sp.record(
                channel_id=message.channel_id,
                sender=message.sender,
                content=message.content,
                parent_id=message.parent_id,
                hidden=params.hidden,
                timestamp=message.timestamp,
                version=message.version,
            )

            sp.emit(
                sp.record(
                    channel_id=message.channel_id,
                    message_id=params.message_id,
                    hidden=params.hidden,
                    moderator=sp.sender,
                ),
                tag="message_multisig_moderated",
            )

        # =======================================================================
        # Governance Entrypoints
        # =======================================================================

        @sp.entrypoint
        def submit_proposal(self, action):
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
            sp.cast(vote, vote_params_type)
            self._check_no_tez_transfer()
            self._check_is_user()
            assert vote.proposal_id in self.data.proposals, "CHANNELS_NO_PROPOSAL"

            proposal = self.data.proposals[vote.proposal_id]
            assert not proposal.executed, "CHANNELS_ALREADY_EXECUTED"
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
            sp.cast(proposal_id, sp.nat)
            self._check_no_tez_transfer()
            self._check_is_user()
            assert proposal_id in self.data.proposals, "CHANNELS_NO_PROPOSAL"

            proposal = self.data.proposals[proposal_id]
            assert not proposal.executed, "CHANNELS_ALREADY_EXECUTED"
            minimum_votes = self._get_minimum_votes()
            assert proposal.positive_votes >= minimum_votes, "CHANNELS_NOT_ENOUGH_VOTES"
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

            if proposal.action.is_variant.set_channel_fee():
                self.data.channel_fee = proposal.action.unwrap.set_channel_fee()
                sp.emit(
                    sp.record(
                        proposal_id=proposal_id,
                        channel_fee=self.data.channel_fee,
                        updated_by=sp.sender,
                    ),
                    tag="channel_fee_set",
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
        def get_channel(self, channel_id):
            sp.cast(channel_id, sp.nat)
            assert channel_id in self.data.channels, "CHANNEL_NOT_FOUND"
            return self.data.channels[channel_id]

        @sp.onchain_view()
        def get_message(self, message_id):
            sp.cast(message_id, sp.nat)
            assert message_id in self.data.messages, "MESSAGE_NOT_FOUND"
            return self.data.messages[message_id]

        @sp.onchain_view()
        def get_message_version(self, key):
            sp.cast(key, history_key_type)
            assert key in self.data.message_history, "VERSION_NOT_FOUND"
            return self.data.message_history[key]

        @sp.onchain_view()
        def get_message_version_count(self, message_id):
            sp.cast(message_id, sp.nat)
            assert message_id in self.data.messages, "MESSAGE_NOT_FOUND"
            return self.data.messages[message_id].version

        @sp.onchain_view()
        def get_fees(self):
            return sp.record(
                post_fee=self.data.post_fee,
                edit_fee=self.data.edit_fee,
                hide_fee=self.data.hide_fee,
                channel_fee=self.data.channel_fee,
            )

        @sp.onchain_view()
        def is_channel_admin(self, params):
            sp.cast(params, channel_admin_key_type)
            assert params.channel_id in self.data.channels, "CHANNEL_NOT_FOUND"
            channel = self.data.channels[params.channel_id]
            return channel.creator == params.address or params.address in self.data.channel_admins[params.channel_id]

        @sp.onchain_view()
        def is_banned(self, address):
            sp.cast(address, sp.address)
            return address in self.data.banned

        @sp.onchain_view()
        def is_channel_banned(self, params):
            sp.cast(params, channel_admin_key_type)
            return (params.channel_id, params.address) in self.data.channel_banned

        @sp.onchain_view()
        def get_proposal(self, proposal_id):
            sp.cast(proposal_id, sp.nat)
            assert proposal_id in self.data.proposals, "CHANNELS_NO_PROPOSAL"
            return self.data.proposals[proposal_id]

        @sp.onchain_view()
        def get_vote(self, key):
            sp.cast(key, vote_key_type)
            return self.data.votes.get(key, default=False)


# ==============================================================================
# Deployment Scenarios
# ==============================================================================


@sp.add_test()
def channels_deploy_shadownet():
    scenario = sp.test_scenario("channels_deploy_shadownet", channels_module)
    scenario.h1("Teia Channels - Deployment Shadownet")

    MULTISIG_ADDRESS = sp.address("KT1KeGd4YtjcKqgyiXUPJQkm2iYA3fQwLGQP")
    FEE_RECIPIENT_ADDRESS = sp.address("KT1KeGd4YtjcKqgyiXUPJQkm2iYA3fQwLGQP")
    POST_FEE = sp.mutez(25000)
    EDIT_FEE = sp.mutez(0)
    HIDE_FEE = sp.mutez(0)
    CHANNEL_FEE = sp.mutez(100000)

    contract_metadata = sp.big_map(
        {
            "": sp.scenario_utils.bytes_of_string("ipfs://QmcgWNSbBDqe2Q1Nmpg6crsAV7QDjXAQpAxQuLcWW2ffFC"),
        }
    )

    contract = channels_module.Channels(
        multisig_address=MULTISIG_ADDRESS,
        fee_recipient=FEE_RECIPIENT_ADDRESS,
        post_fee=POST_FEE,
        edit_fee=EDIT_FEE,
        hide_fee=HIDE_FEE,
        channel_fee=CHANNEL_FEE,
        metadata=contract_metadata,
        counter=sp.nat(0),
    )
    scenario += contract


@sp.add_test()
def channels_deploy_mainnet():
    scenario = sp.test_scenario("channels_deploy_mainnet", channels_module)
    scenario.h1("Teia Channels - Deployment Mainnet")

    MULTISIG_ADDRESS = sp.address("KT1J9FYz29RBQi1oGLw8uXyACrzXzV1dHuvb")
    FEE_RECIPIENT_ADDRESS = sp.address("KT1J9FYz29RBQi1oGLw8uXyACrzXzV1dHuvb")
    POST_FEE = sp.mutez(25000)
    EDIT_FEE = sp.mutez(0)
    HIDE_FEE = sp.mutez(0)
    CHANNEL_FEE = sp.mutez(100000)

    contract_metadata = sp.big_map(
        {
            "": sp.scenario_utils.bytes_of_string("ipfs://QmcgWNSbBDqe2Q1Nmpg6crsAV7QDjXAQpAxQuLcWW2ffFC"),
        }
    )

    contract = channels_module.Channels(
        multisig_address=MULTISIG_ADDRESS,
        fee_recipient=FEE_RECIPIENT_ADDRESS,
        post_fee=POST_FEE,
        edit_fee=EDIT_FEE,
        hide_fee=HIDE_FEE,
        channel_fee=CHANNEL_FEE,
        metadata=contract_metadata,
        counter=sp.nat(0),
    )
    scenario += contract
