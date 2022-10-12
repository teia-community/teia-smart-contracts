import smartpy as sp


class Donations(sp.Contract):
    """A contract that handles donations to a list of addresses.

    This contract combines the fxhash and objkt.com implementations:
    https://github.com/ciphrd/public-contracts/blob/master/donations_ukraine.py
    https://smartpy.io/ide?cid=QmdaQK7XRt8Z6mcBmfqVxppj73kCbnDQDarq5rStoX9oMp&k=dc5cce6b6d07574e8a05

    """

    SPLITS_TYPE = sp.TList(sp.TRecord(
        # The address of the NGO that will receive the donations
        address=sp.TAddress,
        # The percentage per mile of the funds to donate
        pct=sp.TNat))

    def __init__(self, administrator, metadata, oXTZ):
        """Initializes the contract.

        """
        # Define the contract storage data types for clarity
        self.init_type(sp.TRecord(
            # The contract administrator
            administrator=sp.TAddress,
            # The contract metadata
            metadata=sp.TBigMap(sp.TString, sp.TBytes),
            # The oXTZ contract address
            oXTZ=sp.TAddress,
            # The list with the donations splits
            splits=Donations.SPLITS_TYPE,
            # The proposed new administrator address
            proposed_administrator=sp.TOption(sp.TAddress)))

        # Initialize the contract storage
        self.init(sp.record(
            administrator=administrator,
            metadata=metadata,
            oXTZ=oXTZ,
            splits=sp.list([]),
            proposed_administrator=sp.none))

    def check_is_administrator(self):
        """Checks that the address that called the entry point is the contract
        administrator.

        """
        sp.verify(sp.sender == self.data.administrator,
                  message="DONATIONS_NOT_ADMIN")

    def fa2_transfer(self, fa2, from_, to_, token_id, amount):
        """Transfers a number of editions of a FA2 token to another address.

        """
        # Get a handle to the FA2 token transfer entry point
        c = sp.contract(
            t=sp.TList(sp.TRecord(
                from_=sp.TAddress,
                txs=sp.TList(sp.TRecord(
                    to_=sp.TAddress,
                    token_id=sp.TNat,
                    amount=sp.TNat).layout(("to_", ("token_id", "amount")))))),
            address=fa2,
            entry_point="transfer").open_some()

        # Transfer the FA2 token editions to the new address
        sp.transfer(
            arg=sp.list([sp.record(
                from_=from_,
                txs=sp.list([sp.record(
                    to_=to_,
                    token_id=token_id,
                    amount=amount)]))]),
            amount=sp.mutez(0),
            destination=c)

    def fa12_transfer(self, fa12, from_, to_, value):
        """Transfers a number of editions of a FA1.2 token to another address.

        """
        # Get a handle to the FA1.2 token transfer entry point
        c = sp.contract(
            t=sp.TRecord(
                from_=sp.TAddress,
                to_=sp.TAddress,
                value=sp.TNat).layout(("from_ as from", ("to_ as to", "value"))),
            address=fa12,
            entry_point="transfer").open_some()

        # Transfer the FA1.2 token editions to the new address
        sp.transfer(
            arg=sp.record(
                from_=from_,
                to_=to_,
                value=value),
            amount=sp.mutez(0),
            destination=c)

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
    def withdraw(self, unit):
        """Transfers all the contract funds to the NGOs.

        """
        # Define the input parameter data type
        sp.set_type(unit, sp.TUnit)

        # Distribute the contract's balance
        balance = sp.compute(sp.balance)

        with sp.for_("split", self.data.splits) as split:
            sp.send(split.address, sp.split_tokens(balance, split.pct, 1000))

    @sp.entry_point
    def set_splits(self, splits):
        """Sets the donation splits.

        """
        # Define the input parameter data type
        sp.set_type(splits, Donations.SPLITS_TYPE)

        # Check that the administrator executed the entry point
        self.check_is_administrator()

        # Check that the splits percents add to 100%
        pct_sum = sp.local("pct_sum", sp.nat(0))

        with sp.for_("split", splits) as split:
            pct_sum.value += split.pct

        sp.verify(pct_sum.value == 1000, message="DONATIONS_INVALID_SPLITS")

        # Set the new splits
        self.data.splits = splits

    @sp.entry_point
    def forward_oXTZ(self, unit):
        """Initiates the forwarding of oXTZ by querying the oXTZ balance of
        this contract and subsequently calling unwrap on the oXTZ contract.

        """
        # Define the input parameter data type
        sp.set_type(unit, sp.TUnit)

        # Get a handle to the oXTZ getBalance entry point
        c = sp.contract(
            t=sp.TPair(
                sp.TAddress,
                sp.TContract(sp.TNat)),
            address=self.data.oXTZ,
            entry_point="getBalance").open_some()

        # Get the contract oXTZ balance and trigger the oXTZ unwrap entry point
        sp.transfer(
            arg=sp.pair(
                sp.self_address,
                sp.self_entry_point(entry_point="balance_callback")),
            amount=sp.mutez(0),
            destination=c)

    @sp.entry_point
    def balance_callback(self, balance):
        """oXTZ balance callback.

        """
        # Define the input parameter data type
        sp.set_type(balance, sp.TNat)

        # Check that the oXTZ contract executed the entry point
        sp.verify(sp.sender == self.data.oXTZ,
                  message="DONATIONS_NOT_OXTZ_ADDRESS")

        # Get a handle to the oXTZ unwrap entry point
        c = sp.contract(
            t=sp.TNat,
            address=self.data.oXTZ,
            entry_point="unwrap").open_some()

        # Unwrap all the oXTZ tokens in the contract
        sp.transfer(
            arg=balance,
            amount=sp.mutez(0),
            destination=c)

    @sp.entry_point
    def transfer_other_tokens(self, params):
        """Transfers other tokens that might have been sent to the contract.

        """
        # Define the input parameter data type
        sp.set_type(params, sp.TRecord(
            token_address=sp.TAddress,
            token_id=sp.TOption(sp.TNat),
            amount=sp.TNat,
            destination=sp.TAddress))

        # Check that the administrator executed the entry point
        self.check_is_administrator()

        # Check that the token address is not the oXTZ address
        sp.verify(params.token_address != self.data.oXTZ,
                  message="DONATIONS_OXTZ_ADDRESS")

        # Check if we have a FA2 or a FA1.2 token
        with sp.if_(params.token_id.is_some()):
            self.fa2_transfer(
                fa2=params.token_address,
                from_=sp.self_address,
                to_=params.destination,
                token_id=params.token_id.open_some(),
                amount=params.amount)
        with sp.else_():
            self.fa12_transfer(
                fa12=params.token_address,
                from_=sp.self_address,
                to_=params.destination,
                value=params.amount)

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
            message="DONATIONS_NO_NEW_ADMIN"),
            message="DONATIONS_NOT_PROPOSED_ADMIN")

        # Set the new administrator address
        self.data.administrator = sp.sender

        # Reset the proposed administrator value
        self.data.proposed_administrator = sp.none


sp.add_compilation_target("donations", Donations(
    administrator=sp.address("tz1RssrimWo3B8TpCajiNjqBD3MfhUwEgxod"),
    metadata=sp.utils.metadata_of_url("ipfs://bafkreicrnzzdn3v6fgvvtmpjr2op3x6qn2cgitktgxwxp4ezqmj2hqu3ry"),
    oXTZ=sp.address("KT1TjnZYs5CGLbmV6yuW169P8Pnr9BiVwwjz")))
