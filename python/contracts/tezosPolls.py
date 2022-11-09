"""A smart contract where the Tezos community can create polls and vote them.

"""

import smartpy as sp


class TezosPolls(sp.Contract):
    """This contract can be used to create polls that can be voted by any tezos
    wallet.

    """

    POLL_TYPE = sp.TRecord(
        # The user that submitted the poll
        issuer=sp.TAddress,
        # The time when the poll was submitted
        timestamp=sp.TTimestamp,
        # The poll question
        question=sp.TBytes,
        # The poll voting options
        options=sp.TMap(sp.TNat, sp.TBytes),
        # The poll voting period in days
        voting_period=sp.TNat).layout(
            ("issuer", ("timestamp", ("question", ("options", "voting_period")))))

    def __init__(self, metadata):
        """Initializes the contract.

        """
        # Define the contract storage data types for clarity
        self.init_type(sp.TRecord(
            # The contract metadata bigmap
            metadata=sp.TBigMap(sp.TString, sp.TBytes),
            # The big map with the polls information
            polls=sp.TBigMap(sp.TNat, TezosPolls.POLL_TYPE),
            # The big map with the votes information
            votes=sp.TBigMap(sp.TPair(sp.TNat, sp.TAddress), sp.TNat),
            # The big map with the polls current results
            results=sp.TBigMap(sp.TPair(sp.TNat, sp.TNat), sp.TNat),
            # The polls bigmap counter
            counter=sp.TNat))

        # Initialize the contract storage
        self.init(
            metadata=metadata,
            polls=sp.big_map(),
            votes=sp.big_map(),
            results=sp.big_map(),
            counter=0)

    @sp.entry_point
    def create_poll(self, params):
        """Adds a new poll to the polls big map.

        """
        # Define the input parameter data type
        sp.set_type(params, sp.TRecord(
            question=sp.TBytes,
            options=sp.TMap(sp.TNat, sp.TBytes),
            voting_period=sp.TNat).layout(
                ("question", ("options", "voting_period"))))

        # Check that there are at least two options to vote
        sp.verify(sp.len(params.options) > 1, message="POLL_WRONG_OPTIONS")

        # Check that the voting period is between 1 and 5 days
        sp.verify((params.voting_period >= 1) & (params.voting_period <= 5),
                  message="POLL_WRONG_VOTING_PERIOD")

        # Update the polls bigmap with the new poll information
        self.data.polls[self.data.counter] = sp.record(
            issuer=sp.sender,
            timestamp=sp.now,
            question=params.question,
            options=params.options,
            voting_period=params.voting_period)

        # Increase the polls counter
        self.data.counter += 1

    @sp.entry_point
    def vote(self, params):
        """Adds one vote for a given poll.

        """
        # Define the input parameter data type
        sp.set_type(params, sp.TRecord(
            poll_id=sp.TNat,
            option=sp.TNat).layout(("poll_id", "option")))

        # Check that the poll can still be voted
        poll = sp.compute(self.data.polls.get(
            params.poll_id, message="INEXISTENT_POLL"))
        can_vote = sp.now < poll.timestamp.add_days(
            sp.to_int(poll.voting_period))
        sp.verify(can_vote, message="CLOSED_POLL")

        # Check that the selected option exists
        sp.verify(poll.options.contains(params.option),
                  message="POLL_WRONG_OPTION")

        # Check if the user voted before and remove their previous vote from the
        # results big map
        vote_key = sp.compute(sp.pair(params.poll_id, sp.sender))

        with sp.if_(self.data.votes.contains(vote_key)):
            previous_option = sp.compute(self.data.votes[vote_key])
            self.data.results[(params.poll_id, previous_option)] = sp.as_nat(
                self.data.results[(params.poll_id, previous_option)] - 1)

        # Add or update the user's vote
        self.data.votes[vote_key] = params.option

        # Add the vote to the poll results
        result_key = sp.compute(sp.pair(params.poll_id, params.option))
        self.data.results[result_key] = 1 + self.data.results.get(
            result_key, default_value=0)

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
                  message="INEXISTENT_POLL")

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
                  message="NO_USER_VOTE")

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


# Add a compilation target
sp.add_compilation_target("tezosPolls", TezosPolls(
    metadata=sp.utils.metadata_of_url("ipfs://QmdTcVEy8afc2paFRvvQdoK6hn8CDmEmKCsFeW3GV3aCJi")))
