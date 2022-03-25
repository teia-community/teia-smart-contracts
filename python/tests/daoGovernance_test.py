"""Unit tests for the DAO governance class.

"""

import smartpy as sp

# Import the DAO modules
daoTokenModule = sp.io.import_script_from_url("file:contracts/daoToken.py")
daoTreasuryModule = sp.io.import_script_from_url("file:contracts/daoTreasury.py")
daoGovernanceModule = sp.io.import_script_from_url("file:contracts/daoGovernance.py")
representativesModule = sp.io.import_script_from_url("file:contracts/representatives.py")


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


def get_test_environment():
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
        max_supply=2000,
        max_share=500)
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
        users=sp.set([user1.address, user2.address, user3.address, user6.address]),
        dao=admin.address,
        minimum_votes=2,
        expiration_time=3)
    scenario += representatives

    # Initialize the DAO governance contract
    dao = daoGovernanceModule.DAOGovernance(
        metadata=sp.utils.metadata_of_url("ipfs://eee"),
        treasury=treasury.address,
        token=token.address,
        representatives=representatives.address,
        quorum=800,
        governance_parameters=sp.record(
            voting_period=5,
            escrow_amount=10,
            escrow_return=40,
            supermajority=60,
            representatives_share=30,
            quorum_update_period=3,
            quorum_update=20,
            quorum_max_change=20,
            min_quorum=100,
            max_quorum=1300))
    scenario += dao

    # Update the treasury and representatives DAO contract address
    treasury.set_dao(dao.address).run(sender=admin)
    representatives.set_dao(dao.address).run(sender=admin)

    # Add the DAO treasury and DAO governance contracts as maximum share exceptions
    token.add_max_share_exception(treasury.address).run(sender=admin)
    token.add_max_share_exception(dao.address).run(sender=admin)

    # Mint all the DAO tokens and assign them to the users and the treasury
    token.mint([
        sp.record(to_=user1.address, token_id=0, amount=100),
        sp.record(to_=user2.address, token_id=0, amount=200),
        sp.record(to_=user3.address, token_id=0, amount=300),
        sp.record(to_=user4.address, token_id=0, amount=400),
        sp.record(to_=user5.address, token_id=0, amount=5),
        sp.record(to_=user6.address, token_id=0, amount=5),
        sp.record(to_=treasury.address, token_id=0, amount=990)]).run(sender=admin)

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
        "dao": dao}

    return testEnvironment


@sp.add_test(name="Test text proposal")
def test_text_proposal():
    # Get the test environment
    testEnvironment = get_test_environment()
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

    # Check that the initial contract storage information is correct
    scenario.verify(dao.data.metadata[""] == sp.utils.bytes_of_string("ipfs://eee"))
    scenario.verify(dao.data.treasury == treasury.address)
    scenario.verify(dao.data.token == token.address)
    scenario.verify(dao.data.representatives == representatives.address)
    scenario.verify(dao.data.quorum == 800)
    scenario.verify(dao.data.last_quorum_update == sp.timestamp(0))
    scenario.verify(dao.get_proposal_count() == 0)

    # Check that non-DAO members cannot create proposals

    proposal_kind = sp.variant("text", sp.unit)
    proposal_title = sp.utils.bytes_of_string("Dummy title")
    proposal_description = sp.utils.bytes_of_string("Dummy description")
    dao.create_proposal(
        kind=proposal_kind,
        title=proposal_title,
        description=proposal_description).run(
            valid=False, sender=external_user, now=sp.timestamp(100), exception="DAO_NOT_MEMBER")

    # Check that members with less tokens than the escrow cannot create proposals
    dao.create_proposal(
        kind=proposal_kind,
        title=proposal_title,
        description=proposal_description).run(
            valid=False, sender=user5, now=sp.timestamp(100), exception="FA2_INSUFFICIENT_BALANCE")

    # User 4 creates a proposal
    dao.create_proposal(
        kind=proposal_kind,
        title=proposal_title,
        description=proposal_description).run(
            sender=user4, level=10, now=sp.timestamp(100))

    # Check that the contract information has been updated
    scenario.verify(dao.get_proposal(0).kind.is_variant("text"))
    scenario.verify(dao.get_proposal(0).title == proposal_title)
    scenario.verify(dao.get_proposal(0).description == proposal_description)
    scenario.verify(dao.get_proposal(0).issuer == user4.address)
    scenario.verify(dao.get_proposal(0).timestamp == sp.timestamp(100))
    scenario.verify(dao.get_proposal(0).level == 10)
    scenario.verify(dao.get_proposal(0).escrow_amount == 10)
    scenario.verify(dao.get_proposal(0).status.is_variant("open"))
    scenario.verify(dao.get_proposal_count() == 1)

    # Check that the tokens in escrow have been transferred
    scenario.verify(token.data.ledger[user4.address] == 400 - 10)
    scenario.verify(token.data.ledger[dao.address] == 10)

    # Check that it's not possible to vote an innexisting proposal
    representatives.vote_dao_proposal(proposal_id=1, vote=sp.variant("abstain", sp.unit)).run(
        valid=False, sender=user1, now=sp.timestamp(200), level=20, exception="DAO_INEXISTENT_PROPOSAL")
    dao.token_vote(proposal_id=1, vote=sp.variant("abstain", sp.unit), max_checkpoints=sp.none).run(
        valid=False, sender=user1, now=sp.timestamp(200), level=20, exception="DAO_INEXISTENT_PROPOSAL")

    # Check that it's not possible to vote without tokens
    dao.token_vote(proposal_id=0, vote=sp.variant("abstain", sp.unit), max_checkpoints=sp.none).run(
        valid=False, sender=external_user, now=sp.timestamp(200), level=20, exception="DAO_ZERO_BALANCE")

    # User 1 votes as representative
    representatives.vote_dao_proposal(proposal_id=0, vote=sp.variant("abstain", sp.unit)).run(
        sender=user1, now=sp.timestamp(200), level=20)

    # Check that the contract information has been updated
    scenario.verify(dao.get_proposal(0).representatives_votes.total == 1)
    scenario.verify(dao.get_proposal(0).representatives_votes.positive == 0)
    scenario.verify(dao.get_proposal(0).representatives_votes.negative == 0)
    scenario.verify(dao.get_proposal(0).representatives_votes.abstain == 1)
    scenario.verify(dao.get_proposal(0).representatives_votes.participation == 1)
    scenario.verify(dao.get_representative_vote(sp.record(proposal_id=0, member=user1.address)).is_variant("abstain"))

    # Check that it's not possible to vote twice
    representatives.vote_dao_proposal(proposal_id=0, vote=sp.variant("yes", sp.unit)).run(
        valid=False, sender=user1, now=sp.timestamp(250), level=25, exception="DAO_ALREADY_VOTED")
    # dao.token_vote(proposal_id=0, vote=sp.variant("yes", sp.unit), max_checkpoints=sp.none).run(
    #    valid=False, sender=user1, now=sp.timestamp(250), level=25, exception="DAO_ALREADY_VOTED")

    # User 2 votes as representative
    representatives.vote_dao_proposal(proposal_id=0, vote=sp.variant("yes", sp.unit)).run(
        sender=user2, now=sp.timestamp(300), level=30)

    # Check that non representatives cannot vote as representatives
    representatives.vote_dao_proposal(proposal_id=0, vote=sp.variant("yes", sp.unit)).run(
        valid=False, sender=user4, now=sp.timestamp(400), level=40, exception="MS_NOT_USER")

    # User 3, 4 and 5 vote as normal users
    dao.token_vote(proposal_id=0, vote=sp.variant("yes", sp.unit), max_checkpoints=sp.none).run(
        sender=user3, now=sp.timestamp(400), level=40)
    dao.token_vote(proposal_id=0, vote=sp.variant("yes", sp.unit), max_checkpoints=sp.none).run(
        sender=user4, now=sp.timestamp(400), level=40)
    dao.token_vote(proposal_id=0, vote=sp.variant("no", sp.unit), max_checkpoints=sp.none).run(
        sender=user5, now=sp.timestamp(400), level=40)

    # Check that the contract information has been updated
    scenario.verify(dao.get_proposal(0).representatives_votes.total == 2)
    scenario.verify(dao.get_proposal(0).representatives_votes.positive == 1)
    scenario.verify(dao.get_proposal(0).representatives_votes.negative == 0)
    scenario.verify(dao.get_proposal(0).representatives_votes.abstain == 1)
    scenario.verify(dao.get_proposal(0).representatives_votes.participation == 2)
    scenario.verify(dao.get_proposal(0).token_votes.total == 300 + 400 + 5)
    scenario.verify(dao.get_proposal(0).token_votes.positive == 300 + 400)
    scenario.verify(dao.get_proposal(0).token_votes.negative == 5)
    scenario.verify(dao.get_proposal(0).token_votes.abstain == 0)
    scenario.verify(dao.get_proposal(0).token_votes.participation == 3)
    scenario.verify(dao.get_representative_vote(sp.record(proposal_id=0, member=user1.address)).is_variant("abstain"))
    scenario.verify(dao.get_representative_vote(sp.record(proposal_id=0, member=user2.address)).is_variant("yes"))
    scenario.verify(dao.get_vote(sp.record(proposal_id=0, member=user3.address)).vote.is_variant("yes"))
    scenario.verify(dao.get_vote(sp.record(proposal_id=0, member=user3.address)).weight == 300)
    scenario.verify(dao.get_vote(sp.record(proposal_id=0, member=user4.address)).vote.is_variant("yes"))
    scenario.verify(dao.get_vote(sp.record(proposal_id=0, member=user4.address)).weight == 400)
    scenario.verify(dao.get_vote(sp.record(proposal_id=0, member=user5.address)).vote.is_variant("no"))
    scenario.verify(dao.get_vote(sp.record(proposal_id=0, member=user5.address)).weight == 5)

    # Check that it's not possible to evaluate the proposal results before is closed
    dao.evaluate_voting_result(0).run(
        valid=False, sender=user1, now=sp.timestamp(500), level=50, exception="DAO_OPEN_PROPOSAL")

    # Check that only DAO members can evaluate the proposal results
    dao.evaluate_voting_result(0).run(
        valid=False, sender=external_user, now=sp.timestamp(101).add_days(5), level=60, exception="DAO_NOT_MEMBER")

    # Check that it's not possible to vote when the proposal is closed
    representatives.vote_dao_proposal(proposal_id=0, vote=sp.variant("yes", sp.unit)).run(
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
    scenario.verify(dao.get_proposal(0).status.is_variant("approved"))
    scenario.verify(dao.data.quorum == int(800 * 0.8 + (300 + 400 + 5 + 800 * 0.3) * 0.2))
    scenario.verify(dao.data.last_quorum_update == sp.timestamp(101).add_days(5))

    # Check that the tokens in escrow have been transferred back to user 4
    scenario.verify(token.data.ledger[user4.address] == 400)
    scenario.verify(token.data.ledger[dao.address] == 0)

    # Check that only DAO members can execute the proposal
    dao.execute_proposal(0).run(
        valid=False, sender=external_user, exception="DAO_NOT_MEMBER")

    # Execute the proposal
    dao.execute_proposal(0).run(sender=user1)

    # Check that the contract information has been updated
    scenario.verify(dao.get_proposal(0).status.is_variant("executed"))

    # Check that it's not possible to execute twice the proposal
    dao.execute_proposal(0).run(
        valid=False, sender=user1, exception="DAO_STATUS_NOT_APPROVED")


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
    representatives = testEnvironment["representatives"]
    dao = testEnvironment["dao"]

    # Create the recipient contracts and add them to the test scenario
    recipient1 = Recipient()
    recipient2 = Recipient()
    scenario += recipient1
    scenario += recipient2

    # User 4 creates a proposal
    mutez_transfers = [
        sp.record(amount=sp.tez(1), destination=recipient1.address),
        sp.record(amount=sp.tez(2), destination=recipient2.address)]
    proposal_kind = sp.variant("transfer_mutez", mutez_transfers)
    proposal_title = sp.utils.bytes_of_string("Dummy title")
    proposal_description = sp.utils.bytes_of_string("Dummy description")
    dao.create_proposal(
        kind=proposal_kind,
        title=proposal_title,
        description=proposal_description).run(
            sender=user4, level=10, now=sp.timestamp(100))

    # Check that the contract information has been updated
    scenario.verify(dao.get_proposal(0).kind.is_variant("transfer_mutez"))
    scenario.verify(dao.get_proposal(0).title == proposal_title)
    scenario.verify(dao.get_proposal(0).description == proposal_description)
    scenario.verify(dao.get_proposal(0).issuer == user4.address)
    scenario.verify(dao.get_proposal(0).timestamp == sp.timestamp(100))
    scenario.verify(dao.get_proposal(0).level == 10)
    scenario.verify(dao.get_proposal(0).escrow_amount == 10)
    scenario.verify(dao.get_proposal(0).status.is_variant("open"))
    scenario.verify(dao.get_proposal_count() == 1)

    # Check that the tokens in escrow have been transferred
    scenario.verify(token.data.ledger[user4.address] == 400 - 10)
    scenario.verify(token.data.ledger[dao.address] == 10)

    # Users 1 and 2 vote as representatives
    representatives.vote_dao_proposal(proposal_id=0, vote=sp.variant("abstain", sp.unit)).run(
        sender=user1, now=sp.timestamp(200), level=20)
    representatives.vote_dao_proposal(proposal_id=0, vote=sp.variant("yes", sp.unit)).run(
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
    scenario.verify(dao.get_proposal(0).status.is_variant("approved"))

    # Check that the tokens in escrow have been transferred back to user 4
    scenario.verify(token.data.ledger[user4.address] == 400)
    scenario.verify(token.data.ledger[dao.address] == 0)

    # Execute the proposal
    dao.execute_proposal(0).run(sender=user1)

    # Check that the contract information has been updated
    scenario.verify(dao.get_proposal(0).status.is_variant("executed"))

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
    representatives = testEnvironment["representatives"]
    dao = testEnvironment["dao"]

    # User 4 creates a proposal
    token_transfers = sp.set_type_expr(
        sp.record(
            fa2=token.address,
            token_id=sp.nat(0),
            distribution=[
                sp.record(amount=sp.nat(10), destination=user1.address),
                sp.record(amount=sp.nat(20), destination=external_user.address)]),
        t=daoGovernanceModule.DAOGovernance.TOKEN_TRANSFERS_TYPE)
    proposal_kind = sp.variant("transfer_token", token_transfers)
    proposal_title = sp.utils.bytes_of_string("Dummy title")
    proposal_description = sp.utils.bytes_of_string("Dummy description")
    dao.create_proposal(
        kind=proposal_kind,
        title=proposal_title,
        description=proposal_description).run(
            sender=user4, level=10, now=sp.timestamp(100))

    # Check that the contract information has been updated
    scenario.verify(dao.get_proposal(0).kind.is_variant("transfer_token"))
    scenario.verify(dao.get_proposal(0).title == proposal_title)
    scenario.verify(dao.get_proposal(0).description == proposal_description)
    scenario.verify(dao.get_proposal(0).issuer == user4.address)
    scenario.verify(dao.get_proposal(0).timestamp == sp.timestamp(100))
    scenario.verify(dao.get_proposal(0).level == 10)
    scenario.verify(dao.get_proposal(0).escrow_amount == 10)
    scenario.verify(dao.get_proposal(0).status.is_variant("open"))
    scenario.verify(dao.get_proposal_count() == 1)

    # Check that the tokens in escrow have been transferred
    scenario.verify(token.data.ledger[user4.address] == 400 - 10)
    scenario.verify(token.data.ledger[dao.address] == 10)

    # Users 1 and 2 vote as representatives
    representatives.vote_dao_proposal(proposal_id=0, vote=sp.variant("abstain", sp.unit)).run(
        sender=user1, now=sp.timestamp(200), level=20)
    representatives.vote_dao_proposal(proposal_id=0, vote=sp.variant("yes", sp.unit)).run(
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
    scenario.verify(dao.get_proposal(0).status.is_variant("approved"))

    # Check that the tokens in escrow have been transferred back to user 4
    scenario.verify(token.data.ledger[user4.address] == 400)
    scenario.verify(token.data.ledger[dao.address] == 0)

    # Execute the proposal
    dao.execute_proposal(0).run(sender=user1)

    # Check that the contract information has been updated
    scenario.verify(dao.get_proposal(0).status.is_variant("executed"))

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
    representatives = testEnvironment["representatives"]
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
    proposal_kind = sp.variant("lambda_function", treasury_lambda_function)
    proposal_title = sp.utils.bytes_of_string("Dummy title")
    proposal_description = sp.utils.bytes_of_string("Dummy description")
    dao.create_proposal(
        kind=proposal_kind,
        title=proposal_title,
        description=proposal_description).run(
            sender=user4, level=10, now=sp.timestamp(100))

    # Check that the contract information has been updated
    scenario.verify(dao.get_proposal(0).kind.is_variant("lambda_function"))
    scenario.verify(dao.get_proposal(0).title == proposal_title)
    scenario.verify(dao.get_proposal(0).description == proposal_description)
    scenario.verify(dao.get_proposal(0).issuer == user4.address)
    scenario.verify(dao.get_proposal(0).timestamp == sp.timestamp(100))
    scenario.verify(dao.get_proposal(0).level == 10)
    scenario.verify(dao.get_proposal(0).escrow_amount == 10)
    scenario.verify(dao.get_proposal(0).status.is_variant("open"))
    scenario.verify(dao.get_proposal_count() == 1)

    # Check that the tokens in escrow have been transferred
    scenario.verify(token.data.ledger[user4.address] == 400 - 10)
    scenario.verify(token.data.ledger[dao.address] == 10)

    # Users 1 and 2 vote as representatives
    representatives.vote_dao_proposal(proposal_id=0, vote=sp.variant("abstain", sp.unit)).run(
        sender=user1, now=sp.timestamp(200), level=20)
    representatives.vote_dao_proposal(proposal_id=0, vote=sp.variant("yes", sp.unit)).run(
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
    scenario.verify(dao.get_proposal(0).status.is_variant("approved"))

    # Check that the tokens in escrow have been transferred back to user 4
    scenario.verify(token.data.ledger[user4.address] == 400)
    scenario.verify(token.data.ledger[dao.address] == 0)

    # Execute the proposal
    dao.execute_proposal(0).run(sender=user1)

    # Check that the contract information has been updated
    scenario.verify(dao.get_proposal(0).status.is_variant("executed"))

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
                voting_period=5,
                escrow_amount=20,
                escrow_return=30,
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
    proposal_kind = sp.variant("lambda_function", governance_parameters_lambda_function)
    proposal_title = sp.utils.bytes_of_string("Dummy title 2")
    proposal_description = sp.utils.bytes_of_string("Dummy description 2")
    dao.create_proposal(
        kind=proposal_kind,
        title=proposal_title,
        description=proposal_description).run(
            sender=user1, level=50, now=sp.timestamp(500))

    # Check that the contract information has been updated
    scenario.verify(dao.get_proposal(1).kind.is_variant("lambda_function"))
    scenario.verify(dao.get_proposal(1).title == proposal_title)
    scenario.verify(dao.get_proposal(1).description == proposal_description)
    scenario.verify(dao.get_proposal(1).issuer == user1.address)
    scenario.verify(dao.get_proposal(1).timestamp == sp.timestamp(500))
    scenario.verify(dao.get_proposal(1).level == 50)
    scenario.verify(dao.get_proposal(1).escrow_amount == 10)
    scenario.verify(dao.get_proposal(1).status.is_variant("open"))
    scenario.verify(dao.get_proposal_count() == 2)

    # Check that the tokens in escrow have been transferred
    scenario.verify(token.data.ledger[user1.address] == 100 - 10)
    scenario.verify(token.data.ledger[dao.address] == 10)

    # Users 1 and 2 vote as representatives
    representatives.vote_dao_proposal(proposal_id=1, vote=sp.variant("abstain", sp.unit)).run(
        sender=user1, now=sp.timestamp(600), level=60)
    representatives.vote_dao_proposal(proposal_id=1, vote=sp.variant("yes", sp.unit)).run(
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
    scenario.verify(dao.get_proposal(1).status.is_variant("approved"))

    # Check that the tokens in escrow have been transferred back to user 4
    scenario.verify(token.data.ledger[user1.address] == 100)
    scenario.verify(token.data.ledger[dao.address] == 0)

    # Execute the proposal
    dao.execute_proposal(1).run(sender=user1)

    # Check that the contract information has been updated
    scenario.verify(dao.get_proposal(1).status.is_variant("executed"))

    # Check that the DAO governance parameters has been updated
    scenario.verify(dao.data.governance_parameters.escrow_amount == 20)

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
    proposal_kind = sp.variant("lambda_function", representatives_lambda_function)
    proposal_title = sp.utils.bytes_of_string("Dummy title 3")
    proposal_description = sp.utils.bytes_of_string("Dummy description 3")
    dao.create_proposal(
        kind=proposal_kind,
        title=proposal_title,
        description=proposal_description).run(
            sender=user2, level=100, now=sp.timestamp(1000))

    # Check that the contract information has been updated
    scenario.verify(dao.get_proposal(2).kind.is_variant("lambda_function"))
    scenario.verify(dao.get_proposal(2).title == proposal_title)
    scenario.verify(dao.get_proposal(2).description == proposal_description)
    scenario.verify(dao.get_proposal(2).issuer == user2.address)
    scenario.verify(dao.get_proposal(2).timestamp == sp.timestamp(1000))
    scenario.verify(dao.get_proposal(2).level == 100)
    scenario.verify(dao.get_proposal(2).escrow_amount == 20)
    scenario.verify(dao.get_proposal(2).status.is_variant("open"))
    scenario.verify(dao.get_proposal_count() == 3)

    # Check that the tokens in escrow have been transferred
    scenario.verify(token.data.ledger[user2.address] == 200 - 20)
    scenario.verify(token.data.ledger[dao.address] == 20)

    # Users 1 and 2 vote as representatives
    representatives.vote_dao_proposal(proposal_id=2, vote=sp.variant("abstain", sp.unit)).run(
        sender=user1, now=sp.timestamp(1600), level=160)
    representatives.vote_dao_proposal(proposal_id=2, vote=sp.variant("yes", sp.unit)).run(
        sender=user2, now=sp.timestamp(1700), level=170)

    # User 3, 4 and 5 vote as normal users
    dao.token_vote(proposal_id=2, vote=sp.variant("yes", sp.unit), max_checkpoints=sp.none).run(
        sender=user3, now=sp.timestamp(1800), level=180)
    dao.token_vote(proposal_id=2, vote=sp.variant("yes", sp.unit), max_checkpoints=sp.none).run(
        sender=user4, now=sp.timestamp(1900), level=190)
    dao.token_vote(proposal_id=2, vote=sp.variant("no", sp.unit), max_checkpoints=sp.none).run(
        sender=user5, now=sp.timestamp(2000), level=200)

    # Evaluate the proposal results
    dao.evaluate_voting_result(2).run(
        sender=user1, now=sp.timestamp(1001).add_days(5), level=210)

    # Check that the contract information has been updated
    scenario.verify(dao.get_proposal(2).status.is_variant("approved"))

    # Check that the tokens in escrow have been transferred back to user 4
    scenario.verify(token.data.ledger[user2.address] == 200)
    scenario.verify(token.data.ledger[dao.address] == 0)

    # Execute the proposal
    dao.execute_proposal(2).run(sender=user1)

    # Check that the contract information has been updated
    scenario.verify(dao.get_proposal(2).status.is_variant("executed"))

    # Check that the representatives address has been updated
    scenario.verify(dao.data.representatives == new_representatives.address)


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
    representatives = testEnvironment["representatives"]
    dao = testEnvironment["dao"]

    # User 4 creates a proposal
    token_transfers = sp.set_type_expr(
        sp.record(
            fa2=token.address,
            token_id=sp.nat(0),
            distribution=[
                sp.record(amount=sp.nat(10), destination=user1.address),
                sp.record(amount=sp.nat(20), destination=external_user.address)]),
        t=daoGovernanceModule.DAOGovernance.TOKEN_TRANSFERS_TYPE)
    proposal_kind = sp.variant("transfer_token", token_transfers)
    proposal_title = sp.utils.bytes_of_string("Dummy title")
    proposal_description = sp.utils.bytes_of_string("Dummy description")
    dao.create_proposal(
        kind=proposal_kind,
        title=proposal_title,
        description=proposal_description).run(
            sender=user4, level=10, now=sp.timestamp(100))

    # Check that the tokens in escrow have been transferred
    scenario.verify(token.data.ledger[user4.address] == 400 - 10)
    scenario.verify(token.data.ledger[dao.address] == 10)

    # Users 1 and 2 vote as representatives
    representatives.vote_dao_proposal(proposal_id=0, vote=sp.variant("no", sp.unit)).run(
        sender=user1, now=sp.timestamp(200), level=20)
    representatives.vote_dao_proposal(proposal_id=0, vote=sp.variant("no", sp.unit)).run(
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
    scenario.verify(dao.get_proposal(0).status.is_variant("rejected"))

    # Check that the tokens in escrow have been transferred to the treasury
    scenario.verify(token.data.ledger[user4.address] == 400 - 10)
    scenario.verify(token.data.ledger[dao.address] == 0)
    scenario.verify(token.data.ledger[treasury.address] == 990 + 10)

    # Check that it's not possible to execute the proposal
    dao.execute_proposal(0).run(
        valid=False, sender=user1, exception="DAO_STATUS_NOT_APPROVED")


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
    representatives = testEnvironment["representatives"]
    dao = testEnvironment["dao"]

    # User 4 creates a proposal
    token_transfers = sp.set_type_expr(
        sp.record(
            fa2=token.address,
            token_id=sp.nat(0),
            distribution=[
                sp.record(amount=sp.nat(10), destination=user1.address),
                sp.record(amount=sp.nat(20), destination=external_user.address)]),
        t=daoGovernanceModule.DAOGovernance.TOKEN_TRANSFERS_TYPE)
    proposal_kind = sp.variant("transfer_token", token_transfers)
    proposal_title = sp.utils.bytes_of_string("Dummy title")
    proposal_description = sp.utils.bytes_of_string("Dummy description")
    dao.create_proposal(
        kind=proposal_kind,
        title=proposal_title,
        description=proposal_description).run(
            sender=user4, level=10, now=sp.timestamp(100))

    # Check that the tokens in escrow have been transferred
    scenario.verify(token.data.ledger[user4.address] == 400 - 10)
    scenario.verify(token.data.ledger[dao.address] == 10)

    # Users 1 and 2 vote as representatives
    representatives.vote_dao_proposal(proposal_id=0, vote=sp.variant("yes", sp.unit)).run(
        sender=user1, now=sp.timestamp(200), level=20)
    representatives.vote_dao_proposal(proposal_id=0, vote=sp.variant("yes", sp.unit)).run(
        sender=user2, now=sp.timestamp(300), level=30)

    # User 5 votes as normal user
    dao.token_vote(proposal_id=0, vote=sp.variant("yes", sp.unit), max_checkpoints=sp.none).run(
        sender=user5, now=sp.timestamp(400), level=40)

    # Evaluate the proposal results
    dao.evaluate_voting_result(0).run(
        sender=user1, now=sp.timestamp(101).add_days(5), level=60)

    # Check that the contract information has been updated
    scenario.verify(dao.get_proposal(0).status.is_variant("rejected"))

    # Check that the tokens in escrow have been transferred back to user 4
    scenario.verify(token.data.ledger[user4.address] == 400)
    scenario.verify(token.data.ledger[dao.address] == 0)

    # Check that it's not possible to execute the proposal
    dao.execute_proposal(0).run(
        valid=False, sender=user1, exception="DAO_STATUS_NOT_APPROVED")


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
    representatives.lambda_function_proposal(representatives_lambda_function).run(sender=user1)

    # Vote for the proposal
    representatives.vote_proposal(proposal_id=0, approval=True).run(sender=user1)
    representatives.vote_proposal(proposal_id=0, approval=False).run(sender=user2)
    representatives.vote_proposal(proposal_id=0, approval=True).run(sender=user3)

    # Execute the proposal
    representatives.execute_proposal(0).run(sender=user3)

    # Check that the representatives address has been updated
    scenario.verify(dao.data.representatives == new_representatives.address)
