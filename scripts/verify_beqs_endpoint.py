#!/usr/bin/env python3
"""
BEQS Endpoint Verification Script

Tests Bloomberg Equity Screening (BEQS) API integration points:
1. Service availability (//blp/refdata)
2. BeqsRequest availability and structure
3. Response parsing from a test screen
4. Field structure inspection

Run with Bloomberg Terminal connected:
    python scripts/verify_beqs_endpoint.py
"""

import sys
from datetime import datetime
from typing import Optional, Dict, Any, List

try:
    import blpapi
except ImportError:
    print("ERROR: blpapi not installed. Install via: pip install blpapi")
    sys.exit(1)


# =============================================================================
# CONFIGURATION
# =============================================================================

BLOOMBERG_HOST = "localhost"
BLOOMBERG_PORT = 8194
REQUEST_TIMEOUT_MS = 30000

# Test screens to verify
TEST_SCREENS = [
    {"name": "TOP_WORLD_MARKET_CAP", "type": "GLOBAL"},
    # Add more test screens as needed
]


# =============================================================================
# SESSION MANAGEMENT
# =============================================================================

def create_session() -> blpapi.Session:
    """Create and start Bloomberg session."""
    session_options = blpapi.SessionOptions()
    session_options.setServerHost(BLOOMBERG_HOST)
    session_options.setServerPort(BLOOMBERG_PORT)

    session = blpapi.Session(session_options)
    if not session.start():
        raise RuntimeError(f"Failed to start session to {BLOOMBERG_HOST}:{BLOOMBERG_PORT}")

    return session


def open_service(session: blpapi.Session, service_uri: str) -> blpapi.Service:
    """Open a Bloomberg service."""
    if not session.openService(service_uri):
        raise RuntimeError(f"Failed to open service: {service_uri}")
    return session.getService(service_uri)


# =============================================================================
# VERIFICATION TESTS
# =============================================================================

def verify_refdata_service(session: blpapi.Session) -> Dict[str, Any]:
    """Verify //blp/refdata service and list operations."""
    print("\n" + "="*60)
    print("TEST 1: Verify //blp/refdata Service")
    print("="*60)

    result = {
        "service": "//blp/refdata",
        "available": False,
        "operations": [],
        "beqs_available": False,
    }

    try:
        service = open_service(session, "//blp/refdata")
        result["available"] = True
        print(f"[OK] Service opened successfully")
        print(f"     Operations: {service.numOperations()}")

        for i in range(service.numOperations()):
            op = service.getOperation(i)
            op_name = str(op.name())
            result["operations"].append(op_name)

            # Check for BeqsRequest
            if "Beqs" in op_name or "beqs" in op_name.lower():
                result["beqs_available"] = True
                print(f"     [FOUND] {op_name} <-- BEQS Request Type")
            else:
                print(f"     - {op_name}")

        if not result["beqs_available"]:
            print("\n[WARN] BeqsRequest not found in operations list")
            print("       Attempting direct creation...")

    except Exception as e:
        print(f"[ERROR] {e}")
        result["error"] = str(e)

    return result


def verify_beqs_request_structure(session: blpapi.Session) -> Dict[str, Any]:
    """Verify BeqsRequest can be created and inspect its structure."""
    print("\n" + "="*60)
    print("TEST 2: Verify BeqsRequest Structure")
    print("="*60)

    result = {
        "beqs_creatable": False,
        "parameters": [],
        "error": None,
    }

    try:
        service = open_service(session, "//blp/refdata")

        # Try to create BeqsRequest
        try:
            request = service.createRequest("BeqsRequest")
            result["beqs_creatable"] = True
            print("[OK] BeqsRequest created successfully")

            # Inspect request structure
            print("\nRequest Parameters:")
            print("-" * 40)

            element = request.asElement()
            for i in range(element.numElements()):
                elem = element.getElement(i)
                param_info = {
                    "name": str(elem.name()),
                    "type": str(elem.datatype()),
                    "is_array": elem.isArray(),
                }
                result["parameters"].append(param_info)

                type_str = f"[{param_info['type']}]"
                array_str = " (array)" if param_info["is_array"] else ""
                print(f"  - {param_info['name']:20} {type_str:15}{array_str}")

        except blpapi.InvalidArgumentException as e:
            print(f"[ERROR] BeqsRequest not available: {e}")
            result["error"] = str(e)

    except Exception as e:
        print(f"[ERROR] {e}")
        result["error"] = str(e)

    return result


def verify_beqs_global_screen(session: blpapi.Session, screen_name: str, screen_type: str) -> Dict[str, Any]:
    """Test running a BEQS screen and verify response structure."""
    print("\n" + "="*60)
    print(f"TEST 3: Run BEQS Screen '{screen_name}' ({screen_type})")
    print("="*60)

    result = {
        "screen_name": screen_name,
        "screen_type": screen_type,
        "success": False,
        "securities_count": 0,
        "sample_securities": [],
        "response_structure": {},
        "error": None,
    }

    try:
        service = open_service(session, "//blp/refdata")
        request = service.createRequest("BeqsRequest")

        # Set screen parameters
        request.set("screenName", screen_name)
        request.set("screenType", screen_type)

        print(f"Sending request...")
        print(f"  screenName: {screen_name}")
        print(f"  screenType: {screen_type}")

        session.sendRequest(request)

        # Process response
        done = False
        while not done:
            event = session.nextEvent(REQUEST_TIMEOUT_MS)
            event_type = event.eventType()

            if event_type == blpapi.Event.TIMEOUT:
                print("[TIMEOUT] Request timed out")
                result["error"] = "Request timeout"
                break

            for msg in event:
                msg_type = str(msg.messageType())
                print(f"\nMessage Type: {msg_type}")

                # Check for errors
                if msg.hasElement("responseError"):
                    error_elem = msg.getElement("responseError")
                    result["error"] = str(error_elem)
                    print(f"[ERROR] Response error: {error_elem}")
                    continue

                # Parse successful response
                msg_dict = msg.toPy()
                result["response_structure"] = _extract_structure(msg_dict)

                # Extract securities from response
                data = msg_dict.get("data", msg_dict)
                security_data = data.get("securityData", [])

                if isinstance(security_data, list):
                    for sec in security_data:
                        ticker = sec.get("security", "")
                        if ticker:
                            result["sample_securities"].append(ticker)
                            if len(result["sample_securities"]) <= 5:
                                print(f"  [SECURITY] {ticker}")

                result["securities_count"] = len(result["sample_securities"])

                if result["securities_count"] > 0:
                    result["success"] = True

            if event_type == blpapi.Event.RESPONSE:
                done = True

        print(f"\n[RESULT] Found {result['securities_count']} securities")

    except Exception as e:
        print(f"[ERROR] {e}")
        result["error"] = str(e)

    return result


def verify_reference_data_adr_fields(session: blpapi.Session) -> Dict[str, Any]:
    """Verify ADR-related fields work with reference data."""
    print("\n" + "="*60)
    print("TEST 4: Verify ADR Fields via Reference Data")
    print("="*60)

    result = {
        "success": False,
        "test_securities": ["TM US Equity", "SONY US Equity"],
        "fields_tested": [
            "SECURITY_TYP",
            "CNTRY_OF_RISK",
            "ADR_UNDL_TICKER",
            "ADR_SH_PER_ADR",
            "AVG_DAILY_VALUE_TRADED_20D",
        ],
        "results": [],
        "error": None,
    }

    try:
        service = open_service(session, "//blp/refdata")
        request = service.createRequest("ReferenceDataRequest")

        # Add securities
        securities_elem = request.getElement("securities")
        for sec in result["test_securities"]:
            securities_elem.appendValue(sec)

        # Add fields
        fields_elem = request.getElement("fields")
        for field in result["fields_tested"]:
            fields_elem.appendValue(field)

        print(f"Testing securities: {result['test_securities']}")
        print(f"Testing fields: {result['fields_tested']}")

        session.sendRequest(request)

        done = False
        while not done:
            event = session.nextEvent(REQUEST_TIMEOUT_MS)

            if event.eventType() == blpapi.Event.TIMEOUT:
                result["error"] = "Request timeout"
                break

            for msg in event:
                if msg.hasElement("responseError"):
                    result["error"] = str(msg.getElement("responseError"))
                    continue

                if msg.hasElement("securityData"):
                    sec_data = msg.getElement("securityData")

                    for i in range(sec_data.numValues()):
                        sec = sec_data.getValueAsElement(i)
                        ticker = sec.getElementAsString("security")

                        sec_result = {"security": ticker, "fields": {}}

                        if sec.hasElement("fieldData"):
                            field_data = sec.getElement("fieldData")
                            for j in range(field_data.numElements()):
                                field = field_data.getElement(j)
                                field_name = str(field.name())

                                try:
                                    if field.datatype() == blpapi.DataType.STRING:
                                        value = field.getValueAsString()
                                    elif field.datatype() == blpapi.DataType.FLOAT64:
                                        value = field.getValueAsFloat()
                                    elif field.datatype() == blpapi.DataType.INT32:
                                        value = field.getValueAsInteger()
                                    else:
                                        value = str(field)
                                except:
                                    value = str(field)

                                sec_result["fields"][field_name] = value

                        result["results"].append(sec_result)
                        print(f"\n{ticker}:")
                        for k, v in sec_result["fields"].items():
                            print(f"  {k}: {v}")

            if event.eventType() == blpapi.Event.RESPONSE:
                done = True

        result["success"] = len(result["results"]) > 0

    except Exception as e:
        print(f"[ERROR] {e}")
        result["error"] = str(e)

    return result


def _extract_structure(obj: Any, depth: int = 0) -> Dict[str, Any]:
    """Extract structure information from response object."""
    if depth > 3:
        return {"type": type(obj).__name__}

    if isinstance(obj, dict):
        return {
            "type": "dict",
            "keys": list(obj.keys())[:10],
            "sample": {k: _extract_structure(v, depth + 1) for k, v in list(obj.items())[:5]}
        }
    elif isinstance(obj, list):
        return {
            "type": "list",
            "length": len(obj),
            "sample": _extract_structure(obj[0], depth + 1) if obj else None
        }
    else:
        return {"type": type(obj).__name__}


# =============================================================================
# MAIN EXECUTION
# =============================================================================

def main():
    """Run all verification tests."""
    print("="*60)
    print("BLOOMBERG BEQS ENDPOINT VERIFICATION")
    print("="*60)
    print(f"Time: {datetime.now()}")
    print(f"Host: {BLOOMBERG_HOST}:{BLOOMBERG_PORT}")

    results = {}

    # Create session
    print("\nConnecting to Bloomberg...")
    try:
        session = create_session()
        print("[OK] Connected to Bloomberg Terminal")
    except Exception as e:
        print(f"[FATAL] Cannot connect to Bloomberg: {e}")
        print("\nMake sure Bloomberg Terminal is running and API is enabled.")
        sys.exit(1)

    try:
        # Test 1: Verify refdata service
        results["service"] = verify_refdata_service(session)

        # Test 2: Verify BeqsRequest structure
        results["beqs_structure"] = verify_beqs_request_structure(session)

        # Test 3: Run a test screen (if BeqsRequest available)
        if results["beqs_structure"].get("beqs_creatable"):
            for test_screen in TEST_SCREENS:
                key = f"screen_{test_screen['name']}"
                results[key] = verify_beqs_global_screen(
                    session,
                    test_screen["name"],
                    test_screen["type"]
                )
        else:
            print("\n[SKIP] Skipping screen test - BeqsRequest not available")

        # Test 4: Verify ADR fields work
        results["adr_fields"] = verify_reference_data_adr_fields(session)

    finally:
        session.stop()
        print("\n[OK] Session closed")

    # Summary
    print("\n" + "="*60)
    print("VERIFICATION SUMMARY")
    print("="*60)

    print(f"\n1. Service //blp/refdata: {'OK' if results['service']['available'] else 'FAILED'}")
    print(f"2. BeqsRequest available: {'YES' if results['beqs_structure']['beqs_creatable'] else 'NO'}")

    if results["beqs_structure"]["beqs_creatable"]:
        params = [p["name"] for p in results["beqs_structure"]["parameters"]]
        print(f"   Parameters: {', '.join(params)}")

    for test_screen in TEST_SCREENS:
        key = f"screen_{test_screen['name']}"
        if key in results:
            screen_result = results[key]
            status = 'OK' if screen_result['success'] else 'FAILED'
            count = screen_result['securities_count']
            print(f"3. Test screen '{test_screen['name']}': {status} ({count} securities)")

    print(f"4. ADR fields test: {'OK' if results['adr_fields']['success'] else 'FAILED'}")

    # Final recommendation
    print("\n" + "-"*60)
    if results["beqs_structure"]["beqs_creatable"]:
        print("RECOMMENDATION: BeqsRequest is available. Proceed with EQS integration.")
        print("Next steps:")
        print("  1. Create 'Japan ADR Universe' screen in Bloomberg EQS <GO>")
        print("  2. Implement BeqsRequest in bloomberg-mcp")
        print("  3. Test with private screen")
    else:
        print("RECOMMENDATION: BeqsRequest NOT available on this connection.")
        print("Alternatives:")
        print("  1. Use ReferenceDataRequest + client-side filtering")
        print("  2. Check Bloomberg Terminal API settings")
        print("  3. Contact Bloomberg support for BEQS access")

    return results


if __name__ == "__main__":
    results = main()
