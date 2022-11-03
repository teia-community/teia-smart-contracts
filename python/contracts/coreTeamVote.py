"""A smart contract where the Teia Core Team members can vote multi-option text
proposals.

"""

import smartpy as sp


class CoreTeamVote(sp.Contract):
    """This contract allows the Teia Core Team to vote multi-option text
    proposals.

    """

    PROPOSAL_TYPE = sp.TRecord(
        # The user that submitted the proposal
        issuer=sp.TAddress,
        # The time when the proposal was submitted
        timestamp=sp.TTimestamp,
        # The proposal short description
        description=sp.TString,
        # The ipfs link with the text describing the proposal
        text=sp.TString,
        # The proposal voting options
        options=sp.TMap(sp.TNat, sp.TString),
        # The proposal voting period in days
        voting_period=sp.TNat,
        # The minimum number of votes needed to approve the proposal
        minimum_votes=sp.TNat).layout(
            ("issuer", ("timestamp", ("description", ("text", ("options", ("voting_period", "minimum_votes")))))))

    def __init__(self, metadata, core_team_multisig, minimum_votes):
        """Initializes the contract.

        """
        # Define the contract storage data types for clarity
        self.init_type(sp.TRecord(
            # The contract metadata bigmap
            metadata=sp.TBigMap(sp.TString, sp.TBytes),
            # The Teia Core Team Multisig contract address
            core_team_multisig=sp.TAddress,
            # The big map with the proposals information
            proposals=sp.TBigMap(sp.TNat, CoreTeamVote.PROPOSAL_TYPE),
            # The big map with the votes information
            votes=sp.TBigMap(sp.TPair(sp.TNat, sp.TAddress), sp.TNat),
            # The minimum number of votes needed to approve proposals
            minimum_votes=sp.TNat,
            # The proposals bigmap counter
            counter=sp.TNat))

        # Initialize the contract storage
        self.init(
            metadata=metadata,
            core_team_multisig=core_team_multisig,
            proposals=sp.big_map(),
            votes=sp.big_map(),
            minimum_votes=minimum_votes,
            counter=0)

    def check_is_user(self):
        """Checks that the address that called the entry point is from one of
        the Teia Core Team multisig users.

        """
        is_user = sp.view(
            name="is_user",
            address=self.data.core_team_multisig,
            param=sp.sender,
            t=sp.TBool).open_some()
        sp.verify(is_user, message="CTV_NOT_CORE_TEAM_USER")

    @sp.entry_point
    def create_proposal(self, params):
        """Adds a new proposal to the proposals big map.

        """
        # Define the input parameter data type
        sp.set_type(params, sp.TRecord(
            description=sp.TString,
            text=sp.TString,
            options=sp.TMap(sp.TNat, sp.TString),
            voting_period=sp.TNat).layout(
                ("description", ("text", ("options", "voting_period")))))

        # Check that one of the Core Team users executed the entry point
        self.check_is_user()

        # Check that there are at least two options to vote
        sp.verify(sp.len(params.options) > 1, message="CTV_WRONG_OPTIONS")

        # Check that the voting period is longer than one day
        sp.verify(params.voting_period > 1, message="CTV_WRONG_VOTING_PERIOD")

        # Update the proposals bigmap with the new proposal information
        self.data.proposals[self.data.counter] = sp.record(
            issuer=sp.sender,
            timestamp=sp.now,
            description=params.description,
            text=params.text,
            options=params.options,
            voting_period=params.voting_period,
            minimum_votes=self.data.minimum_votes)

        # Increase the proposals counter
        self.data.counter += 1

    @sp.entry_point
    def vote_proposal(self, params):
        """Adds one vote for a given proposal.

        """
        # Define the input parameter data type
        sp.set_type(params, sp.TRecord(
            proposal_id=sp.TNat,
            option=sp.TNat).layout(("proposal_id", "option")))

        # Check that one of the Core Team users executed the entry point
        self.check_is_user()

        # Check that the proposal can still be voted
        proposal = sp.compute(self.data.proposals.get(
            params.proposal_id, message="CTV_INEXISTENT_PROPOSAL"))
        can_vote = sp.now < proposal.timestamp.add_days(
            sp.to_int(proposal.voting_period))
        sp.verify(can_vote, message="CTV_CLOSED_PROPOSAL")

        # Check that the selected option exists
        sp.verify(proposal.options.contains(params.option),
                  message="CTV_WRONG_OPTION")

        # Add or update the user's vote
        self.data.votes[(params.proposal_id, sp.sender)] = params.option

    @sp.entry_point
    def set_minimum_votes(self, minimum_votes):
        """Updates the minimum votes parameter.

        """
        # Define the input parameter data type
        sp.set_type(minimum_votes, sp.TNat)

        # Check that the Teia Core Team multisig executed the entry point
        sp.verify(sp.sender == self.data.core_team_multisig,
                  message="CTV_NOT_MULTISIG")

        # Check that the number of minimum votes is larger than one
        sp.verify(minimum_votes > 1, message="CTV_WRONG_MINIMUM_VOTES")

        # Update the minimum votes parameter
        self.data.minimum_votes = minimum_votes

    @sp.onchain_view()
    def get_proposal_count(self):
        """Returns the total number of proposals.

        """
        sp.result(self.data.counter)

    @sp.onchain_view()
    def get_proposal(self, proposal_id):
        """Returns the complete information from a given proposal.

        """
        # Define the input parameter data type
        sp.set_type(proposal_id, sp.TNat)

        # Check that the proposal id is present in the proposals big map
        sp.verify(self.data.proposals.contains(proposal_id),
                  message="CTV_INEXISTENT_PROPOSAL")

        # Return the proposal information
        sp.result(self.data.proposals[proposal_id])

    @sp.onchain_view()
    def get_vote(self, params):
        """Returns a user's vote.

        """
        # Define the input parameter data type
        sp.set_type(params, sp.TRecord(
            proposal_id=sp.TNat,
            user=sp.TAddress).layout(("proposal_id", "user")))

        # Check that the vote is present in the votes big map
        sp.verify(self.data.votes.contains((params.proposal_id, params.user)),
                  message="CTV_NO_USER_VOTE")

        # Return the user's vote
        sp.result(self.data.votes[(params.proposal_id, params.user)])

    @sp.onchain_view()
    def has_voted(self, params):
        """Returns true if the user has voted the given proposal.

        """
        # Define the input parameter data type
        sp.set_type(params, sp.TRecord(
            proposal_id=sp.TNat,
            user=sp.TAddress).layout(("proposal_id", "user")))

        # Return true if the user has voted the proposal
        sp.result(self.data.votes.contains((params.proposal_id, params.user)))


# Add a compilation target
sp.add_compilation_target("coreTeamVote", CoreTeamVote(
    metadata=sp.utils.metadata_of_url("ipfs://QmVGVvVQBEgKA8meTq8QsRvTx4o9iKA1q3Nof7XdL3PcMB"),
    core_team_multisig=sp.address("KT1J9FYz29RBQi1oGLw8uXyACrzXzV1dHuvb"),
    minimum_votes=sp.nat(5)))
