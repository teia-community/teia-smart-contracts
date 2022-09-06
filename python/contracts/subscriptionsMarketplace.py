import smartpy as sp


class SubscriptionsMarketplace(sp.Contract):
    """This contract implements a marketplace for subscription tokens.

    """

    COLLECTION_TYPE = sp.TRecord(
        # The collection creator
        creator=sp.TAddress,
        # The collection metadata
        metadata=sp.TMap(sp.TString, sp.TBytes),
        # The metadata that will be used to mint the tokens
        token_metadata=sp.TMap(sp.TString, sp.TBytes),
        # The token mint price
        mint_price=sp.TMutez,
        # The maximum number of tokens in the collection
        max_tokens=sp.TOption(sp.TNat)).layout(
            ("creator", ("metadata", ("token_metadata", ("mint_price", "max_tokens")))))

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

    def __init__(self, administrator, metadata, fee):
        """Initializes the contract.

        """
        # Define the contract storage data types for clarity
        self.init_type(sp.TRecord(
            # The contract administrator
            administrator=sp.TAddress,
            # The contract metadata
            metadata=sp.TBigMap(sp.TString, sp.TBytes),
            # The marketplace fee taken for each mint in per mille
            fee=sp.TNat,
            # The address that will receive the marketplace fees
            fee_recipient=sp.TAddress,
            # The token contract address
            token_contract=sp.TOption(sp.TAddress),
            # The subscription fees contract address
            fees_contract=sp.TOption(sp.TAddress),
            # The big map with the collections information
            collections=sp.TBigMap(
                sp.TNat, SubscriptionsMarketplace.COLLECTION_TYPE),
            # The big map with the mint status of each collection
            mint_open=sp.TBigMap(sp.TNat, sp.TBool),
            # The number of tokens minted in each collection
            minted_tokens=sp.TBigMap(sp.TNat, sp.TNat),
            # The proposed new administrator address
            proposed_administrator=sp.TOption(sp.TAddress),
            # A counter that tracks the total number of collections
            counter=sp.TNat))

        # Initialize the contract storage
        self.init(
            administrator=administrator,
            metadata=metadata,
            fee=fee,
            fee_recipient=administrator,
            token_contract=sp.none,
            fees_contract=sp.none,
            collections=sp.big_map(),
            mint_open=sp.big_map(),
            minted_tokens=sp.big_map(),
            proposed_administrator=sp.none,
            counter=0)

    def check_no_tez_transfer(self):
        """Checks that no tez were transferred in the operation.

        """
        sp.verify(sp.amount == sp.mutez(0), message="SM_TEZ_TRANSFER")

    def check_is_administrator(self):
        """Checks that the address that called the entry point is the contract
        administrator.

        """
        sp.verify(sp.sender == self.data.administrator, message="SM_NOT_ADMIN")

    def check_collection_exists(self, collection_id):
        """Checks that the given collection exists.

        """
        sp.verify(self.data.collections.contains(collection_id),
                  message="SM_COLLECTION_UNDEFINED")

    def check_is_collection_creator(self, creator):
        """Checks that the address that called the entry point is the
        collection creator.

        """
        sp.verify(sp.sender == creator, message="SM_NOT_COLLECTION_CREATOR")

    @sp.entry_point
    def create_collection(self, params):
        """Creates a new collection.

        """
        # Define the input parameter data type
        sp.set_type(params, sp.TRecord(
            metadata=sp.TMap(sp.TString, sp.TBytes),
            token_metadata=sp.TMap(sp.TString, sp.TBytes),
            mint_price=sp.TMutez,
            max_tokens=sp.TOption(sp.TNat),
            fee_information=SubscriptionsMarketplace.COLLECTION_FEE_TYPE).layout(
                ("metadata", ("token_metadata", ("mint_price", ("max_tokens", "fee_information"))))))

        # Check that no tez have been transferred
        self.check_no_tez_transfer()

        # Update the collections and the minted tokens big map
        collection_id = sp.compute(self.data.counter)
        self.data.collections[collection_id] = sp.record(
            creator=sp.sender,
            metadata=params.metadata,
            token_metadata=params.token_metadata,
            mint_price=params.mint_price,
            max_tokens=params.max_tokens)
        self.data.mint_open[collection_id] = False
        self.data.minted_tokens[collection_id] = 0

        # Send the subscription fee information to the fees contract
        add_fee_handle = sp.contract(
            t=sp.TRecord(
                collection_id=sp.TNat,
                fee_information=SubscriptionsMarketplace.COLLECTION_FEE_TYPE).layout(
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
    def set_max_tokens(self, params):
        """Sets the maximum number of tokens that can be minted in the
        collection.

        """
        # Define the input parameter data type
        sp.set_type(params, sp.TRecord(
            collection_id=sp.TNat,
            new_max_tokens=sp.TNat).layout(
                ("collection_id", "new_max_tokens")))

        # Check that no tez have been transferred
        self.check_no_tez_transfer()

        # Check that the collection exists
        collection_id = sp.compute(params.collection_id)
        self.check_collection_exists(collection_id)

        # Check that the collection creator executed the entry point
        collection = sp.compute(self.data.collections[collection_id])
        self.check_is_collection_creator(collection.creator)

        # Check that there are less minted tokens than the new max_tokens value
        new_max_tokens = sp.compute(params.new_max_tokens)
        sp.verify(self.data.minted_tokens[collection_id] <= new_max_tokens,
                  message="SM_TOO_MANY_MINTED_TOKENS")

        # Check that the new max_tokens value is smaller than the previous
        sp.verify(~collection.max_tokens.is_some() | 
                  (collection.max_tokens.open_some() > new_max_tokens),
                  message="SM_WRONG_MAX_NUMBER")

        # Check if the user wants to delete the collection
        with sp.if_(new_max_tokens == 0):
            # Delete the collection
            del self.data.collections[collection_id]
            del self.data.mint_open[collection_id]
            del self.data.minted_tokens[collection_id]
        with sp.else_():
            # Set the new max_tokens value
            self.data.collections[collection_id].max_tokens = sp.some(
                new_max_tokens)

    @sp.entry_point
    def open_mint(self, params):
        """Sets the collection minting status to open or closed.

        """
        # Define the input parameter data type
        sp.set_type(params, sp.TRecord(
            collection_id=sp.TNat,
            new_status=sp.TBool).layout(
                ("collection_id", "new_status")))

        # Check that no tez have been transferred
        self.check_no_tez_transfer()

        # Check that the collection exists
        collection_id = sp.compute(params.collection_id)
        self.check_collection_exists(collection_id)

        # Check that the collection creator executed the entry point
        self.check_is_collection_creator(
            self.data.collections[collection_id].creator)

        # Update the collection minting status
        self.data.mint_open[collection_id] = params.new_status

    @sp.entry_point
    def mint_subscription(self, collection_id):
        # Define the input parameter data type
        sp.set_type(collection_id, sp.TNat)

        # Check that the collection exists
        self.check_collection_exists(collection_id)

        # Check that the collection minting status is open
        sp.verify(self.data.mint_open[collection_id],
                  message="SM_MINTING_IS_CLOSED")

        # Check that it is still possible to mint tokens for this collection
        collection = sp.compute(self.data.collections[collection_id])
        minted_tokens = sp.compute(self.data.minted_tokens[collection_id])

        with sp.if_(collection.max_tokens.is_some()):
            sp.verify(collection.max_tokens.open_some() > minted_tokens,
                      message="SM_ALL_TOKENS_MINTED")

        # Check that the sent amount coincides with the mint price
        sp.verify(sp.amount == collection.mint_price,
                  message="SM_WRONG_TEZ_AMOUNT")

        # Calculate the marketplace fees
        marketplace_fees = sp.compute(
            sp.split_tokens(sp.amount, self.data.fee, 1000))

        # Send the marketplace fee to the fee recipient
        with sp.if_(marketplace_fees > sp.mutez(0)):
            sp.send(self.data.fee_recipient, marketplace_fees)

        # Send the remaining amount to the collection creator
        remaining_amount = sp.compute(sp.amount - marketplace_fees)

        with sp.if_(remaining_amount > sp.mutez(0)):
            sp.send(collection.creator, remaining_amount)

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
                metadata=collection.token_metadata,
                collection_id=collection_id),
            amount=sp.mutez(0),
            destination=mint_handle)

        # Increase the minted tokens counter
        self.data.minted_tokens[collection_id] = minted_tokens + 1

    @sp.entry_point
    def update_fee(self, new_fee):
        """Updates the marketplace management fees.

        """
        # Define the input parameter data type
        sp.set_type(new_fee, sp.TNat)

        # Check that the administrator executed the entry point
        self.check_is_administrator()

        # Check that the new fee is not larger than 25%
        sp.verify(new_fee <= 250, message="MP_WRONG_FEES")

        # Set the new management fee
        self.data.fee = new_fee

    @sp.entry_point
    def set_token_contract(self, token_contract):
        """Sets the token contract.

        """
        # Define the input parameter data type
        sp.set_type(token_contract, sp.TAddress)

        # Check that the administrator executed the entry point
        self.check_is_administrator()

        # Check that the token contract has not been set before
        sp.verify(~self.data.token_contract.is_some(),
                  message="SM_TOKEN_CONTRACT_ALREADY_SET")

        # Set the token contract address
        self.data.token_contract = sp.some(token_contract)

    @sp.entry_point
    def set_fees_contract(self, fees_contract):
        """Sets the contract that will administer the collection fees.

        For security reasons, the fees contract can only be set once.

        """
        # Define the input parameter data type
        sp.set_type(fees_contract, sp.TAddress)

        # Check that the administrator executed the entry point
        self.check_is_administrator()

        # Check that fees contract has not been set before
        sp.verify(~self.data.fees_contract.is_some(),
                  message="SM_FEES_CONTRACT_ALREADY_SET")

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
            message="SM_NO_NEW_ADMIN"), message="SM_NOT_PROPOSED_ADMIN")

        # Set the new administrator address
        self.data.administrator = sp.sender

        # Reset the proposed administrator value
        self.data.proposed_administrator = sp.none


sp.add_compilation_target("subscriptionMarketplace", SubscriptionsMarketplace(
    administrator=sp.address("tz1M9CMEtsXm3QxA7FmMU2Qh7xzsuGXVbcDr"),
    metadata=sp.utils.metadata_of_url("ipfs://bbb"),
    fee=sp.nat(25)))
