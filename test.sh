#!/bin/bash
cd python
#
# teiaMarketplace_v1
#
~/smartpy-cli/SmartPy.sh compile contracts/teiaMarketplace_v1.py /tmp/contracts/teiaMarketplace_v1
~/smartpy-cli/SmartPy.sh test tests/teiaMarketplace_v1_test.py /tmp/tests/teiaMarketplace_v1
#
# multisigWallet_v1
#
~/smartpy-cli/SmartPy.sh compile contracts/multisigWallet_v1.py /tmp/contracts/multisigWallet_v1
~/smartpy-cli/SmartPy.sh test tests/multisigWallet_v1_test.py /tmp/tests/multisigContract_v1
#
# fa2
#
~/smartpy-cli/SmartPy.sh compile contracts/fa2.py /tmp/contracts/fa2
~/smartpy-cli/SmartPy.sh test tests/fa2_test.py /tmp/tests/fa2
#
# minter
#
~/smartpy-cli/SmartPy.sh compile contracts/minter.py /tmp/contracts/minter
~/smartpy-cli/SmartPy.sh test tests/minter_test.py /tmp/tests/minter
#
# marketplace
#
~/smartpy-cli/SmartPy.sh compile contracts/marketplace.py /tmp/contracts/marketplace
~/smartpy-cli/SmartPy.sh test tests/marketplace_test.py /tmp/tests/marketplace
#
# artistsCollaboration
#
~/smartpy-cli/SmartPy.sh compile contracts/artistsCollaboration.py /tmp/contracts/artistsCollaboration
~/smartpy-cli/SmartPy.sh test tests/artistsCollaboration_test.py /tmp/tests/artistsCollaboration
#
cd - > /dev/null
