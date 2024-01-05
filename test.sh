#!/bin/bash
cd python
~/smartpy-cli/SmartPy.sh test tests/teiaMarketplace_v1_test.py /tmp/tests/teiaMarketplace_v1
~/smartpy-cli/SmartPy.sh test tests/multisigWallet_v1_test.py /tmp/tests/multisigContract_v1
~/smartpy-cli/SmartPy.sh test tests/fa2_test.py /tmp/tests/fa2
~/smartpy-cli/SmartPy.sh test tests/minter_test.py /tmp/tests/minter
~/smartpy-cli/SmartPy.sh test tests/marketplace_test.py /tmp/tests/marketplace
~/smartpy-cli/SmartPy.sh test tests/artistsCollaboration_test.py /tmp/tests/artistsCollaboration
~/smartpy-cli/SmartPy.sh test tests/daoToken_test.py /tmp/tests/daoToken
~/smartpy-cli/SmartPy.sh test tests/daoTokenDrop_test.py /tmp/tests/daoTokenDrop
~/smartpy-cli/SmartPy.sh test tests/daoTreasury_test.py /tmp/tests/daoTreasury
~/smartpy-cli/SmartPy.sh test tests/daoGovernance_test.py /tmp/tests/daoGovernance
~/smartpy-cli/SmartPy.sh test tests/representatives_test.py /tmp/tests/representatives
~/smartpy-cli/SmartPy.sh test tests/daoMultisig_test.py /tmp/tests/daoMultisig
~/smartpy-cli/SmartPy.sh test tests/teiaPolls_test.py /tmp/tests/teiaPolls
~/smartpy-cli/SmartPy.sh test tests/deadMansSwitch_test.py /tmp/tests/deadMansSwitch
~/smartpy-cli/SmartPy.sh test tests/si_fa2_test.py /tmp/tests/si_fa2 --html --purge
~/smartpy-cli/SmartPy.sh test tests/si_list_test.py /tmp/tests/si_list --html --purge
cd - > /dev/null
