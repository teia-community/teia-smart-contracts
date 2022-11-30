import smartpy as sp


class DeadMansSwitch(sp.Contract):
    """A dead man's switch contract. A multisig contract will take control of
    the funds in case the contract admin is dead or lost access to their keys.
    The admin needs to ping the contract regularly to indicate that they are
    still alive.

    """

    def __init__(self, metadata, administrator, multisig, ping_interval):
        """Initializes the contract.

        """
        # Define the contract storage data types for clarity
        self.init_type(sp.TRecord(
            # The contract metadata
            metadata=sp.TBigMap(sp.TString, sp.TBytes),
            # The contract administrator
            administrator=sp.TAddress,
            # The multisig contract address that will become the contract
            # administrator when the current one stops pinging the contract
            multisig=sp.TAddress,
            # The ping interval in days
            ping_interval=sp.TNat,
            # The last ping timestamp
            last_ping=sp.TTimestamp,
            # The proposed new administrator address
            proposed_administrator=sp.TOption(sp.TAddress)))

        # Initialize the contract storage
        self.init(
            metadata=metadata,
            administrator=administrator,
            multisig=multisig,
            ping_interval=ping_interval,
            last_ping=sp.now,
            proposed_administrator=sp.none)

    def check_is_administrator(self):
        """Checks that the address that called the entry point is the contract
        administrator.

        """
        sp.verify(sp.sender == self.data.administrator, message="DM_NOT_ADMIN")

    def check_is_multisig(self):
        """Checks that the address that called the entry point is the multisig
        contract.

        """
        sp.verify(sp.sender == self.data.multisig, message="DM_NOT_MULTISIG")

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
    def transfer_tez(self, params):
        """Transfers a given tez amount to the provided destination address.

        """
        # Define the input parameter data type
        sp.set_type(params, sp.TRecord(
            amount=sp.TMutez,
            destination=sp.TAddress))

        # Check that the administrator executed the entry point
        self.check_is_administrator()

        # Transfer the tez
        sp.send(params.destination, params.amount)

        # Update the last ping timestamp parameter
        self.data.last_ping = sp.now

    @sp.entry_point
    def transfer_tokens(self, params):
        """Transfers a FA2 or FA1.2 token to a given address.

        """
        # Define the input parameter data type
        sp.set_type(params, sp.TRecord(
            token_address=sp.TAddress,
            token_id=sp.TOption(sp.TNat),
            amount=sp.TNat,
            destination=sp.TAddress))

        # Check that the administrator executed the entry point
        self.check_is_administrator()

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

        # Update the last ping timestamp parameter
        self.data.last_ping = sp.now

    @sp.entry_point
    def ping(self, unit):
        """Pings the contract.

        """
        # Define the input parameter data type
        sp.set_type(unit, sp.TUnit)

        # Check that the administrator executed the entry point
        self.check_is_administrator()

        # Update the last ping timestamp parameter
        self.data.last_ping = sp.now

    @sp.entry_point
    def take_control(self, unit):
        """The multisig tries to take control of the contract.

        """
        # Define the input parameter data type
        sp.set_type(unit, sp.TUnit)

        # Check that the multisig executed the entry point
        self.check_is_multisig()

        # Check that the last ping is older than the ping interval time
        ping_deadline = self.data.last_ping.add_days(
            sp.to_int(self.data.ping_interval))
        sp.verify(sp.now > ping_deadline, message="DM_NOT_DEAD")

        # Set the multisig as the new contract administrator
        self.data.administrator = sp.sender

        # Update the last ping timestamp parameter
        self.data.last_ping = sp.now

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

        # Update the last ping timestamp parameter
        self.data.last_ping = sp.now

    @sp.entry_point
    def accept_administrator(self):
        """The proposed administrator accepts the contract administrator
        responsibilities.

        """
        # Check that the proposed administrator executed the entry point
        sp.verify(sp.sender == self.data.proposed_administrator.open_some(
            message="DM_NO_NEW_ADMIN"),
            message="DM_NOT_PROPOSED_ADMIN")

        # Set the new administrator address
        self.data.administrator = sp.sender

        # Reset the proposed administrator value
        self.data.proposed_administrator = sp.none

        # Update the last ping timestamp parameter
        self.data.last_ping = sp.now

    @sp.entry_point
    def set_multisig(self, multisig):
        """Sets the multisig contract address.

        """
        # Define the input parameter data type
        sp.set_type(multisig, sp.TAddress)

        # Check that the administrator executed the entry point
        self.check_is_administrator()

        # Set the new multisig contract address
        self.data.multisig = multisig

        # Update the last ping timestamp parameter
        self.data.last_ping = sp.now

    @sp.entry_point
    def set_ping_interval(self, ping_interval):
        """Sets the ping interval in days.

        """
        # Define the input parameter data type
        sp.set_type(ping_interval, sp.TNat)

        # Check that the administrator executed the entry point
        self.check_is_administrator()

        # Set the new ping interval
        self.data.ping_interval = ping_interval

        # Update the last ping timestamp parameter
        self.data.last_ping = sp.now


# Add a compilation target
sp.add_compilation_target("deadMansSwitch", DeadMansSwitch(
    metadata=sp.utils.metadata_of_url("ipfs://aaaa"),
    administrator=sp.address("tz111"),
    multisig=sp.address("KT111"),
    ping_interval=90))
