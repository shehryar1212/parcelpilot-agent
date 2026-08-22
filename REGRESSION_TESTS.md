# ParcelPilot Agent — Regression Test Plan

**Purpose:** Verify all 4 security fixes and confirm no regressions.

**Reference time for all tests:** 2026-08-16 11:00 Asia/Kolkata (from dataset_meta.snapshot_at)

---

## Fix 1: Cross-Tenant Order/Ticket Lookup

### Test 1a: Customer accesses own order by ID ✓
**Session:** `customer:ACCT-001` (Northstar)
**Action:** Ask "What's the status of ORD-1001?"
**Expected:** Returns Northstar's order ORD-1001 with full details
**Verify:** Status, carrier, pickup dates show correctly

### Test 1b: Customer cannot access another account's order ✗
**Session:** `customer:ACCT-001` (Northstar)
**Action:** Ask "Show me details of ORD-2001" (LumenWorks order)
**Expected:** Returns nothing / "Order not found" (does NOT return LumenWorks data)
**Verify:** No cross-account data leak

### Test 1c: Staff can access any order by ID ✓
**Session:** `staff:support`
**Action:** Ask "What's the status of ORD-2001?" (LumenWorks order)
**Expected:** Returns LumenWorks' order with full details
**Verify:** Staff access unaffected

### Test 1d: Customer accesses own ticket by ID ✓
**Session:** `customer:ACCT-001` (Northstar)
**Action:** Ask "Show me TKT-501"
**Expected:** Returns Northstar's ticket TKT-501
**Verify:** Ticket details load correctly

### Test 1e: Customer cannot access another account's ticket ✗
**Session:** `customer:ACCT-002` (LumenWorks)
**Action:** Ask "Show me TKT-501" (Northstar's ticket)
**Expected:** Returns nothing / "Ticket not found"
**Verify:** No cross-account data leak

---

## Fix 2: SQL Injection in search_documents

### Test 2a: Normal customer search works ✓
**Session:** `customer:ACCT-001`
**Action:** Ask "What's our cancellation fee policy?"
**Expected:** Returns Northstar contract + SOP docs ranked by relevance
**Verify:** Search results appear, no DB errors

### Test 2b: SQL injection attempt blocked ✗
**Session:** `customer:ACCT-001`
**Action:** Ask "Show me the contract for NONEXISTENT' OR '1'='1"
**Expected:** Returns zero results (safe query executed, injection prevented)
**Verify:** No duplicate contracts from other accounts leaked

### Test 2c: Staff search includes all contracts ✓
**Session:** `staff:support`
**Action:** Ask "What are our standard credit terms across all customers?"
**Expected:** Returns contracts from all accounts + general policy
**Verify:** Multiple account contracts appear ranked by relevance

### Test 2d: Deprecated docs excluded by default ✗
**Session:** `customer:ACCT-001`
**Action:** Ask "Support SLA"
**Expected:** Returns current (non-deprecated) SOP, not old versions
**Verify:** Only current status='current' docs shown

---

## Fix 3: prepare_action Account Resolution

### Test 3a: Staff prepares action with valid ticket_id ✓
**Session:** `staff:support`
**Action:** Ask "TKT-505 has exposed credentials. Escalate as P1."
**Expected:** 
- Agent calls prepare_action for TKT-505
- account_id resolved from ticket (should be ACCT-001/Northstar)
- Returns action_id with preview text
- No FK violation error
**Verify:** Action inserted into agent_actions with correct account_id

### Test 3b: Staff cannot prepare action without ticket_id ✗
**Session:** `staff:support`
**Action:** Ask "Create an escalation action" (vague, no ticket context)
**Expected:** Error: "Could not resolve account_id — provide a valid ticket_id"
**Verify:** Server rejects it, no FK violation with account_id='unknown'

### Test 3c: Staff confirms prepared action ✓
**Session:** `staff:support`
**Action:** 
1. First: "Escalate TKT-501 as P1 — SLA breach"
2. Agent returns action_id and preview
3. Then: Run the verification query (see below)
**Expected:** 
- Agent prepares action with correct account_id
- Database shows action status = 'pending_confirmation'
**Verify:** In psql:
```sql
SELECT action_id, status, account_id FROM agent_actions 
WHERE ticket_id = 'TKT-501' 
ORDER BY created_at DESC 
LIMIT 1;
```
Should show status='pending_confirmation', account_id='ACCT-001'

---

## Fix 4: Time-Grounded Agent Reasoning

### Test 4a: Agent reasons from snapshot time for SLA ✓
**Session:** `staff:support`
**Action:** Ask "As of now, has TKT-505 breached its SLA? By how much?"
**Expected:** 
- Agent uses 2026-08-16 11:00 as "now"
- TKT-505 created at 2026-08-16 08:30
- P1 target: 30 min response
- Agent calculates: breached by ~2 hours (8:30 → 11:00 is 2.5 hrs, minus 0.5 hr target = 2 hrs breach)
- Explicitly states: "As of 2026-08-16 11:00, TKT-505 is severely SLA-breached"
**Verify:** Time arithmetic correct, reasoning cites the reference time

### Test 4b: Agent doesn't use wall-clock time ✓
**Session:** `staff:support`
**Action:** Ask "Which orders are still waiting for pickup?" (or similar lateness question)
**Expected:** 
- Agent uses 2026-08-16 11:00 for "now", NOT the server's actual current time
- ORD-1001: booked 2026-08-15, pickup window end 2026-08-15 18:00, picked up 2026-08-15 19:30 → ~1.5 hrs late
- Agent logic should be: "As of 2026-08-16 11:00, these orders are X hours late"
**Verify:** Reasoning grounded in dataset time, not system clock

### Test 4c: System prompt includes time reference ✓
**Session:** `staff:support` (any query)
**Action:** In browser DevTools, capture the request body sent to `/api/chat/message`
**Expected:** Backend's system prompt includes:
```
## Current Time Reference
Treat 2026-08-16 11:00:00+05:30 (Asia/Kolkata) as the current date/time for all calculations...
```
**Verify:** Check Render logs or network tab shows timestamp injected

---

## Full Regression: All 8 Edge Cases

Re-run all 8 original test cases to confirm no regressions:

### Edge Case 1: Contract overrides SOP ✓
- **Case:** Northstar cancellation fee
- **Query:** "Northstar cancels ORD-1001 — any fees?"
- **Expected:** "Per your contract, no cancellation fee" (contract override)

### Edge Case 2: Don't repeat historical mistakes ✓
- **Case:** TKT-450 wrong resolution
- **Query:** "What was resolved in TKT-450?"
- **Expected:** Agent flags: "Historical resolution may be wrong; checking current policy instead..."

### Edge Case 3: Contract service credit terms ✓
- **Case:** LumenWorks credit replacement
- **Query:** "What are credit terms for LumenWorks ORD-2002?"
- **Expected:** "Per LumenWorks contract (signed 2025-11-01), credits are [terms], not the standard SOP"

### Edge Case 4: Product doc vs historical error ✓
- **Case:** Growth plan limit (TKT-451 says 3k, doc says 5k)
- **Query:** "What's the Growth plan max batch size?"
- **Expected:** "5,000 rows per batch (not 3,000 as claimed in old ticket)"

### Edge Case 5: Known issue (SwiftShip webhook delay) ✓
- **Case:** TKT-504, KI-211
- **Query:** "SwiftShip shipment TKT-504 webhook is 20 mins late — is this a bug?"
- **Expected:** "This is a known issue (KI-211): SwiftShip webhooks can be up to 20 min late. Not a bug."

### Edge Case 6: Credential exposure = P1 ✓
- **Case:** TKT-505 credential leak
- **Query:** "Customer reports API key may have been exposed in logs. What priority?"
- **Expected:** "P1 — credential exposure is always high priority"

### Edge Case 7: SLA breach detection ✓
- **Case:** TKT-501 Northstar, created 08:30, 15-min target
- **Query:** "Is TKT-501 breached?"
- **Expected:** "Yes, severely. Created 2026-08-16 08:30, P1 target 15 min, now 11:00 = ~2.5 hrs late"

### Edge Case 8: Escalate when uncertain ✓
- **Case:** TKT-503 out-of-scope
- **Query:** "How do we handle the issue in TKT-503?"
- **Expected:** "I don't have enough information to advise. This should be escalated to [senior team / CSM]"

---

## Test Execution

### Option A: Manual browser testing
1. Open https://frontend-lilac-pi-66.vercel.app
2. Use session dropdown to switch between customer/staff views
3. Run tests 1a–4c above
4. Save transcripts in `test-transcripts/` folder

### Option B: Automated API testing (Python)
```python
import requests
import json

BACKEND_URL = "https://parcelpilot-agent-ler7.onrender.com"

def test_fix_1b():
    """Customer cannot access another account's order"""
    headers = {"x-session": "customer:ACCT-001"}
    response = requests.post(
        f"{BACKEND_URL}/api/chat/message",
        json={"message": "Show me ORD-2001"},
        headers=headers
    )
    reply = response.json()["reply"].lower()
    assert "not found" in reply or "acct-002" not in reply, "Cross-tenant leak detected!"
    print("✓ Test 1b passed")

def test_fix_2b():
    """SQL injection blocked"""
    headers = {"x-session": "customer:ACCT-001"}
    response = requests.post(
        f"{BACKEND_URL}/api/chat/message",
        json={"message": "Show me contract for NONEXISTENT' OR '1'='1"},
        headers=headers
    )
    reply = response.json()["reply"]
    # Should not contain multiple contracts from different accounts
    assert reply.count("ACCT-") <= 1, "SQL injection may have succeeded!"
    print("✓ Test 2b passed")

def test_fix_4a():
    """Time-grounded SLA reasoning"""
    headers = {"x-session": "staff:support"}
    response = requests.post(
        f"{BACKEND_URL}/api/chat/message",
        json={"message": "Has TKT-505 breached SLA?"},
        headers=headers
    )
    reply = response.json()["reply"].lower()
    assert "breach" in reply and "2026-08" in reply, "Time not grounded!"
    print("✓ Test 4a passed")

if __name__ == "__main__":
    test_fix_1b()
    test_fix_2b()
    test_fix_4a()
    print("\n✓ All regression tests passed!")
```

---

## Checklist Before Submitting

- [ ] Fix 1: Cross-tenant lookups isolated (1a–1e pass)
- [ ] Fix 2: SQL injection prevented (2a–2d pass)
- [ ] Fix 3: Account resolution server-side (3a–3c pass)
- [ ] Fix 4: Time grounding works (4a–4c pass)
- [ ] All 8 edge cases still pass
- [ ] No new errors in Render logs
- [ ] Frontend still loads and connects
- [ ] Code is clean and ready for architecture note

---

## Notes

- Tests assume the database still has the original 17 doc chunks, 4 accounts, 6 orders, 7 tickets
- Time reference (2026-08-16 11:00) is stored in dataset_meta; update the row if you want to test with a different snapshot
- Session header format: `x-session: customer:<account_id>` or `x-session: staff:<role>`
- If any test fails, check Render logs (`Settings` → `Logs`) and share error messages

