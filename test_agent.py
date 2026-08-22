#!/usr/bin/env python3
"""
Automated test script for ParcelPilot Agent.
Tests all 8 dataset edge cases + core functionality.
"""

import requests
import json
from typing import Tuple

BACKEND_URL = "https://parcelpilot-agent-ler7.onrender.com"
# BACKEND_URL = "http://localhost:8000"  # For local testing

def test_query(message: str, session: str, description: str = "") -> Tuple[str, list]:
    """Send a query to the agent and return (reply, tool_calls)."""
    headers = {"x-session": session}
    try:
        response = requests.post(
            f"{BACKEND_URL}/api/chat/message",
            json={"message": message},
            headers=headers,
            timeout=30
        )
        if response.status_code == 200:
            data = response.json()
            return data["reply"], data.get("tool_calls", [])
        else:
            return f"[ERROR {response.status_code}]", []
    except Exception as e:
        return f"[EXCEPTION: {e}]", []

def check_response(reply: str, keywords: list, description: str) -> bool:
    """Check if response contains any of the keywords."""
    found = any(kw.lower() in reply.lower() for kw in keywords)
    status = "✓ PASS" if found else "✗ FAIL"
    print(f"{status}: {description}")
    if not found:
        print(f"   Expected keywords: {keywords}")
        print(f"   Got: {reply[:150]}...")
    return found

# ============================================================================
# EDGE CASE TESTS (8 from dataset)
# ============================================================================

print("\n" + "="*70)
print("EDGE CASE TESTS (8 from dataset)")
print("="*70)

tests_passed = 0
tests_total = 0

# Test 1: Contract overrides SOP
tests_total += 1
reply, _ = test_query(
    "Northstar cancels ORD-1001 — any cancellation fee?",
    "customer:ACCT-001"
)
if check_response(reply, ["no cancellation fee", "contract", "waive"], "Test 1: Contract overrides SOP"):
    tests_passed += 1

# Test 2: Don't repeat historical mistakes
tests_total += 1
reply, _ = test_query(
    "Customer reports SwiftShip connectivity issues after 6 PM. Should we refund like we did before?",
    "staff:support"
)
if check_response(reply, ["known", "expected", "not a bug", "policy", "no refund"], "Test 2: Historical mistakes"):
    tests_passed += 1

# Test 3: Contract service credit terms
tests_total += 1
reply, _ = test_query(
    "LumenWorks wants a credit for ORD-2002 — what are the terms?",
    "staff:support"
)
if check_response(reply, ["LumenWorks", "contract", "credit"], "Test 3: Contract credit terms"):
    tests_passed += 1

# Test 4: Product doc vs historical error
tests_total += 1
reply, _ = test_query(
    "According to our product docs, what's the max batch size for the Growth plan?",
    "customer:ACCT-003"
)
if check_response(reply, ["5000", "5,000", "growth", "batch"], "Test 4: Product doc vs historical"):
    tests_passed += 1

# Test 5: Known issue (SwiftShip webhook)
tests_total += 1
reply, _ = test_query(
    "SwiftShip webhook is 20 minutes late — is this a bug?",
    "staff:support"
)
if check_response(reply, ["known", "not a bug", "20 min"], "Test 5: Known issues"):
    tests_passed += 1

# Test 6: Credential exposure = P1
tests_total += 1
reply, _ = test_query(
    "API key may have been exposed — what priority?",
    "staff:support"
)
if check_response(reply, ["P1", "credential", "high priority"], "Test 6: Credential exposure = P1"):
    tests_passed += 1

# Test 7: SLA breach detection
tests_total += 1
reply, _ = test_query(
    "Is TKT-501 breached?",
    "staff:support"
)
if check_response(reply, ["breach", "SLA", "P1"], "Test 7: SLA breach detection"):
    tests_passed += 1

# Test 8: Escalate when uncertain
tests_total += 1
reply, _ = test_query(
    "What should we do about TKT-503?",
    "staff:support"
)
if check_response(reply, ["escalate", "uncertain", "not sure", "don't know"], "Test 8: Escalate when uncertain"):
    tests_passed += 1

# ============================================================================
# SECURITY TESTS
# ============================================================================

print("\n" + "="*70)
print("SECURITY TESTS")
print("="*70)

# Test: Customer can't see other customer's data
tests_total += 1
reply, _ = test_query(
    "Show me ORD-2001 details",  # LumenWorks order
    "customer:ACCT-001"  # Northstar session
)
if check_response(reply, ["not found", "not available", "don't have", "access", "unable"], "Security: Cross-tenant isolation"):
    tests_passed += 1

# Test: Staff can see all customer data
tests_total += 1
reply, _ = test_query(
    "Get details for order ORD-1001",
    "staff:support"
)
if check_response(reply, ["ORD-1001", "order", "status"], "Security: Staff can see all data"):
    tests_passed += 1

# Test: Customer can see own data
tests_total += 1
reply, _ = test_query(
    "What's my order ORD-1001 status?",
    "customer:ACCT-001"
)
if check_response(reply, ["ORD-1001", "status"], "Security: Customer sees own data"):
    tests_passed += 1

# ============================================================================
# TOOL USAGE TESTS
# ============================================================================

print("\n" + "="*70)
print("TOOL USAGE TESTS")
print("="*70)

# Test: Agent uses search_documents
tests_total += 1
reply, tools = test_query(
    "What's our cancellation policy?",
    "customer:ACCT-001"
)
has_search = any(t["name"] == "search_documents" for t in tools)
status = "✓ PASS" if has_search else "✗ FAIL"
print(f"{status}: Agent uses search_documents tool")
if has_search:
    tests_passed += 1

# Test: Agent uses query_structured_data
tests_total += 1
reply, tools = test_query(
    "Show me my tickets",
    "customer:ACCT-001"
)
has_query = any(t["name"] == "query_structured_data" for t in tools)
status = "✓ PASS" if has_query else "✗ FAIL"
print(f"{status}: Agent uses query_structured_data tool")
if has_query:
    tests_passed += 1

# ============================================================================
# SUMMARY
# ============================================================================

print("\n" + "="*70)
print(f"SUMMARY: {tests_passed}/{tests_total} tests passed")
print("="*70)

if tests_passed == tests_total:
    print("✓ All tests passed!")
else:
    print(f"✗ {tests_total - tests_passed} test(s) failed")
    print("\nNote: Some failures may be due to model variation or context limits.")
    print("Check individual responses above for details.")
