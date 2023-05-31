import smartpy as sp


class Representatives(sp.Contract):
    """This contract implements a basic multisig wallet / mini-DAO for the 
    Teia community representatives.

    """

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

    REPRESENTATIVE_TYPE = sp.TRecord(
        # The representative address
        address=sp.TAddress,
        # The represented community
        community=sp.TString).layout(
            ("address", "community"))

    LAMBDA_FUNCTION_TYPE = sp.TLambda(sp.TUnit, sp.TList(sp.TOperation))

    PROPOSAL_KIND_TYPE = sp.TVariant(
        # A proposal in the form of text to be voted for
        text=sp.TBytes,
        # A proposal to transfer mutez from the contract to other accounts
        transfer_mutez=MUTEZ_TRANSFERS_TYPE,
        # A proposal to transfer a FA2 token from the contract to other accounts
        transfer_token=TOKEN_TRANSFERS_TYPE,
        # A proposal to execute a lambda function
        lambda_function=LAMBDA_FUNCTION_TYPE,
        # A proposal to add a new representative
        add_representative=REPRESENTATIVE_TYPE,
        # A proposal to remove an existing representative
        remove_representative=REPRESENTATIVE_TYPE,
        # A proposal to change the minimum votes parameter
        minimum_votes=sp.TNat,
        # A proposal to change the expiration time parameter
        expiration_time=sp.TNat)

    PROPOSAL_TYPE = sp.TRecord(
        # The kind of proposal: text, transfer_mutez, transfer_token, etc
        kind=PROPOSAL_KIND_TYPE,
        # The representative that submitted the proposal
        issuer=REPRESENTATIVE_TYPE,
        # The timestamp when the proposal was submitted
        timestamp=sp.TTimestamp,
        # Flag to indicate if the proposal has been already executed
        executed=sp.TBool,
        # The number of positive votes that the proposal has received
        positive_votes=sp.TNat).layout(
            ("kind", ("issuer", ("timestamp", ("executed", "positive_votes")))))

    FA2_TX_TYPE = sp.TRecord(
        # The token destination
        to_=sp.TAddress,
        # The token id
        token_id=sp.TNat,
        # The number of token editions
        amount=sp.TNat).layout(
            ("to_", ("token_id", "amount")))

    FA2_TRANSFER_TYPE = sp.TList(sp.TRecord(
        # The address that sends the token editions
        from_=sp.TAddress,
        # The list of token transfers
        txs=sp.TList(FA2_TX_TYPE)).layout(
                ("from_", "txs")))

    def __init__(self, metadata, representatives, minimum_votes, expiration_time):
        """Initializes the contract.

        """
        # Define the contract storage data types for clarity
        self.init_type(sp.TRecord(
            # The contract metadata
            metadata=sp.TBigMap(sp.TString, sp.TBytes),
            # The Teia community representatives
            representatives=sp.TMap(sp.TAddress, sp.TString),
            # The Teia communities represented in the contract
            communities=sp.TSet(sp.TString),
            # The minimum number of positive votes needed to execute a proposal
            minimum_votes=sp.TNat,
            # The proposals expiration time in days
            expiration_time=sp.TNat,
            # The big map with the proposals information
            proposals=sp.TBigMap(sp.TNat, Representatives.PROPOSAL_TYPE),
            # The big map with the votes information
            votes=sp.TBigMap(sp.TPair(sp.TNat, sp.TString), sp.TBool),
            # The proposals counter
            counter=sp.TNat))

        # Initialize the contract storage
        self.init(
            metadata=metadata,
            representatives=representatives,
            communities=sp.set(representatives.values()),
            minimum_votes=minimum_votes,
            expiration_time=expiration_time,
            proposals=sp.big_map(),
            votes=sp.big_map(),
            counter=0)

        # Fill the contract metadata
        self.contract_metadata = {
            "name": "Teia representatives multisig wallet / mini-DAO",
            "description": "Multisig wallet contract used for the Teia representatives",
            "version": "1.0.0",
            "authors": ["Teia Community <https://twitter.com/TeiaCommunity>"],
            "homepage": "https://teia.art",
            "source": {
                "tools": ["SmartPy 0.16.0"],
                "location": "https://github.com/teia-community/teia-smart-contracts/blob/main/python/contracts/representatives.py"
            },
            "license": {
                "name": "MIT",
                "details": "The MIT License"
            },
            "interfaces": ["TZIP-016"],
            "errors": [ {"error": {"string": "REPS_NOT_REPRESENTATIVE"},
                         "expansion": {"string": "The operation can only be executed by one of the representatives"},
                         "languages": ["en"]},
                        {"error": {"string": "REPS_ADDRESS_EXISTS"},
                         "expansion": {"string": "The proposed address is already in the representatives list"},
                         "languages": ["en"]},
                        {"error": {"string": "REPS_COMMUNITY_EXISTS"},
                         "expansion": {"string": "The proposed community is already in the representatives list"},
                         "languages": ["en"]},
                        {"error": {"string": "REPS_WRONG_ADDRESS"},
                         "expansion": {"string": "The proposed address is not from a representative"},
                         "languages": ["en"]},
                        {"error": {"string": "REPS_WRONG_COMMUNITY"},
                         "expansion": {"string": "The proposed community is not from a representative"},
                         "languages": ["en"]},
                        {"error": {"string": "REPS_WRONG_MINIMUM_VOTES"},
                         "expansion": {"string": "The minimum_votes parameter cannot be smaller than one or higher than the number of representatives"},
                         "languages": ["en"]},
                        {"error": {"string": "REPS_WRONG_EXPIRATION_TIME"},
                         "expansion": {"string": "The expiration_time parameter cannot be smaller than one day"},
                         "languages": ["en"]},
                        {"error": {"string": "REPS_INEXISTENT_PROPOSAL"},
                         "expansion": {"string": "The given proposal id does not exist"},
                         "languages": ["en"]},
                        {"error": {"string": "REPS_EXECUTED_PROPOSAL"},
                         "expansion": {"string": "The proposal has been executed and cannot be voted or executed anymore"},
                         "languages": ["en"]},
                        {"error": {"string": "REPS_EXPIRED_PROPOSAL"},
                         "expansion": {"string": "The proposal has expired and cannot be voted or executed anymore"},
                         "languages": ["en"]},
                        {"error": {"string": "REPS_NOT_EXECUTABLE"},
                         "expansion": {"string": "The proposal did not receive enough positive votes to be executed"},
                         "languages": ["en"]},
                        {"error": {"string": "REPS_LAST_REPRESENTATIVE"},
                         "expansion": {"string": "The last representative cannot be removed"},
                         "languages": ["en"]}]}
        self.init_metadata("contract_metadata", self.contract_metadata)

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
    def add_proposal(self, kind):
        """Adds a new proposal to the proposals big map.

        """
        # Define the input parameter data type
        sp.set_type(kind, Representatives.PROPOSAL_KIND_TYPE)

        # Check that one of the representatives executed the entry point
        community = self.data.representatives.get(
            sp.sender, message="REPS_NOT_REPRESENTATIVE")

        # Check that the proposals parameters make sense
        with kind.match_cases() as arg:
            with arg.match("add_representative") as representative:
                # Check that the representative doesn't exist
                sp.verify(~self.data.representatives.contains(representative.address),
                          message="REPS_ADDRESS_EXISTS")
                sp.verify(~self.data.communities.contains(representative.community),
                          message="REPS_COMMUNITY_EXISTS")

            with arg.match("remove_representative") as representative:
                # Check that the representative exists
                sp.verify(self.data.representatives.contains(representative.address),
                          message="REPS_WRONG_ADDRESS")
                sp.verify(self.data.representatives[representative.address] == representative.community,
                          message="REPS_WRONG_COMMUNITY")

            with arg.match("minimum_votes") as minimum_votes:
                # Check that the minimum votes parameter is at least 1 vote
                sp.verify(minimum_votes >= 1,
                          message="REPS_WRONG_MINIMUM_VOTES")

            with arg.match("expiration_time") as expiration_time:
                # Check that the expiration time parameter is at least 1 day
                sp.verify(expiration_time >= 1,
                          message="REPS_WRONG_EXPIRATION_TIME")

        # Add the new proposal information to the proposals big map
        self.data.proposals[self.data.counter] = sp.record(
            kind=kind,
            issuer=sp.record(
                address=sp.sender,
                community=community),
            timestamp=sp.now,
            executed=False,
            positive_votes=0)

        # Increase the proposals counter
        self.data.counter += 1

    @sp.entry_point
    def vote_proposal(self, params):
        """Adds one vote for a given proposal.

        """
        # Define the input parameter data type
        sp.set_type(params, sp.TRecord(
            proposal_id=sp.TNat,
            approval=sp.TBool).layout(("proposal_id", "approval")))

        # Check that one of the representatives executed the entry point
        community = self.data.representatives.get(
            sp.sender, message="REPS_NOT_REPRESENTATIVE")

        # Check that the proposal exists
        proposal = sp.compute(self.data.proposals.get(
            params.proposal_id, message="REPS_INEXISTENT_PROPOSAL"))

        # Check that the proposal has not been executed
        sp.verify(~proposal.executed, message="REPS_EXECUTED_PROPOSAL")

        # Check that the proposal has not expired
        expiration_date = proposal.timestamp.add_days(
            sp.to_int(self.data.expiration_time))
        sp.verify(sp.now <= expiration_date, message="REPS_EXPIRED_PROPOSAL")

        # Check if the representative voted positive before and remove their
        # previous vote from the proposal positive votes counter
        positive_votes = sp.local("positive_votes", proposal.positive_votes)
        vote_key = sp.compute(sp.pair(params.proposal_id, community))

        with sp.if_(self.data.votes.get(vote_key, default_value=False)):
            positive_votes.value = sp.as_nat(positive_votes.value - 1)

        # Add the vote to the proposal positive votes counter if it's positive
        with sp.if_(params.approval):
            positive_votes.value += 1

        self.data.proposals[params.proposal_id].positive_votes = positive_votes.value

        # Add or update the representatives vote
        self.data.votes[vote_key] = params.approval

    @sp.entry_point
    def execute_proposal(self, proposal_id):
        """Executes a given proposal.

        """
        # Define the input parameter data type
        sp.set_type(proposal_id, sp.TNat)

        # Check that one of the representatives executed the entry point
        sp.verify(self.data.representatives.contains(sp.sender),
                  message="REPS_NOT_REPRESENTATIVE")

        # Check that the proposal exists
        proposal = sp.compute(self.data.proposals.get(
            proposal_id, message="REPS_INEXISTENT_PROPOSAL"))

        # Check that the proposal has not been executed
        sp.verify(~proposal.executed, message="REPS_EXECUTED_PROPOSAL")

        # Check that the proposal has not expired
        expiration_date = proposal.timestamp.add_days(
            sp.to_int(self.data.expiration_time))
        sp.verify(sp.now <= expiration_date, message="REPS_EXPIRED_PROPOSAL")

        # Check that the proposal received enough positive votes
        sp.verify(proposal.positive_votes >= self.data.minimum_votes,
                  message="REPS_NOT_EXECUTABLE")

        # Set the proposal status as executed
        self.data.proposals[proposal_id].executed = True

        # Execute the proposal
        with proposal.kind.match_cases() as arg:
            with arg.match("transfer_mutez") as mutez_transfers:
                # Send the mutez to the list of destination addresses
                with sp.for_("mutez_transfer", mutez_transfers) as mutez_transfer:
                    sp.send(mutez_transfer.destination, mutez_transfer.amount)

            with arg.match("transfer_token") as token_transfers:
                # Calculate the list of token transactions
                txs = sp.local("txs", sp.list(t=Representatives.FA2_TX_TYPE))

                with sp.for_("distribution", token_transfers.distribution) as distribution:
                    txs.value.push(sp.record(
                        to_=distribution.destination,
                        token_id=token_transfers.token_id,
                        amount=distribution.amount))

                # Get a handle to the FA2 token transfer entry point
                transfer_handle = sp.contract(
                    t=Representatives.FA2_TRANSFER_TYPE,
                    address=token_transfers.fa2,
                    entry_point="transfer").open_some()

                # Execute the transfer
                sp.transfer(
                    arg=sp.list([sp.record(
                        from_=sp.self_address,
                        txs=txs.value)]),
                    amount=sp.mutez(0),
                    destination=transfer_handle)

            with arg.match("lambda_function") as lambda_function:
                # Execute the lambda function
                operations = lambda_function(sp.unit)
                sp.add_operations(operations)

            with arg.match("add_representative") as representative:
                # Check that the representative doesn't exist
                sp.verify(~self.data.representatives.contains(representative.address),
                          message="REPS_ADDRESS_EXISTS")
                sp.verify(~self.data.communities.contains(representative.community),
                          message="REPS_COMMUNITY_EXISTS")

                # Add the new representative
                self.data.representatives[representative.address] = representative.community
                self.data.communities.add(representative.community)

            with arg.match("remove_representative") as representative:
                # Check that the representative exists
                sp.verify(self.data.representatives.contains(representative.address),
                          message="REPS_WRONG_ADDRESS")
                sp.verify(self.data.representatives[representative.address] == representative.community,
                          message="REPS_WRONG_COMMUNITY")

                # Check that it's not the last representative
                sp.verify(sp.len(self.data.representatives) > 1,
                          message="REPS_LAST_REPRESENTATIVE")

                # Remove the representative
                del self.data.representatives[representative.address]
                self.data.communities.remove(representative.community)

                # Update the minimum votes parameter if necessary
                n_representatives = sp.compute(sp.len(self.data.representatives))

                with sp.if_(self.data.minimum_votes > n_representatives):
                    self.data.minimum_votes = n_representatives

            with arg.match("minimum_votes") as minimum_votes:
                # Check that the minimum votes are not larger than the number of
                # representatives
                sp.verify(minimum_votes <= sp.len(self.data.representatives),
                          message="REPS_WRONG_MINIMUM_VOTES")

                # Update the minimum votes parameter
                self.data.minimum_votes = minimum_votes

            with arg.match("expiration_time") as expiration_time:
                # Update the expiration time parameter
                self.data.expiration_time = expiration_time

    @sp.entry_point
    def update_representative_address(self, new_address):
        """Updates the associated address for a community representative.

        """
        # Define the input parameter data type
        sp.set_type(new_address, sp.TAddress)

        # Check that one of the representatives executed the entry point
        community = self.data.representatives.get(
            sp.sender, message="REPS_NOT_REPRESENTATIVE")

        # Check that the new address is not yet a community representative
        sp.verify(~self.data.representatives.contains(new_address),
                  message="REPS_ADDRESS_EXISTS")

        # Replace the representative address
        self.data.representatives[new_address] = community
        del self.data.representatives[sp.sender]

    @sp.onchain_view()
    def get_representative_community(self, address):
        """Returns the representative community

        """
        # Define the input parameter data type
        sp.set_type(address, sp.TAddress)

        # Check that the given address is from a community representative
        community = self.data.representatives.get(
            address, message="REPS_NOT_REPRESENTATIVE")

        # Return the representative community
        sp.result(community)


sp.add_compilation_target("representatives", Representatives(
    metadata=sp.utils.metadata_of_url("ipfs://QmSPr2fiDfnTXq7DemP9Eeh1dhrUwp4QFDDQYUhZKCqnMQ"),
    representatives={
        sp.address("tz1YgDUQV2eXm8pUWNz3S5aWP86iFzNp4jnD"): "desperate tezos bakers",
        sp.address("tz1c5of2FGiz5C5xpKieGAt2abJaz7VwmU9q"): "poor artists community",
        sp.address("tz1h9TG6uuxv2FtmE5yqMyKQqx8hkXk7NY6c"): "not-so-smart contract devs",
        sp.address("tz1gpLc1GQ7zMoSkPLcWmGRhEdoekU3ed6Pe"): "IPFS freaks",
        sp.address("tz1XpohDbFnGbsMqaXtENMHWYYHhMVtBPSTR"): "compulsive writers",
        sp.address("tz1gnL9CeM5h5kRzWZztFYLypCNnVQZjndBN"): "magnificent overlords"
    },
    minimum_votes=sp.nat(2),
    expiration_time=sp.nat(7)))
