import smartpy as sp


class SubscriptionFee(sp.Contract):
    """This contract calculates and distributes the subscription fees
    associated to a specific token contract.

    """

    COLLECTION_FEE_TYPE = sp.TRecord(
        # The fee in mutez
        fee=sp.TMutez,
        # The fee payment interval in days
        interval=sp.TNat,
        # The fee recipient
        recipient=sp.TAddress,
        # The date when the fee doesn't need to be paid anymore
        end_date=sp.TOption(sp.TTimestamp)).layout(
            ("fee", ("interval", ("recipient", "end_date"))))

    def __init__(self, administrator, metadata, token_contract):
        """Initializes the contract.

        """
        # Define the contract storage data types for clarity
        self.init_type(sp.TRecord(
            # The contract administrator
            administrator=sp.TAddress,
            # The contract metadata
            metadata=sp.TBigMap(sp.TString, sp.TBytes),
            # The token contract
            token_contract=sp.TAddress,
            # The big map with the token owners deposits to pay the fees
            deposits=sp.TBigMap(sp.TAddress, sp.TMutez),
            # The big map with the fee information for each collection
            fees=sp.TBigMap(sp.TNat, SubscriptionFee.COLLECTION_FEE_TYPE),
            # The big map with the tokens next fee payment information
            next_payments=sp.TBigMap(sp.TNat, sp.TTimestamp),
             # The big map with the tokens fee payment approvals
            approved_tokens=sp.TBigMap(
                sp.TPair(sp.TAddress, sp.TNat), sp.TUnit),
            # The proposed new administrator address
            proposed_administrator=sp.TOption(sp.TAddress)))

        # Initialize the contract storage
        self.init(
            administrator=administrator,
            metadata=metadata,
            token_contract=token_contract,
            deposits=sp.big_map(),
            fees=sp.big_map(),
            next_payments=sp.big_map(),
            approved_tokens=sp.big_map(),
            proposed_administrator=sp.none)

    def check_no_tez_transfer(self):
        """Checks that no tez were transferred in the operation.

        """
        sp.verify(sp.amount == sp.mutez(0), message="SFEE_TEZ_TRANSFER")

    def get_deposit(self, user):
        """Gets the amount of mutez in the user deposit.

        """
        return self.data.deposits.get(user, sp.mutez(0))

    def check_is_administrator(self):
        """Checks that the address that called the entry point is the contract
        administrator.

        """
        sp.verify(sp.sender == self.data.administrator,
                  message="SFEE_NOT_ADMIN")

    def check_is_token_contract(self):
        """Checks that the address that called the entry point is the token
        contract.

        """
        sp.verify(sp.sender == self.data.token_contract,
                  message="SFEE_NOT_TOKEN_CONTRACT")

    def check_collection_exists(self, collection_id):
        """Checks that the given collection exists.

        """
        sp.verify(self.data.fees.contains(collection_id),
                  message="SFEE_COLLECTION_UNDEFINED")

    def check_token_exists(self, token_id):
        """Checks that the given token exists.

        """
        sp.verify(self.data.next_payments.contains(token_id),
                  message="SFEE_TOKEN_UNDEFINED")

    def check_token_is_approved(self, user, token_id):
        """Checks that the user approved to pay the token fees.

        """
        sp.verify(self.data.approved_tokens.contains((user, token_id)),
                  message="SFEE_TOKEN_NOT_APPROVED")

    def get_token_collection(self, token_id):
        """Gets the token collection id from the token contract on-chain view.

        """
        return sp.view(
            name="token_collection",
            address=self.data.token_contract,
            param=token_id,
            t=sp.TNat).open_some()

    def get_token_owner(self, token_id):
        """Gets the token owner from the token contract on-chain view.

        """
        return sp.view(
            name="token_owner",
            address=self.data.token_contract,
            param=token_id,
            t=sp.TAddress).open_some()

    @sp.entry_point
    def default(self, unit):
        """Default entrypoint that allows receiving tez transfers in the same
        way as one would do with a normal tz wallet.

        This is mostly used to redirect staking rewards or donations to the
        contract administrator deposit.

        """
        # Define the input parameter data type
        sp.set_type(unit, sp.TUnit)

        # Move the transferred tez amount to the contract administrator deposit
        self.data.deposits[self.data.administrator] = self.get_deposit(
            self.data.administrator) + sp.amount

    @sp.entry_point
    def set_delegate(self, baker):
        """Delegates the tez stored in the contract to the given baker.

        """
        # Define the input parameter data type
        sp.set_type(baker, sp.TOption(sp.TKeyHash))

        # Check that the administrator executed the entry point
        self.check_is_administrator()

        # Set the new delegate
        sp.set_delegate(baker)

    @sp.entry_point
    def transfer_to_deposit(self, unit):
        """Transfers some mutez to the sender deposit.

        """
        # Define the input parameter data type
        sp.set_type(unit, sp.TUnit)

        # Add the transferred amount to the sender deposit
        self.data.deposits[sp.sender] = self.get_deposit(sp.sender) + sp.amount

    @sp.entry_point
    def withdraw_from_deposit(self, amount):
        """Withdraws a given amount of mutez from the sender deposit.

        """
        # Define the input parameter data type
        sp.set_type(amount, sp.TMutez)

        # Check that no tez have been transferred
        self.check_no_tez_transfer()

        # Check that the amount to withdraw is larger than zero
        sp.verify(amount > sp.mutez(0), message="SFEE_WRONG_TEZ_AMOUNT")

        # Check that the sender deposit has enough funds
        deposit = sp.compute(self.get_deposit(sp.sender))
        sp.verify(deposit >= amount, message="SFEE_INSUFFICIENT_TEZ_BALANCE")

        # Remove the amount from the sender deposit
        self.data.deposits[sp.sender] = deposit - amount

        # Transfer the tez amount to the sender
        sp.send(sp.sender, amount)

    @sp.entry_point
    def add_fee(self, params):
        """Adds the subscription fee information for a new collection.

        """
        # Define the input parameter data type
        sp.set_type(params, sp.TRecord(
            collection_id=sp.TNat,
            fee_information=SubscriptionFee.COLLECTION_FEE_TYPE).layout(
                ("collection_id", "fee_information")))

        # Check that the token contract executed the entry point
        self.check_is_token_contract()

        # Add the fee information
        self.data.fees[params.collection_id] = params.fee_information

    @sp.entry_point
    def add_token(self, params):
        """Adds the relevant information for a new token.

        """
        # Define the input parameter data type
        sp.set_type(params, sp.TRecord(
            token_id=sp.TNat,
            collection_id=sp.TNat).layout(
                ("token_id", "collection_id")))

        # Check that the token contract executed the entry point
        self.check_is_token_contract()

        # Check that the collection exists
        self.check_collection_exists(params.collection_id)

        # Add the next payment information
        self.data.next_payments[params.token_id] = sp.now.add_seconds(
            sp.to_int(self.data.fees[params.collection_id].interval * 24 * 3600))

    @sp.entry_point
    def token_approval(self, params):
        """The user approves or disapproves to pay fees for the given token.

        """
        # Define the input parameter data type
        sp.set_type(params, sp.TRecord(
            token_id=sp.TNat,
            approval=sp.TBool).layout(
                ("token_id", "approval")))

        # Check that no tez have been transferred
        self.check_no_tez_transfer()

        # Add or remove the token approval
        with sp.if_(params.approval):
            self.data.approved_tokens[(sp.sender, params.token_id)] = sp.unit
        with sp.else_():
            del self.data.approved_tokens[(sp.sender, params.token_id)]

    @sp.entry_point
    def pay_fees(self, params):
        """Pays the fees associated to a given token.

        Any user can pay the fees of a given token. They don't need to be the
        token owner.

        This is necessary when the token is transferred to a contract that
        might not have a way to pay the fees.

        """
        # Define the input parameter data type
        sp.set_type(params, sp.TRecord(
            token_id=sp.TNat,
            payments=sp.TNat).layout(
                ("token_id", "payments")))

        # Check that no tez have been transferred
        self.check_no_tez_transfer()

        # Check that the token exists
        self.check_token_exists(params.token_id)

        # Check that the fee recipient is not the current token owner, since
        # the fee recipient never pays fees
        fee_information = sp.compute(
            self.data.fees[self.get_token_collection(params.token_id)])
        token_owner = self.get_token_owner(params.token_id)
        sp.verify(fee_information.recipient != token_owner,
                  message="SFEE_OWNER_IS_FEE_RECIPIENT")

        # Check that the end date has not been reached
        next_payment = sp.compute(self.data.next_payments[params.token_id])
        sp.verify((~fee_information.end_date.is_some()) | 
                  (next_payment < fee_information.end_date.open_some()),
                  message="SFEE_END_DATE_REACHED")

        # Check that the sender approved to pay the token fees
        self.check_token_is_approved(sp.sender, params.token_id)

        # Calculate the amount of fees to pay
        fee_amount = sp.compute(sp.mul(params.payments, fee_information.fee))

        # Check if there is some fee to pay
        with sp.if_(fee_amount > sp.mutez(0)):
            # Check that the sender has enough tez in their deposit to pay
            deposit = sp.compute(self.get_deposit(sp.sender))
            sp.verify(deposit >= fee_amount,
                      message="SFEE_INSUFFICIENT_TEZ_BALANCE")

            # Subtract the fee amount from the sender deposit
            self.data.deposits[sp.sender] = deposit - fee_amount

            # Send the fee amount to the fee recipient
            sp.send(fee_information.recipient, fee_amount)

        # Update the deadline for the next payment
        self.data.next_payments[params.token_id] = next_payment.add_seconds(
                sp.to_int(params.payments * fee_information.interval * 24 * 3600))

    @sp.entry_point
    def apply_fees(self, token_id):
        """Applies the fees associated to a given token.

        Anyone can call this entrypoint.

        If the owner does not have enough tez in their deposit to pay the fees,
        the token is sent to the fee recipient.

        """
        # Define the input parameter data type
        sp.set_type(token_id, sp.TNat)

        # Check that no tez have been transferred
        self.check_no_tez_transfer()

        # Check that the token exists
        self.check_token_exists(token_id)

        # Check that the fee recipient is not the current token owner, since
        # the fee recipient never pays fees
        fee_information = sp.compute(
            self.data.fees[self.get_token_collection(token_id)])
        token_owner = sp.compute(self.get_token_owner(token_id))
        sp.verify(fee_information.recipient != token_owner,
                  message="SFEE_OWNER_IS_FEE_RECIPIENT")

        # Check that the end date has not been reached
        next_payment = sp.compute(self.data.next_payments[token_id])
        sp.verify((~fee_information.end_date.is_some()) | 
                  (next_payment < fee_information.end_date.open_some()),
                  message="SFEE_END_DATE_REACHED")

        # Check if the deadline to pay the fees has expired
        with sp.if_(sp.now > next_payment):
            # Calculate the amount of fees to pay
            payments = sp.compute(1 + (
                sp.as_nat(sp.now - next_payment) // (fee_information.interval * 24 * 3600)))
            fee_amount = sp.compute(sp.mul(payments, fee_information.fee))

            # Check if there is some fee to pay
            with sp.if_(fee_amount > sp.mutez(0)):
                # Check if owner has enough tez in their deposit to pay the fee
                # and has accepted to pay the fees for that token
                deposit = sp.compute(self.get_deposit(token_owner))
                approved = self.data.approved_tokens.contains(
                    (token_owner, token_id))

                with sp.if_((deposit >= fee_amount) & approved):
                    # Subtract the fee amount from the owner deposit
                    self.data.deposits[token_owner] = deposit - fee_amount

                    # Send the fee amount to the fee recipient
                    sp.send(fee_information.recipient, fee_amount)

                    # Update the deadline for the next payment
                    self.data.next_payments[token_id] = next_payment.add_seconds(
                        sp.to_int(payments * fee_information.interval * 24 * 3600))
                with sp.else_():
                    with sp.if_((deposit > sp.mutez(0)) & approved):
                        # Send whatever is available in the owner deposit to
                        # the fee recipient
                        sp.send(fee_information.recipient, deposit)

                        # Set the token owner deposit to zero
                        self.data.deposits[token_owner] = sp.mutez(0)

                    # Transfer the token to the fee recipient
                    transfer_handle = sp.contract(
                        t=sp.TList(sp.TRecord(
                            from_=sp.TAddress,
                            txs=sp.TList(sp.TRecord(
                                to_=sp.TAddress,
                                token_id=sp.TNat,
                                amount=sp.TNat).layout(("to_", ("token_id", "amount")))))),
                        address=self.data.token_contract,
                        entry_point="transfer").open_some()
                    sp.transfer(
                        arg=sp.list([sp.record(
                            from_=token_owner,
                            txs=sp.list([sp.record(
                                to_=fee_information.recipient,
                                token_id=token_id,
                                amount=1)]))]),
                        amount=sp.mutez(0),
                        destination=transfer_handle)

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
            message="SFEE_NO_NEW_ADMIN"), message="SFEE_NOT_PROPOSED_ADMIN")

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


sp.add_compilation_target("subscriptionFee", SubscriptionFee(
    administrator=sp.address("tz1M9CMEtsXm3QxA7FmMU2Qh7xzsuGXVbcDr"),
    metadata=sp.utils.metadata_of_url("ipfs://bbb"),
    token_contract=sp.address("KT1M9CMEtsXm3QxA7FmMU2Qh7xzsuGXVbcDr")))
