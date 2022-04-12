import smartpy as sp
from teia_sc.error_collection import ErrorCollection


class DAOGovernance(sp.Contract):
    """This contract implements a Decentralized Autonomous Organization (DAO)
    governed by DAO token holders and community representatives.

    The contract is a combination of the Teia multisig wallet contract and the
    Murmuration DAO smart contracts:
      https://github.com/teia-community/teia-smart-contracts
      https://github.com/Hover-Labs/murmuration

    Main features:
        - It considers two kinds of DAO members: DAO token holders and
          community representatives.
        - Many proposals can run at the same time.
        - It could use linear or quadratic voting methods.
        - Members do not need to escrow their DAO tokens for voting, only to
          create proposals.
        - It uses on-chain views instead of callback functions to access DAO
          token balances.
        - DAO governance parameters can be updated via lambda proposals.
        - Separates the DAO governance from the DAO treasury.
        - It includes the figure of the DAO guardians, which could cancel
          malicious proposals.
        - It includes the figure of the DAO administrator, which could update
          some of the DAO parameters, like the quorum.

    """

    VOTE_WEIGHT_METHOD_TYPE = sp.TVariant(
        # Linear/proportional voting: vote weight = DAO token amount
        linear=sp.TUnit,
        # Quadractic voting: vote weight = sqrt(DAO token amount)
        quadratic=sp.TUnit)

    GOVERNANCE_PARAMETERS_TYPE = sp.TRecord(
        # The vote weight method
        vote_method=VOTE_WEIGHT_METHOD_TYPE,
        # The proposal voting period in days
        vote_period=sp.TNat,
        # The proposal waiting period in days before it can be executed
        wait_period=sp.TNat,
        # The amount of DAO tokens to escrow to create a proposal
        escrow_amount=sp.TNat,
        # The percentage of positive votes needed to return the tokens in escrow
        escrow_return=sp.TNat,
        # The minimum amout of DAO tokens needed to vote proposals
        min_amount=sp.TNat,
        # The percentage of positive votes needed to reach super-majority
        supermajority=sp.TNat,
        # The representatives vote share percentage relative to the quorum
        representatives_share=sp.TNat,
        # The minimum period between quorum updates in days
        quorum_update_period=sp.TNat,
        # The quorum update percentage
        quorum_update=sp.TNat,
        # The maximum quorum percentage change
        quorum_max_change=sp.TNat,
        # The minimum possible quorum value
        min_quorum=sp.TNat,
        # The maximum possible quorum value
        max_quorum=sp.TNat).layout(
            ("vote_method", ("vote_period", ("wait_period", ("escrow_amount", ("escrow_return", ("min_amount", ("supermajority", ("representatives_share", ("quorum_update_period", ("quorum_update", ("quorum_max_change", ("min_quorum", "max_quorum")))))))))))))

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

    LAMBDA_FUNCTION_TYPE = sp.TLambda(sp.TUnit, sp.TList(sp.TOperation))

    PROPOSAL_KIND_TYPE = sp.TVariant(
        # A proposal in the form of text to be voted for
        text=sp.TUnit,
        # A proposal to transfer mutez from the DAO treasury to other accounts
        transfer_mutez=MUTEZ_TRANSFERS_TYPE,
        # A proposal to transfer a token from the DAO treasury to other accounts
        transfer_token=TOKEN_TRANSFERS_TYPE,
        # A proposal to execute a lambda function
        lambda_function=LAMBDA_FUNCTION_TYPE)

    PROPOSAL_STATUS_TYPE = sp.TVariant(
        # The status for proposals that are open and can still be voted
        open=sp.TUnit,
        # The status for proposals that has been cancelled by the proposal
        # issuer or the DAO guardians
        cancelled=sp.TUnit,
        # The status for proposals that have been approved but not yet executed
        approved=sp.TUnit,
        # The status for approved and executed proposals
        executed=sp.TUnit,
        # The status for proposals that didn't receive enough votes to be
        # approved and executed
        rejected=sp.TUnit)

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

    PROPOSAL_TYPE = sp.TRecord(
        # The proposal title
        title=sp.TBytes,
        # The proposal description (normally a link to a file stored in IPFS)
        description=sp.TBytes,
        # The kind of proposal: text, transfer_mutez, transfer_token, etc
        kind=PROPOSAL_KIND_TYPE,
        # The DAO member that submitted the proposal
        issuer=sp.TAddress,
        # The timestamp when the proposal was submitted
        timestamp=sp.TTimestamp,
        # The block level when the proposal was submitted
        level=sp.TNat,
        # The vote weight method to use for the proposal
        vote_method=VOTE_WEIGHT_METHOD_TYPE,
        # The amount of DAO tokens in escrow
        escrow_amount=sp.TNat,
        # The proposal current status: open, approved, executed or rejected
        status=PROPOSAL_STATUS_TYPE,
        # The proposal votes summary from the DAO token holders
        token_votes=VOTES_SUMMARY_TYPE,
        # The proposal votes summary from the community representatives
        representatives_votes=VOTES_SUMMARY_TYPE).layout(
            ("title", ("description", ("kind", ("issuer", ("timestamp", ("level", ("vote_method", ("escrow_amount", ("status", ("token_votes", "representatives_votes")))))))))))

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
        # The vote weight based on the DAO token balance
        weight=sp.TNat).layout(
            ("vote", "weight"))

    FA2_TRANSFER_TYPE = sp.TList(sp.TRecord(
        # The address that sends the token editions
        from_=sp.TAddress,
        # The list of token trasfers
        txs=sp.TList(sp.TRecord(
            # The token destination
            to_=sp.TAddress,
            # The token id
            token_id=sp.TNat,
            # The number of token editions
            amount=sp.TNat).layout(("to_", ("token_id", "amount"))))).layout(
                ("from_", "txs")))

    # Start a collection for smart contract errors
    error_collection = ErrorCollection(__qualname__).inject_into_smartpy(sp)

    def __init__(self, metadata, administrator, treasury, token,
                 representatives, guardians, quorum, governance_parameters):
        """Initializes the contract.

        """
        # Define the contract storage data types for clarity
        self.init_type(sp.TRecord(
            # The contract metadata
            metadata=sp.TBigMap(sp.TString, sp.TBytes),
            # The DAO administrator contract address
            administrator=sp.TAddress,
            # The DAO treasury contract address
            treasury=sp.TAddress,
            # The DAO token contract address
            token=sp.TAddress,
            # The community representatives contract address
            representatives=sp.TAddress,
            # The DAO guardians contract address
            guardians=sp.TAddress,
            # The minimum number of votes needed to approve proposals
            quorum=sp.TNat,
            # The last quorum update
            last_quorum_update=sp.TTimestamp,
            # The DAO governance parameters
            governance_parameters=DAOGovernance.GOVERNANCE_PARAMETERS_TYPE,
            # The big map with the proposals information
            proposals=sp.TBigMap(sp.TNat, DAOGovernance.PROPOSAL_TYPE),
            # The big map with the DAO token holders votes information
            token_votes=sp.TBigMap(
                sp.TPair(sp.TNat, sp.TAddress), DAOGovernance.VOTE_TYPE),
            # The big map with the community representatives votes information
            representatives_votes=sp.TBigMap(
                sp.TPair(sp.TNat, sp.TString), DAOGovernance.VOTE_KIND_TYPE),
            # The proposals counter
            counter=sp.TNat))

        # Initialize the contract storage
        self.init(
            metadata=metadata,
            administrator=administrator,
            treasury=treasury,
            token=token,
            representatives=representatives,
            guardians=guardians,
            quorum=quorum,
            last_quorum_update=sp.timestamp(0),
            governance_parameters=governance_parameters,
            proposals=sp.big_map(),
            token_votes=sp.big_map(),
            representatives_votes=sp.big_map(),
            counter=0)

    @sp.private_lambda(with_storage=None, with_operations=False, wrap_call=True)
    def check_is_dao_member(self, token):
        """Checks that the address that called the entry point is from one of
        the DAO members.

        """
        # Get the sender token balance
        parameter = sp.set_type_expr(
            sp.record(
                owner=sp.sender,
                token_id=0),
            sp.TRecord(
                owner=sp.TAddress,
                token_id=sp.TNat).layout(
                    ("owner", "token_id")))
        token_balance = sp.view(
            name="get_balance",
            address=token,
            param=parameter,
            t=sp.TNat).open_some()

        # Check that the token balance is not zero
        sp.verify(token_balance > 0, message="DAO_NOT_MEMBER")

    @sp.private_lambda(with_storage=None, with_operations=True, wrap_call=True)
    def transfer_tokens(self, params):
        """Transfers a given amount of DAO tokens.

        """
        # Define the input parameter data type
        sp.set_type(params, sp.TRecord(
            token=sp.TAddress,
            from_=sp.TAddress,
            to_=sp.TAddress,
            amount=sp.TNat).layout(
                ("token", ("from_", ("to_", "amount")))))

        # Get a handle to the DAO token transfer entry point
        transfer_handle = sp.contract(
            t=DAOGovernance.FA2_TRANSFER_TYPE,
            address=params.token,
            entry_point="transfer").open_some()

        # Execute the tranfer
        sp.transfer(
            arg=[sp.record(
                from_=params.from_,
                txs=[sp.record(
                    to_=params.to_,
                    token_id=sp.nat(0),
                    amount=params.amount)])],
            amount=sp.mutez(0),
            destination=transfer_handle)

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

    def get_prior_token_balance(self, level, max_checkpoints):
        """Gets the sender prior token balance calling the DAO token on-chain
        view.

        """
        parameter = sp.set_type_expr(
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
            param=parameter,
            t=sp.TNat).open_some()

    @sp.entry_point
    def create_proposal(self, params):
        """Creates a new DAO proposal.

        """
        # Define the input parameter data type
        sp.set_type(params, sp.TRecord(
            title=sp.TBytes,
            description=sp.TBytes,
            kind=DAOGovernance.PROPOSAL_KIND_TYPE).layout(
                ("title", ("description", "kind"))))

        # Check that one of the DAO members executed the entry point
        self.check_is_dao_member(self.data.token)

        # Check if it's necessary to escrow DAO tokens to create proposals
        escrow_amount = sp.compute(self.data.governance_parameters.escrow_amount)

        with sp.if_(escrow_amount > 0):
            # Transfer the DAO tokens from the sender to the DAO contract
            self.transfer_tokens(sp.record(
                token=self.data.token,
                from_=sp.sender,
                to_=sp.self_address,
                amount=escrow_amount))

        # Add the new proposal information to the proposals big map
        self.data.proposals[self.data.counter] = sp.record(
            title=params.title,
            description=params.description,
            kind=params.kind,
            issuer=sp.sender,
            timestamp=sp.now,
            level=sp.level,
            vote_method=self.data.governance_parameters.vote_method,
            escrow_amount=escrow_amount,
            status=sp.variant("open", sp.unit),
            token_votes=sp.record(
                positive=0,
                negative=0,
                abstain=0,
                total=0,
                participation=0),
            representatives_votes=sp.record(
                positive=0,
                negative=0,
                abstain=0,
                total=0,
                participation=0))

        # Increase the proposals counter
        self.data.counter += 1

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
        proposal = sp.compute(self.data.proposals.get(
            params.proposal_id, message="DAO_INEXISTENT_PROPOSAL"))

        # Check that the proposal status is still set as open
        sp.verify(proposal.status.is_variant("open"),
                  message="DAO_STATUS_NOT_OPEN")

        # Check that the proposal voting period didn't expire
        end_date = proposal.timestamp.add_days(
            sp.to_int(self.data.governance_parameters.vote_period))
        sp.verify(sp.now < end_date, message="DAO_CLOSED_PROPOSAL")

        # Check that the member didn't vote the proposal before
        vote_key = sp.pair(params.proposal_id, sp.sender)
        sp.verify(~self.data.token_votes.contains(vote_key),
                  message="DAO_ALREADY_VOTED")

        # Get the member DAO token balance at the proposal creation
        token_balance = sp.local("token_balance", self.get_prior_token_balance(
            proposal.level, params.max_checkpoints))

        # Add the amount of tokens in escrow if the voter is the proposal issuer
        with sp.if_(sp.sender == proposal.issuer):
            token_balance.value += proposal.escrow_amount

        # Check that the token balance is higher than the minimum required amount
        sp.verify(token_balance.value >= self.data.governance_parameters.min_amount,
                  message="DAO_INSUFICIENT_BALANCE")

        # Calculate the vote weight
        weight = sp.local("weight", token_balance.value)

        with sp.if_(proposal.vote_method.is_variant("quadratic")):
            # We divide the balance by 10000 to reduce the number of iterations
            weight.value = 100 * self.integer_square_root(token_balance.value // 10000)

        # Update the DAO token holders votes summary
        new_votes = sp.local("new_votes", proposal.token_votes)
        new_votes.value.total += weight.value
        new_votes.value.participation += 1

        with params.vote.match_cases() as arg:
            with arg.match("yes"):
                new_votes.value.positive += weight.value
            with arg.match("no"):
                new_votes.value.negative += weight.value
            with arg.match("abstain"):
                new_votes.value.abstain += weight.value

        self.data.proposals[params.proposal_id].token_votes = new_votes.value

        # Add the vote to the token votes big map
        self.data.token_votes[vote_key] = sp.record(vote=params.vote, weight=weight.value)

    @sp.entry_point
    def representatives_vote(self, params):
        """Adds a new representative vote for a given proposal.

        """
        # Define the input parameter data type
        sp.set_type(params, sp.TRecord(
            proposal_id=sp.TNat,
            vote=DAOGovernance.VOTE_KIND_TYPE).layout(
                ("proposal_id", "vote")))

        # Check that the proposal exists
        proposal = sp.compute(self.data.proposals.get(
            params.proposal_id, message="DAO_INEXISTENT_PROPOSAL"))

        # Check that the proposal status is still set as open
        sp.verify(proposal.status.is_variant("open"),
                  message="DAO_STATUS_NOT_OPEN")

        # Check that the proposal voting period didn't expire
        end_date = proposal.timestamp.add_days(
            sp.to_int(self.data.governance_parameters.vote_period))
        sp.verify(sp.now < end_date, message="DAO_CLOSED_PROPOSAL")

        # Get the representative community
        community = sp.view(
            name="get_representative_community",
            address=self.data.representatives,
            param=sp.sender,
            t=sp.TString).open_some()

        # Check that the representative didn't vote the proposal before
        vote_key = sp.compute(sp.pair(params.proposal_id, community))
        sp.verify(~self.data.representatives_votes.contains(vote_key),
                  message="DAO_ALREADY_VOTED")

        # Update the representatives votes summary
        new_votes = sp.local("new_votes", proposal.representatives_votes)
        new_votes.value.total += 1
        new_votes.value.participation += 1

        with params.vote.match_cases() as arg:
            with arg.match("yes"):
                new_votes.value.positive += 1
            with arg.match("no"):
                new_votes.value.negative += 1
            with arg.match("abstain"):
                new_votes.value.abstain += 1

        self.data.proposals[params.proposal_id].representatives_votes = new_votes.value

        # Add the vote to the representatives votes big map
        self.data.representatives_votes[vote_key] = params.vote

    @sp.entry_point
    def cancel_proposal(self, params):
        """Cancels an open proposal.

        """
        # Define the input parameter data type
        sp.set_type(params, sp.TRecord(
            proposal_id=sp.TNat,
            return_escrow=sp.TBool).layout(
                ("proposal_id", "return_escrow")))

        # Check that the proposal exists
        proposal = sp.compute(self.data.proposals.get(
            params.proposal_id, message="DAO_INEXISTENT_PROPOSAL"))

        # Check that the address that called the entry point is the proposal
        # issuer or the DAO guardians
        sp.verify((sp.sender == proposal.issuer) | 
                  (sp.sender == self.data.guardians),
                  message="DAO_NOT_ISSUER_OR_GUARDIANS")

        # Check that the proposal status is set as open or approved
        sp.verify(proposal.status.is_variant("open") | 
                  proposal.status.is_variant("approved"),
                  message="DAO_STATUS_NOT_OPEN_OR_APPROVED")

        # Check if there are still some DAO tokens in escrow
        with sp.if_((proposal.escrow_amount > 0) & proposal.status.is_variant("open")):
            # Make sure that we don't divide by zero in the next steps
            representatives_votes_total = sp.local("representatives_votes_total", proposal.representatives_votes.total)

            with sp.if_(representatives_votes_total.value == 0):
                representatives_votes_total.value = 1

            # Calculate the representatives votes based on the current quorum
            representatives_total = sp.compute(self.data.quorum * self.data.governance_parameters.representatives_share) // 100
            representatives_positive = (representatives_total * proposal.representatives_votes.positive) // representatives_votes_total.value
            representatives_negative = (representatives_total * proposal.representatives_votes.negative) // representatives_votes_total.value

            # Count the total positive and negative votes
            positive = sp.compute(proposal.token_votes.positive + representatives_positive)
            positive_and_negative = positive + proposal.token_votes.negative + representatives_negative

            # Check which address should receive the DAO tokens
            receiver = sp.local("receiver", self.data.treasury)
            return_escrow = params.return_escrow & (positive > ((positive_and_negative * self.data.governance_parameters.escrow_return) // 100))

            with sp.if_(return_escrow):
                receiver.value = proposal.issuer

            # Transfer the DAO tokens
            self.transfer_tokens(sp.record(
                token=self.data.token,
                from_=sp.self_address,
                to_=receiver.value,
                amount=proposal.escrow_amount))

        # Set the proposal status as cancelled
        self.data.proposals[params.proposal_id].status = sp.variant("cancelled", sp.unit)

    @sp.entry_point
    def evaluate_voting_result(self, proposal_id):
        """Evaluates the voting result of a given proposal.

        """
        # Define the input parameter data type
        sp.set_type(proposal_id, sp.TNat)

        # Check that one of the DAO members executed the entry point
        self.check_is_dao_member(self.data.token)

        # Check that the proposal exists
        proposal = sp.compute(self.data.proposals.get(
            proposal_id, message="DAO_INEXISTENT_PROPOSAL"))

        # Check that the proposal status is still set as open
        sp.verify(proposal.status.is_variant("open"),
                  message="DAO_STATUS_NOT_OPEN")

        # Check that the proposal voting period has finished
        end_date = proposal.timestamp.add_days(
            sp.to_int(self.data.governance_parameters.vote_period))
        sp.verify(sp.now > end_date, message="DAO_OPEN_PROPOSAL")

        # Make sure that we don't divide by zero in the next steps
        representatives_votes_total = sp.local("representatives_votes_total", proposal.representatives_votes.total)

        with sp.if_(representatives_votes_total.value == 0):
            representatives_votes_total.value = 1

        # Calculate the representatives votes based on the current quorum
        representatives_total = sp.compute(self.data.quorum * self.data.governance_parameters.representatives_share) // 100
        representatives_positive = (representatives_total * proposal.representatives_votes.positive) // representatives_votes_total.value
        representatives_negative = (representatives_total * proposal.representatives_votes.negative) // representatives_votes_total.value

        # Count the total votes
        total = sp.compute(proposal.token_votes.total + representatives_total)
        positive = sp.compute(proposal.token_votes.positive + representatives_positive)
        positive_and_negative = sp.compute(positive + proposal.token_votes.negative + representatives_negative)

        # Check if there are some DAO tokens in escrow
        with sp.if_(proposal.escrow_amount > 0):
            # Check which address should receive the DAO tokens
            receiver = sp.local("receiver", self.data.treasury)
            return_escrow = positive > ((positive_and_negative * self.data.governance_parameters.escrow_return) // 100)

            with sp.if_(return_escrow):
                receiver.value = proposal.issuer

            # Transfer the DAO tokens
            self.transfer_tokens(sp.record(
                token=self.data.token,
                from_=sp.self_address,
                to_=receiver.value,
                amount=proposal.escrow_amount))

        # Check if the proposal passed the required thresholds to be approved
        passed_supermajority = sp.compute(positive > ((positive_and_negative * self.data.governance_parameters.supermajority) // 100))
        passed_quorum = total > self.data.quorum

        # Set the proposal status as rejected or approved depending on the result
        new_status = sp.local("new_status", sp.variant("rejected", sp.unit))

        with sp.if_(passed_supermajority & passed_quorum):
            new_status.value = sp.variant("approved", sp.unit)

        self.data.proposals[proposal_id].status = new_status.value

        # Check if the quorum can be updated
        # To minimize the effect of spam proposals, quorum updates cannot be too
        # often and can only happen for proposals that had a super-majority
        min_quorum_update_date = self.data.last_quorum_update.add_days(
            sp.to_int(self.data.governance_parameters.quorum_update_period))

        with sp.if_((sp.now > min_quorum_update_date) & passed_supermajority):
            # Calculate the new quorum value
            old_quorum_contribution = self.data.quorum * sp.as_nat(100 - self.data.governance_parameters.quorum_update)
            proposal_contribution = total * self.data.governance_parameters.quorum_update
            new_quorum = sp.local("new_quorum", (old_quorum_contribution + proposal_contribution) // 100)

            # Check that the quorum doesn't decrease or increase too fast
            min_quorum = sp.compute((self.data.quorum * sp.as_nat(100 - self.data.governance_parameters.quorum_max_change)) // 100)
            max_quorum = sp.compute((self.data.quorum * (100 + self.data.governance_parameters.quorum_max_change)) // 100)

            with sp.if_(new_quorum.value < min_quorum):
                new_quorum.value = min_quorum

            with sp.if_(new_quorum.value > max_quorum):
                new_quorum.value = max_quorum

            # Check that the new quorum value stays within the limits
            with sp.if_(new_quorum.value < self.data.governance_parameters.min_quorum):
                new_quorum.value = self.data.governance_parameters.min_quorum

            with sp.if_(new_quorum.value > self.data.governance_parameters.max_quorum):
                new_quorum.value = self.data.governance_parameters.max_quorum

            # Update the quorum parameters
            self.data.quorum = new_quorum.value
            self.data.last_quorum_update = sp.now

    @sp.entry_point
    def execute_proposal(self, proposal_id):
        """Executes a given proposal.

        """
        # Define the input parameter data type
        sp.set_type(proposal_id, sp.TNat)

        # Check that one of the DAO members executed the entry point
        self.check_is_dao_member(self.data.token)

        # Check that the proposal exists
        proposal = sp.compute(self.data.proposals.get(
            proposal_id, message="DAO_INEXISTENT_PROPOSAL"))

        # Check that the proposal is approved
        sp.verify(proposal.status.is_variant("approved"),
                  message="DAO_STATUS_NOT_APPROVED")

        # Check that the proposal wating period has finished
        end_date = proposal.timestamp.add_days(sp.to_int(
            self.data.governance_parameters.vote_period + 
            self.data.governance_parameters.wait_period))
        sp.verify(sp.now > end_date, message="DAO_WAITING_PROPOSAL")

        # Set the proposal status as executed
        self.data.proposals[proposal_id].status = sp.variant(
            "executed", sp.unit)

        # Execute the proposal
        with proposal.kind.match_cases() as arg:
            with arg.match("transfer_mutez") as mutez_transfers:
                # Get a handle to the DAO treasury transfer mutez entry point
                transfer_mutez_handle = sp.contract(
                    t=DAOGovernance.MUTEZ_TRANSFERS_TYPE,
                    address=self.data.treasury,
                    entry_point="transfer_mutez").open_some()

                # Execute the tranfer
                sp.transfer(
                    arg=mutez_transfers,
                    amount=sp.mutez(0),
                    destination=transfer_mutez_handle)
            with arg.match("transfer_token") as token_transfers:
                # Get a handle to the DAO treasury transfer token entry point
                transfer_token_handle = sp.contract(
                    t=DAOGovernance.TOKEN_TRANSFERS_TYPE,
                    address=self.data.treasury,
                    entry_point="transfer_token").open_some()

                # Execute the tranfer
                sp.transfer(
                    arg=token_transfers,
                    amount=sp.mutez(0),
                    destination=transfer_token_handle)
            with arg.match("lambda_function") as lambda_function:
                # Execute the lambda function
                operations = lambda_function(sp.unit)
                sp.add_operations(operations)

    @sp.entry_point
    def set_treasury(self, new_treasury):
        """Updates the DAO treasury contract address.

        """
        # Define the input parameter data type
        sp.set_type(new_treasury, sp.TAddress)

        # Check that the DAO or the DAO aministrator executed the entry point
        sp.verify((sp.sender == sp.self_address) | 
                  (sp.sender == self.data.administrator),
                  message="DAO_NOT_DAO_OR_ADMIN")

        # Update the DAO treasury contract address
        self.data.treasury = new_treasury

    @sp.entry_point
    def set_representatives(self, new_representatives):
        """Updates the community representatives contract address.

        """
        # Define the input parameter data type
        sp.set_type(new_representatives, sp.TAddress)

        # Check that the DAO or the representatives executed the entry point
        sp.verify((sp.sender == sp.self_address) | 
                  (sp.sender == self.data.representatives),
                  message="DAO_NOT_DAO_OR_REPRESENTATIVES")

        # Update the representatives contract address
        self.data.representatives = new_representatives

    @sp.entry_point
    def set_guardians(self, new_guardians):
        """Updates the DAO guardians contract address.

        """
        # Define the input parameter data type
        sp.set_type(new_guardians, sp.TAddress)

        # Check that the DAO or the guardians executed the entry point
        sp.verify((sp.sender == sp.self_address) | 
                  (sp.sender == self.data.guardians),
                  message="DAO_NOT_DAO_OR_GUARDIANS")

        # Update the DAO guardians contract address
        self.data.guardians = new_guardians

    @sp.entry_point
    def set_quorum(self, new_quorum):
        """Updates the DAO quorum.

        """
        # Define the input parameter data type
        sp.set_type(new_quorum, sp.TNat)

        # Check that the DAO or the DAO aministrator executed the entry point
        sp.verify((sp.sender == sp.self_address) | 
                  (sp.sender == self.data.administrator),
                  message="DAO_NOT_DAO_OR_ADMIN")

        # Update the DAO quorum parameter
        self.data.quorum = new_quorum

    @sp.entry_point
    def set_governance_parameters(self, new_governance_parameters):
        """Updates the DAO governance parameters.

        """
        # Define the input parameter data type
        sp.set_type(new_governance_parameters,
                    DAOGovernance.GOVERNANCE_PARAMETERS_TYPE)

        # Check that the DAO or the DAO aministrator executed the entry point
        sp.verify((sp.sender == sp.self_address) | 
                  (sp.sender == self.data.administrator),
                  message="DAO_NOT_DAO_OR_ADMIN")

        # Update the governance parameters
        self.data.governance_parameters = new_governance_parameters

    @sp.entry_point(private=True)
    def get_integer_square_root(self, number):
        """Returns the square root of the given number.

        Note that this is a private entrypoint only used for testing purposes.

        """
        # Define the input parameter data type
        sp.set_type(number, sp.TNat)

        # Store the result in the counter just for test purposes
        self.data.counter = self.integer_square_root(number)


sp.add_compilation_target("dao", DAOGovernance(
    metadata=sp.utils.metadata_of_url("ipfs://aaa"),
    administrator=sp.address("KT1QmSmQ8Mj8JHNKKQmepFqQZy7kDWQ1ekaa"),
    treasury=sp.address("KT1QmSmQ8Mj8JHNKKQmepFqQZy7kDWQ1ekbb"),
    token=sp.address("KT1QmSmQ8Mj8JHNKKQmepFqQZy7kDWQ1ekcc"),
    representatives=sp.address("KT1QmSmQ8Mj8JHNKKQmepFqQZy7kDWQ1ekdd"),
    guardians=sp.address("KT1QmSmQ8Mj8JHNKKQmepFqQZy7kDWQ1ekee"),
    quorum=8000,
    governance_parameters=sp.record(
        vote_method=sp.variant("linear", sp.unit),
        vote_period=5,
        wait_period=2,
        escrow_amount=100,
        escrow_return=30,
        min_amount=1,
        supermajority=70,
        representatives_share=30,
        quorum_update_period=10,
        quorum_update=20,
        quorum_max_change=20,
        min_quorum=1000,
        max_quorum=100000)))
