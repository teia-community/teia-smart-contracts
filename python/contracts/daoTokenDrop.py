import smartpy as sp


class DAOTokenDrop(sp.Contract):
    """This contract implements a DAO token drop distribution using a Merkle
    tree.

    The code is highly based on the Token Drop template by Anshu Jalan:
    https://github.com/AnshuJalan/token-drop-template

    The main modifications are:
        - Possibility to update the Merkle tree.
        - Introduction of a claim period.
        - Introduction of a DAO treasury address that will receive the unclaimed
          tokens after the claim period has passed.
        - On-chain view to get an address claimed tokens.

    """

    def __init__(self, administrator, metadata, token, treasury, merkle_root, expiration_date):
        """Initializes the contract.

        """
        # Define the contract storage data types for clarity
        self.init_type(sp.TRecord(
            # The contract administrator
            administrator=sp.TAddress,
            # The contract metadata
            metadata=sp.TBigMap(sp.TString, sp.TBytes),
            # The DAO token address
            token=sp.TAddress,
            # The DAO treasury address
            treasury=sp.TAddress,
            # The Merkle tree root associated to the DAO distribution list
            merkle_root=sp.TBytes,
            # The claim period expiration date
            expiration_date=sp.TTimestamp,
            # The big map with the users that already claimed their tokens
            claimed=sp.TBigMap(sp.TAddress, sp.TNat),
            # The proposed new administrator address
            proposed_administrator=sp.TOption(sp.TAddress)))

        # Initialize the contract storage
        self.init(
            administrator=administrator,
            metadata=metadata,
            token=token,
            treasury=treasury,
            merkle_root=merkle_root,
            expiration_date=expiration_date,
            claimed=sp.big_map(),
            proposed_administrator=sp.none)

        # Fill the contract metadata
        self.contract_metadata = {
            "name": "Teia DAO token distribution contract",
            "description": "Token distribution contract used for the Teia DAO",
            "version": "1.0.0",
            "authors": ["Teia Community <https://twitter.com/TeiaCommunity>"],
            "homepage": "https://teia.art",
            "source": {
                "tools": ["SmartPy 0.16.0"],
                "location": "https://github.com/teia-community/teia-smart-contracts/blob/main/python/contracts/daoTokenDrop.py"
            },
            "interfaces": ["TZIP-016"],
            "errors": [ {"error": {"string": "DROP_NOT_ADMIN"},
                         "expansion": {"string": "The account that executed the entry point is not the contract administrator"},
                         "languages": ["en"]},
                        {"error": {"string": "DROP_NO_NEW_ADMIN"},
                         "expansion": {"string": "The new administrator has not been proposed"},
                         "languages": ["en"]},
                        {"error": {"string": "DROP_NOT_PROPOSED_ADMIN"},
                         "expansion": {"string": "The operation can only be executed by the proposed administrator"},
                         "languages": ["en"]},
                        {"error": {"string": "DROP_TEZ_TRANSFER"},
                         "expansion": {"string": "The operation does not accept tez transfers"},
                         "languages": ["en"]},
                        {"error": {"string": "DROP_INVALID_MERKLE_PROOF"},
                         "expansion": {"string": "The provided Merkle proof is not valid"},
                         "languages": ["en"]},
                        {"error": {"string": "DROP_INVALID_LEAF"},
                         "expansion": {"string": "The provided leaf is not valid"},
                         "languages": ["en"]},
                        {"error": {"string": "DROP_SENDER_NOT_LEAF"},
                         "expansion": {"string": "The wallet that executed the operation is not the one in the leaf"},
                         "languages": ["en"]},
                        {"error": {"string": "DROP_ALL_TOKENS_CLAIMED"},
                         "expansion": {"string": "The wallet that executed the operation has already claimed all their tokens"},
                         "languages": ["en"]},
                        {"error": {"string": "DROP_CLAIM_EXPIRED"},
                         "expansion": {"string": "The token claim period has expired"},
                         "languages": ["en"]},
                        {"error": {"string": "DROP_CLAIM_NOT_EXPIRED"},
                         "expansion": {"string": "The token claim period has not expired"},
                         "languages": ["en"]}]}
        self.init_metadata("contract_metadata", self.contract_metadata)

    def check_is_administrator(self):
        """Checks that the address that called the entry point is the contract
        administrator.

        """
        sp.verify(sp.sender == self.data.administrator,
                  message="DROP_NOT_ADMIN")

    def verify_proof(self, proof, leaf):
        """Computes the Merkle tree root from the provided proof and leaf and
        checks that it coincides with the stored merkle root.

        """
        # Loop over the proof elements and calculate the combined hash
        combined_hash = sp.local("combined_hash", sp.sha256(leaf))

        with sp.for_("proof_element", proof) as proof_element:
            with sp.if_(combined_hash.value < proof_element):
                combined_hash.value = sp.sha256(
                    combined_hash.value + proof_element)
            with sp.else_():
                combined_hash.value = sp.sha256(
                    proof_element + combined_hash.value)

        # Check that the combined hash coincides with the stored Merkle root
        sp.verify(combined_hash.value == self.data.merkle_root,
                  message="DROP_INVALID_MERKLE_PROOF")

    def dao_transfer(self, address, amount):
        """Transfers some DAO tokens from the contract to an address.

        """
        # Get a handle to the DAO token transfer entry point
        token_transfer_handle = sp.contract(
            t=sp.TList(sp.TRecord(
                from_=sp.TAddress,
                txs=sp.TList(sp.TRecord(
                    to_=sp.TAddress,
                    token_id=sp.TNat,
                    amount=sp.TNat).layout(
                        ("to_", ("token_id", "amount"))))).layout(
                            ("from_", "txs"))),
            address=self.data.token,
            entry_point="transfer").open_some()

        # Execute the transfer
        sp.transfer(
            arg=sp.list([sp.record(
                from_=sp.self_address,
                txs=sp.list([sp.record(
                    to_=address,
                    token_id=sp.nat(0),
                    amount=amount)]))]),
            amount=sp.mutez(0),
            destination=token_transfer_handle)

    @sp.entry_point
    def claim(self, params):
        """Claims some DAO tokens.

        """
        # Define the input parameter data type
        sp.set_type(params, sp.TRecord(
            proof=sp.TList(sp.TBytes),
            leaf=sp.TBytes).layout(("proof", "leaf")))

        # Check that the sender didn't transfer any tez
        sp.verify(sp.amount == sp.tez(0), message="DROP_TEZ_TRANSFER")

        # Check that the claim period didn't expire
        sp.verify(sp.now < self.data.expiration_date,
                  message="DROP_CLAIM_EXPIRED")

        # Unpack the leaf data
        leaf_data_type = sp.TRecord(
            address=sp.TAddress,
            value=sp.TNat).layout(("address", "value"))
        leaf_data = sp.compute(sp.unpack(
            params.leaf, leaf_data_type).open_some("DROP_INVALID_LEAF"))

        # Check that the sender coincides with the leaf address
        sp.verify(sp.sender == leaf_data.address,
                  message="DROP_SENDER_NOT_LEAF")

        # Check that the sender didn't claim all the tokens
        unclaimed_tokens = sp.compute(sp.as_nat(
            leaf_data.value - self.data.claimed.get(sp.sender, 0)))
        sp.verify(unclaimed_tokens > 0, message="DROP_ALL_TOKENS_CLAIMED")

        # Check that the provided proof is correct
        self.verify_proof(params.proof, params.leaf)

        # Transfer the unclaimed DAO token editions to the sender
        self.dao_transfer(sp.sender, unclaimed_tokens)

        # Update the claimed big map
        self.data.claimed[sp.sender] = leaf_data.value

    @sp.entry_point
    def transfer_to_treasury(self, amount):
        """Transfers some DAO tokens to the DAO treasury.

        This entrypoint can be executed by anyone only after the claim period
        has expired.

        """
        # Define the input parameter data type
        sp.set_type(amount, sp.TNat)

        # Check that the sender didn't transfer any tez
        sp.verify(sp.amount == sp.tez(0), message="DROP_TEZ_TRANSFER")

        # Check that the claim period has expired
        sp.verify(sp.now > self.data.expiration_date,
                  message="DROP_CLAIM_NOT_EXPIRED")

        # Transfer the DAO tokens to the treasury
        self.dao_transfer(self.data.treasury, amount)

    @sp.entry_point
    def update_treasury(self, new_treasury):
        """Updates the DAO treasury address that will receive the unclaimed
        tokens after the claim period.

        """
        # Define the input parameter data type
        sp.set_type(new_treasury, sp.TAddress)

        # Check that the administrator executed the entry point
        self.check_is_administrator()

        # Update the DAO treasury address
        self.data.treasury = new_treasury

    @sp.entry_point
    def update_merkle_root(self, new_merkle_root):
        """Updates the Merkle tree root to reflect an updated DAO token
        distribution.

        """
        # Define the input parameter data type
        sp.set_type(new_merkle_root, sp.TBytes)

        # Check that the administrator executed the entry point
        self.check_is_administrator()

        # Update the Merkle tree root
        self.data.merkle_root = new_merkle_root

    @sp.entry_point
    def update_expiration_date(self, new_expiration_date):
        """Updates the claim expiration date.

        """
        # Define the input parameter data type
        sp.set_type(new_expiration_date, sp.TTimestamp)

        # Check that the administrator executed the entry point
        self.check_is_administrator()

        # Update the claim expiration date
        self.data.expiration_date = new_expiration_date

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
            "DROP_NO_NEW_ADMIN"), message="DROP_NOT_PROPOSED_ADMIN")

        # Set the new administrator address
        self.data.administrator = sp.sender

        # Reset the proposed administrator value
        self.data.proposed_administrator = sp.none

    @sp.onchain_view(pure=True)
    def claimed_tokens(self, address):
        """Returns the number of tokens claimed by the address.

        """
        # Define the input parameter data type
        sp.set_type(address, sp.TAddress)

        # Return the number of claimed tokens
        sp.result(self.data.claimed.get(address, 0))


sp.add_compilation_target("daoTokenDrop", DAOTokenDrop(
    administrator=sp.address("tz1gnL9CeM5h5kRzWZztFYLypCNnVQZjndBN"),
    metadata=sp.utils.metadata_of_url("ipfs://QmNhC5Uucwh8TRfzL8xxo2y7RbJVkShuVr8dXCfoFoVCZ5"),
    token=sp.address("KT1Bdh3NcpSnTy9kPGQLzBr9u51KHfPYqCnN"),
    treasury=sp.address("tz1gnL9CeM5h5kRzWZztFYLypCNnVQZjndBN"),
    merkle_root=sp.bytes("0x00"),
    expiration_date=sp.timestamp_from_utc(2023, 5, 30, 23, 59, 59)))
