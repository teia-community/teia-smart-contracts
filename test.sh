#!/bin/bash
cd python
~/smartpy-cli/SmartPy.sh test tests/teiaMarketplace_v1_test.py /tmp/tests/teiaMarketplace_v1
~/smartpy-cli/SmartPy.sh test tests/multisigWallet_v1_test.py /tmp/tests/multisigContract_v1
~/smartpy-cli/SmartPy.sh test tests/fa2_test.py /tmp/tests/fa2
~/smartpy-cli/SmartPy.sh test tests/minter_test.py /tmp/tests/minter
~/smartpy-cli/SmartPy.sh test tests/marketplace_test.py /tmp/tests/marketplace
~/smartpy-cli/SmartPy.sh test tests/artistsCollaboration_test.py /tmp/tests/artistsCollaboration
cd - > /dev/null
