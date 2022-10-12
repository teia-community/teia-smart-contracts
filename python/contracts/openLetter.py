import smartpy as sp


class OpenLetter(sp.Contract):
    """A simple contract that can be used to sign an open letter.

    """

    def __init__(self, metadata, letter):
        """Initializes the contract.

        """
        # Define the contract storage data types for clarity
        self.init_type(sp.TRecord(
            # The contract metadata
            metadata=sp.TBigMap(sp.TString, sp.TBytes),
            # The open letter ipfs link
            letter=sp.TString,
            # The bigmap with the wallets that signed the letter
            signatures=sp.TBigMap(sp.TAddress, sp.TUnit)))

        # Initialize the contract storage
        self.init(
            metadata=metadata,
            letter=letter,
            signatures=sp.big_map())

    @sp.entry_point
    def sign_letter(self, unit):
        """Sign the letter.

        """
        # Define the input parameter data type
        sp.set_type(unit, sp.TUnit)

        # Check that the user didn't send any tez
        sp.verify(sp.amount == sp.mutez(0), message="No tez transfers allowed")

        # Check that the user didn't sign the letter
        sp.verify(~self.data.signatures.contains(sp.sender),
                  message="Letter already signed")

        # Add the new signature
        self.data.signatures[sp.sender] = sp.unit

    @sp.entry_point
    def remove_signature(self, unit):
        """Removes the user signature.

        """
        # Define the input parameter data type
        sp.set_type(unit, sp.TUnit)

        # Check that the user didn't send any tez
        sp.verify(sp.amount == sp.mutez(0), message="No tez transfers allowed")

        # Check that the user signed the letter
        sp.verify(self.data.signatures.contains(sp.sender),
                  message="Didn't sign the letter")

        # Remove the signature
        del self.data.signatures[sp.sender]

    @sp.onchain_view(pure=True)
    def signed(self, user_address):
        """Returns True if the user address signed the letter.

        """
        # Define the input parameter data type
        sp.set_type(user_address, sp.TAddress)

        # Return True if the user signed the letter 
        sp.result(self.data.signatures.contains(user_address))


# Add a compilation target
sp.add_compilation_target("openLetter", OpenLetter(
    metadata=sp.utils.metadata_of_url("ipfs://aaaa"),
    letter=sp.string("ipfs://bbb")))
