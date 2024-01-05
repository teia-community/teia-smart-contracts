import smartpy as sp


class SpanishInquisitionList(sp.Contract):
    """This contract represents a list of users that are blocked or allowed to
    transfer tokens.

    """

    LIST_TYPE = sp.TVariant(
        # The list contains users that are blocked to transfer tokens
        BLOCK=sp.TUnit,
        # The list contains users that are allowed to transfer tokens
        ALLOW=sp.TUnit)

    def __init__(self, administrator, metadata, type):
        """Initializes the contract.

        """
        # Define the contract storage data types for clarity
        self.init_type(sp.TRecord(
            # The contract administrator
            administrator=sp.TAddress,
            # The contract metadata
            metadata=sp.TBigMap(sp.TString, sp.TBytes),
            # The list type
            type=SpanishInquisitionList.LIST_TYPE,
            # The big map with the list members
            members=sp.TBigMap(sp.TAddress, sp.TUnit),
            # The proposed new administrator address
            proposed_administrator=sp.TOption(sp.TAddress)))

        # Initialize the contract storage
        self.init(
            administrator=administrator,
            metadata=metadata,
            type=type,
            members=sp.big_map(),
            proposed_administrator=sp.none)

    def check_is_administrator(self):
        """Checks that the address that called the entry point is the contract
        administrator.

        """
        sp.verify(sp.sender == self.data.administrator,
                  message="SI_LIST_NOT_ADMIN")

    @sp.entry_point
    def add_members(self, members):
        """Adds members to the list.

        """
        # Define the input parameter data type
        sp.set_type(members, sp.TList(sp.TAddress))

        # Check that the administrator executed the entry point
        self.check_is_administrator()

        # Add the members
        with sp.for_("member", members) as member:
            self.data.members[member] = sp.unit

    @sp.entry_point
    def remove_members(self, members):
        """Removes members from the list.

        """
        # Define the input parameter data type
        sp.set_type(members, sp.TList(sp.TAddress))

        # Check that the administrator executed the entry point
        self.check_is_administrator()

        # Remove the members
        with sp.for_("member", members) as member:
            sp.verify(self.data.members.contains(member),
                      message="SI_LIST_NOT_MEMBER")
            del self.data.members[member]

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
            message="SI_LIST_NO_NEW_ADMIN"),
            message="SI_LIST_NOT_PROPOSED_ADMIN")

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
    def is_member(self, address):
        """Returns True if the given address is a list member.

        """
        # Define the input parameter data type
        sp.set_type(address, sp.TAddress)

        # Return True if the address is in the list
        sp.result(self.data.members.contains(address))


sp.add_compilation_target("si_list", SpanishInquisitionList(
    administrator=sp.address("tz1M9CMEtsXm3QxA7FmMU2Qh7xzsuGXVbcDr"),
    metadata=sp.utils.metadata_of_url("ipfs://aaa"),
    type=sp.variant("BLOCK", sp.unit)))
