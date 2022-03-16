"""Unit tests for the DAO token drop class.

"""

import smartpy as sp

# Import the DAO modules
daoTokenModule = sp.io.import_script_from_url("file:contracts/daoToken.py")
daoTokenDropModule = sp.io.import_script_from_url("file:contracts/daoTokenDrop.py")

# Define a valid Merkle tree generated using the utility provided at
# https://github.com/AnshuJalan/token-drop-template/deploy/utilites/merkleTree.ts
user1 = sp.address("tz1ZczbHu1iLWRa88n9CUiCKDGex5ticp19S")
user2 = sp.address("tz1eUzpKnk5gKLYw4HWs2sWsynfbT7ypGxNM")
user3 = sp.address("tz1fxRWk1b53H3RLVxuipjCJJghPmzju7zQA")
user4 = sp.address("tz1VyBpzPZSpYHpqKzvVHWGs8vSuoiBHmZSN")

tokens_user1 = sp.nat(100)
tokens_user2 = sp.nat(200)
tokens_user3 = sp.nat(300)
tokens_user4 = sp.nat(400)

proof_user1 = [sp.bytes("0x6fd53a9cbed7131f073ffb7c5e98bbb862ec36ea760b66067656f6091949e4f2"),
               sp.bytes("0x2800b79312399df0116736073b3c468fb4ebd3c791624bdcc1db2d3cbe5ffc58")]
proof_user2 = [sp.bytes("0x4ef76d73abb14194755febcf8830493a021ef08c5477823e409ecb1aac86de79"),
               sp.bytes("0x2800b79312399df0116736073b3c468fb4ebd3c791624bdcc1db2d3cbe5ffc58")]
proof_user3 = [sp.bytes("0x8630b4452805c75bdab9da5d09dc1cfd4fcbd971e397af31fab3ee7421ae745a"),
               sp.bytes("0x555a4df967eca2f3e44cb4930abd5ca5202d0b76a822bd30cbaea05dbec40d02")]
proof_user4 = [sp.bytes("0x803d9cd47ab3a3997d8a4fee2f2fc0bcc032fb57211490cbb2cb90c44c5c2db2"),
               sp.bytes("0x555a4df967eca2f3e44cb4930abd5ca5202d0b76a822bd30cbaea05dbec40d02")]

merkle_root = sp.bytes("0x83e3763b42f4e89fbf5cb200c15ce03f2fe116c912fa7098f9970ff8d3db2ca3")


def get_test_environment():
    # Initialize the test scenario
    scenario = sp.test_scenario()

    # Create the test accounts
    admin = sp.test_account("admin")
    user5 = sp.test_account("user5")

    # Initialize the DAO token FA2 contract
    daoToken = daoTokenModule.DAOToken(
        administrator=admin.address,
        metadata=sp.utils.metadata_of_url("ipfs://aaa"),
        token_metadata=sp.utils.bytes_of_string("ipfs://bbb"),
        max_supply=1000,
        max_share=350)
    scenario += daoToken

    # Initialize the DAO token drop contract
    daoTokenDrop = daoTokenDropModule.DAOTokenDrop(
        administrator=admin.address,
        metadata=sp.utils.metadata_of_url("ipfs://ccc"),
        token=daoToken.address,
        merkle_root=merkle_root)
    scenario += daoTokenDrop

    # Add the DAO token drop contract as a maximum share exception
    daoToken.add_max_share_exception(daoTokenDrop.address).run(sender=admin)

    # Save all the variables in a test environment dictionary
    testEnvironment = {
        "scenario": scenario,
        "admin": admin,
        "user5": user5,
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

    # Mint some DAO tokens and assign them to the DAO token drop contract
    daoToken.mint([
        sp.record(to_=daoTokenDrop.address, token_id=0, amount=1000)]).run(sender=admin)

    # Check that the contract information has been updated
    scenario.verify(daoToken.get_balance(sp.record(owner=daoTokenDrop.address, token_id=0)) == 1000)
    scenario.verify(daoToken.total_supply(0) == 1000)


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
    daoTokenDrop.transfer_administrator(new_administrator).run(valid=False, sender=user1)
    daoTokenDrop.transfer_administrator(new_administrator).run(sender=admin)

    # Check that the proposed administrator is updated
    scenario.verify(daoTokenDrop.data.proposed_administrator.open_some() == new_administrator)

    # Check that only the proposed administrator can accept the administrator position
    daoTokenDrop.accept_administrator().run(valid=False, sender=admin)
    daoTokenDrop.accept_administrator().run(sender=user1)

    # Check that the administrator is updated
    scenario.verify(daoTokenDrop.data.administrator == new_administrator)
    scenario.verify(~daoTokenDrop.data.proposed_administrator.is_some())

    # Check that only the new administrator can propose a new administrator
    new_administrator = user2
    daoTokenDrop.transfer_administrator(new_administrator).run(valid=False, sender=admin)
    daoTokenDrop.transfer_administrator(new_administrator).run(sender=user1)

    # Check that the proposed administrator is updated
    scenario.verify(daoTokenDrop.data.proposed_administrator.open_some() == new_administrator)
