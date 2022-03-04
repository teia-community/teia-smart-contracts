# teia-smart-contracts

Teia Community smart contracts

| Contract                | Comment                       | Audited? |
| ------------------------|-------------------------------|----------|
| teiaMarketplace_v1.py   | The official Teia marketplace | YES      |
| multisigWallet_v1.py    | The officual Teia multisig    | YES      |
| fa2.py                  |                               | NO       |
| minter.py               |                               | NO       |
| marketplace.py          |                               | NO       |
| artistsCollaboration.py |                               | NO       |


## SmartPy installation

```bash
wget https://smartpy.io/cli/install.sh
bash ./install.sh --prefix ~/admin/smartpy
rm install.sh
```

## Execute the tests

```bash
cd teia-smart-contracts
~/admin/smartpy/SmartPy.sh test python/tests/teiaMarketplace_v1_test.py output/tests/teiaMarketplace_v1 --html --purge
~/admin/smartpy/SmartPy.sh test python/tests/multisigWallet_v1_test.py output/tests/multisigWallet_v1 --html --purge
~/admin/smartpy/SmartPy.sh test python/tests/fa2_test.py output/tests/fa2 --html --purge
~/admin/smartpy/SmartPy.sh test python/tests/minter_test.py output/tests/minter --html --purge
~/admin/smartpy/SmartPy.sh test python/tests/marketplace_test.py output/tests/marketplace --html --purge
~/admin/smartpy/SmartPy.sh test python/tests/artistsCollaboration_test.py output/tests/artistsCollaboration --html --purge
```

## Compile the contracts

```bash
cd teia-smart-contracts
~/admin/smartpy/SmartPy.sh compile python/contracts/teiaMarketplace_v1.py output/contracts/teiaMarketplace_v1 --html --purge
~/admin/smartpy/SmartPy.sh compile python/contracts/multisigWallet_v1.py output/contracts/multisigWallet_v1 --html --purge
~/admin/smartpy/SmartPy.sh compile python/contracts/fa2.py output/contracts/fa2 --html --purge
~/admin/smartpy/SmartPy.sh compile python/contracts/minter.py output/contracts/minter --html --purge
~/admin/smartpy/SmartPy.sh compile python/contracts/marketplace.py output/contracts/marketplace --html --purge
~/admin/smartpy/SmartPy.sh compile python/contracts/artistsCollaboration.py output/contracts/artistsCollaboration --html --purge
```
