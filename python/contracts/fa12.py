import smartpy as sp


class FA12(sp.Contract):
    """This contract tries to simplify and extend the FA1.2 contract template
    example in smartpy.io v0.16.0.

    The contract follows the FA1.2 standard specification:
    https://gitlab.com/tezos/tzip/-/blob/master/proposals/tzip-7/tzip-7.md

    """

    BALANCES_VALUE_TYPE = sp.TRecord(
        # The owner token spending approvals
        approvals=sp.TMap(sp.TAddress, sp.TNat),
        # The owner token balance
        balance=sp.TNat).layout(("approvals", "balance"))

    TOKEN_METADATA_VALUE_TYPE = sp.TRecord(
        # The token id
        token_id=sp.TNat,
        # The map with the token metadata information
        token_info=sp.TMap(sp.TString, sp.TBytes)).layout(
            ("token_id", "token_info"))

    def __init__(self, administrator, metadata, token_metadata):
        """Initializes the contract.

        """
        # Define the contract storage data types for clarity
        self.init_type(sp.TRecord(
            # The contract administrator
            administrator=sp.TAddress,
            # The contract metadata
            metadata=sp.TBigMap(sp.TString, sp.TBytes),
            # The token balances
            balances=sp.TBigMap(sp.TAddress, FA12.BALANCES_VALUE_TYPE),
            # The token total supply
            totalSupply=sp.TNat,
            # The big map with the token metadata
            token_metadata=sp.TBigMap(sp.TNat, FA12.TOKEN_METADATA_VALUE_TYPE)))

        # Initialize the contract storage
        self.init(
            administrator=administrator,
            metadata=metadata,
            balances=sp.big_map(),
            totalSupply=0,
            token_metadata=sp.big_map({
                0: sp.record(
                    token_id=0,
                    token_info=token_metadata)
                }))

        # Build the TZIP-016 contract metadata
        # This is helpful to get the off-chain views code in json format
        contract_metadata = {
            "name": "Extended FA1.2 template contract",
            "description": "This contract tries to simplify and extend the "
                "FA1.2 contract template example in smartpy.io v0.16.0",
            "version": "v1.0.0",
            "authors": ["Teia Community <https://twitter.com/TeiaCommunity>"],
            "homepage": "https://teia.art",
            "source": {
                "tools": ["SmartPy 0.16.0"],
                "location": "https://github.com/teia-community/teia-smart-contracts/blob/main/python/contracts/fa12.py"
            },
            "interfaces": ["TZIP-007", "TZIP-016"],
            "views": [
                self.getAllowance,
                self.getBalance,
                self.getTotalSupply]
        }

        self.init_metadata("contract_metadata", contract_metadata)

    def check_is_administrator(self):
        """Checks that the address that called the entry point is the contract
        administrator.

        """
        sp.verify(sp.sender == self.data.administrator,
                  message="FA1.2_NotAdmin")

    @sp.entry_point
    def mint(self, params):
        """Mints new token editions.

        """
        # Define the input parameter data type
        sp.set_type(params, sp.TRecord(
            address=sp.TAddress,
            value=sp.TNat).layout(("address", "value")))

        # Check that the administrator executed the entry point
        self.check_is_administrator()

        # Update the balances big map
        with sp.if_(self.data.balances.contains(params.address)):
            self.data.balances[params.address].balance += params.value
        with sp.else_():
            self.data.balances[params.address] = sp.record(
                approvals={},
                balance=params.value)

        # Increase the token total supply
        self.data.totalSupply += params.value

    @sp.entry_point
    def burn(self, params):
        """Burns some token editions.

        """
        # Define the input parameter data type
        sp.set_type(params, sp.TRecord(
            address=sp.TAddress,
            value=sp.TNat).layout(("address", "value")))

        # Check that the administrator executed the entry point
        self.check_is_administrator()

        # Update the balances big map
        sp.verify(self.data.balances.contains(params.address),
                  message="FA1.2_InsufficientBalance")
        self.data.balances[params.address].balance = sp.as_nat(
            self.data.balances[params.address].balance - params.value,
            "FA1.2_InsufficientBalance")

        # Decrease the token total supply
        self.data.totalSupply = sp.as_nat(self.data.totalSupply - params.value)

    @sp.entry_point
    def transfer(self, params):
        """The owner or spender transfers some token editions to a given
        address.

        """
        # Define the input parameter data type
        sp.set_type(params, sp.TRecord(
            from_=sp.TAddress,
            to_=sp.TAddress,
            value=sp.TNat).layout(("from_ as from", ("to_ as to", "value"))))

        # Check that the owner has enough editions
        sp.verify(self.data.balances.contains(params.from_) & 
                  (self.data.balances[params.from_].balance >= params.value),
                  message="FA1.2_InsufficientBalance")

        # Check that the owner, spender or the administrator executed the entry point
        sp.verify((sp.sender == params.from_) | 
                  (self.data.balances[params.from_].approvals.get(sp.sender, default_value=sp.nat(0)) >= params.value) | 
                  (sp.sender == self.data.administrator),
                  message="FA1.2_NotAllowed")

        # Update the balances big map
        with sp.if_(self.data.balances.contains(params.to_)):
            self.data.balances[params.to_].balance += params.value
        with sp.else_():
            self.data.balances[params.to_] = sp.record(
                approvals={},
                balance=params.value)

        self.data.balances[params.from_].balance = sp.as_nat(
            self.data.balances[params.from_].balance - params.value)

        with sp.if_((sp.sender != params.from_) & (sp.sender != self.data.administrator)):
            self.data.balances[params.from_].approvals[sp.sender] = sp.as_nat(
                self.data.balances[params.from_].approvals[sp.sender] - params.value)

    @sp.entry_point
    def approve(self, params):
        """The owner approves another user to spend some of their token
        editions.

        """
        # Define the input parameter data type
        sp.set_type(params, sp.TRecord(
            spender=sp.TAddress,
            value=sp.TNat).layout(("spender", "value")))

        # Update the balances big map
        with sp.if_(self.data.balances.contains(sp.sender)):
            # Check that we are not trying to change the allowance from a
            # non-zero value to a non-zero value
            # https://docs.google.com/document/d/1YLPtQxZu1UAvO9cZ1O2RPXBbT0mooh4DYKjA_jp-RLM
            current_value = self.data.balances[sp.sender].approvals.get(
                params.spender, default_value=sp.nat(0))
            sp.verify((current_value == 0) | (params.value == 0),
                      message="FA1.2_UnsafeAllowanceChange")
            self.data.balances[sp.sender].approvals[params.spender] = params.value
        with sp.else_():
            self.data.balances[sp.sender] = sp.record(
                approvals={params.spender: params.value},
                balance=0)

    @sp.entry_point
    def safeApprove(self, params):
        """The owner approves another user to spend some of their token
        editions in a safer way than with the approve entry point.

        """
        # Define the input parameter data type
        sp.set_type(params, sp.TRecord(
            spender=sp.TAddress,
            value=sp.TNat,
            previous_value=sp.TNat).layout(
                ("spender", ("value", "previous_value"))))

        # Update the balances big map
        with sp.if_(self.data.balances.contains(sp.sender)):
            current_value = self.data.balances[sp.sender].approvals.get(
                params.spender, default_value=sp.nat(0))
            sp.verify(current_value == params.previous_value,
                message="FA1.2_UnsafeAllowanceChange")
            self.data.balances[sp.sender].approvals[params.spender] = params.value
        with sp.else_():
            sp.verify(params.previous_value == sp.nat(0),
                message="FA1.2_UnsafeAllowanceChange")
            self.data.balances[sp.sender] = sp.record(
                approvals={params.spender: params.value},
                balance=0)

    @sp.entry_point
    def update_metadata(self, params):
        """Updates the contract metadata.

        """
        # Define the input parameter data type
        sp.set_type(params, sp.TRecord(
            key=sp.TString,
            value=sp.TBytes).layout(("key", "value")))

        # Check that the administrator executed the entry point
        self.check_is_administrator()

        # Update the contract metadata
        self.data.metadata[params.key] = params.value

    @sp.entry_point
    def setAdministrator(self, administrator):
        """Sets the contract administrator to another address.

        """
        # Define the input parameter data type
        sp.set_type(administrator, sp.TAddress)

        # Check that the administrator executed the entry point
        self.check_is_administrator()

        # Set the new administrator address
        self.data.administrator = administrator

    @sp.onchain_view(pure=True)
    def getAllowance(self, params):
        """Returns the spender spending allowance for a given owner.

        """
        # Define the input parameter data type
        sp.set_type(params, sp.TRecord(
            owner=sp.TAddress,
            spender=sp.TAddress).layout(("owner", "spender")))

        # Return the spender allowance
        with sp.if_(self.data.balances.contains(params.owner)):
            sp.result(self.data.balances[params.owner].approvals.get(
                params.spender, default_value=sp.nat(0)))
        with sp.else_():
            sp.result(sp.nat(0))

    @sp.onchain_view(pure=True)
    def getBalance(self, owner):
        """Returns the owner balance.

        """
        # Define the input parameter data type
        sp.set_type(owner, sp.TAddress)

        # Return the owner balance
        with sp.if_(self.data.balances.contains(owner)):
            sp.result(self.data.balances[owner].balance)
        with sp.else_():
            sp.result(sp.nat(0))

    @sp.onchain_view(pure=True)
    def getTotalSupply(self):
        """Returns the token total supply.

        """
        sp.result(self.data.totalSupply)


sp.add_compilation_target("fa12", FA12(
    administrator=sp.address("tz1M9CMEtsXm3QxA7FmMU2Qh7xzsuGXVbcDr"),
    metadata=sp.utils.metadata_of_url("ipfs://aaa"),
    token_metadata={
            "decimals": sp.utils.bytes_of_string("18"),
            "name": sp.utils.bytes_of_string("My Great Token"),
            "symbol": sp.utils.bytes_of_string("MGT"),
            "icon": sp.utils.bytes_of_string("ipfs://aaa")}))
