"""Unit tests for the dead man's switch contract class.

"""

import smartpy as sp

# Import the dead man's switch and FA2 contract modules
deadMansSwitchModule = sp.io.import_script_from_url("file:contracts/deadMansSwitch.py")
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
    admin = sp.test_account("admin")
    multisig = sp.test_account("multisig")
    other = sp.test_account("other")

    # Initialize the dead man's switch contract
    deadMansSwitch = deadMansSwitchModule.DeadMansSwitch(
        metadata=sp.utils.metadata_of_url("ipfs://aaa"),
        administrator=admin.address,
        multisig=multisig.address,
        ping_interval=30)
    deadMansSwitch.set_initial_balance(sp.tez(10))
    scenario += deadMansSwitch

    # Create the FA2 token contract and add it to the test scenario
    fa2_admin = sp.test_account("fa2_admin")
    fa2 = fa2Module.FA2(
        config=fa2Module.FA2_config(),
        admin=fa2_admin.address,
        meta=sp.utils.metadata_of_url("ipfs://aaa"))
    scenario += fa2

    # Mint one token
    fa2.mint(
        address=admin.address,
        token_id=sp.nat(0),
        amount=sp.nat(100),
        token_info={"": sp.utils.bytes_of_string("ipfs://bbb")}).run(sender=fa2_admin)

    # Save all the variables in a test environment dictionary
    testEnvironment = {
        "scenario": scenario,
        "admin": admin,
        "multisig": multisig,
        "other": other,
        "deadMansSwitch": deadMansSwitch,
        "fa2": fa2}

    return testEnvironment


@sp.add_test(name="Test default entrypoint")
def test_default_entrypoint():
    # Get the test environment
    testEnvironment = get_test_environment()
    scenario = testEnvironment["scenario"]
    admin = testEnvironment["admin"]
    multisig = testEnvironment["multisig"]
    other = testEnvironment["other"]
    deadMansSwitch = testEnvironment["deadMansSwitch"]

    # Check that the admin can send tez to the contract
    deadMansSwitch.default(sp.unit).run(sender=admin, amount=sp.tez(1))

    # Check that the tez are now part of the contract balance
    scenario.verify(deadMansSwitch.balance == sp.tez(10 + 1))

    # Check that any other user can also send tez to the contract
    deadMansSwitch.default(sp.unit).run(sender=multisig, amount=sp.tez(2))
    deadMansSwitch.default(sp.unit).run(sender=other, amount=sp.tez(3))

    # Check that the tez have been added to the contract balance
    scenario.verify(deadMansSwitch.balance == sp.tez(10 + 1 + 2 + 3))


@sp.add_test(name="Test transfer tez")
def test_transfer_tezt():
    # Get the test environment
    testEnvironment = get_test_environment()
    scenario = testEnvironment["scenario"]
    admin = testEnvironment["admin"]
    multisig = testEnvironment["multisig"]
    other = testEnvironment["other"]
    deadMansSwitch = testEnvironment["deadMansSwitch"]

    # Create the account that will receive the tez transfers and add it to the
    # scenario
    recipient = Recipient()
    scenario += recipient

    # Check that the admin is able to transfer tez
    deadMansSwitch.transfer_tez(
        amount=sp.tez(1),
        destination=recipient.address).run(sender=admin, now=sp.timestamp(10))

    # Check that the correct tez amount has been sent
    scenario.verify(recipient.balance == sp.tez(1))
    scenario.verify(deadMansSwitch.balance == sp.tez(10 - 1))

    # Check that the last ping timestamp has been updated
    scenario.verify(deadMansSwitch.data.last_ping == sp.timestamp(10))

    # Check that other users cannot transfer tez from the contract
    deadMansSwitch.transfer_tez(
        amount=sp.tez(1),
        destination=recipient.address).run(valid=False, sender=multisig)

    deadMansSwitch.transfer_tez(
        amount=sp.tez(1),
        destination=recipient.address).run(valid=False, sender=other)


@sp.add_test(name="Test transfer fa2 token")
def test_transfer_fa2_token():
    # Get the test environment
    testEnvironment = get_test_environment()
    scenario = testEnvironment["scenario"]
    admin = testEnvironment["admin"]
    multisig = testEnvironment["multisig"]
    other = testEnvironment["other"]
    deadMansSwitch = testEnvironment["deadMansSwitch"]
    fa2 = testEnvironment["fa2"]

    # Transfer some tokens to the contract
    fa2.transfer(sp.list([sp.record(
        from_=admin.address,
        txs=sp.list([sp.record(
            to_=deadMansSwitch.address,
            token_id=0,
            amount=20)]))])).run(sender=admin)

    # Check that the token ledger information is correct
    scenario.verify(fa2.data.ledger[(admin.address, 0)].balance == 100 - 20)
    scenario.verify(fa2.data.ledger[(deadMansSwitch.address, 0)].balance == 20)

    # Check that the admin is able to transfer some token editions
    deadMansSwitch.transfer_tokens(
        token_address=fa2.address,
        token_id=sp.some(0),
        amount=10,
        destination=other.address).run(sender=admin, now=sp.timestamp(10))

    # Check that the token ledger information is correct
    scenario.verify(fa2.data.ledger[(admin.address, 0)].balance == 100 - 20)
    scenario.verify(fa2.data.ledger[(deadMansSwitch.address, 0)].balance == 20 - 10)
    scenario.verify(fa2.data.ledger[(other.address, 0)].balance == 10)

    # Check that the last ping timestamp has been updated
    scenario.verify(deadMansSwitch.data.last_ping == sp.timestamp(10))

    # Check that other users cannot transfer tokens from the contract
    deadMansSwitch.transfer_tokens(
        token_address=fa2.address,
        token_id=sp.some(0),
        amount=10,
        destination=other.address).run(valid=False, sender=multisig)

    deadMansSwitch.transfer_tokens(
        token_address=fa2.address,
        token_id=sp.some(0),
        amount=10,
        destination=other.address).run(valid=False, sender=other)
