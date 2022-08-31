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

    TOKEN_FEE_VALUE_TYPE = sp.TRecord(
        # The current price set by the token owner
        price=sp.TMutez,
        # The Harberger fee in per mile
        fee=sp.TNat,
        # The Harberger fee recipient
        fee_recipient=sp.TAddress,
        # The deadline for the next fee payment
        next_payment=sp.TTimestamp).layout(
            ("price", ("fee", ("fee_recipient", "next_payment"))))

    OPERATOR_KEY_TYPE = sp.TRecord(
        # The token owner
        owner=sp.TAddress,
        # The operator allowed by the owner to transfer their token
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
            ledger=sp.TBigMap(sp.TNat, sp.TAddress),
            # The big map with the tokens metadata
            token_metadata=sp.TBigMap(
                sp.TNat, HarbergerToken.TOKEN_METADATA_VALUE_TYPE),
            # The big map with the tokens fee information
            token_fee=sp.TBigMap(
                sp.TNat, HarbergerToken.TOKEN_FEE_VALUE_TYPE),
            # The big map with the tokens operators
            operators=sp.TBigMap(HarbergerToken.OPERATOR_KEY_TYPE, sp.TUnit),
            # The big map with the token owners deposits to pay the fees
            deposits=sp.TBigMap(sp.TAddress, sp.TMutez),
            # The proposed new administrator address
            proposed_administrator=sp.TOption(sp.TAddress),
            # A counter that tracks the total number of tokens minted so far
            counter=sp.TNat))

        # Initialize the contract storage
        self.init(
            administrator=administrator,
            metadata=metadata,
            ledger=sp.big_map(),
            token_metadata=sp.big_map(),
            token_fee=sp.big_map(),
            operators=sp.big_map(),
            deposits=sp.big_map(),
            proposed_administrator=sp.none,
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
                "tools": ["SmartPy 0.9.1"],
                "location": "https://github.com/teia-community/teia-smart-contracts/blob/main/python/contracts/harbergerToken.py"
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
        sp.verify(token_id < self.data.counter, message="FA2_TOKEN_UNDEFINED")

    @sp.entry_point
    def transfer_to_deposit(self, unit):
        """Transfers some mutez to the sender deposit.

        """
        # Define the input parameter data type
        sp.set_type(unit, sp.TUnit)

        # Add the transferred amount to the sender deposit
        self.data.deposits[sp.sender] = self.data.deposits.get(
            sp.sender, sp.mutez(0)) + sp.amount

    @sp.entry_point
    def withdraw_from_deposit(self, amount):
        """Withdraws a given amount of mutez from the sender deposit.

        """
        # Define the input parameter data type
        sp.set_type(amount, sp.TMutez)

        # Check that the amount to send is larger than zero
        sp.verify(amount > sp.mutez(0), message="FA2_WRONG_TEZ_AMOUNT")

        # Check that the sender deposit has enough funds
        deposit = sp.compute(self.data.deposits.get(sp.sender, sp.mutez(0)))
        sp.verify(deposit >= amount, message="FA2_INSUFFICIENT_TEZ_BALANCE")

        # Remove the amount from the sender deposit
        self.data.deposits[sp.sender] = deposit - amount

        # Transfer the tez to the sender
        sp.send(sp.sender, amount)

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

        # Check that the administrator executed the entry point
        self.check_is_administrator()

        # Check that the fee does not exceed 100%
        sp.verify(params.fee <= 1000, message="FA2_INVALID_FEE")

        # Update the ledger and token metadata big maps
        token_id = sp.compute(self.data.counter)
        self.data.ledger[token_id] = params.creator
        self.data.token_metadata[token_id] = sp.record(
            token_id=token_id,
            token_info=params.metadata)

        # Add the fee information.
        # The fee recipient is set to the token creator.
        # The next payment value is not important at this moment, because the
        # first owner is the fee recipient and they never pay fees
        self.data.token_fee[token_id] = sp.record(
            price=params.price,
            fee=params.fee,
            fee_recipient=params.creator,
            next_payment=sp.now)

        # Increase the tokens counter
        self.data.counter += 1

    @sp.entry_point
    def set_price(self, params):
        """Sets a new price for the token.

        Before updating the price all remaining fees need to be paid.

        """
        # Define the input parameter data type
        sp.set_type(params, sp.TRecord(
            token_id=sp.TNat,
            price=sp.TMutez).layout(
                ("token_id", "price")))

        # Check that the token exists
        self.check_token_exists(params.token_id)

        # Check that the sender is the token owner
        sp.verify(sp.sender == self.data.ledger[params.token_id],
                  message="FA2_SENDER_IS_NOT_OWNER")

        # Get the fee information
        fee_information = sp.compute(self.data.token_fee[params.token_id])

        # Charge the fee if the owner is not the fee recipient
        with sp.if_(sp.sender != fee_information.fee_recipient):
            # Calculate the fee amount to pay for the new price
            fee = sp.local("fee",
                sp.split_tokens(params.price, fee_information.fee, 1000))

            # Calculate the remaining fee amount from the old price
            montly_payment = sp.split_tokens(
                fee_information.price, fee_information.fee, 1000)
            remaining_fee = sp.compute(sp.split_tokens(
                montly_payment, abs(sp.now - fee_information.next_payment),
                3600 * 24 * 30))

            # Combine the two fees
            with sp.if_(sp.now < fee_information.next_payment):
                with sp.if_(fee.value > remaining_fee):
                    fee.value -= remaining_fee
                with sp.else_():
                    fee.value = sp.mutez(0)
            with sp.else_():
                fee.value += remaining_fee

            # Check if there is some fee to pay
            with sp.if_(fee.value > sp.mutez(0)):
                # Check that the owner has enough tez in their deposit to pay
                # the fee
                deposit = sp.compute(
                    self.data.deposits.get(sp.sender, sp.mutez(0)))
                sp.verify(deposit >= fee.value,
                          message="FA2_INSUFFICIENT_TEZ_BALANCE")

                # Subtract the fee from the owner deposit
                self.data.deposits[sp.sender] = deposit - fee.value

                # Send the fee to the fee recipient
                sp.send(fee_information.fee_recipient, fee.value)

        # Update the fee information
        self.data.token_fee[params.token_id] = sp.record(
            price=params.price,
            fee=fee_information.fee,
            fee_recipient=fee_information.fee_recipient,
            next_payment=sp.now.add_days(30))

    @sp.entry_point
    def pay_fees(self, params):
        """Pays the fees associated to a given token.

        Any user can pay the fees of a given token. They don't need to own the
        token.

        """
        # Define the input parameter data type
        sp.set_type(params, sp.TRecord(
            token_id=sp.TNat,
            months=sp.TNat).layout(
                ("token_id", "months")))

        # Check that the token exists
        self.check_token_exists(params.token_id)

        # Get the fee information
        fee_information = sp.compute(self.data.token_fee[params.token_id])

        # Check that the fee recipient is not the current token owner, since
        # the fee recipient never pays fees
        sp.verify(fee_information.fee_recipient != self.data.ledger[params.token_id],
                  message="FA2_OWNER_IS_FEE_RECIPIENT")

        # Calculate the amount of fees to pay
        fee = sp.compute(sp.mul(params.months, sp.split_tokens(
            fee_information.price, fee_information.fee, 1000)))

        # Check if there is some fee to pay
        with sp.if_(fee > sp.mutez(0)):
            # Check that the sender has enough tez in their deposit to pay
            deposit = sp.compute(self.data.deposits.get(sp.sender, sp.mutez(0)))           
            sp.verify(deposit >= fee,
                      message="FA2_INSUFFICIENT_TEZ_BALANCE")

            # Subtract the fee from the sender deposit
            self.data.deposits[sp.sender] = deposit - fee

            # Send the fee to the fee recipient
            sp.send(fee_information.fee_recipient, fee)

        # Update the deadline for the next payment
        self.data.token_fee[params.token_id].next_payment = fee_information.next_payment.add_days(
            sp.mul(params.months, 30))

    @sp.entry_point
    def apply_fees(self, token_id):
        """Applies the fees associated to a given token.

        Anyone can call this entrypoint.

        If the owner does not have enough tez in their deposit to pay the fees,
        the token price is set to zero, and could be collected by anyone.

        """
        # Define the input parameter data type
        sp.set_type(token_id, sp.TNat)

        # Check that the token exists
        self.check_token_exists(token_id)

        # Get the fee information
        fee_information = sp.compute(self.data.token_fee[token_id])

        # Check that the fee recipient is not the current token owner, since
        # the fee recipient never pays fees
        owner = sp.compute(self.data.ledger[token_id])
        sp.verify(fee_information.fee_recipient != owner,
                  message="FA2_OWNER_IS_FEE_RECIPIENT")

        # Check if the deadline to pay the fees has expired
        with sp.if_(sp.now > fee_information.next_payment):
            # Calculate the amount of fees to pay
            montly_payment = sp.split_tokens(
                fee_information.price, fee_information.fee, 1000)
            months_to_pay = sp.compute(1 + (
                sp.as_nat(sp.now - fee_information.next_payment) // sp.nat(3600 * 24 * 30)))
            fee = sp.compute(sp.mul(months_to_pay, montly_payment))

            # Check if there is some fee to pay
            with sp.if_(fee > sp.mutez(0)):
                # Check if owner has enough tez in their deposit to pay the fee
                deposit = sp.compute(
                    self.data.deposits.get(owner, sp.mutez(0)))

                with sp.if_(deposit >= fee):
                    # Subtract the fee from the owners deposit
                    self.data.deposits[owner] = deposit - fee

                    # Send the fee to the fee recipient
                    sp.send(fee_information.fee_recipient, fee)

                    # Update the deadline for the next payment
                    self.data.token_fee[token_id].next_payment = fee_information.next_payment.add_days(
                        sp.mul(months_to_pay, 30))
                with sp.else_():
                    with sp.if_(deposit > sp.mutez(0)):
                        # Send whatever is available in the owner deposit to the
                        # fee recipient
                        sp.send(fee_information.fee_recipient, deposit)

                        # Set the owner deposit to zero
                        self.data.deposits[owner] = sp.mutez(0)

                    # Set the token price to zero, so anyone could collect it
                    self.data.token_fee[token_id].price = sp.mutez(0)

    @sp.entry_point
    def collect(self, params):
        """Collects a given token and sets a new price for it.

        """
        # Define the input parameter data type
        sp.set_type(params, sp.TRecord(
            token_id=sp.TNat,
            price=sp.TMutez).layout(
                ("token_id", "price")))

        # Check that the token exists
        self.check_token_exists(params.token_id)

        # Get the fee information
        fee_information = sp.compute(self.data.token_fee[params.token_id])

        # Check that the provided tez amount is exactly the token price
        sp.verify(sp.amount == fee_information.price,
                  message="FA2_WRONG_TEZ_AMOUNT")

        # Send the tez to the previous owner
        with sp.if_(sp.amount > sp.mutez(0)):
            sp.send(self.data.ledger[params.token_id], sp.amount)

        # Calculate the fee amount to pay for the new price
        fee = sp.compute(
            sp.split_tokens(params.price, fee_information.fee, 1000))

        # Check if there is some fee to pay
        with sp.if_(fee > sp.mutez(0)):
            # Check that the sender has enough tez in their deposit to pay
            deposit = sp.compute(self.data.deposits.get(sp.sender, sp.mutez(0)))
            sp.verify(deposit >= fee, message="FA2_INSUFFICIENT_TEZ_BALANCE")

            # Subtract the fee from the sender deposit
            self.data.deposits[sp.sender] = deposit - fee

            # Send the fee to the fee recipient
            sp.send(fee_information.fee_recipient, fee)

        # Update the fee information
        self.data.token_fee[params.token_id] = sp.record(
            price=params.price,
            fee=fee_information.fee,
            fee_recipient=fee_information.fee_recipient,
            next_payment=sp.now.add_days(30))

        # Update the ledger information
        self.data.ledger[params.token_id] = sp.sender

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
                token_id = sp.compute(tx.token_id)
                self.check_token_exists(token_id)

                # Check that the sender is one of the token operators
                owner = sp.compute(transfer.from_)
                sp.verify(
                    (sp.sender == owner) | 
                    self.data.operators.contains(sp.record(
                        owner=owner,
                        operator=sp.sender,
                        token_id=token_id)),
                    message="FA2_NOT_OPERATOR")

                # Check that the transfer amount is not zero
                with sp.if_(tx.amount > 0):
                    # Check that the owner really owns the token
                    sp.verify(self.data.ledger[token_id] == owner,
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
            with sp.if_(self.data.ledger[request.token_id] == request.owner):
                sp.result(sp.record(request=request, balance=1))
            with sp.else_():
                sp.result(sp.record(request=request, balance=0))

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
            message="FA_NO_NEW_ADMIN"), message="FA_NOT_PROPOSED_ADMIN")

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
        with sp.if_(self.data.ledger[params.token_id] == params.owner):
            sp.result(sp.nat(1))
        with sp.else_():
            sp.result(sp.nat(0))

    @sp.onchain_view(pure=True)
    def total_supply(self, token_id):
        """Returns the total supply for a given token id.

        """
        # Define the input parameter data type
        sp.set_type(token_id, sp.TNat)

        # Check that the token exists
        self.check_token_exists(token_id)

        # Return the token total supply
        sp.result(1)

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


sp.add_compilation_target("harbergerToken", HarbergerToken(
    administrator=sp.address("tz1M9CMEtsXm3QxA7FmMU2Qh7xzsuGXVbcDr"),
    metadata=sp.utils.metadata_of_url("ipfs://bbb")))
