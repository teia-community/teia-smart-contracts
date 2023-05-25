"""Unit tests for the DAO token drop class.

"""

import smartpy as sp

# Import the DAO modules
daoTokenModule = sp.io.import_script_from_url("file:contracts/daoToken.py")
daoTokenDropModule = sp.io.import_script_from_url("file:contracts/daoTokenDrop.py")

user1 = sp.address("tz1ZczbHu1iLWRa88n9CUiCKDGex5ticp19S")
user2 = sp.address("tz1eUzpKnk5gKLYw4HWs2sWsynfbT7ypGxNM")
user3 = sp.address("tz1fxRWk1b53H3RLVxuipjCJJghPmzju7zQA")
user4 = sp.address("tz1VyBpzPZSpYHpqKzvVHWGs8vSuoiBHmZSN")
user5 = sp.address("tz1g6JRCpsEnD2BLiAzPNK3GBD1fKicV9rCx")

# Define a valid Merkle tree generated using the utility provided at
# https://github.com/AnshuJalan/token-drop-template/deploy/utilites/merkleTree.ts
tokens_user1_1 = sp.nat(100)
tokens_user2_1 = sp.nat(200)
tokens_user3_1 = sp.nat(300)
tokens_user4_1 = sp.nat(400)

proof_user1_1 = [sp.bytes("0x6fd53a9cbed7131f073ffb7c5e98bbb862ec36ea760b66067656f6091949e4f2"),
                 sp.bytes("0x2800b79312399df0116736073b3c468fb4ebd3c791624bdcc1db2d3cbe5ffc58")]
proof_user2_1 = [sp.bytes("0x4ef76d73abb14194755febcf8830493a021ef08c5477823e409ecb1aac86de79"),
                 sp.bytes("0x2800b79312399df0116736073b3c468fb4ebd3c791624bdcc1db2d3cbe5ffc58")]
proof_user3_1 = [sp.bytes("0x8630b4452805c75bdab9da5d09dc1cfd4fcbd971e397af31fab3ee7421ae745a"),
                 sp.bytes("0x555a4df967eca2f3e44cb4930abd5ca5202d0b76a822bd30cbaea05dbec40d02")]
proof_user4_1 = [sp.bytes("0x803d9cd47ab3a3997d8a4fee2f2fc0bcc032fb57211490cbb2cb90c44c5c2db2"),
                 sp.bytes("0x555a4df967eca2f3e44cb4930abd5ca5202d0b76a822bd30cbaea05dbec40d02")]

merkle_root_1 = sp.bytes("0x83e3763b42f4e89fbf5cb200c15ce03f2fe116c912fa7098f9970ff8d3db2ca3")

# Define a second Merkle tree with a second drop distribution
tokens_user1_2 = sp.nat(150)
tokens_user2_2 = sp.nat(250)
tokens_user3_2 = sp.nat(320)
tokens_user4_2 = sp.nat(200)
tokens_user5_2 = sp.nat(123)

proof_user1_2 = [sp.bytes("0xbf463c2dfdbc9e480c34db517415bdeea647f56fdcfe224f1ee22be8fd9c3a89"),
                 sp.bytes("0x485efbfcefebf603f38bcd139c8f5c61a65991cfa87294d9a669acc5b6365cdc"),
                 sp.bytes("0xdb108c5970061e1adf6fb04f6b2fc962d0cd13cd18b5080558b6ad28861876ad")]
proof_user2_2 = [sp.bytes("0x53895e5a19a9cb6cf173871ccc476d4a35f85694ac00f90e907cca81bb30c328"),
                 sp.bytes("0xcd4905621589e383ac1fb09ef66600fcf55d53cf1feb82f9940f26e816a75374"),
                 sp.bytes("0xdb108c5970061e1adf6fb04f6b2fc962d0cd13cd18b5080558b6ad28861876ad")]
proof_user3_2 = [sp.bytes("0x00c5dbcba2239456bd39111bfcc50029b36d76446d113dfbf6e60585d2cbbabc"),
                 sp.bytes("0xcd4905621589e383ac1fb09ef66600fcf55d53cf1feb82f9940f26e816a75374"),
                 sp.bytes("0xdb108c5970061e1adf6fb04f6b2fc962d0cd13cd18b5080558b6ad28861876ad")]
proof_user4_2 = [sp.bytes("0xc0fa180b3bf01cdd479b91a888a275dac84aea183c24463dfaf9d43397717ad5"),
                 sp.bytes("0x485efbfcefebf603f38bcd139c8f5c61a65991cfa87294d9a669acc5b6365cdc"),
                 sp.bytes("0xdb108c5970061e1adf6fb04f6b2fc962d0cd13cd18b5080558b6ad28861876ad")]
proof_user5_2 = [sp.bytes("0x78e3cb75439f9a2c311ff0f3dc2795de5263699222e246a0002fbc7f1d35e926")]

merkle_root_2 = sp.bytes("0x460982b9e159309ad1a1116904cf46857b64ea03a5e634e0cbd7a09c85a17688")

# Define a wrong proof for user 1
proof_user1_wrong = [sp.bytes("0x6fd53a9cbed7131f073ffb7c5e98bbb862ec36ea760b66067656f6091949e4f2"),
                     sp.bytes("0x555a4df967eca2f3e44cb4930abd5ca5202d0b76a822bd30cbaea05dbec40d02")]


def get_test_environment():
    # Initialize the test scenario
    scenario = sp.test_scenario()

    # Create the test accounts
    admin = sp.test_account("admin")
    treasury = sp.test_account("treasury")
    external_user = sp.test_account("external_user")

    # Initialize the DAO token FA2 contract
    daoToken = daoTokenModule.DAOToken(
        administrator=admin.address,
        metadata=sp.utils.metadata_of_url("ipfs://aaa"),
        token_metadata=sp.utils.bytes_of_string("ipfs://bbb"),
        supply=1500,
        max_share=350)
    scenario += daoToken

    # Initialize the DAO token drop contract to use the first Merkle tree
    daoTokenDrop = daoTokenDropModule.DAOTokenDrop(
        administrator=admin.address,
        metadata=sp.utils.metadata_of_url("ipfs://ccc"),
        token=daoToken.address,
        treasury=treasury.address,
        merkle_root=merkle_root_1,
        expiration_date=sp.timestamp_from_utc(2022, 12, 31, 23, 59, 59))
    scenario += daoTokenDrop

    # Add the DAO token drop contract and the treasury as maximum share exceptions
    daoToken.add_max_share_exception(daoTokenDrop.address).run(sender=admin)
    daoToken.add_max_share_exception(treasury.address).run(sender=admin)

    # Transfer all the editions from the admin to the DAO token drop contract
    daoToken.transfer([
        sp.record(
            from_=admin.address,
            txs=[sp.record(to_=daoTokenDrop.address, token_id=0, amount=1500)])
        ]).run(sender=admin)

    # Save all the variables in a test environment dictionary
    testEnvironment = {
        "scenario": scenario,
        "admin": admin,
        "treasury": treasury,
        "external_user": external_user,
        "daoToken": daoToken,
        "daoTokenDrop": daoTokenDrop}

    return testEnvironment


@sp.add_test(name="Test claim")
def test_claim():
    # Get the test environment
    testEnvironment = get_test_environment()
    scenario = testEnvironment["scenario"]
    admin = testEnvironment["admin"]
    daoToken = testEnvironment["daoToken"]
    daoTokenDrop = testEnvironment["daoTokenDrop"]

    # Check that all the tokens are in the DAO token drop contract
    scenario.verify(daoToken.get_balance(sp.record(owner=daoTokenDrop.address, token_id=0)) == 1500)
    scenario.verify(daoToken.total_supply(0) == 1500)

    # Check that the claim fails if the user sends some tez
    daoTokenDrop.claim(sp.record(
        proof=proof_user1_1,
        leaf=sp.pack(sp.record(address=user1, value=tokens_user1_1)))).run(
            valid=False, sender=user1, amount=sp.tez(2), exception="DROP_TEZ_TRANSFER")

    # Check that claiming the tokens after the expiration date fails
    daoTokenDrop.claim(sp.record(
        proof=proof_user1_1,
        leaf=sp.pack(sp.record(address=user1, value=tokens_user1_1)))).run(
            valid=False, sender=user1, now=sp.timestamp_from_utc(2023, 1, 1, 0, 0, 0), exception="DROP_CLAIM_EXPIRED")

    # Check that the packing needs to be correct
    daoTokenDrop.claim(sp.record(
        proof=proof_user1_1,
        leaf=sp.pack(sp.record(address=tokens_user1_1, tokens=user1)))).run(
            valid=False, sender=user1)

    # Check that it's not possible to claim the tokens of other user
    daoTokenDrop.claim(sp.record(
        proof=proof_user1_1,
        leaf=sp.pack(sp.record(address=user1, value=tokens_user1_1)))).run(
            valid=False, sender=user2, exception="DROP_SENDER_NOT_LEAF")

    # Check that even the admin cannot do it
    daoTokenDrop.claim(sp.record(
        proof=proof_user1_1,
        leaf=sp.pack(sp.record(address=user1, value=tokens_user1_1)))).run(
            valid=False, sender=admin, exception="DROP_SENDER_NOT_LEAF")

    # Check that claiming the tokens with the wrong proof fails
    daoTokenDrop.claim(sp.record(
        proof=proof_user1_wrong,
        leaf=sp.pack(sp.record(address=user1, value=tokens_user1_1)))).run(
            valid=False, sender=user1, exception="DROP_INVALID_MERKLE_PROOF")

    # User 1 and user 2 claim their tokens
    daoTokenDrop.claim(sp.record(
        proof=proof_user1_1,
        leaf=sp.pack(sp.record(address=user1, value=tokens_user1_1)))).run(sender=user1)
    daoTokenDrop.claim(sp.record(
        proof=proof_user2_1,
        leaf=sp.pack(sp.record(address=user2, value=tokens_user2_1)))).run(sender=user2)

    # Check that the contracts information have been updated
    scenario.verify(daoToken.get_balance(sp.record(owner=user1, token_id=0)) == tokens_user1_1)
    scenario.verify(daoToken.get_balance(sp.record(owner=user2, token_id=0)) == tokens_user2_1)
    scenario.verify(daoToken.get_balance(sp.record(owner=user3, token_id=0)) == 0)
    scenario.verify(daoToken.get_balance(sp.record(owner=user4, token_id=0)) == 0)
    scenario.verify(daoToken.get_balance(sp.record(owner=daoTokenDrop.address, token_id=0)) == sp.as_nat(
        1500 - (tokens_user1_1 + tokens_user2_1)))
    scenario.verify(daoTokenDrop.claimed_tokens(user1) == tokens_user1_1)
    scenario.verify(daoTokenDrop.claimed_tokens(user2) == tokens_user2_1)
    scenario.verify(daoTokenDrop.claimed_tokens(user3) == 0)
    scenario.verify(daoTokenDrop.claimed_tokens(user4) == 0)

    # Check that it's not possible to claim the tokens again
    daoTokenDrop.claim(sp.record(
        proof=proof_user1_1,
        leaf=sp.pack(sp.record(address=user1, value=tokens_user1_1)))).run(
            valid=False, sender=user1, exception="DROP_ALL_TOKENS_CLAIMED")

    # User 3 claims their tokens
    daoTokenDrop.claim(sp.record(
        proof=proof_user3_1,
        leaf=sp.pack(sp.record(address=user3, value=tokens_user3_1)))).run(sender=user3)

    # Check that user 4 cannot claim their tokens because that would make them
    # exceed the maximum share
    daoTokenDrop.claim(sp.record(
        proof=proof_user4_1,
        leaf=sp.pack(sp.record(address=user4, value=tokens_user4_1)))).run(
            valid=False, sender=user4, exception="FA2_SHARE_EXCESS")

    # Check that the contracts information have been updated
    scenario.verify(daoToken.get_balance(sp.record(owner=user1, token_id=0)) == tokens_user1_1)
    scenario.verify(daoToken.get_balance(sp.record(owner=user2, token_id=0)) == tokens_user2_1)
    scenario.verify(daoToken.get_balance(sp.record(owner=user3, token_id=0)) == tokens_user3_1)
    scenario.verify(daoToken.get_balance(sp.record(owner=user4, token_id=0)) == 0)
    scenario.verify(daoToken.get_balance(sp.record(owner=daoTokenDrop.address, token_id=0)) == sp.as_nat(
        1500 - (tokens_user1_1 + tokens_user2_1 + tokens_user3_1)))
    scenario.verify(daoTokenDrop.claimed_tokens(user1) == tokens_user1_1)
    scenario.verify(daoTokenDrop.claimed_tokens(user2) == tokens_user2_1)
    scenario.verify(daoTokenDrop.claimed_tokens(user3) == tokens_user3_1)
    scenario.verify(daoTokenDrop.claimed_tokens(user4) == 0)


@sp.add_test(name="Test transfer to treasury")
def test_transfer_to_treasury():
    # Get the test environment
    testEnvironment = get_test_environment()
    scenario = testEnvironment["scenario"]
    admin = testEnvironment["admin"]
    treasury = testEnvironment["treasury"]
    external_user = testEnvironment["external_user"]
    daoToken = testEnvironment["daoToken"]
    daoTokenDrop = testEnvironment["daoTokenDrop"]

    # User 1 and user 2 claim their tokens
    daoTokenDrop.claim(sp.record(
        proof=proof_user1_1,
        leaf=sp.pack(sp.record(address=user1, value=tokens_user1_1)))).run(sender=user1)
    daoTokenDrop.claim(sp.record(
        proof=proof_user2_1,
        leaf=sp.pack(sp.record(address=user2, value=tokens_user2_1)))).run(sender=user2)

    # Check that it's not possible to transfer the tokens to the treasury before 
    # the claim period has expired
    daoTokenDrop.transfer_to_treasury(sp.nat(100)).run(
        valid=False, sender=user1, now=sp.timestamp_from_utc(2022, 12, 31, 0, 0, 0), exception="DROP_CLAIM_NOT_EXPIRED")

    # Transfer some tokens to the treasury
    daoTokenDrop.transfer_to_treasury(sp.nat(100)).run(
        sender=user1, now=sp.timestamp_from_utc(2023, 1, 1, 0, 0, 0))
    daoTokenDrop.transfer_to_treasury(sp.nat(200)).run(
        sender=external_user, now=sp.timestamp_from_utc(2023, 1, 1, 0, 0, 0))

    # Check that the contracts information have been updated
    scenario.verify(daoToken.get_balance(sp.record(owner=user1, token_id=0)) == tokens_user1_1)
    scenario.verify(daoToken.get_balance(sp.record(owner=user2, token_id=0)) == tokens_user2_1)
    scenario.verify(daoToken.get_balance(sp.record(owner=user3, token_id=0)) == 0)
    scenario.verify(daoToken.get_balance(sp.record(owner=user4, token_id=0)) == 0)
    scenario.verify(daoToken.get_balance(sp.record(owner=daoTokenDrop.address, token_id=0)) == sp.as_nat(
        1500 - (tokens_user1_1 + tokens_user2_1 + 300)))
    scenario.verify(daoToken.get_balance(sp.record(owner=treasury.address, token_id=0)) == 300)
    scenario.verify(daoTokenDrop.claimed_tokens(user1) == tokens_user1_1)
    scenario.verify(daoTokenDrop.claimed_tokens(user2) == tokens_user2_1)
    scenario.verify(daoTokenDrop.claimed_tokens(user3) == 0)
    scenario.verify(daoTokenDrop.claimed_tokens(user4) == 0)
    scenario.verify(daoTokenDrop.claimed_tokens(treasury.address) == 0)


@sp.add_test(name="Test update treasury")
def test_update_treasury():
    # Get the test environment
    testEnvironment = get_test_environment()
    scenario = testEnvironment["scenario"]
    admin = testEnvironment["admin"]
    treasury = testEnvironment["treasury"]
    daoToken = testEnvironment["daoToken"]
    daoTokenDrop = testEnvironment["daoTokenDrop"]

    # Check the original treasury
    scenario.verify(daoTokenDrop.data.treasury == treasury.address)

    # Check that only the admin can update the treasury
    new_treasury = user4
    daoTokenDrop.update_treasury(new_treasury).run(
        valid=False, sender=user1, exception="DROP_NOT_ADMIN")
    daoTokenDrop.update_treasury(new_treasury).run(sender=admin)

    # Check that the contracts information have been updated
    scenario.verify(daoTokenDrop.data.treasury == new_treasury)


@sp.add_test(name="Test update merkle root")
def test_update_merkle_root():
    # Get the test environment
    testEnvironment = get_test_environment()
    scenario = testEnvironment["scenario"]
    admin = testEnvironment["admin"]
    daoToken = testEnvironment["daoToken"]
    daoTokenDrop = testEnvironment["daoTokenDrop"]

    # User 1 and user 2 their tokens
    daoTokenDrop.claim(sp.record(
        proof=proof_user1_1,
        leaf=sp.pack(sp.record(address=user1, value=tokens_user1_1)))).run(sender=user1)
    daoTokenDrop.claim(sp.record(
        proof=proof_user2_1,
        leaf=sp.pack(sp.record(address=user2, value=tokens_user2_1)))).run(sender=user2)

    # Check that the contracts information have been updated
    scenario.verify(daoToken.get_balance(sp.record(owner=user1, token_id=0)) == tokens_user1_1)
    scenario.verify(daoToken.get_balance(sp.record(owner=user2, token_id=0)) == tokens_user2_1)
    scenario.verify(daoToken.get_balance(sp.record(owner=user3, token_id=0)) == 0)
    scenario.verify(daoToken.get_balance(sp.record(owner=user4, token_id=0)) == 0)
    scenario.verify(daoToken.get_balance(sp.record(owner=daoTokenDrop.address, token_id=0)) == sp.as_nat(
        1500 - (tokens_user1_1 + tokens_user2_1)))
    scenario.verify(daoTokenDrop.claimed_tokens(user1) == tokens_user1_1)
    scenario.verify(daoTokenDrop.claimed_tokens(user2) == tokens_user2_1)
    scenario.verify(daoTokenDrop.claimed_tokens(user3) == 0)
    scenario.verify(daoTokenDrop.claimed_tokens(user4) == 0)
    scenario.verify(daoTokenDrop.claimed_tokens(user5) == 0)

    # Check that only the admin can update the Merkle tree root
    daoTokenDrop.update_merkle_root(merkle_root_2).run(
        valid=False, sender=user1, exception="DROP_NOT_ADMIN")

    # Update the Merkle tree root to reflect a new drop distribution
    daoTokenDrop.update_merkle_root(merkle_root_2).run(sender=admin)

    # Check that the contracts information have been updated
    scenario.verify(daoTokenDrop.data.merkle_root == merkle_root_2)

    # Check that it's not possible anymore to use the previous proofs
    daoTokenDrop.claim(sp.record(
        proof=proof_user3_1,
        leaf=sp.pack(sp.record(address=user3, value=tokens_user3_1)))).run(
            valid=False, sender=user3, exception="DROP_INVALID_MERKLE_PROOF")
 
    # All the users claim their tokens
    daoTokenDrop.claim(sp.record(
        proof=proof_user1_2,
        leaf=sp.pack(sp.record(address=user1, value=tokens_user1_2)))).run(sender=user1)
    daoTokenDrop.claim(sp.record(
        proof=proof_user2_2,
        leaf=sp.pack(sp.record(address=user2, value=tokens_user2_2)))).run(sender=user2)
    daoTokenDrop.claim(sp.record(
        proof=proof_user3_2,
        leaf=sp.pack(sp.record(address=user3, value=tokens_user3_2)))).run(sender=user3)
    daoTokenDrop.claim(sp.record(
        proof=proof_user4_2,
        leaf=sp.pack(sp.record(address=user4, value=tokens_user4_2)))).run(sender=user4)
    daoTokenDrop.claim(sp.record(
        proof=proof_user5_2,
        leaf=sp.pack(sp.record(address=user5, value=tokens_user5_2)))).run(sender=user5)

    # Check that the contracts information have been updated
    scenario.verify(daoToken.get_balance(sp.record(owner=user1, token_id=0)) == tokens_user1_2)
    scenario.verify(daoToken.get_balance(sp.record(owner=user2, token_id=0)) == tokens_user2_2)
    scenario.verify(daoToken.get_balance(sp.record(owner=user3, token_id=0)) == tokens_user3_2)
    scenario.verify(daoToken.get_balance(sp.record(owner=user4, token_id=0)) == tokens_user4_2)
    scenario.verify(daoToken.get_balance(sp.record(owner=user5, token_id=0)) == tokens_user5_2)
    scenario.verify(daoToken.get_balance(sp.record(owner=daoTokenDrop.address, token_id=0)) == sp.as_nat(
        1500 - (tokens_user1_2 + tokens_user2_2 + tokens_user3_2 + tokens_user4_2 + tokens_user5_2)))
    scenario.verify(daoTokenDrop.claimed_tokens(user1) == tokens_user1_2)
    scenario.verify(daoTokenDrop.claimed_tokens(user2) == tokens_user2_2)
    scenario.verify(daoTokenDrop.claimed_tokens(user3) == tokens_user3_2)
    scenario.verify(daoTokenDrop.claimed_tokens(user4) == tokens_user4_2)
    scenario.verify(daoTokenDrop.claimed_tokens(user5) == tokens_user5_2)


@sp.add_test(name="Test update expiration date")
def test_update_expiration_date():
    # Get the test environment
    testEnvironment = get_test_environment()
    scenario = testEnvironment["scenario"]
    admin = testEnvironment["admin"]
    daoToken = testEnvironment["daoToken"]
    daoTokenDrop = testEnvironment["daoTokenDrop"]

    # User 1 claim their tokens
    daoTokenDrop.claim(sp.record(
        proof=proof_user1_1,
        leaf=sp.pack(sp.record(address=user1, value=tokens_user1_1)))).run(
            sender=user1, now=sp.timestamp_from_utc(2022, 12, 31, 23, 59, 50))

    # Check that user 2 claimed their tokens too late
    daoTokenDrop.claim(sp.record(
        proof=proof_user2_1,
        leaf=sp.pack(sp.record(address=user2, value=tokens_user2_1)))).run(
            valid=False, sender=user2, now=sp.timestamp_from_utc(2023, 1, 1, 0, 0, 0), exception="DROP_CLAIM_EXPIRED")

    # Check that the contracts information have been updated
    scenario.verify(daoToken.get_balance(sp.record(owner=user1, token_id=0)) == tokens_user1_1)
    scenario.verify(daoToken.get_balance(sp.record(owner=user2, token_id=0)) == 0)
    scenario.verify(daoToken.get_balance(sp.record(owner=daoTokenDrop.address, token_id=0)) == sp.as_nat(
        1500 - tokens_user1_1))
    scenario.verify(daoTokenDrop.claimed_tokens(user1) == tokens_user1_1)
    scenario.verify(daoTokenDrop.claimed_tokens(user2) == 0)

    # Check that only the admin can update the expiration date
    daoTokenDrop.update_expiration_date(
        sp.timestamp_from_utc(2023, 5, 1, 0, 0, 0)).run(valid=False, sender=user1, exception="DROP_NOT_ADMIN")

    # Change the expiration date
    daoTokenDrop.update_expiration_date(
        sp.timestamp_from_utc(2023, 5, 1, 0, 0, 0)).run(sender=admin)

    # Check that the contracts information have been updated
    scenario.verify(daoTokenDrop.data.expiration_date == sp.timestamp_from_utc(2023, 5, 1, 0, 0, 0))

    # Check that user 2 can now claim their tokens
    daoTokenDrop.claim(sp.record(
        proof=proof_user2_1,
        leaf=sp.pack(sp.record(address=user2, value=tokens_user2_1)))).run(
            sender=user2, now=sp.timestamp_from_utc(2023, 3, 1, 0, 0, 0))

    # Check that the contracts information have been updated
    scenario.verify(daoToken.get_balance(sp.record(owner=user1, token_id=0)) == tokens_user1_1)
    scenario.verify(daoToken.get_balance(sp.record(owner=user2, token_id=0)) == tokens_user2_1)
    scenario.verify(daoToken.get_balance(sp.record(owner=daoTokenDrop.address, token_id=0)) == sp.as_nat(
        1500 - (tokens_user1_1 + tokens_user2_1)))
    scenario.verify(daoTokenDrop.claimed_tokens(user1) == tokens_user1_1)
    scenario.verify(daoTokenDrop.claimed_tokens(user2) == tokens_user2_1)


@sp.add_test(name="Test transfer and accept administrator")
def test_transfer_and_accept_administrator():
    # Get the test environment
    testEnvironment = get_test_environment()
    scenario = testEnvironment["scenario"]
    admin = testEnvironment["admin"]
    daoTokenDrop = testEnvironment["daoTokenDrop"]

    # Check the original administrator
    scenario.verify(daoTokenDrop.data.administrator == admin.address)

    # Check that only the admin can transfer the administrator
    new_administrator = user1
    daoTokenDrop.transfer_administrator(new_administrator).run(
        valid=False, sender=user1, exception="DROP_NOT_ADMIN")
    daoTokenDrop.transfer_administrator(new_administrator).run(sender=admin)

    # Check that the proposed administrator is updated
    scenario.verify(daoTokenDrop.data.proposed_administrator.open_some() == new_administrator)

    # Check that only the proposed administrator can accept the administrator position
    daoTokenDrop.accept_administrator().run(
        valid=False, sender=admin, exception="DROP_NOT_PROPOSED_ADMIN")
    daoTokenDrop.accept_administrator().run(sender=user1)

    # Check that the administrator is updated
    scenario.verify(daoTokenDrop.data.administrator == new_administrator)
    scenario.verify(~daoTokenDrop.data.proposed_administrator.is_some())

    # Check that only the new administrator can propose a new administrator
    new_administrator = user2
    daoTokenDrop.transfer_administrator(new_administrator).run(
        valid=False, sender=admin, exception="DROP_NOT_ADMIN")
    daoTokenDrop.transfer_administrator(new_administrator).run(sender=user1)

    # Check that the proposed administrator is updated
    scenario.verify(daoTokenDrop.data.proposed_administrator.open_some() == new_administrator)
