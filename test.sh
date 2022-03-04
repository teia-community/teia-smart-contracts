#!/bin/bash
~/smartpy-cli/SmartPy.sh test python/tests/teiaMarketplace_v1_test.py /tmp/teiaMarketplace_v1
~/smartpy-cli/SmartPy.sh test python/tests/multisigWallet_v1_test.py /tmp/multisigContract_v1
~/smartpy-cli/SmartPy.sh test python/tests/fa2_test.py /tmp/fa2
~/smartpy-cli/SmartPy.sh test python/tests/minter_test.py /tmp/minter
~/smartpy-cli/SmartPy.sh test python/tests/marketplace_test.py /tmp/marketplace
~/smartpy-cli/SmartPy.sh test python/tests/artistsCollaboration_test.py /tmp/artistsCollaboration
cd - > /dev/null
