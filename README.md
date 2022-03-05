# Teia Community smart contracts

| Contract | TzKT link | Status |
|----------|-----------|--------|
| [Teia Marketplace (v1)](python/contracts/teiaMarketplace_v1.py) | [KT1PHubm9HtyQEJ4BBpMTVomq6mhbfNZ9z5w](https://tzkt.io/KT1PHubm9HtyQEJ4BBpMTVomq6mhbfNZ9z5w) | Audited |
| [Multisig Wallet / mini-DAO (v1)](python/ccontracts/multisigWallet_v1.py) | [KT1PKBTVmdxfgkFvSeNUQacYiEFsPBw16B4P](https://tzkt.io/KT1PKBTVmdxfgkFvSeNUQacYiEFsPBw16B4P) | Audited |
| [Extended FA2 token](python/ccontracts/fa2.py) | | Prototype |
| [Extended FA2 token minter](python/ccontracts/minter.py) | | Prototype |
| [Marketplace for the extended FA2 token](python/ccontracts/marketplace.py) | | Prototype |
| [Artists collaboration](python/ccontracts/artistsCollaboration.py) | | Prototype |


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
```
