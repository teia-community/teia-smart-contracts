"""Unit tests for the DAO governance class.

"""

import smartpy as sp

# Import the DAO modules
daoTokenModule = sp.io.import_script_from_url("file:contracts/daoToken.py")
daoTreasuryModule = sp.io.import_script_from_url("file:contracts/daoTreasury.py")
daoGovernanceModule = sp.io.import_script_from_url("file:contracts/daoGovernance.py")
representativesModule = sp.io.import_script_from_url("file:contracts/representatives.py")


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
            escrow_return=30,
            supermajority=60,
            representatives_share=30,
            quorum_update_period=3,
            min_quorum=100,
            max_quorum=1300))
    scenario += dao

    # Add the DAO treasury and DAO governance contracts as maximum share exceptions
    token.add_max_share_exception(treasury.address).run(sender=admin)
    token.add_max_share_exception(dao.address).run(sender=admin)

    # Update the treasury DAO contract address
    treasury.set_dao(dao.address).run(sender=admin)

    # Update the representatives DAO contract address
    def dao_lambda_function(params):
        sp.set_type(params, sp.TUnit)
        set_dao_handle = sp.contract(sp.TAddress, representatives.address, "set_dao").open_some()
        sp.result([sp.transfer_operation(dao.address, sp.mutez(0), set_dao_handle)])

    representatives.lambda_function_proposal(dao_lambda_function).run(sender=user1)
    representatives.vote_proposal(proposal_id=0, approval=True).run(sender=user1)
    representatives.vote_proposal(proposal_id=0, approval=True).run(sender=user2)
    representatives.execute_proposal(0).run(sender=user1)

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


@sp.add_test(name="Test create vote and execute proposal")
def test_create_vote_and_execute_proposal():
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
    proposal_parameters = sp.record(
        mutez_transfers=sp.none,
        token_transfers=sp.none,
        lambda_function=sp.none)
    dao.create_proposal(
        kind=proposal_kind,
        title=proposal_title,
        description=proposal_description,
        parameters=proposal_parameters).run(
            valid=False, sender=external_user, now=sp.timestamp(100), exception="DAO_NOT_MEMBER")

    # Check that members with less tokens than the escrow cannot create proposals
    dao.create_proposal(
        kind=proposal_kind,
        title=proposal_title,
        description=proposal_description,
        parameters=proposal_parameters).run(
            valid=False, sender=user5, now=sp.timestamp(100), exception="FA2_INSUFFICIENT_BALANCE")

    # User 4 creates a proposal
    dao.create_proposal(
        kind=proposal_kind,
        title=proposal_title,
        description=proposal_description,
        parameters=proposal_parameters).run(
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
    scenario.verify(dao.data.representatives_votes[0].total == 1)
    scenario.verify(dao.data.representatives_votes[0].positive == 0)
    scenario.verify(dao.data.representatives_votes[0].negative == 0)
    scenario.verify(dao.data.representatives_votes[0].abstain == 1)
    scenario.verify(dao.data.representatives_votes[0].participation == 1)
    scenario.verify(dao.get_vote(sp.record(proposal_id=0, member=user1.address)).vote.is_variant("abstain"))
    scenario.verify(dao.get_vote(sp.record(proposal_id=0, member=user1.address)).weight == 0)

    # Check that it's not possible to vote twice
    representatives.vote_dao_proposal(proposal_id=0, vote=sp.variant("yes", sp.unit)).run(
        valid=False, sender=user1, now=sp.timestamp(250), level=25, exception="DAO_ALREADY_VOTED")
    dao.token_vote(proposal_id=0, vote=sp.variant("yes", sp.unit), max_checkpoints=sp.none).run(
        valid=False, sender=user1, now=sp.timestamp(250), level=25, exception="DAO_ALREADY_VOTED")

    # User 2 votes as representative
    representatives.vote_dao_proposal(proposal_id=0, vote=sp.variant("yes", sp.unit)).run(
        sender=user2, now=sp.timestamp(300), level=30)
    user5 = testEnvironment["user5"]

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
    scenario.verify(dao.data.representatives_votes[0].total == 2)
    scenario.verify(dao.data.representatives_votes[0].positive == 1)
    scenario.verify(dao.data.representatives_votes[0].negative == 0)
    scenario.verify(dao.data.representatives_votes[0].abstain == 1)
    scenario.verify(dao.data.representatives_votes[0].participation == 2)
    scenario.verify(dao.data.token_votes[0].total == 300 + 400 + 5)
    scenario.verify(dao.data.token_votes[0].positive == 300 + 400)
    scenario.verify(dao.data.token_votes[0].negative == 5)
    scenario.verify(dao.data.token_votes[0].abstain == 0)
    scenario.verify(dao.data.token_votes[0].participation == 3)
    scenario.verify(dao.get_vote(sp.record(proposal_id=0, member=user1.address)).vote.is_variant("abstain"))
    scenario.verify(dao.get_vote(sp.record(proposal_id=0, member=user1.address)).weight == 0)
    scenario.verify(dao.get_vote(sp.record(proposal_id=0, member=user2.address)).vote.is_variant("yes"))
    scenario.verify(dao.get_vote(sp.record(proposal_id=0, member=user2.address)).weight == 0)
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


@sp.add_test(name="Test set representatives")
def test_set_representatives():
    # Get the test environment
    testEnvironment = get_test_environment()
    scenario = testEnvironment["scenario"]
    user1 = testEnvironment["user1"]
    user2 = testEnvironment["user2"]
    user3 = testEnvironment["user3"]
    user4 = testEnvironment["user4"]
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
    representatives.vote_proposal(proposal_id=1, approval=True).run(sender=user1)
    representatives.vote_proposal(proposal_id=1, approval=False).run(sender=user2)
    representatives.vote_proposal(proposal_id=1, approval=True).run(sender=user3)

    # Execute the proposal
    representatives.execute_proposal(1).run(sender=user3)

    # Check that the representatives address has been updated
    scenario.verify(dao.data.representatives == new_representatives.address)
