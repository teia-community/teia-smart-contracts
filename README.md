# Teia Community smart contracts

| Contract | TzKT link | Status |
|----------|-----------|--------|
| [Teia Marketplace (v1)](python/contracts/teiaMarketplace_v1.py) | [KT1PHubm9HtyQEJ4BBpMTVomq6mhbfNZ9z5w](https://tzkt.io/KT1PHubm9HtyQEJ4BBpMTVomq6mhbfNZ9z5w) | Audited |
| [Multisig Wallet / mini-DAO (v1)](python/contracts/multisigWallet_v1.py) | [KT1PKBTVmdxfgkFvSeNUQacYiEFsPBw16B4P](https://tzkt.io/KT1PKBTVmdxfgkFvSeNUQacYiEFsPBw16B4P) | Audited |
| [Core Team multisig](python/contracts/daoMultisig.py) | [KT1J9FYz29RBQi1oGLw8uXyACrzXzV1dHuvb](https://tzkt.io/KT1J9FYz29RBQi1oGLw8uXyACrzXzV1dHuvb) | Deployed |
| [Extended FA2 token](python/contracts/fa2.py) | | Prototype |
| [Extended FA2 token minter](python/contracts/minter.py) | | Prototype |
| [Marketplace for the extended FA2 token](python/contracts/marketplace.py) | | Prototype |
| [Artists collaboration](python/contracts/artistsCollaboration.py) | | Prototype |
| [DAO token](python/contracts/daoToken.py) | | Prototype |
| [DAO token distributor](python/contracts/daoTokenDrop.py) | | Prototype |
| [DAO governance](python/contracts/daoGovernance.py) | | Prototype |
| [DAO treasury](python/contracts/daoTreasury.py) | | Prototype |
| [DAO representatives](python/contracts/representatives.py) | | Prototype |
| [Harberger token](python/contracts/harbergerToken.py) | | Prototype |
| [Harberger fee](python/contracts/harbergerFee.py) | | Prototype |
| [Harberger token minter](python/contracts/harbergerMinter.py) | | Prototype |
| [Subscription token](python/contracts/subscriptionToken.py) | | Prototype |
| [Subscription fee](python/contracts/subscriptionFee.py) | | Prototype |
| [Subscriptions marketplace](python/contracts/subscriptionsMarketplace.py) | | Prototype |
| [Contract for donation campaigns](python/contracts/donations.py) | | Prototype |
| [Contract for signing open letters](python/contracts/openLetter.py) | | Prototype |


## SmartPy installation

```bash
wget https://smartpy.io/cli/install.sh
bash ./install.sh
rm install.sh
```

## Compile the contracts

```bash
cd teia-smart-contracts/python
~/smartpy-cli/SmartPy.sh compile contracts/teiaMarketplace_v1.py ../output/contracts/teiaMarketplace_v1 --html --purge
~/smartpy-cli/SmartPy.sh compile contracts/multisigWallet_v1.py ../output/contracts/multisigWallet_v1 --html --purge
~/smartpy-cli/SmartPy.sh compile contracts/fa2.py ../output/contracts/fa2 --html --purge
~/smartpy-cli/SmartPy.sh compile contracts/minter.py ../output/contracts/minter --html --purge
~/smartpy-cli/SmartPy.sh compile contracts/marketplace.py ../output/contracts/marketplace --html --purge
~/smartpy-cli/SmartPy.sh compile contracts/artistsCollaboration.py ../output/contracts/artistsCollaboration --html --purge
~/smartpy-cli/SmartPy.sh compile contracts/daoToken.py ../output/contracts/daoToken --html --purge
~/smartpy-cli/SmartPy.sh compile contracts/daoTokenDrop.py ../output/contracts/daoTokenDrop --html --purge
~/smartpy-cli/SmartPy.sh compile contracts/daoGovernance.py ../output/contracts/daoGovernance --html --purge
~/smartpy-cli/SmartPy.sh compile contracts/daoTreasury.py ../output/contracts/daoTreasury --html --purge
~/smartpy-cli/SmartPy.sh compile contracts/representatives.py ../output/contracts/representatives --html --purge
~/smartpy-cli/SmartPy.sh compile contracts/daoMultisig.py ../output/contracts/daoMultisig --html --purge
~/smartpy-cli/SmartPy.sh compile contracts/coreTeamVote.py ../output/contracts/coreTeamVote --html --purge
~/smartpy-cli/SmartPy.sh compile contracts/harbergerToken.py ../output/contracts/harbergerToken --html --purge
~/smartpy-cli/SmartPy.sh compile contracts/harbergerFee.py ../output/contracts/harbergerFee --html --purge
~/smartpy-cli/SmartPy.sh compile contracts/harbergerMinter.py ../output/contracts/harbergerMinter --html --purge
~/smartpy-cli/SmartPy.sh compile contracts/subscriptionToken.py ../output/contracts/subscriptionToken --html --purge
~/smartpy-cli/SmartPy.sh compile contracts/subscriptionFee.py ../output/contracts/subscriptionFee --html --purge
~/smartpy-cli/SmartPy.sh compile contracts/subscriptionsMarketplace.py ../output/contracts/subscriptionsMarketplace --html --purge
~/smartpy-cli/SmartPy.sh compile contracts/donations.py ../output/contracts/donations --html --purge
~/smartpy-cli/SmartPy.sh compile contracts/openLetter.py ../output/contracts/openLetter --html --purge
```

## Execute the tests

```bash
cd teia-smart-contracts/python
~/smartpy-cli/SmartPy.sh test tests/teiaMarketplace_v1_test.py ../output/tests/teiaMarketplace_v1 --html --purge
~/smartpy-cli/SmartPy.sh test tests/multisigWallet_v1_test.py ../output/tests/multisigContract_v1 --html --purge
~/smartpy-cli/SmartPy.sh test tests/fa2_test.py ../output/tests/fa2 --html --purge
~/smartpy-cli/SmartPy.sh test tests/minter_test.py ../output/tests/minter --html --purge
~/smartpy-cli/SmartPy.sh test tests/marketplace_test.py ../output/tests/marketplace --html --purge
~/smartpy-cli/SmartPy.sh test tests/artistsCollaboration_test.py ../output/tests/artistsCollaboration --html --purge
~/smartpy-cli/SmartPy.sh test tests/daoToken_test.py ../output/tests/daoToken --html --purge
~/smartpy-cli/SmartPy.sh test tests/daoTokenDrop_test.py ../output/tests/daoTokenDrop --html --purge
~/smartpy-cli/SmartPy.sh test tests/daoGovernance_test.py ../output/tests/daoGovernance --html --purge
~/smartpy-cli/SmartPy.sh test tests/representatives_test.py ../output/tests/representatives --html --purge
~/smartpy-cli/SmartPy.sh test tests/daoMultisig_test.py ../output/tests/daoMultisig --html --purge
```
