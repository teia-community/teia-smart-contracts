"""Unit tests for the DAO token drop class.

"""

import smartpy as sp

# Import the DAO modules
daoTokenModule = sp.io.import_script_from_url("file:contracts/daoToken.py")
daoTokenDropModule = sp.io.import_script_from_url("file:contracts/daoTokenDrop.py")


def get_test_environment():
    # Initialize the test scenario
    scenario = sp.test_scenario()

    # Create the test accounts
    admin = sp.test_account("admin")
    user1 = sp.test_account("user1")
    user2 = sp.test_account("user2")
    user3 = sp.test_account("user3")

    # Initialize the DAO token FA2 contract
    daoToken = daoTokenModule.DAOToken(
        administrator=admin.address,
        metadata=sp.utils.metadata_of_url("ipfs://aaa"),
        token_metadata=sp.utils.bytes_of_string("ipfs://bbb"),
        max_supply=1000000000000,
        max_share=50000000000)
    scenario += daoToken

    # Initialize the DAO token drop contract
    daoTokenDrop = daoTokenDropModule.DAOTokenDrop(
        administrator=admin.address,
        metadata=sp.utils.metadata_of_url("ipfs://ccc"),
        token=daoToken.address,
        merkle_root=sp.bytes("0x00"))
    scenario += daoTokenDrop

    # Save all the variables in a test environment dictionary
    testEnvironment = {
        "scenario": scenario,
        "admin": admin,
        "user1": user1,
        "user2": user2,
        "user3": user3,
        "daoToken": daoToken,
        "daoTokenDrop": daoTokenDrop}

    return testEnvironment


@sp.add_test(name="Test claim")
def test_claim():
    # Get the test environment
    testEnvironment = get_test_environment()
    scenario = testEnvironment["scenario"]
    admin = testEnvironment["admin"]
    user1 = testEnvironment["user1"]
    user2 = testEnvironment["user2"]
    user3 = testEnvironment["user3"]
    daoToken = testEnvironment["daoToken"]
    daoTokenDrop = testEnvironment["daoTokenDrop"]

    # Mint some DAO tokens and assign them to the DAO token drop contract
    daoToken.mint([
        sp.record(to_=daoTokenDrop.address, token_id=0, amount=100)]).run(sender=admin)

    # Check that the contract information has been updated
    scenario.verify(daoToken.get_balance(sp.record(owner=daoTokenDrop.address, token_id=0)) == 100)
    scenario.verify(daoToken.total_supply(0) == 100)


@sp.add_test(name="Test transfer and accept administrator")
def test_transfer_and_accept_administrator():
    # Get the test environment
    testEnvironment = get_test_environment()
    scenario = testEnvironment["scenario"]
    admin = testEnvironment["admin"]
    user1 = testEnvironment["user1"]
    user2 = testEnvironment["user2"]
    daoTokenDrop = testEnvironment["daoTokenDrop"]

    # Check the original administrator
    scenario.verify(daoTokenDrop.data.administrator == admin.address)

    # Check that only the admin can transfer the administrator
    new_administrator = user1.address
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
    new_administrator = user2.address
    daoTokenDrop.transfer_administrator(new_administrator).run(valid=False, sender=admin)
    daoTokenDrop.transfer_administrator(new_administrator).run(sender=user1)

    # Check that the proposed administrator is updated
    scenario.verify(daoTokenDrop.data.proposed_administrator.open_some() == new_administrator)
