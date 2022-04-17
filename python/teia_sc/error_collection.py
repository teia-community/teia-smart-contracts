from __future__ import annotations
from collections import defaultdict
from html import escape
from json import dumps
from re import match
from inspect import stack

# TODO's :
#  Add support for multiple languages in errors.
#  Look at Michelson return types in TZIP-16 standard,
#    - How to specify properly
#    - How to leverage smartpy for the return values

# The follwing stores information collected on the various contracts
contracts = defaultdict(lambda:defaultdict(lambda:defaultdict(dict)))

# Keyword arguments that can be supplied to ErrorCollector.add_tzip16_error():
ALLOWED_ERROR_DATA_KEYS = [
    'failwith_type',  # Return type from `FAILWITH` instruction. Always represented as string.
    'expansion',      # Required for TZIP-16 expansion metadata
    'expansion_type', # Required for TZIP-16 expansion metadata
    'doc',            # For extended documentation/tips for dealing with some errors. Optional.
    ]

# Allowed values for failwith_type and expansion_type.
ALLOWED_ERROR_MESSAGE_TYPES = [
    'string',
    'bytes',
    ]

# Module option to block smartpy injection. This will cause there to be no
# discovery of smart contract errors (through tests). It may be useful as a
# switch to turn off that function without touching the contract code.
# Not so useful today, but perhaps in the future if ever the case arises
# where the injection has an undesirable effect on smartpy.
BLOCK_SMARTPY_INJECTION = False

# Default settings for
_TestError_default_flags = dict(
    WARN_LONG_KEY = True,
    LONG_KEY_THRESHOLD = 8,
    ERROR_NO_MESSAGE = True,
    WARN_NO_DOC = False,
    )

class SimpleTestMessageCollector():
    "Simple class to collect and sort verification messages according to severity"
    def __init__(self) -> None:
        self.warnings = []
        self.errors = []
        self.infos = []
    def append(self, severity, message) -> None:
        "Append message of severity 'INFO', 'WARN' or 'ERROR'."
        if severity=='INFO':
            self.infos.append(message)
        elif severity=='WARN':
            self.warnings.append(message)
        elif severity=='ERROR':
            self.errors.append(message)
        else:
            raise ValueError("Severity not one of 'INFO', 'WARN', 'ERROR'.")
    def to_dict(self) -> dict:
        "Return dict with infos, warnings, messages."
        return { 'infos':self.infos, 'warnings':self.warnings, 'errors':self.errors, }

def _add_sc_error_ref(error_code):
    "Marks presence of error"
    # These are false positives:
    if match(r"View \w+ is invalid!", error_code):
        return
    def get_contract_caller():
        # Traverse stack to check who the caller was
        for line in stack():
            if 'self' in line[0].f_locals:
                cn = line[0].f_locals['self'].__class__.__name__
                global contracts
                if cn in contracts:
                    return cn
        return None, None
    contract_name = get_contract_caller()
    if contract_name:
        # Record the reference
        global contracts
        contracts[contract_name]['error_collection'][error_code].update({})
    return error_code

class ErrorCollection():
    "For collecting contract error messages, to provide them for metadata and documentation."
    # Options:
    # Whether to raise AttributeError for non-compliances
    TZIP16_NONCOMPLIANCE_RAISE_ERROR = False
    # Whether to add "ERROR_MISSING_*" strings for missing metadata fields.
    # This is currently required to avoid runtime errors.
    TZIP16_POPULATE_MISSING_KEYS = True
    SCENARIO_LINTING_REPORT_PROVIDE_ADDERROR_CALLS = True
    SCENARIO_LINTING_REPORT_PROVIDE_ADDERROR_CALLS_STDOUT = True

    def __init__(self, contract_name) -> None:
        global contracts
        self.contract = contracts[contract_name]
        self.contract_name = contract_name
        self.error_collection = self.contract['error_collection']
        self.flags = _TestError_default_flags.copy()
        self.add_tzip16_error_default_kwargs = {}

    def inject_into_smartpy(self, sp) -> ErrorCollection:
        """Adds wrappers into SmartPy functions to gather contract failure messages.

        :param sp: The smartpy module to inject into.
        :type sp: module
        """
        # Wrapped functions have exact arguments replicated to hopefully
        # cause errors if smartpy changes the interface at some point.
        if 'injected_error_collection' in dir(sp):
            return self
        if BLOCK_SMARTPY_INJECTION:
            return self
        # Wrap messages in sp.verify using ready-made functionality
        sp.wrap_verify_messages = _add_sc_error_ref
        # Wrap sp.failwith
        def wrapped_failwith(failwith):
            def failwith_wrapper(message):
                _add_sc_error_ref(message)
                return failwith(message)
            return failwith_wrapper
        sp.failwith = wrapped_failwith(sp.failwith)
        # Wrap sp.Expr.open_variant()
        def wrapped_open_variant(open_variant):
            def open_variant_wrapper(_self, name, message = None):
                if message is not None:
                    _add_sc_error_ref(message)
                return open_variant(_self, name, message=message)
            return open_variant_wrapper
        sp.Expr.open_variant = wrapped_open_variant(sp.Expr.open_variant)
        # Set flag so we don't repeat this procedure:
        sp.injected_error_collection = True
        # Return self for use with instantiation
        return self

    def add_error(self, error_code, **kwargs) -> None:
        "Add error"
        errors = self.error_collection
        error = errors[error_code]
        if 'allow_updates' not in kwargs or not kwargs['allow_updates']:
            # Check for redefinitions and disallow changes in this method:
            kwargs.pop('allow_updates')
            for key, item in kwargs.items():
                if (key in error) and (error[key]!=item):
                    raise AttributeError(f"Redefining '{key}' with new value is not allowed, use TODO to update")
        # Put stuff into error
        error.update(kwargs)

    def add_or_update_error(self, error_code, **kwargs) -> None:
        "Add or update error"
        self.error_collection[error_code].update(kwargs)

    def tzip16_error_check_kwargs(self, **kwargs) -> None:
        "Check if arguments are allowed."
        for key, item in kwargs.items():
            if not key in ALLOWED_ERROR_DATA_KEYS:
                raise AttributeError(f"'{key}' is not in the allowed error keys: {ALLOWED_ERROR_DATA_KEYS}")
            if key=='failwith_type' and item not in ALLOWED_ERROR_MESSAGE_TYPES:
                raise AttributeError(f"'{item}' is not in the allowed error types: {ALLOWED_ERROR_MESSAGE_TYPES}")

    def tzip16_error_default(self, **kwargs) -> None:
        """Reset and set default arguments to add_tzip16_error() as given by kwargs.

        This is a convenience method which gives less clutter when using add_tzip16_error to 
        input errors in the contract script.
        """
        # Check kwargs are allowed
        self.tzip16_error_check_kwargs(**kwargs)
        # Set the new default parameters for add_tzip16_error()
        self.add_tzip16_error_default_kwargs = dict(kwargs)

    def add_tzip16_error(self, error_code, **kwargs) -> None:
        "Add error with metadata to collection and check input. Allowed kwargs in ALLOWED_ERROR_DATA_KEYS."
        # Check kwargs are allowed
        self.tzip16_error_check_kwargs(**kwargs)
        # Start with current default parameters and update them with kwargs
        effective_kwargs = dict(self.add_tzip16_error_default_kwargs)
        effective_kwargs.update(kwargs)
        errors = self.error_collection
        error = errors[error_code]
        # Check for redefinitions and disallow changes in this method:
        for key, item in effective_kwargs.items():
            if (key in error) and (error[key]!=item):
                raise AttributeError(f"Redefining '{key}' with new value is not allowed, use TODO to update")
        # Put stuff into error
        error.update(effective_kwargs)

    def verify_error_collection(self, **kwargs) -> SimpleTestMessageCollector:
        "Verifies that all errors pass a set of tests."
        # The optional parameters flags dict can be used to adjust flags by caller.
        test_params = self.flags.copy()
        if 'flags' in kwargs:
            test_params.update(kwargs['flags'])

        # Tests on error data, to go through:
        all_tests = dict(
            LONG_CODE         = 'WARN',
            NO_EXPANSION      = 'ERROR',
            NO_EXPANSION_TYPE = 'ERROR',
            NO_FAILWITH_TYPE  = 'ERROR',
            )

        # Somewhere to collect messages:
        messages = SimpleTestMessageCollector()

        # Iterate over the errors
        for error_key, error_item in self.error_collection.items():
            for test, severity in all_tests.items():
                if test=='LONG_CODE':
                    if len(error_key)>test_params['LONG_KEY_THRESHOLD']:
                        messages.append(severity, f"Error code \"{error_key}\" longer than {test_params['LONG_KEY_THRESHOLD']} characters.")
                if test=='NO_EXPANSION':
                    if 'expansion' not in error_item or not error_item['expansion']:
                        messages.append(severity, f"Error {error_key} 'expansion' attribute is not present or empty.")
                if test=='NO_EXPANSION_TYPE':
                    if 'expansion_type' not in error_item:
                        messages.append(severity, f"Error {error_key} 'expansion_type' attribute is not present or empty.")
                if test=='NO_FAILWITH_TYPE':
                    if 'failwith_type' not in error_item:
                        messages.append(severity, f"Error {error_key} 'failwith_type' attribute is not present or empty.")

        return messages

    def tzip16_metadata(self, populate_missing_keys = True ) -> list(dict):
        "Return a list with error code and expansion, suitable for adding to the metadata. (Follows TZIP-16)"
        def tzip16_error(code, failwith_type, expansion, expansion_type):
            return dict(
                error     = {failwith_type: code},       # Content should be a Michelson expression (TZIP-16), TODO investigate
                expansion = {expansion_type: expansion}, # Content should be a Michelson expression (TZIP-16), TODO investigate
                languages = ["en"],
                )
        for key, item in self.error_collection.items():
            if not all(['failwith_type' in item, 'expansion' in item, 'expansion_type' in item]):
                message = f"All attributes ('failwith_type', 'expansion', 'expansion_type') required for TZIP-16 metadata in error \"{key}\""
                print(f"TZIP-16 Non-compliance in {key} : {item}\n{message}")
                if ErrorCollection.TZIP16_NONCOMPLIANCE_RAISE_ERROR:
                    raise AttributeError(message)
            if populate_missing_keys and ErrorCollection.TZIP16_POPULATE_MISSING_KEYS:
                if not 'failwith_type' in item:
                    item['failwith_type'] = 'ERROR_MISSING_TYPE'
                if not 'expansion' in item:
                    item['expansion'] = 'ERROR_MISSING_EXPANSION'
                if not 'expansion_type' in item:
                    item['expansion_type'] = 'ERROR_MISSING_EXPANSION_TYPE'
            else:
                if not 'failwith_type' in item:
                    item['failwith_type'] = ''
                if not 'expansion' in item:
                    item['expansion'] = ''
                if not 'expansion_type' in item:
                    item['expansion_type'] = ''

        return [tzip16_error(key,item['failwith_type'],item['expansion'],item['expansion_type']) for key, item in self.error_collection.items()]

    def scenario_linting_report(self, scenario) -> None:
        "Output a SmartPy test report."
        if ErrorCollection.SCENARIO_LINTING_REPORT_PROVIDE_ADDERROR_CALLS_STDOUT:
            sprint = lambda x: [scenario.p("<pre><code>"+x+"</code></pre>"), print(x)]
        else:
            sprint = lambda x: scenario.p("<pre><code>"+x+"</code></pre>")
        results = self.verify_error_collection()
        scenario.h2(f"FAILWITH Linting report for {self.contract_name}.")
        if results.errors:
            scenario.h3(f"Errors ({len(results.errors)})")
            scenario.p("<br>".join([escape(str(e)) for e in results.errors]))
        if results.warnings:
            scenario.h3(f"Warnings ({len(results.warnings)})")
            scenario.p("<br>".join([escape(str(e)) for e in results.warnings]))
        if results.infos:
            scenario.h3("Infos")
            scenario.p("<br>".join([escape(str(e)) for e in results.infos]))

        tzip_dict = self.tzip16_metadata()
        if results.errors or results.warnings:
            print("*** TZIP-16 Metadata linting report for contract call errors.")
            print(f"*** {self.contract_name}: {len(results.errors)} errors and {len(results.warnings)} warnings.")

            if ErrorCollection.SCENARIO_LINTING_REPORT_PROVIDE_ADDERROR_CALLS:
                scenario.h3(msg:="*** Helpful snippet to add error metadata to contract:")
                if ErrorCollection.SCENARIO_LINTING_REPORT_PROVIDE_ADDERROR_CALLS_STDOUT:
                    print(msg)
                sprint(f"## The following lines would be added in {self.contract_name} class:\n"
                   "# A function handle to call the contract's error_collection.add_tzip16_error()\n"
                 + f"tzip16_error = {self.contract_name}.error_collection.add_tzip16_error\n\n"
                 + f"## The following lines would be added in {self.contract_name}.__init__():\n"
                 + "# A tzip16_error() call for each error encountered in the contract:\n"
                 + "\n".join( [f"tzip16_error(\"{key}\","
                     +"\n  " +"\n  ".join(
                         [f"{item_key:18} = \"{item_value}\"," for item_key, item_value in item.items()]) + ")"
                     for key, item in self.error_collection.items()]))

        scenario.h3("JSON for error metadata")
        scenario.p("<pre><code>"+dumps(tzip_dict, indent = 2)+"</pre></code>")

