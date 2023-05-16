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

    # Save all the variables in a test environment dictionary
    testEnvironment = {
        "scenario": scenario,
        "admin": admin,
        "multisig": multisig,
        "other": other,
        "deadMansSwitch": deadMansSwitch}

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
    recipient1 = Recipient()
    recipient2 = Recipient()
    scenario += recipient1
    scenario += recipient2

    # Check that the admin is able to transfer tez
    deadMansSwitch.transfer_tez([
        sp.record(amount=sp.tez(1), destination=recipient1.address),
        sp.record(amount=sp.tez(2), destination=recipient2.address)]).run(sender=admin, now=sp.timestamp(10))

    # Check that the correct tez amount has been sent
    scenario.verify(recipient1.balance == sp.tez(1))
    scenario.verify(recipient2.balance == sp.tez(2))
    scenario.verify(deadMansSwitch.balance == sp.tez(10 - 1 - 2))

    # Check that the last ping timestamp has been updated
    scenario.verify(deadMansSwitch.data.last_ping == sp.timestamp(10))

    # Check that other users cannot transfer tez from the contract
    deadMansSwitch.transfer_tez([
        sp.record(amount=sp.tez(1), destination=recipient1.address),
        sp.record(amount=sp.tez(2), destination=recipient2.address)]).run(
            valid=False, sender=multisig, exception="DM_NOT_ADMIN")
    deadMansSwitch.transfer_tez([
        sp.record(amount=sp.tez(1), destination=recipient1.address),
        sp.record(amount=sp.tez(2), destination=recipient2.address)]).run(
            valid=False, sender=other, exception="DM_NOT_ADMIN")


@sp.add_test(name="Test transfer fa2 token")
def test_transfer_fa2_token():
    # Get the test environment
    testEnvironment = get_test_environment()
    scenario = testEnvironment["scenario"]
    admin = testEnvironment["admin"]
    multisig = testEnvironment["multisig"]
    other = testEnvironment["other"]
    deadMansSwitch = testEnvironment["deadMansSwitch"]

    # Create the FA2 token contract and add it to the test scenario
    fa2_admin = sp.test_account("fa2_admin")
    fa2 = fa2Module.FA2(
        config=fa2Module.FA2_config(),
        admin=fa2_admin.address,
        meta=sp.utils.metadata_of_url("ipfs://aaa"))
    scenario += fa2

    # Mint one token
    fa2.mint(
        address=other.address,
        token_id=sp.nat(0),
        amount=sp.nat(100),
        token_info={"": sp.utils.bytes_of_string("ipfs://bbb")}).run(sender=fa2_admin)

    # Transfer some tokens to the contract
    fa2.transfer(sp.list([sp.record(
        from_=other.address,
        txs=sp.list([sp.record(
            to_=deadMansSwitch.address,
            token_id=0,
            amount=20)]))])).run(sender=other)

    # Check that the token ledger information is correct
    scenario.verify(fa2.data.ledger[(other.address, 0)].balance == 100 - 20)
    scenario.verify(fa2.data.ledger[(deadMansSwitch.address, 0)].balance == 20)

    # Check that the admin is able to transfer some token editions
    deadMansSwitch.transfer_tokens(
        token_address=fa2.address,
        token_id=sp.some(0),
        amount=10,
        destination=multisig.address).run(sender=admin, now=sp.timestamp(10))

    # Check that the token ledger information is correct
    scenario.verify(fa2.data.ledger[(other.address, 0)].balance == 100 - 20)
    scenario.verify(fa2.data.ledger[(deadMansSwitch.address, 0)].balance == 20 - 10)
    scenario.verify(fa2.data.ledger[(multisig.address, 0)].balance == 10)

    # Check that the last ping timestamp has been updated
    scenario.verify(deadMansSwitch.data.last_ping == sp.timestamp(10))

    # Check that other users cannot transfer tokens from the contract
    deadMansSwitch.transfer_tokens(
        token_address=fa2.address,
        token_id=sp.some(0),
        amount=10,
        destination=other.address).run(
            valid=False, sender=multisig, exception="DM_NOT_ADMIN")
    deadMansSwitch.transfer_tokens(
        token_address=fa2.address,
        token_id=sp.some(0),
        amount=10,
        destination=other.address).run(
            valid=False, sender=other, exception="DM_NOT_ADMIN")


@sp.add_test(name="Test ping")
def test_ping():
    # Get the test environment
    testEnvironment = get_test_environment()
    scenario = testEnvironment["scenario"]
    admin = testEnvironment["admin"]
    multisig = testEnvironment["multisig"]
    other = testEnvironment["other"]
    deadMansSwitch = testEnvironment["deadMansSwitch"]

    # The admin pings the contract
    deadMansSwitch.ping().run(sender=admin, now=sp.timestamp(10))

    # Check that the last ping timestamp has been updated
    scenario.verify(deadMansSwitch.data.last_ping == sp.timestamp(10))

    # Check that other users cannot ping the contract
    deadMansSwitch.ping().run(
        valid=False, sender=multisig, now=sp.timestamp(20), exception="DM_NOT_ADMIN")
    deadMansSwitch.ping().run(
        valid=False, sender=other, now=sp.timestamp(20), exception="DM_NOT_ADMIN")

    # The admin pings the contract again
    deadMansSwitch.ping().run(sender=admin, now=sp.timestamp(30))

    # Check that the last ping timestamp has been updated
    scenario.verify(deadMansSwitch.data.last_ping == sp.timestamp(30))


@sp.add_test(name="Test take control")
def test_take_control():
    # Get the test environment
    testEnvironment = get_test_environment()
    scenario = testEnvironment["scenario"]
    admin = testEnvironment["admin"]
    multisig = testEnvironment["multisig"]
    other = testEnvironment["other"]
    deadMansSwitch = testEnvironment["deadMansSwitch"]

    # The admin pings the contract
    deadMansSwitch.ping().run(sender=admin, now=sp.timestamp(10))

    # Check that the last ping timestamp has been updated
    scenario.verify(deadMansSwitch.data.last_ping == sp.timestamp(10))

    # Check that the multisig cannot take control too early
    deadMansSwitch.take_control().run(
        valid=False, sender=multisig, now=sp.timestamp(20), exception="DM_NOT_DEAD")
    deadMansSwitch.take_control().run(
        valid=False, sender=multisig, now=sp.timestamp(10 - 1).add_days(
            sp.to_int(deadMansSwitch.data.ping_interval)), exception="DM_NOT_DEAD")

    # Check that only the multisig cannot take control when the last ping is too old
    timestamp = sp.timestamp(
        10 + 1).add_days(sp.to_int(deadMansSwitch.data.ping_interval))
    deadMansSwitch.take_control().run(
        valid=False, sender=admin, now=timestamp, exception="DM_NOT_MULTISIG")
    deadMansSwitch.take_control().run(
        valid=False, sender=other, now=timestamp, exception="DM_NOT_MULTISIG")
    deadMansSwitch.take_control().run(sender=multisig, now=timestamp)

    # Check that the multisig is the new admin and the last ping has been updated
    scenario.verify(deadMansSwitch.data.administrator == multisig.address)
    scenario.verify(deadMansSwitch.data.last_ping == timestamp)


@sp.add_test(name="Test transfer and accept administrator")
def test_transfer_and_accept_administrator():
    # Get the test environment
    testEnvironment = get_test_environment()
    scenario = testEnvironment["scenario"]
    admin = testEnvironment["admin"]
    multisig = testEnvironment["multisig"]
    other = testEnvironment["other"]
    deadMansSwitch = testEnvironment["deadMansSwitch"]

    # Check the original administrator
    scenario.verify(deadMansSwitch.data.administrator == admin.address)

    # Check that only the admin can transfer the administrator
    new_administrator = other.address
    deadMansSwitch.transfer_administrator(new_administrator).run(
        valid=False, sender=multisig, exception="DM_NOT_ADMIN")
    deadMansSwitch.transfer_administrator(new_administrator).run(
        valid=False, sender=other, exception="DM_NOT_ADMIN")
    deadMansSwitch.transfer_administrator(new_administrator).run(sender=admin)

    # Check that the proposed administrator is updated
    scenario.verify(deadMansSwitch.data.proposed_administrator.open_some() == new_administrator)

    # Check that only the proposed administrator can accept the administrator position
    deadMansSwitch.accept_administrator().run(
        valid=False, sender=admin, exception="DM_NOT_PROPOSED_ADMIN")
    deadMansSwitch.accept_administrator().run(
        valid=False, sender=multisig, exception="DM_NOT_PROPOSED_ADMIN")
    deadMansSwitch.accept_administrator().run(sender=other)

    # Check that the administrator is updated
    scenario.verify(deadMansSwitch.data.administrator == new_administrator)
    scenario.verify(~deadMansSwitch.data.proposed_administrator.is_some())

    # Check that only the new administrator can propose a new administrator
    new_administrator = multisig.address
    deadMansSwitch.transfer_administrator(new_administrator).run(
        valid=False, sender=admin, exception="DM_NOT_ADMIN")
    deadMansSwitch.transfer_administrator(new_administrator).run(sender=other)

    # Check that the proposed administrator is updated
    scenario.verify(deadMansSwitch.data.proposed_administrator.open_some() == new_administrator)


@sp.add_test(name="Test set multisig")
def test_set_multisig():
    # Get the test environment
    testEnvironment = get_test_environment()
    scenario = testEnvironment["scenario"]
    admin = testEnvironment["admin"]
    multisig = testEnvironment["multisig"]
    other = testEnvironment["other"]
    deadMansSwitch = testEnvironment["deadMansSwitch"]

    # Check that only the admin can update the multisig address
    new_multisig = other.address
    deadMansSwitch.set_multisig(new_multisig).run(
        valid=False, sender=multisig, now=sp.timestamp(20), exception="DM_NOT_ADMIN")
    deadMansSwitch.set_multisig(new_multisig).run(
        valid=False, sender=other, now=sp.timestamp(20), exception="DM_NOT_ADMIN")
    deadMansSwitch.set_multisig(new_multisig).run(
        sender=admin, now=sp.timestamp(20))

    # Check that the multisig address is updated
    scenario.verify(deadMansSwitch.data.multisig == new_multisig)

    # Check that the last ping timestamp has been updated
    scenario.verify(deadMansSwitch.data.last_ping == sp.timestamp(20))


@sp.add_test(name="Test set ping interval")
def test_set_ping_interval():
    # Get the test environment
    testEnvironment = get_test_environment()
    scenario = testEnvironment["scenario"]
    admin = testEnvironment["admin"]
    multisig = testEnvironment["multisig"]
    other = testEnvironment["other"]
    deadMansSwitch = testEnvironment["deadMansSwitch"]

    # Check that only the admin can update the ping interval
    new_ping_interval = 100
    deadMansSwitch.set_ping_interval(new_ping_interval).run(
        valid=False, sender=multisig, now=sp.timestamp(20), exception="DM_NOT_ADMIN")
    deadMansSwitch.set_ping_interval(new_ping_interval).run(
        valid=False, sender=other, now=sp.timestamp(20), exception="DM_NOT_ADMIN")
    deadMansSwitch.set_ping_interval(new_ping_interval).run(
        sender=admin, now=sp.timestamp(20))

    # Check that the ping interval is updated
    scenario.verify(deadMansSwitch.data.ping_interval == new_ping_interval)

    # Check that the last ping timestamp has been updated
    scenario.verify(deadMansSwitch.data.last_ping == sp.timestamp(20))

    # Check that it's not possible to set the ping interval to 0
    deadMansSwitch.set_ping_interval(0).run(
        valid=False, sender=admin, now=sp.timestamp(30), exception="DM_INVALID_PING_INTERVAL")
