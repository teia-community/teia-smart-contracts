import smartpy as sp
from os import environ


class DAOToken(sp.Contract):
    """This contract adapts the FA2 contract template example in smartpy.io
    v0.9.1 to use it as a DAO token.

    The FA2 template was originally developed by Seb Mondet:
    https://gitlab.com/smondet/fa2-smartpy

    The contract follows the FA2 standard specification:
    https://gitlab.com/tezos/tzip/-/blob/master/proposals/tzip-12/tzip-12.md

    The contract makes use of the Kolibri DAO implementation of token balance
    checkpoints:
    https://github.com/Hover-Labs/murmuration/blob/main/docs/token.md

    The token has no mint entry point. All tokens will be minted at origination.
    That means that the total supply is fixed and cannot be changed.

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

    CHECKPOINT_KEY_TYPE = sp.TPair(
        # The owner of the token editions
        sp.TAddress,
        # The owner checkpoint number
        sp.TNat)

    CHECKPOINT_VALUE_TYPE = sp.TRecord(
        # The block level where the checkpoint was taken
        level=sp.TNat,
        # The owner token balance at that block level
        balance=sp.TNat).layout(
            ("level", "balance"))

    # Basis for contract instance metadata
    CONTRACT_METADATA_BASE = {
        "name": "Teia DAO FA2 token contract",
        "description": "DAO token contract used in the Teia DAO",
        "version": "1.0.0",
        "authors": ["Teia Community <https://twitter.com/TeiaCommunity>"],
        "homepage": "https://teia.art",
        "source": {
            "tools": ["SmartPy 0.16.0"],
            "location": "https://github.com/teia-community/teia-smart-contracts/blob/main/python/contracts/daoToken.py"
        },
        "interfaces": ["TZIP-012", "TZIP-016"],
        "errors": [ {'error': {'string': 'FA2_TOKEN_UNDEFINED'},
                     'expansion': {'string': 'ERROR_MISSING_EXPANSION'},
                     'languages': ['en']},
                    {'error': {'string': 'FA2_NO_NEW_ADMIN'},
                     'expansion': {'string': 'ERROR_MISSING_EXPANSION'},
                     'languages': ['en']},
                    {'error': {'string': 'FA2_NOT_PROPOSED_ADMIN'},
                     'expansion': {'string': 'ERROR_MISSING_EXPANSION'},
                     'languages': ['en']},
                    {'error': {'string': 'FA2_NOT_ADMIN'},
                     'expansion': {'string': 'ERROR_MISSING_EXPANSION'},
                     'languages': ['en']},
                    {'error': {'string': 'FA2_SHARE_EXCESS'},
                     'expansion': {'string': 'ERROR_MISSING_EXPANSION'},
                     'languages': ['en']},
                    {'error': {'string': 'FA2_NOT_OPERATOR'},
                     'expansion': {'string': 'ERROR_MISSING_EXPANSION'},
                     'languages': ['en']},
                    {'error': {'string': 'FA2_INSUFFICIENT_BALANCE'},
                     'expansion': {'string': 'ERROR_MISSING_EXPANSION'},
                     'languages': ['en']},
                    {'error': {'string': 'FA2_SENDER_IS_NOT_OWNER'},
                     'expansion': {'string': 'ERROR_MISSING_EXPANSION'},
                     'languages': ['en']},
                    {'error': {'string': 'FA2_WRONG_LEVEL'},
                     'expansion': {'string': 'ERROR_MISSING_EXPANSION'},
                     'languages': ['en']},
                    {'error': {'string': 'FA2_WRONG_MAX_SHARE'},
                     'expansion': {'string': 'ERROR_MISSING_EXPANSION'},
                     'languages': ['en']},
                    {'error': {'string': 'FA2_WRONG_MAX_CHECKPOINTS'},
                     'expansion': {'string': 'ERROR_MISSING_EXPANSION'},
                     'languages': ['en']}],
        "views": [],  # Filled in in __init__
        "permissions": {
            "operator": "owner-or-operator-transfer",
            "receiver": "owner-no-hook",
            "sender": "owner-no-hook"
        }
    }

    def __init__(self, administrator, metadata, token_metadata, supply,
                 max_share):
        """Initializes the contract.

        """
        # Define the contract storage data types for clarity
        self.init_type(sp.TRecord(
            # The contract administrator
            administrator=sp.TAddress,
            # The contract metadata
            metadata=sp.TBigMap(sp.TString, sp.TBytes),
            # The ledger big map where the token owners are listed
            ledger=sp.TBigMap(sp.TAddress, sp.TNat),
            # The token total supply
            supply=sp.TNat,
            # The maximum number of tokens that a DAO member can have
            max_share=sp.TNat,
            # The big map with the token metadata
            token_metadata=sp.TBigMap(
                sp.TNat, DAOToken.TOKEN_METADATA_VALUE_TYPE),
            # The big map with the token operators
            operators=sp.TBigMap(DAOToken.OPERATOR_KEY_TYPE, sp.TUnit),
            # The big map with the token balance checkpoints
            checkpoints=sp.TBigMap(
                DAOToken.CHECKPOINT_KEY_TYPE, DAOToken.CHECKPOINT_VALUE_TYPE),
            # The big map with the number of checkpoints per token owner
            n_checkpoints=sp.TBigMap(sp.TAddress, sp.TNat),
            # The set of wallets that can own more tokens than the maximum share
            max_share_exceptions=sp.TSet(sp.TAddress),
            # The proposed new administrator address
            proposed_administrator=sp.TOption(sp.TAddress)))

        # Initialize the contract storage
        self.init(
            administrator=administrator,
            metadata=metadata,
            ledger=sp.big_map({administrator: supply}),
            supply=supply,
            max_share=max_share,
            token_metadata=sp.big_map({
                0: sp.record(token_id=0, token_info={"": token_metadata})}),
            operators=sp.big_map(),
            checkpoints=sp.big_map(),
            n_checkpoints=sp.big_map(),
            max_share_exceptions=sp.set([]),
            proposed_administrator=sp.none)

        # Build the TZIP-016 contract metadata
        # (For producing metadata JSON and TZIP-16 linting)
        self.contract_metadata = dict(DAOToken.CONTRACT_METADATA_BASE)
        self.contract_metadata.update({
            "views": [ 
                # NOTE: TZIP-16 specifies views as a list of offchain views, so perhaps 
                # adding "onchain" : "true" seems reasonable. The structure is however
                # not built until the init_metadata call. So it would perhaps be better 
                # to ask smartpy if they can add it. 
                self.get_balance,
                self.total_supply,
                self.all_tokens,
                self.is_operator,
                self.token_metadata,
                self.get_prior_balance]
            })

        self.init_metadata("contract_metadata", self.contract_metadata)

    def check_is_administrator(self):
        """Checks that the address that called the entry point is the contract
        administrator.

        """
        sp.verify(sp.sender == self.data.administrator, message="FA2_NOT_ADMIN")

    @sp.private_lambda(with_storage=None, wrap_call=True)
    def check_token_exists(self, token_id):
        """Checks that the given token exists.

        """
        sp.verify(token_id == 0, message="FA2_TOKEN_UNDEFINED")

    @sp.private_lambda(with_storage="read-write", wrap_call=True)
    def add_checkpoint(self, owner):
        """Adds a new checkpoint to the checkpoints big map.

        """
        # Get the owner current balance
        balance = sp.compute(self.data.ledger[owner])

        # Check if the owner has already some checkpoints
        with sp.if_(self.data.n_checkpoints.contains(owner)):
            # Get the last checkpoint index
            index = sp.compute(sp.as_nat(self.data.n_checkpoints[owner] - 1))

            # Check if the last checkpoint is at the same block level
            with sp.if_(self.data.checkpoints[(owner, index)].level == sp.level):
                # Update the checkpoint balance
                self.data.checkpoints[(owner, index)].balance = balance
            with sp.else_():
                # Check that the balance has changed
                with sp.if_(self.data.checkpoints[(owner, index)].balance != balance):
                    # Add a new checkpoint
                    self.data.checkpoints[(owner, index + 1)] = sp.record(
                        level=sp.level, balance=balance)

                    # Increase the owner checkpoints counter
                    self.data.n_checkpoints[owner] = index + 2
        with sp.else_():
            # Add the owner first checkpoint
            self.data.checkpoints[(owner, 0)] = sp.record(
                level=sp.level, balance=balance)

            # Increase the owner checkpoints counter
            self.data.n_checkpoints[owner] = 1

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

                    # Check that the balance is lower than the maximum share
                    sp.verify(self.data.max_share_exceptions.contains(tx.to_) | 
                              (self.data.ledger[tx.to_] < self.data.max_share),
                              message="FA2_SHARE_EXCESS")

                    # Add the new balance checkpoints
                    self.add_checkpoint(owner)
                    self.add_checkpoint(tx.to_)

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
        responsibilities.

        """
        # Check that the proposed administrator executed the entry point
        sp.verify(sp.sender == self.data.proposed_administrator.open_some(
            "FA2_NO_NEW_ADMIN"), message="FA2_NOT_PROPOSED_ADMIN")

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

    @sp.entry_point
    def add_max_share_exception(self, exception):
        """Adds or removes an exception to the set of addresses that can own
        more tokens than the maximum share.

        """
        # Define the input parameter data type
        sp.set_type(exception, sp.TAddress)

        # Check that the administrator executed the entry point
        self.check_is_administrator()

        # Add or remove the max share exception
        with sp.if_(self.data.max_share_exceptions.contains(exception)):
            self.data.max_share_exceptions.remove(exception)
        with sp.else_():
            self.data.max_share_exceptions.add(exception)

    @sp.entry_point
    def set_max_share(self, max_share):
        """Sets the maximum share of tokens that a wallet can own.

        """
        # Define the input parameter data type
        sp.set_type(max_share, sp.TNat)

        # Check that the administrator executed the entry point
        self.check_is_administrator()

        # Check that the new max_share value is between 1% and 10% of the token
        # total supply
        sp.verify((max_share >= (self.data.supply // 100)) & 
                  (max_share <= (self.data.supply // 10)),
                  message="FA2_WRONG_MAX_SHARE")

        # Update the max share
        self.data.max_share = max_share

    @sp.onchain_view(pure=True)
    def get_prior_balance(self, params):
        """Returns the owner token balance at a given block level.

        """
        # Define the input parameter data type
        sp.set_type(params, sp.TRecord(
            owner=sp.TAddress,
            level=sp.TNat,
            max_checkpoints=sp.TOption(sp.TNat)).layout(("owner", ("level", "max_checkpoints"))))

        # Check that the requested level is smaller than the current level
        sp.verify(params.level < sp.level, message="FA2_WRONG_LEVEL")

        # Check that, if defined, max checkpoints is larger than zero
        sp.verify(~params.max_checkpoints.is_some() | 
                  (params.max_checkpoints.open_some() > 0),
                  message="FA2_WRONG_MAX_CHECKPOINTS")

        # Check if the owner has any checkpoints
        with sp.if_(~self.data.n_checkpoints.contains(params.owner)):
            # No checkpoints implies zero balance
            sp.result(sp.nat(0))
        with sp.else_():
            # Define the upper and lower checkpoint limits
            lower = sp.local("lower", sp.nat(0))
            upper = sp.local("upper", sp.as_nat(self.data.n_checkpoints[params.owner] - 1))

            with sp.if_(params.max_checkpoints.is_some() & (params.max_checkpoints.open_some() <= upper.value)):
                lower.value = sp.as_nat(upper.value - params.max_checkpoints.open_some() + 1)

            # Check if the requested level is older than the first checkpoint
            with sp.if_(params.level < self.data.checkpoints[(params.owner, lower.value)].level):
                # The balance was zero at the requested level
                sp.result(sp.nat(0))
            with sp.else_():
                # Perform a binary search to find the correct checkpoint
                # https://en.wikipedia.org/wiki/Binary_search_algorithm#Alternative_procedure
                with sp.while_(lower.value < upper.value):
                    # Get the central index using the ceiling value
                    center = sp.local("center", sp.as_nat(upper.value - (sp.as_nat(upper.value - lower.value) // 2)))

                    # Check in which half we should continue the search
                    with sp.if_(params.level < self.data.checkpoints[(params.owner, center.value)].level):
                        # Search the lower half
                        upper.value = sp.as_nat(center.value - 1)
                    with sp.else_():
                        # Search the upper half
                        lower.value = center.value

                # Return the balance at the lower index checkpoint
                sp.result(self.data.checkpoints[(params.owner, lower.value)].balance)

    @sp.onchain_view(pure=True)
    def get_balance(self, params):
        """Returns the owner token balance.

        """
        # Define the input parameter data type
        sp.set_type(params, sp.TRecord(
            owner=sp.TAddress,
            token_id=sp.TNat).layout(("owner", "token_id")))

        # Check that the token exists
        sp.verify(params.token_id == 0, message="FA2_TOKEN_UNDEFINED")

        # Return the owner token balance
        sp.result(self.data.ledger.get(params.owner, 0))

    @sp.onchain_view(pure=True)
    def total_supply(self, token_id):
        """Returns the total supply for a given token id.

        """
        # Define the input parameter data type
        sp.set_type(token_id, sp.TNat)

        # Check that the token exists
        sp.verify(token_id == 0, message="FA2_TOKEN_UNDEFINED")

        # Return the token total supply
        sp.result(self.data.supply)

    @sp.offchain_view(pure=True)
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
        sp.verify(params.token_id == 0, message="FA2_TOKEN_UNDEFINED")

        # Return true if the token operator exists
        sp.result(self.data.operators.contains(params))

    @sp.offchain_view(pure=True)
    def token_metadata(self, token_id):
        """Returns the token metadata.

        """
        # Define the input parameter data type
        sp.set_type(token_id, sp.TNat)

        # Return the token metadata
        sp.result(self.data.token_metadata.get(
            token_id, message="FA2_TOKEN_UNDEFINED"))


# With smartpy-cli and teia_sc we can do some coverage and add further error tests:
if 'tzip16_error_inline' in environ.get('TEIA_SC_PARAMS', '').split(':'):
    from teia_sc.error_collection import ErrorCollection
    # Start collection of smart contract errors (for runtime tests)
    DAOToken.error_collection = ErrorCollection(DAOToken.__name__
            ).inject_into_smartpy(sp).add_base_metadata(DAOToken)

sp.add_compilation_target("daoToken", DAOToken(
    administrator=sp.address("tz1M9CMEtsXm3QxA7FmMU2Qh7xzsuGXVbcDr"),
    metadata=sp.utils.metadata_of_url("ipfs://aaa"),
    token_metadata=sp.utils.bytes_of_string("ipfs://bbb"),
    supply=1000000000000,
    max_share=50000000000))
