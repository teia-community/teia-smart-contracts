"""A helper module to manage tezos smart contract errors for TZIP-16 metadata.
"""

from collections import defaultdict
from html import escape
from re import match

# TODO's :
#  add support for multiple languages in errors

# The follwing stores information collected on the various contracts
contracts = defaultdict(lambda:defaultdict(lambda:defaultdict(dict)))

ALLOWED_ERROR_DATA_KEYS = [
    'failwith_type',  # Return type from `FAILWITH` instruction. Always represented as string.
    'expansion',      # Required for TZIP-16 expansion metadata
    'expansion_type', # Required for TZIP-16 expansion metadata
    'doc',            # For extended documentation/tips for dealing with some errors. Optional.
    ]

ALLOWED_ERROR_MESSAGE_TYPES = [
    'string',
    'bytes',
    ]

_TestError_default_flags = dict(
    WARN_LONG_KEY = True,
    LONG_KEY_THRESHOLD = 8,
    ERROR_NO_MESSAGE = True,
    WARN_NO_DOC = False,
    )

class SimpleTestMessageCollector():
    "Simple class to collect and sort verification messages"
    def __init__(self):
        self.warnings = []
        self.errors = []
        self.infos = []
    def append(self, severity, message):
        "Append message of severity 'INFO', 'WARN' or 'ERROR'."
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
    # Options:
    # Whether to raise AttributeError for non-compliances
    TZIP16_NONCOMPLIANCE_RAISE_ERROR = False
    # Whether to add "ERROR_MISSING_*" strings for missing metadata fields.
    # This is currently required to avoid runtime errors.
    TZIP16_POPULATE_MISSING_KEYS = True
    SCENARIO_LINTING_REPORT_PROVIDE_ADDERROR_CALLS_STDOUT = True

    def __init__(self, contract_name) -> None:
        self.contract = contracts[contract_name]
        self.contract_name = contract_name
        self.error_collection = self.contract['error_messages']
        self.flags = _TestError_default_flags

    def inject(self, sp):
        "Code to add wrappers to SmartPy functions deal with contract failure results."
        # Wrapped functions have exact arguments replicated to hopefully
        # Cause errors if smartpy changes their interface.
        if 'injected_error_collection' in dir(sp):
            raise NotImplementedError("TODO: Removal and re-injection of smartpy wrappers for ErrorCollection.")
        # Wrap sp.verify
        sp.wrap_verify_messages = self.add_error
        # Wrap sp.failwith
        def wrapped_failwith(failwith):
            def failwith_wrapper(message):
                self.add_error(message)
                return failwith(message)
            return failwith_wrapper
        sp.failwith = wrapped_failwith(sp.failwith)
        # Wrap sp.Expr.open_variant()
        def wrapped_open_variant(open_variant):
            def open_variant_wrapper(_self, name, message = None):
                if message is not None:
                    self.add_error(message)
                return open_variant(_self, name, message=message)
            return open_variant_wrapper
        sp.Expr.open_variant = wrapped_open_variant(sp.Expr.open_variant)
        # Set flag so we don't repeat this procedure:
        sp.injected_error_collection = True
        # Return self for use with instantiation
        return self

    def add_error(self, error_code, **kwargs) -> str:
        "Add error and check input, possible kwargs in ALLOWED_ERROR_DATA_KEYS"
        # These are false positives:
        if match(r"View \w+ is invalid!", error_code):
            return

        errors = self.error_collection
        error = errors[error_code]
        # Check for redefinitions and disallow changes in this method:
        for key, item in kwargs.items():
            if (key in error) and (error[key]!=item):
                raise AttributeError(f"Redefining '{key}' with new value is not allowed, use TODO to update")
            if not key in ALLOWED_ERROR_DATA_KEYS:
                raise AttributeError(f"'{key}' is not in the allowed error keys: {ALLOWED_ERROR_DATA_KEYS}")
            if key=='failwith_type' and item not in ALLOWED_ERROR_MESSAGE_TYPES:
                raise AttributeError(f"'{item}' is not in the allowed error types: {ALLOWED_ERROR_MESSAGE_TYPES}")
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
                message = f"All attributes ('failwith_type', 'expansion', 'expansion_type') required for TZIP-16 metadata in error \"{key}\""
                print(f"TZIP-16 Non-compliance in {key} : {item}\n{message}")
                if ErrorCollection.TZIP16_NONCOMPLIANCE_RAISE_ERROR:
                    raise AttributeError(message)
            if ErrorCollection.TZIP16_POPULATE_MISSING_KEYS:
                if not 'failwith_type' in item:
                    item['failwith_type'] = 'ERROR_MISSING_TYPE'
                if not 'expansion' in item:
                    item['expansion'] = 'ERROR_MISSING_EXPANSION'
                if not 'expansion_type' in item:
                    item['expansion_type'] = 'ERROR_MISSING_EXPANSION_TYPE'

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
            print("*** TZIP-16 Metadata linting report for contract call errors.")
            print(f"*** {self.contract_name}: {len(results.errors)} errors and {len(results.warnings)} warnings.")
            _ = self.tzip16_metadata()
            if ErrorCollection.SCENARIO_LINTING_REPORT_PROVIDE_ADDERROR_CALLS_STDOUT:
                print("*** (help) Function calls to add metadata to contract and ErrorCollector:\n")
                print("# A function handle to call the contract's error_collection.add_error()")
                print("add_error = DAOToken.error_collector.add_error")
                print("# An add_error method for each error encountered in the contract:")
                print("\n".join( [f"add_error(\"{key}\","
                     +"\n          " +"\n          ".join(
                      [f"{item_key} = \"{item_value}\"," for item_key, item_value in item.items()]) + ")"
                     for key, item in self.error_collection.items()]))


    # Convenience aliases:
    ERR=add_error
