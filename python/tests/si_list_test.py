"""Unit tests for the Spanish Inquisition list class.

"""

import smartpy as sp

# Import the Spanish Inquisition list contract module
listModule = sp.io.import_script_from_url("file:contracts/si_list.py")


def get_test_environment():
    # Initialize the test scenario
    scenario = sp.test_scenario()

    # Create the test accounts
    admin = sp.test_account("admin")
    user1 = sp.test_account("user1")
    user2 = sp.test_account("user2")
    user3 = sp.test_account("user3")
    user4 = sp.test_account("user4")

    # Initialize the list contract
    si_list = listModule.SpanishInquisitionList(
        administrator=admin.address,
        metadata=sp.utils.metadata_of_url("ipfs://aaa"),
        type=sp.variant("BLOCK", sp.unit))
    scenario += si_list

    # Save all the variables in a test environment dictionary
    testEnvironment = {
        "scenario": scenario,
        "admin": admin,
        "user1": user1,
        "user2": user2,
        "user3": user3,
        "user4": user4,
        "si_list": si_list}

    return testEnvironment


@sp.add_test(name="Test add and remove users")
def test_add_and_remove_users():
    # Get the test environment
    testEnvironment = get_test_environment()
    scenario = testEnvironment["scenario"]
    admin = testEnvironment["admin"]
    user1 = testEnvironment["user1"]
    user2 = testEnvironment["user2"]
    user3 = testEnvironment["user3"]
    user4 = testEnvironment["user4"]
    si_list = testEnvironment["si_list"]

    # Check that a normal user cannot add members
    si_list.add_members([user1.address, user2.address]).run(
        valid=False, sender=user1, exception="SI_LIST_NOT_ADMIN")

    # Check that the admin can add members
    si_list.add_members([user1.address, user2.address]).run(sender=admin)

    # Check that the contract information has been updated
    scenario.verify(si_list.data.members.contains(user1.address))
    scenario.verify(si_list.data.members.contains(user2.address))
    scenario.verify(~si_list.data.members.contains(user3.address))
    scenario.verify(~si_list.data.members.contains(user4.address))
    scenario.verify(si_list.is_member(user1.address))
    scenario.verify(si_list.is_member(user2.address))
    scenario.verify(~si_list.is_member(user3.address))
    scenario.verify(~si_list.is_member(user4.address))

    # Add a new member and one that was already in the list
    si_list.add_members([user1.address, user4.address]).run(sender=admin)

    # Check that the contract information has been updated
    scenario.verify(si_list.is_member(user1.address))
    scenario.verify(si_list.is_member(user2.address))
    scenario.verify(~si_list.is_member(user3.address))
    scenario.verify(si_list.is_member(user4.address))

    # Check that a normal user cannot remove members
    si_list.remove_members([user2.address]).run(
        valid=False, sender=user1, exception="SI_LIST_NOT_ADMIN")

    # Remove one member
    si_list.remove_members([user2.address]).run(sender=admin)

    # Check that the contract information has been updated
    scenario.verify(si_list.is_member(user1.address))
    scenario.verify(~si_list.is_member(user2.address))
    scenario.verify(~si_list.is_member(user3.address))
    scenario.verify(si_list.is_member(user4.address))

    # Check that if fails if one tries to remove a user that is not a member
    si_list.remove_members([user1.address, user3.address]).run(
        valid=False, sender=admin, exception="SI_LIST_NOT_MEMBER")

    # Remove two members
    si_list.remove_members([user1.address, user4.address]).run(sender=admin)

    # Check that the contract information has been updated
    scenario.verify(~si_list.is_member(user1.address))
    scenario.verify(~si_list.is_member(user2.address))
    scenario.verify(~si_list.is_member(user3.address))
    scenario.verify(~si_list.is_member(user4.address))


@sp.add_test(name="Test transfer and accept administrator")
def test_transfer_and_accept_administrator():
    # Get the test environment
    testEnvironment = get_test_environment()
    scenario = testEnvironment["scenario"]
    admin = testEnvironment["admin"]
    user1 = testEnvironment["user1"]
    user2 = testEnvironment["user2"]
    si_list = testEnvironment["si_list"]

    # Check the original administrator
    scenario.verify(si_list.data.administrator == admin.address)

    # Check that only the admin can transfer the administrator
    new_administrator = user1.address
    si_list.transfer_administrator(new_administrator).run(
        valid=False, sender=user1, exception="SI_LIST_NOT_ADMIN")
    si_list.transfer_administrator(new_administrator).run(sender=admin)

    # Check that the proposed administrator is updated
    scenario.verify(si_list.data.proposed_administrator.open_some() == new_administrator)

    # Check that only the proposed administrator can accept the administrator position
    si_list.accept_administrator().run(
        valid=False, sender=admin, exception="SI_LIST_NOT_PROPOSED_ADMIN")
    si_list.accept_administrator().run(sender=user1)

    # Check that the administrator is updated
    scenario.verify(si_list.data.administrator == new_administrator)
    scenario.verify(~si_list.data.proposed_administrator.is_some())

    # Check that only the new administrator can propose a new administrator
    new_administrator = user2.address
    si_list.transfer_administrator(new_administrator).run(
        valid=False, sender=admin, exception="SI_LIST_NOT_ADMIN")
    si_list.transfer_administrator(new_administrator).run(sender=user1)

    # Check that the proposed administrator is updated
    scenario.verify(si_list.data.proposed_administrator.open_some() == new_administrator)


@sp.add_test(name="Test set metadata")
def test_set_metadata():
    # Get the test environment
    testEnvironment = get_test_environment()
    scenario = testEnvironment["scenario"]
    admin = testEnvironment["admin"]
    user1 = testEnvironment["user1"]
    si_list = testEnvironment["si_list"]

    # Check that only the admin can update the metadata
    new_metadata = sp.record(k="", v=sp.utils.bytes_of_string("ipfs://zzzz"))
    si_list.set_metadata(new_metadata).run(
        valid=False, sender=user1, exception="SI_LIST_NOT_ADMIN")
    si_list.set_metadata(new_metadata).run(sender=admin)

    # Check that the metadata is updated
    scenario.verify(si_list.data.metadata[new_metadata.k] == new_metadata.v)

    # Add some extra metadata
    extra_metadata = sp.record(k="aaa", v=sp.utils.bytes_of_string("ipfs://ffff"))
    si_list.set_metadata(extra_metadata).run(sender=admin)

    # Check that the two metadata entries are present
    scenario.verify(si_list.data.metadata[new_metadata.k] == new_metadata.v)
    scenario.verify(si_list.data.metadata[extra_metadata.k] == extra_metadata.v)
