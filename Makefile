# Makefile for Teia Smart Contracts
#
# Usage example:
#
#   TARGET=daoToken make compile test 
#

# Location of SmartPy CLI
ifeq ($(SMARTPY_DIR),)
  SMARTPY_DIR:=~/smartpy-cli
endif

SMARTPY:=${SMARTPY_DIR}/SmartPy.sh

SHELL:=bash

DEFAULT_TARGET:=multisigWallet_v1

# TARGET, if none is given in the environment
ifeq ($(TARGET),)
  TARGET:=${DEFAULT_TARGET}
endif

# The environment variable TEIA_SC_PARAMS holds flags separated by ':' which
# can be used to control metadata and test features. Leaving this blank should
# cause contracts to run without the teia_sc package. This should not affect
# the smart contract Michelson code output. It may however affect metadata.
# Typical use: 
# 'tzip16_error_inline' - turns on in-contract error script
# 'tzip16_error_lint' - turns on additional tests and lint report for tzip16 errors
ifeq ($(TEIA_SC_PARAMS),)
  export TEIA_SC_PARAMS:=tzip16_error_inline:tzip16_error_lint
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
	cd ${COMPILE_DIR}; ${SMARTPY} compile ${SC_SRC_DIR}/$(strip $1).py ${SC_OUT_DIR}/contracts/$(strip $1) --purge --html
endef

define TEST
	cd ${COMPILE_DIR}; ${SMARTPY} test ${SC_TEST_DIR}/$(strip $1)_test.py ${SC_OUT_DIR}/tests/$(strip $1) --purge --html
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
    $(call COMPILE, fa12)
	$(call COMPILE, fa2)
	$(call COMPILE, minter)
	$(call COMPILE, marketplace)
	$(call COMPILE, artistsCollaboration)
	$(call COMPILE, daoToken)
	$(call COMPILE, daoTokenDrop)
	$(call COMPILE, daoTreasury)
	$(call COMPILE, daoGovernance)
	$(call COMPILE, representatives)
	$(call COMPILE, daoMultisig)
	$(call COMPILE, coreTeamVote)
	$(call COMPILE, teiaPolls)
	$(call COMPILE, harbergerToken)
	$(call COMPILE, harbergerFee)
	$(call COMPILE, harbergerMinter)
	$(call COMPILE, subscriptionToken)
	$(call COMPILE, subscriptionFee)
	$(call COMPILE, subscriptionsMarketplace)
	$(call COMPILE, donations)
	$(call COMPILE, openLetter)
	$(call COMPILE, tezosPolls)
	$(call COMPILE, deadMansSwitch)

test_all:
	$(call TEST, teiaMarketplace_v1)
	$(call TEST, multisigWallet_v1)
	$(call TEST, fa2)
	$(call TEST, minter)
	$(call TEST, marketplace)
	$(call TEST, artistsCollaboration)
	$(call TEST, daoToken)
	$(call TEST, daoTokenDrop)
	$(call TEST, daoTreasury)
	$(call TEST, daoGovernance)
	$(call TEST, representatives)
	$(call TEST, daoMultisig)
	$(call TEST, teiaPolls)
	$(call TEST, deadMansSwitch)
