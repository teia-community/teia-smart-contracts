import smartpy as sp


class SpanishInquisitionFA2(sp.Contract):
    """This contract tries to simplify and extend the FA2 contract template
    example in smartpy.io v0.9.1. It adds the possibility to have block and
    allow lists to control who can transfer and receive the tokens.

    The FA2 template was originally developed by Seb Mondet:
    https://gitlab.com/smondet/fa2-smartpy

    The contract follows the FA2 standard specification:
    https://gitlab.com/tezos/tzip/-/blob/master/proposals/tzip-12/tzip-12.md

    """

    LEDGER_KEY_TYPE = sp.TPair(
        # The owner of the token editions
        sp.TAddress,
        # The token id
        sp.TNat)

    TOKEN_METADATA_VALUE_TYPE = sp.TRecord(
        # The token id
        token_id=sp.TNat,
        # The map with the token metadata information
        token_info=sp.TMap(sp.TString, sp.TBytes)).layout(
            ("token_id", "token_info"))

    USER_ROYALTIES_TYPE = sp.TRecord(
        # The user address
        address=sp.TAddress,
        # The user royalties in per mille (100 is 10%)
        royalties=sp.TNat).layout(
            ("address", "royalties"))

    TOKEN_ROYALTIES_VALUE_TYPE = sp.TRecord(
        # The token original minter
        minter=USER_ROYALTIES_TYPE,
        # The token creator (it could be a single creator or a collaboration)
        creator=USER_ROYALTIES_TYPE).layout(
            ("minter", "creator"))

    OPERATOR_KEY_TYPE = sp.TRecord(
        # The owner of the token editions
        owner=sp.TAddress,
        # The operator allowed by the owner to transfer their token editions
        operator=sp.TAddress,
        # The token id
        token_id=sp.TNat).layout(
            ("owner", ("operator", "token_id")))

    def __init__(self, administrator, metadata):
        """Initializes the contract.

        """
        # Define the contract storage data types for clarity
        self.init_type(sp.TRecord(
            # The contract administrator
            administrator=sp.TAddress,
            # The contract metadata
            metadata=sp.TBigMap(sp.TString, sp.TBytes),
            # The ledger big map where the tokens owners are listed
            ledger=sp.TBigMap(SpanishInquisitionFA2.LEDGER_KEY_TYPE, sp.TNat),
            # The tokens total supply
            supply=sp.TBigMap(sp.TNat, sp.TNat),
            # The big map with the tokens metadata
            token_metadata=sp.TBigMap(
                sp.TNat, SpanishInquisitionFA2.TOKEN_METADATA_VALUE_TYPE),
            # The big map with the tokens data (source code, description, etc)
            token_data=sp.TBigMap(sp.TNat, sp.TMap(sp.TString, sp.TBytes)),
            # The big map with the tokens royalties for the minter and creators
            token_royalties=sp.TBigMap(
                sp.TNat, SpanishInquisitionFA2.TOKEN_ROYALTIES_VALUE_TYPE),
            # The big map with the tokens operators
            operators=sp.TBigMap(
                SpanishInquisitionFA2.OPERATOR_KEY_TYPE, sp.TUnit),
            # The list of smart contracts with the artist allow lists
            allow_lists=sp.TSet(sp.TAddress),
            # The list of smart contracts with the artist block lists
            block_lists=sp.TSet(sp.TAddress),
            # The proposed new administrator address
            proposed_administrator=sp.TOption(sp.TAddress),
            # A counter that tracks the total number of tokens minted so far
            counter=sp.TNat))

        # Initialize the contract storage
        self.init(
            administrator=administrator,
            metadata=metadata,
            ledger=sp.big_map(),
            supply=sp.big_map(),
            token_metadata=sp.big_map(),
            token_data=sp.big_map(),
            token_royalties=sp.big_map(),
            operators=sp.big_map(),
            allow_lists=sp.set(),
            block_lists=sp.set(),
            proposed_administrator=sp.none,
            counter=0)

        # Build the TZIP-016 contract metadata
        # This is helpful to get the off-chain views code in json format
        contract_metadata = {
            "name": "Extended FA2 template contract with block and allow lists",
            "description" : "This contract tries to simplify and extend the "
                "FA2 contract template example in smartpy.io v0.9.1. It adds "
                "the possibility to have block and allow lists to control who "
                "can transfer and receive the tokens.",
            "version": "v1.0.0",
            "authors": ["Teia Community <https://twitter.com/TeiaCommunity>"],
            "homepage": "https://teia.art",
            "source": {
                "tools": ["SmartPy 0.16.0"],
                "location": "https://github.com/teia-community/teia-smart-contracts/blob/main/python/contracts/si_fa2.py"
            },
            "interfaces": ["TZIP-012", "TZIP-016"],
            "views": [
                self.get_balance,
                self.total_supply,
                self.all_tokens,
                self.is_operator,
                self.token_metadata,
                self.token_data,
                self.token_royalties],
            "permissions": {
                "operator": "owner-or-operator-transfer",
                "receiver": "owner-no-hook",
                "sender": "owner-no-hook"
            }
        }

        self.init_metadata("contract_metadata", contract_metadata)

    def check_is_administrator(self):
        """Checks that the address that called the entry point is the contract
        administrator.

        """
        sp.verify(sp.sender == self.data.administrator, message="FA2_NOT_ADMIN")

    def check_token_exists(self, token_id):
        """Checks that the given token exists.

        """
        sp.verify(token_id < self.data.counter, message="FA2_TOKEN_UNDEFINED")

    @sp.private_lambda(with_storage=None, with_operations=False, wrap_call=True)
    def can_transfer_tokens(self, params):
        """Checks that the given address can transfer tokens.

        """
        # Define the input parameter data type
        sp.set_type(params, sp.TRecord(
            address=sp.TAddress,
            allow_lists=sp.TSet(sp.TAddress),
            block_lists=sp.TSet(sp.TAddress)).layout(
                ("address", ("allow_lists", "block_lists"))))

        # Check if the address can transfer tokens
        address = sp.compute(params.address)
        allow_lists = sp.compute(params.allow_lists.elements())
        block_lists = sp.compute(params.block_lists.elements())

        with sp.if_(sp.len(allow_lists) > 0):
            is_allowed = sp.local("is_allowed", False)

            with sp.for_("allow_list", allow_lists) as allow_list:
                is_allowed.value = is_allowed.value | sp.view(
                    name="is_member",
                    address=allow_list,
                    param=address,
                    t=sp.TBool).open_some()

            sp.verify(is_allowed.value, message="FA2_NOT_ALLOWED_USER")
        with sp.else_():
            with sp.for_("block_list", block_lists) as block_list:
                is_blocked = sp.view(
                    name="is_member",
                    address=block_list,
                    param=address,
                    t=sp.TBool).open_some()
                sp.verify(~is_blocked, message="FA2_BLOCKED_USER")

    @sp.entry_point(private=True)
    def check_can_transfer_tokens(self, address):
        """Calculates the square root of the given number.

        Note that this is a private entrypoint only used for testing purposes.

        """
        # Define the input parameter data type
        sp.set_type(address, sp.TAddress)

        # Store the result in the counter just for test purposes
        self.can_transfer_tokens(sp.record(
            address=address,
            allow_lists=self.data.allow_lists,
            block_lists=self.data.block_lists))

    @sp.entry_point
    def mint(self, params):
        """Mints a new token.

        """
        # Define the input parameter data type
        sp.set_type(params, sp.TRecord(
            amount=sp.TNat,
            metadata=sp.TMap(sp.TString, sp.TBytes),
            data=sp.TMap(sp.TString, sp.TBytes),
            royalties=SpanishInquisitionFA2.TOKEN_ROYALTIES_VALUE_TYPE).layout(
                ("amount", ("metadata", ("data", "royalties")))))

        # Check that the administrator executed the entry point
        self.check_is_administrator()

        # Check that the total royalties do not exceed 100%
        sp.verify(params.royalties.minter.royalties + 
                  params.royalties.creator.royalties <= 1000,
                  message="FA2_INVALID_ROYALTIES")

        # Update the big maps
        token_id = sp.compute(self.data.counter)
        self.data.ledger[
            (params.royalties.minter.address, token_id)] = params.amount
        self.data.supply[token_id] = params.amount
        self.data.token_metadata[token_id] = sp.record(
            token_id=token_id,
            token_info=params.metadata)
        self.data.token_data[token_id] = params.data
        self.data.token_royalties[token_id] = params.royalties

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

        # Check that the sender can transfer tokens
        allow_lists = sp.compute(self.data.allow_lists)
        block_lists = sp.compute(self.data.block_lists)
        self.can_transfer_tokens(sp.record(
            address=sp.sender,
            allow_lists=allow_lists,
            block_lists=block_lists))

        # Loop over the list of transfers
        with sp.for_("transfer", params) as transfer:
            # Check that the owner can transfer tokens
            owner = sp.compute(transfer.from_)
            self.can_transfer_tokens(sp.record(
                address=owner,
                allow_lists=allow_lists,
                block_lists=block_lists))

            with sp.for_("tx", transfer.txs) as tx:
                # Check that the token exists
                token_id = sp.compute(tx.token_id)
                self.check_token_exists(token_id)

                # Check that the sender is one of the token operators
                sp.verify(
                    (sp.sender == owner) | 
                    self.data.operators.contains(sp.record(
                        owner=owner,
                        operator=sp.sender,
                        token_id=token_id)),
                    message="FA2_NOT_OPERATOR")

                # Check that the transfer amount is not zero
                with sp.if_(tx.amount > 0):
                    # Check that the new owner can receive tokens
                    self.can_transfer_tokens(sp.record(
                        address=tx.to_,
                        allow_lists=allow_lists,
                        block_lists=block_lists))

                    # Remove the token amount from the owner
                    owner_key = sp.pair(owner, token_id)
                    self.data.ledger[owner_key] = sp.as_nat(
                        self.data.ledger.get(owner_key, 0) - tx.amount,
                        "FA2_INSUFFICIENT_BALANCE")

                    # Add the token amount to the new owner
                    new_owner_key = sp.pair(tx.to_, token_id)
                    self.data.ledger[new_owner_key] = self.data.ledger.get(
                        new_owner_key, 0) + tx.amount

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
            sp.result(sp.record(
                request=request,
                balance=self.data.ledger.get(
                    (request.owner, request.token_id), 0)))

        sp.transfer(
            params.requests.map(process_request), sp.mutez(0), params.callback)

    @sp.entry_point
    def update_operators(self, params):
        """Updates a list of operators.

        """
        # Define the input parameter data type
        sp.set_type(params, sp.TList(sp.TVariant(
            add_operator=SpanishInquisitionFA2.OPERATOR_KEY_TYPE,
            remove_operator=SpanishInquisitionFA2.OPERATOR_KEY_TYPE)))

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
    def update_lists(self, params):
        """Updates the allow or block lists.

        """
        # Define the input parameter data type
        sp.set_type(params, sp.TVariant(
            add_allow_list=sp.TAddress,
            remove_allow_list=sp.TAddress,
            add_block_list=sp.TAddress,
            remove_block_list=sp.TAddress))

        # Check that the administrator executed the entry point
        self.check_is_administrator()

        # Add or remove the list
        with params.match_cases() as arg:
            with arg.match("add_allow_list") as list_address:
                self.data.allow_lists.add(list_address)
            with arg.match("remove_allow_list") as list_address:
                self.data.allow_lists.remove(list_address)
            with arg.match("add_block_list") as list_address:
                self.data.block_lists.add(list_address)
            with arg.match("remove_block_list") as list_address:
                self.data.block_lists.remove(list_address)

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
            message="FA2_NO_NEW_ADMIN"), message="FA2_NOT_PROPOSED_ADMIN")

        # Set the new administrator address
        self.data.administrator = sp.sender

        # Reset the proposed administrator value
        self.data.proposed_administrator = sp.none

    @sp.entry_point
    def set_metadata(self, params):
        """Updates the contract metadata.

        """
        # Define the input parameter data type
        sp.set_type(params, sp.TRecord(
            k=sp.TString,
            v=sp.TBytes).layout(("k", "v")))

        # Check that the administrator executed the entry point
        self.check_is_administrator()

        # Update the contract metadata
        self.data.metadata[params.k] = params.v

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
        sp.result(self.data.ledger.get((params.owner, params.token_id), 0))

    @sp.onchain_view(pure=True)
    def total_supply(self, token_id):
        """Returns the total supply for a given token id.

        """
        # Define the input parameter data type
        sp.set_type(token_id, sp.TNat)

        # Check that the token exists
        self.check_token_exists(token_id)

        # Return the token total supply
        sp.result(self.data.supply.get(token_id, 0))

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
        sp.set_type(params, SpanishInquisitionFA2.OPERATOR_KEY_TYPE)

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
    def token_data(self, token_id):
        """Returns the token on-chain data.

        """
        # Define the input parameter data type
        sp.set_type(token_id, sp.TNat)

        # Return the token on-chain data
        sp.result(self.data.token_data[token_id])

    @sp.onchain_view(pure=True)
    def token_royalties(self, token_id):
        """Returns the token royalties information.

        """
        # Define the input parameter data type
        sp.set_type(token_id, sp.TNat)

        # Return the token royalties information
        sp.result(self.data.token_royalties[token_id])


sp.add_compilation_target("fa2", SpanishInquisitionFA2(
    administrator=sp.address("tz1M9CMEtsXm3QxA7FmMU2Qh7xzsuGXVbcDr"),
    metadata=sp.utils.metadata_of_url("ipfs://aaa")))
