import smartpy as sp


class DAOGovernance(sp.Contract):
    """This contract implements a DAO governed by token holders.

    """

    PROPOSAL_KIND_TYPE = sp.TVariant(
        # A proposal in the form of text to be voted for
        text=sp.TUnit,
        # A proposal to transfer mutez from the contract to other accounts
        transfer_mutez=sp.TUnit,
        # A proposal to transfer a token from the contract to other accounts
        transfer_token=sp.TUnit,
        # A proposal to update the DAO governance parameters
        update_governance=sp.TUnit,
        # A proposal to execute a lambda function
        lambda_function=sp.TUnit)

    MUTEZ_TRANSFERS_TYPE = sp.TList(sp.TRecord(
        # The amount of mutez to transfer
        amount=sp.TMutez,
        # The transfer destination
        destination=sp.TAddress).layout(
            ("amount", "destination")))

    TOKEN_TRANSFERS_TYPE = sp.TRecord(
        # The token contract address
        fa2=sp.TAddress,
        # The token id
        token_id=sp.TNat,
        # The token transfer distribution
        distribution=sp.TList(sp.TRecord(
            # The number of token editions to transfer
            amount=sp.TNat,
            # The transfer destination
            destination=sp.TAddress).layout(("amount", "destination")))).layout(
                ("fa2", ("token_id", "distribution")))

    GOVERNANCE_PARAMETERS_TYPE = sp.TRecord(
        # The proposal voting period in days
        voting_period=sp.TNat,
        # The percentage of votes for super-majority
        percentage_for_super_majority=sp.TNat,
        # The quorum cap
        quorum_cap=sp.TNat).layout(
            ("voting_period", ("percentage_for_super_majority", "quorum_cap")))

    LAMBDA_FUNCTION_TYPE = sp.TLambda(sp.TUnit, sp.TList(sp.TOperation))

    PROPOSAL_PARAMETERS_TYPE = sp.TRecord(
        # The list of mutez transfers
        mutez_transfers=sp.TOption(MUTEZ_TRANSFERS_TYPE),
        # The list of token transfers
        token_transfers=sp.TOption(TOKEN_TRANSFERS_TYPE),
        # The new governance parameters
        governance=sp.TOption(GOVERNANCE_PARAMETERS_TYPE),
        # The lambda function to execute
        lambda_function=sp.TOption(LAMBDA_FUNCTION_TYPE)).layout(
            ("mutez_transfers", ("token_transfers", ("governance", "lambda_function"))))

    PROPOSAL_STATUS_TYPE = sp.TVariant(
        # The status for proposals that are open and can still be voted
        open=sp.TUnit,
        # The status for proposals that have been approved but not yet executed
        approved=sp.TUnit,
        # The status for approved and executed proposals
        executed=sp.TUnit,
        # The status for proposals that didn't receive enough votes to be
        # approved and executed during the voting period
        rejected=sp.TUnit)

    PROPOSAL_TYPE = sp.TRecord(
        # The kind of proposal: text, transfer_mutez, transfer_token, etc
        kind=PROPOSAL_KIND_TYPE,
        # The proposal title
        title=sp.TBytes,
        # The proposal description
        description=sp.TBytes,
        # The proposal parameters
        parameters=PROPOSAL_PARAMETERS_TYPE,
        # The user that submitted the proposal
        issuer=sp.TAddress,
        # The timestamp when the proposal was submitted
        timestamp=sp.TTimestamp,
        # The block level when the proposal was submitted
        level=sp.TNat,
        # The proposal current status: open, executed or rejected
        status=PROPOSAL_STATUS_TYPE).layout(
            ("kind", ("title", ("description", ("parameters", ("issuer", ("timestamp", ("level", "status"))))))))

    VOTES_SUMMARY_TYPE = sp.TRecord(
        # The number of positive votes that the proposal has received
        positive=sp.TNat,
        # The number of negative votes that the proposal has received
        negative=sp.TNat,
        # The number of abstain votes that the proposal has received
        abstain=sp.TNat,
        # The total number of votes that the proposal has received
        total=sp.TNat,
        # The total number of wallets that voted
        participation=sp.TNat).layout(
            ("positive", ("negative", ("abstain", ("total", "participation")))))

    VOTE_KIND_TYPE = sp.TVariant(
        # A positive vote
        yes=sp.TUnit,
        # A negative vote
        no=sp.TUnit,
        # An abstain vote
        abstain=sp.TUnit)

    VOTE_TYPE = sp.TRecord(
        # The user vote: yes, no or abstain
        vote=VOTE_KIND_TYPE,
        # The vote weight based on their DAO token balance
        weight=sp.TNat).layout(
            ("vote", "weight"))

    FA2_TX_TYPE = sp.TRecord(
        # The token destination
        to_=sp.TAddress,
        # The token id
        token_id=sp.TNat,
        # The number of token editions
        amount=sp.TNat).layout(
            ("to_", ("token_id", "amount")))

    def __init__(self, metadata, token, representatives):
        """Initializes the contract.

        """
        # Define the contract storage data types for clarity
        self.init_type(sp.TRecord(
            # The contract metadata
            metadata=sp.TBigMap(sp.TString, sp.TBytes),
            # The DAO token contract address
            token=sp.TAddress,
            # The DAO representatives contract address
            representatives=sp.TAddress,
            # The quorum needed to approve proposals
            quorum=sp.TNat,
            # The DAO governance parameters
            governance_parameters=DAOGovernance.GOVERNANCE_PARAMETERS_TYPE,
            # The big map with the proposals information
            proposals=sp.TBigMap(sp.TNat, DAOGovernance.PROPOSAL_TYPE),
            # The big map with the DAO token holders vote summaries
            token_votes=sp.TBigMap(sp.TNat, DAOGovernance.VOTES_SUMMARY_TYPE),
            # The big map with the representatives vote summaries
            representatives_votes=sp.TBigMap(
                sp.TNat, DAOGovernance.VOTES_SUMMARY_TYPE),
            # The big map with all the votes information
            votes=sp.TBigMap(
                sp.TPair(sp.TNat, sp.TAddress), DAOGovernance.VOTE_TYPE),
            # The proposals counter
            counter=sp.TNat))

        # Initialize the contract storage
        self.init(
            metadata=metadata,
            token=token,
            representatives=representatives,
            quorum=80,
            governance_parameters=sp.record(
                voting_period=10,
                percentage_for_super_majority=10,
                quorum_cap=10),
            proposals=sp.big_map(),
            token_votes=sp.big_map(),
            representatives_votes=sp.big_map(),
            votes=sp.big_map(),
            counter=0)

    def get_token_balance(self):
        """Gets the sender token balance calling the DAO token on-chain view.

        """
        return sp.view(
            name="get_balance",
            address=self.data.token,
            param=sp.record(owner=sp.sender, token_id=sp.nat(0)),
            t=sp.TNat).open_some()

    def get_prior_token_balance(self, level, max_checkpoints):
        """Gets the sender prior token balance calling the DAO token on-chain
        view.

        """
        return sp.view(
            name="get_prior_balance",
            address=self.data.token,
            param=sp.record(
                owner=sp.sender, level=level, max_checkpoints=max_checkpoints),
            t=sp.TNat).open_some()

    def check_is_member(self):
        """Checks that the address that called the entry point is one of the
        DAO members.

        """
        sp.verify((sp.sender == self.data.representatives) | 
                  (self.get_token_balance() > 0),
                  message="DAO_NOT_MEMBER")

    def add_proposal(self, kind, title, description, mutez_transfers=sp.none,
                     token_transfers=sp.none, governance=sp.none,
                     lambda_function=sp.none):
        """Adds a new proposal to the proposals and vote summaries big maps.

        """
        # Add the new proposal information to the proposals big map
        self.data.proposals[self.data.counter] = sp.record(
            kind=sp.variant(kind, sp.unit),
            title=title,
            description=description,
            parameters=sp.record(
                mutez_transfers=mutez_transfers,
                token_transfers=token_transfers,
                governance=governance,
                lambda_function=lambda_function),
            issuer=sp.sender,
            timestamp=sp.now,
            level=sp.level,
            status=sp.variant("open", sp.unit))

        # Initialize DAO token holders vote counters for the new proposal
        self.data.token_votes[self.data.counter] = sp.record(
            positive=0,
            negative=0,
            abstain=0,
            total=0,
            participation=0)

        # Initialize representatives vote counters for the new proposal
        self.data.representatives_votes[self.data.counter] = sp.record(
            positive=0,
            negative=0,
            abstain=0,
            total=0,
            participation=0)

        # Increase the proposals counter
        self.data.counter += 1

    @sp.entry_point
    def default(self, unit):
        """Default entrypoint that allows receiving tez transfers in the same
        way as one would do with a normal tz wallet.

        """
        # Define the input parameter data type
        sp.set_type(unit, sp.TUnit)

        # Do nothing, just receive tez
        pass

    @sp.entry_point
    def text_proposal(self, params):
        """Adds a new text proposal to the proposals big map.

        """
        # Define the input parameter data type
        sp.set_type(params, sp.TRecord(
            title=sp.TBytes,
            description=sp.TBytes)).layout(("title", "description"))

        # Check that one of the DAO members executed the entry point
        self.check_is_member()

        # Add the proposal
        self.add_proposal(
            kind="text",
            title=params.title,
            description=params.description)

    @sp.entry_point
    def transfer_mutez_proposal(self, params):
        """Adds a new transfer mutez proposal to the proposals big map.

        """
        # Define the input parameter data type
        sp.set_type(params, sp.TRecord(
            title=sp.TBytes,
            description=sp.TBytes,
            mutez_transfers=DAOGovernance.MUTEZ_TRANSFERS_TYPE).layout(
                ("title", ("description", "mutez_transfers"))))

        # Check that one of the DAO members executed the entry point
        self.check_is_member()

        # Add the proposal
        self.add_proposal(
            kind="transfer_mutez",
            title=params.title,
            description=params.description,
            mutez_transfers=sp.some(params.mutez_transfers))

    @sp.entry_point
    def transfer_token_proposal(self, params):
        """Adds a new transfer token proposal to the proposals big map.

        """
        # Define the input parameter data type
        sp.set_type(params, sp.TRecord(
            title=sp.TBytes,
            description=sp.TBytes,
            token_transfers=DAOGovernance.TOKEN_TRANSFERS_TYPE).layout(
                ("title", ("description", "token_transfers"))))

        # Check that one of the DAO members executed the entry point
        self.check_is_member()

        # Add the proposal
        self.add_proposal(
            kind="transfer_token",
            title=params.title,
            description=params.description,
            token_transfers=sp.some(params.token_transfers))

    @sp.entry_point
    def update_governance_proposal(self, params):
        """Adds a new update governance proposal to the proposals big map.

        """
        # Define the input parameter data type
        sp.set_type(params, sp.TRecord(
            title=sp.TBytes,
            description=sp.TBytes,
            governance=DAOGovernance.GOVERNANCE_PARAMETERS_TYPE).layout(
                ("title", ("description", "governance"))))

        # Check that one of the DAO members executed the entry point
        self.check_is_member()

        # Add the proposal
        self.add_proposal(
            kind="update_governance",
            title=params.title,
            description=params.description,
            governance=sp.some(params.governance))

    @sp.entry_point
    def lambda_function_proposal(self, params):
        """Adds a new lambda function proposal to the proposals big map.

        """
        # Define the input parameter data type
        sp.set_type(params, sp.TRecord(
            title=sp.TBytes,
            description=sp.TBytes,
            lambda_function=DAOGovernance.LAMBDA_FUNCTION_TYPE).layout(
                ("title", ("description", "lambda_function"))))

        # Check that one of the DAO members executed the entry point
        self.check_is_member()

        # Add the proposal
        self.add_proposal(
            kind="lambda_function",
            title=params.title,
            description=params.description,
            lambda_function=sp.some(params.lambda_function))

    @sp.entry_point
    def token_vote(self, params):
        """Adds a new DAO token holder vote for a given proposal.

        """
        # Define the input parameter data type
        sp.set_type(params, sp.TRecord(
            proposal_id=sp.TNat,
            vote=DAOGovernance.VOTE_KIND_TYPE,
            max_checkpoints=sp.TOption(sp.TNat)).layout(
                ("proposal_id", ("vote", "max_checkpoints"))))

        # Check that the proposal exists
        sp.verify(params.proposal_id < self.data.counter,
                  message="DAO_INEXISTENT_PROPOSAL")

        # Check that the proposal voting period didn't expire
        end_date = self.data.proposals[params.proposal_id].timestamp.add_days(
            sp.to_int(self.data.governance_parameters.voting_period))
        sp.verify(sp.now < end_date, message="DAO_CLOSED_PROPOSAL")

        # Check that the member didn't vote the proposal before
        sp.verify(~self.data.votes.contains((params.proposal_id, sp.sender)),
                  message="DAO_ALREADY_VOTED")

        # Get the member DAO token balance at the proposal creation
        token_balance = sp.compute(self.get_prior_token_balance(
            self.data.proposals[params.proposal_id].level, params.max_checkpoints))

        # Check that the token balance is not zero
        sp.verify(token_balance > 0, message="DAO_ZERO_BALANCE")

        # Calculate the voting weight (for the moment we assume linear weight)
        voting_weight = token_balance

        # Update the DAO token holders vote summary
        new_votes = sp.local(
            "new_votes", self.data.token_votes[params.proposal_id])
        new_votes.value.total += voting_weight
        new_votes.value.participation += 1

        with params.vote.match_cases() as arg:
            with arg.match("yes"):
                new_votes.value.positive += voting_weight
            with arg.match("no"):
                new_votes.value.negative += voting_weight
            with arg.match("abstain"):
                new_votes.value.abstain += voting_weight

        self.data.token_votes[params.proposal_id] = new_votes.value

        # Add the vote to the votes big map
        self.data.votes[(params.proposal_id, sp.sender)] = sp.record(
            vote=params.vote,
            weight=voting_weight)

    @sp.entry_point
    def representatives_vote(self, params):
        """Adds a new representative vote for a given proposal.

        """
        # Define the input parameter data type
        sp.set_type(params, sp.TRecord(
            proposal_id=sp.TNat,
            vote=DAOGovernance.VOTE_KIND_TYPE,
            representative=sp.TAddress).layout(
                ("proposal_id", ("vote", "representative"))))

        # Check that the representatives contract executed the entry point
        sp.verify(sp.sender == self.data.representatives,
                  message="DAO_NOT_REPRESENTATIVES")

        # Check that the proposal exists
        sp.verify(params.proposal_id < self.data.counter,
                  message="DAO_INEXISTENT_PROPOSAL")

        # Check that the proposal voting period didn't expire
        end_date = self.data.proposals[params.proposal_id].timestamp.add_days(
            sp.to_int(self.data.governance_parameters.voting_period))
        sp.verify(sp.now < end_date, message="DAO_CLOSED_PROPOSAL")

        # Check that the representative didn't vote the proposal before
        sp.verify(~self.data.votes.contains((params.proposal_id, params.representative)),
                  message="DAO_ALREADY_VOTED")

        # Update the representatives vote summary
        new_votes = sp.local(
            "new_votes", self.data.representatives_votes[params.proposal_id])
        new_votes.value.total += 1
        new_votes.value.participation += 1

        with params.vote.match_cases() as arg:
            with arg.match("yes"):
                new_votes.value.positive += 1
            with arg.match("no"):
                new_votes.value.negative += 1
            with arg.match("abstain"):
                new_votes.value.abstain += 1

        self.data.representatives_votes[params.proposal_id] = new_votes.value

        # Add the vote to the votes big map
        self.data.votes[(params.proposal_id, params.representative)] = sp.record(
            vote=params.vote,
            weight=1)

    @sp.entry_point
    def execute_proposal(self, proposal_id):
        """Executes a given proposal.

        """
        # Define the input parameter data type
        sp.set_type(proposal_id, sp.TNat)

        # Check that one of the DAO members executed the entry point
        self.check_is_member()

        # Check that the proposal exists
        sp.verify(proposal_id < self.data.counter,
                  message="DAO_INEXISTENT_PROPOSAL")

        # Check that the proposal is approved
        proposal = sp.local("proposal", self.data.proposals[proposal_id])
        sp.verify(proposal.value.status.is_variant("approved"),
                  message="DAO_NOT_APPROVED")

        # Execute the proposal
        self.data.proposals[proposal_id].status = sp.variant(
            "executed", sp.unit)

        with sp.if_(proposal.value.kind.is_variant("transfer_mutez")):
            mutez_transfers = proposal.value.parameters.mutez_transfers.open_some()

            with sp.for_("mutez_transfer", mutez_transfers) as mutez_transfer:
                sp.send(mutez_transfer.destination, mutez_transfer.amount)

        with sp.if_(proposal.value.kind.is_variant("transfer_token")):
            txs = sp.local("txs", sp.list(t=DAOGovernance.FA2_TX_TYPE))
            token_transfers = proposal.value.parameters.token_transfers.open_some()

            with sp.for_("distribution", token_transfers.distribution) as distribution:
                txs.value.push(sp.record(
                    to_=distribution.destination,
                    token_id=token_transfers.token_id,
                    amount=distribution.amount))

            self.fa2_transfer(token_transfers.fa2, sp.self_address, txs.value)

        with sp.if_(proposal.value.kind.is_variant("update_governance")):
            self.data.governance_parameters = proposal.value.parameters.governance.open_some()

        with sp.if_(proposal.value.kind.is_variant("lambda_function")):
            operations = proposal.value.parameters.lambda_function.open_some()(sp.unit)
            sp.add_operations(operations)

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
                  message="DAO_INEXISTENT_PROPOSAL")

        # Return the proposal information
        sp.result(self.data.proposals[proposal_id])

    @sp.onchain_view()
    def get_vote(self, params):
        """Returns a member's vote.

        """
        # Define the input parameter data type
        sp.set_type(params, sp.TRecord(
            proposal_id=sp.TNat,
            member=sp.TAddress).layout(("proposal_id", "member")))

        # Check that the vote is present in the votes big map
        sp.verify(self.data.votes.contains((params.proposal_id, params.member)),
                  message="DAO_NO_MEMBER_VOTE")

        # Return the member's vote
        sp.result(self.data.votes[(params.proposal_id, params.member)])

    @sp.onchain_view()
    def has_voted(self, params):
        """Returns true if the member has voted the given proposal.

        """
        # Define the input parameter data type
        sp.set_type(params, sp.TRecord(
            proposal_id=sp.TNat,
            member=sp.TAddress).layout(("proposal_id", "member")))

        # Return true if the member has voted the proposal
        sp.result(self.data.votes.contains((params.proposal_id, params.member)))

    def fa2_transfer(self, fa2, from_, txs):
        """Transfers a number of editions of a FA2 token to several wallets.

        """
        # Get a handle to the FA2 token transfer entry point
        c = sp.contract(
            t=sp.TList(sp.TRecord(
                from_=sp.TAddress,
                txs=sp.TList(DAOGovernance.FA2_TX_TYPE))),
            address=fa2,
            entry_point="transfer").open_some()

        # Transfer the FA2 token editions to the new address
        sp.transfer(
            arg=sp.list([sp.record(from_=from_, txs=txs)]),
            amount=sp.mutez(0),
            destination=c)


sp.add_compilation_target("dao", DAOGovernance(
    metadata=sp.utils.metadata_of_url("ipfs://aaa"),
    token=sp.address("KT1QmSmQ8Mj8JHNKKQmepFqQZy7kDWQ1ekaa"),
    representatives=sp.address("KT1QmSmQ8Mj8JHNKKQmepFqQZy7kDWQ1ekbb")))
