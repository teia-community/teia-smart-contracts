import smartpy as sp


class DAOTreasury(sp.Contract):
    """This contract implements a DAO treasury that can hold tez and tokens.

    """

    MUTEZ_TRANSFERS_TYPE = sp.TList(sp.TRecord(
        # The amount of mutez to transfer
        amount=sp.TMutez,
        # The transfer destination
        destination=sp.TAddress).layout(("amount", "destination")))

    FA2_TOKEN_TRANSFERS_TYPE = sp.TRecord(
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

    FA12_TOKEN_TRANSFERS_TYPE = sp.TRecord(
        # The token contract address
        fa12=sp.TAddress,
        # The token transfer distribution
        distribution=sp.TList(sp.TRecord(
            # The number of token editions to transfer
            amount=sp.TNat,
            # The transfer destination
            destination=sp.TAddress).layout(("amount", "destination")))).layout(
                ("fa12", "distribution"))

    FA2_TX_TYPE = sp.TRecord(
        # The token destination
        to_=sp.TAddress,
        # The token id
        token_id=sp.TNat,
        # The number of token editions
        amount=sp.TNat).layout(("to_", ("token_id", "amount")))

    def __init__(self, metadata, administrator):
        """Initializes the contract.

        """
        # Define the contract storage data types for clarity
        self.init_type(sp.TRecord(
            # The contract metadata
            metadata=sp.TBigMap(sp.TString, sp.TBytes),
            # The contract administrator
            administrator=sp.TAddress,
            # The proposed new administrator address
            proposed_administrator=sp.TOption(sp.TAddress)))

        # Initialize the contract storage
        self.init(
            metadata=metadata,
            administrator=administrator,
            proposed_administrator=sp.none)

        # Fill the contract metadata
        self.contract_metadata = {
            "name": "Teia DAO treasury contract",
            "description": "Treasury contract used for the Teia DAO",
            "version": "1.0.0",
            "authors": ["Teia Community <https://twitter.com/TeiaCommunity>"],
            "homepage": "https://teia.art",
            "source": {
                "tools": ["SmartPy 0.16.0"],
                "location": "https://github.com/teia-community/teia-smart-contracts/blob/main/python/contracts/daoTreasury.py"
            },
            "license": {
                "name": "MIT",
                "details": "The MIT License"
            },
            "interfaces": ["TZIP-016"],
            "errors": [ {"error": {"string": "TREASURY_NOT_ADMIN"},
                         "expansion": {"string": "The account that executed the entry point is not the contract administrator"},
                         "languages": ["en"]},
                        {"error": {"string": "TREASURY_NO_NEW_ADMIN"},
                         "expansion": {"string": "The new administrator has not been proposed"},
                         "languages": ["en"]},
                        {"error": {"string": "TREASURY_NOT_PROPOSED_ADMIN"},
                         "expansion": {"string": "The operation can only be executed by the proposed administrator"},
                         "languages": ["en"]}]}
        self.init_metadata("contract_metadata", self.contract_metadata)

    def check_is_administrator(self):
        """Checks that the address that called the entry point is the contract
        administrator.

        """
        sp.verify(sp.sender == self.data.administrator,
                  message="TREASURY_NOT_ADMIN")

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

        # Check that the administrator executed the entry point
        self.check_is_administrator()

        # Transfer the mutez to the list of addresses
        with sp.for_("mutez_transfer", mutez_transfers) as mutez_transfer:
            sp.send(mutez_transfer.destination, mutez_transfer.amount)

    @sp.entry_point
    def transfer_fa2_token(self, token_transfers):
        """Transfers a FA2 token to a list of addresses.

        """
        # Define the input parameter data type
        sp.set_type(token_transfers, DAOTreasury.FA2_TOKEN_TRANSFERS_TYPE)

        # Check that the administrator executed the entry point
        self.check_is_administrator()

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
    def transfer_fa12_token(self, token_transfers):
        """Transfers a FA12 token to a list of addresses.

        """
        # Define the input parameter data type
        sp.set_type(token_transfers, DAOTreasury.FA12_TOKEN_TRANSFERS_TYPE)

        # Check that the administrator executed the entry point
        self.check_is_administrator()

        # Get a handle to the token transfer entry point
        token_transfer_handle = sp.contract(
            t=sp.TRecord(
                from_=sp.TAddress,
                to_=sp.TAddress,
                value=sp.TNat).layout(("from_ as from", ("to_ as to", "value"))),
            address=token_transfers.fa12,
            entry_point="transfer").open_some()

        # Execute the transfers
        with sp.for_("distribution", token_transfers.distribution) as distribution:
            sp.transfer(
                arg=sp.record(
                    from_=sp.self_address,
                    to_=distribution.destination,
                    value=distribution.amount),
                amount=sp.mutez(0),
                destination=token_transfer_handle)

    @sp.entry_point
    def transfer_administrator(self, proposed_administrator):
        """Proposes to transfer the contract administrator to another address.

        """
        # Define the input parameter data type
        sp.set_type(proposed_administrator, sp.TAddress)

        # Check that the administrator executed the entry point
        self.check_is_administrator()

        # Set the new proposed administrator address
        self.data.proposed_administrator = sp.some(proposed_administrator)

    @sp.entry_point
    def accept_administrator(self):
        """The proposed administrator accepts the contract administrator
        responsibilities.

        """
        # Check that the proposed administrator executed the entry point
        sp.verify(sp.sender == self.data.proposed_administrator.open_some(
            "TREASURY_NO_NEW_ADMIN"), message="TREASURY_NOT_PROPOSED_ADMIN")

        # Set the new administrator address
        self.data.administrator = sp.sender

        # Reset the proposed administrator value
        self.data.proposed_administrator = sp.none

    @sp.entry_point
    def set_delegate(self, new_baker):
        """Delegates the contract stored tez to the given baker address.

        """
        # Define the input parameter data type
        sp.set_type(new_baker, sp.TOption(sp.TKeyHash))

        # Check that the administrator executed the entry point
        self.check_is_administrator()

        # Update the baker address
        sp.set_delegate(new_baker)


sp.add_compilation_target("daoTreasury", DAOTreasury(
    metadata=sp.utils.metadata_of_url("ipfs://QmewNgfyryssmkFHnr46vPDXeA8JiDMyfViDhNGSb8Voe4"),
    administrator=sp.address("tz1gnL9CeM5h5kRzWZztFYLypCNnVQZjndBN")))
