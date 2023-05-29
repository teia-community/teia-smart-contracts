"""Unit tests for the DAO treasury contract class.

"""

import smartpy as sp

# Import the DAO treasury and fa2 contract modules
daoTreasuryModule = sp.io.import_script_from_url("file:contracts/daoTreasury.py")
fa12Module = sp.io.import_script_from_url("file:contracts/fa12.py")
fa2Module = sp.io.import_script_from_url("file:hen-contracts/fa2.py")


class Recipient(sp.Contract):
    """This contract simulates a user that can receive tez transfers.

    It should only be used to test that tez transfers are sent correctly.

    """

    def __init__(self):
        """Initializes the contract.

        """
        self.init()

    @sp.entry_point
    def default(self, unit):
        """Default entrypoint that allows receiving tez transfers in the same
        way as one would do with a normal tz wallet.

        """
        # Define the input parameter data type
        sp.set_type(unit, sp.TUnit)

        # Do nothing, just receive tez
        pass


def get_test_environment():
    # Initialize the test scenario
    scenario = sp.test_scenario()

    # Create the test accounts
    dao = sp.test_account("dao")
    user = sp.test_account("user")

    # Initialize the DAO treasury contract
    treasury = daoTreasuryModule.DAOTreasury(
        metadata=sp.utils.metadata_of_url("ipfs://aaa"),
        dao=dao.address)
    treasury.set_initial_balance(sp.tez(10))
    scenario += treasury

    # Save all the variables in a test environment dictionary
    testEnvironment = {
        "scenario": scenario,
        "dao": dao,
        "user": user,
        "treasury": treasury}

    return testEnvironment


@sp.add_test(name="Test default entrypoint")
def test_default_entripoint():
    # Get the test environment
    testEnvironment = get_test_environment()
    scenario = testEnvironment["scenario"]
    dao = testEnvironment["dao"]
    user = testEnvironment["user"]
    treasury = testEnvironment["treasury"]

    # Check that any user can send tez to the contract
    treasury.default(sp.unit).run(sender=dao, amount=sp.tez(1))
    treasury.default(sp.unit).run(sender=user, amount=sp.tez(3))

    # Check that the tez are now part of the contract balance
    scenario.verify(treasury.balance == sp.tez(10 + 1 + 3))


@sp.add_test(name="Test transfer mutez")
def test_transfer_mutez():
    # Get the test environment
    testEnvironment = get_test_environment()
    scenario = testEnvironment["scenario"]
    dao = testEnvironment["dao"]
    user = testEnvironment["user"]
    treasury = testEnvironment["treasury"]

    # Create the accounts that will receive the tez transfers and add them to
    # the scenario
    recipient1 = Recipient()
    recipient2 = Recipient()
    scenario += recipient1
    scenario += recipient2

    # Check that only the DAO contract can transfer tez
    mutez_transfers = sp.list([
        sp.record(amount=sp.tez(3), destination=recipient1.address),
        sp.record(amount=sp.tez(2), destination=recipient2.address)])
    treasury.transfer_mutez(mutez_transfers).run(
        valid=False, sender=user, exception="TREASURY_NOT_DAO")
    treasury.transfer_mutez(mutez_transfers).run(sender=dao)

    # Check that the contract balance is correct
    scenario.verify(treasury.balance == sp.tez(10 - 3 - 2))

    # Check that the tez amounts have been sent to the correct destinations
    scenario.verify(recipient1.balance == sp.tez(3))
    scenario.verify(recipient2.balance == sp.tez(2))


@sp.add_test(name="Test transfer fa2 token")
def test_transfer_fa2_token():
    # Get the test environment
    testEnvironment = get_test_environment()
    scenario = testEnvironment["scenario"]
    dao = testEnvironment["dao"]
    user = testEnvironment["user"]
    treasury = testEnvironment["treasury"]

    # Create the FA2 token contract and add it to the test scenario
    admin = sp.test_account("admin")
    fa2 = fa2Module.FA2(
        config=fa2Module.FA2_config(),
        admin=admin.address,
        meta=sp.utils.metadata_of_url("ipfs://aaa"))
    scenario += fa2

    # Mint one token
    fa2.mint(
        address=user.address,
        token_id=sp.nat(0),
        amount=sp.nat(100),
        token_info={"": sp.utils.bytes_of_string("ipfs://bbb")}).run(sender=admin)

    # The user transfers 20 editions of the token to the treasury
    fa2.transfer(sp.list([sp.record(
        from_=user.address,
        txs=sp.list([sp.record(
            to_=treasury.address,
            token_id=0,
            amount=20)]))])).run(sender=user)

    # Check that the token ledger information is correct
    scenario.verify(fa2.data.ledger[(user.address, 0)].balance == 100 - 20)
    scenario.verify(fa2.data.ledger[(treasury.address, 0)].balance == 20)

    # Check that only the DAO contract can transfer the token
    user2 = sp.test_account("user2")
    user3 = sp.test_account("user3")
    token_transfers = sp.record(
        fa2=fa2.address,
        token_id=sp.nat(0),
        distribution=sp.list([
            sp.record(amount=sp.nat(5), destination=user2.address),
            sp.record(amount=sp.nat(1), destination=user3.address)]))
    treasury.transfer_fa2_token(token_transfers).run(
        valid=False, sender=user, exception="TREASURY_NOT_DAO")
    treasury.transfer_fa2_token(token_transfers).run(sender=dao)

    # Check that the token ledger information is correct
    scenario.verify(fa2.data.ledger[(user.address, 0)].balance == 100 - 20)
    scenario.verify(fa2.data.ledger[(treasury.address, 0)].balance == 20 - 5 - 1)
    scenario.verify(fa2.data.ledger[(user2.address, 0)].balance == 5)
    scenario.verify(fa2.data.ledger[(user3.address, 0)].balance == 1)


@sp.add_test(name="Test transfer fa12 token")
def test_transfer_fa12_token():
    # Get the test environment
    testEnvironment = get_test_environment()
    scenario = testEnvironment["scenario"]
    dao = testEnvironment["dao"]
    user = testEnvironment["user"]
    treasury = testEnvironment["treasury"]

    # Create the FA1.2 token contract and add it to the test scenario
    admin = sp.test_account("admin")
    fa12 = fa12Module.FA12(
        administrator=admin.address,
        metadata=sp.utils.metadata_of_url("ipfs://aaa"),
        token_metadata={
            "decimals": sp.utils.bytes_of_string("18"),
            "name": sp.utils.bytes_of_string("My Great Token"),
            "symbol": sp.utils.bytes_of_string("MGT"),
            "icon": sp.utils.bytes_of_string("ipfs://aaa")})
    scenario += fa12

    # Mint some token editions
    fa12.mint(address=user.address, value=sp.nat(100)).run(sender=admin)

    # The user transfers 20 editions of the token to the treasury
    fa12.transfer(sp.record(
        from_=user.address,
        to_=treasury.address,
        value=20)).run(sender=user)

    # Check that the token balances information is correct
    scenario.verify(fa12.data.balances[user.address].balance == 100 - 20)
    scenario.verify(fa12.data.balances[treasury.address].balance == 20)

    # Check that only the DAO contract can transfer the token
    user2 = sp.test_account("user2")
    user3 = sp.test_account("user3")
    token_transfers = sp.record(
        fa12=fa12.address,
        distribution=sp.list([
            sp.record(amount=sp.nat(5), destination=user2.address),
            sp.record(amount=sp.nat(1), destination=user3.address)]))
    treasury.transfer_fa12_token(token_transfers).run(
        valid=False, sender=user, exception="TREASURY_NOT_DAO")
    treasury.transfer_fa12_token(token_transfers).run(sender=dao)

    # Check that the token ledger information is correct
    scenario.verify(fa12.data.balances[user.address].balance == 100 - 20)
    scenario.verify(fa12.data.balances[treasury.address].balance == 20 - 5 - 1)
    scenario.verify(fa12.data.balances[user2.address].balance == 5)
    scenario.verify(fa12.data.balances[user3.address].balance == 1)


@sp.add_test(name="Test set dao")
def test_set_dao():
    # Get the test environment
    testEnvironment = get_test_environment()
    scenario = testEnvironment["scenario"]
    dao = testEnvironment["dao"]
    user = testEnvironment["user"]
    treasury = testEnvironment["treasury"]

    # Check the original DAO contract address
    scenario.verify(treasury.data.dao == dao.address)

    # Check that only the DAO contract can set the new DAO
    treasury.set_dao(user.address).run(
        valid=False, sender=user, exception="TREASURY_NOT_DAO")
    treasury.set_dao(user.address).run(sender=dao)

    # Check that the contract information have been updated
    scenario.verify(treasury.data.dao == user.address)


@sp.add_test(name="Test set delegate")
def test_set_delegate():
    # Get the test environment
    testEnvironment = get_test_environment()
    scenario = testEnvironment["scenario"]
    dao = testEnvironment["dao"]
    user = testEnvironment["user"]
    treasury = testEnvironment["treasury"]

    # Check that only the DAO contract can set the delegate
    voting_powers = {user.public_key_hash: 0}
    delegate = sp.some(user.public_key_hash)
    treasury.set_delegate(delegate).run(
        valid=False, sender=user, voting_powers=voting_powers, exception="TREASURY_NOT_DAO")
    treasury.set_delegate(delegate).run(sender=dao, voting_powers=voting_powers)
