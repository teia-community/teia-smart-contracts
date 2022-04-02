# Makefile for Teia Smart Contracts
#
# Usage example:
#
#   TARGET=daoToken make compile test 
#


# Location of SmartPy CLI (adjust to local installation, or set environment variable)
SMARTPY:=~/ext/smartpy-cli/SmartPy.sh

SHELL:=bash

DEFAULT_TARGET:=multisigWallet_v1

# TARGET, if none is given in the environment
ifeq ($(TARGET),)
  TARGET:=${DEFAULT_TARGET}
endif

export PYTHONPATH:=.:$(PYTHONPATH)

# Contracts source
SC_SRC_DIR:=$(realpath ./python/contracts)
# Contracts test source
SC_TEST_DIR:=$(realpath ./python/tests)
# Output directory, absolute path
SC_OUT_DIR:=$(realpath ./output)
# Compile and test working directory
COMPILE_DIR:=$(realpath ./python)

define COMPILE
	cd ${COMPILE_DIR}; ${SMARTPY} compile ${SC_SRC_DIR}/$(strip $1).py ${SC_OUT_DIR}/contracts/${TARGET} --purge --html
endef

define TEST
	cd ${COMPILE_DIR}; ${SMARTPY} test ${SC_TEST_DIR}/$(strip $1)_test.py ${SC_OUT_DIR}/tests/${TARGET} --purge --html
endef

## Compile the TARGET contract
# Usage example (bash): "TARGET=xyzContract make compile;"
compile:
	$(call COMPILE, ${TARGET})

## Execute tests on TARGET contract
test:
	$(call TEST, ${TARGET})

compile_all:
	$(call COMPILE, teiaMarketplace_v1)
	$(call COMPILE, multisigWallet_v1)
	$(call COMPILE, fa2)
	$(call COMPILE, minter)
	$(call COMPILE, marketplace)
	$(call COMPILE, artistsCollaboration)
	$(call COMPILE, daoToken)
	$(call COMPILE, daoTokenDrop)
	$(call COMPILE, daoGovernance)
	$(call COMPILE, daoTreasury)
	$(call COMPILE, representatives)

test_all:
	$(call TEST, teiaMarketplace_v1)
	$(call TEST, multisigWallet_v1)
	$(call TEST, fa2)
	$(call TEST, minter)
	$(call TEST, marketplace)
	$(call TEST, artistsCollaboration)
	$(call TEST, daoToken)
	$(call TEST, daoTokenDrop)
	$(call TEST, daoGovernance)
#	$(call TEST, daoTreasury)
	$(call TEST, representatives)

