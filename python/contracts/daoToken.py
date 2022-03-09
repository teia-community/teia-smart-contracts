import smartpy as sp


class DAOToken(sp.Contract):
    """This contract adapts the FA2 contract template example in smartpy.io
    v0.9.1 to be used as a DAO token.

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
        # The owner of the token editions
        owner=sp.TAddress,
        # The operator allowed by the owner to transfer their token editions
        operator=sp.TAddress,
        # The token id
        token_id=sp.TNat).layout(
            ("owner", ("operator", "token_id")))

    def __init__(self, administrator, metadata, token_metadata):
        """Initializes the contract.

        """
        # Define the contract storage data types for clarity
        self.init_type(sp.TRecord(
            # The contract administrador
            administrator=sp.TAddress,
            # The contract metadata
            metadata=sp.TBigMap(sp.TString, sp.TBytes),
            # The ledger big map where the token owners are listed
            ledger=sp.TBigMap(sp.TAddress, sp.TNat),
            # The token total supply
            supply=sp.TNat,
            # The big map with the token metadata
            token_metadata=sp.TBigMap(sp.TNat, DAOToken.TOKEN_METADATA_VALUE_TYPE),
            # The big map with the token operators
            operators=sp.TBigMap(DAOToken.OPERATOR_KEY_TYPE, sp.TUnit),
            # The proposed new administrator address
            proposed_administrator=sp.TOption(sp.TAddress)))

        # Initialize the contract storage
        self.init(
            administrator=administrator,
            metadata=metadata,
            ledger=sp.big_map(),
            supply=0,
            token_metadata=sp.big_map({
                0: sp.record(
                    token_id=0,
                    token_info={
                        "": token_metadata,
                        "name": sp.utils.bytes_of_string("Teia Community DAO"),
                        "symbol": sp.utils.bytes_of_string("teiaDAO"),
                        "decimals": sp.utils.bytes_of_string("6")
                    })}),
            operators=sp.big_map(),
            proposed_administrator=sp.none)

        # Build the TZIP-016 contract metadata
        # This is helpful to get the off-chain views code in json format
        contract_metadata = {
            "name": "Teia Community DAO token contract",
            "description" : "A basic DAO token contract for the Teia Community",
            "version": "v1.0.0",
            "authors": ["Teia Community <https://twitter.com/TeiaCommunity>"],
            "homepage": "https://teia.art",
            "source": {
                "tools": ["SmartPy 0.9.1"],
                "location": "https://github.com/teia-community/teia-smart-contracts/blob/main/python/contracts/daoToken.py"
            },
            "interfaces": ["TZIP-012", "TZIP-016"],
            "views": [
                self.get_balance,
                self.total_supply,
                self.all_tokens,
                self.is_operator,
                self.token_metadata],
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
        sp.verify(token_id == 0, message="FA2_TOKEN_UNDEFINED")

    @sp.entry_point
    def mint(self, params):
        """Mints new token editions.

        """
        # Define the input parameter data type
        sp.set_type(params, sp.TList(sp.TRecord(
            to_=sp.TAddress,
            token_id=sp.TNat,
            amount=sp.TNat).layout(
                ("to_", ("token_id", "amount")))))

        # Check that the administrator executed the entry point
        self.check_is_administrator()

        # Loop over the list of mints
        with sp.for_("mint", params) as mint:
            # Check that the token exists
            self.check_token_exists(mint.token_id)

            # Update the ledger big map and the total supply
            self.data.ledger[mint.to_] = self.data.ledger.get(
                mint.to_, 0) + mint.amount
            self.data.supply += mint.amount

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

        # Loop over the list of transfers
        with sp.for_("transfer", params) as transfer:
            with sp.for_("tx", transfer.txs) as tx:
                # Check that the token exists
                self.check_token_exists(tx.token_id)

                # Check that the sender is one of the token operators
                owner = sp.compute(transfer.from_)
                sp.verify(
                    (sp.sender == owner) | 
                    self.data.operators.contains(sp.record(
                        owner=owner,
                        operator=sp.sender,
                        token_id=0)),
                    message="FA2_NOT_OPERATOR")

                # Check that the transfer amount is not zero
                with sp.if_(tx.amount > 0):
                    # Remove the token amount from the owner
                    self.data.ledger[owner] = sp.as_nat(
                        self.data.ledger.get(owner, 0) - tx.amount,
                        "FA2_INSUFFICIENT_BALANCE")

                    # Add the token amount to the new owner
                    self.data.ledger[tx.to_] = self.data.ledger.get(
                        tx.to_, 0) + tx.amount

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
                balance=self.data.ledger.get(request.owner, 0)))

        sp.transfer(
            params.requests.map(process_request), sp.mutez(0), params.callback)

    @sp.entry_point
    def update_operators(self, params):
        """Updates a list of operators.

        """
        # Define the input parameter data type
        sp.set_type(params, sp.TList(sp.TVariant(
            add_operator=DAOToken.OPERATOR_KEY_TYPE,
            remove_operator=DAOToken.OPERATOR_KEY_TYPE)))

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
        responsabilities.

        """
        # Check that there is a proposed administrator
        sp.verify(self.data.proposed_administrator.is_some(),
                  message="FA_NO_NEW_ADMIN")

        # Check that the proposed administrator executed the entry point
        sp.verify(sp.sender == self.data.proposed_administrator.open_some(),
                  message="FA_NOT_PROPOSED_ADMIN")

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
        sp.result(self.data.ledger.get(params.owner, 0))

    @sp.onchain_view(pure=True)
    def total_supply(self, token_id):
        """Returns the total supply for a given token id.

        """
        # Define the input parameter data type
        sp.set_type(token_id, sp.TNat)

        # Check that the token exists
        self.check_token_exists(token_id)

        # Return the token total supply
        sp.result(self.data.supply)

    @sp.onchain_view(pure=True)
    def all_tokens(self):
        """Returns a list with all the token ids.

        """
        sp.result(sp.list([0], t=sp.TNat))

    @sp.onchain_view(pure=True)
    def is_operator(self, params):
        """Checks if a given token operator exists.

        """
        # Define the input parameter data type
        sp.set_type(params, DAOToken.OPERATOR_KEY_TYPE)

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


sp.add_compilation_target("daoToken", DAOToken(
    administrator=sp.address("tz1M9CMEtsXm3QxA7FmMU2Qh7xzsuGXVbcDr"),
    metadata=sp.utils.metadata_of_url("ipfs://aaa"),
    token_metadata=sp.utils.bytes_of_string("ipfs://bbb")))