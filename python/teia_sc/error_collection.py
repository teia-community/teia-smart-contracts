"""
This module adds some tests and coverage for contract failwith results.

This module will track failwith results that occur during testing. It will
then check against errors explained in CONTRACT_METADATA_BASE['errors'] and
report if some explanations/expansions are missing.

The module will not discover contract failure conditions that do not occur
during test. In some cases this could be hard cover. E.g. divide by zero, or
other illegal use of instructions will also cause contract failure.

Finding and testing these illegal conditions have not been a focus of this
implementation yet, although it could perhaps be added soon. The expected
use-case for the module as is, is to check all messages have explainers.
"""

from __future__ import annotations
from collections import defaultdict
from itertools import combinations
from html import escape
from re import match
from inspect import stack
from logging import warning
from pprint import pformat

# TODO's :
#  Add support for multiple languages.
#  Look at Michelson return types in TZIP-16 standard,
#    - How to specify properly
#    - Leverage smartpy for the return values?

# The following stores information collected on the various contracts
contracts = defaultdict(lambda:defaultdict(lambda:defaultdict(dict)))

# Keyword arguments that can be supplied to ErrorCollector.add_tzip16_error():
ALLOWED_ERROR_DATA_KEYS = [
    'failwith_type',  # Return type from `FAILWITH` instruction. Always represented as string.
    'expansion_data', # Required for TZIP-16 expansion metadata
    'expansion_type', # Required for TZIP-16 expansion metadata
    'languages',      # List of language codes, e.g. ["en", "fr"]
    ]

ALLOWED_ERROR_METADATA_KEYS = [
    'error',     # Return type from `FAILWITH` instruction. Always represented as string.
    'view',      # Required for TZIP-16 expansion metadata
    'expansion', # Required for TZIP-16 expansion metadata
    'languages', # List of language codes, e.g. ["en", "fr"]
    ]

# Allowed values for failwith_type and expansion_type.
ALLOWED_ERROR_MESSAGE_TYPES = [
    'string',
    'bytes',
    ]

# Language codes extracted from https://en.wikipedia.org/wiki/IETF_language_tag
ALLOWED_LANGUAGE_CODES = {
    'af', 'am',  'ar',  'arn', 'as',  'az',  'ba',  'be',  'bg',  'bn',  'bo',  'br',
    'bs', 'ca',  'co',  'cs',  'cy',  'da',  'de',  'dsb', 'dv',  'el',  'en',  'es',
    'et', 'eu',  'fa',  'fi',  'fil', 'fo',  'fr',  'fy',  'ga',  'gd',  'gl',  'gsw',
    'gu', 'ha',  'he',  'hi',  'hr',  'hsb', 'hu',  'hy',  'id',  'ig',  'ii',  'is',
    'it', 'iu',  'ja',  'ka',  'kk',  'kl',  'km',  'kn',  'ko',  'kok', 'ky',  'lb',
    'lo', 'lt',  'lv',  'mi',  'mk',  'ml',  'mn',  'moh', 'mr',  'ms',  'mt',  'my',
    'nb', 'ne',  'nl',  'nn',  'no',  'nso', 'oc',  'or',  'pa',  'pl',  'prs', 'ps',
    'pt', 'qut', 'quz', 'rm',  'ro',  'ru',  'rw',  'sa',  'sah', 'se',  'si',  'sk',
    'sl', 'sma', 'smj', 'smn', 'sms', 'sq',  'sr',  'sv',  'sw',  'syr', 'ta',  'te',
    'tg', 'th',  'tk',  'tn',  'tr',  'tt',  'tzm', 'ug',  'uk',  'ur',  'uz',  'vi',
    'wo', 'xh',  'yo',  'zh',  'zu'}

MICHELSON_CORE_PRIMITIVE_TYPES = { "string", "int", "nat", "bytes" }

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

def check_legal_language_codes(tzip16_languages) -> True:
    "Check that the languages given are a list with legal codes"
    if not isinstance(tzip16_languages,list):
        raise TypeError("TZIP-16 error languages should be given as a list of strings.")
    for l_code in tzip16_languages: # pylint: disable=invalid-name
        if not isinstance(l_code,str):
            raise TypeError("TZIP-16 error languages should be given as a list of strings.")
        if l_code not in ALLOWED_LANGUAGE_CODES:
            raise ValueError(f"Unknown language code used for TZIP-16 error: \"{l_code}\"")
    return True

def check_expansion_legal(tzip16_expansion) -> True:
    "Check that the expansion given is a dict with 1 item"
    if not isinstance(tzip16_expansion,dict):
        raise TypeError(f"TZIP-16 expansion should be a dict, not {type(tzip16_expansion)}.")
    if not len(tzip16_expansion)==1:
        raise TypeError('TZIP-16 static error expansion metadata expects 1 element')
    # TODO more tests for expansion type and data can be added here
    return True

def check_error_legal(tzip16_error) -> True:
    "Check that the error given is a dict with 1 item"
    if not isinstance(tzip16_error,dict):
        raise TypeError(f"TZIP-16 expansion should be a dict, not {type(tzip16_error)}.")
    if not len(tzip16_error)==1:
        raise TypeError("TZIP-16 static errors represent 1 stack element with a generic type."+
                        " The metadata input should be a dict with 2 element.")
    # TODO more tests for error type and data can be added here
    return True

def check_error_metadata_keys_clean(tzip16_error, critical=False) -> bool:
    "Check remaining kwargs to warn about unknown key names, but otherwise pass them through"
    clean = True
    for key in tzip16_error.keys():
        if key not in ALLOWED_ERROR_METADATA_KEYS:
            msg = f"Unknown key '{key}' used for TZIP-16 error."
            if not critical:
                warning("Warning:" + msg)
            else:
                raise ValueError(msg)
            clean = False
    return clean

def check_tzip16_error_kwargs(**kwargs) -> None:
    "Check if arguments are allowed."
    for key, item in kwargs.items():
        if not key in ALLOWED_ERROR_DATA_KEYS:
            raise AttributeError(f"'{key}' is not in the allowed error keys: {ALLOWED_ERROR_DATA_KEYS}")
        if key=='failwith_type' and item not in ALLOWED_ERROR_MESSAGE_TYPES:
            raise AttributeError(f"'{item}' is not in the allowed error types: {ALLOWED_ERROR_MESSAGE_TYPES}")

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

def _add_sc_error_ref(failwith_result):
    "Marks presence of error"
    # These are false positives:
    if match(r"View \w+ is invalid!", failwith_result):
        return
    def get_contract_caller():
        # Traverse stack to check who the caller was
        for line in stack():
            if 'self' in line[0].f_locals:
                contract_name = line[0].f_locals['self'].__class__.__name__
                if contract_name in contracts:
                    return contract_name
        return None, None
    contract_name = get_contract_caller()
    if contract_name:
        # Record the reference
        contracts[contract_name]['error_collection'][failwith_result].update({})
    return failwith_result

class ErrorCollection():
    "For collecting contract error messages, to provide them for metadata and documentation."
    # Options:
    # Whether to raise AttributeError for non-compliances
    TZIP16_NONCOMPLIANCE_RAISE_ERROR = False
    # Whether to add "ERROR_MISSING_*" strings for missing metadata fields.
    # This is currently required to avoid runtime errors.
    TZIP16_POPULATE_MISSING_KEYS = True
    SCENARIO_LINTING_REPORT_PROVIDE_ERRORS_DICT = True
    SCENARIO_LINTING_REPORT_PROVIDE_ERRORS_DICT_STDOUT = True

    def __init__(self, contract_name) -> None:
        self.contract = contracts[contract_name]
        self.contract_name = contract_name
        self.error_collection = self.contract['error_collection']
        self.languages = self.contract['languages'] = defaultdict(set)
        self.flags = _TestError_default_flags.copy()
        self.add_tzip16_error_default_kwargs = {}

    def add_base_metadata(self, cls) -> ErrorCollection:
        """Add metadata from the cls class variable CONTRACT_METADATA_BASE
        into the ErrorCollection instance."""
        for error in cls.CONTRACT_METADATA_BASE['errors']:
            self.add_tzip16_error_from_metadata(error)
        # Return self for use with instantiation / chaining
        return self

    def inject_into_smartpy(self, smartpy) -> ErrorCollection:
        """Adds wrappers into SmartPy functions to gather contract failure messages.

        :param smartpy: The smartpy module to inject into.
        :type smartpy: module
        """
        # Wrapped functions have exact arguments replicated to hopefully
        # cause errors if smartpy changes the interface at some point.
        if 'injected_error_collection' in dir(smartpy):
            return self
        if BLOCK_SMARTPY_INJECTION:
            return self
        # Wrap messages in smartpy.verify using ready-made functionality
        smartpy.wrap_verify_messages = _add_sc_error_ref
        # Wrap smartpy.failwith
        def wrapped_failwith(failwith):
            def failwith_wrapper(message):
                _add_sc_error_ref(message)
                return failwith(message)
            return failwith_wrapper
        smartpy.failwith = wrapped_failwith(smartpy.failwith)
        # Wrap smartpy.Expr.open_variant()
        def wrapped_open_variant(open_variant):
            def open_variant_wrapper(_self, name, message = None):
                if message is not None:
                    _add_sc_error_ref(message)
                return open_variant(_self, name, message=message)
            return open_variant_wrapper
        smartpy.Expr.open_variant = wrapped_open_variant(smartpy.Expr.open_variant)
        # Set flag so we don't repeat this procedure:
        smartpy.injected_error_collection = True
        # Return self for use with instantiation / chaining
        return self

    def add_error(self, failwith_result, **kwargs) -> None:
        "Add error"
        errors = self.error_collection
        error = errors[failwith_result]
        if 'allow_updates' not in kwargs or not kwargs['allow_updates']:
            # Check for redefinitions and disallow changes in this method:
            kwargs.pop('allow_updates')
            for key, item in kwargs.items():
                if (key in error) and (error[key]!=item):
                    raise AttributeError(f"Redefining '{key}' with new value is not allowed, use TODO to update")
        # Put stuff into error
        error.update(kwargs)

    def add_or_update_error(self, failwith_result, **kwargs) -> None:
        "Add or update error"
        self.error_collection[failwith_result].update(kwargs)

    def tzip16_error_default(self, **kwargs) -> None:
        """Reset and set default arguments to add_tzip16_error() as given by kwargs.

        This is a convenience method which gives less clutter when using add_tzip16_error to
        input errors in the contract script.
        """
        # Check kwargs are allowed
        check_tzip16_error_kwargs(**kwargs)
        # Set the new default parameters for add_tzip16_error()
        self.add_tzip16_error_default_kwargs = dict(kwargs)

    def add_tzip16_error(self, failwith_result, **kwargs) -> None:
        "Add error with metadata to collection and check input. Allowed kwargs in ALLOWED_ERROR_DATA_KEYS."
        # Check kwargs are allowed
        check_tzip16_error_kwargs(**kwargs)
        # Start with current default parameters and update them with kwargs
        effective_kwargs = dict(self.add_tzip16_error_default_kwargs)
        effective_kwargs.update(kwargs)
        errors = self.error_collection
        error = errors[failwith_result]
        # Check for redefinitions and disallow changes in this method:
        for key, item in effective_kwargs.items():
            if (key in error) and (error[key]!=item):
                raise AttributeError(f"Redefining '{key}' with new value is not allowed, use TODO to update")
        # Put stuff into error
        error.update(effective_kwargs)


    def add_languages(self, languages, failwith_result):
        "Add the languages and the failwith_result to self.languages to keep track."
        check_legal_language_codes(languages)
        for l_code in languages:
            self.languages[l_code].add(failwith_result)

    def add_tzip16_error_from_metadata(self, tzip16_error):
        """Reads a TZIP-16 error (defined as a dict in the contract metadata)
        test if the input format looks compliant and inserts the error in
        the ErrorCollection via add_tzip16_error()"""
        # pylint: disable=too-many-branches
        if 'view' in tzip16_error:
            warning("NotImplementedWarning: TZIP-16 dynamic errors are not handled yet.")
            return

        check_error_legal(tzip16_error['error'])
        # Get 'error' key, value pair.
        (failwith_type, failwith_result), = tzip16_error['error'].items()
        tzip16_error.pop('error')

        # Start assembling a kwargs dict to pass to add_tzip16_error()
        add_error_kwargs = dict(failwith_type=failwith_type)

        if 'expansion' in tzip16_error:
            check_expansion_legal(tzip16_error['expansion'])
            # Get the key, value pair
            (expansion_type, expansion_data), = tzip16_error['expansion'].items()
            add_error_kwargs.update(expansion_type=expansion_type, expansion_data=expansion_data)
            tzip16_error.pop('expansion')

        # Pass through remaining kwargs (after pop)
        add_error_kwargs.update(tzip16_error)

        # Check remaining kwargs to warn about unknown key names
        check_error_metadata_keys_clean(tzip16_error)

        if 'languages' in tzip16_error:
            self.add_languages(tzip16_error['languages'], failwith_result)

        # Add the error into the internal structure
        self.add_tzip16_error( failwith_result, **add_error_kwargs )

    def verify_error_collection(self, **kwargs) -> SimpleTestMessageCollector:
        "Verifies that all errors pass a set of tests."
        # pylint: disable=too-many-branches
        # The optional parameters flags dict can be used to adjust flags by caller.
        test_params = self.flags.copy()
        if 'flags' in kwargs:
            test_params.update(kwargs['flags'])

        # Tests on error data, to go through:
        error_tests = dict(
            LONG_CODE         = 'WARN',
            NO_EXPANSION_DATA = 'ERROR',
            NO_EXPANSION_TYPE = 'ERROR',
            NO_FAILWITH_TYPE  = 'ERROR',
            SIMPLE_FAILWITH_TYPE  = 'WARN',
            )

        language_tests = dict(
            LANGUAGES_HAVE_DIFFERENT_ERROR_RESULTS = 'WARN',
        )

        # Somewhere to collect messages:
        messages = SimpleTestMessageCollector()

        # Iterate over the errors
        for error_key, error_item in self.error_collection.items():
            for test, severity in error_tests.items():
                if test=='LONG_CODE':
                    if 'failwith_type' in error_item and error_item['failwith_type'] in MICHELSON_CORE_PRIMITIVE_TYPES:
                        if len(error_key)>test_params['LONG_KEY_THRESHOLD']:
                            messages.append(severity,
                                f"Error result \"{error_key}\" longer than {test_params['LONG_KEY_THRESHOLD']} characters.")

                if test=='NO_EXPANSION_DATA':
                    if 'expansion_data' not in error_item or not error_item['expansion_data']:
                        messages.append(severity, f"Error {error_key} 'expansion_data' attribute is not present or empty.")
                if test=='NO_EXPANSION_TYPE':
                    if 'expansion_type' not in error_item:
                        messages.append(severity, f"Error {error_key} 'expansion_type' attribute is not present or empty.")
                if test=='NO_FAILWITH_TYPE':
                    if 'failwith_type' not in error_item:
                        messages.append(severity, f"Error {error_key} 'failwith_type' attribute is not present or empty.")
                if test=='SIMPLE_FAILWITH_TYPE':
                    if ('failwith_type' in error_item
                      and not error_item['failwith_type'] in MICHELSON_CORE_PRIMITIVE_TYPES):
                        messages.append(severity, f"Non primitive return-type for error result \"{error_key}\".")

        # Iterate over language combinations:
        known_language_codes = set(self.languages.keys())
        if 'LANGUAGES_HAVE_DIFFERENT_ERROR_RESULTS' in language_tests:
            severity = language_tests['LANGUAGES_HAVE_DIFFERENT_ERROR_RESULTS']
            for l1_code, l2_code in combinations(known_language_codes, 2):
                l1_code_set, l2_code_set = self.languages[l1_code], self.languages[l2_code]
                if l1_code_set.difference(l2_code_set):
                    messages.append(severity, f"Language \"{l1_code}\" implements but \"{l2_code}\" does not implement:\n"
                                            + f"{pformat(l1_code_set.difference(l2_code_set),indent=1,width=100)}")
                if l2_code_set.difference(l1_code_set):
                    messages.append(severity, f"Language \"{l2_code}\" implements but \"{l1_code}\" does not implement:\n"
                                            + f"{pformat(l2_code_set.difference(l1_code_set),indent=1,width=100)}")

        return messages

    def tzip16_metadata(self, populate_missing_keys = True ) -> list(dict):
        "Return a list with error and expansion, suitable for adding to the metadata. (Follows TZIP-16)"
        def tzip16_error(failwith_result, failwith_type, expansion_data, expansion_type):
            return dict(
                error     = {failwith_type: failwith_result},
                expansion = {expansion_type: expansion_data},
                languages = ["en"],
                )
        for key, item in self.error_collection.items():
            if not all(['failwith_type' in item, 'expansion_data' in item, 'expansion_type' in item]):
                message = ("All attributes ('failwith_type', 'expansion_data',"
                         +f" 'expansion_type') required for TZIP-16 metadata in error \"{key}\"")
                print(f"TZIP-16 Non-compliance in {key} : {item}\n{message}")
                if ErrorCollection.TZIP16_NONCOMPLIANCE_RAISE_ERROR:
                    raise AttributeError(message)
            if populate_missing_keys and ErrorCollection.TZIP16_POPULATE_MISSING_KEYS:
                if not 'failwith_type' in item:
                    item['failwith_type'] = 'ERROR_MISSING_FAILWITH_TYPE'
                if not 'expansion_data' in item:
                    item['expansion_data'] = 'ERROR_MISSING_EXPANSION_DATA'
                if not 'expansion_type' in item:
                    item['expansion_type'] = 'ERROR_MISSING_EXPANSION_TYPE'
            else:
                if not 'failwith_type' in item:
                    item['failwith_type'] = ''
                if not 'expansion_data' in item:
                    item['expansion_data'] = ''
                if not 'expansion_type' in item:
                    item['expansion_type'] = ''

        return [ tzip16_error(key,item['failwith_type'],item['expansion_data'],item['expansion_type'])
                 for key, item in self.error_collection.items() ]

    def scenario_linting_report(self, scenario) -> None:
        "Output a SmartPy test report."
        if ErrorCollection.SCENARIO_LINTING_REPORT_PROVIDE_ERRORS_DICT_STDOUT:
            sprint = lambda x: [scenario.p("<pre><code>"+x+"</code></pre>"), print(x)]
        else:
            sprint = lambda x: scenario.p("<pre><code>"+x+"</code></pre>")
        results = self.verify_error_collection()
        scenario.h2(f"FAILWITH Linting report for {self.contract_name}.")
        if results.errors:
            scenario.h3(f"Errors ({len(results.errors)})")
            scenario.p("<br>".join([escape(str(error)) for error in results.errors]))
        if results.warnings:
            scenario.h3(f"Warnings ({len(results.warnings)})")
            scenario.p("<br>".join([escape(str(error)) for error in results.warnings]))
        if results.infos:
            scenario.h3("Infos")
            scenario.p("<br>".join([escape(str(error)) for error in results.infos]))

        tzip_metadata_errors_list = self.tzip16_metadata()
        if results.errors or results.warnings:
            print("\n*** TZIP-16 Metadata linting report for contract call errors.")
            print(f"*** {self.contract_name}: {len(results.errors)} errors and {len(results.warnings)} warnings.")

            if ErrorCollection.SCENARIO_LINTING_REPORT_PROVIDE_ERRORS_DICT:
                scenario.h3(msg:="Error metadata helper dict (contains errors or missing fields)")
                if ErrorCollection.SCENARIO_LINTING_REPORT_PROVIDE_ERRORS_DICT_STDOUT:
                    print(msg)
                sprint(pformat({'errors':tzip_metadata_errors_list}, indent=1, width=100 ) )
