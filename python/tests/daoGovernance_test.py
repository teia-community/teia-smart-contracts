"""Unit tests for the DAO governance class.

"""
from os import environ
import smartpy as sp

# Import the DAO modules
daoTokenModule = sp.io.import_script_from_url("file:contracts/daoToken.py")
daoTreasuryModule = sp.io.import_script_from_url("file:contracts/daoTreasury.py")
daoGovernanceModule = sp.io.import_script_from_url("file:contracts/daoGovernance.py")
representativesModule = sp.io.import_script_from_url("file:contracts/representatives.py")
multisigWalletModule = sp.io.import_script_from_url("file:contracts/multisigWallet_v1.py")


class Recipient(sp.Contract):
    """This contract simulates a user that can recive tez transfers.

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


def get_test_environment(vote_weight_mode="linear", decimals=1):
    # Initialize the test scenario
    scenario = sp.test_scenario()

    # Create the test accounts
    admin = sp.test_account("admin")
    user1 = sp.test_account("user1")
    user2 = sp.test_account("user2")
    user3 = sp.test_account("user3")
    user4 = sp.test_account("user4")
    user5 = sp.test_account("user5")
    user6 = sp.test_account("user6")
    external_user = sp.test_account("external_user")

    # Initialize the DAO token FA2 contract
    token = daoTokenModule.DAOToken(
        administrator=admin.address,
        metadata=sp.utils.metadata_of_url("ipfs://aaa"),
        token_metadata=sp.utils.bytes_of_string("ipfs://bbb"),
        supply=2000 * decimals,
        max_share=500 * decimals)
    scenario += token

    # Initialize the DAO treasury contract
    treasury = daoTreasuryModule.DAOTreasury(
        metadata=sp.utils.metadata_of_url("ipfs://ccc"),
        dao=admin.address)
    treasury.set_initial_balance(sp.tez(10))
    scenario += treasury

    # Initialize the representatives contract
    representatives = representativesModule.Representatives(
        metadata=sp.utils.metadata_of_url("ipfs://ddd"),
        representatives={
            user1.address: "community1",
            user2.address: "community2",
            user3.address: "community3",
            user6.address: "community4"},
        minimum_votes=2,
        expiration_time=3)
    scenario += representatives

    # Initialize the DAO guardians contract
    guardians = multisigWalletModule.MultisigWallet(
        metadata=sp.utils.metadata_of_url("ipfs://eee"),
        users=sp.set([user4.address, user5.address]),
        minimum_votes=2,
        expiration_time=3)
    scenario += guardians

    # Initialize the DAO governance contract
    dao = daoGovernanceModule.DAOGovernance(
        metadata=sp.utils.metadata_of_url("ipfs://fff"),
        administrator=admin.address,
        treasury=treasury.address,
        token=token.address,
        representatives=representatives.address,
        guardians=guardians.address,
        quorum=800,
        governance_parameters=sp.record(
            vote_method=sp.variant(vote_weight_mode, sp.unit),
            vote_period=5,
            wait_period=2,
            escrow_amount=10 * decimals,
            escrow_return=40,
            min_amount=1,
            supermajority=60,
            representatives_share=30,
            quorum_update_period=3,
            quorum_update=20,
            quorum_max_change=20,
            min_quorum=100,
            max_quorum=1300))
    scenario += dao

    # Update the treasury DAO contract address
    treasury.set_dao(dao.address).run(sender=admin)

    # Add the DAO treasury and DAO governance contracts as maximum share exceptions
    token.add_max_share_exception(treasury.address).run(sender=admin)
    token.add_max_share_exception(dao.address).run(sender=admin)

    # Transfer some the editions from the admin to the users and the treasury
    token.transfer([
        sp.record(
            from_=admin.address,
            txs=[
                sp.record(to_=user1.address, token_id=0, amount=100 * decimals),
                sp.record(to_=user2.address, token_id=0, amount=200 * decimals),
                sp.record(to_=user3.address, token_id=0, amount=300 * decimals),
                sp.record(to_=user4.address, token_id=0, amount=400 * decimals),
                sp.record(to_=user5.address, token_id=0, amount=5 * decimals),
                sp.record(to_=user6.address, token_id=0, amount=5 * decimals),
                sp.record(to_=treasury.address, token_id=0, amount=990 * decimals)])
        ]).run(sender=admin)

    # Add the DAO as operator to the users tokens
    token.update_operators([sp.variant("add_operator", sp.record(
        owner=user1.address, operator=dao.address, token_id=0))]).run(sender=user1)
    token.update_operators([sp.variant("add_operator", sp.record(
        owner=user2.address, operator=dao.address, token_id=0))]).run(sender=user2)
    token.update_operators([sp.variant("add_operator", sp.record(
        owner=user3.address, operator=dao.address, token_id=0))]).run(sender=user3)
    token.update_operators([sp.variant("add_operator", sp.record(
        owner=user4.address, operator=dao.address, token_id=0))]).run(sender=user4)
    token.update_operators([sp.variant("add_operator", sp.record(
        owner=user5.address, operator=dao.address, token_id=0))]).run(sender=user5)
    token.update_operators([sp.variant("add_operator", sp.record(
        owner=user6.address, operator=dao.address, token_id=0))]).run(sender=user6)

    # Save all the variables in a test environment dictionary
    testEnvironment = {
        "scenario": scenario,
        "admin": admin,
        "user1": user1,
        "user2": user2,
        "user3": user3,
        "user4": user4,
        "user5": user5,
        "user6": user6,
        "external_user": external_user,
        "token": token,
        "treasury": treasury,
        "representatives": representatives,
        "guardians": guardians,
        "dao": dao}

    return testEnvironment


@sp.add_test(name="Test text proposal")
def test_text_proposal():
    # Get the test environment
    testEnvironment = get_test_environment()
    scenario = testEnvironment["scenario"]
    admin = testEnvironment["admin"]
    user1 = testEnvironment["user1"]
    user2 = testEnvironment["user2"]
    user3 = testEnvironment["user3"]
    user4 = testEnvironment["user4"]
    user5 = testEnvironment["user5"]
    user6 = testEnvironment["user6"]
    external_user = testEnvironment["external_user"]
    token = testEnvironment["token"]
    treasury = testEnvironment["treasury"]
    representatives = testEnvironment["representatives"]
    guardians = testEnvironment["guardians"]
    dao = testEnvironment["dao"]

    # Check that the initial contract storage information is correct
    scenario.verify(dao.data.metadata[""] == sp.utils.bytes_of_string("ipfs://fff"))
    scenario.verify(dao.data.administrator == admin.address)
    scenario.verify(dao.data.treasury == treasury.address)
    scenario.verify(dao.data.token == token.address)
    scenario.verify(dao.data.representatives == representatives.address)
    scenario.verify(dao.data.guardians == guardians.address)
    scenario.verify(dao.data.quorum == 800)
    scenario.verify(dao.data.last_quorum_update == sp.timestamp(0))
    scenario.verify(dao.data.gp_counter == 1)
    scenario.verify(dao.data.counter == 0)

    # Check that non-DAO members cannot create proposals
    proposal_title = sp.utils.bytes_of_string("Dummy title")
    proposal_description = sp.utils.bytes_of_string("Dummy description")
    proposal_kind = sp.variant("text", sp.unit)
    dao.create_proposal(
        title=proposal_title,
        description=proposal_description,
        kind=proposal_kind).run(
            valid=False, sender=external_user, now=sp.timestamp(100), exception="DAO_NOT_MEMBER")

    # Check that members with less tokens than the escrow cannot create proposals
    dao.create_proposal(
        title=proposal_title,
        description=proposal_description,
        kind=proposal_kind).run(
            valid=False, sender=user5, now=sp.timestamp(100), exception="FA2_INSUFFICIENT_BALANCE")

    # User 4 creates a proposal
    dao.create_proposal(
        title=proposal_title,
        description=proposal_description,
        kind=proposal_kind).run(
            sender=user4, level=10, now=sp.timestamp(100))

    # Check that the contract information has been updated
    scenario.verify(dao.data.proposals[0].title == proposal_title)
    scenario.verify(dao.data.proposals[0].description == proposal_description)
    scenario.verify(dao.data.proposals[0].kind.is_variant("text"))
    scenario.verify(dao.data.proposals[0].issuer == user4.address)
    scenario.verify(dao.data.proposals[0].timestamp == sp.timestamp(100))
    scenario.verify(dao.data.proposals[0].level == 10)
    scenario.verify(dao.data.proposals[0].quorum == dao.data.quorum)
    scenario.verify(dao.data.proposals[0].gp_index == 0)
    scenario.verify(dao.data.proposals[0].status.is_variant("open"))
    scenario.verify(dao.data.counter == 1)

    # Check that the tokens in escrow have been transferred
    scenario.verify(token.data.ledger[user4.address] == 400 - 10)
    scenario.verify(token.data.ledger[dao.address] == 10)

    # Check that it's not possible to vote an innexisting proposal
    dao.representatives_vote(proposal_id=1, vote=sp.variant("abstain", sp.unit)).run(
        valid=False, sender=user1, now=sp.timestamp(200), level=20, exception="DAO_INEXISTENT_PROPOSAL")
    dao.token_vote(proposal_id=1, vote=sp.variant("abstain", sp.unit), max_checkpoints=sp.none).run(
        valid=False, sender=user1, now=sp.timestamp(200), level=20, exception="DAO_INEXISTENT_PROPOSAL")

    # Check that it's not possible to vote without tokens
    dao.token_vote(proposal_id=0, vote=sp.variant("abstain", sp.unit), max_checkpoints=sp.none).run(
        valid=False, sender=external_user, now=sp.timestamp(200), level=20, exception="DAO_INSUFICIENT_BALANCE")

    # User 1 votes as representative
    dao.representatives_vote(proposal_id=0, vote=sp.variant("abstain", sp.unit)).run(
        sender=user1, now=sp.timestamp(200), level=20)

    # Check that the contract information has been updated
    scenario.verify(dao.data.proposals[0].representatives_votes.total == 1)
    scenario.verify(dao.data.proposals[0].representatives_votes.positive == 0)
    scenario.verify(dao.data.proposals[0].representatives_votes.negative == 0)
    scenario.verify(dao.data.proposals[0].representatives_votes.abstain == 1)
    scenario.verify(dao.data.proposals[0].representatives_votes.participation == 1)
    scenario.verify(dao.data.representatives_votes[(0, "community1")].is_variant("abstain"))

    # Check that it's not possible to vote twice
    dao.representatives_vote(proposal_id=0, vote=sp.variant("yes", sp.unit)).run(
        valid=False, sender=user1, now=sp.timestamp(250), level=25, exception="DAO_ALREADY_VOTED")

    # Check that the representative can also vote with their tokens
    dao.token_vote(proposal_id=0, vote=sp.variant("yes", sp.unit), max_checkpoints=sp.none).run(
        sender=user1, now=sp.timestamp(250), level=25)

    # User 2 votes as representative
    dao.representatives_vote(proposal_id=0, vote=sp.variant("yes", sp.unit)).run(
        sender=user2, now=sp.timestamp(300), level=30)

    # Check that non representatives cannot vote as representatives
    dao.representatives_vote(proposal_id=0, vote=sp.variant("yes", sp.unit)).run(
        valid=False, sender=user4, now=sp.timestamp(400), level=40, exception="REPS_NOT_REPRESENTATIVE")

    # User 3, 4 and 5 vote as normal users
    dao.token_vote(proposal_id=0, vote=sp.variant("yes", sp.unit), max_checkpoints=sp.none).run(
        sender=user3, now=sp.timestamp(400), level=40)
    dao.token_vote(proposal_id=0, vote=sp.variant("yes", sp.unit), max_checkpoints=sp.none).run(
        sender=user4, now=sp.timestamp(400), level=40)
    dao.token_vote(proposal_id=0, vote=sp.variant("no", sp.unit), max_checkpoints=sp.none).run(
        sender=user5, now=sp.timestamp(400), level=40)

    # Check that the contract information has been updated
    scenario.verify(dao.data.proposals[0].representatives_votes.total == 2)
    scenario.verify(dao.data.proposals[0].representatives_votes.positive == 1)
    scenario.verify(dao.data.proposals[0].representatives_votes.negative == 0)
    scenario.verify(dao.data.proposals[0].representatives_votes.abstain == 1)
    scenario.verify(dao.data.proposals[0].representatives_votes.participation == 2)
    scenario.verify(dao.data.proposals[0].token_votes.total == 100 + 300 + 400 + 5)
    scenario.verify(dao.data.proposals[0].token_votes.positive == 100 + 300 + 400)
    scenario.verify(dao.data.proposals[0].token_votes.negative == 5)
    scenario.verify(dao.data.proposals[0].token_votes.abstain == 0)
    scenario.verify(dao.data.proposals[0].token_votes.participation == 4)
    scenario.verify(dao.data.representatives_votes[(0, "community1")].is_variant("abstain"))
    scenario.verify(dao.data.representatives_votes[(0, "community2")].is_variant("yes"))
    scenario.verify(dao.data.token_votes[(0, user1.address)].vote.is_variant("yes"))
    scenario.verify(dao.data.token_votes[(0, user1.address)].weight == 100)
    scenario.verify(dao.data.token_votes[(0, user3.address)].vote.is_variant("yes"))
    scenario.verify(dao.data.token_votes[(0, user3.address)].weight == 300)
    scenario.verify(dao.data.token_votes[(0, user4.address)].vote.is_variant("yes"))
    scenario.verify(dao.data.token_votes[(0, user4.address)].weight == 400)
    scenario.verify(dao.data.token_votes[(0, user5.address)].vote.is_variant("no"))
    scenario.verify(dao.data.token_votes[(0, user5.address)].weight == 5)

    # Check that it's not possible to evaluate the proposal results before is closed
    dao.evaluate_voting_result(0).run(
        valid=False, sender=user1, now=sp.timestamp(500), level=50, exception="DAO_OPEN_PROPOSAL")

    # Check that only DAO members can evaluate the proposal results
    dao.evaluate_voting_result(0).run(
        valid=False, sender=external_user, now=sp.timestamp(101).add_days(5), level=60, exception="DAO_NOT_MEMBER")

    # Check that it's not possible to vote when the proposal is closed
    dao.representatives_vote(proposal_id=0, vote=sp.variant("yes", sp.unit)).run(
        valid=False, sender=user6, now=sp.timestamp(101).add_days(5), level=50, exception="DAO_CLOSED_PROPOSAL")
    dao.token_vote(proposal_id=0, vote=sp.variant("yes", sp.unit), max_checkpoints=sp.none).run(
        valid=False, sender=user6, now=sp.timestamp(101).add_days(5), level=50, exception="DAO_CLOSED_PROPOSAL")

    # Check that it's not possible to evaluate an innexisting proposal
    dao.evaluate_voting_result(1).run(
        valid=False, sender=user1, now=sp.timestamp(101).add_days(5), level=60, exception="DAO_INEXISTENT_PROPOSAL")

    # Check that it's not possible to execute a proposal that is not yet approved
    dao.execute_proposal(0).run(
        valid=False, sender=user1, exception="DAO_STATUS_NOT_APPROVED")

    # Check that it's not possible to execute an innexisting proposal
    dao.execute_proposal(1).run(
        valid=False, sender=user1, exception="DAO_INEXISTENT_PROPOSAL")

    # Evaluate the proposal results
    dao.evaluate_voting_result(0).run(
        sender=user1, now=sp.timestamp(101).add_days(5), level=60)

    # Check that the contract information has been updated
    scenario.verify(dao.data.proposals[0].status.is_variant("approved"))
    scenario.verify(dao.data.quorum == int(800 * 0.8 + (100 + 300 + 400 + 5 + 800 * 0.3) * 0.2))
    scenario.verify(dao.data.last_quorum_update == sp.timestamp(101).add_days(5))

    # Check that the tokens in escrow have been transferred back to user 4
    scenario.verify(token.data.ledger[user4.address] == 400)
    scenario.verify(token.data.ledger[dao.address] == 0)

    # Check that it's not possible to execute a proposal before the wating time
    # has passed
    dao.execute_proposal(0).run(
        valid=False, sender=user1, now=sp.timestamp(101).add_days(5 + 1), exception="DAO_WAITING_PROPOSAL")

    # Check that only DAO members can execute the proposal
    dao.execute_proposal(0).run(
        valid=False, sender=external_user, now=sp.timestamp(101).add_days(5 + 2), exception="DAO_NOT_MEMBER")

    # Execute the proposal
    dao.execute_proposal(0).run(sender=user1, now=sp.timestamp(101).add_days(5 + 2))

    # Check that the contract information has been updated
    scenario.verify(dao.data.proposals[0].status.is_variant("executed"))

    # Check that it's not possible to execute twice the proposal
    dao.execute_proposal(0).run(
        valid=False, sender=user1, now=sp.timestamp(101).add_days(5 + 2), exception="DAO_STATUS_NOT_APPROVED")


@sp.add_test(name="Test transfer mutez proposal")
def test_transfer_mutez_proposal():
    # Get the test environment
    testEnvironment = get_test_environment()
    scenario = testEnvironment["scenario"]
    user1 = testEnvironment["user1"]
    user2 = testEnvironment["user2"]
    user3 = testEnvironment["user3"]
    user4 = testEnvironment["user4"]
    user5 = testEnvironment["user5"]
    token = testEnvironment["token"]
    treasury = testEnvironment["treasury"]
    dao = testEnvironment["dao"]

    # Create the recipient contracts and add them to the test scenario
    recipient1 = Recipient()
    recipient2 = Recipient()
    scenario += recipient1
    scenario += recipient2

    # User 4 creates a proposal
    proposal_title = sp.utils.bytes_of_string("Dummy title")
    proposal_description = sp.utils.bytes_of_string("Dummy description")
    mutez_transfers = [
        sp.record(amount=sp.tez(1), destination=recipient1.address),
        sp.record(amount=sp.tez(2), destination=recipient2.address)]
    proposal_kind = sp.variant("transfer_mutez", mutez_transfers)
    dao.create_proposal(
        title=proposal_title,
        description=proposal_description,
        kind=proposal_kind).run(
            sender=user4, level=10, now=sp.timestamp(100))

    # Check that the contract information has been updated
    scenario.verify(dao.data.proposals[0].title == proposal_title)
    scenario.verify(dao.data.proposals[0].description == proposal_description)
    scenario.verify(dao.data.proposals[0].kind.is_variant("transfer_mutez"))
    scenario.verify(dao.data.proposals[0].issuer == user4.address)
    scenario.verify(dao.data.proposals[0].timestamp == sp.timestamp(100))
    scenario.verify(dao.data.proposals[0].level == 10)
    scenario.verify(dao.data.proposals[0].quorum == dao.data.quorum)
    scenario.verify(dao.data.proposals[0].gp_index == 0)
    scenario.verify(dao.data.proposals[0].status.is_variant("open"))
    scenario.verify(dao.data.gp_counter == 1)
    scenario.verify(dao.data.counter == 1)

    # Check that the tokens in escrow have been transferred
    scenario.verify(token.data.ledger[user4.address] == 400 - 10)
    scenario.verify(token.data.ledger[dao.address] == 10)

    # Users 1 and 2 vote as representatives
    dao.representatives_vote(proposal_id=0, vote=sp.variant("abstain", sp.unit)).run(
        sender=user1, now=sp.timestamp(200), level=20)
    dao.representatives_vote(proposal_id=0, vote=sp.variant("yes", sp.unit)).run(
        sender=user2, now=sp.timestamp(300), level=30)

    # User 3, 4 and 5 vote as normal users
    dao.token_vote(proposal_id=0, vote=sp.variant("yes", sp.unit), max_checkpoints=sp.none).run(
        sender=user3, now=sp.timestamp(400), level=40)
    dao.token_vote(proposal_id=0, vote=sp.variant("yes", sp.unit), max_checkpoints=sp.none).run(
        sender=user4, now=sp.timestamp(400), level=40)
    dao.token_vote(proposal_id=0, vote=sp.variant("no", sp.unit), max_checkpoints=sp.none).run(
        sender=user5, now=sp.timestamp(400), level=40)

    # Evaluate the proposal results
    dao.evaluate_voting_result(0).run(
        sender=user1, now=sp.timestamp(101).add_days(5), level=60)

    # Check that the contract information has been updated
    scenario.verify(dao.data.proposals[0].status.is_variant("approved"))

    # Check that the tokens in escrow have been transferred back to user 4
    scenario.verify(token.data.ledger[user4.address] == 400)
    scenario.verify(token.data.ledger[dao.address] == 0)

    # Execute the proposal
    dao.execute_proposal(0).run(sender=user1, now=sp.timestamp(101).add_days(5 + 2))

    # Check that the contract information has been updated
    scenario.verify(dao.data.proposals[0].status.is_variant("executed"))

    # Check that the tez have been transferred
    scenario.verify(treasury.balance == sp.tez(10) - sp.tez(1) - sp.tez(2))
    scenario.verify(recipient1.balance == sp.tez(1))
    scenario.verify(recipient2.balance == sp.tez(2))


@sp.add_test(name="Test transfer token proposal")
def test_transfer_token_proposal():
    # Get the test environment
    testEnvironment = get_test_environment()
    scenario = testEnvironment["scenario"]
    user1 = testEnvironment["user1"]
    user2 = testEnvironment["user2"]
    user3 = testEnvironment["user3"]
    user4 = testEnvironment["user4"]
    user5 = testEnvironment["user5"]
    external_user = testEnvironment["external_user"]
    token = testEnvironment["token"]
    treasury = testEnvironment["treasury"]
    dao = testEnvironment["dao"]

    # User 4 creates a proposal
    proposal_title = sp.utils.bytes_of_string("Dummy title")
    proposal_description = sp.utils.bytes_of_string("Dummy description")
    token_transfers = sp.set_type_expr(
        sp.record(
            fa2=token.address,
            token_id=sp.nat(0),
            distribution=[
                sp.record(amount=sp.nat(10), destination=user1.address),
                sp.record(amount=sp.nat(20), destination=external_user.address)]),
        t=daoGovernanceModule.DAOGovernance.TOKEN_TRANSFERS_TYPE)
    proposal_kind = sp.variant("transfer_token", token_transfers)
    dao.create_proposal(
        title=proposal_title,
        description=proposal_description,
        kind=proposal_kind).run(
            sender=user4, level=10, now=sp.timestamp(100))

    # Check that the contract information has been updated
    scenario.verify(dao.data.proposals[0].title == proposal_title)
    scenario.verify(dao.data.proposals[0].description == proposal_description)
    scenario.verify(dao.data.proposals[0].kind.is_variant("transfer_token"))
    scenario.verify(dao.data.proposals[0].issuer == user4.address)
    scenario.verify(dao.data.proposals[0].timestamp == sp.timestamp(100))
    scenario.verify(dao.data.proposals[0].level == 10)
    scenario.verify(dao.data.proposals[0].quorum == dao.data.quorum)
    scenario.verify(dao.data.proposals[0].gp_index == 0)
    scenario.verify(dao.data.proposals[0].status.is_variant("open"))
    scenario.verify(dao.data.gp_counter == 1)
    scenario.verify(dao.data.counter == 1)

    # Check that the tokens in escrow have been transferred
    scenario.verify(token.data.ledger[user4.address] == 400 - 10)
    scenario.verify(token.data.ledger[dao.address] == 10)

    # Users 1 and 2 vote as representatives
    dao.representatives_vote(proposal_id=0, vote=sp.variant("abstain", sp.unit)).run(
        sender=user1, now=sp.timestamp(200), level=20)
    dao.representatives_vote(proposal_id=0, vote=sp.variant("yes", sp.unit)).run(
        sender=user2, now=sp.timestamp(300), level=30)

    # User 3, 4 and 5 vote as normal users
    dao.token_vote(proposal_id=0, vote=sp.variant("yes", sp.unit), max_checkpoints=sp.none).run(
        sender=user3, now=sp.timestamp(400), level=40)
    dao.token_vote(proposal_id=0, vote=sp.variant("yes", sp.unit), max_checkpoints=sp.none).run(
        sender=user4, now=sp.timestamp(400), level=40)
    dao.token_vote(proposal_id=0, vote=sp.variant("no", sp.unit), max_checkpoints=sp.none).run(
        sender=user5, now=sp.timestamp(400), level=40)

    # Evaluate the proposal results
    dao.evaluate_voting_result(0).run(
        sender=user1, now=sp.timestamp(101).add_days(5), level=60)

    # Check that the contract information has been updated
    scenario.verify(dao.data.proposals[0].status.is_variant("approved"))

    # Check that the tokens in escrow have been transferred back to user 4
    scenario.verify(token.data.ledger[user4.address] == 400)
    scenario.verify(token.data.ledger[dao.address] == 0)

    # Execute the proposal
    dao.execute_proposal(0).run(sender=user1, now=sp.timestamp(101).add_days(5 + 2))

    # Check that the contract information has been updated
    scenario.verify(dao.data.proposals[0].status.is_variant("executed"))

    # Check that the tokens have been transferred
    scenario.verify(token.data.ledger[treasury.address] == 990 - 10 - 20)
    scenario.verify(token.data.ledger[user1.address] == 100 + 10)
    scenario.verify(token.data.ledger[external_user.address] == 20)


@sp.add_test(name="Test lambda function proposal")
def test_lambda_function_proposal():
    # Get the test environment
    testEnvironment = get_test_environment()
    scenario = testEnvironment["scenario"]
    user1 = testEnvironment["user1"]
    user2 = testEnvironment["user2"]
    user3 = testEnvironment["user3"]
    user4 = testEnvironment["user4"]
    user5 = testEnvironment["user5"]
    token = testEnvironment["token"]
    dao = testEnvironment["dao"]

    # Create a new treasury account
    new_treasury = sp.test_account("new_treasury")

    # Define the lambda function that will set the new treasury address
    def treasury_lambda_function(params):
        sp.set_type(params, sp.TUnit)
        set_treasury_handle = sp.contract(
            sp.TAddress, dao.address, "set_treasury").open_some()
        sp.result([sp.transfer_operation(
            new_treasury.address, sp.mutez(0), set_treasury_handle)])

    # User 4 creates a proposal
    proposal_title = sp.utils.bytes_of_string("Dummy title")
    proposal_description = sp.utils.bytes_of_string("Dummy description")
    proposal_kind = sp.variant("lambda_function", treasury_lambda_function)
    dao.create_proposal(
        title=proposal_title,
        description=proposal_description,
        kind=proposal_kind).run(
            sender=user4, level=10, now=sp.timestamp(100))

    # Check that the contract information has been updated
    scenario.verify(dao.data.proposals[0].title == proposal_title)
    scenario.verify(dao.data.proposals[0].description == proposal_description)
    scenario.verify(dao.data.proposals[0].kind.is_variant("lambda_function"))
    scenario.verify(dao.data.proposals[0].issuer == user4.address)
    scenario.verify(dao.data.proposals[0].timestamp == sp.timestamp(100))
    scenario.verify(dao.data.proposals[0].level == 10)
    scenario.verify(dao.data.proposals[0].quorum == dao.data.quorum)
    scenario.verify(dao.data.proposals[0].gp_index == 0)
    scenario.verify(dao.data.proposals[0].status.is_variant("open"))
    scenario.verify(dao.data.gp_counter == 1)
    scenario.verify(dao.data.counter == 1)

    # Check that the tokens in escrow have been transferred
    scenario.verify(token.data.ledger[user4.address] == 400 - 10)
    scenario.verify(token.data.ledger[dao.address] == 10)

    # Users 1 and 2 vote as representatives
    dao.representatives_vote(proposal_id=0, vote=sp.variant("abstain", sp.unit)).run(
        sender=user1, now=sp.timestamp(200), level=20)
    dao.representatives_vote(proposal_id=0, vote=sp.variant("yes", sp.unit)).run(
        sender=user2, now=sp.timestamp(300), level=30)

    # User 3, 4 and 5 vote as normal users
    dao.token_vote(proposal_id=0, vote=sp.variant("yes", sp.unit), max_checkpoints=sp.none).run(
        sender=user3, now=sp.timestamp(400), level=40)
    dao.token_vote(proposal_id=0, vote=sp.variant("yes", sp.unit), max_checkpoints=sp.none).run(
        sender=user4, now=sp.timestamp(400), level=40)
    dao.token_vote(proposal_id=0, vote=sp.variant("no", sp.unit), max_checkpoints=sp.none).run(
        sender=user5, now=sp.timestamp(400), level=40)

    # Evaluate the proposal results
    dao.evaluate_voting_result(0).run(
        sender=user1, now=sp.timestamp(101).add_days(5), level=60)

    # Check that the contract information has been updated
    scenario.verify(dao.data.proposals[0].status.is_variant("approved"))

    # Check that the tokens in escrow have been transferred back to user 4
    scenario.verify(token.data.ledger[user4.address] == 400)
    scenario.verify(token.data.ledger[dao.address] == 0)

    # Execute the proposal
    dao.execute_proposal(0).run(sender=user1, now=sp.timestamp(101).add_days(5 + 2))

    # Check that the contract information has been updated
    scenario.verify(dao.data.proposals[0].status.is_variant("executed"))

    # Check that the treasury address has been updated
    scenario.verify(dao.data.treasury == new_treasury.address)

    # Define the lambda function that will update DAO governance parameters
    def governance_parameters_lambda_function(params):
        sp.set_type(params, sp.TUnit)
        set_governance_parameters_handle = sp.contract(
            daoGovernanceModule.DAOGovernance.GOVERNANCE_PARAMETERS_TYPE,
            dao.address, "set_governance_parameters").open_some()
        sp.result([sp.transfer_operation(
            sp.record(
                vote_method=sp.variant("linear", sp.unit),
                vote_period=5,
                wait_period=2,
                escrow_amount=20,
                escrow_return=30,
                min_amount=6,
                supermajority=60,
                representatives_share=30,
                quorum_update_period=3,
                quorum_update=20,
                quorum_max_change=20,
                min_quorum=100,
                max_quorum=1300),
            sp.mutez(0),
            set_governance_parameters_handle)])

    # User 1 creates a proposal
    proposal_title = sp.utils.bytes_of_string("Dummy title 2")
    proposal_description = sp.utils.bytes_of_string("Dummy description 2")
    proposal_kind = sp.variant("lambda_function", governance_parameters_lambda_function)
    dao.create_proposal(
        title=proposal_title,
        description=proposal_description,
        kind=proposal_kind).run(
            sender=user1, level=50, now=sp.timestamp(500))

    # Check that the contract information has been updated
    scenario.verify(dao.data.proposals[1].title == proposal_title)
    scenario.verify(dao.data.proposals[1].description == proposal_description)
    scenario.verify(dao.data.proposals[1].kind.is_variant("lambda_function"))
    scenario.verify(dao.data.proposals[1].issuer == user1.address)
    scenario.verify(dao.data.proposals[1].timestamp == sp.timestamp(500))
    scenario.verify(dao.data.proposals[1].level == 50)
    scenario.verify(dao.data.proposals[1].quorum == dao.data.quorum)
    scenario.verify(dao.data.proposals[1].gp_index == 0)
    scenario.verify(dao.data.proposals[1].status.is_variant("open"))
    scenario.verify(dao.data.gp_counter == 1)
    scenario.verify(dao.data.counter == 2)

    # Check that the tokens in escrow have been transferred
    scenario.verify(token.data.ledger[user1.address] == 100 - 10)
    scenario.verify(token.data.ledger[dao.address] == 10)

    # Users 1 and 2 vote as representatives
    dao.representatives_vote(proposal_id=1, vote=sp.variant("abstain", sp.unit)).run(
        sender=user1, now=sp.timestamp(600), level=60)
    dao.representatives_vote(proposal_id=1, vote=sp.variant("yes", sp.unit)).run(
        sender=user2, now=sp.timestamp(700), level=70)

    # User 3, 4 and 5 vote as normal users
    dao.token_vote(proposal_id=1, vote=sp.variant("yes", sp.unit), max_checkpoints=sp.none).run(
        sender=user3, now=sp.timestamp(800), level=80)
    dao.token_vote(proposal_id=1, vote=sp.variant("yes", sp.unit), max_checkpoints=sp.none).run(
        sender=user4, now=sp.timestamp(900), level=90)
    dao.token_vote(proposal_id=1, vote=sp.variant("no", sp.unit), max_checkpoints=sp.none).run(
        sender=user5, now=sp.timestamp(1000), level=100)

    # Evaluate the proposal results
    dao.evaluate_voting_result(1).run(
        sender=user1, now=sp.timestamp(501).add_days(5), level=110)

    # Check that the contract information has been updated
    scenario.verify(dao.data.proposals[1].status.is_variant("approved"))

    # Check that the tokens in escrow have been transferred back to user 4
    scenario.verify(token.data.ledger[user1.address] == 100)
    scenario.verify(token.data.ledger[dao.address] == 0)

    # Execute the proposal
    dao.execute_proposal(1).run(sender=user1, now=sp.timestamp(501).add_days(5 + 2))

    # Check that the contract information has been updated
    scenario.verify(dao.data.proposals[1].status.is_variant("executed"))

    # Check that the DAO governance parameters has been updated
    scenario.verify(dao.data.governance_parameters[1].escrow_amount == 20)
    scenario.verify(dao.data.governance_parameters[1].min_amount == 6)

    # Create a new representatives account
    new_representatives = sp.test_account("new_representatives")

    # Define the lambda function that will set the new representatives address
    def representatives_lambda_function(params):
        sp.set_type(params, sp.TUnit)
        set_representatives_handle = sp.contract(
            sp.TAddress, dao.address, "set_representatives").open_some()
        sp.result([sp.transfer_operation(
            new_representatives.address, sp.mutez(0), set_representatives_handle)])

    # User 2 creates a proposal
    proposal_title = sp.utils.bytes_of_string("Dummy title 3")
    proposal_description = sp.utils.bytes_of_string("Dummy description 3")
    proposal_kind = sp.variant("lambda_function", representatives_lambda_function)
    dao.create_proposal(
        title=proposal_title,
        description=proposal_description,
        kind=proposal_kind).run(
            sender=user2, level=100, now=sp.timestamp(1000))

    # Check that the contract information has been updated
    scenario.verify(dao.data.proposals[2].title == proposal_title)
    scenario.verify(dao.data.proposals[2].description == proposal_description)
    scenario.verify(dao.data.proposals[2].kind.is_variant("lambda_function"))
    scenario.verify(dao.data.proposals[2].issuer == user2.address)
    scenario.verify(dao.data.proposals[2].timestamp == sp.timestamp(1000))
    scenario.verify(dao.data.proposals[2].level == 100)
    scenario.verify(dao.data.proposals[2].quorum == dao.data.quorum)
    scenario.verify(dao.data.proposals[2].gp_index == 1)
    scenario.verify(dao.data.proposals[2].status.is_variant("open"))
    scenario.verify(dao.data.gp_counter == 2)
    scenario.verify(dao.data.counter == 3)

    # Check that the tokens in escrow have been transferred
    scenario.verify(token.data.ledger[user2.address] == 200 - 20)
    scenario.verify(token.data.ledger[dao.address] == 20)

    # Users 1 and 2 vote as representatives
    dao.representatives_vote(proposal_id=2, vote=sp.variant("abstain", sp.unit)).run(
        sender=user1, now=sp.timestamp(1600), level=160)
    dao.representatives_vote(proposal_id=2, vote=sp.variant("yes", sp.unit)).run(
        sender=user2, now=sp.timestamp(1700), level=170)

    # User 3, 4 and 5 vote as normal users
    dao.token_vote(proposal_id=2, vote=sp.variant("yes", sp.unit), max_checkpoints=sp.none).run(
        sender=user3, now=sp.timestamp(1800), level=180)
    dao.token_vote(proposal_id=2, vote=sp.variant("yes", sp.unit), max_checkpoints=sp.none).run(
        sender=user4, now=sp.timestamp(1900), level=190)
    dao.token_vote(proposal_id=2, vote=sp.variant("no", sp.unit), max_checkpoints=sp.none).run(
        valid=False, sender=user5, now=sp.timestamp(2000), level=200)

    # Evaluate the proposal results
    dao.evaluate_voting_result(2).run(
        sender=user1, now=sp.timestamp(1001).add_days(5), level=210)

    # Check that the contract information has been updated
    scenario.verify(dao.data.proposals[2].status.is_variant("approved"))

    # Check that the tokens in escrow have been transferred back to user 4
    scenario.verify(token.data.ledger[user2.address] == 200)
    scenario.verify(token.data.ledger[dao.address] == 0)

    # Execute the proposal
    dao.execute_proposal(2).run(sender=user1, now=sp.timestamp(1001).add_days(5 + 2))

    # Check that the contract information has been updated
    scenario.verify(dao.data.proposals[2].status.is_variant("executed"))

    # Check that the representatives address has been updated
    scenario.verify(dao.data.representatives == new_representatives.address)


@sp.add_test(name="Test cancel proposal")
def test_cancel_proposal():
    # Get the test environment
    testEnvironment = get_test_environment()
    scenario = testEnvironment["scenario"]
    user1 = testEnvironment["user1"]
    user2 = testEnvironment["user2"]
    user3 = testEnvironment["user3"]
    user4 = testEnvironment["user4"]
    user5 = testEnvironment["user5"]
    external_user = testEnvironment["external_user"]
    token = testEnvironment["token"]
    treasury = testEnvironment["treasury"]
    guardians = testEnvironment["guardians"]
    dao = testEnvironment["dao"]

    # User 4 creates a proposal
    proposal_title = sp.utils.bytes_of_string("Dummy title")
    proposal_description = sp.utils.bytes_of_string("Dummy description")
    token_transfers = sp.set_type_expr(
        sp.record(
            fa2=token.address,
            token_id=sp.nat(0),
            distribution=[
                sp.record(amount=sp.nat(10), destination=user1.address),
                sp.record(amount=sp.nat(20), destination=external_user.address)]),
        t=daoGovernanceModule.DAOGovernance.TOKEN_TRANSFERS_TYPE)
    proposal_kind = sp.variant("transfer_token", token_transfers)
    dao.create_proposal(
        title=proposal_title,
        description=proposal_description,
        kind=proposal_kind).run(
            sender=user4, level=10, now=sp.timestamp(100))

    # Check that the tokens in escrow have been transferred
    scenario.verify(token.data.ledger[user4.address] == 400 - 10)
    scenario.verify(token.data.ledger[dao.address] == 10)

    # User 3, 4 and 5 vote as normal users
    dao.token_vote(proposal_id=0, vote=sp.variant("no", sp.unit), max_checkpoints=sp.none).run(
        sender=user3, now=sp.timestamp(400), level=40)
    dao.token_vote(proposal_id=0, vote=sp.variant("no", sp.unit), max_checkpoints=sp.none).run(
        sender=user4, now=sp.timestamp(400), level=40)
    dao.token_vote(proposal_id=0, vote=sp.variant("yes", sp.unit), max_checkpoints=sp.none).run(
        sender=user5, now=sp.timestamp(400), level=40)

    # Check that it's not possible to cancel an innexisting proposal
    dao.cancel_proposal(proposal_id=1, return_escrow=True).run(
        valid=False, sender=user4, now=sp.timestamp(500), level=50, exception="DAO_INEXISTENT_PROPOSAL")

    # Check that only the proposal issuer can cancel the proposal
    dao.cancel_proposal(proposal_id=0, return_escrow=True).run(
        valid=False, sender=user1, now=sp.timestamp(500), level=50, exception="DAO_NOT_ISSUER_NOR_GUARDIAN")

    # Cancel the proposal
    dao.cancel_proposal(proposal_id=0, return_escrow=True).run(
        sender=user4, now=sp.timestamp(500), level=50)

    # Check that the contract information has been updated
    scenario.verify(dao.data.proposals[0].status.is_variant("cancelled"))

    # Check that the tokens in escrow have been transferred to the treasury
    scenario.verify(token.data.ledger[user4.address] == 400 - 10)
    scenario.verify(token.data.ledger[dao.address] == 0)
    scenario.verify(token.data.ledger[treasury.address] == 990 + 10)

    # Check that it's not possible to cancel, evaluate or execute the proposal
    dao.cancel_proposal(proposal_id=0, return_escrow=True).run(
        valid=False, sender=user4, now=sp.timestamp(600), level=60, exception="DAO_STATUS_NOT_OPEN_OR_APPROVED")
    dao.evaluate_voting_result(0).run(
        valid=False, sender=user1, now=sp.timestamp(101).add_days(5), level=60, exception="DAO_STATUS_NOT_OPEN")
    dao.execute_proposal(0).run(
        valid=False, sender=user1, now=sp.timestamp(101).add_days(5 + 2), exception="DAO_STATUS_NOT_APPROVED")

    # User 1 creates 3 proposals
    proposal_title = sp.utils.bytes_of_string("Dummy title")
    proposal_description = sp.utils.bytes_of_string("Dummy description")
    proposal_kind = sp.variant("text", sp.unit)
    dao.create_proposal(
        title=proposal_title,
        description=proposal_description,
        kind=proposal_kind).run(sender=user1, level=70)
    dao.create_proposal(
        title=proposal_title,
        description=proposal_description,
        kind=proposal_kind).run(sender=user1, level=70)
    dao.create_proposal(
        title=proposal_title,
        description=proposal_description,
        kind=proposal_kind).run(sender=user1, level=70)

    # Check that the tokens in escrow have been transferred
    scenario.verify(token.data.ledger[user1.address] == 100 - 30)
    scenario.verify(token.data.ledger[dao.address] == 30)

    # The users vote the first new proposal
    dao.token_vote(proposal_id=1, vote=sp.variant("yes", sp.unit), max_checkpoints=sp.none).run(
        sender=user3, now=sp.timestamp(800), level=80)
    dao.token_vote(proposal_id=1, vote=sp.variant("yes", sp.unit), max_checkpoints=sp.none).run(
        sender=user4, now=sp.timestamp(800), level=80)
    dao.token_vote(proposal_id=1, vote=sp.variant("yes", sp.unit), max_checkpoints=sp.none).run(
        sender=user5, now=sp.timestamp(800), level=80)

    # Define the lambda function that will cancel all the proposals
    def guardians_lambda_function(params):
        sp.set_type(params, sp.TUnit)
        cancel_proposal_handle = sp.contract(
            sp.TRecord(proposal_id=sp.TNat, return_escrow=sp.TBool).layout(
                ("proposal_id", "return_escrow")),
            dao.address,
            "cancel_proposal").open_some()
        sp.result([
            sp.transfer_operation(sp.record(proposal_id=1, return_escrow=False), sp.mutez(0), cancel_proposal_handle),
            sp.transfer_operation(sp.record(proposal_id=2, return_escrow=False), sp.mutez(0), cancel_proposal_handle),
            sp.transfer_operation(sp.record(proposal_id=3, return_escrow=False), sp.mutez(0), cancel_proposal_handle)])

    # Add a lambda proposal
    guardians.lambda_function_proposal(guardians_lambda_function).run(sender=user4)

    # Vote for the proposal
    guardians.vote_proposal(proposal_id=0, approval=True).run(sender=user4)
    guardians.vote_proposal(proposal_id=0, approval=True).run(sender=user5)

    # Execute the proposal
    guardians.execute_proposal(0).run(sender=user4, now=sp.timestamp(900), level=90)

    # Check that the contract information has been updated
    scenario.verify(dao.data.proposals[1].status.is_variant("cancelled"))
    scenario.verify(dao.data.proposals[2].status.is_variant("cancelled"))
    scenario.verify(dao.data.proposals[3].status.is_variant("cancelled"))

    # Check that the tokens in escrow have been transferred to the treasury
    scenario.verify(token.data.ledger[user1.address] == 100 - 30)
    scenario.verify(token.data.ledger[dao.address] == 0)
    scenario.verify(token.data.ledger[treasury.address] == 990 + 10 + 30)


@sp.add_test(name="Test supermajority failed proposal")
def test_supermajority_failed_proposal():
    # Get the test environment
    testEnvironment = get_test_environment()
    scenario = testEnvironment["scenario"]
    user1 = testEnvironment["user1"]
    user2 = testEnvironment["user2"]
    user3 = testEnvironment["user3"]
    user4 = testEnvironment["user4"]
    user5 = testEnvironment["user5"]
    external_user = testEnvironment["external_user"]
    token = testEnvironment["token"]
    treasury = testEnvironment["treasury"]
    dao = testEnvironment["dao"]

    # User 4 creates a proposal
    proposal_title = sp.utils.bytes_of_string("Dummy title")
    proposal_description = sp.utils.bytes_of_string("Dummy description")
    token_transfers = sp.set_type_expr(
        sp.record(
            fa2=token.address,
            token_id=sp.nat(0),
            distribution=[
                sp.record(amount=sp.nat(10), destination=user1.address),
                sp.record(amount=sp.nat(20), destination=external_user.address)]),
        t=daoGovernanceModule.DAOGovernance.TOKEN_TRANSFERS_TYPE)
    proposal_kind = sp.variant("transfer_token", token_transfers)
    dao.create_proposal(
        title=proposal_title,
        description=proposal_description,
        kind=proposal_kind).run(
            sender=user4, level=10, now=sp.timestamp(100))

    # Check that the tokens in escrow have been transferred
    scenario.verify(token.data.ledger[user4.address] == 400 - 10)
    scenario.verify(token.data.ledger[dao.address] == 10)

    # Users 1 and 2 vote as representatives
    dao.representatives_vote(proposal_id=0, vote=sp.variant("no", sp.unit)).run(
        sender=user1, now=sp.timestamp(200), level=20)
    dao.representatives_vote(proposal_id=0, vote=sp.variant("no", sp.unit)).run(
        sender=user2, now=sp.timestamp(300), level=30)

    # User 3, 4 and 5 vote as normal users
    dao.token_vote(proposal_id=0, vote=sp.variant("yes", sp.unit), max_checkpoints=sp.none).run(
        sender=user3, now=sp.timestamp(400), level=40)
    dao.token_vote(proposal_id=0, vote=sp.variant("no", sp.unit), max_checkpoints=sp.none).run(
        sender=user4, now=sp.timestamp(400), level=40)
    dao.token_vote(proposal_id=0, vote=sp.variant("no", sp.unit), max_checkpoints=sp.none).run(
        sender=user5, now=sp.timestamp(400), level=40)

    # Evaluate the proposal results
    dao.evaluate_voting_result(0).run(
        sender=user1, now=sp.timestamp(101).add_days(5), level=60)

    # Check that the contract information has been updated
    scenario.verify(dao.data.proposals[0].status.is_variant("rejected"))

    # Check that the tokens in escrow have been transferred to the treasury
    scenario.verify(token.data.ledger[user4.address] == 400 - 10)
    scenario.verify(token.data.ledger[dao.address] == 0)
    scenario.verify(token.data.ledger[treasury.address] == 990 + 10)

    # Check that it's not possible to execute the proposal
    dao.execute_proposal(0).run(
        valid=False, sender=user1, now=sp.timestamp(101).add_days(5 + 2), exception="DAO_STATUS_NOT_APPROVED")


@sp.add_test(name="Test quorum failed proposal")
def test_quorum_failed_proposal():
    # Get the test environment
    testEnvironment = get_test_environment()
    scenario = testEnvironment["scenario"]
    user1 = testEnvironment["user1"]
    user2 = testEnvironment["user2"]
    user3 = testEnvironment["user3"]
    user4 = testEnvironment["user4"]
    user5 = testEnvironment["user5"]
    external_user = testEnvironment["external_user"]
    token = testEnvironment["token"]
    treasury = testEnvironment["treasury"]
    dao = testEnvironment["dao"]

    # User 4 creates a proposal
    proposal_title = sp.utils.bytes_of_string("Dummy title")
    proposal_description = sp.utils.bytes_of_string("Dummy description")
    token_transfers = sp.set_type_expr(
        sp.record(
            fa2=token.address,
            token_id=sp.nat(0),
            distribution=[
                sp.record(amount=sp.nat(10), destination=user1.address),
                sp.record(amount=sp.nat(20), destination=external_user.address)]),
        t=daoGovernanceModule.DAOGovernance.TOKEN_TRANSFERS_TYPE)
    proposal_kind = sp.variant("transfer_token", token_transfers)
    dao.create_proposal(
        title=proposal_title,
        description=proposal_description,
        kind=proposal_kind).run(
            sender=user4, level=10, now=sp.timestamp(100))

    # Check that the tokens in escrow have been transferred
    scenario.verify(token.data.ledger[user4.address] == 400 - 10)
    scenario.verify(token.data.ledger[dao.address] == 10)

    # Users 1 and 2 vote as representatives
    dao.representatives_vote(proposal_id=0, vote=sp.variant("yes", sp.unit)).run(
        sender=user1, now=sp.timestamp(200), level=20)
    dao.representatives_vote(proposal_id=0, vote=sp.variant("yes", sp.unit)).run(
        sender=user2, now=sp.timestamp(300), level=30)

    # User 5 votes as normal user
    dao.token_vote(proposal_id=0, vote=sp.variant("yes", sp.unit), max_checkpoints=sp.none).run(
        sender=user5, now=sp.timestamp(400), level=40)

    # Evaluate the proposal results
    dao.evaluate_voting_result(0).run(
        sender=user1, now=sp.timestamp(101).add_days(5), level=60)

    # Check that the contract information has been updated
    scenario.verify(dao.data.proposals[0].status.is_variant("rejected"))

    # Check that the tokens in escrow have been transferred back to user 4
    scenario.verify(token.data.ledger[user4.address] == 400)
    scenario.verify(token.data.ledger[dao.address] == 0)

    # Check that it's not possible to execute the proposal
    dao.execute_proposal(0).run(
        valid=False, sender=user1, now=sp.timestamp(101).add_days(5 + 2), exception="DAO_STATUS_NOT_APPROVED")


@sp.add_test(name="Test set representatives")
def test_set_representatives():
    # Get the test environment
    testEnvironment = get_test_environment()
    scenario = testEnvironment["scenario"]
    user1 = testEnvironment["user1"]
    user2 = testEnvironment["user2"]
    user3 = testEnvironment["user3"]
    dao = testEnvironment["dao"]
    representatives = testEnvironment["representatives"]

    # Create a new representatives account
    new_representatives = sp.test_account("new_representatives")

    # Define the lambda function that will set the new representatives address
    def representatives_lambda_function(params):
        sp.set_type(params, sp.TUnit)
        set_representatives_handle = sp.contract(
            sp.TAddress, dao.address, "set_representatives").open_some()
        sp.result([sp.transfer_operation(
            new_representatives.address, sp.mutez(0), set_representatives_handle)])

    # Check the initial representatives address
    scenario.verify(dao.data.representatives == representatives.address)

    # Add a lambda proposal
    representatives.add_proposal(sp.variant("lambda_function", representatives_lambda_function)).run(sender=user1)

    # Vote for the proposal
    representatives.vote_proposal(proposal_id=0, approval=True).run(sender=user1)
    representatives.vote_proposal(proposal_id=0, approval=False).run(sender=user2)
    representatives.vote_proposal(proposal_id=0, approval=True).run(sender=user3)

    # Execute the proposal
    representatives.execute_proposal(0).run(sender=user3)

    # Check that the representatives address has been updated
    scenario.verify(dao.data.representatives == new_representatives.address)

    # Check that the old representatives cannot set the representatives again
    representatives.add_proposal(sp.variant("lambda_function", representatives_lambda_function)).run(sender=user1)
    representatives.vote_proposal(proposal_id=1, approval=True).run(sender=user1)
    representatives.vote_proposal(proposal_id=1, approval=False).run(sender=user2)
    representatives.vote_proposal(proposal_id=1, approval=True).run(sender=user3)
    representatives.execute_proposal(1).run(
        valid=False, sender=user3, exception="DAO_NOT_DAO_OR_REPRESENTATIVES")


@sp.add_test(name="Test set guardians")
def test_set_guardians():
    # Get the test environment
    testEnvironment = get_test_environment()
    scenario = testEnvironment["scenario"]
    user4 = testEnvironment["user4"]
    user5 = testEnvironment["user5"]
    dao = testEnvironment["dao"]
    guardians = testEnvironment["guardians"]

    # Create a new DAO guardians account
    new_guardians = sp.test_account("new_guardians")

    # Define the lambda function that will set the new guardians address
    def guardians_lambda_function(params):
        sp.set_type(params, sp.TUnit)
        set_guardians_handle = sp.contract(
            sp.TAddress, dao.address, "set_guardians").open_some()
        sp.result([sp.transfer_operation(
            new_guardians.address, sp.mutez(0), set_guardians_handle)])

    # Check the initial DAO guardians address
    scenario.verify(dao.data.guardians == guardians.address)

    # Add a lambda proposal
    guardians.lambda_function_proposal(guardians_lambda_function).run(sender=user4)

    # Vote for the proposal
    guardians.vote_proposal(proposal_id=0, approval=True).run(sender=user4)
    guardians.vote_proposal(proposal_id=0, approval=True).run(sender=user5)

    # Execute the proposal
    guardians.execute_proposal(0).run(sender=user4)

    # Check that the representatives address has been updated
    scenario.verify(dao.data.guardians == new_guardians.address)

    # Check that the old DAO guardians cannot set the guardians again
    guardians.lambda_function_proposal(guardians_lambda_function).run(sender=user4)
    guardians.vote_proposal(proposal_id=1, approval=True).run(sender=user4)
    guardians.vote_proposal(proposal_id=1, approval=True).run(sender=user5)
    guardians.execute_proposal(1).run(
        valid=False, sender=user4, exception="DAO_NOT_DAO_OR_GUARDIANS")


@sp.add_test(name="Test admin")
def test_admin():
    # Get the test environment
    testEnvironment = get_test_environment()
    scenario = testEnvironment["scenario"]
    admin = testEnvironment["admin"]
    dao = testEnvironment["dao"]

    # Create a new treasury account
    new_treasury = sp.test_account("new_treasury")

    # Update the DAO treasury address
    dao.set_treasury(new_treasury.address).run(sender=admin)

    # Check that the treasury address has been updated
    scenario.verify(dao.data.treasury == new_treasury.address)

    # Update the DAO quorum
    dao.set_quorum(2).run(sender=admin)

    # Check that the quorum has been updated
    scenario.verify(dao.data.quorum == 2)


@sp.add_test(name="Test integer square root")
def test_integer_square_root():
    # Get the test environment
    testEnvironment = get_test_environment()
    scenario = testEnvironment["scenario"]
    dao = testEnvironment["dao"]

    dao.get_integer_square_root(0)
    scenario.verify(dao.data.counter == 0)

    dao.get_integer_square_root(1)
    scenario.verify(dao.data.counter == 1)

    dao.get_integer_square_root(3)
    scenario.verify(dao.data.counter == 1)

    dao.get_integer_square_root(4)
    scenario.verify(dao.data.counter == 2)

    dao.get_integer_square_root(8)
    scenario.verify(dao.data.counter == 2)

    dao.get_integer_square_root(9)
    scenario.verify(dao.data.counter == 3)

    dao.get_integer_square_root(10)
    scenario.verify(dao.data.counter == 3)

    dao.get_integer_square_root(12345 * 12345 - 1)
    scenario.verify(dao.data.counter == 12344)

    dao.get_integer_square_root(12345 * 12345)
    scenario.verify(dao.data.counter == 12345)

    dao.get_integer_square_root(12345 * 12345 + 1)
    scenario.verify(dao.data.counter == 12345)


@sp.add_test(name="Test quadratic voting")
def test_quadratic_voting():
    # Get the test environment
    decimals = 1000000
    testEnvironment = get_test_environment(
        vote_weight_mode="quadratic", decimals=decimals)
    scenario = testEnvironment["scenario"]
    user1 = testEnvironment["user1"]
    user2 = testEnvironment["user2"]
    user3 = testEnvironment["user3"]
    user4 = testEnvironment["user4"]
    user5 = testEnvironment["user5"]
    user6 = testEnvironment["user6"]
    external_user = testEnvironment["external_user"]
    token = testEnvironment["token"]
    treasury = testEnvironment["treasury"]
    representatives = testEnvironment["representatives"]
    dao = testEnvironment["dao"]

    # User 4 creates a proposal
    proposal_title = sp.utils.bytes_of_string("Dummy title")
    proposal_description = sp.utils.bytes_of_string("Dummy description")
    proposal_kind = sp.variant("text", sp.unit)
    dao.create_proposal(
        title=proposal_title,
        description=proposal_description,
        kind=proposal_kind).run(
            sender=user4, level=10, now=sp.timestamp(100))

    # User 1 and 2 vote as representatives
    dao.representatives_vote(proposal_id=0, vote=sp.variant("abstain", sp.unit)).run(
        sender=user1, now=sp.timestamp(200), level=20)
    dao.representatives_vote(proposal_id=0, vote=sp.variant("yes", sp.unit)).run(
        sender=user2, now=sp.timestamp(300), level=30)

    # Check that the contract information has been updated
    scenario.verify(dao.data.proposals[0].representatives_votes.total == 2)
    scenario.verify(dao.data.proposals[0].representatives_votes.positive == 1)
    scenario.verify(dao.data.proposals[0].representatives_votes.negative == 0)
    scenario.verify(dao.data.proposals[0].representatives_votes.abstain == 1)
    scenario.verify(dao.data.proposals[0].representatives_votes.participation == 2)
    scenario.verify(dao.data.representatives_votes[(0, "community1")].is_variant("abstain"))
    scenario.verify(dao.data.representatives_votes[(0, "community2")].is_variant("yes"))

    # User 3, 4 and 5 vote as normal users
    dao.token_vote(proposal_id=0, vote=sp.variant("yes", sp.unit), max_checkpoints=sp.none).run(
        sender=user3, now=sp.timestamp(400), level=40)
    dao.token_vote(proposal_id=0, vote=sp.variant("yes", sp.unit), max_checkpoints=sp.none).run(
        sender=user4, now=sp.timestamp(400), level=40)
    dao.token_vote(proposal_id=0, vote=sp.variant("no", sp.unit), max_checkpoints=sp.none).run(
        sender=user5, now=sp.timestamp(400), level=40)

    # Check that the contract information has been updated
    scenario.verify(dao.data.proposals[0].token_votes.total == 100 * int(pow(300 * decimals / 10000, 0.5)) + 100 * int(pow(400 * decimals / 10000, 0.5)) + 100 * int(pow(5 * decimals / 10000, 0.5)))
    scenario.verify(dao.data.proposals[0].token_votes.positive == 100 * int(pow(300 * decimals / 10000, 0.5)) + 100 * int(pow(400 * decimals / 10000, 0.5)))
    scenario.verify(dao.data.proposals[0].token_votes.negative == 100 * int(pow(5 * decimals / 10000, 0.5)))
    scenario.verify(dao.data.proposals[0].token_votes.abstain == 0)
    scenario.verify(dao.data.proposals[0].token_votes.participation == 3)
    scenario.verify(dao.data.representatives_votes[(0, "community1")].is_variant("abstain"))
    scenario.verify(dao.data.representatives_votes[(0, "community2")].is_variant("yes"))
    scenario.verify(dao.data.token_votes[(0, user3.address)].vote.is_variant("yes"))
    scenario.verify(dao.data.token_votes[(0, user3.address)].weight == 100 * int(pow(300 * decimals / 10000, 0.5)))
    scenario.verify(dao.data.token_votes[(0, user4.address)].vote.is_variant("yes"))
    scenario.verify(dao.data.token_votes[(0, user4.address)].weight == 100 * int(pow(400 * decimals / 10000, 0.5)))
    scenario.verify(dao.data.token_votes[(0, user5.address)].vote.is_variant("no"))
    scenario.verify(dao.data.token_votes[(0, user5.address)].weight == 100 * int(pow(5 * decimals / 10000, 0.5)))


if ('tzip16_error_lint' in environ.get('TEIA_SC_PARAMS','').split(':') and
    type(daoGovernanceModule.DAOGovernance.error_collection).__name__ == 'ErrorCollection'):
    @sp.add_test(name="Lint FAILWITH messages")
    def test_error_message_rules():
        scenario = sp.test_scenario()
        daoGovernanceModule.DAOGovernance.error_collection.scenario_linting_report(scenario)
