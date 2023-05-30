"""Unit tests for the Representatives contract class.

"""

import smartpy as sp

# Import the representatives and fa2 contract modules
representativesModule = sp.io.import_script_from_url("file:contracts/representatives.py")
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


class Dummy(sp.Contract):
    """This is a dummy contract to be used only for test purposes.

    """

    def __init__(self):
        """Initializes the contract.

        """
        self.init(x=sp.nat(0), y=sp.nat(0))

    @sp.entry_point
    def update_x(self, x):
        """Updates the x value.

        """
        self.data.x = x

    @sp.entry_point
    def update_y(self, y):
        """Updates the y value.

        """
        self.data.y = y


def get_test_environment():
    # Initialize the test scenario
    scenario = sp.test_scenario()

    # Create the test accounts
    representative1 = sp.test_account("representative1")
    representative2 = sp.test_account("representative2")
    representative3 = sp.test_account("representative3")
    representative4 = sp.test_account("representative4")
    non_representative = sp.test_account("non_representative")

    # Initialize the representatives contract
    representatives = representativesModule.Representatives(
        metadata=sp.utils.metadata_of_url("ipfs://aaa"),
        representatives={
            representative1.address: "community1",
            representative2.address: "community2",
            representative3.address: "community3",
            representative4.address: "community4"},
        minimum_votes=3,
        expiration_time=3)
    representatives.set_initial_balance(sp.tez(10))
    scenario += representatives

    # Save all the variables in a test environment dictionary
    testEnvironment = {
        "scenario": scenario,
        "representative1": representative1,
        "representative2": representative2,
        "representative3": representative3,
        "representative4": representative4,
        "non_representative": non_representative,
        "representatives": representatives}

    return testEnvironment


@sp.add_test(name="Test default entripoint")
def test_default_entripoint():
    # Get the test environment
    testEnvironment = get_test_environment()
    scenario = testEnvironment["scenario"]
    representative1 = testEnvironment["representative1"]
    non_representative = testEnvironment["non_representative"]
    representatives = testEnvironment["representatives"]

    # Check that representatives can send tez to the contract
    representatives.default(sp.unit).run(sender=representative1, amount=sp.tez(3))

    # Check that the tez are now part of the contract balance
    scenario.verify(representatives.balance == sp.tez(10 + 3))

    # Check that non-representatives can also send tez to the contract
    representatives.default(sp.unit).run(sender=non_representative, amount=sp.tez(5))

    # Check that the tez have been added to the contract balance
    scenario.verify(representatives.balance == sp.tez(10 + 3 + 5))


@sp.add_test(name="Test create vote and execute proposal")
def test_create_vote_and_execute_proposal():
    # Get the test environment
    testEnvironment = get_test_environment()
    scenario = testEnvironment["scenario"]
    representative1 = testEnvironment["representative1"]
    representative2 = testEnvironment["representative2"]
    representative3 = testEnvironment["representative3"]
    representative4 = testEnvironment["representative4"]
    non_representative = testEnvironment["non_representative"]
    representatives = testEnvironment["representatives"]

    # Check that we have the expected representatives
    scenario.verify(representatives.data.representatives[representative1.address] == "community1")
    scenario.verify(representatives.data.representatives[representative2.address] == "community2")
    scenario.verify(representatives.data.representatives[representative3.address] == "community3")
    scenario.verify(representatives.data.representatives[representative4.address] == "community4")
    scenario.verify(representatives.get_representative_community(representative1.address) == "community1")
    scenario.verify(representatives.get_representative_community(representative2.address) == "community2")
    scenario.verify(representatives.get_representative_community(representative3.address) == "community3")
    scenario.verify(representatives.get_representative_community(representative4.address) == "community4")
    scenario.verify(~representatives.data.representatives.contains(non_representative.address))
    scenario.verify(sp.len(representatives.data.representatives) == 4)

    # Check that we have the expected communities
    scenario.verify(representatives.data.communities.contains("community1"))
    scenario.verify(representatives.data.communities.contains("community2"))
    scenario.verify(representatives.data.communities.contains("community3"))
    scenario.verify(representatives.data.communities.contains("community4"))
    scenario.verify(sp.len(representatives.data.communities.elements()) == 4)

    # Check that we start with zero proposals
    scenario.verify(representatives.data.counter == 0)

    # Check that only representatives can submit proposals
    new_representative = sp.record(
        address=non_representative.address,
        community="community5")
    representatives.add_proposal(sp.variant("add_representative", new_representative)).run(
        valid=False, sender=non_representative, exception="REPS_NOT_REPRESENTATIVE")

    # Create the add representative proposal with one of the representatives
    representatives.add_proposal(sp.variant("add_representative", new_representative)).run(
        sender=representative1)

    # Check that the proposal has been added to the proposals big map
    scenario.verify(representatives.data.proposals.contains(0))
    scenario.verify(representatives.data.counter == 1)
    scenario.verify(representatives.data.proposals[0].issuer.address == representative1.address)
    scenario.verify(representatives.data.proposals[0].issuer.community == "community1")
    scenario.verify(representatives.data.proposals[0].timestamp == sp.timestamp(0))
    scenario.verify(~representatives.data.proposals[0].executed)
    scenario.verify(representatives.data.proposals[0].positive_votes == 0)

    # The first 3 representatives vote the proposal
    representatives.vote_proposal(proposal_id=0, approval=True).run(sender=representative1)
    representatives.vote_proposal(proposal_id=0, approval=True).run(sender=representative2)
    representatives.vote_proposal(proposal_id=0, approval=False).run(sender=representative3)

    # Check that the non-representative cannot vote the proposal
    representatives.vote_proposal(proposal_id=0, approval=True).run(
        valid=False, sender=non_representative, exception="REPS_NOT_REPRESENTATIVE")

    # Check that the votes have been added to the votes big map
    scenario.verify(representatives.data.votes[(0, "community1")] == True)
    scenario.verify(representatives.data.votes[(0, "community2")] == True)
    scenario.verify(representatives.data.votes[(0, "community3")] == False)
    scenario.verify(representatives.data.proposals[0].positive_votes == 2)
    scenario.verify(~representatives.data.proposals[0].executed)

    # The second representative changes their vote
    representatives.vote_proposal(proposal_id=0, approval=False).run(sender=representative2)

    # Check that the votes have been updated
    scenario.verify(representatives.data.votes[(0, "community2")] == False)
    scenario.verify(representatives.data.proposals[0].positive_votes == 1)

    # The third representative also changes their vote
    representatives.vote_proposal(proposal_id=0, approval=True).run(sender=representative3)

    # Check that the votes have been updated
    scenario.verify(representatives.data.votes[(0, "community3")] == True)
    scenario.verify(representatives.data.proposals[0].positive_votes == 2)

    # Check that voting twice positive only counts as one vote
    representatives.vote_proposal(proposal_id=0, approval=True).run(sender=representative3)
    scenario.verify(representatives.data.proposals[0].positive_votes == 2)

    # Check that voting twice negative doesn't modify the result
    representatives.vote_proposal(proposal_id=0, approval=False).run(sender=representative2)
    scenario.verify(representatives.data.proposals[0].positive_votes == 2)

    # Check that the proposal cannot be executed because it doesn't have enough positive votes
    representatives.execute_proposal(0).run(
        valid=False, sender=representative1, exception="REPS_NOT_EXECUTABLE")

    # The 4th representative votes positive
    representatives.vote_proposal(proposal_id=0, approval=True).run(sender=representative4)

    # Check that the vote has been added
    scenario.verify(representatives.data.votes[(0, "community4")] == True)
    scenario.verify(representatives.data.proposals[0].positive_votes == 3)
    scenario.verify(~representatives.data.proposals[0].executed)

    # Check that the proposal can only be executed by one of the representatives
    representatives.execute_proposal(0).run(
        valid=False, sender=non_representative, exception="REPS_NOT_REPRESENTATIVE")

    # Execute the proposal with one of the representatives
    representatives.execute_proposal(0).run(sender=representative3)

    # Check that the proposal is listed as executed
    scenario.verify(representatives.data.proposals[0].executed)

    # Check that the proposal cannot be voted or executed anymore
    representatives.vote_proposal(proposal_id=0, approval=True).run(
        valid=False, sender=representative1, exception="REPS_EXECUTED_PROPOSAL")
    representatives.execute_proposal(0).run(
        valid=False, sender=representative1, exception="REPS_EXECUTED_PROPOSAL")

    # Check that the new representative can create a new proposal and vote it
    old_representative = sp.record(
        address=representative1.address,
        community="community1")
    representatives.add_proposal(sp.variant("remove_representative", old_representative)).run(
        sender=non_representative)
    representatives.vote_proposal(proposal_id=1, approval=True).run(sender=non_representative)

    # Check that the proposal and vote have been added to the big maps
    scenario.verify(representatives.data.proposals.contains(1))
    scenario.verify(representatives.data.counter == 2)
    scenario.verify(representatives.data.proposals[1].issuer.address == new_representative.address)
    scenario.verify(representatives.data.proposals[1].issuer.community == new_representative.community)
    scenario.verify(~representatives.data.proposals[1].executed)
    scenario.verify(representatives.data.proposals[1].positive_votes == 1)
    scenario.verify(representatives.data.votes[(1, "community5")] == True)

    # The other representatives vote the proposal
    representatives.vote_proposal(proposal_id=1, approval=True).run(sender=representative1)
    representatives.vote_proposal(proposal_id=1, approval=True).run(sender=representative2)
    representatives.vote_proposal(proposal_id=1, approval=True).run(sender=representative3)
    representatives.vote_proposal(proposal_id=1, approval=True).run(sender=representative4)

    # Check that is not possible to vote or execute the proposal when it has expired
    representatives.vote_proposal(proposal_id=1, approval=False).run(
        valid=False, sender=representative1, now=sp.timestamp(1).add_days(3), exception="REPS_EXPIRED_PROPOSAL")
    representatives.execute_proposal(1).run(
        valid=False, sender=representative1, now=sp.timestamp(1).add_days(3), exception="REPS_EXPIRED_PROPOSAL")


@sp.add_test(name="Test text proposal")
def test_text_proposal():
    # Get the test environment
    testEnvironment = get_test_environment()
    scenario = testEnvironment["scenario"]
    representative1 = testEnvironment["representative1"]
    representative2 = testEnvironment["representative2"]
    representative3 = testEnvironment["representative3"]
    representative4 = testEnvironment["representative4"]
    representatives = testEnvironment["representatives"]

    # Add a text proposal
    text = sp.utils.bytes_of_string("ipfs://zzz")
    representatives.add_proposal(sp.variant("text", text)).run(sender=representative1)

    # Vote for the proposal
    representatives.vote_proposal(proposal_id=0, approval=True).run(sender=representative1)
    representatives.vote_proposal(proposal_id=0, approval=False).run(sender=representative2)
    representatives.vote_proposal(proposal_id=0, approval=True).run(sender=representative3)
    representatives.vote_proposal(proposal_id=0, approval=True).run(sender=representative4)

    # Execute the proposal
    representatives.execute_proposal(0).run(sender=representative3)

    # Check that the proposal is listed as executed
    scenario.verify(representatives.data.proposals[0].executed)


@sp.add_test(name="Test transter mutez proposal")
def test_transfer_mutez_proposal():
    # Get the test environment
    testEnvironment = get_test_environment()
    scenario = testEnvironment["scenario"]
    representative1 = testEnvironment["representative1"]
    representative2 = testEnvironment["representative2"]
    representative3 = testEnvironment["representative3"]
    representative4 = testEnvironment["representative4"]
    representatives = testEnvironment["representatives"]

    # Create the accounts that will receive the tez transfers and add the to
    # the scenario
    recipient1 = Recipient()
    recipient2 = Recipient()
    scenario += recipient1
    scenario += recipient2

    # Add a transfer tez proposal
    mutez_transfers = sp.list([
        sp.record(amount=sp.tez(3), destination=recipient1.address),
        sp.record(amount=sp.tez(2), destination=recipient2.address)])
    representatives.add_proposal(sp.variant("transfer_mutez", mutez_transfers)).run(sender=representative1)

    # Vote for the proposal
    representatives.vote_proposal(proposal_id=0, approval=True).run(sender=representative1)
    representatives.vote_proposal(proposal_id=0, approval=False).run(sender=representative2)
    representatives.vote_proposal(proposal_id=0, approval=True).run(sender=representative3)
    representatives.vote_proposal(proposal_id=0, approval=True).run(sender=representative4)

    # Execute the proposal
    representatives.execute_proposal(0).run(sender=representative3)

    # Check that the proposal is listed as executed
    scenario.verify(representatives.data.proposals[0].executed)

    # Check that the contract balance is correct
    scenario.verify(representatives.balance == sp.tez(10 - 3 - 2))

    # Check that the tez amounts have been sent to the correct destinations
    scenario.verify(recipient1.balance == sp.tez(3))
    scenario.verify(recipient2.balance == sp.tez(2))


@sp.add_test(name="Test transter token proposal")
def test_transfer_token_proposal():
    # Get the test environment
    testEnvironment = get_test_environment()
    scenario = testEnvironment["scenario"]
    representative1 = testEnvironment["representative1"]
    representative2 = testEnvironment["representative2"]
    representative3 = testEnvironment["representative3"]
    representative4 = testEnvironment["representative4"]
    representatives = testEnvironment["representatives"]

    # Create the FA2 token contract and add it to the test scenario
    admin = sp.test_account("admin")
    fa2 = fa2Module.FA2(
        config=fa2Module.FA2_config(),
        admin=admin.address,
        meta=sp.utils.metadata_of_url("ipfs://aaa"))
    scenario += fa2

    # Mint one token
    fa2.mint(
        address=representative1.address,
        token_id=sp.nat(0),
        amount=sp.nat(100),
        token_info={"": sp.utils.bytes_of_string("ipfs://bbb")}).run(sender=admin)

    # The first representative transfers 20 editions of the token to the representatives
    fa2.transfer(sp.list([sp.record(
        from_=representative1.address,
        txs=sp.list([sp.record(
            to_=representatives.address,
            token_id=0,
            amount=20)]))])).run(sender=representative1)

    # Check that the token ledger information is correct
    scenario.verify(fa2.data.ledger[(representative1.address, 0)].balance == 100 - 20)
    scenario.verify(fa2.data.ledger[(representatives.address, 0)].balance == 20)

    # Create the accounts that will receive the token transfers
    receptor1 = sp.test_account("receptor1")
    receptor2 = sp.test_account("receptor2")

    # Add a transfer token proposal
    token_transfers = sp.record(
        fa2=fa2.address,
        token_id=sp.nat(0),
        distribution=sp.list([
            sp.record(amount=sp.nat(5), destination=receptor1.address),
            sp.record(amount=sp.nat(1), destination=receptor2.address)]))
    representatives.add_proposal(sp.variant("transfer_token", token_transfers)).run(sender=representative3)

    # Vote for the proposal
    representatives.vote_proposal(proposal_id=0, approval=True).run(sender=representative1)
    representatives.vote_proposal(proposal_id=0, approval=False).run(sender=representative2)
    representatives.vote_proposal(proposal_id=0, approval=True).run(sender=representative3)
    representatives.vote_proposal(proposal_id=0, approval=True).run(sender=representative4)

    # Execute the proposal
    representatives.execute_proposal(0).run(sender=representative3)

    # Check that the proposal is listed as executed
    scenario.verify(representatives.data.proposals[0].executed)

    # Check that the token ledger information is correct
    scenario.verify(fa2.data.ledger[(representative1.address, 0)].balance == 100 - 20)
    scenario.verify(fa2.data.ledger[(representatives.address, 0)].balance == 20 - 5 - 1)
    scenario.verify(fa2.data.ledger[(receptor1.address, 0)].balance == 5)
    scenario.verify(fa2.data.ledger[(receptor2.address, 0)].balance == 1)


@sp.add_test(name="Test lambda function proposal")
def test_lambda_function_proposal():
    # Get the test environment
    testEnvironment = get_test_environment()
    scenario = testEnvironment["scenario"]
    representative1 = testEnvironment["representative1"]
    representative2 = testEnvironment["representative2"]
    representative3 = testEnvironment["representative3"]
    representative4 = testEnvironment["representative4"]
    representatives = testEnvironment["representatives"]

    # Initialize the dummy contract and add it to the test scenario
    dummyContract = Dummy()
    scenario += dummyContract

    # Define the lambda function that will update the dummy contract
    def dummy_lambda_function(params):
        sp.set_type(params, sp.TUnit)
        dummyContractHandle = sp.contract(sp.TNat, dummyContract.address, "update_x").open_some()
        sp.result([sp.transfer_operation(sp.nat(2), sp.mutez(0), dummyContractHandle)])

    # Add a lambda proposal
    representatives.add_proposal(sp.variant("lambda_function", dummy_lambda_function)).run(sender=representative4)

    # Vote for the proposal
    representatives.vote_proposal(proposal_id=0, approval=True).run(sender=representative1)
    representatives.vote_proposal(proposal_id=0, approval=False).run(sender=representative2)
    representatives.vote_proposal(proposal_id=0, approval=True).run(sender=representative3)
    representatives.vote_proposal(proposal_id=0, approval=True).run(sender=representative4)

    # Execute the proposal
    representatives.execute_proposal(0).run(sender=representative3)

    # Check that the dummy contract storage has been updated to the correct vale
    scenario.verify(dummyContract.data.x == 2)
    scenario.verify(dummyContract.data.y == 0)


@sp.add_test(name="Test add representative proposal")
def test_add_representative_proposal():
    # Get the test environment
    testEnvironment = get_test_environment()
    scenario = testEnvironment["scenario"]
    representative1 = testEnvironment["representative1"]
    representative2 = testEnvironment["representative2"]
    representative3 = testEnvironment["representative3"]
    representative4 = testEnvironment["representative4"]
    representatives = testEnvironment["representatives"]

    # Create the new representative account
    representative5 = sp.test_account("representative5")

    # Check that it's not possible to add the same representative twice
    new_representative = sp.record(
        address=representative1.address,
        community="community1")
    representatives.add_proposal(sp.variant("add_representative", new_representative)).run(
        valid=False, sender=representative4, exception="REPS_ADDRESS_EXISTS")
    new_representative = sp.record(
        address=representative5.address,
        community="community1")
    representatives.add_proposal(sp.variant("add_representative", new_representative)).run(
        valid=False, sender=representative4, exception="REPS_COMMUNITY_EXISTS")

    # Add a add representative proposal
    new_representative = sp.record(
        address=representative5.address,
        community="community5")
    representatives.add_proposal(sp.variant("add_representative", new_representative)).run(sender=representative4)

    # Vote for the proposal
    representatives.vote_proposal(proposal_id=0, approval=True).run(sender=representative1)
    representatives.vote_proposal(proposal_id=0, approval=False).run(sender=representative2)
    representatives.vote_proposal(proposal_id=0, approval=True).run(sender=representative3)
    representatives.vote_proposal(proposal_id=0, approval=True).run(sender=representative4)

    # Execute the proposal
    representatives.execute_proposal(0).run(sender=representative3)

    # Check that now there are 5 representatives
    scenario.verify(sp.len(representatives.data.representatives) == 5)
    scenario.verify(representatives.data.representatives[representative5.address] == "community5")
    scenario.verify(representatives.data.communities.contains("community5"))


@sp.add_test(name="Test remove representative proposal")
def test_remove_representative_proposal():
    # Get the test environment
    testEnvironment = get_test_environment()
    scenario = testEnvironment["scenario"]
    representative1 = testEnvironment["representative1"]
    representative2 = testEnvironment["representative2"]
    representative3 = testEnvironment["representative3"]
    representative4 = testEnvironment["representative4"]
    representatives = testEnvironment["representatives"]

    # Create the new representative account
    representative5 = sp.test_account("representative5")

    # Check that it's not possible to remove a representative that is not in the representatives
    old_representative = sp.record(
        address=representative5.address,
        community="community5")
    representatives.add_proposal(sp.variant("remove_representative", old_representative)).run(
        valid=False, sender=representative4, exception="REPS_WRONG_ADDRESS")
    old_representative = sp.record(
        address=representative1.address,
        community="community2")
    representatives.add_proposal(sp.variant("remove_representative", old_representative)).run(
        valid=False, sender=representative4, exception="REPS_WRONG_COMMUNITY")

    # Add a remove representative proposal
    old_representative = sp.record(
        address=representative2.address,
        community="community2")
    representatives.add_proposal(sp.variant("remove_representative", old_representative)).run(sender=representative4)

    # Vote for the proposal
    representatives.vote_proposal(proposal_id=0, approval=True).run(sender=representative1)
    representatives.vote_proposal(proposal_id=0, approval=False).run(sender=representative2)
    representatives.vote_proposal(proposal_id=0, approval=True).run(sender=representative3)
    representatives.vote_proposal(proposal_id=0, approval=True).run(sender=representative4)

    # Execute the proposal
    representatives.execute_proposal(0).run(sender=representative3)

    # Check that now there are 3 representatives
    scenario.verify(sp.len(representatives.data.representatives) == 3)
    scenario.verify(~representatives.data.representatives.contains(representative2.address))
    scenario.verify(~representatives.data.communities.contains("community2"))


@sp.add_test(name="Test minimum votes proposal")
def test_minimum_votes_proposal():
    # Get the test environment
    testEnvironment = get_test_environment()
    scenario = testEnvironment["scenario"]
    representative1 = testEnvironment["representative1"]
    representative2 = testEnvironment["representative2"]
    representative3 = testEnvironment["representative3"]
    representative4 = testEnvironment["representative4"]
    representatives = testEnvironment["representatives"]

    # Check that the minimum votes cannot be set to 0
    representatives.add_proposal(sp.variant("minimum_votes", 0)).run(
        valid=False, sender=representative4, exception="REPS_WRONG_MINIMUM_VOTES")

    # Add a minimum votes proposal
    representatives.add_proposal(sp.variant("minimum_votes", 4)).run(sender=representative4)

    # Vote for the proposal
    representatives.vote_proposal(proposal_id=0, approval=True).run(sender=representative1)
    representatives.vote_proposal(proposal_id=0, approval=False).run(sender=representative2)
    representatives.vote_proposal(proposal_id=0, approval=True).run(sender=representative3)
    representatives.vote_proposal(proposal_id=0, approval=True).run(sender=representative4)

    # Execute the proposal
    representatives.execute_proposal(0).run(sender=representative3)

    # Check that the minimum votes parameter has been updated
    scenario.verify(representatives.data.minimum_votes == 4)

    # Propose a minimum votes proposal larger than the number of representatives
    representatives.add_proposal(sp.variant("minimum_votes", 10)).run(sender=representative4)

    # Vote for the proposal
    representatives.vote_proposal(proposal_id=1, approval=True).run(sender=representative1)
    representatives.vote_proposal(proposal_id=1, approval=True).run(sender=representative2)
    representatives.vote_proposal(proposal_id=1, approval=True).run(sender=representative3)
    representatives.vote_proposal(proposal_id=1, approval=True).run(sender=representative4)

    # Check that the proposal can't be executed because the number of representatives is smaller
    # than the proposed minimum votes
    representatives.execute_proposal(1).run(
        valid=False, sender=representative3, exception="REPS_WRONG_MINIMUM_VOTES")

    # Add a remove representative proposal
    old_representative = sp.record(
        address=representative1.address,
        community="community1")
    representatives.add_proposal(sp.variant("remove_representative", old_representative)).run(sender=representative4)

    # Vote for the proposal
    representatives.vote_proposal(proposal_id=2, approval=True).run(sender=representative1)
    representatives.vote_proposal(proposal_id=2, approval=True).run(sender=representative2)
    representatives.vote_proposal(proposal_id=2, approval=True).run(sender=representative3)
    representatives.vote_proposal(proposal_id=2, approval=True).run(sender=representative4)

    # Execute the proposal
    representatives.execute_proposal(2).run(sender=representative3)

    # Check that the minimum votes parameter has been updated
    scenario.verify(representatives.data.minimum_votes == 3)


@sp.add_test(name="Test expiration time proposal")
def test_expiration_time_proposal():
    # Get the test environment
    testEnvironment = get_test_environment()
    scenario = testEnvironment["scenario"]
    representative1 = testEnvironment["representative1"]
    representative2 = testEnvironment["representative2"]
    representative3 = testEnvironment["representative3"]
    representative4 = testEnvironment["representative4"]
    representatives = testEnvironment["representatives"]

    # Check that the expiration time cannot be set to 0
    representatives.add_proposal(sp.variant("expiration_time", 0)).run(
        valid=False, sender=representative4, exception="REPS_WRONG_EXPIRATION_TIME")

    # Add an expiration time proposal
    representatives.add_proposal(sp.variant("expiration_time", 100)).run(sender=representative4)

    # Vote for the proposal
    representatives.vote_proposal(proposal_id=0, approval=True).run(sender=representative1)
    representatives.vote_proposal(proposal_id=0, approval=False).run(sender=representative2)
    representatives.vote_proposal(proposal_id=0, approval=True).run(sender=representative3)
    representatives.vote_proposal(proposal_id=0, approval=True).run(sender=representative4)

    # Execute the proposal
    representatives.execute_proposal(0).run(sender=representative3)

    # Check that the expiration time parameter has been updated
    scenario.verify(representatives.data.expiration_time == 100)


@sp.add_test(name="Test update representative address")
def test_update_representative_address():
    # Get the test environment
    testEnvironment = get_test_environment()
    scenario = testEnvironment["scenario"]
    representative1 = testEnvironment["representative1"]
    representative2 = testEnvironment["representative2"]
    representative3 = testEnvironment["representative3"]
    representative4 = testEnvironment["representative4"]
    non_representative = testEnvironment["non_representative"]
    representatives = testEnvironment["representatives"]

    # Check that only a representative can change the representative address
    representatives.update_representative_address(non_representative.address).run(
        valid=False, sender=non_representative, exception="REPS_NOT_REPRESENTATIVE")
    representatives.update_representative_address(non_representative.address).run(
        sender=representative1)

    # Check that the representative address has been updated
    scenario.verify(representatives.data.representatives[non_representative.address] == "community1")
    scenario.verify(representatives.data.representatives[representative2.address] == "community2")
    scenario.verify(representatives.data.representatives[representative3.address] == "community3")
    scenario.verify(representatives.data.representatives[representative4.address] == "community4")
    scenario.verify(representatives.get_representative_community(non_representative.address) == "community1")
    scenario.verify(representatives.get_representative_community(representative2.address) == "community2")
    scenario.verify(representatives.get_representative_community(representative3.address) == "community3")
    scenario.verify(representatives.get_representative_community(representative4.address) == "community4")
    scenario.verify(~representatives.data.representatives.contains(representative1.address))
    scenario.verify(sp.len(representatives.data.representatives) == 4)
