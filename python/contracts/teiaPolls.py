"""A smart contract where Teia DAO members can create polls and vote in them.

"""

import smartpy as sp


class TeiaPolls(sp.Contract):
    """This contract can be used to create polls that can be voted by any Teia
    DAO member.

    """

    VOTE_WEIGHT_METHOD_TYPE = sp.TVariant(
        # Linear/proportional weight: vote weight = DAO token amount
        linear=sp.TUnit,
        # Quadratic weight: vote weight = sqrt(DAO token amount)
        quadratic=sp.TUnit,
        # Equal weight: all votes count the same
        equal=sp.TUnit)

    POLL_TYPE = sp.TRecord(
        # The poll question
        question=sp.TBytes,
        # The poll description
        description=sp.TBytes,
        # The poll voting options
        options=sp.TMap(sp.TNat, sp.TBytes),
        # The poll vote weight method
        vote_weight_method=VOTE_WEIGHT_METHOD_TYPE,
        # The poll vote period in days
        vote_period=sp.TNat,
        # The user that submitted the poll
        issuer=sp.TAddress,
        # The time when the poll was submitted
        timestamp=sp.TTimestamp,
        # The block level when the poll was submitted
        level=sp.TNat,
        # The total number of votes for each poll option
        votes_count=sp.TMap(sp.TNat, sp.TNat)).layout(
            ("question", ("description", ("options", ("vote_weight_method", ("vote_period", ("issuer", ("timestamp", ("level", "votes_count")))))))))

    VOTE_TYPE = sp.TRecord(
        # The poll option voted by the user
        option=sp.TNat,
        # The user vote weight
        weight=sp.TNat).layout(
            ("option", "weight"))

    def __init__(self, metadata, token):
        """Initializes the contract.

        """
        # Define the contract storage data types for clarity
        self.init_type(sp.TRecord(
            # The contract metadata
            metadata=sp.TBigMap(sp.TString, sp.TBytes),
            # The DAO token contract address
            token=sp.TAddress,
            # The big map with the polls information
            polls=sp.TBigMap(sp.TNat, TeiaPolls.POLL_TYPE),
            # The big map with the votes information
            votes=sp.TBigMap(
                sp.TPair(sp.TNat, sp.TAddress), TeiaPolls.VOTE_TYPE),
            # The polls counter
            counter=sp.TNat))

        # Initialize the contract storage
        self.init(
            metadata=metadata,
            token=token,
            polls=sp.big_map(),
            votes=sp.big_map(),
            counter=0)

        # Fill the contract metadata
        self.contract_metadata = {
            "name": "Teia multi-option polls contract",
            "description": "Multi-option polls contract used for the Teia DAO",
            "version": "1.0.0",
            "authors": ["Teia Community <https://twitter.com/TeiaCommunity>"],
            "homepage": "https://teia.art",
            "source": {
                "tools": ["SmartPy 0.16.0"],
                "location": "https://github.com/teia-community/teia-smart-contracts/blob/main/python/contracts/teiaPolls.py"
            },
            "license": {
                "name": "MIT",
                "details": "The MIT License"
            },
            "interfaces": ["TZIP-016"],
            "errors": [ {"error": {"string": "POLL_NOT_DAO_MEMBER"},
                         "expansion": {"string": "The account that executed the entry point is not a DAO token holder"},
                         "languages": ["en"]},
                        {"error": {"string": "POLL_WRONG_OPTIONS"},
                         "expansion": {"string": "There must be at least two options to vote in the poll"},
                         "languages": ["en"]},
                        {"error": {"string": "POLL_WRONG_VOTE_PERIOD"},
                         "expansion": {"string": "The poll voting period should be between 1 and 30 days"},
                         "languages": ["en"]},
                        {"error": {"string": "POLL_NONEXISTENT_POLL"},
                         "expansion": {"string": "There is no poll with the given id"},
                         "languages": ["en"]},
                        {"error": {"string": "POLL_WRONG_OPTION"},
                         "expansion": {"string": "The poll doesn't have the provided vote option"},
                         "languages": ["en"]},
                        {"error": {"string": "POLL_CLOSED_POLL"},
                         "expansion": {"string": "The poll voting period has passed and it is not possible to vote it anymore"},
                         "languages": ["en"]},
                        {"error": {"string": "POLL_INSUFICIENT_BALANCE"},
                         "expansion": {"string": "The account that executed the entry point does not have enough DAO tokens to vote the poll"},
                         "languages": ["en"]},
                        {"error": {"string": "POLL_NO_USER_VOTE"},
                         "expansion": {"string": "The user didn't vote for the given poll yet"},
                         "languages": ["en"]}]}
        self.init_metadata("contract_metadata", self.contract_metadata)

    def check_is_dao_member(self):
        """Checks that the address that called the entry point is from one of
        the DAO members.

        """
        # Get the sender token balance
        params = sp.set_type_expr(
            sp.record(
                owner=sp.sender,
                token_id=sp.nat(0)),
            sp.TRecord(
                owner=sp.TAddress,
                token_id=sp.TNat).layout(
                    ("owner", "token_id")))
        token_balance = sp.view(
            name="get_balance",
            address=self.data.token,
            param=params,
            t=sp.TNat).open_some()

        # Check that the token balance is not zero
        sp.verify(token_balance > 0, message="POLL_NOT_DAO_MEMBER")

    def get_prior_token_balance(self, level, max_checkpoints):
        """Gets the sender prior token balance calling the DAO token on-chain
        view.

        """
        params = sp.set_type_expr(
            sp.record(
                owner=sp.sender,
                level=level,
                max_checkpoints=max_checkpoints),
            sp.TRecord(
                owner=sp.TAddress,
                level=sp.TNat,
                max_checkpoints=sp.TOption(sp.TNat)).layout(
                    ("owner", ("level", "max_checkpoints"))))

        return sp.view(
            name="get_prior_balance",
            address=self.data.token,
            param=params,
            t=sp.TNat).open_some()

    @sp.private_lambda(with_storage=None, with_operations=False, wrap_call=True)
    def integer_square_root(self, number):
        """Calculates the integer square root of a number using Newton's method.

        https://en.wikipedia.org/wiki/Integer_square_root

        """
        x0 = sp.local("x0", number // 2)

        with sp.if_(x0.value != 0):
            x1 = sp.local("x1", (x0.value + number // x0.value) // 2)

            with sp.while_(x1.value < x0.value):
                x0.value = x1.value
                x1.value = (x0.value + number // x0.value) // 2

            sp.result(x0.value)
        with sp.else_():
            sp.result(number)

    @sp.entry_point
    def create_poll(self, params):
        """Adds a new poll to the polls big map.

        """
        # Define the input parameter data type
        sp.set_type(params, sp.TRecord(
            question=sp.TBytes,
            description=sp.TBytes,
            options=sp.TMap(sp.TNat, sp.TBytes),
            vote_weight_method=TeiaPolls.VOTE_WEIGHT_METHOD_TYPE,
            vote_period=sp.TNat).layout(
                ("question", ("description", ("options", ("vote_weight_method", " vote_period"))))))

        # Check that one of the DAO members executed the entry point
        self.check_is_dao_member()

        # Check that there are at least two options to vote
        sp.verify(sp.len(params.options) > 1, message="POLL_WRONG_OPTIONS")

        # Check that the vote period is between 1 and 30 days
        sp.verify((params.vote_period >= 1) & (params.vote_period <= 30),
                  message="POLL_WRONG_VOTE_PERIOD")

        # Initialize the map that will contain vote count for each poll option
        votes_count = sp.local("votes_count",
                               sp.map({}, tkey=sp.TNat, tvalue=sp.TNat))

        with sp.for_("option", params.options.keys()) as option:
            votes_count.value[option] = 0

        # Update the polls bigmap with the new poll information
        self.data.polls[self.data.counter] = sp.record(
            question=params.question,
            description=params.description,
            options=params.options,
            vote_weight_method=params.vote_weight_method,
            vote_period=params.vote_period,
            issuer=sp.sender,
            timestamp=sp.now,
            level=sp.level,
            votes_count=votes_count.value)

        # Increase the polls counter
        self.data.counter += 1

    @sp.entry_point
    def vote(self, params):
        """Adds one vote for a given poll.

        """
        # Define the input parameter data type
        sp.set_type(params, sp.TRecord(
            poll_id=sp.TNat,
            option=sp.TNat,
            max_checkpoints=sp.TOption(sp.TNat)).layout(
                ("poll_id", ("option", "max_checkpoints"))))

        # Check that the poll exists
        poll = sp.compute(self.data.polls.get(
            params.poll_id, message="POLL_NONEXISTENT_POLL"))

        # Check that the selected option exists
        sp.verify(poll.options.contains(params.option),
                  message="POLL_WRONG_OPTION")

        # Check that the poll voting period didn't expire
        end_date = poll.timestamp.add_days(sp.to_int(poll.vote_period))
        sp.verify(sp.now < end_date, message="POLL_CLOSED_POLL")

        # Get the member DAO token balance at the poll creation
        token_balance = sp.local("token_balance", self.get_prior_token_balance(
            poll.level, params.max_checkpoints))

        # Check that the token balance is higher than zero
        sp.verify(token_balance.value > 0, message="POLL_INSUFICIENT_BALANCE")

        # Calculate the vote weight
        weight = sp.local("weight", 0)

        with poll.vote_weight_method.match_cases() as arg:
            with arg.match("linear"):
                weight.value = token_balance.value
            with arg.match("quadratic"):
                # Divide the balance by 10000 to reduce the number of iterations
                weight.value = 100 * self.integer_square_root(
                    token_balance.value // 10000)
            with arg.match("equal"):
                weight.value = 1

        # Check if the user voted before and remove their previous vote from the
        # poll votes
        vote_key = sp.compute(sp.pair(params.poll_id, sp.sender))
        new_votes_count = sp.local("new_votes_count", poll.votes_count)

        with sp.if_(self.data.votes.contains(vote_key)):
            previous_option = sp.compute(self.data.votes[vote_key].option)
            new_votes_count.value[previous_option] = sp.as_nat(
                new_votes_count.value[previous_option] - weight.value)

        # Add or update the user's vote
        self.data.votes[vote_key] = sp.record(
            option=params.option,
            weight=weight.value)

        # Add the user vote to the poll votes
        new_votes_count.value[params.option] = new_votes_count.value[params.option] + weight.value
        self.data.polls[params.poll_id].votes_count = new_votes_count.value

    @sp.onchain_view()
    def get_poll_count(self):
        """Returns the total number of polls.

        """
        sp.result(self.data.counter)

    @sp.onchain_view()
    def get_poll(self, poll_id):
        """Returns the complete information from a given poll.

        """
        # Define the input parameter data type
        sp.set_type(poll_id, sp.TNat)

        # Check that the poll id is present in the polls big map
        sp.verify(self.data.polls.contains(poll_id),
                  message="POLL_NONEXISTENT_POLL")

        # Return the poll information
        sp.result(self.data.polls[poll_id])

    @sp.onchain_view()
    def get_vote(self, params):
        """Returns a user's vote.

        """
        # Define the input parameter data type
        sp.set_type(params, sp.TRecord(
            poll_id=sp.TNat,
            user=sp.TAddress).layout(("poll_id", "user")))

        # Check that the vote is present in the votes big map
        sp.verify(self.data.votes.contains((params.poll_id, params.user)),
                  message="POLL_NO_USER_VOTE")

        # Return the user's vote
        sp.result(self.data.votes[(params.poll_id, params.user)])

    @sp.onchain_view()
    def has_voted(self, params):
        """Returns true if the user has voted the given poll.

        """
        # Define the input parameter data type
        sp.set_type(params, sp.TRecord(
            poll_id=sp.TNat,
            user=sp.TAddress).layout(("poll_id", "user")))

        # Return true if the user has voted the poll
        sp.result(self.data.votes.contains((params.poll_id, params.user)))

    @sp.entry_point(private=True)
    def get_integer_square_root(self, number):
        """Calculates the square root of the given number.

        Note that this is a private entrypoint only used for testing purposes.

        """
        # Define the input parameter data type
        sp.set_type(number, sp.TNat)

        # Store the result in the counter just for test purposes
        self.data.counter = self.integer_square_root(number)


# Add a compilation target
sp.add_compilation_target("teiaPolls", TeiaPolls(
    metadata=sp.utils.metadata_of_url("ipfs://QmYH2RWFybPAiZJWKG8a8i4TVFQH8DLLKD5BTtGoiMXc5S"),
    token=sp.address("KT1QrtA753MSv8VGxkDrKKyJniG5JtuHHbtV")))
