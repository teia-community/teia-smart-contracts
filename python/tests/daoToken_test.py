"""Unit tests for the DAO token FA2 class.

"""

import smartpy as sp
from os import environ

# Import the DAO token FA2 contract module
daoTokenModule = sp.io.import_script_from_url("file:contracts/daoToken.py")


class Dummy(sp.Contract):
    """This dummy contract implements a callback method to receive the token
    balance information.

    """

    def __init__(self):
        """Initializes the contract.

        """
        # Define the contract storage data types for clarity
        self.init_type(sp.TRecord(
            balances=sp.TBigMap(sp.TPair(sp.TAddress, sp.TNat), sp.TNat)))

        # Initialize the contract storage
        self.init(balances=sp.big_map())

    @sp.entry_point
    def receive_balances(self, params):
        """Callback entry point that receives the token balance information.

        """
        # Define the input parameter data type
        sp.set_type(params, sp.TList(sp.TRecord(
                request=sp.TRecord(owner=sp.TAddress, token_id=sp.TNat).layout(("owner", "token_id")),
                balance=sp.TNat).layout(("request", "balance"))))

        # Save the returned information in the balances big map
        with sp.for_("balance_info", params) as balance_info:
            request = balance_info.request
            self.data.balances[
                (request.owner, request.token_id)] = balance_info.balance


def get_test_environment():
    # Initialize the test scenario
    scenario = sp.test_scenario()

    # Create the test accounts
    admin = sp.test_account("admin")
    initial_owner = sp.test_account("initial_owner")
    user1 = sp.test_account("user1")
    user2 = sp.test_account("user2")
    user3 = sp.test_account("user3")

    # Initialize the DAO token FA2 contract
    fa2 = daoTokenModule.DAOToken(
        administrator=admin.address,
        metadata=sp.utils.metadata_of_url("ipfs://aaa"),
        token_metadata=sp.utils.bytes_of_string("ipfs://bbb"),
        initial_owner=initial_owner.address,
        supply=1000000000000,
        max_share=50000000000)
    scenario += fa2

    # Save all the variables in a test environment dictionary
    testEnvironment = {
        "scenario": scenario,
        "admin": admin,
        "initial_owner": initial_owner,
        "user1": user1,
        "user2": user2,
        "user3": user3,
        "fa2": fa2}

    return testEnvironment


@sp.add_test(name="Test transfer")
def test_transfer():
    # Get the test environment
    testEnvironment = get_test_environment()
    scenario = testEnvironment["scenario"]
    admin = testEnvironment["admin"]
    initial_owner = testEnvironment["initial_owner"]
    user1 = testEnvironment["user1"]
    user2 = testEnvironment["user2"]
    user3 = testEnvironment["user3"]
    fa2 = testEnvironment["fa2"]

    # Check that the initial contract information is correct
    scenario.verify(fa2.data.ledger[initial_owner.address] == 1000000000000)
    scenario.verify(~fa2.data.ledger.contains(admin.address))
    scenario.verify(~fa2.data.ledger.contains(user1.address))
    scenario.verify(~fa2.data.ledger.contains(user2.address))
    scenario.verify(~fa2.data.ledger.contains(user3.address))
    scenario.verify(fa2.get_balance(sp.record(owner=initial_owner.address, token_id=0)) == 1000000000000)
    scenario.verify(fa2.get_balance(sp.record(owner=admin.address, token_id=0)) == 0)
    scenario.verify(fa2.get_balance(sp.record(owner=user1.address, token_id=0)) == 0)
    scenario.verify(fa2.get_balance(sp.record(owner=user2.address, token_id=0)) == 0)
    scenario.verify(fa2.get_balance(sp.record(owner=user3.address, token_id=0)) == 0)
    scenario.verify(~fa2.data.n_checkpoints.contains(initial_owner.address))
    scenario.verify(~fa2.data.n_checkpoints.contains(admin.address))
    scenario.verify(~fa2.data.n_checkpoints.contains(user1.address))
    scenario.verify(~fa2.data.n_checkpoints.contains(user2.address))
    scenario.verify(~fa2.data.n_checkpoints.contains(user3.address))
    scenario.verify(fa2.data.supply == 1000000000000)
    scenario.verify(fa2.total_supply(0) == 1000000000000)
    scenario.verify(fa2.data.max_share == 50000000000)
    scenario.verify(fa2.data.max_share_exceptions.contains(initial_owner.address))
    scenario.verify(sp.len(fa2.data.max_share_exceptions) == 1)
    scenario.verify(fa2.token_metadata(0).token_info[""] == sp.utils.bytes_of_string("ipfs://bbb"))
    scenario.verify(sp.len(fa2.all_tokens()) == 1)

    # Transfer some editions from the initial owner to the first user
    editions = 15
    fa2.transfer([
        sp.record(
            from_=initial_owner.address,
            txs=[sp.record(to_=user1.address, token_id=0, amount=editions)])
        ]).run(sender=initial_owner, level=0)

    # Check that the contract information has been updated
    scenario.verify(fa2.get_balance(sp.record(owner=initial_owner.address, token_id=0)) == 1000000000000 - editions)
    scenario.verify(fa2.get_balance(sp.record(owner=admin.address, token_id=0)) == 0)
    scenario.verify(fa2.get_balance(sp.record(owner=user1.address, token_id=0)) == editions)
    scenario.verify(fa2.get_balance(sp.record(owner=user2.address, token_id=0)) == 0)
    scenario.verify(fa2.get_balance(sp.record(owner=user3.address, token_id=0)) == 0)
    scenario.verify(fa2.data.n_checkpoints[initial_owner.address] == 1)
    scenario.verify(~fa2.data.n_checkpoints.contains(admin.address))
    scenario.verify(fa2.data.n_checkpoints[user1.address] == 1)
    scenario.verify(~fa2.data.n_checkpoints.contains(user2.address))
    scenario.verify(~fa2.data.n_checkpoints.contains(user3.address))
    scenario.verify(fa2.data.checkpoints[(initial_owner.address, 0)].level == 0)
    scenario.verify(fa2.data.checkpoints[(initial_owner.address, 0)].balance == 1000000000000 - editions)
    scenario.verify(fa2.data.checkpoints[(user1.address, 0)].level == 0)
    scenario.verify(fa2.data.checkpoints[(user1.address, 0)].balance == editions)
    scenario.verify(fa2.total_supply(0) == 1000000000000)

    # Check that another user cannot transfer the tokens from the first user
    fa2.transfer([
        sp.record(
            from_=user1.address,
            txs=[sp.record(to_=user3.address, token_id=0, amount=3)])
        ]).run(valid=False, sender=user3, exception="FA2_NOT_OPERATOR")

    # Check that even the admin cannot transfer the tokens from the first user
    fa2.transfer([
        sp.record(
            from_=user1.address,
            txs=[sp.record(to_=user3.address, token_id=0, amount=3)])
        ]).run(valid=False, sender=admin, exception="FA2_NOT_OPERATOR")

    # Check that the owner can transfer the tokens
    fa2.transfer([
        sp.record(
            from_=user1.address,
            txs=[sp.record(to_=user3.address, token_id=0, amount=3)])
        ]).run(sender=user1, level=20)

    # Check that the contract information has been updated
    scenario.verify(fa2.get_balance(sp.record(owner=initial_owner.address, token_id=0)) == 1000000000000 - editions)
    scenario.verify(fa2.get_balance(sp.record(owner=admin.address, token_id=0)) == 0)
    scenario.verify(fa2.get_balance(sp.record(owner=user1.address, token_id=0)) == editions - 3)
    scenario.verify(fa2.get_balance(sp.record(owner=user2.address, token_id=0)) == 0)
    scenario.verify(fa2.get_balance(sp.record(owner=user3.address, token_id=0)) == 3)
    scenario.verify(fa2.data.n_checkpoints[initial_owner.address] == 1)
    scenario.verify(~fa2.data.n_checkpoints.contains(admin.address))
    scenario.verify(fa2.data.n_checkpoints[user1.address] == 2)
    scenario.verify(~fa2.data.n_checkpoints.contains(user2.address))
    scenario.verify(fa2.data.n_checkpoints[user3.address] == 1)
    scenario.verify(fa2.data.checkpoints[(user1.address, 1)].level == 20)
    scenario.verify(fa2.data.checkpoints[(user1.address, 1)].balance == editions - 3)
    scenario.verify(fa2.data.checkpoints[(user3.address, 0)].level == 20)
    scenario.verify(fa2.data.checkpoints[(user3.address, 0)].balance == 3)
    scenario.verify(fa2.total_supply(0) == 1000000000000)

    # Check that the owner cannot transfer more tokens than the ones they have
    fa2.transfer([
        sp.record(
            from_=user1.address,
            txs=[sp.record(to_=user2.address, token_id=0, amount=30)])
        ]).run(valid=False, sender=user1, exception="FA2_INSUFFICIENT_BALANCE")

    # Check that an owner cannot transfer other owners editions
    fa2.transfer([
        sp.record(
            from_=user1.address,
            txs=[sp.record(to_=user3.address, token_id=0, amount=1)])
        ]).run(valid=False, sender=user3, exception="FA2_NOT_OPERATOR")

    # Check that the new owner can transfer their own editions
    fa2.transfer([
        sp.record(
            from_=user3.address,
            txs=[sp.record(to_=user2.address, token_id=0, amount=1)])
        ]).run(sender=user3, level=30)

    # Check that the contract information has been updated
    scenario.verify(fa2.get_balance(sp.record(owner=initial_owner.address, token_id=0)) == 1000000000000 - editions)
    scenario.verify(fa2.get_balance(sp.record(owner=user1.address, token_id=0)) == editions - 3)
    scenario.verify(fa2.get_balance(sp.record(owner=user2.address, token_id=0)) == 1)
    scenario.verify(fa2.get_balance(sp.record(owner=user3.address, token_id=0)) == 3 - 1)
    scenario.verify(fa2.data.n_checkpoints[initial_owner.address] == 1)
    scenario.verify(fa2.data.n_checkpoints[user1.address] == 2)
    scenario.verify(fa2.data.n_checkpoints[user2.address] == 1)
    scenario.verify(fa2.data.n_checkpoints[user3.address] == 2)
    scenario.verify(fa2.data.checkpoints[(user2.address, 0)].level == 30)
    scenario.verify(fa2.data.checkpoints[(user2.address, 0)].balance == 1)
    scenario.verify(fa2.data.checkpoints[(user3.address, 1)].level == 30)
    scenario.verify(fa2.data.checkpoints[(user3.address, 1)].balance == 3 - 1)
    scenario.verify(fa2.total_supply(0) == 1000000000000)

    # Make the second user as operator of the first user token
    fa2.update_operators([sp.variant("add_operator", sp.record(
        owner=user1.address,
        operator=user2.address,
        token_id=0))]).run(sender=user1)

    # Check that the second user now can transfer the user1 editions
    fa2.transfer([
        sp.record(
            from_=user1.address,
            txs=[sp.record(to_=user3.address, token_id=0, amount=5)])
        ]).run(sender=user2, level=40)

    # Check that the contract information has been updated
    scenario.verify(fa2.get_balance(sp.record(owner=initial_owner.address, token_id=0)) == 1000000000000 - editions)
    scenario.verify(fa2.get_balance(sp.record(owner=user1.address, token_id=0)) == editions - 3 - 5)
    scenario.verify(fa2.get_balance(sp.record(owner=user2.address, token_id=0)) == 1)
    scenario.verify(fa2.get_balance(sp.record(owner=user3.address, token_id=0)) == 3 - 1 + 5)
    scenario.verify(fa2.data.n_checkpoints[initial_owner.address] == 1)
    scenario.verify(fa2.data.n_checkpoints[user1.address] == 3)
    scenario.verify(fa2.data.n_checkpoints[user2.address] == 1)
    scenario.verify(fa2.data.n_checkpoints[user3.address] == 3)
    scenario.verify(fa2.data.checkpoints[(user1.address, 2)].level == 40)
    scenario.verify(fa2.data.checkpoints[(user1.address, 2)].balance == editions - 3 - 5)
    scenario.verify(fa2.data.checkpoints[(user3.address, 2)].level == 40)
    scenario.verify(fa2.data.checkpoints[(user3.address, 2)].balance == 3 - 1 + 5)
    scenario.verify(fa2.total_supply(0) == 1000000000000)

    # Transfer a large amount of tokens to the users
    fa2.transfer([
        sp.record(
            from_=initial_owner.address,
            txs=[sp.record(to_=user1.address, token_id=0, amount=fa2.data.max_share / 2),
                 sp.record(to_=user2.address, token_id=0, amount=fa2.data.max_share / 2)])
        ]).run(sender=initial_owner, level=50)

    # Check that the contract information has been updated
    scenario.verify(fa2.get_balance(sp.record(owner=initial_owner.address, token_id=0)) == 1000000000000 - editions - 50000000000)
    scenario.verify(fa2.get_balance(sp.record(owner=user1.address, token_id=0)) == editions - 3 - 5 + fa2.data.max_share / 2)
    scenario.verify(fa2.get_balance(sp.record(owner=user2.address, token_id=0)) == 1 + fa2.data.max_share / 2)
    scenario.verify(fa2.get_balance(sp.record(owner=user3.address, token_id=0)) == 3 - 1 + 5)
    scenario.verify(fa2.data.n_checkpoints[initial_owner.address] == 2)
    scenario.verify(fa2.data.n_checkpoints[user1.address] == 4)
    scenario.verify(fa2.data.n_checkpoints[user2.address] == 2)
    scenario.verify(fa2.data.n_checkpoints[user3.address] == 3)
    scenario.verify(fa2.data.checkpoints[(initial_owner.address, 1)].level == 50)
    scenario.verify(fa2.data.checkpoints[(initial_owner.address, 1)].balance == 1000000000000 - editions - 50000000000)
    scenario.verify(fa2.data.checkpoints[(user1.address, 3)].level == 50)
    scenario.verify(fa2.data.checkpoints[(user1.address, 3)].balance == editions - 3 - 5 + fa2.data.max_share / 2)
    scenario.verify(fa2.data.checkpoints[(user2.address, 1)].level == 50)
    scenario.verify(fa2.data.checkpoints[(user2.address, 1)].balance == 1 + fa2.data.max_share / 2)
    scenario.verify(fa2.total_supply(0) == 1000000000000)

    # Check that it's not possible to have more tokens than the allowed share
    fa2.transfer([
        sp.record(
            from_=user1.address,
            txs=[sp.record(to_=user2.address, token_id=0, amount=fa2.data.max_share / 2)])
        ]).run(valid=False, sender=user1, level=50, exception="FA2_SHARE_EXCESS")


@sp.add_test(name="Test complex transfer")
def test_complex_transfer():
    # Get the test environment
    testEnvironment = get_test_environment()
    scenario = testEnvironment["scenario"]
    admin = testEnvironment["admin"]
    initial_owner = testEnvironment["initial_owner"]
    user1 = testEnvironment["user1"]
    user2 = testEnvironment["user2"]
    user3 = testEnvironment["user3"]
    fa2 = testEnvironment["fa2"]

    # Transfer some editions from the initial owner to two users
    fa2.transfer([
        sp.record(
            from_=initial_owner.address,
            txs=[sp.record(to_=user1.address, token_id=0, amount=10),
                 sp.record(to_=user2.address, token_id=0, amount=20)])
        ]).run(sender=initial_owner, level=10)

    # Check that the contract information has been updated
    scenario.verify(fa2.get_balance(sp.record(owner=initial_owner.address, token_id=0)) == 1000000000000 - 10 - 20)
    scenario.verify(fa2.get_balance(sp.record(owner=user1.address, token_id=0)) == 10)
    scenario.verify(fa2.get_balance(sp.record(owner=user2.address, token_id=0)) == 20)
    scenario.verify(fa2.get_balance(sp.record(owner=user3.address, token_id=0)) == 0)
    scenario.verify(fa2.data.n_checkpoints[initial_owner.address] == 1)
    scenario.verify(fa2.data.n_checkpoints[user1.address] == 1)
    scenario.verify(fa2.data.n_checkpoints[user2.address] == 1)
    scenario.verify(~fa2.data.n_checkpoints.contains(user3.address))
    scenario.verify(fa2.data.checkpoints[(initial_owner.address, 0)].level == 10)
    scenario.verify(fa2.data.checkpoints[(initial_owner.address, 0)].balance == 1000000000000 - 10 - 20)
    scenario.verify(fa2.data.checkpoints[(user1.address, 0)].level == 10)
    scenario.verify(fa2.data.checkpoints[(user1.address, 0)].balance == 10)
    scenario.verify(fa2.data.checkpoints[(user2.address, 0)].level == 10)
    scenario.verify(fa2.data.checkpoints[(user2.address, 0)].balance == 20)
    scenario.verify(fa2.total_supply(0) == 1000000000000)

    # Check that users can only transfer tokens they own
    fa2.transfer([
        sp.record(
            from_=user1.address,
            txs=[sp.record(to_=user3.address, token_id=0, amount=3)]),
        sp.record(
            from_=user2.address,
            txs=[sp.record(to_=user3.address, token_id=0, amount=3)])
        ]).run(valid=False, sender=user1, exception="FA2_NOT_OPERATOR")

    # Check that the owner can transfer the token to several users
    fa2.transfer([
        sp.record(
            from_=user1.address,
            txs=[
                sp.record(to_=user2.address, token_id=0, amount=2),
                sp.record(to_=user3.address, token_id=0, amount=3)])
        ]).run(sender=user1, level=20)

    # Check that the contract information has been updated
    scenario.verify(fa2.get_balance(sp.record(owner=initial_owner.address, token_id=0)) == 1000000000000 - 10 - 20)
    scenario.verify(fa2.get_balance(sp.record(owner=user1.address, token_id=0)) == 10 - 2 - 3)
    scenario.verify(fa2.get_balance(sp.record(owner=user2.address, token_id=0)) == 20 + 2)
    scenario.verify(fa2.get_balance(sp.record(owner=user3.address, token_id=0)) == 3)
    scenario.verify(fa2.data.n_checkpoints[initial_owner.address] == 1)
    scenario.verify(fa2.data.n_checkpoints[user1.address] == 2)
    scenario.verify(fa2.data.n_checkpoints[user2.address] == 2)
    scenario.verify(fa2.data.n_checkpoints[user3.address] == 1)
    scenario.verify(fa2.data.checkpoints[(user1.address, 1)].level == 20)
    scenario.verify(fa2.data.checkpoints[(user1.address, 1)].balance == 10 - 2 - 3)
    scenario.verify(fa2.data.checkpoints[(user2.address, 1)].level == 20)
    scenario.verify(fa2.data.checkpoints[(user2.address, 1)].balance == 20 + 2)
    scenario.verify(fa2.data.checkpoints[(user3.address, 0)].level == 20)
    scenario.verify(fa2.data.checkpoints[(user3.address, 0)].balance == 3)

    # Check that the admin cannot transfer whatever token they want
    fa2.transfer([
        sp.record(
            from_=user1.address,
            txs=[sp.record(to_=user3.address, token_id=0, amount=1)]),
        sp.record(
            from_=user2.address,
            txs=[sp.record(to_=user3.address, token_id=0, amount=5)])
        ]).run(valid=False, sender=admin, exception="FA2_NOT_OPERATOR")

    # Check that owners can transfer tokens to themselves
    fa2.transfer([
        sp.record(
            from_=user2.address,
            txs=[
                sp.record(to_=user2.address, token_id=0, amount=1),
                sp.record(to_=user2.address, token_id=0, amount=2),
                sp.record(to_=user2.address, token_id=0, amount=0)])
        ]).run(sender=user2, level=30)

    # Check that the contract information has been updated
    scenario.verify(fa2.get_balance(sp.record(owner=initial_owner.address, token_id=0)) == 1000000000000 - 10 - 20)
    scenario.verify(fa2.get_balance(sp.record(owner=user1.address, token_id=0)) == 10 - 2 - 3)
    scenario.verify(fa2.get_balance(sp.record(owner=user2.address, token_id=0)) == 20 + 2)
    scenario.verify(fa2.get_balance(sp.record(owner=user3.address, token_id=0)) == 3)
    scenario.verify(fa2.data.n_checkpoints[initial_owner.address] == 1)
    scenario.verify(fa2.data.n_checkpoints[user1.address] == 2)
    scenario.verify(fa2.data.n_checkpoints[user2.address] == 2)
    scenario.verify(fa2.data.n_checkpoints[user3.address] == 1)
    scenario.verify(fa2.data.checkpoints[(user2.address, 1)].level == 20)
    scenario.verify(fa2.data.checkpoints[(user2.address, 1)].balance == 20 + 2)

    # Make the second user as operator of the first user tokens
    fa2.update_operators([sp.variant("add_operator", sp.record(
        owner=user1.address,
        operator=user2.address,
        token_id=0))]).run(sender=user1)

    # Check that the second user can transfer their tokens and the first user token
    fa2.transfer([
        sp.record(
            from_=user2.address,
            txs=[sp.record(to_=user3.address, token_id=0, amount=1)]),
        sp.record(
            from_=user1.address,
            txs=[sp.record(to_=user3.address, token_id=0, amount=2)])
        ]).run(sender=user2, level=40)

    # Check that the contract information has been updated
    scenario.verify(fa2.get_balance(sp.record(owner=initial_owner.address, token_id=0)) == 1000000000000 - 10 - 20)
    scenario.verify(fa2.get_balance(sp.record(owner=user1.address, token_id=0)) == 10 - 2 - 3 - 2)
    scenario.verify(fa2.get_balance(sp.record(owner=user2.address, token_id=0)) == 20 + 2 - 1)
    scenario.verify(fa2.get_balance(sp.record(owner=user3.address, token_id=0)) == 3 + 2 + 1)
    scenario.verify(fa2.data.n_checkpoints[initial_owner.address] == 1)
    scenario.verify(fa2.data.n_checkpoints[user1.address] == 3)
    scenario.verify(fa2.data.n_checkpoints[user2.address] == 3)
    scenario.verify(fa2.data.n_checkpoints[user3.address] == 2)
    scenario.verify(fa2.data.checkpoints[(user1.address, 2)].level == 40)
    scenario.verify(fa2.data.checkpoints[(user1.address, 2)].balance == 10 - 2 - 3 - 2)
    scenario.verify(fa2.data.checkpoints[(user2.address, 2)].level == 40)
    scenario.verify(fa2.data.checkpoints[(user2.address, 2)].balance == 20 + 2 - 1)
    scenario.verify(fa2.data.checkpoints[(user3.address, 1)].level == 40)
    scenario.verify(fa2.data.checkpoints[(user3.address, 1)].balance == 3 + 2 + 1)


@sp.add_test(name="Test prior balance")
def test_prior_balance():
    # Get the test environment
    testEnvironment = get_test_environment()
    scenario = testEnvironment["scenario"]
    admin = testEnvironment["admin"]
    initial_owner = testEnvironment["initial_owner"]
    user1 = testEnvironment["user1"]
    user2 = testEnvironment["user2"]
    user3 = testEnvironment["user3"]
    fa2 = testEnvironment["fa2"]

    # Transfer some editions from the initial owner to two users
    fa2.transfer([
        sp.record(
            from_=initial_owner.address,
            txs=[sp.record(to_=user1.address, token_id=0, amount=10),
                 sp.record(to_=user2.address, token_id=0, amount=20)])
        ]).run(sender=initial_owner, level=10)

    # Check that the contract information has been updated
    scenario.verify(fa2.data.checkpoints[(initial_owner.address, 0)].level == 10)
    scenario.verify(fa2.data.checkpoints[(initial_owner.address, 0)].balance == 1000000000000 - 10 - 20)
    scenario.verify(fa2.data.checkpoints[(user1.address, 0)].level == 10)
    scenario.verify(fa2.data.checkpoints[(user1.address, 0)].balance == 10)
    scenario.verify(fa2.data.checkpoints[(user2.address, 0)].level == 10)
    scenario.verify(fa2.data.checkpoints[(user2.address, 0)].balance == 20)

    # Check that the owner can transfer the token to several users
    fa2.transfer([
        sp.record(
            from_=user1.address,
            txs=[
                sp.record(to_=user2.address, token_id=0, amount=2),
                sp.record(to_=user3.address, token_id=0, amount=3)])
        ]).run(sender=user1, level=20)

    # Check that the contract information has been updated
    scenario.verify(fa2.data.checkpoints[(user1.address, 1)].level == 20)
    scenario.verify(fa2.data.checkpoints[(user1.address, 1)].balance == 10 - 2 - 3)
    scenario.verify(fa2.data.checkpoints[(user2.address, 1)].level == 20)
    scenario.verify(fa2.data.checkpoints[(user2.address, 1)].balance == 20 + 2)
    scenario.verify(fa2.data.checkpoints[(user3.address, 0)].level == 20)
    scenario.verify(fa2.data.checkpoints[(user3.address, 0)].balance == 3)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=initial_owner.address, max_checkpoints=sp.none, level=9)) == 0)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=initial_owner.address, max_checkpoints=sp.none, level=10)) == 1000000000000 - 10 - 20)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=initial_owner.address, max_checkpoints=sp.none, level=11)) == 1000000000000 - 10 - 20)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user1.address, max_checkpoints=sp.none, level=9)) == 0)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user1.address, max_checkpoints=sp.none, level=10)) == 10)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user1.address, max_checkpoints=sp.none, level=11)) == 10)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user2.address, max_checkpoints=sp.none, level=9)) == 0)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user2.address, max_checkpoints=sp.none, level=10)) == 20)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user2.address, max_checkpoints=sp.none, level=11)) == 20)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user3.address, max_checkpoints=sp.none, level=9)) == 0)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user3.address, max_checkpoints=sp.none, level=10)) == 0)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user3.address, max_checkpoints=sp.none, level=11)) == 0)
    scenario.verify(sp.is_failing(fa2.get_prior_balance(sp.record(owner=user1.address, max_checkpoints=sp.none, level=20))))
    scenario.verify(sp.is_failing(fa2.get_prior_balance(sp.record(owner=user1.address, max_checkpoints=sp.none, level=30))))

    # Check that owners can transfer tokens to themselves
    fa2.transfer([
        sp.record(
            from_=user2.address,
            txs=[
                sp.record(to_=user2.address, token_id=0, amount=1),
                sp.record(to_=user2.address, token_id=0, amount=2),
                sp.record(to_=user2.address, token_id=0, amount=0)])
        ]).run(sender=user2, level=30)

    # Check that the contract information has been updated
    scenario.verify(fa2.data.checkpoints[(user2.address, 1)].level == 20)
    scenario.verify(fa2.data.checkpoints[(user2.address, 1)].balance == 20 + 2)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=initial_owner.address, max_checkpoints=sp.none, level=9)) == 0)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=initial_owner.address, max_checkpoints=sp.none, level=10)) == 1000000000000 - 10 - 20)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=initial_owner.address, max_checkpoints=sp.none, level=11)) == 1000000000000 - 10 - 20)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=initial_owner.address, max_checkpoints=sp.none, level=20)) == 1000000000000 - 10 - 20)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=initial_owner.address, max_checkpoints=sp.none, level=25)) == 1000000000000 - 10 - 20)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user1.address, max_checkpoints=sp.none, level=9)) == 0)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user1.address, max_checkpoints=sp.none, level=10)) == 10)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user1.address, max_checkpoints=sp.none, level=11)) == 10)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user1.address, max_checkpoints=sp.none, level=20)) == 10 - 2 - 3)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user1.address, max_checkpoints=sp.none, level=25)) == 10 - 2 - 3)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user2.address, max_checkpoints=sp.none, level=9)) == 0)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user2.address, max_checkpoints=sp.none, level=10)) == 20)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user2.address, max_checkpoints=sp.none, level=11)) == 20)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user2.address, max_checkpoints=sp.none, level=20)) == 20 + 2)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user2.address, max_checkpoints=sp.none, level=25)) == 20 + 2)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user3.address, max_checkpoints=sp.none, level=9)) == 0)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user3.address, max_checkpoints=sp.none, level=10)) == 0)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user3.address, max_checkpoints=sp.none, level=11)) == 0)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user3.address, max_checkpoints=sp.none, level=20)) == 3)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user3.address, max_checkpoints=sp.none, level=25)) == 3)
    scenario.verify(sp.is_failing(fa2.get_prior_balance(sp.record(owner=user1.address, max_checkpoints=sp.none, level=30))))
    scenario.verify(sp.is_failing(fa2.get_prior_balance(sp.record(owner=user1.address, max_checkpoints=sp.none, level=40))))

    # Make the second user as operator of the first user token
    fa2.update_operators([sp.variant("add_operator", sp.record(
        owner=user1.address,
        operator=user2.address,
        token_id=0))]).run(sender=user1)

    # Check that the second user can transfer their tokens and the first user token
    fa2.transfer([
        sp.record(
            from_=user2.address,
            txs=[sp.record(to_=user3.address, token_id=0, amount=1)]),
        sp.record(
            from_=user1.address,
            txs=[sp.record(to_=user3.address, token_id=0, amount=2)])
        ]).run(sender=user2, level=40)

    # Check that the contract information has been updated
    scenario.verify(fa2.data.checkpoints[(user1.address, 2)].level == 40)
    scenario.verify(fa2.data.checkpoints[(user1.address, 2)].balance == 10 - 2 - 3 - 2)
    scenario.verify(fa2.data.checkpoints[(user2.address, 2)].level == 40)
    scenario.verify(fa2.data.checkpoints[(user2.address, 2)].balance == 20 + 2 - 1)
    scenario.verify(fa2.data.checkpoints[(user3.address, 1)].level == 40)
    scenario.verify(fa2.data.checkpoints[(user3.address, 1)].balance == 3 + 2 + 1)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=initial_owner.address, max_checkpoints=sp.none, level=9)) == 0)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=initial_owner.address, max_checkpoints=sp.none, level=10)) == 1000000000000 - 10 - 20)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=initial_owner.address, max_checkpoints=sp.none, level=11)) == 1000000000000 - 10 - 20)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=initial_owner.address, max_checkpoints=sp.none, level=20)) == 1000000000000 - 10 - 20)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=initial_owner.address, max_checkpoints=sp.none, level=25)) == 1000000000000 - 10 - 20)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=initial_owner.address, max_checkpoints=sp.none, level=30)) == 1000000000000 - 10 - 20)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=initial_owner.address, max_checkpoints=sp.none, level=35)) == 1000000000000 - 10 - 20)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user1.address, max_checkpoints=sp.none, level=9)) == 0)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user1.address, max_checkpoints=sp.none, level=10)) == 10)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user1.address, max_checkpoints=sp.none, level=11)) == 10)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user1.address, max_checkpoints=sp.none, level=20)) == 10 - 2 - 3)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user1.address, max_checkpoints=sp.none, level=25)) == 10 - 2 - 3)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user1.address, max_checkpoints=sp.none, level=30)) == 10 - 2 - 3)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user1.address, max_checkpoints=sp.none, level=35)) == 10 - 2 - 3)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user2.address, max_checkpoints=sp.none, level=9)) == 0)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user2.address, max_checkpoints=sp.none, level=10)) == 20)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user2.address, max_checkpoints=sp.none, level=11)) == 20)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user2.address, max_checkpoints=sp.none, level=20)) == 20 + 2)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user2.address, max_checkpoints=sp.none, level=25)) == 20 + 2)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user2.address, max_checkpoints=sp.none, level=30)) == 20 + 2)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user2.address, max_checkpoints=sp.none, level=35)) == 20 + 2)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user3.address, max_checkpoints=sp.none, level=9)) == 0)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user3.address, max_checkpoints=sp.none, level=10)) == 0)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user3.address, max_checkpoints=sp.none, level=11)) == 0)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user3.address, max_checkpoints=sp.none, level=20)) == 3)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user3.address, max_checkpoints=sp.none, level=25)) == 3)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user3.address, max_checkpoints=sp.none, level=30)) == 3)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user3.address, max_checkpoints=sp.none, level=35)) == 3)
    scenario.verify(sp.is_failing(fa2.get_prior_balance(sp.record(owner=user1.address, max_checkpoints=sp.none, level=40))))
    scenario.verify(sp.is_failing(fa2.get_prior_balance(sp.record(owner=user1.address, max_checkpoints=sp.none, level=50))))

    # Transfer some extra editions from the initial owner to the first user
    fa2.transfer([
        sp.record(
            from_=initial_owner.address,
            txs=[sp.record(to_=user1.address, token_id=0, amount=100)])
        ]).run(sender=initial_owner, level=50)

    # Check that the contract information has been updated
    scenario.verify(fa2.data.checkpoints[(initial_owner.address, 1)].level == 50)
    scenario.verify(fa2.data.checkpoints[(initial_owner.address, 1)].balance == 1000000000000 - 10 - 20 - 100)
    scenario.verify(fa2.data.checkpoints[(user1.address, 3)].level == 50)
    scenario.verify(fa2.data.checkpoints[(user1.address, 3)].balance == 10 - 2 - 3 - 2 + 100)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=initial_owner.address, max_checkpoints=sp.none, level=9)) == 0)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=initial_owner.address, max_checkpoints=sp.none, level=10)) == 1000000000000 - 10 - 20)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=initial_owner.address, max_checkpoints=sp.none, level=11)) == 1000000000000 - 10 - 20)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=initial_owner.address, max_checkpoints=sp.none, level=20)) == 1000000000000 - 10 - 20)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=initial_owner.address, max_checkpoints=sp.none, level=25)) == 1000000000000 - 10 - 20)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=initial_owner.address, max_checkpoints=sp.none, level=30)) == 1000000000000 - 10 - 20)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=initial_owner.address, max_checkpoints=sp.none, level=35)) == 1000000000000 - 10 - 20)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=initial_owner.address, max_checkpoints=sp.none, level=40)) == 1000000000000 - 10 - 20)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=initial_owner.address, max_checkpoints=sp.none, level=45)) == 1000000000000 - 10 - 20)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user1.address, max_checkpoints=sp.none, level=9)) == 0)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user1.address, max_checkpoints=sp.none, level=10)) == 10)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user1.address, max_checkpoints=sp.none, level=11)) == 10)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user1.address, max_checkpoints=sp.none, level=20)) == 10 - 2 - 3)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user1.address, max_checkpoints=sp.none, level=25)) == 10 - 2 - 3)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user1.address, max_checkpoints=sp.none, level=30)) == 10 - 2 - 3)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user1.address, max_checkpoints=sp.none, level=35)) == 10 - 2 - 3)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user1.address, max_checkpoints=sp.none, level=40)) == 10 - 2 - 3 - 2)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user1.address, max_checkpoints=sp.none, level=45)) == 10 - 2 - 3 - 2)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user2.address, max_checkpoints=sp.none, level=9)) == 0)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user2.address, max_checkpoints=sp.none, level=10)) == 20)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user2.address, max_checkpoints=sp.none, level=11)) == 20)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user2.address, max_checkpoints=sp.none, level=20)) == 20 + 2)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user2.address, max_checkpoints=sp.none, level=25)) == 20 + 2)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user2.address, max_checkpoints=sp.none, level=30)) == 20 + 2)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user2.address, max_checkpoints=sp.none, level=35)) == 20 + 2)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user2.address, max_checkpoints=sp.none, level=40)) == 20 + 2 - 1)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user2.address, max_checkpoints=sp.none, level=45)) == 20 + 2 - 1)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user3.address, max_checkpoints=sp.none, level=9)) == 0)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user3.address, max_checkpoints=sp.none, level=10)) == 0)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user3.address, max_checkpoints=sp.none, level=11)) == 0)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user3.address, max_checkpoints=sp.none, level=20)) == 3)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user3.address, max_checkpoints=sp.none, level=25)) == 3)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user3.address, max_checkpoints=sp.none, level=30)) == 3)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user3.address, max_checkpoints=sp.none, level=35)) == 3)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user3.address, max_checkpoints=sp.none, level=40)) == 3 + 2 + 1)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user3.address, max_checkpoints=sp.none, level=45)) == 3 + 2 + 1)

    # The second user transfers some tokens to the first user
    fa2.transfer([sp.record(
            from_=user2.address,
            txs=[sp.record(to_=user1.address, token_id=0, amount=5)])
        ]).run(sender=user2, level=60)

    # Check that the contract information has been updated
    scenario.verify(fa2.data.checkpoints[(user1.address, 4)].level == 60)
    scenario.verify(fa2.data.checkpoints[(user1.address, 4)].balance == 10 - 2 - 3 - 2 + 100 + 5)
    scenario.verify(fa2.data.checkpoints[(user2.address, 3)].level == 60)
    scenario.verify(fa2.data.checkpoints[(user2.address, 3)].balance == 20 + 2 - 1 - 5)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=initial_owner.address, max_checkpoints=sp.none, level=9)) == 0)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=initial_owner.address, max_checkpoints=sp.none, level=10)) == 1000000000000 - 10 - 20)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=initial_owner.address, max_checkpoints=sp.none, level=11)) == 1000000000000 - 10 - 20)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=initial_owner.address, max_checkpoints=sp.none, level=20)) == 1000000000000 - 10 - 20)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=initial_owner.address, max_checkpoints=sp.none, level=25)) == 1000000000000 - 10 - 20)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=initial_owner.address, max_checkpoints=sp.none, level=30)) == 1000000000000 - 10 - 20)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=initial_owner.address, max_checkpoints=sp.none, level=35)) == 1000000000000 - 10 - 20)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=initial_owner.address, max_checkpoints=sp.none, level=40)) == 1000000000000 - 10 - 20)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=initial_owner.address, max_checkpoints=sp.none, level=45)) == 1000000000000 - 10 - 20)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=initial_owner.address, max_checkpoints=sp.none, level=50)) == 1000000000000 - 10 - 20 - 100)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=initial_owner.address, max_checkpoints=sp.none, level=59)) == 1000000000000 - 10 - 20 - 100)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user1.address, max_checkpoints=sp.none, level=9)) == 0)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user1.address, max_checkpoints=sp.none, level=10)) == 10)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user1.address, max_checkpoints=sp.none, level=11)) == 10)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user1.address, max_checkpoints=sp.none, level=20)) == 10 - 2 - 3)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user1.address, max_checkpoints=sp.none, level=25)) == 10 - 2 - 3)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user1.address, max_checkpoints=sp.none, level=30)) == 10 - 2 - 3)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user1.address, max_checkpoints=sp.none, level=35)) == 10 - 2 - 3)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user1.address, max_checkpoints=sp.none, level=40)) == 10 - 2 - 3 - 2)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user1.address, max_checkpoints=sp.none, level=45)) == 10 - 2 - 3 - 2)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user1.address, max_checkpoints=sp.none, level=50)) == 10 - 2 - 3 - 2 + 100)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user1.address, max_checkpoints=sp.none, level=59)) == 10 - 2 - 3 - 2 + 100)

    # The first user transfers some tokens to the third user
    fa2.transfer([sp.record(
            from_=user1.address,
            txs=[sp.record(to_=user3.address, token_id=0, amount=15)])
        ]).run(sender=user1, level=70)

    # Check that the contract information has been updated
    scenario.verify(fa2.data.checkpoints[(user1.address, 5)].level == 70)
    scenario.verify(fa2.data.checkpoints[(user1.address, 5)].balance == 10 - 2 - 3 - 2 + 100 + 5 - 15)
    scenario.verify(fa2.data.checkpoints[(user3.address, 2)].level == 70)
    scenario.verify(fa2.data.checkpoints[(user3.address, 2)].balance == 3 + 2 + 1 + 15)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user1.address, max_checkpoints=sp.none, level=9)) == 0)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user1.address, max_checkpoints=sp.none, level=10)) == 10)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user1.address, max_checkpoints=sp.none, level=11)) == 10)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user1.address, max_checkpoints=sp.none, level=20)) == 10 - 2 - 3)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user1.address, max_checkpoints=sp.none, level=25)) == 10 - 2 - 3)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user1.address, max_checkpoints=sp.none, level=30)) == 10 - 2 - 3)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user1.address, max_checkpoints=sp.none, level=35)) == 10 - 2 - 3)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user1.address, max_checkpoints=sp.none, level=40)) == 10 - 2 - 3 - 2)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user1.address, max_checkpoints=sp.none, level=45)) == 10 - 2 - 3 - 2)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user1.address, max_checkpoints=sp.none, level=50)) == 10 - 2 - 3 - 2 + 100)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user1.address, max_checkpoints=sp.none, level=59)) == 10 - 2 - 3 - 2 + 100)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user1.address, max_checkpoints=sp.none, level=60)) == 10 - 2 - 3 - 2 + 100 + 5)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user1.address, max_checkpoints=sp.none, level=61)) == 10 - 2 - 3 - 2 + 100 + 5)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user2.address, max_checkpoints=sp.none, level=9)) == 0)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user2.address, max_checkpoints=sp.none, level=10)) == 20)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user2.address, max_checkpoints=sp.none, level=11)) == 20)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user2.address, max_checkpoints=sp.none, level=20)) == 20 + 2)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user2.address, max_checkpoints=sp.none, level=25)) == 20 + 2)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user2.address, max_checkpoints=sp.none, level=30)) == 20 + 2)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user2.address, max_checkpoints=sp.none, level=35)) == 20 + 2)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user2.address, max_checkpoints=sp.none, level=40)) == 20 + 2 - 1)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user2.address, max_checkpoints=sp.none, level=45)) == 20 + 2 - 1)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user2.address, max_checkpoints=sp.none, level=50)) == 20 + 2 - 1)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user2.address, max_checkpoints=sp.none, level=59)) == 20 + 2 - 1)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user2.address, max_checkpoints=sp.none, level=60)) == 20 + 2 - 1 - 5)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user2.address, max_checkpoints=sp.none, level=61)) == 20 + 2 - 1 - 5)

    # Execute something to update the level
    fa2.transfer_administrator(user2.address).run(sender=admin, level=80)

    # Check that the contract information has been updated
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user1.address, max_checkpoints=sp.none, level=9)) == 0)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user1.address, max_checkpoints=sp.none, level=10)) == 10)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user1.address, max_checkpoints=sp.none, level=11)) == 10)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user1.address, max_checkpoints=sp.none, level=20)) == 10 - 2 - 3)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user1.address, max_checkpoints=sp.none, level=25)) == 10 - 2 - 3)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user1.address, max_checkpoints=sp.none, level=30)) == 10 - 2 - 3)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user1.address, max_checkpoints=sp.none, level=35)) == 10 - 2 - 3)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user1.address, max_checkpoints=sp.none, level=40)) == 10 - 2 - 3 - 2)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user1.address, max_checkpoints=sp.none, level=45)) == 10 - 2 - 3 - 2)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user1.address, max_checkpoints=sp.none, level=50)) == 10 - 2 - 3 - 2 + 100)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user1.address, max_checkpoints=sp.none, level=59)) == 10 - 2 - 3 - 2 + 100)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user1.address, max_checkpoints=sp.none, level=60)) == 10 - 2 - 3 - 2 + 100 + 5)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user1.address, max_checkpoints=sp.none, level=61)) == 10 - 2 - 3 - 2 + 100 + 5)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user1.address, max_checkpoints=sp.none, level=70)) == 10 - 2 - 3 - 2 + 100 + 5 - 15)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user1.address, max_checkpoints=sp.none, level=77)) == 10 - 2 - 3 - 2 + 100 + 5 - 15)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user3.address, max_checkpoints=sp.none, level=9)) == 0)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user3.address, max_checkpoints=sp.none, level=10)) == 0)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user3.address, max_checkpoints=sp.none, level=11)) == 0)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user3.address, max_checkpoints=sp.none, level=20)) == 3)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user3.address, max_checkpoints=sp.none, level=25)) == 3)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user3.address, max_checkpoints=sp.none, level=30)) == 3)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user3.address, max_checkpoints=sp.none, level=35)) == 3)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user3.address, max_checkpoints=sp.none, level=40)) == 3 + 2 + 1)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user3.address, max_checkpoints=sp.none, level=45)) == 3 + 2 + 1)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user3.address, max_checkpoints=sp.none, level=50)) == 3 + 2 + 1)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user3.address, max_checkpoints=sp.none, level=59)) == 3 + 2 + 1)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user3.address, max_checkpoints=sp.none, level=60)) == 3 + 2 + 1)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user3.address, max_checkpoints=sp.none, level=61)) == 3 + 2 + 1)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user3.address, max_checkpoints=sp.none, level=70)) == 3 + 2 + 1 + 15)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user3.address, max_checkpoints=sp.none, level=77)) == 3 + 2 + 1 + 15)

    # Check that setting the maximum checkpoints to use works as expected
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user1.address, max_checkpoints=sp.some(100), level=59)) == 10 - 2 - 3 - 2 + 100)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user1.address, max_checkpoints=sp.some(6), level=59)) == 10 - 2 - 3 - 2 + 100)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user1.address, max_checkpoints=sp.some(4), level=59)) == 10 - 2 - 3 - 2 + 100)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user1.address, max_checkpoints=sp.some(3), level=59)) == 10 - 2 - 3 - 2 + 100)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user1.address, max_checkpoints=sp.some(2), level=59)) == 0)
    scenario.verify(fa2.get_prior_balance(sp.record(owner=user1.address, max_checkpoints=sp.some(1), level=59)) == 0)
    scenario.verify(sp.is_failing(fa2.get_prior_balance(sp.record(owner=user1.address, max_checkpoints=sp.some(0), level=59))))


@sp.add_test(name="Test balance of")
def test_balance_of():
    # Get the test environment
    testEnvironment = get_test_environment()
    scenario = testEnvironment["scenario"]
    initial_owner = testEnvironment["initial_owner"]
    user1 = testEnvironment["user1"]
    user2 = testEnvironment["user2"]
    user3 = testEnvironment["user3"]
    fa2 = testEnvironment["fa2"]

    # Initialize the dummy contract and add it to the test scenario
    dummyContract = Dummy()
    scenario += dummyContract

    # Get the contract handler to the receive_balances entry point
    c = sp.contract(
            t=sp.TList(sp.TRecord(
                request=sp.TRecord(owner=sp.TAddress, token_id=sp.TNat).layout(("owner", "token_id")),
                balance=sp.TNat).layout(("request", "balance"))),
            address=dummyContract.address,
            entry_point="receive_balances").open_some()

    # Transfer some editions from the initial owner to two users
    fa2.transfer([
        sp.record(
            from_=initial_owner.address,
            txs=[sp.record(to_=user1.address, token_id=0, amount=10),
                 sp.record(to_=user2.address, token_id=0, amount=20)])
        ]).run(sender=initial_owner)

    # Check the balances using the on-chain view
    scenario.verify(fa2.get_balance(sp.record(owner=user1.address, token_id=0)) == 10)
    scenario.verify(fa2.get_balance(sp.record(owner=user2.address, token_id=0)) == 20)

    # Check that it doesn't fail if there is not row for that information in the ledger
    scenario.verify(fa2.get_balance(sp.record(owner=user3.address, token_id=0)) == 0)

    # Check that it fails if the token doesn't exist
    scenario.verify(sp.is_failing(fa2.get_balance(sp.record(owner=user1.address, token_id=10))))

    # Check that asking for the token balances fails if the token doesn't exist
    fa2.balance_of(sp.record(
        requests=[sp.record(owner=user1.address, token_id=10)],
        callback=c)).run(valid=False, sender=user3, exception="FA2_TOKEN_UNDEFINED")

    # Ask for the token balances
    fa2.balance_of(sp.record(
        requests=[
            sp.record(owner=user1.address, token_id=0),
            sp.record(owner=user2.address, token_id=0),
            sp.record(owner=user3.address, token_id=0)],
        callback=c)).run(sender=user3)

    # Check that the returned balances are correct
    scenario.verify(dummyContract.data.balances[(user1.address, 0)] == 10)
    scenario.verify(dummyContract.data.balances[(user2.address, 0)] == 20)
    scenario.verify(dummyContract.data.balances[(user3.address, 0)] == 0)


@sp.add_test(name="Test update operators")
def test_update_operators():
    # Get the test environment
    testEnvironment = get_test_environment()
    scenario = testEnvironment["scenario"]
    admin = testEnvironment["admin"]
    initial_owner = testEnvironment["initial_owner"]
    user1 = testEnvironment["user1"]
    user2 = testEnvironment["user2"]
    user3 = testEnvironment["user3"]
    fa2 = testEnvironment["fa2"]

    # Transfer some editions from the initial owner to two users
    fa2.transfer([
        sp.record(
            from_=initial_owner.address,
            txs=[sp.record(to_=user1.address, token_id=0, amount=10),
                 sp.record(to_=user2.address, token_id=0, amount=20)])
        ]).run(sender=initial_owner)

    # Check that the operators information is empty
    scenario.verify(~fa2.is_operator(
        sp.record(owner=user1.address, operator=user2.address, token_id=0)))
    scenario.verify(~fa2.is_operator(
        sp.record(owner=user2.address, operator=user1.address, token_id=0)))

    # Check that is not possible to change the operators if one is not the owner
    fa2.update_operators([
        sp.variant("add_operator", sp.record(
            owner=user1.address,
            operator=user2.address,
            token_id=0))
        ]).run(valid=False, sender=user2, exception="FA2_SENDER_IS_NOT_OWNER")
    fa2.update_operators([
        sp.variant("add_operator", sp.record(
            owner=user1.address,
            operator=user2.address,
            token_id=0))
        ]).run(valid=False, sender=user3, exception="FA2_SENDER_IS_NOT_OWNER")

    # Check that the admin cannot add operators
    fa2.update_operators([
        sp.variant("add_operator", sp.record(
            owner=user1.address,
            operator=user2.address,
            token_id=0))
        ]).run(valid=False, sender=admin, exception="FA2_SENDER_IS_NOT_OWNER")

    # Check that the user can change the operators of token they own
    fa2.update_operators([
        sp.variant("add_operator", sp.record(
            owner=user1.address,
            operator=user3.address,
            token_id=0)),
        sp.variant("add_operator", sp.record(
            owner=user1.address,
            operator=user2.address,
            token_id=0))
        ]).run(sender=user1)

    # Check that the contract information has been updated
    scenario.verify(fa2.is_operator(
        sp.record(owner=user1.address, operator=user3.address, token_id=0)))
    scenario.verify(fa2.is_operator(
        sp.record(owner=user1.address, operator=user2.address, token_id=0)))

    # Check that adding and removing operators works at the same time
    fa2.update_operators([
        sp.variant("remove_operator", sp.record(
            owner=user1.address,
            operator=user3.address,
            token_id=0)),
        sp.variant("add_operator", sp.record(
            owner=user1.address,
            operator=user2.address,
            token_id=0))
        ]).run(sender=user1)

    # Check that the contract information has been updated
    scenario.verify(~fa2.is_operator(
        sp.record(owner=user1.address, operator=user3.address, token_id=0)))
    scenario.verify(fa2.is_operator(
        sp.record(owner=user1.address, operator=user2.address, token_id=0)))

    # Check that removing an operator that doesn't exist works
    fa2.update_operators([
        sp.variant("remove_operator", sp.record(
            owner=user1.address,
            operator=user3.address,
            token_id=0))
        ]).run(sender=user1)

    # Check that the contract information has been updated
    scenario.verify(~fa2.is_operator(
        sp.record(owner=user1.address, operator=user3.address, token_id=0)))

    # Check operators cannot change the operators of editions that they don't own
    fa2.update_operators([
        sp.variant("add_operator", sp.record(
            owner=user1.address,
            operator=user3.address,
            token_id=0))
        ]).run(valid=False, sender=user2, exception="FA2_SENDER_IS_NOT_OWNER")
    fa2.update_operators([
        sp.variant("remove_operator", sp.record(
            owner=user1.address,
            operator=user2.address,
            token_id=0))
        ]).run(valid=False, sender=user2, exception="FA2_SENDER_IS_NOT_OWNER")

    # Check that the admin cannot remove operators
    fa2.update_operators([
        sp.variant("remove_operator", sp.record(
            owner=user1.address,
            operator=user2.address,
            token_id=0))
        ]).run(valid=False, sender=admin, exception="FA2_SENDER_IS_NOT_OWNER")


@sp.add_test(name="Test transfer and accept administrator")
def test_transfer_and_accept_administrator():
    # Get the test environment
    testEnvironment = get_test_environment()
    scenario = testEnvironment["scenario"]
    admin = testEnvironment["admin"]
    user1 = testEnvironment["user1"]
    user2 = testEnvironment["user2"]
    fa2 = testEnvironment["fa2"]

    # Check the original administrator
    scenario.verify(fa2.data.administrator == admin.address)

    # Check that is not possible to accept the administrator position if it's not set
    fa2.accept_administrator().run(valid=False, sender=admin, exception="FA2_NO_NEW_ADMIN")

    # Check that only the admin can transfer the administrator
    new_administrator = user1.address
    fa2.transfer_administrator(new_administrator).run(valid=False, sender=user1, exception="FA2_NOT_ADMIN")
    fa2.transfer_administrator(new_administrator).run(sender=admin)

    # Check that the proposed administrator is updated
    scenario.verify(fa2.data.proposed_administrator.open_some() == new_administrator)

    # Check that only the proposed administrator can accept the administrator position
    fa2.accept_administrator().run(valid=False, sender=admin, exception="FA2_NOT_PROPOSED_ADMIN")
    fa2.accept_administrator().run(sender=user1)

    # Check that the administrator is updated
    scenario.verify(fa2.data.administrator == new_administrator)
    scenario.verify(~fa2.data.proposed_administrator.is_some())

    # Check that only the new administrator can propose a new administrator
    new_administrator = user2.address
    fa2.transfer_administrator(new_administrator).run(valid=False, sender=admin, exception="FA2_NOT_ADMIN")
    fa2.transfer_administrator(new_administrator).run(sender=user1)

    # Check that the proposed administrator is updated
    scenario.verify(fa2.data.proposed_administrator.open_some() == new_administrator)


@sp.add_test(name="Test set metadata")
def test_set_metadata():
    # Get the test environment
    testEnvironment = get_test_environment()
    scenario = testEnvironment["scenario"]
    admin = testEnvironment["admin"]
    user1 = testEnvironment["user1"]
    fa2 = testEnvironment["fa2"]

    # Check that only the admin can update the metadata
    new_metadata = sp.record(k="", v=sp.utils.bytes_of_string("ipfs://zzzz"))
    fa2.set_metadata(new_metadata).run(valid=False, sender=user1, exception="FA2_NOT_ADMIN")
    fa2.set_metadata(new_metadata).run(sender=admin)

    # Check that the metadata is updated
    scenario.verify(fa2.data.metadata[new_metadata.k] == new_metadata.v)

    # Add some extra metadata
    extra_metadata = sp.record(k="aaa", v=sp.utils.bytes_of_string("ipfs://ffff"))
    fa2.set_metadata(extra_metadata).run(sender=admin)

    # Check that the two metadata entries are present
    scenario.verify(fa2.data.metadata[new_metadata.k] == new_metadata.v)
    scenario.verify(fa2.data.metadata[extra_metadata.k] == extra_metadata.v)


@sp.add_test(name="Test add max share exception")
def test_add_max_share_exception():
    # Get the test environment
    testEnvironment = get_test_environment()
    scenario = testEnvironment["scenario"]
    admin = testEnvironment["admin"]
    initial_owner = testEnvironment["initial_owner"]
    user1 = testEnvironment["user1"]
    user2 = testEnvironment["user2"]
    user3 = testEnvironment["user3"]
    fa2 = testEnvironment["fa2"]

    # Check that it's not possible to transfer more than the allowed share of tokens
    fa2.transfer([
        sp.record(
            from_=initial_owner.address,
            txs=[sp.record(to_=user1.address, token_id=0, amount=fa2.data.max_share)])
        ]).run(valid=False, sender=initial_owner, exception="FA2_SHARE_EXCESS")
 
    # Add the first user address as an exception
    fa2.add_max_share_exception(user1.address).run(sender=admin)

    # Check that now is possible to transfer more than the allowed share of tokens
    fa2.transfer([
        sp.record(
            from_=initial_owner.address,
            txs=[sp.record(to_=user1.address, token_id=0, amount=fa2.data.max_share)])
        ]).run(sender=initial_owner)

    # Add user 2 as another exception
    fa2.add_max_share_exception(user2.address).run(sender=admin)

    # Check that now is possible to transfer more than the allowed share of tokens
    fa2.transfer([
        sp.record(
            from_=initial_owner.address,
            txs=[sp.record(to_=user2.address, token_id=0, amount=fa2.data.max_share + 100)])
        ]).run(sender=initial_owner)

    # Check that only the admin can add exceptions
    fa2.add_max_share_exception(user3.address).run(valid=False, sender=initial_owner, exception="FA2_NOT_ADMIN")
    fa2.add_max_share_exception(user3.address).run(valid=False, sender=user2, exception="FA2_NOT_ADMIN")

    # Check that the contract information has been updated
    scenario.verify(fa2.get_balance(sp.record(owner=initial_owner.address, token_id=0)) == sp.as_nat(fa2.data.supply - (2 * fa2.data.max_share + 100)))
    scenario.verify(fa2.get_balance(sp.record(owner=user1.address, token_id=0)) == fa2.data.max_share)
    scenario.verify(fa2.get_balance(sp.record(owner=user2.address, token_id=0)) == fa2.data.max_share + 100)
    scenario.verify(fa2.get_balance(sp.record(owner=user3.address, token_id=0)) == 0)
    scenario.verify(fa2.data.max_share_exceptions.contains(initial_owner.address))
    scenario.verify(fa2.data.max_share_exceptions.contains(user1.address))
    scenario.verify(fa2.data.max_share_exceptions.contains(user2.address))
    scenario.verify(~fa2.data.max_share_exceptions.contains(user3.address))

    # Remove user 2 from the exception list
    fa2.add_max_share_exception(user2.address).run(sender=admin)

    # Check that the exception list contains only the initial owner and the first user
    scenario.verify(fa2.data.max_share_exceptions.contains(initial_owner.address))
    scenario.verify(fa2.data.max_share_exceptions.contains(user1.address))
    scenario.verify(~fa2.data.max_share_exceptions.contains(user2.address))
    scenario.verify(~fa2.data.max_share_exceptions.contains(user3.address))

    # Check that user 2 can't receive more tokens, but can transfer their tokens
    fa2.transfer([
        sp.record(
            from_=initial_owner.address,
            txs=[sp.record(to_=user2.address, token_id=0, amount=1)])
        ]).run(valid=False, sender=initial_owner, exception="FA2_SHARE_EXCESS")
    fa2.transfer([
        sp.record(
            from_=user2.address,
            txs=[sp.record(to_=user3.address, token_id=0, amount=10)])
        ]).run(sender=user2)

    # Check that user 1 can still receive more tokens
    fa2.transfer([
        sp.record(
            from_=initial_owner.address,
            txs=[sp.record(to_=user1.address, token_id=0, amount=1)])
        ]).run(sender=initial_owner)

    # Check that the contract information has been updated
    scenario.verify(fa2.get_balance(sp.record(owner=initial_owner.address, token_id=0)) == sp.as_nat(fa2.data.supply - (2 * fa2.data.max_share + 100 + 1)))
    scenario.verify(fa2.get_balance(sp.record(owner=user1.address, token_id=0)) == fa2.data.max_share + 1)
    scenario.verify(fa2.get_balance(sp.record(owner=user2.address, token_id=0)) == sp.as_nat(fa2.data.max_share + 100 - 10))
    scenario.verify(fa2.get_balance(sp.record(owner=user3.address, token_id=0)) == 10)


@sp.add_test(name="Test set max share")
def test_set_max_share():
    # Get the test environment
    testEnvironment = get_test_environment()
    scenario = testEnvironment["scenario"]
    admin = testEnvironment["admin"]
    initial_owner = testEnvironment["initial_owner"]
    user1 = testEnvironment["user1"]
    user2 = testEnvironment["user2"]
    user3 = testEnvironment["user3"]
    fa2 = testEnvironment["fa2"]

    # Check that it's not possible to transfer more than the allowed share of tokens
    original_max_share = scenario.compute(fa2.data.max_share)
    fa2.transfer([
        sp.record(
            from_=initial_owner.address,
            txs=[sp.record(to_=user1.address, token_id=0, amount=original_max_share)])
        ]).run(valid=False, sender=initial_owner, exception="FA2_SHARE_EXCESS")

    # Check that only the admin can change the max share parameter
    new_max_share = fa2.data.supply * 3 // 100
    fa2.set_max_share(new_max_share).run(valid=False, sender=user2, exception="FA2_NOT_ADMIN")
    fa2.set_max_share(new_max_share).run(sender=admin)

    # Check that the max share is updated
    scenario.verify(fa2.data.max_share != original_max_share)
    scenario.verify(fa2.data.max_share == new_max_share)

    # Check that it's not possible to transfer more than the allowed share of tokens
    fa2.transfer([
        sp.record(
            from_=initial_owner.address,
            txs=[sp.record(to_=user1.address, token_id=0, amount=new_max_share)])
        ]).run(valid=False, sender=initial_owner, exception="FA2_SHARE_EXCESS")
    fa2.transfer([
        sp.record(
            from_=initial_owner.address,
            txs=[sp.record(to_=user1.address, token_id=0, amount=sp.as_nat(new_max_share - 1))])
        ]).run(sender=initial_owner)

    # Check that the maximum share can only be set within the 1% and 10% limits
    fa2.set_max_share(sp.as_nat((fa2.data.supply // 100) - 1)).run(
        valid=False, sender=admin, exception="FA2_WRONG_MAX_SHARE")
    fa2.set_max_share((fa2.data.supply // 10) + 1).run(
        valid=False, sender=admin, exception="FA2_WRONG_MAX_SHARE")
    fa2.set_max_share(fa2.data.supply // 100).run(sender=admin)
    fa2.set_max_share(fa2.data.supply // 10).run(sender=admin)


if ('tzip16_error_lint' in environ.get('TEIA_SC_PARAMS', '').split(':') and
    type(daoTokenModule.DAOToken.error_collection).__name__ == 'ErrorCollection'):

    @sp.add_test(name="Lint FAILWITH messages")
    def test_error_message_rules():
        scenario = sp.test_scenario()
        daoTokenModule.DAOToken.error_collection.scenario_linting_report(scenario)

