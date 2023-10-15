"""Unit tests for the Teia polls class.

"""
from os import environ
import smartpy as sp

# Import the DAO modules
daoTokenModule = sp.io.import_script_from_url("file:contracts/daoToken.py")
teiaPollsModule = sp.io.import_script_from_url("file:contracts/teiaPolls.py")


def get_test_environment(decimals=1):
    # Initialize the test scenario
    scenario = sp.test_scenario()

    # Create the test accounts
    admin = sp.test_account("admin")
    user1 = sp.test_account("user1")
    user2 = sp.test_account("user2")
    user3 = sp.test_account("user3")
    external_user = sp.test_account("external_user")

    # Initialize the DAO token FA2 contract
    token = daoTokenModule.DAOToken(
        administrator=admin.address,
        metadata=sp.utils.metadata_of_url("ipfs://aaa"),
        token_metadata=sp.utils.bytes_of_string("ipfs://bbb"),
        initial_owner=admin.address,
        supply=2000 * decimals,
        max_share=500 * decimals)
    scenario += token

    # Initialize the Teia polls contract
    polls = teiaPollsModule.TeiaPolls(
        metadata=sp.utils.metadata_of_url("ipfs://ccc"),
        token=token.address)
    scenario += polls

    # Transfer some the editions from the admin to the users and the treasury
    token.transfer([
        sp.record(
            from_=admin.address,
            txs=[
                sp.record(to_=user1.address, token_id=0, amount=100 * decimals),
                sp.record(to_=user2.address, token_id=0, amount=200 * decimals),
                sp.record(to_=user3.address, token_id=0, amount=300 * decimals)])
        ]).run(sender=admin)

    # Save all the variables in a test environment dictionary
    testEnvironment = {
        "scenario": scenario,
        "user1": user1,
        "user2": user2,
        "user3": user3,
        "external_user": external_user,
        "token": token,
        "polls": polls}

    return testEnvironment


@sp.add_test(name="Test create poll")
def test_create_poll():
    # Get the test environment
    testEnvironment = get_test_environment()
    scenario = testEnvironment["scenario"]
    user1 = testEnvironment["user1"]
    user2 = testEnvironment["user2"]
    user3 = testEnvironment["user3"]
    external_user = testEnvironment["external_user"]
    token = testEnvironment["token"]
    polls = testEnvironment["polls"]

    # Check that the initial contract storage information is correct
    scenario.verify(polls.data.metadata[""] == sp.utils.bytes_of_string("ipfs://ccc"))
    scenario.verify(polls.data.token == token.address)
    scenario.verify(polls.data.counter == 0)

    # Check that non-DAO members cannot create polls
    poll_question = sp.utils.bytes_of_string("Dummy question")
    poll_description = sp.utils.bytes_of_string("Dummy description")
    poll_options = {
        1: sp.utils.bytes_of_string("option 1"),
        2: sp.utils.bytes_of_string("option 2"),
        3: sp.utils.bytes_of_string("option 3")}
    vote_weight_method = sp.variant("linear", sp.unit)
    vote_period = 3
    polls.create_poll(
        question=poll_question,
        description=poll_description,
        options=poll_options,
        vote_weight_method=vote_weight_method,
        vote_period=vote_period).run(
            valid=False, sender=external_user, level=10, now=sp.timestamp(100), exception="POLL_NOT_DAO_MEMBER")

    # Check that user 1 can create a poll
    polls.create_poll(
        question=poll_question,
        description=poll_description,
        options=poll_options,
        vote_weight_method=vote_weight_method,
        vote_period=vote_period).run(
            sender=user1, level=10, now=sp.timestamp(100))

    # Check that the contract information has been updated
    poll = polls.get_poll(0)
    scenario.verify(poll.question == poll_question)
    scenario.verify(poll.description == poll_description)
    scenario.verify(sp.len(poll.options) == 3)
    scenario.verify(poll.options[1] == poll_options[1])
    scenario.verify(poll.options[2] == poll_options[2])
    scenario.verify(poll.options[3] == poll_options[3])
    scenario.verify(poll.vote_weight_method.is_variant("linear"))
    scenario.verify(poll.issuer == user1.address)
    scenario.verify(poll.timestamp == sp.timestamp(100))
    scenario.verify(poll.level == 10)
    scenario.verify(sp.len(poll.votes_count) == 3)
    scenario.verify(poll.votes_count[1] == 0)
    scenario.verify(poll.votes_count[2] == 0)
    scenario.verify(poll.votes_count[3] == 0)
    scenario.verify(polls.data.counter == 1)
    scenario.verify(polls.get_poll_count() == 1)

    # Check that submitting a proposal with only 1 option fails
    polls.create_poll(
        question=poll_question,
        description=poll_description,
        options={1: sp.utils.bytes_of_string("option 1")},
        vote_weight_method=vote_weight_method,
        vote_period=vote_period).run(
            valid=False, sender=user1, level=20, now=sp.timestamp(200), exception="POLL_WRONG_OPTIONS")

    # Check that submitting a proposal with the wrong vote period fails
    polls.create_poll(
        question=poll_question,
        description=poll_description,
        options=poll_options,
        vote_weight_method=vote_weight_method,
        vote_period=0).run(
            valid=False, sender=user1, level=20, now=sp.timestamp(200), exception="POLL_WRONG_VOTE_PERIOD")
    polls.create_poll(
        question=poll_question,
        description=poll_description,
        options=poll_options,
        vote_weight_method=vote_weight_method,
        vote_period=31).run(
            valid=False, sender=user1, level=20, now=sp.timestamp(200), exception="POLL_WRONG_VOTE_PERIOD")

    # Check that user 2 can create another poll
    poll_question = sp.utils.bytes_of_string("Dummy question 2")
    poll_description = sp.utils.bytes_of_string("Dummy description 2")
    poll_options = {
        0: sp.utils.bytes_of_string("option 0"),
        7: sp.utils.bytes_of_string("option 7"),
        9: sp.utils.bytes_of_string("option 9")}
    vote_weight_method = sp.variant("quadratic", sp.unit)
    vote_period = 10
    polls.create_poll(
        question=poll_question,
        description=poll_description,
        options=poll_options,
        vote_weight_method=vote_weight_method,
        vote_period=vote_period).run(
            sender=user2, level=20, now=sp.timestamp(200))

    # Check that the contract information has been updated
    poll = polls.get_poll(1)
    scenario.verify(poll.question == poll_question)
    scenario.verify(poll.description == poll_description)
    scenario.verify(sp.len(poll.options) == 3)
    scenario.verify(poll.options[0] == poll_options[0])
    scenario.verify(poll.options[7] == poll_options[7])
    scenario.verify(poll.options[9] == poll_options[9])
    scenario.verify(poll.vote_weight_method.is_variant("quadratic"))
    scenario.verify(poll.issuer == user2.address)
    scenario.verify(poll.timestamp == sp.timestamp(200))
    scenario.verify(poll.level == 20)
    scenario.verify(sp.len(poll.votes_count) == 3)
    scenario.verify(poll.votes_count[0] == 0)
    scenario.verify(poll.votes_count[7] == 0)
    scenario.verify(poll.votes_count[9] == 0)
    scenario.verify(polls.data.counter == 2)
    scenario.verify(polls.get_poll_count() == 2)


@sp.add_test(name="Test vote")
def test_vote():
    # Get the test environment
    testEnvironment = get_test_environment()
    scenario = testEnvironment["scenario"]
    user1 = testEnvironment["user1"]
    user2 = testEnvironment["user2"]
    user3 = testEnvironment["user3"]
    external_user = testEnvironment["external_user"]
    token = testEnvironment["token"]
    polls = testEnvironment["polls"]

    # User 1 creates a poll
    poll_question = sp.utils.bytes_of_string("Dummy question")
    poll_description = sp.utils.bytes_of_string("Dummy description")
    poll_options = {
        1: sp.utils.bytes_of_string("option 1"),
        2: sp.utils.bytes_of_string("option 2"),
        3: sp.utils.bytes_of_string("option 3")}
    vote_weight_method = sp.variant("linear", sp.unit)
    vote_period = 3
    polls.create_poll(
        question=poll_question,
        description=poll_description,
        options=poll_options,
        vote_weight_method=vote_weight_method,
        vote_period=vote_period).run(
            sender=user1, level=10, now=sp.timestamp(100))

    # Check that it's not possible to vote without DAO tokens
    polls.vote(poll_id=0, option=1, max_checkpoints=sp.none).run(
        valid=False, sender=external_user, now=sp.timestamp(200), level=20, exception="POLL_INSUFICIENT_BALANCE")

    # Check that it fails if a user selects the wrong poll or wrong option
    polls.vote(poll_id=1, option=1, max_checkpoints=sp.none).run(
        valid=False, sender=user1, now=sp.timestamp(200), level=20, exception="POLL_NONEXISTENT_POLL")
    polls.vote(poll_id=0, option=7, max_checkpoints=sp.none).run(
        valid=False, sender=user1, now=sp.timestamp(200), level=20, exception="POLL_WRONG_OPTION")

    # Check that it fails if the proposal voting period has finished
    polls.vote(poll_id=0, option=1, max_checkpoints=sp.none).run(
        valid=False, sender=user1, now=sp.timestamp(101).add_days(3), level=20, exception="POLL_CLOSED_POLL")

    # User 1 votes in the poll
    polls.vote(poll_id=0, option=1, max_checkpoints=sp.none).run(
        sender=user1, now=sp.timestamp(200), level=20)

    # Check that the contract information has been updated
    poll = polls.get_poll(0)
    vote = polls.get_vote(sp.record(poll_id=0, user=user1.address))
    scenario.verify(poll.votes_count[1] == 100)
    scenario.verify(poll.votes_count[2] == 0)
    scenario.verify(poll.votes_count[3] == 0)
    scenario.verify(vote.option == 1)
    scenario.verify(vote.weight == 100)
    scenario.verify(polls.has_voted(sp.record(poll_id=0, user=user1.address)))
    scenario.verify(~polls.has_voted(sp.record(poll_id=0, user=user2.address)))
    scenario.verify(~polls.has_voted(sp.record(poll_id=0, user=user3.address)))

    # User 2 votes in the poll
    polls.vote(poll_id=0, option=2, max_checkpoints=sp.none).run(
        sender=user2, now=sp.timestamp(300), level=30)

    # Check that the contract information has been updated
    poll = polls.get_poll(0)
    vote = polls.get_vote(sp.record(poll_id=0, user=user2.address))
    scenario.verify(poll.votes_count[1] == 100)
    scenario.verify(poll.votes_count[2] == 200)
    scenario.verify(poll.votes_count[3] == 0)
    scenario.verify(vote.option == 2)
    scenario.verify(vote.weight == 200)
    scenario.verify(polls.has_voted(sp.record(poll_id=0, user=user1.address)))
    scenario.verify(polls.has_voted(sp.record(poll_id=0, user=user2.address)))
    scenario.verify(~polls.has_voted(sp.record(poll_id=0, user=user3.address)))

    # User 1 changes their vote
    polls.vote(poll_id=0, option=3, max_checkpoints=sp.none).run(
        sender=user1, now=sp.timestamp(400), level=40)

    # Check that the contract information has been updated
    poll = polls.get_poll(0)
    vote = polls.get_vote(sp.record(poll_id=0, user=user1.address))
    scenario.verify(poll.votes_count[1] == 0)
    scenario.verify(poll.votes_count[2] == 200)
    scenario.verify(poll.votes_count[3] == 100)
    scenario.verify(vote.option == 3)
    scenario.verify(vote.weight == 100)
    scenario.verify(polls.has_voted(sp.record(poll_id=0, user=user1.address)))
    scenario.verify(polls.has_voted(sp.record(poll_id=0, user=user2.address)))
    scenario.verify(~polls.has_voted(sp.record(poll_id=0, user=user3.address)))

    # User 2 changes their vote
    polls.vote(poll_id=0, option=3, max_checkpoints=sp.none).run(
        sender=user2, now=sp.timestamp(500), level=50)

    # Check that the contract information has been updated
    poll = polls.get_poll(0)
    vote = polls.get_vote(sp.record(poll_id=0, user=user2.address))
    scenario.verify(poll.votes_count[1] == 0)
    scenario.verify(poll.votes_count[2] == 0)
    scenario.verify(poll.votes_count[3] == 300)
    scenario.verify(vote.option == 3)
    scenario.verify(vote.weight == 200)
    scenario.verify(polls.has_voted(sp.record(poll_id=0, user=user1.address)))
    scenario.verify(polls.has_voted(sp.record(poll_id=0, user=user2.address)))
    scenario.verify(~polls.has_voted(sp.record(poll_id=0, user=user3.address)))


@sp.add_test(name="Test quadratic vote")
def test_quadratic_vote():
    # Get the test environment
    decimals = 1000000
    testEnvironment = get_test_environment(decimals)
    scenario = testEnvironment["scenario"]
    user1 = testEnvironment["user1"]
    user2 = testEnvironment["user2"]
    user3 = testEnvironment["user3"]
    external_user = testEnvironment["external_user"]
    token = testEnvironment["token"]
    polls = testEnvironment["polls"]

    # User 1 creates a poll
    poll_question = sp.utils.bytes_of_string("Dummy question")
    poll_description = sp.utils.bytes_of_string("Dummy description")
    poll_options = {
        1: sp.utils.bytes_of_string("option 1"),
        2: sp.utils.bytes_of_string("option 2"),
        3: sp.utils.bytes_of_string("option 3")}
    vote_weight_method = sp.variant("quadratic", sp.unit)
    vote_period = 3
    polls.create_poll(
        question=poll_question,
        description=poll_description,
        options=poll_options,
        vote_weight_method=vote_weight_method,
        vote_period=vote_period).run(
            sender=user1, level=10, now=sp.timestamp(100))

    # User 1 votes in the poll
    polls.vote(poll_id=0, option=1, max_checkpoints=sp.none).run(
        sender=user1, now=sp.timestamp(200), level=20)

    # Check that the contract information has been updated
    poll = polls.get_poll(0)
    vote = polls.get_vote(sp.record(poll_id=0, user=user1.address))
    scenario.verify(poll.votes_count[1] == 100 * int(pow(100 * decimals / 10000, 0.5)))
    scenario.verify(poll.votes_count[2] == 0)
    scenario.verify(poll.votes_count[3] == 0)
    scenario.verify(vote.option == 1)
    scenario.verify(vote.weight == 100 * int(pow(100 * decimals / 10000, 0.5)))
    scenario.verify(polls.has_voted(sp.record(poll_id=0, user=user1.address)))
    scenario.verify(~polls.has_voted(sp.record(poll_id=0, user=user2.address)))
    scenario.verify(~polls.has_voted(sp.record(poll_id=0, user=user3.address)))

    # User 2 votes in the poll
    polls.vote(poll_id=0, option=2, max_checkpoints=sp.none).run(
        sender=user2, now=sp.timestamp(300), level=30)

    # Check that the contract information has been updated
    poll = polls.get_poll(0)
    vote = polls.get_vote(sp.record(poll_id=0, user=user2.address))
    scenario.verify(poll.votes_count[1] == 100 * int(pow(100 * decimals / 10000, 0.5)))
    scenario.verify(poll.votes_count[2] == 100 * int(pow(200 * decimals / 10000, 0.5)))
    scenario.verify(poll.votes_count[3] == 0)
    scenario.verify(vote.option == 2)
    scenario.verify(vote.weight == 100 * int(pow(200 * decimals / 10000, 0.5)))
    scenario.verify(polls.has_voted(sp.record(poll_id=0, user=user1.address)))
    scenario.verify(polls.has_voted(sp.record(poll_id=0, user=user2.address)))
    scenario.verify(~polls.has_voted(sp.record(poll_id=0, user=user3.address)))

    # User 1 changes their vote
    polls.vote(poll_id=0, option=3, max_checkpoints=sp.none).run(
        sender=user1, now=sp.timestamp(400), level=40)

    # Check that the contract information has been updated
    poll = polls.get_poll(0)
    vote = polls.get_vote(sp.record(poll_id=0, user=user1.address))
    scenario.verify(poll.votes_count[1] == 0)
    scenario.verify(poll.votes_count[2] == 100 * int(pow(200 * decimals / 10000, 0.5)))
    scenario.verify(poll.votes_count[3] == 100 * int(pow(100 * decimals / 10000, 0.5)))
    scenario.verify(vote.option == 3)
    scenario.verify(vote.weight == 100 * int(pow(100 * decimals / 10000, 0.5)))
    scenario.verify(polls.has_voted(sp.record(poll_id=0, user=user1.address)))
    scenario.verify(polls.has_voted(sp.record(poll_id=0, user=user2.address)))
    scenario.verify(~polls.has_voted(sp.record(poll_id=0, user=user3.address)))

    # User 2 changes their vote
    polls.vote(poll_id=0, option=3, max_checkpoints=sp.none).run(
        sender=user2, now=sp.timestamp(500), level=50)

    # Check that the contract information has been updated
    poll = polls.get_poll(0)
    vote = polls.get_vote(sp.record(poll_id=0, user=user2.address))
    scenario.verify(poll.votes_count[1] == 0)
    scenario.verify(poll.votes_count[2] == 0)
    scenario.verify(poll.votes_count[3] == 100 * int(pow(100 * decimals / 10000, 0.5)) + 100 * int(pow(200 * decimals / 10000, 0.5)))
    scenario.verify(vote.option == 3)
    scenario.verify(vote.weight == 100 * int(pow(200 * decimals / 10000, 0.5)))
    scenario.verify(polls.has_voted(sp.record(poll_id=0, user=user1.address)))
    scenario.verify(polls.has_voted(sp.record(poll_id=0, user=user2.address)))
    scenario.verify(~polls.has_voted(sp.record(poll_id=0, user=user3.address)))


@sp.add_test(name="Test equal vote")
def test_equal_vote():
    # Get the test environment
    testEnvironment = get_test_environment()
    scenario = testEnvironment["scenario"]
    user1 = testEnvironment["user1"]
    user2 = testEnvironment["user2"]
    user3 = testEnvironment["user3"]
    external_user = testEnvironment["external_user"]
    token = testEnvironment["token"]
    polls = testEnvironment["polls"]

    # User 1 creates a poll
    poll_question = sp.utils.bytes_of_string("Dummy question")
    poll_description = sp.utils.bytes_of_string("Dummy description")
    poll_options = {
        1: sp.utils.bytes_of_string("option 1"),
        2: sp.utils.bytes_of_string("option 2"),
        3: sp.utils.bytes_of_string("option 3")}
    vote_weight_method = sp.variant("equal", sp.unit)
    vote_period = 3
    polls.create_poll(
        question=poll_question,
        description=poll_description,
        options=poll_options,
        vote_weight_method=vote_weight_method,
        vote_period=vote_period).run(
            sender=user1, level=10, now=sp.timestamp(100))

    # User 1 votes in the poll
    polls.vote(poll_id=0, option=1, max_checkpoints=sp.none).run(
        sender=user1, now=sp.timestamp(200), level=20)

    # Check that the contract information has been updated
    poll = polls.get_poll(0)
    vote = polls.get_vote(sp.record(poll_id=0, user=user1.address))
    scenario.verify(poll.votes_count[1] == 1)
    scenario.verify(poll.votes_count[2] == 0)
    scenario.verify(poll.votes_count[3] == 0)
    scenario.verify(vote.option == 1)
    scenario.verify(vote.weight == 1)
    scenario.verify(polls.has_voted(sp.record(poll_id=0, user=user1.address)))
    scenario.verify(~polls.has_voted(sp.record(poll_id=0, user=user2.address)))
    scenario.verify(~polls.has_voted(sp.record(poll_id=0, user=user3.address)))

    # User 2 votes in the poll
    polls.vote(poll_id=0, option=2, max_checkpoints=sp.none).run(
        sender=user2, now=sp.timestamp(300), level=30)

    # Check that the contract information has been updated
    poll = polls.get_poll(0)
    vote = polls.get_vote(sp.record(poll_id=0, user=user2.address))
    scenario.verify(poll.votes_count[1] == 1)
    scenario.verify(poll.votes_count[2] == 1)
    scenario.verify(poll.votes_count[3] == 0)
    scenario.verify(vote.option == 2)
    scenario.verify(vote.weight == 1)
    scenario.verify(polls.has_voted(sp.record(poll_id=0, user=user1.address)))
    scenario.verify(polls.has_voted(sp.record(poll_id=0, user=user2.address)))
    scenario.verify(~polls.has_voted(sp.record(poll_id=0, user=user3.address)))

    # User 1 changes their vote
    polls.vote(poll_id=0, option=3, max_checkpoints=sp.none).run(
        sender=user1, now=sp.timestamp(400), level=40)

    # Check that the contract information has been updated
    poll = polls.get_poll(0)
    vote = polls.get_vote(sp.record(poll_id=0, user=user1.address))
    scenario.verify(poll.votes_count[1] == 0)
    scenario.verify(poll.votes_count[2] == 1)
    scenario.verify(poll.votes_count[3] == 1)
    scenario.verify(vote.option == 3)
    scenario.verify(vote.weight == 1)
    scenario.verify(polls.has_voted(sp.record(poll_id=0, user=user1.address)))
    scenario.verify(polls.has_voted(sp.record(poll_id=0, user=user2.address)))
    scenario.verify(~polls.has_voted(sp.record(poll_id=0, user=user3.address)))

    # User 2 changes their vote
    polls.vote(poll_id=0, option=3, max_checkpoints=sp.none).run(
        sender=user2, now=sp.timestamp(500), level=50)

    # Check that the contract information has been updated
    poll = polls.get_poll(0)
    vote = polls.get_vote(sp.record(poll_id=0, user=user2.address))
    scenario.verify(poll.votes_count[1] == 0)
    scenario.verify(poll.votes_count[2] == 0)
    scenario.verify(poll.votes_count[3] == 2)
    scenario.verify(vote.option == 3)
    scenario.verify(vote.weight == 1)
    scenario.verify(polls.has_voted(sp.record(poll_id=0, user=user1.address)))
    scenario.verify(polls.has_voted(sp.record(poll_id=0, user=user2.address)))
    scenario.verify(~polls.has_voted(sp.record(poll_id=0, user=user3.address)))


@sp.add_test(name="Test integer square root")
def test_integer_square_root():
    # Get the test environment
    testEnvironment = get_test_environment()
    scenario = testEnvironment["scenario"]
    polls = testEnvironment["polls"]

    polls.get_integer_square_root(0)
    scenario.verify(polls.data.counter == 0)

    polls.get_integer_square_root(1)
    scenario.verify(polls.data.counter == 1)

    polls.get_integer_square_root(3)
    scenario.verify(polls.data.counter == 1)

    polls.get_integer_square_root(4)
    scenario.verify(polls.data.counter == 2)

    polls.get_integer_square_root(8)
    scenario.verify(polls.data.counter == 2)

    polls.get_integer_square_root(9)
    scenario.verify(polls.data.counter == 3)

    polls.get_integer_square_root(10)
    scenario.verify(polls.data.counter == 3)

    polls.get_integer_square_root(12345 * 12345 - 1)
    scenario.verify(polls.data.counter == 12344)

    polls.get_integer_square_root(12345 * 12345)
    scenario.verify(polls.data.counter == 12345)

    polls.get_integer_square_root(12345 * 12345 + 1)
    scenario.verify(polls.data.counter == 12345)
