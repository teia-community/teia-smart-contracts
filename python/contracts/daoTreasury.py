import smartpy as sp


class DAOTreasury(sp.Contract):
    """This contract implements a DAO treasury that can hold tez and tokens.

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

    FA2_TX_TYPE = sp.TRecord(
        # The token destination
        to_=sp.TAddress,
        # The token id
        token_id=sp.TNat,
        # The number of token editions
        amount=sp.TNat).layout(("to_", ("token_id", "amount")))

    def __init__(self, metadata, dao):
        """Initializes the contract.

        """
        # Define the contract storage data types for clarity
        self.init_type(sp.TRecord(
            # The contract metadata
            metadata=sp.TBigMap(sp.TString, sp.TBytes),
            # The DAO contract address
            dao=sp.TAddress))

        # Initialize the contract storage
        self.init(
            metadata=metadata,
            dao=dao)

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
    def transfer_mutez(self, mutez_transfers):
        """Transfers some tez to a list of addresses.

        """
        # Define the input parameter data type
        sp.set_type(mutez_transfers, DAOTreasury.MUTEZ_TRANSFERS_TYPE)

        # Check that the DAO contract executed the entry point
        sp.verify(sp.sender == self.data.dao, message="TREASURY_NOT_DAO")

        # Transfer the mutez to the list of addresses
        with sp.for_("mutez_transfer", mutez_transfers) as mutez_transfer:
            sp.send(mutez_transfer.destination, mutez_transfer.amount)

    @sp.entry_point
    def transfer_token(self, token_transfers):
        """Transfers a token to a list of addresses.

        """
        # Define the input parameter data type
        sp.set_type(token_transfers, DAOTreasury.TOKEN_TRANSFERS_TYPE)

        # Check that the DAO contract executed the entry point
        sp.verify(sp.sender == self.data.dao, message="TREASURY_NOT_DAO")

        # Build the FA2 transactions list
        txs = sp.local("txs", sp.list(t=DAOTreasury.FA2_TX_TYPE))

        with sp.for_("distribution", token_transfers.distribution) as distribution:
            txs.value.push(sp.record(
                to_=distribution.destination,
                token_id=token_transfers.token_id,
                amount=distribution.amount))

        # Get a handle to the token transfer entry point
        token_transfer_handle = sp.contract(
            t=sp.TList(sp.TRecord(
                from_=sp.TAddress,
                txs=sp.TList(DAOTreasury.FA2_TX_TYPE))),
            address=token_transfers.fa2,
            entry_point="transfer").open_some()

        # Execute the transfer
        sp.transfer(
            arg=sp.list([sp.record(
                from_=sp.self_address,
                txs=txs.value)]),
            amount=sp.mutez(0),
            destination=token_transfer_handle)

    @sp.entry_point
    def set_dao(self, new_dao):
        """Updates the DAO contract address.

        """
        # Define the input parameter data type
        sp.set_type(new_dao, sp.TAddress)

        # Check that the DAO contract executed the entry point
        sp.verify(sp.sender == self.data.dao, message="TREASURY_NOT_DAO")

        # Update the DAO contract address
        self.data.dao = new_dao

    @sp.entry_point
    def set_delegate(self, new_baker):
        """Delegates the contract stored tez to the given baker address.

        """
        # Define the input parameter data type
        sp.set_type(new_baker, sp.TOption(sp.TKeyHash))

        # Check that the DAO contract executed the entry point
        sp.verify(sp.sender == self.data.dao, message="TREASURY_NOT_DAO")

        # Update the baker address
        sp.set_delegate(new_baker)


sp.add_compilation_target("daoTreasury", DAOTreasury(
    metadata=sp.utils.metadata_of_url("ipfs://aaa"),
    dao=sp.address("KT1QmSmQ8Mj8JHNKKQmepFqQZy7kDWQ1ekaa")))
