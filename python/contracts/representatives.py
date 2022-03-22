import smartpy as sp

# Import the Teia multisig wallet contract module
multisig = sp.io.import_script_from_url("file:contracts/multisigWallet_v1.py")


class Representatives(multisig.MultisigWallet):
    """This contract implements a basic multisig wallet / mini-DAO for the 
    Teia community representatives.

    """

    VOTE_KIND_TYPE = sp.TVariant(
        # A positive vote
        yes=sp.TUnit,
        # A negative vote
        no=sp.TUnit,
        # An abstain vote
        abstain=sp.TUnit)

    def __init__(self, metadata, users, dao, minimum_votes,
                 expiration_time=sp.nat(5)):
        """Initializes the contract.

        """
        # Define the contract storage data types for clarity
        self.init_type(sp.TRecord(
            # The contract metadata
            metadata=sp.TBigMap(sp.TString, sp.TBytes),
            # The Teia community representatives
            users=sp.TSet(sp.TAddress),
            # The DAO governance contract address
            dao=sp.TAddress,
            # The big map with the proposals information
            proposals=sp.TBigMap(sp.TNat, Representatives.PROPOSAL_TYPE),
            # The big map with the votes information
            votes=sp.TBigMap(sp.TPair(sp.TNat, sp.TAddress), sp.TBool),
            # The minimum number of positive votes needed to execute a proposal
            minimum_votes=sp.TNat,
            # The proposals expiration time in days
            expiration_time=sp.TNat,
            # The proposals counter
            counter=sp.TNat))

        # Initialize the contract storage
        self.init(
            metadata=metadata,
            users=users,
            dao=dao,
            proposals=sp.big_map(),
            votes=sp.big_map(),
            minimum_votes=minimum_votes,
            expiration_time=expiration_time,
            counter=0)

    @sp.entry_point
    def vote_dao_proposal(self, params):
        """Votes a DAO proposal as a representative.

        """
        # Define the input parameter data type
        sp.set_type(params, sp.TRecord(
            proposal_id=sp.TNat,
            vote=Representatives.VOTE_KIND_TYPE).layout(
                ("proposal_id", "vote")))

        # Check that one of the users executed the entry point
        self.check_is_user()

        # Get a handle to the DAO representatives vote entry point
        representatives_vote_handle = sp.contract(
            t=sp.TRecord(
                proposal_id=sp.TNat,
                vote=Representatives.VOTE_KIND_TYPE,
                representative=sp.TAddress).layout(
                    ("proposal_id", ("vote", "representative"))),
            address=self.data.dao,
            entry_point="representatives_vote").open_some()

        # Vote as a representative the DAO proposal
        sp.transfer(
            arg=sp.record(
                proposal_id=params.proposal_id,
                vote=params.vote,
                representative=sp.sender),
            amount=sp.mutez(0),
            destination=representatives_vote_handle)

    @sp.entry_point
    def set_dao(self, new_dao):
        """Updates the DAO contract address.

        """
        # Define the input parameter data type
        sp.set_type(new_dao, sp.TAddress)

        # Check that the multisig itself executed the entry point
        sp.verify(sp.sender == sp.self_address, message="MS_NOT_MULTISIG")

        # Update the DAO contract address
        self.data.dao = new_dao


sp.add_compilation_target("representatives", Representatives(
    metadata=sp.utils.metadata_of_url("ipfs://aaa"),
    users=sp.set([sp.address("tz1g6JRCpsEnD2BLiAzPNK3GBD1fKicV9rCx")]),
    dao=sp.address("KT1QmSmQ8Mj8JHNKKQmepFqQZy7kDWQ1ekbb"),
    minimum_votes=sp.nat(1),
    expiration_time=sp.nat(7)))
