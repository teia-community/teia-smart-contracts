#!/bin/bash
cd python
~/smartpy-cli/SmartPy.sh compile contracts/teiaMarketplace_v1.py /tmp/contracts/teiaMarketplace_v1
~/smartpy-cli/SmartPy.sh compile contracts/multisigWallet_v1.py /tmp/contracts/multisigWallet_v1
~/smartpy-cli/SmartPy.sh compile contracts/fa2.py /tmp/contracts/fa2
~/smartpy-cli/SmartPy.sh compile contracts/minter.py /tmp/contracts/minter
~/smartpy-cli/SmartPy.sh compile contracts/marketplace.py /tmp/contracts/marketplace
~/smartpy-cli/SmartPy.sh compile contracts/artistsCollaboration.py /tmp/contracts/artistsCollaboration
~/smartpy-cli/SmartPy.sh compile contracts/daoToken.py /tmp/contracts/daoToken
~/smartpy-cli/SmartPy.sh compile contracts/daoTokenDrop.py /tmp/contracts/daoTokenDrop
~/smartpy-cli/SmartPy.sh compile contracts/daoGovernance.py /tmp/contracts/daoGovernance
~/smartpy-cli/SmartPy.sh compile contracts/daoTreasury.py /tmp/contracts/daoTreasury
~/smartpy-cli/SmartPy.sh compile contracts/representatives.py /tmp/contracts/representatives
~/smartpy-cli/SmartPy.sh compile contracts/harbergerToken.py /tmp/contracts/harbergerToken
~/smartpy-cli/SmartPy.sh compile contracts/harbergerFee.py /tmp/contracts/harbergerFee
~/smartpy-cli/SmartPy.sh compile contracts/subscriptionToken.py /tmp/contracts/subscriptionToken
~/smartpy-cli/SmartPy.sh compile contracts/subscriptionFee.py /tmp/contracts/subscriptionFee
~/smartpy-cli/SmartPy.sh compile contracts/subscriptionsMarketplace /tmp/contracts/subscriptionsMarketplace
cd - > /dev/null
