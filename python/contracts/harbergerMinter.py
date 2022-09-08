import smartpy as sp


class HarbergerMinter(sp.Contract):
    """This contract implements a basic minter for Harberger fee tokens.

    """

    def __init__(self, metadata):
        """Initializes the contract.

        """
        # Define the contract storage data types for clarity
        self.init_type(sp.TRecord(
            # The contract metadata
            metadata=sp.TBigMap(sp.TString, sp.TBytes),
            # The token contract address
            token_contract=sp.TOption(sp.TAddress)))

        # Initialize the contract storage
        self.init(
            metadata=metadata,
            token_contract=sp.none)

    @sp.entry_point
    def mint_token(self, params):
        # Define the input parameter data type
        sp.set_type(params, sp.TRecord(
            metadata=sp.TMap(sp.TString, sp.TBytes),
            price=sp.TMutez,
            fee=sp.TNat).layout(
                ("metadata", ("price", "fee"))))

        # Check that no tez have been transferred
        sp.verify(sp.amount == sp.mutez(0), message="HM_TEZ_TRANSFER")

        # Check that the fee is not larger than 25%
        sp.verify(params.fee <= 250, message="HM_WRONG_FEE")

        # Send the mint information to the token contract
        mint_handle = sp.contract(
            t=sp.TRecord(
                creator=sp.TAddress,
                metadata=sp.TMap(sp.TString, sp.TBytes),
                price=sp.TMutez,
                fee=sp.TNat).layout(
                    ("creator", ("metadata", ("price", "fee")))),
            address=self.data.token_contract.open_some(),
            entry_point="mint").open_some()
        sp.transfer(
            arg=sp.record(
                creator=sp.sender,
                metadata=params.metadata,
                price=params.price,
                fee=params.fee),
            amount=sp.mutez(0),
            destination=mint_handle)

    @sp.entry_point
    def set_token_contract(self, token_contract):
        """Sets the token contract.

        """
        # Define the input parameter data type
        sp.set_type(token_contract, sp.TAddress)

        # Check that the token contract has not been set before
        sp.verify(~self.data.token_contract.is_some(),
                  message="HM_TOKEN_CONTRACT_ALREADY_SET")

        # Set the token contract address
        self.data.token_contract = sp.some(token_contract)


sp.add_compilation_target("harbergerMinter", HarbergerMinter(
    metadata=sp.utils.metadata_of_url("ipfs://aaa")))
