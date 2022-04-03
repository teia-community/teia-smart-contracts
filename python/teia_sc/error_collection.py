"""A helper module to manage tezos smart contract errors for TZIP-16 metadata.
"""

from collections import defaultdict
from sys import stdout
from copy import copy
from html import escape

# TODO's :
#  add support for multiple languages in errors

# The follwing stores information collected on the various contracts
contracts = defaultdict(lambda:defaultdict(lambda:defaultdict(dict)))

ALLOWED_ERROR_DATA_KEYS = [
    'failwith_type',  # Return type from `FAILWITH` instruction. Always represented as string.
    'expansion',      # For TZIP-16 expansion metadata
    'expansion_type', # For TZIP-16 expansion metadata
    'doc',            # For extended documentation/tips for dealing with some errors. Optional.
    ]

ALLOWED_ERROR_MESSAGE_TYPES = [
    'string', # 
    'bytes',  # "0xfedcba9876543210" TODO untested
    ]

_TestError_default_flags = dict(
    WARN_LONG_KEY = True,
    LONG_KEY_THRESHOLD = 8,
    ERROR_NO_MESSAGE = True,
    WARN_NO_DOC = False,
    )

class SimpleTestMessageCollector():
    # Simple class to collect and sort verification messages
    def __init__(self):
        self.warnings = []
        self.errors = []
        self.infos = []
    def append(self, severity, message):
        if severity=='INFO':
            self.infos.append(message)
        if severity=='WARN':
            self.warnings.append(message)
        if severity=='ERROR':
            self.errors.append(message)
    def to_dict(self):        
        "Return instance variables as dict"
        return { 'infos':self.infos, 'warnings':self.warnings, 'errors':self.errors, }

class ErrorCollection():
    "For collecting contract error messages, to provide them for metadata and documentation."

    def __init__(self, contract_name) -> None:
        self.contract = contracts[contract_name]
        self.error_collection = self.contract['error_messages']
        self.flags = _TestError_default_flags

    def add_error(self, error_code, **kwargs) -> str:
        "Add error and check input, possible kwargs in ALLOWED_ERROR_DATA_KEYS"
        errors = self.error_collection
        error = errors[error_code]
        # Check for redefinitions and disallow changes in this method:
        for key, item in kwargs.items():
            if (key in error) and (error[key]!=item):
                raise AttributeError(f"Redefining '{key}' with new value is not allowed, use TODO to update")
            if not key in ALLOWED_ERROR_DATA_KEYS:
                raise AttributeError(f"'{key}' is not in the allowed error keys: {ALLOWED_ERROR_DATA_KEYS}")
            if key=='failwith_type' and item not in ALLOWED_ERROR_MESSAGE_TYPES:
                raise AttributeError(f"'{key}' is not in the allowed error types: {ALLOWED_ERROR_MESSAGE_TYPES}")
        # Put stuff into error
        error.update(kwargs)

    def verify_error_collection(self, **kwargs) -> SimpleTestMessageCollector:
        "Verifies that all errors pass a set of tests."
        # The optional parameters flags dict can be used to adjust flags by caller.
        test_params = _TestError_default_flags.copy()
        if 'flags' in kwargs:
            test_params.update(kwargs['flags'])

        # Tests on error data, to go through:
        all_tests = dict(
            LONG_CODE        = 'WARN',
            NO_MESSAGE       = 'ERROR',
            NO_MESSAGE_TYPE  = 'WARN',
            NO_FAILWITH_TYPE = 'ERROR',
            )

        # Somewhere to collect messages:
        messages = SimpleTestMessageCollector()
        
        # Iterate over the errors
        for error_key, error_item in self.error_collection.items():
            for test, severity in all_tests.items():
                if test=='LONG_CODE':
                    if len(error_key)>test_params['LONG_KEY_THRESHOLD']:
                        messages.append(severity, f"Error code \"{error_key}\" longer than {test_params['LONG_KEY_THRESHOLD']} characters.")
                if test=='NO_MESSAGE':
                    if 'expansion' not in error_item or not error_item['expansion']:
                        messages.append(severity, f"Error {error_key} 'expansion' attribute is not present or empty.")
                if test=='NO_MESSAGE_TYPE':
                    if 'expansion_type' not in error_item:
                        messages.append(severity, f"Error {error_key} 'expansion_type' attribute is not present or empty.")
                if test=='NO_FAILWITH_TYPE':
                    if 'failwith_type' not in error_item:
                        messages.append(severity, f"Error {error_key} 'failwith_type' attribute is not present or empty.")

        return messages
    
    def tzip16_metadata(self):
        "Return a list with error code and expansion, suitable for adding to the metadata. (Follows TZIP-16)"
        def tzip16_error(code, failwith_type, expansion, expansion_type):
            return dict(
                error     = {failwith_type: code},   # Content should be a Michelson expression (TZIP-16), TODO add test?
                expansion = {expansion_type: expansion}, # Content should be a Michelson expression (TZIP-16), TODO add test?
                languages = ["en"],
                )
        for key, item in self.error_collection.items():
            if not all(['failwith_type' in item, 'expansion' in item, 'expansion_type' in item]):
                print(f"{key} : {item}")
                raise AttributeError(f"All attributes ('failwith_type', 'expansion', 'expansion_type') required for TZIP-16 metadata in error \"{key}\"")

        return [tzip16_error(key,item['failwith_type'],item['expansion'],item['expansion_type']) for key, item in self.error_collection.items()]

    def scenario_linting_report(self, scenario):
        "Output a SmartPy test report."
        results = self.verify_error_collection()
        scenario.h2("FAILWITH Linting report.")
        if results.errors:
            scenario.h3(f"Errors ({len(results.errors)})")
            scenario.p("<br>".join([escape(str(e)) for e in results.errors]))
        if results.warnings:
            scenario.h3(f"Warnings ({len(results.warnings)})")
            scenario.p("<br>".join([escape(str(e)) for e in results.warnings]))
        if results.infos:
            scenario.h3("Infos")
            scenario.p("<br>".join([escape(str(e)) for e in results.infos]))

        if results.errors or results.warnings:
            print(f"Contract {len(results.errors)} linter errors and {len(results.warnings)} warnings.")

    # Convenience aliases:
    ERR=add_error


