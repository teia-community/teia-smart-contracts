
# --- Test: Create conversation and post ---

@sp.add_test()
def test_create_and_post():
    """Test creating a conversation and posting messages."""
    scenario = sp.test_scenario("create_and_post", [mock_multisig_module, direct_messages_module])
    scenario.h1("Create Conversation and Post")
    admin, alice, bob, charlie, dave, multisig, contract = _setup(scenario)

    # Alice creates a conversation with Bob
    scenario.h2("Alice creates conversation with Bob")
    contract.create_conversation(
        sp.record(metadata_uri=sp.bytes("0x6d657461"), participants=[bob.address]),
        _sender=alice,
    )
    scenario.verify(contract.data.conversations[1].creator == alice.address)
    scenario.verify(contract.data.conversations[1].message_count == 0)

    # Alice is a participant
    is_alice = sp.View(contract, "is_participant")(
        sp.record(conversation_id=sp.nat(1), address=alice.address)
    )
    scenario.verify(is_alice)

    # Bob is a participant
    is_bob = sp.View(contract, "is_participant")(
        sp.record(conversation_id=sp.nat(1), address=bob.address)
    )
    scenario.verify(is_bob)

    # Charlie is NOT a participant
    is_charlie = sp.View(contract, "is_participant")(
        sp.record(conversation_id=sp.nat(1), address=charlie.address)
    )
    scenario.verify(~is_charlie)

    # Alice posts
    scenario.h2("Alice posts")
    contract.post_message(
        sp.record(conversation_id=sp.nat(1), content=sp.bytes("0x48656c6c6f"), parent_id=sp.none),
        _sender=alice,
    )
    scenario.verify(contract.data.messages[1].sender == alice.address)

    # Bob posts
    scenario.h2("Bob posts")
    contract.post_message(
        sp.record(conversation_id=sp.nat(1), content=sp.bytes("0x576f726c64"), parent_id=sp.none),
        _sender=bob,
    )
    scenario.verify(contract.data.messages[2].sender == bob.address)

    conv = sp.View(contract, "get_conversation")(sp.nat(1))
    scenario.verify(conv.message_count == 2)

    # Charlie cannot post (not a participant)
    scenario.h2("Charlie rejected — not participant")
    contract.post_message(
        sp.record(conversation_id=sp.nat(1), content=sp.bytes("0x4e6f7065"), parent_id=sp.none),
        _sender=charlie,
        _valid=False,
        _exception="NOT_PARTICIPANT",
    )


# --- Test: Participants management ---

@sp.add_test()
def test_participants():
    """Test adding and removing participants."""
    scenario = sp.test_scenario("participants", [mock_multisig_module, direct_messages_module])
    scenario.h1("Participants Management")
    admin, alice, bob, charlie, dave, multisig, contract = _setup(scenario)

    contract.create_conversation(
        sp.record(metadata_uri=sp.bytes("0x6d657461"), participants=[bob.address]),
        _sender=alice,
    )

    # Non-admin cannot add participants
    scenario.h2("Non-admin cannot update participants")
    contract.update_participants(
        sp.record(conversation_id=sp.nat(1), to_add=[charlie.address], to_remove=[]),
        _sender=bob,
        _valid=False,
        _exception="NOT_CONVERSATION_ADMIN",
    )

    # Creator adds charlie
    scenario.h2("Creator adds Charlie")
    contract.update_participants(
        sp.record(conversation_id=sp.nat(1), to_add=[charlie.address], to_remove=[]),
        _sender=alice,
    )

    # Charlie can now post
    contract.post_message(
        sp.record(conversation_id=sp.nat(1), content=sp.bytes("0x4869"), parent_id=sp.none),
        _sender=charlie,
    )
    scenario.verify(contract.data.messages[1].sender == charlie.address)

    # Creator removes Bob
    scenario.h2("Creator removes Bob")
    contract.update_participants(
        sp.record(conversation_id=sp.nat(1), to_add=[], to_remove=[bob.address]),
        _sender=alice,
    )

    # Bob can no longer post
    contract.post_message(
        sp.record(conversation_id=sp.nat(1), content=sp.bytes("0x4e6f7065"), parent_id=sp.none),
        _sender=bob,
        _valid=False,
        _exception="NOT_PARTICIPANT",
    )


# --- Test: Conversation admins ---

@sp.add_test()
def test_conversation_admins():
    """Test admin delegation for conversations."""
    scenario = sp.test_scenario("conversation_admins", [mock_multisig_module, direct_messages_module])
    scenario.h1("Conversation Admins")
    admin, alice, bob, charlie, dave, multisig, contract = _setup(scenario)

    contract.create_conversation(
        sp.record(metadata_uri=sp.bytes("0x6d657461"), participants=[bob.address, charlie.address]),
        _sender=alice,
    )

    # Only creator can add admins
    scenario.h2("Non-creator cannot add admins")
    contract.update_conversation_admins(
        sp.record(conversation_id=sp.nat(1), to_add=[bob.address], to_remove=[]),
        _sender=bob,
        _valid=False,
        _exception="NOT_CONVERSATION_CREATOR",
    )

    # Creator adds Bob as admin
    scenario.h2("Creator adds Bob as admin")
    contract.update_conversation_admins(
        sp.record(conversation_id=sp.nat(1), to_add=[bob.address], to_remove=[]),
        _sender=alice,
    )

    is_admin = sp.View(contract, "is_conversation_admin")(
        sp.record(conversation_id=sp.nat(1), address=bob.address)
    )
    scenario.verify(is_admin)

    # Admin can add participants
    scenario.h2("Admin adds Dave")
    contract.update_participants(
        sp.record(conversation_id=sp.nat(1), to_add=[dave.address], to_remove=[]),
        _sender=bob,
    )

    is_dave = sp.View(contract, "is_participant")(
        sp.record(conversation_id=sp.nat(1), address=dave.address)
    )
    scenario.verify(is_dave)

    # Admin can delete messages
    scenario.h2("Admin deletes message")
    contract.post_message(
        sp.record(conversation_id=sp.nat(1), content=sp.bytes("0x4869"), parent_id=sp.none),
        _sender=charlie,
    )
    contract.delete_message(sp.nat(1), _sender=bob)
    scenario.verify(~contract.data.messages.contains(sp.nat(1)))

    # Admin cannot add other admins
    scenario.h2("Admin cannot add other admins")
    contract.update_conversation_admins(
        sp.record(conversation_id=sp.nat(1), to_add=[charlie.address], to_remove=[]),
        _sender=bob,
        _valid=False,
        _exception="NOT_CONVERSATION_CREATOR",
    )

    # Admin cannot delete conversation
    scenario.h2("Admin cannot delete conversation")
    contract.delete_conversation(sp.nat(1), _sender=bob, _valid=False, _exception="NOT_CONVERSATION_CREATOR")

    # Creator removes admin
    scenario.h2("Creator removes Bob as admin")
    contract.update_conversation_admins(
        sp.record(conversation_id=sp.nat(1), to_add=[], to_remove=[bob.address]),
        _sender=alice,
    )

    # Bob can no longer update participants
    contract.update_participants(
        sp.record(conversation_id=sp.nat(1), to_add=[admin.address], to_remove=[]),
        _sender=bob,
        _valid=False,
        _exception="NOT_CONVERSATION_ADMIN",
    )


# --- Test: Message replies ---

@sp.add_test()
def test_replies():
    """Test message reply functionality."""
    scenario = sp.test_scenario("dm_replies", [mock_multisig_module, direct_messages_module])
    scenario.h1("Message Replies")
    admin, alice, bob, charlie, dave, multisig, contract = _setup(scenario)

    contract.create_conversation(
        sp.record(metadata_uri=sp.bytes("0x6d657461"), participants=[bob.address]),
        _sender=alice,
    )

    # Top-level message
    contract.post_message(
        sp.record(conversation_id=sp.nat(1), content=sp.bytes("0x48656c6c6f"), parent_id=sp.none),
        _sender=alice,
    )
    scenario.verify(~contract.data.messages[1].parent_id.is_some())

    # Reply
    contract.post_message(
        sp.record(conversation_id=sp.nat(1), content=sp.bytes("0x5265706c79"), parent_id=sp.Some(sp.nat(1))),
        _sender=bob,
    )
    scenario.verify(contract.data.messages[2].parent_id.is_some())

    # Reply to non-existent message
    contract.post_message(
        sp.record(conversation_id=sp.nat(1), content=sp.bytes("0x4e6f"), parent_id=sp.Some(sp.nat(999))),
        _sender=alice,
        _valid=False,
        _exception="PARENT_NOT_FOUND",
    )

    # Reply to message in different conversation
    contract.create_conversation(
        sp.record(metadata_uri=sp.bytes("0x6d65746132"), participants=[bob.address]),
        _sender=alice,
    )
    contract.post_message(
        sp.record(conversation_id=sp.nat(2), content=sp.bytes("0x4e6f"), parent_id=sp.Some(sp.nat(1))),
        _sender=alice,
        _valid=False,
        _exception="PARENT_WRONG_CONVERSATION",
    )

    # Delete parent, reply remains
    contract.delete_message(sp.nat(1), _sender=alice)
    scenario.verify(~contract.data.messages.contains(sp.nat(1)))
    scenario.verify(contract.data.messages[2].sender == bob.address)


# --- Test: Delete conversation ---

@sp.add_test()
def test_delete_conversation():
    """Test deleting a conversation."""
    scenario = sp.test_scenario("delete_conversation", [mock_multisig_module, direct_messages_module])
    scenario.h1("Delete Conversation")
    admin, alice, bob, charlie, dave, multisig, contract = _setup(scenario)

    contract.create_conversation(
        sp.record(metadata_uri=sp.bytes("0x6d657461"), participants=[bob.address]),
        _sender=alice,
    )

    # Non-creator cannot delete
    contract.delete_conversation(sp.nat(1), _sender=bob, _valid=False, _exception="NOT_CONVERSATION_CREATOR")

    # Creator deletes
    contract.delete_conversation(sp.nat(1), _sender=alice)
    scenario.verify(~contract.data.conversations.contains(sp.nat(1)))


# --- Test: Fees ---

@sp.add_test()
def test_fees():
    """Test message and conversation fees."""
    scenario = sp.test_scenario("dm_fees", [mock_multisig_module, direct_messages_module])
    scenario.h1("Fees")

    admin = sp.test_account("Admin")
    alice = sp.test_account("Alice")
    bob = sp.test_account("Bob")

    multisig = mock_multisig_module.MockMultisig(
        users={admin.address},
        minimum_votes=sp.nat(1),
        expiration_time=sp.nat(30),
    )
    scenario += multisig

    contract_metadata = sp.big_map({"": sp.scenario_utils.bytes_of_string("ipfs://test")})
    contract = direct_messages_module.DirectMessages(
        multisig_address=multisig.address,
        fee_recipient=admin.address,
        message_fee=sp.mutez(100),
        conversation_fee=sp.mutez(500),
        metadata=contract_metadata,
        counter=sp.nat(0),
    )
    scenario += contract

    # Wrong conversation fee
    scenario.h2("Wrong conversation fee")
    contract.create_conversation(
        sp.record(metadata_uri=sp.bytes("0x6d657461"), participants=[bob.address]),
        _sender=alice,
        _amount=sp.mutez(0),
        _valid=False,
        _exception="INCORRECT_FEE",
    )

    # Correct conversation fee
    scenario.h2("Correct conversation fee")
    contract.create_conversation(
        sp.record(metadata_uri=sp.bytes("0x6d657461"), participants=[bob.address]),
        _sender=alice,
        _amount=sp.mutez(500),
    )

    # Wrong message fee
    scenario.h2("Wrong message fee")
    contract.post_message(
        sp.record(conversation_id=sp.nat(1), content=sp.bytes("0x4869"), parent_id=sp.none),
        _sender=alice,
        _amount=sp.mutez(0),
        _valid=False,
        _exception="INCORRECT_FEE",
    )

    # Correct message fee
    scenario.h2("Correct message fee")
    contract.post_message(
        sp.record(conversation_id=sp.nat(1), content=sp.bytes("0x4869"), parent_id=sp.none),
        _sender=alice,
        _amount=sp.mutez(100),
    )


# --- Test: Edge cases ---

@sp.add_test()
def test_edge_cases():
    """Test edge cases and error handling."""
    scenario = sp.test_scenario("dm_edge_cases", [mock_multisig_module, direct_messages_module])
    scenario.h1("Edge Cases")
    admin, alice, bob, charlie, dave, multisig, contract = _setup(scenario)

    contract.create_conversation(
        sp.record(metadata_uri=sp.bytes("0x6d657461"), participants=[bob.address]),
        _sender=alice,
    )

    # Empty content
    contract.post_message(
        sp.record(conversation_id=sp.nat(1), content=sp.bytes("0x"), parent_id=sp.none),
        _sender=alice,
        _valid=False,
        _exception="EMPTY_CONTENT",
    )

    # Non-existent conversation
    contract.post_message(
        sp.record(conversation_id=sp.nat(999), content=sp.bytes("0x4869"), parent_id=sp.none),
        _sender=alice,
        _valid=False,
        _exception="CONVERSATION_NOT_FOUND",
    )

    # Empty metadata
    contract.create_conversation(
        sp.record(metadata_uri=sp.bytes("0x"), participants=[bob.address]),
        _sender=alice,
        _valid=False,
        _exception="EMPTY_METADATA",
    )

    # Delete non-existent message
    contract.delete_message(sp.nat(999), _sender=alice, _valid=False, _exception="MESSAGE_NOT_FOUND")

    # Delete non-existent conversation
    contract.delete_conversation(sp.nat(999), _sender=alice, _valid=False, _exception="CONVERSATION_NOT_FOUND")



@sp.add_test()
def deploy():
    """Deployment scenario."""
    scenario = sp.test_scenario("deploy", direct_messages_module)
    scenario.h1("Direct Messages - Deployment")

    MULTISIG_ADDRESS = sp.address("KT1J9FYz29RBQi1oGLw8uXyACrzXzV1dHuvb")
    FEE_RECIPIENT_ADDRESS = sp.address("KT1J9FYz29RBQi1oGLw8uXyACrzXzV1dHuvb")
    MESSAGE_FEE = sp.mutez(100000)
    CONVERSATION_FEE = sp.mutez(100000)

    contract_metadata = sp.big_map(
        {
            "": sp.scenario_utils.bytes_of_string("ipfs://aaa"),
        }
    )

    contract = direct_messages_module.DirectMessages(
        multisig_address=MULTISIG_ADDRESS,
        fee_recipient=FEE_RECIPIENT_ADDRESS,
        message_fee=MESSAGE_FEE,
        conversation_fee=CONVERSATION_FEE,
        metadata=contract_metadata,
        counter=sp.nat(0),
    )
    scenario += contract




# ==============================================================================
# token gated Tests
# ==============================================================================


# --- Test: Token holder posts ---

@sp.add_test()
def test_token_holder_posts():
    """Test that token holders can post messages."""
    scenario = sp.test_scenario("token_holder_posts", [mock_multisig_module, mock_fa2_module, token_gate_module])
    scenario.h1("Token Holder Posts")
    admin, alice, bob, charlie, multisig, fa2, contract = _setup(scenario)

    # Give Alice token 0
    fa2.set_balance(sp.record(owner=alice.address, token_id=sp.nat(0), balance=sp.nat(1)), _sender=admin)

    # Alice posts to token 0's room
    scenario.h2("Alice posts (holds token)")
    contract.post_message(
        sp.record(
            fa2_address=fa2.address,
            token_id=sp.nat(0),
            content=sp.bytes("0x48656c6c6f"),
            parent_id=sp.none,
        ),
        _sender=alice,
    )

    # Room should be created
    scenario.verify(contract.data.rooms[1].message_count == 1)
    scenario.verify(contract.data.messages[1].sender == alice.address)
    scenario.verify(contract.data.messages[1].room_id == 1)

    # Room key lookup works
    room_id_result = sp.View(contract, "get_room_id")(
        sp.record(fa2_address=fa2.address, token_id=sp.nat(0))
    )
    scenario.verify(room_id_result == sp.Some(sp.nat(1)))


# --- Test: Non-holder rejected ---

@sp.add_test()
def test_non_holder_rejected():
    """Test that non-holders cannot post."""
    scenario = sp.test_scenario("non_holder_rejected", [mock_multisig_module, mock_fa2_module, token_gate_module])
    scenario.h1("Non-Holder Rejected")
    admin, alice, bob, charlie, multisig, fa2, contract = _setup(scenario)

    # Bob has no tokens
    scenario.h2("Bob rejected (no tokens)")
    contract.post_message(
        sp.record(
            fa2_address=fa2.address,
            token_id=sp.nat(0),
            content=sp.bytes("0x4e6f7065"),
            parent_id=sp.none,
        ),
        _sender=bob,
        _valid=False,
        _exception="NOT_TOKEN_HOLDER",
    )


# --- Test: Multiple holders same room ---

@sp.add_test()
def test_multiple_holders():
    """Test multiple holders posting to the same room."""
    scenario = sp.test_scenario("multiple_holders", [mock_multisig_module, mock_fa2_module, token_gate_module])
    scenario.h1("Multiple Holders")
    admin, alice, bob, charlie, multisig, fa2, contract = _setup(scenario)

    # Give tokens
    fa2.set_balance(sp.record(owner=alice.address, token_id=sp.nat(0), balance=sp.nat(1)), _sender=admin)
    fa2.set_balance(sp.record(owner=bob.address, token_id=sp.nat(0), balance=sp.nat(3)), _sender=admin)

    # Both post
    contract.post_message(
        sp.record(fa2_address=fa2.address, token_id=sp.nat(0), content=sp.bytes("0x416c696365"), parent_id=sp.none),
        _sender=alice,
    )
    contract.post_message(
        sp.record(fa2_address=fa2.address, token_id=sp.nat(0), content=sp.bytes("0x426f62"), parent_id=sp.none),
        _sender=bob,
    )

    # Same room, 2 messages
    scenario.verify(contract.data.rooms[1].message_count == 2)
    scenario.verify(contract.data.messages[1].sender == alice.address)
    scenario.verify(contract.data.messages[2].sender == bob.address)


# --- Test: Different tokens, different rooms ---

@sp.add_test()
def test_different_rooms():
    """Test that different tokens get different rooms."""
    scenario = sp.test_scenario("different_rooms", [mock_multisig_module, mock_fa2_module, token_gate_module])
    scenario.h1("Different Rooms")
    admin, alice, bob, charlie, multisig, fa2, contract = _setup(scenario)

    fa2.set_balance(sp.record(owner=alice.address, token_id=sp.nat(0), balance=sp.nat(1)), _sender=admin)
    fa2.set_balance(sp.record(owner=alice.address, token_id=sp.nat(1), balance=sp.nat(1)), _sender=admin)

    # Post to token 0
    contract.post_message(
        sp.record(fa2_address=fa2.address, token_id=sp.nat(0), content=sp.bytes("0x526f6f6d30"), parent_id=sp.none),
        _sender=alice,
    )

    # Post to token 1
    contract.post_message(
        sp.record(fa2_address=fa2.address, token_id=sp.nat(1), content=sp.bytes("0x526f6f6d31"), parent_id=sp.none),
        _sender=alice,
    )

    # Two different rooms
    scenario.verify(contract.data.rooms[1].message_count == 1)
    scenario.verify(contract.data.rooms[2].message_count == 1)
    scenario.verify(contract.data.messages[1].room_id == 1)
    scenario.verify(contract.data.messages[2].room_id == 2)


# --- Test: Replies ---

@sp.add_test()
def test_replies():
    """Test reply functionality in token rooms."""
    scenario = sp.test_scenario("tg_replies", [mock_multisig_module, mock_fa2_module, token_gate_module])
    scenario.h1("Replies")
    admin, alice, bob, charlie, multisig, fa2, contract = _setup(scenario)

    fa2.set_balance(sp.record(owner=alice.address, token_id=sp.nat(0), balance=sp.nat(1)), _sender=admin)
    fa2.set_balance(sp.record(owner=bob.address, token_id=sp.nat(0), balance=sp.nat(1)), _sender=admin)

    # Top-level message
    contract.post_message(
        sp.record(fa2_address=fa2.address, token_id=sp.nat(0), content=sp.bytes("0x48656c6c6f"), parent_id=sp.none),
        _sender=alice,
    )
    scenario.verify(~contract.data.messages[1].parent_id.is_some())

    # Reply
    contract.post_message(
        sp.record(fa2_address=fa2.address, token_id=sp.nat(0), content=sp.bytes("0x5265706c79"), parent_id=sp.Some(sp.nat(1))),
        _sender=bob,
    )
    scenario.verify(contract.data.messages[2].parent_id.is_some())

    # Reply to non-existent message
    contract.post_message(
        sp.record(fa2_address=fa2.address, token_id=sp.nat(0), content=sp.bytes("0x4e6f"), parent_id=sp.Some(sp.nat(999))),
        _sender=alice,
        _valid=False,
        _exception="PARENT_NOT_FOUND",
    )


# --- Test: Delete message ---

@sp.add_test()
def test_delete_message():
    """Test message deletion — sender only."""
    scenario = sp.test_scenario("tg_delete", [mock_multisig_module, mock_fa2_module, token_gate_module])
    scenario.h1("Delete Message")
    admin, alice, bob, charlie, multisig, fa2, contract = _setup(scenario)

    fa2.set_balance(sp.record(owner=alice.address, token_id=sp.nat(0), balance=sp.nat(1)), _sender=admin)
    fa2.set_balance(sp.record(owner=bob.address, token_id=sp.nat(0), balance=sp.nat(1)), _sender=admin)

    contract.post_message(
        sp.record(fa2_address=fa2.address, token_id=sp.nat(0), content=sp.bytes("0x4869"), parent_id=sp.none),
        _sender=alice,
    )

    # Bob cannot delete Alice's message
    contract.delete_message(sp.nat(1), _sender=bob, _valid=False, _exception="NOT_AUTHORIZED")

    # Alice deletes her own message
    contract.delete_message(sp.nat(1), _sender=alice)
    scenario.verify(~contract.data.messages.contains(sp.nat(1)))
    scenario.verify(contract.data.rooms[1].message_count == 0)


# --- Test: Edge cases ---

@sp.add_test()
def test_edge_cases():
    """Test edge cases."""
    scenario = sp.test_scenario("tg_edge_cases", [mock_multisig_module, mock_fa2_module, token_gate_module])
    scenario.h1("Edge Cases")
    admin, alice, bob, charlie, multisig, fa2, contract = _setup(scenario)

    fa2.set_balance(sp.record(owner=alice.address, token_id=sp.nat(0), balance=sp.nat(1)), _sender=admin)

    # Empty content
    contract.post_message(
        sp.record(fa2_address=fa2.address, token_id=sp.nat(0), content=sp.bytes("0x"), parent_id=sp.none),
        _sender=alice,
        _valid=False,
        _exception="EMPTY_CONTENT",
    )

    # Non-existent room lookup returns None
    room_id_result = sp.View(contract, "get_room_id")(
        sp.record(fa2_address=fa2.address, token_id=sp.nat(999))
    )
    scenario.verify(~room_id_result.is_some())

    # Delete non-existent message
    contract.delete_message(sp.nat(999), _sender=alice, _valid=False, _exception="MESSAGE_NOT_FOUND")


# --- Test: Fees ---

@sp.add_test()
def test_fees():
    """Test message fees."""
    scenario = sp.test_scenario("tg_fees", [mock_multisig_module, mock_fa2_module, token_gate_module])
    scenario.h1("Fees")
    admin = sp.test_account("Admin")
    alice = sp.test_account("Alice")

    multisig = mock_multisig_module.MockMultisig(
        users={admin.address},
        minimum_votes=sp.nat(1),
        expiration_time=sp.nat(30),
    )
    scenario += multisig

    fa2 = mock_fa2_module.MockFA2()
    scenario += fa2

    contract = token_gate_module.TokenGate(
        multisig_address=multisig.address,
        fee_recipient=admin.address,
        message_fee=sp.mutez(100),
        metadata=sp.big_map({"": sp.scenario_utils.bytes_of_string("ipfs://test")}),
        counter=sp.nat(0),
    )
    scenario += contract

    fa2.set_balance(sp.record(owner=alice.address, token_id=sp.nat(0), balance=sp.nat(1)), _sender=admin)

    # Wrong fee
    contract.post_message(
        sp.record(fa2_address=fa2.address, token_id=sp.nat(0), content=sp.bytes("0x4869"), parent_id=sp.none),
        _sender=alice,
        _amount=sp.mutez(0),
        _valid=False,
        _exception="INCORRECT_FEE",
    )

    # Correct fee
    contract.post_message(
        sp.record(fa2_address=fa2.address, token_id=sp.nat(0), content=sp.bytes("0x4869"), parent_id=sp.none),
        _sender=alice,
        _amount=sp.mutez(100),
    )



@sp.add_test()
def deploy():
    """Deployment scenario."""
    scenario = sp.test_scenario("deploy", token_gate_module)
    scenario.h1("Token Gate - Deployment")

    MULTISIG_ADDRESS = sp.address("KT1J9FYz29RBQi1oGLw8uXyACrzXzV1dHuvb")
    FEE_RECIPIENT_ADDRESS = sp.address("KT1J9FYz29RBQi1oGLw8uXyACrzXzV1dHuvb")
    MESSAGE_FEE = sp.mutez(0)

    contract_metadata = sp.big_map(
        {
            "": sp.scenario_utils.bytes_of_string("ipfs://aaa"),
        }
    )

    contract = token_gate_module.TokenGate(
        multisig_address=MULTISIG_ADDRESS,
        fee_recipient=FEE_RECIPIENT_ADDRESS,
        message_fee=MESSAGE_FEE,
        metadata=contract_metadata,
        counter=sp.nat(0),
    )
    scenario += contract

# ==============================================================================
# channel tests
# ==============================================================================


# ==============================================================================
# Mock Multisig for Testing
# ==============================================================================


@sp.module
def mock_multisig_module():
    class MockMultisig(sp.Contract):
        def __init__(self, users, minimum_votes, expiration_time):
            self.data.users = sp.cast(users, sp.set[sp.address])
            self.data.minimum_votes = sp.cast(minimum_votes, sp.nat)
            self.data.expiration_time = sp.cast(expiration_time, sp.nat)

        @sp.onchain_view()
        def is_user(self, address):
            sp.cast(address, sp.address)
            return address in self.data.users

        @sp.onchain_view()
        def get_minimum_votes(self):
            return self.data.minimum_votes

        @sp.onchain_view()
        def get_expiration_time(self):
            return self.data.expiration_time


# ==============================================================================
# Tests
# ==============================================================================


def _setup(scenario, message_fee=sp.mutez(0), channel_fee=sp.mutez(0)):
    """Shared test setup."""
    admin = sp.test_account("Admin")
    alice = sp.test_account("Alice")
    bob = sp.test_account("Bob")
    charlie = sp.test_account("Charlie")
    dave = sp.test_account("Dave")

    multisig = mock_multisig_module.MockMultisig(
        users=sp.set([admin.address]),
        minimum_votes=sp.nat(1),
        expiration_time=sp.nat(7),
    )
    scenario += multisig

    contract = channel_merkle_module.ChannelMerkle(
        multisig_address=multisig.address,
        fee_recipient=admin.address,
        message_fee=message_fee,
        channel_fee=channel_fee,
        metadata=sp.big_map(),
        counter=sp.nat(0),
    )
    scenario += contract

    return admin, alice, bob, charlie, dave, multisig, contract


# --- Test 1: Create channel ---

@sp.add_test()
def test_create_channel():
    """Test creating channels."""
    scenario = sp.test_scenario("create_channel", [mock_multisig_module, channel_merkle_module])
    scenario.h1("Create Channel")
    admin, alice, bob, charlie, dave, multisig, contract = _setup(scenario)

    # Alice creates a channel
    scenario.h2("Alice creates channel")
    contract.create_channel(
        sp.bytes("0x697066733a2f2f6d657461"),
        _sender=alice,
    )
    scenario.verify(contract.data.channels.contains(1))
    scenario.verify(contract.data.channels[1].creator == alice.address)
    scenario.verify(contract.data.channel_id_counter == 2)

    # Bob creates a channel
    scenario.h2("Bob creates channel")
    contract.create_channel(
        sp.bytes("0x697066733a2f2f626f62"),
        _sender=bob,
    )
    scenario.verify(contract.data.channels.contains(2))
    scenario.verify(contract.data.channel_id_counter == 3)

    # Empty metadata fails
    scenario.h2("Empty metadata fails")
    contract.create_channel(
        sp.bytes("0x"),
        _sender=alice,
        _valid=False,
        _exception="EMPTY_METADATA",
    )


# --- Test 2: Post to open channel ---

@sp.add_test()
def test_post_open_channel():
    """Test posting to an open channel — anyone can post."""
    scenario = sp.test_scenario("post_open", [mock_multisig_module, channel_merkle_module])
    scenario.h1("Post to Open Channel")
    admin, alice, bob, charlie, dave, multisig, contract = _setup(scenario)

    contract.create_channel(sp.bytes("0x6d657461"), _sender=alice)

    # Anyone can post
    scenario.h2("Bob posts")
    contract.post_message(
        sp.record(
            channel_id=sp.nat(1),
            content=sp.bytes("0x48656c6c6f"),
            proof=sp.none,
            parent_id=sp.none,
        ),
        _sender=bob,
    )
    scenario.verify(contract.data.messages[1].sender == bob.address)
    scenario.verify(contract.data.messages[1].channel_id == 1)

    channel = sp.View(contract, "get_channel")(sp.nat(1))
    scenario.verify(channel.message_count == 1)

    # Charlie posts
    contract.post_message(
        sp.record(channel_id=sp.nat(1), content=sp.bytes("0x576f726c64"), proof=sp.none, parent_id=sp.none),
        _sender=charlie,
    )
    scenario.verify(contract.data.message_id_counter == 3)


# --- Test 3: Configure channel as allowlist ---

@sp.add_test()
def test_configure_allowlist():
    """Test configuring a channel with allowlist mode."""
    scenario = sp.test_scenario("configure_allowlist", [mock_multisig_module, channel_merkle_module])
    scenario.h1("Configure Channel - Allowlist")
    admin, alice, bob, charlie, dave, multisig, contract = _setup(scenario)

    contract.create_channel(sp.bytes("0x6d657461"), _sender=alice)

    # Only creator can configure
    scenario.h2("Non-creator cannot configure")
    contract.configure_channel(
        sp.record(
            channel_id=sp.nat(1),
            access_mode=sp.variant.allowlist(()),
            merkle_root=sp.Some(sp.bytes("0x" + "aa" * 32)),
            merkle_uri=sp.Some(sp.bytes("0x697066733a2f2f6c697374")),
        ),
        _sender=bob,
        _valid=False,
        _exception="NOT_CHANNEL_ADMIN",
    )

    # Creator configures allowlist
    scenario.h2("Creator sets allowlist")
    contract.configure_channel(
        sp.record(
            channel_id=sp.nat(1),
            access_mode=sp.variant.allowlist(()),
            merkle_root=sp.Some(sp.bytes("0x" + "aa" * 32)),
            merkle_uri=sp.Some(sp.bytes("0x697066733a2f2f6c697374")),
        ),
        _sender=alice,
    )
    scenario.verify(contract.data.channels[1].merkle_root.is_some())
    scenario.verify(contract.data.channels[1].merkle_root.is_some())

    # Allowlist without root fails
    scenario.h2("Allowlist without root fails")
    contract.configure_channel(
        sp.record(
            channel_id=sp.nat(1),
            access_mode=sp.variant.allowlist(()),
            merkle_root=sp.none,
            merkle_uri=sp.none,
        ),
        _sender=alice,
        _valid=False,
        _exception="ALLOWLIST_NEEDS_ROOT",
    )

    # Open with root fails
    scenario.h2("Open mode with root fails")
    contract.configure_channel(
        sp.record(
            channel_id=sp.nat(1),
            access_mode=sp.variant.unrestricted(()),
            merkle_root=sp.Some(sp.bytes("0x" + "aa" * 32)),
            merkle_uri=sp.none,
        ),
        _sender=alice,
        _valid=False,
        _exception="UNRESTRICTED_NO_ROOT",
    )

    # Blocklist with root fails
    scenario.h2("Blocklist with root fails")
    contract.configure_channel(
        sp.record(
            channel_id=sp.nat(1),
            access_mode=sp.variant.blocklist(()),
            merkle_root=sp.Some(sp.bytes("0x" + "aa" * 32)),
            merkle_uri=sp.none,
        ),
        _sender=alice,
        _valid=False,
        _exception="BLOCKLIST_NO_ROOT",
    )

    # Back to open
    scenario.h2("Back to open")
    contract.configure_channel(
        sp.record(
            channel_id=sp.nat(1),
            access_mode=sp.variant.unrestricted(()),
            merkle_root=sp.none,
            merkle_uri=sp.none,
        ),
        _sender=alice,
    )
    scenario.verify(~contract.data.channels[1].merkle_root.is_some())


# We use a helper contract to compute Merkle leaves and roots on-chain,
# since sp.pack() uses Michelson encoding that can't be replicated in Python.

@sp.module
def merkle_helper_module():
    """Helper contract to compute Merkle leaves, intermediate nodes, and roots for testing."""

    class MerkleHelper(sp.Contract):
        def __init__(self):
            self.data.leaf1 = sp.bytes("0x")
            self.data.leaf2 = sp.bytes("0x")
            self.data.leaf3 = sp.bytes("0x")
            self.data.left_node = sp.bytes("0x")   # blake2b(leaf1 + leaf2)
            self.data.right_node = sp.bytes("0x")   # blake2b(leaf3 + leaf3)
            self.data.root_2 = sp.bytes("0x")
            self.data.root_3 = sp.bytes("0x")

        @sp.entrypoint
        def compute_leaves(self, params):
            sp.cast(params, sp.record(addr1=sp.address, addr2=sp.address, addr3=sp.address))
            self.data.leaf1 = sp.blake2b(sp.pack(params.addr1))
            self.data.leaf2 = sp.blake2b(sp.pack(params.addr2))
            self.data.leaf3 = sp.blake2b(sp.pack(params.addr3))

            # 2-leaf tree: root = blake2b(leaf1 + leaf2)
            self.data.root_2 = sp.blake2b(self.data.leaf1 + self.data.leaf2)

            # 3-leaf tree:
            #         root_3
            #        /      \
            #   left_node   right_node
            #    / \          / \
            # leaf1 leaf2  leaf3 leaf3
            self.data.left_node = sp.blake2b(self.data.leaf1 + self.data.leaf2)
            self.data.right_node = sp.blake2b(self.data.leaf3 + self.data.leaf3)
            self.data.root_3 = sp.blake2b(self.data.left_node + self.data.right_node)


@sp.add_test()
def test_merkle_allowlist_full():
    """Full Merkle allowlist test using helper to compute roots."""
    scenario = sp.test_scenario(
        "merkle_allowlist_full",
        [mock_multisig_module, channel_merkle_module, merkle_helper_module],
    )
    scenario.h1("Merkle Allowlist - Full Test")
    admin, alice, bob, charlie, dave, multisig, contract = _setup(scenario)

    # Use helper to compute leaves and root
    helper = merkle_helper_module.MerkleHelper()
    scenario += helper

    helper.compute_leaves(
        addr1=bob.address,
        addr2=charlie.address,
        addr3=dave.address,
        _sender=admin,
    )

    # Create channel
    contract.create_channel(sp.bytes("0x6d657461"), _sender=alice)

    # Configure as allowlist with 2-leaf root (bob + charlie)
    scenario.h2("Configure allowlist: bob + charlie")
    contract.configure_channel(
        sp.record(
            channel_id=sp.nat(1),
            access_mode=sp.variant.allowlist(()),
            merkle_root=sp.Some(helper.data.root_2),
            merkle_uri=sp.Some(sp.bytes("0x697066733a2f2f6c697374")),
        ),
        _sender=alice,
    )

    # Bob posts with valid proof: [{hash: leaf_charlie, direction: 1}]
    scenario.h2("Bob posts with valid proof")
    contract.post_message(
        sp.record(
            channel_id=sp.nat(1),
            content=sp.bytes("0x48656c6c6f"),
            proof=sp.Some([sp.record(hash=helper.data.leaf2, direction=sp.nat(1))]),
            parent_id=sp.none,
        ),
        _sender=bob,
    )
    scenario.verify(contract.data.messages[1].sender == bob.address)

    # Charlie posts with valid proof: [{hash: leaf_bob, direction: 0}]
    scenario.h2("Charlie posts with valid proof")
    contract.post_message(
        sp.record(
            channel_id=sp.nat(1),
            content=sp.bytes("0x576f726c64"),
            proof=sp.Some([sp.record(hash=helper.data.leaf1, direction=sp.nat(0))]),
            parent_id=sp.none,
        ),
        _sender=charlie,
    )
    scenario.verify(contract.data.messages[2].sender == charlie.address)

    # Dave is NOT in the allowlist — posts with empty proof, should fail
    scenario.h2("Dave rejected — not in allowlist (empty proof)")
    contract.post_message(
        sp.record(
            channel_id=sp.nat(1),
            content=sp.bytes("0x4e6f7065"),
            proof=sp.Some([]),
            parent_id=sp.none,
        ),
        _sender=dave,
        _valid=False,
        _exception="INVALID_MERKLE_PROOF",
    )

    # Dave tries with bob's proof — should fail (wrong leaf)
    scenario.h2("Dave rejected — wrong proof")
    contract.post_message(
        sp.record(
            channel_id=sp.nat(1),
            content=sp.bytes("0x4e6f7065"),
            proof=sp.Some([sp.record(hash=helper.data.leaf2, direction=sp.nat(1))]),
            parent_id=sp.none,
        ),
        _sender=dave,
        _valid=False,
        _exception="INVALID_MERKLE_PROOF",
    )

    # Post without proof when allowlist is set — fails
    scenario.h2("No proof when allowlist active — fails")
    contract.post_message(
        sp.record(
            channel_id=sp.nat(1),
            content=sp.bytes("0x4e6f7065"),
            proof=sp.none,
            parent_id=sp.none,
        ),
        _sender=bob,
        _valid=False,
        _exception="PROOF_REQUIRED",
    )

    # Clear allowlist — back to open
    scenario.h2("Clear allowlist — back to open")
    contract.configure_channel(
        sp.record(
            channel_id=sp.nat(1),
            access_mode=sp.variant.unrestricted(()),
            merkle_root=sp.none,
            merkle_uri=sp.none,
        ),
        _sender=alice,
    )

    # Dave can now post (open channel)
    scenario.h2("Dave posts to open channel")
    contract.post_message(
        sp.record(
            channel_id=sp.nat(1),
            content=sp.bytes("0x4f70656e"),
            proof=sp.none,
            parent_id=sp.none,
        ),
        _sender=dave,
    )
    scenario.verify(contract.data.messages[3].sender == dave.address)


# --- Test: 3-leaf Merkle tree ---

@sp.add_test()
def test_merkle_three_leaves():
    """Test Merkle proof with 3 leaves (odd count — last node duplicated)."""
    scenario = sp.test_scenario(
        "merkle_3_leaves",
        [mock_multisig_module, channel_merkle_module, merkle_helper_module],
    )
    scenario.h1("Merkle Allowlist - 3 Leaves")
    admin, alice, bob, charlie, dave, multisig, contract = _setup(scenario)

    helper = merkle_helper_module.MerkleHelper()
    scenario += helper

    helper.compute_leaves(
        addr1=bob.address,
        addr2=charlie.address,
        addr3=dave.address,
        _sender=admin,
    )

    contract.create_channel(sp.bytes("0x6d657461"), _sender=alice)

    # Configure with 3-leaf root (bob, charlie, dave)
    scenario.h2("Configure allowlist: bob + charlie + dave")
    contract.configure_channel(
        sp.record(
            channel_id=sp.nat(1),
            access_mode=sp.variant.allowlist(()),
            merkle_root=sp.Some(helper.data.root_3),
            merkle_uri=sp.Some(sp.bytes("0x697066733a2f2f6c697374")),
        ),
        _sender=alice,
    )

    # 3-leaf tree structure:
    #         root_3
    #        /      \
    #   left_node   right_node
    #    / \          / \
    # leaf1 leaf2  leaf3 leaf3  (leaf3 duplicated)

    # Bob (leaf1, index 0) proof:
    #   Step 1: sibling=leaf2, direction=1 → compute left_node
    #   Step 2: sibling=right_node, direction=1 → compute root
    scenario.h2("Bob posts with 3-leaf proof")
    contract.post_message(
        sp.record(
            channel_id=sp.nat(1),
            content=sp.bytes("0x426f62"),
            proof=sp.Some([
                sp.record(hash=helper.data.leaf2, direction=sp.nat(1)),
                sp.record(hash=helper.data.right_node, direction=sp.nat(1)),
            ]),
            parent_id=sp.none,
        ),
        _sender=bob,
    )
    scenario.verify(contract.data.messages[1].sender == bob.address)

    # Charlie (leaf2, index 1) proof:
    #   Step 1: sibling=leaf1, direction=0 → compute left_node
    #   Step 2: sibling=right_node, direction=1 → compute root
    scenario.h2("Charlie posts with 3-leaf proof")
    contract.post_message(
        sp.record(
            channel_id=sp.nat(1),
            content=sp.bytes("0x436861726c6965"),
            proof=sp.Some([
                sp.record(hash=helper.data.leaf1, direction=sp.nat(0)),
                sp.record(hash=helper.data.right_node, direction=sp.nat(1)),
            ]),
            parent_id=sp.none,
        ),
        _sender=charlie,
    )
    scenario.verify(contract.data.messages[2].sender == charlie.address)

    # Dave (leaf3, index 2) proof:
    #   Step 1: sibling=leaf3, direction=1 (duplicated) → compute right_node
    #   Step 2: sibling=left_node, direction=0 → compute root
    scenario.h2("Dave posts with 3-leaf proof")
    contract.post_message(
        sp.record(
            channel_id=sp.nat(1),
            content=sp.bytes("0x44617665"),
            proof=sp.Some([
                sp.record(hash=helper.data.leaf3, direction=sp.nat(1)),
                sp.record(hash=helper.data.left_node, direction=sp.nat(0)),
            ]),
            parent_id=sp.none,
        ),
        _sender=dave,
    )
    scenario.verify(contract.data.messages[3].sender == dave.address)

    # Admin is NOT in the tree — rejected
    scenario.h2("Admin rejected — not in allowlist")
    contract.post_message(
        sp.record(
            channel_id=sp.nat(1),
            content=sp.bytes("0x4e6f7065"),
            proof=sp.Some([
                sp.record(hash=helper.data.leaf2, direction=sp.nat(1)),
                sp.record(hash=helper.data.right_node, direction=sp.nat(1)),
            ]),
            parent_id=sp.none,
        ),
        _sender=admin,
        _valid=False,
        _exception="INVALID_MERKLE_PROOF",
    )


# --- Test: Blocklist ---

@sp.add_test()
def test_blocklist():
    """Test blocklist mode — blocked addresses rejected."""
    scenario = sp.test_scenario("blocklist", [mock_multisig_module, channel_merkle_module])
    scenario.h1("Blocklist")
    admin, alice, bob, charlie, dave, multisig, contract = _setup(scenario)

    contract.create_channel(sp.bytes("0x6d657461"), _sender=alice)

    # Configure as blocklist
    scenario.h2("Configure as blocklist")
    contract.configure_channel(
        sp.record(
            channel_id=sp.nat(1),
            access_mode=sp.variant.blocklist(()),
            merkle_root=sp.none,
            merkle_uri=sp.none,
        ),
        _sender=alice,
    )

    # Anyone can post initially
    contract.post_message(
        sp.record(channel_id=sp.nat(1), content=sp.bytes("0x4869"), proof=sp.none, parent_id=sp.none),
        _sender=bob,
    )
    scenario.verify(contract.data.messages[1].sender == bob.address)

    # Block Bob
    scenario.h2("Block Bob")
    contract.update_blocklist(
        sp.record(
            channel_id=sp.nat(1),
            to_block=[bob.address],
            to_unblock=[],
        ),
        _sender=alice,
    )

    # Bob is blocked
    scenario.h2("Bob cannot post")
    contract.post_message(
        sp.record(channel_id=sp.nat(1), content=sp.bytes("0x4e6f7065"), proof=sp.none, parent_id=sp.none),
        _sender=bob,
        _valid=False,
        _exception="ADDRESS_BLOCKED",
    )

    # Charlie can still post
    scenario.h2("Charlie can still post")
    contract.post_message(
        sp.record(channel_id=sp.nat(1), content=sp.bytes("0x596573"), proof=sp.none, parent_id=sp.none),
        _sender=charlie,
    )

    # Verify is_blocked view
    blocked_result = sp.View(contract, "is_blocked")(
        sp.record(channel_id=sp.nat(1), address=bob.address)
    )
    scenario.verify(blocked_result == True)

    not_blocked_result = sp.View(contract, "is_blocked")(
        sp.record(channel_id=sp.nat(1), address=charlie.address)
    )
    scenario.verify(not_blocked_result == False)

    # Unblock Bob
    scenario.h2("Unblock Bob")
    contract.update_blocklist(
        sp.record(
            channel_id=sp.nat(1),
            to_block=[],
            to_unblock=[bob.address],
        ),
        _sender=alice,
    )

    # Bob can post again
    scenario.h2("Bob can post again")
    contract.post_message(
        sp.record(channel_id=sp.nat(1), content=sp.bytes("0x4261636b"), proof=sp.none, parent_id=sp.none),
        _sender=bob,
    )

    # Non-creator cannot update blocklist
    scenario.h2("Non-creator cannot update blocklist")
    contract.update_blocklist(
        sp.record(channel_id=sp.nat(1), to_block=[dave.address], to_unblock=[]),
        _sender=bob,
        _valid=False,
        _exception="NOT_CHANNEL_ADMIN",
    )

    # Cannot update blocklist when not in blocklist mode
    scenario.h2("Cannot update blocklist in open mode")
    contract.configure_channel(
        sp.record(
            channel_id=sp.nat(1),
            access_mode=sp.variant.unrestricted(()),
            merkle_root=sp.none,
            merkle_uri=sp.none,
        ),
        _sender=alice,
    )
    contract.update_blocklist(
        sp.record(channel_id=sp.nat(1), to_block=[bob.address], to_unblock=[]),
        _sender=alice,
        _valid=False,
        _exception="NOT_BLOCKLIST_MODE",
    )


# --- Test: Delete message ---

@sp.add_test()
def test_delete_message():
    """Test message deletion — sender and creator can delete."""
    scenario = sp.test_scenario("delete_message", [mock_multisig_module, channel_merkle_module])
    scenario.h1("Delete Message")
    admin, alice, bob, charlie, dave, multisig, contract = _setup(scenario)

    contract.create_channel(sp.bytes("0x6d657461"), _sender=alice)

    # Bob posts
    contract.post_message(
        sp.record(channel_id=sp.nat(1), content=sp.bytes("0x4869"), proof=sp.none, parent_id=sp.none),
        _sender=bob,
    )

    # Charlie cannot delete Bob's message
    scenario.h2("Non-author/non-creator cannot delete")
    contract.delete_message(sp.nat(1), _sender=charlie, _valid=False, _exception="NOT_AUTHORIZED")

    # Bob deletes his own
    scenario.h2("Sender deletes own message")
    contract.delete_message(sp.nat(1), _sender=bob)
    scenario.verify(~contract.data.messages.contains(1))

    # Post another
    contract.post_message(
        sp.record(channel_id=sp.nat(1), content=sp.bytes("0x576f726c64"), proof=sp.none, parent_id=sp.none),
        _sender=bob,
    )

    # Alice (creator) moderates
    scenario.h2("Creator moderates")
    contract.delete_message(sp.nat(2), _sender=alice)
    scenario.verify(~contract.data.messages.contains(2))


# --- Test: Update channel metadata ---

@sp.add_test()
def test_update_channel():
    """Test channel metadata update — creator only."""
    scenario = sp.test_scenario("update_channel", [mock_multisig_module, channel_merkle_module])
    scenario.h1("Update Channel")
    admin, alice, bob, charlie, dave, multisig, contract = _setup(scenario)

    contract.create_channel(sp.bytes("0x6f6c64"), _sender=alice)

    # Non-creator fails
    contract.update_channel(
        sp.record(channel_id=sp.nat(1), metadata_uri=sp.bytes("0x6e6577")),
        _sender=bob,
        _valid=False,
        _exception="NOT_CHANNEL_CREATOR",
    )

    # Creator updates
    contract.update_channel(
        sp.record(channel_id=sp.nat(1), metadata_uri=sp.bytes("0x6e6577")),
        _sender=alice,
    )
    channel = sp.View(contract, "get_channel")(sp.nat(1))
    scenario.verify(channel.metadata_uri == sp.bytes("0x6e6577"))


# --- Test: Hide and delete channel ---

@sp.add_test()
def test_hide_and_delete_channel():
    """Test hiding and deleting a channel."""
    scenario = sp.test_scenario("hide_delete_channel", [mock_multisig_module, channel_merkle_module])
    scenario.h1("Hide & Delete Channel")
    admin, alice, bob, charlie, dave, multisig, contract = _setup(scenario)

    contract.create_channel(sp.bytes("0x6d657461"), _sender=alice)

    # Post a message first
    contract.post_message(
        sp.record(channel_id=sp.nat(1), content=sp.bytes("0x4869"), proof=sp.none, parent_id=sp.none),
        _sender=bob,
    )

    # Non-creator cannot hide
    scenario.h2("Non-creator cannot hide")
    contract.hide_channel(sp.nat(1), _sender=bob, _valid=False, _exception="NOT_CHANNEL_CREATOR")

    # Hide channel
    scenario.h2("Creator hides channel")
    contract.hide_channel(sp.nat(1), _sender=alice)
    scenario.verify(contract.data.channels[1].hidden == True)

    # Cannot post to hidden channel
    scenario.h2("Cannot post to hidden channel")
    contract.post_message(
        sp.record(channel_id=sp.nat(1), content=sp.bytes("0x4e6f"), proof=sp.none, parent_id=sp.none),
        _sender=bob,
        _valid=False,
        _exception="CHANNEL_HIDDEN",
    )

    # Cannot configure hidden channel
    scenario.h2("Cannot configure hidden channel")
    contract.configure_channel(
        sp.record(
            channel_id=sp.nat(1),
            access_mode=sp.variant.blocklist(()),
            merkle_root=sp.none,
            merkle_uri=sp.none,
        ),
        _sender=alice,
        _valid=False,
        _exception="CHANNEL_HIDDEN",
    )

    # Create another channel for delete test
    contract.create_channel(sp.bytes("0x6d65746132"), _sender=alice)

    # Non-creator cannot delete
    scenario.h2("Non-creator cannot delete channel")
    contract.delete_channel(sp.nat(2), _sender=bob, _valid=False, _exception="NOT_CHANNEL_CREATOR")

    # Creator deletes
    scenario.h2("Creator deletes channel")
    contract.delete_channel(sp.nat(2), _sender=alice)
    scenario.verify(~contract.data.channels.contains(2))


# --- Test: Fee enforcement ---

@sp.add_test()
def test_fee_enforcement():
    """Test channel and message fees."""
    scenario = sp.test_scenario("fees", [mock_multisig_module, channel_merkle_module])
    scenario.h1("Fee Enforcement")
    admin, alice, bob, charlie, dave, multisig, contract = _setup(
        scenario, message_fee=sp.mutez(100), channel_fee=sp.mutez(500)
    )

    # Create without fee fails
    contract.create_channel(
        sp.bytes("0x6d657461"),
        _sender=alice,
        _amount=sp.mutez(0),
        _valid=False,
        _exception="INCORRECT_FEE",
    )

    # Create with correct fee
    contract.create_channel(sp.bytes("0x6d657461"), _sender=alice, _amount=sp.mutez(500))

    # Post without fee fails
    contract.post_message(
        sp.record(channel_id=sp.nat(1), content=sp.bytes("0x4869"), proof=sp.none, parent_id=sp.none),
        _sender=bob,
        _amount=sp.mutez(0),
        _valid=False,
        _exception="INCORRECT_FEE",
    )

    # Post with correct fee
    contract.post_message(
        sp.record(channel_id=sp.nat(1), content=sp.bytes("0x4869"), proof=sp.none, parent_id=sp.none),
        _sender=bob,
        _amount=sp.mutez(100),
    )


# --- Test: Governance ---

@sp.add_test()
def test_governance():
    """Test governance: pause, fee changes."""
    scenario = sp.test_scenario("governance", [mock_multisig_module, channel_merkle_module])
    scenario.h1("Governance")
    admin, alice, bob, charlie, dave, multisig, contract = _setup(scenario)

    # Non-user cannot submit
    contract.submit_proposal(
        sp.variant.set_pause(True),
        _sender=alice,
        _valid=False,
        _exception="CHANNELS_NOT_MULTISIG_USER",
    )

    # Pause
    scenario.h2("Pause")
    contract.submit_proposal(sp.variant.set_pause(True), _sender=admin)
    contract.vote_proposal(proposal_id=sp.nat(0), approval=True, _sender=admin)
    contract.execute_proposal(sp.nat(0), _sender=admin)
    scenario.verify(contract.data.paused == True)

    # Cannot create when paused
    contract.create_channel(
        sp.bytes("0x6d657461"),
        _sender=alice,
        _valid=False,
        _exception="CONTRACT_PAUSED",
    )

    # Unpause
    scenario.h2("Unpause")
    contract.submit_proposal(sp.variant.set_pause(False), _sender=admin)
    contract.vote_proposal(proposal_id=sp.nat(1), approval=True, _sender=admin)
    contract.execute_proposal(sp.nat(1), _sender=admin)
    scenario.verify(contract.data.paused == False)

    # Set fees
    scenario.h2("Set channel fee")
    contract.submit_proposal(sp.variant.set_channel_fee(sp.mutez(1000)), _sender=admin)
    contract.vote_proposal(proposal_id=sp.nat(2), approval=True, _sender=admin)
    contract.execute_proposal(sp.nat(2), _sender=admin)
    scenario.verify(sp.View(contract, "get_channel_fee")() == sp.mutez(1000))


# --- Test: Validation edge cases ---

@sp.add_test()
def test_validation():
    """Test input validation edge cases."""
    scenario = sp.test_scenario("validation", [mock_multisig_module, channel_merkle_module])
    scenario.h1("Validation")
    admin, alice, bob, charlie, dave, multisig, contract = _setup(scenario)

    contract.create_channel(sp.bytes("0x6d657461"), _sender=alice)

    # Empty content
    scenario.h2("Empty content fails")
    contract.post_message(
        sp.record(channel_id=sp.nat(1), content=sp.bytes("0x"), proof=sp.none, parent_id=sp.none),
        _sender=bob,
        _valid=False,
        _exception="EMPTY_CONTENT",
    )

    # Non-existent channel
    scenario.h2("Post to non-existent channel")
    contract.post_message(
        sp.record(channel_id=sp.nat(999), content=sp.bytes("0x4869"), proof=sp.none, parent_id=sp.none),
        _sender=bob,
        _valid=False,
        _exception="CHANNEL_NOT_FOUND",
    )

    # Delete non-existent message
    scenario.h2("Delete non-existent message")
    contract.delete_message(sp.nat(999), _sender=alice, _valid=False, _exception="MESSAGE_NOT_FOUND")

    # Hide non-existent channel
    scenario.h2("Hide non-existent channel")
    contract.hide_channel(sp.nat(999), _sender=alice, _valid=False, _exception="CHANNEL_NOT_FOUND")

    # Delete non-existent channel
    scenario.h2("Delete non-existent channel")
    contract.delete_channel(sp.nat(999), _sender=alice, _valid=False, _exception="CHANNEL_NOT_FOUND")


# --- Test: Channel Admins ---


@sp.add_test()
def test_channel_admins():
    """Test channel admin delegation."""
    scenario = sp.test_scenario("channel_admins", [mock_multisig_module, channel_merkle_module])
    scenario.h1("Channel Admins")
    admin, alice, bob, charlie, dave, multisig, contract = _setup(scenario)

    contract.create_channel(sp.bytes("0x6d657461"), _sender=alice)

    # Only creator can add admins
    scenario.h2("Non-creator cannot add admins")
    contract.update_channel_admins(
        sp.record(channel_id=sp.nat(1), to_add=[bob.address], to_remove=[]),
        _sender=bob,
        _valid=False,
        _exception="NOT_CHANNEL_CREATOR",
    )

    # Creator adds bob as admin
    scenario.h2("Creator adds Bob as admin")
    contract.update_channel_admins(
        sp.record(channel_id=sp.nat(1), to_add=[bob.address], to_remove=[]),
        _sender=alice,
    )

    # Verify via view
    is_admin_result = sp.View(contract, "is_channel_admin")(
        sp.record(channel_id=sp.nat(1), address=bob.address)
    )
    scenario.verify(is_admin_result)

    # Creator is also reported as admin
    is_creator_admin = sp.View(contract, "is_channel_admin")(
        sp.record(channel_id=sp.nat(1), address=alice.address)
    )
    scenario.verify(is_creator_admin)

    # Non-admin is not admin
    is_charlie_admin = sp.View(contract, "is_channel_admin")(
        sp.record(channel_id=sp.nat(1), address=charlie.address)
    )
    scenario.verify(~is_charlie_admin)

    # Admin can configure channel
    scenario.h2("Admin configures channel")
    contract.configure_channel(
        sp.record(
            channel_id=sp.nat(1),
            access_mode=sp.variant.blocklist(()),
            merkle_root=sp.none,
            merkle_uri=sp.none,
        ),
        _sender=bob,
    )

    # Admin can update blocklist
    scenario.h2("Admin updates blocklist")
    contract.update_blocklist(
        sp.record(channel_id=sp.nat(1), to_block=[dave.address], to_unblock=[]),
        _sender=bob,
    )

    # Admin can delete messages
    scenario.h2("Admin deletes message")
    contract.post_message(
        sp.record(channel_id=sp.nat(1), content=sp.bytes("0x4869"), proof=sp.none, parent_id=sp.none),
        _sender=charlie,
    )
    contract.delete_message(sp.nat(1), _sender=bob)
    scenario.verify(~contract.data.messages.contains(sp.nat(1)))

    # Non-admin cannot configure
    scenario.h2("Non-admin cannot configure")
    contract.configure_channel(
        sp.record(
            channel_id=sp.nat(1),
            access_mode=sp.variant.unrestricted(()),
            merkle_root=sp.none,
            merkle_uri=sp.none,
        ),
        _sender=charlie,
        _valid=False,
        _exception="NOT_CHANNEL_ADMIN",
    )

    # Admin cannot add other admins
    scenario.h2("Admin cannot add other admins")
    contract.update_channel_admins(
        sp.record(channel_id=sp.nat(1), to_add=[charlie.address], to_remove=[]),
        _sender=bob,
        _valid=False,
        _exception="NOT_CHANNEL_CREATOR",
    )

    # Admin cannot hide channel
    scenario.h2("Admin cannot hide channel")
    contract.hide_channel(sp.nat(1), _sender=bob, _valid=False, _exception="NOT_CHANNEL_CREATOR")

    # Admin cannot delete channel
    scenario.h2("Admin cannot delete channel")
    contract.delete_channel(sp.nat(1), _sender=bob, _valid=False, _exception="NOT_CHANNEL_CREATOR")

    # Creator removes admin
    scenario.h2("Creator removes Bob as admin")
    contract.update_channel_admins(
        sp.record(channel_id=sp.nat(1), to_add=[], to_remove=[bob.address]),
        _sender=alice,
    )

    # Bob can no longer configure
    scenario.h2("Removed admin cannot configure")
    contract.configure_channel(
        sp.record(
            channel_id=sp.nat(1),
            access_mode=sp.variant.unrestricted(()),
            merkle_root=sp.none,
            merkle_uri=sp.none,
        ),
        _sender=bob,
        _valid=False,
        _exception="NOT_CHANNEL_ADMIN",
    )


# --- Test: Message Replies ---


@sp.add_test()
def test_message_replies():
    """Test posting replies to messages."""
    scenario = sp.test_scenario("message_replies", [mock_multisig_module, channel_merkle_module])
    scenario.h1("Message Replies")
    admin, alice, bob, charlie, dave, multisig, contract = _setup(scenario)

    contract.create_channel(sp.bytes("0x6d657461"), _sender=alice)

    # 1. Post a top-level message
    scenario.h2("Post top-level message")
    contract.post_message(
        sp.record(channel_id=sp.nat(1), content=sp.bytes("0x48656c6c6f"), proof=sp.none, parent_id=sp.none),
        _sender=bob,
    )
    scenario.verify(contract.data.messages[1].sender == bob.address)
    scenario.verify(~contract.data.messages[1].parent_id.is_some())

    # 2. Reply to that message
    scenario.h2("Reply to message 1")
    contract.post_message(
        sp.record(channel_id=sp.nat(1), content=sp.bytes("0x5265706c79"), proof=sp.none, parent_id=sp.Some(sp.nat(1))),
        _sender=charlie,
    )
    scenario.verify(contract.data.messages[2].sender == charlie.address)
    scenario.verify(contract.data.messages[2].parent_id.is_some())

    # 3. Reply to a reply (flat threading)
    scenario.h2("Reply to a reply (flat)")
    contract.post_message(
        sp.record(channel_id=sp.nat(1), content=sp.bytes("0x5265706c7932"), proof=sp.none, parent_id=sp.Some(sp.nat(2))),
        _sender=dave,
    )
    scenario.verify(contract.data.messages[3].sender == dave.address)
    scenario.verify(contract.data.messages[3].parent_id.is_some())

    # 4. Reply to non-existent message → PARENT_NOT_FOUND
    scenario.h2("Reply to non-existent message")
    contract.post_message(
        sp.record(channel_id=sp.nat(1), content=sp.bytes("0x4e6f7065"), proof=sp.none, parent_id=sp.Some(sp.nat(999))),
        _sender=bob,
        _valid=False,
        _exception="PARENT_NOT_FOUND",
    )

    # 5. Reply to message in different channel → PARENT_WRONG_CHANNEL
    scenario.h2("Reply to message in different channel")
    contract.create_channel(sp.bytes("0x6d65746132"), _sender=alice)
    contract.post_message(
        sp.record(channel_id=sp.nat(2), content=sp.bytes("0x4e6f7065"), proof=sp.none, parent_id=sp.Some(sp.nat(1))),
        _sender=bob,
        _valid=False,
        _exception="PARENT_WRONG_CHANNEL",
    )

    # 6. Delete parent, replies remain
    scenario.h2("Delete parent — replies remain")
    contract.delete_message(sp.nat(1), _sender=bob)
    scenario.verify(~contract.data.messages.contains(sp.nat(1)))
    scenario.verify(contract.data.messages[2].sender == charlie.address)
    scenario.verify(contract.data.messages[3].sender == dave.address)

    # 7. Top-level post with parent_id = None works as before
    scenario.h2("Top-level post still works")
    contract.post_message(
        sp.record(channel_id=sp.nat(1), content=sp.bytes("0x546f70"), proof=sp.none, parent_id=sp.none),
        _sender=bob,
    )
    scenario.verify(contract.data.messages[4].sender == bob.address)
    scenario.verify(~contract.data.messages[4].parent_id.is_some())


# ==============================================================================
# Deployment Scenario
# ==============================================================================


@sp.add_test()
def deploy():
    """Deployment scenario."""
    scenario = sp.test_scenario("deploy", channel_merkle_module)
    scenario.h1("Channel Merkle - Deployment")

    MULTISIG_ADDRESS = sp.address("KT1J9FYz29RBQi1oGLw8uXyACrzXzV1dHuvb")
    FEE_RECIPIENT_ADDRESS = sp.address("KT1J9FYz29RBQi1oGLw8uXyACrzXzV1dHuvb")
    MESSAGE_FEE = sp.mutez(0)
    CHANNEL_FEE = sp.mutez(0)

    contract_metadata = sp.big_map(
        {
            "": sp.scenario_utils.bytes_of_string("ipfs://aaa"),
        }
    )

    contract = channel_merkle_module.ChannelMerkle(
        multisig_address=MULTISIG_ADDRESS,
        fee_recipient=FEE_RECIPIENT_ADDRESS,
        message_fee=MESSAGE_FEE,
        channel_fee=CHANNEL_FEE,
        metadata=contract_metadata,
        counter=sp.nat(0),
    )
    scenario += contract







@sp.add_test()
def channel_deploy():
    """Deployment scenario."""
    scenario = sp.test_scenario("channel_deploy", channels_module)
    scenario.h1("Channel Merkle - Deployment")

    MULTISIG_ADDRESS = sp.address("KT1J9FYz29RBQi1oGLw8uXyACrzXzV1dHuvb")
    FEE_RECIPIENT_ADDRESS = sp.address("KT1J9FYz29RBQi1oGLw8uXyACrzXzV1dHuvb")
    MESSAGE_FEE = sp.mutez(100000)
    CHANNEL_FEE = sp.mutez(100000)

    contract_metadata = sp.big_map(
        {
            "": sp.scenario_utils.bytes_of_string("ipfs://aaa"),
        }
    )

    contract = channels_module.Channels(
        multisig_address=MULTISIG_ADDRESS,
        fee_recipient=FEE_RECIPIENT_ADDRESS,
        message_fee=MESSAGE_FEE,
        channel_fee=CHANNEL_FEE,
        metadata=contract_metadata,
        counter=sp.nat(0),
    )
    scenario += contract



@sp.add_test()
def deploy():
    """Deployment scenario."""
    scenario = sp.test_scenario("deploy", token_gate_module)
    scenario.h1("Token Gate - Deployment")

    MULTISIG_ADDRESS = sp.address("KT1J9FYz29RBQi1oGLw8uXyACrzXzV1dHuvb")
    FEE_RECIPIENT_ADDRESS = sp.address("KT1J9FYz29RBQi1oGLw8uXyACrzXzV1dHuvb")
    MESSAGE_FEE = sp.mutez(100000)

    contract_metadata = sp.big_map(
        {
            "": sp.scenario_utils.bytes_of_string("ipfs://aaa"),
        }
    )

    contract = token_gate_module.TokenGate(
        multisig_address=MULTISIG_ADDRESS,
        fee_recipient=FEE_RECIPIENT_ADDRESS,
        message_fee=MESSAGE_FEE,
        metadata=contract_metadata,
        counter=sp.nat(0),
    )
    scenario += contract
