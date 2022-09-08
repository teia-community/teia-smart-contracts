import smartpy as sp


class HarbergerToken(sp.Contract):
    """This contract extends the FA2 contract template example in smartpy.io
    v0.9.1 to apply a Harberger fee to the token owners.

    The FA2 template was originally developed by Seb Mondet:
    https://gitlab.com/smondet/fa2-smartpy

    The contract follows the FA2 standard specification:
    https://gitlab.com/tezos/tzip/-/blob/master/proposals/tzip-12/tzip-12.md

    """

    TOKEN_METADATA_VALUE_TYPE = sp.TRecord(
        # The token id
        token_id=sp.TNat,
        # The map with the token metadata information
        token_info=sp.TMap(sp.TString, sp.TBytes)).layout(
            ("token_id", "token_info"))

    OPERATOR_KEY_TYPE = sp.TRecord(
        # The token owner
        owner=sp.TAddress,
        # The operator allowed by the owner to transfer their token
        operator=sp.TAddress,
        # The token id
        token_id=sp.TNat).layout(
            ("owner", ("operator", "token_id")))

    TOKEN_FEE_TYPE = sp.TRecord(
        # The price set by the token owner
        price=sp.TMutez,
        # The Harberger fee in per mile
        fee=sp.TNat,
        # The Harberger fee recipient
        recipient=sp.TAddress,
        # The deadline for the next fee payment
        next_payment=sp.TTimestamp,
        # Flag that indicates if the token is currently on a Dutch auction
        auction=sp.TBool).layout(
            ("price", ("fee", ("recipient", ("next_payment", "auction")))))

    def __init__(self, minter_contract, metadata):
        """Initializes the contract.

        """
        # Define the contract storage data types for clarity
        self.init_type(sp.TRecord(
            # The minter contract address
            minter_contract=sp.TAddress,
            # The contract metadata
            metadata=sp.TBigMap(sp.TString, sp.TBytes),
            # The fees contract address
            fees_contract=sp.TOption(sp.TAddress),
            # The ledger big map where the tokens owners are listed
            ledger=sp.TBigMap(sp.TNat, sp.TAddress),
            # The big map with the tokens metadata
            token_metadata=sp.TBigMap(
                sp.TNat, HarbergerToken.TOKEN_METADATA_VALUE_TYPE),
            # The big map with the tokens operators
            operators=sp.TBigMap(HarbergerToken.OPERATOR_KEY_TYPE, sp.TUnit),
            # A counter that tracks the total number of tokens minted so far
            counter=sp.TNat))

        # Initialize the contract storage
        self.init(
            minter_contract=minter_contract,
            metadata=metadata,
            fees_contract=sp.none,
            ledger=sp.big_map(),
            token_metadata=sp.big_map(),
            operators=sp.big_map(),
            counter=0)

        # Build the TZIP-016 contract metadata
        # This is helpful to get the off-chain views code in json format
        contract_metadata = {
            "name": "Extended FA2 template contract with a Harberger fee",
            "description": "This contract extends the FA2 contract template "
            "example in smartpy.io v0.9.1 to apply a Harberger fee to the "
            "token owners",
            "version": "v1.0.0",
            "authors": ["Teia Community <https://twitter.com/TeiaCommunity>"],
            "homepage": "https://teia.art",
            "source": {
                "tools": ["SmartPy 0.13.0"],
                "location": "https://github.com/teia-community/teia-smart-contracts/blob/main/python/contracts/harbergerToken.py"
            },
            "interfaces": ["TZIP-012", "TZIP-016"],
            "views": [
                self.get_balance,
                self.total_supply,
                self.all_tokens,
                self.is_operator,
                self.token_metadata,
                self.token_owner],
            "permissions": {
                "operator": "owner-or-operator-transfer",
                "receiver": "owner-no-hook",
                "sender": "owner-no-hook"
            }
        }

        self.init_metadata("contract_metadata", contract_metadata)

    def check_no_tez_transfer(self):
        """Checks that no tez were transferred in the operation.

        """
        sp.verify(sp.amount == sp.mutez(0), message="FA2_TEZ_TRANSFER")

    def check_is_minter_contract(self):
        """Checks that the address that called the entry point is the minter
        contract.

        """
        sp.verify(sp.sender == self.data.minter_contract,
                  message="FA2_NOT_MINTER_CONTRACT")

    def check_token_exists(self, token_id):
        """Checks that the given token exists.

        """
        sp.verify(token_id < self.data.counter, message="FA2_TOKEN_UNDEFINED")

    @sp.entry_point
    def mint(self, params):
        """Mints a new token.

        """
        # Define the input parameter data type
        sp.set_type(params, sp.TRecord(
            creator=sp.TAddress,
            metadata=sp.TMap(sp.TString, sp.TBytes),
            price=sp.TMutez,
            fee=sp.TNat).layout(
                ("creator", ("metadata", ("price", "fee")))))

        # Check that the minter contract executed the entry point
        self.check_is_minter_contract()

        # Update the ledger and token metadata big maps
        token_id = sp.compute(self.data.counter)
        self.data.ledger[token_id] = params.creator
        self.data.token_metadata[token_id] = sp.record(
            token_id=token_id,
            token_info=params.metadata)

        # Send the fee information to the fees contract
        add_fee_handle = sp.contract(
            t=HarbergerToken.TOKEN_FEE_TYPE,
            address=self.data.fees_contract.open_some(),
            entry_point="add_fee").open_some()
        sp.transfer(
            arg=sp.record(
                price=params.price,
                fee=params.fee,
                recipient=params.creator,
                next_payment=sp.now,
                auction=False),
            amount=sp.mutez(0),
            destination=add_fee_handle)

        # Increase the tokens counter
        self.data.counter += 1

    @sp.entry_point
    def transfer(self, params):
        """Executes a list of token transfers.

        """
        # Define the input parameter data type
        sp.set_type(params, sp.TList(sp.TRecord(
            from_=sp.TAddress,
            txs=sp.TList(sp.TRecord(
                to_=sp.TAddress,
                token_id=sp.TNat,
                amount=sp.TNat).layout(
                    ("to_", ("token_id", "amount"))))).layout(
                        ("from_", "txs"))))

        # Check that no tez have been transferred
        self.check_no_tez_transfer()

        # Loop over the list of transfers
        with sp.for_("transfer", params) as transfer:
            with sp.for_("tx", transfer.txs) as tx:
                # Check that the token exists
                token_id = sp.compute(tx.token_id)
                self.check_token_exists(token_id)

                # Check that the sender is one of the token operators
                owner = sp.compute(transfer.from_)
                fees_contract = self.data.fees_contract.open_some()
                sp.verify(
                    (sp.sender == owner) | 
                    (sp.sender == fees_contract) | 
                    self.data.operators.contains(sp.record(
                        owner=owner,
                        operator=sp.sender,
                        token_id=token_id)),
                    message="FA2_NOT_OPERATOR")

                # Check that the transfer amount is not zero
                with sp.if_(tx.amount > 0):
                    # Check that the owner really owns the token
                    sp.verify((tx.amount == 1) & 
                              (self.data.ledger[token_id] == owner),
                              message="FA2_INSUFFICIENT_BALANCE")

                    # Set the new token owner
                    self.data.ledger[token_id] = tx.to_

    @sp.entry_point
    def balance_of(self, params):
        """Requests information about a list of token balances.

        """
        # Define the input parameter data type
        request_type = sp.TRecord(
            owner=sp.TAddress,
            token_id=sp.TNat).layout(("owner", "token_id"))
        sp.set_type(params, sp.TRecord(
            requests=sp.TList(request_type),
            callback=sp.TContract(sp.TList(sp.TRecord(
                request=request_type,
                balance=sp.TNat).layout(("request", "balance"))))).layout(
                    ("requests", "callback")))

        def process_request(request):
            # Check that the token exists
            self.check_token_exists(request.token_id)

            # Return the owner token balance
            balance = sp.local("balance", sp.nat(0))

            with sp.if_(self.data.ledger[request.token_id] == request.owner):
                balance.value = sp.nat(1)

            sp.result(sp.record(request=request, balance=balance.value))

        sp.transfer(
            params.requests.map(process_request), sp.mutez(0), params.callback)

    @sp.entry_point
    def update_operators(self, params):
        """Updates a list of operators.

        """
        # Define the input parameter data type
        sp.set_type(params, sp.TList(sp.TVariant(
            add_operator=HarbergerToken.OPERATOR_KEY_TYPE,
            remove_operator=HarbergerToken.OPERATOR_KEY_TYPE)))

        # Check that no tez have been transferred
        self.check_no_tez_transfer()

        # Loop over the list of update operators
        with sp.for_("update_operator", params) as update_operator:
            with update_operator.match_cases() as arg:
                with arg.match("add_operator") as operator_key:
                    # Check that the token exists
                    self.check_token_exists(operator_key.token_id)

                    # Check that the sender is the token owner
                    sp.verify(sp.sender == operator_key.owner,
                              message="FA2_SENDER_IS_NOT_OWNER")

                    # Add the new operator to the operators big map
                    self.data.operators[operator_key] = sp.unit
                with arg.match("remove_operator") as operator_key:
                    # Check that the token exists
                    self.check_token_exists(operator_key.token_id)

                    # Check that the sender is the token owner
                    sp.verify(sp.sender == operator_key.owner,
                              message="FA2_SENDER_IS_NOT_OWNER")

                    # Remove the operator from the operators big map
                    del self.data.operators[operator_key]

    @sp.entry_point
    def set_fees_contract(self, fees_contract):
        """Sets the contract that will administer the token fees.

        """
        # Define the input parameter data type
        sp.set_type(fees_contract, sp.TAddress)

        # Check that the minter contract executed the entry point
        self.check_is_minter_contract()

        # Set the fees contract address
        self.data.fees_contract = sp.some(fees_contract)

    @sp.onchain_view(pure=True)
    def token_exists(self, token_id):
        """Checks if the token exists.

        """
        # Define the input parameter data type
        sp.set_type(token_id, sp.TNat)

        # Return true if the token exists
        sp.result(token_id < self.data.counter)

    @sp.onchain_view(pure=True)
    def count_tokens(self):
        """Returns how many tokens are in this FA2 contract.

        """
        sp.result(self.data.counter)

    @sp.onchain_view(pure=True)
    def get_balance(self, params):
        """Returns the owner token balance.

        """
        # Define the input parameter data type
        sp.set_type(params, sp.TRecord(
            owner=sp.TAddress,
            token_id=sp.TNat).layout(("owner", "token_id")))

        # Check that the token exists
        self.check_token_exists(params.token_id)

        # Return the owner token balance
        balance = sp.local("balance", sp.nat(0))

        with sp.if_(self.data.ledger[params.token_id] == params.owner):
            balance.value = sp.nat(1)

        sp.result(balance.value)

    @sp.onchain_view(pure=True)
    def total_supply(self, token_id):
        """Returns the total supply for a given token id.

        """
        # Define the input parameter data type
        sp.set_type(token_id, sp.TNat)

        # Check that the token exists
        self.check_token_exists(token_id)

        # Return the token total supply
        sp.result(sp.nat(1))

    @sp.onchain_view(pure=True)
    def all_tokens(self):
        """Returns a list with all the token ids.

        """
        sp.result(sp.range(0, self.data.counter))

    @sp.onchain_view(pure=True)
    def is_operator(self, params):
        """Checks if a given token operator exists.

        """
        # Define the input parameter data type
        sp.set_type(params, HarbergerToken.OPERATOR_KEY_TYPE)

        # Check that the token exists
        self.check_token_exists(params.token_id)

        # Return true if the token operator exists
        sp.result(self.data.operators.contains(params))

    @sp.onchain_view(pure=True)
    def token_metadata(self, token_id):
        """Returns the token metadata.

        """
        # Define the input parameter data type
        sp.set_type(token_id, sp.TNat)

        # Check that the token exists
        self.check_token_exists(token_id)

        # Return the token metadata
        sp.result(self.data.token_metadata[token_id])

    @sp.onchain_view(pure=True)
    def token_owner(self, token_id):
        """Returns the token owner.

        """
        # Define the input parameter data type
        sp.set_type(token_id, sp.TNat)

        # Check that the token exists
        self.check_token_exists(token_id)

        # Return the token owner
        sp.result(self.data.ledger[token_id])


sp.add_compilation_target("harbergerToken", HarbergerToken(
    minter_contract=sp.address("tz1M9CMEtsXm3QxA7FmMU2Qh7xzsuGXVbcDr"),
    metadata=sp.utils.metadata_of_url("ipfs://aaa")))
