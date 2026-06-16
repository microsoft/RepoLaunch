from launch.scripts.parser import run_parser

# A correct, well-formed parser that maps an XML test report to per-test status.
GOOD_PARSER = '''
def parser(log):
    import xml.etree.ElementTree as ET
    root = ET.fromstring(log)
    return {
        e.attrib["testName"]: e.attrib["outcome"].lower()
        for e in root.iter()
        if e.tag.endswith("UnitTestResult")
    }
'''

CLEAN_LOG = '<TestRun><UnitTestResult testName="t1" outcome="Passed"/></TestRun>'

# The raw stdout the harness actually passes to the parser: the echoed command
# line precedes the report, so a strict XML/JSON parser raises on it.
WRAPPED_LOG = "cd /testbed && cat TestResults/test-results.trx\n" + CLEAN_LOG


def test_run_parser_returns_dict_on_clean_input():
    assert run_parser(GOOD_PARSER, CLEAN_LOG) == {"t1": "passed"}


def test_run_parser_surfaces_traceback_when_parser_raises():
    # ElementTree cannot parse the command-echo-prefixed output, so the parser
    # raises. capture_output returns the traceback as a string rather than a
    # dict, so the traceback must be present in the result for callers to
    # surface it back to the agent.
    result = run_parser(GOOD_PARSER, WRAPPED_LOG)
    assert not isinstance(result, dict)
    assert "traceback" in result.lower()
    assert "ParseError" in result
