import smartpy as sp


class SubscriptionCollections(sp.Contract):
    """This contract represents a list of collections for subscription tokens.

    """

    COLLECTION_TYPE = sp.TRecord(
        # The collection name
        name=sp.TBytes,
        # The collection creator
        creator=sp.TAddress,
        # The metadata that will be used for minting the tokens
        metadata=sp.TMap(sp.TString, sp.TBytes),
        # The token mint price
        mint_price=sp.TMutez,
        # The maximum number of tokens in the collection
        max_tokens=sp.TOption(sp.TNat)).layout(
            ("name", ("creator", ("metadata", ("mint_price", "max_tokens")))))

    COLLECTION_FEE_TYPE = sp.TRecord(
        # The subscription fee in mutez
        fee=sp.TMutez,
        # The fee payment interval in days
        interval=sp.TNat,
        # The fee recipient
        recipient=sp.TAddress,
        # The date when the fee doesn't need to be paid anymore
        end_date=sp.TOption(sp.TTimestamp)).layout(
            ("fee", ("interval", ("recipient", "end_date"))))

    def __init__(self, metadata):
        """Initializes the contract.

        """
        # Define the contract storage data types for clarity
        self.init_type(sp.TRecord(
            # The contract metadata
            metadata=sp.TBigMap(sp.TString, sp.TBytes),
            # The token contract address
            token_contract=sp.TOption(sp.TAddress),
            # The fees contract address
            fees_contract=sp.TOption(sp.TAddress),
            # The big map with the collections information
            collections=sp.TBigMap(
                sp.TNat, SubscriptionCollections.COLLECTION_TYPE),
            # The number of tokens minted in each collection
            minted_tokens=sp.TBigMap(sp.TNat, sp.TNat),
            # A counter that tracks the total number of collections
            counter=sp.TNat))

        # Initialize the contract storage
        self.init(
            metadata=metadata,
            token_contract=sp.none,
            fees_contract=sp.none,
            collections=sp.big_map(),
            minted_tokens=sp.big_map(),
            counter=0)

    @sp.entry_point
    def create_collection(self, params):
        """Creates a new collection.

        """
        # Define the input parameter data type
        sp.set_type(params, sp.TRecord(
            name=sp.TBytes,
            creator=sp.TAddress,
            metadata=sp.TMap(sp.TString, sp.TBytes),
            mint_price=sp.TMutez,
            max_tokens=sp.TOption(sp.TNat),
            fee_information=SubscriptionCollections.COLLECTION_FEE_TYPE).layout(
                ("name", ("creator", ("metadata", ("mint_price", ("max_tokens", "fee_information")))))))

        # Update the collections and the minted tokens big map
        collection_id = sp.compute(self.data.counter)
        self.data.collections[collection_id] = sp.record(
            name=params.name,
            creator=params.creator,
            metadata=params.metadata,
            mint_price=params.mint_price,
            max_tokens=params.max_tokens)
        self.data.minted_tokens[collection_id] = 0

        # Send the fee information to the fees contract
        add_fee_handle = sp.contract(
            t=sp.TRecord(
                collection_id=sp.TNat,
                fee_information=SubscriptionCollections.COLLECTION_FEE_TYPE).layout(
                    ("collection_id", "fee_information")),
            address=self.data.fees_contract.open_some(),
            entry_point="add_fee").open_some()
        sp.transfer(
            arg=sp.record(
                collection_id=collection_id,
                fee_information=params.fee_information),
            amount=sp.mutez(0),
            destination=add_fee_handle)

        # Increase the collections counter
        self.data.counter = collection_id + 1

    @sp.entry_point
    def mint_subscription(self, collection_id):
        # Define the input parameter data type
        sp.set_type(collection_id, sp.TNat)

        # Check that the collection exists
        sp.verify(collection_id < self.data.counter,
                  message="COLLECTIONS_COLLECTION_UNDEFINED")

        # Check that it is still possible to mint tokens for this collection
        collection = sp.compute(self.data.collections[collection_id])
        minted_tokens = sp.compute(self.data.minted_tokens[collection_id])

        with sp.if_(collection.max_tokens.is_some()):
            sp.verify(collection.max_tokens.open_some() > minted_tokens,
                      message="COLLECTIONS_ALL_TOKENS_MINTED")

        # Check that the sent amount coincides with the mint price
        sp.verify(sp.amount == collection.mint_price,
                  message="COLLECTIONS_WRONG_TEZ_AMOUNT")

        # Send the tez to the collection creator
        with sp.if_(sp.amount > sp.mutez(0)):
            sp.send(collection.creator, sp.amount)

        # Send the mint information to the token contract
        mint_handle = sp.contract(
            t=sp.TRecord(
                minter=sp.TAddress,
                metadata=sp.TMap(sp.TString, sp.TBytes),
                collection_id=sp.TNat).layout(
                    ("minter", ("metadata", "collection_id"))),
            address=self.data.token_contract.open_some(),
            entry_point="mint").open_some()
        sp.transfer(
            arg=sp.record(
                minter=sp.sender,
                metadata=collection.metadata,
                collection_id=collection_id),
            amount=sp.mutez(0),
            destination=mint_handle)

        # Increase the minted tokens counter
        self.data.minted_tokens[collection_id] = minted_tokens + 1

    @sp.entry_point
    def set_token_contract(self, token_contract):
        """Sets the token contract.

        """
        # Define the input parameter data type
        sp.set_type(token_contract, sp.TAddress)

        # Check that the token contract has not been set before
        sp.verify(~self.data.token_contract.is_some(),
                  message="COLLECTIONS_TOKEN_CONTRACT_ALREADY_SET")

        # Set the token contract address
        self.data.token_contract = sp.some(token_contract)

    @sp.entry_point
    def set_fees_contract(self, fees_contract):
        """Sets the contract that will administer the collection fees.

        For security reasons, the fees contract can only be set once.

        """
        # Define the input parameter data type
        sp.set_type(fees_contract, sp.TAddress)

        # Check that fees contract has not been set before
        sp.verify(~self.data.fees_contract.is_some(),
                  message="COLLECTIONS_FEES_CONTRACT_ALREADY_SET")

        # Set the fees contract address
        self.data.fees_contract = sp.some(fees_contract)

        # Set the fees contract in the token contract
        set_fees_contract_handle = sp.contract(
            t=sp.TAddress,
            address=self.data.token_contract.open_some(),
            entry_point="set_fees_contract").open_some()
        sp.transfer(
            arg=fees_contract,
            amount=sp.mutez(0),
            destination=set_fees_contract_handle)


sp.add_compilation_target("subscriptionCollections", SubscriptionCollections(
    metadata=sp.utils.metadata_of_url("ipfs://bbb")))
