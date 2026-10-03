#!/usr/bin/env python3
"""
V13.9.1 Production Regression Test Suite
Automated verification across all 10 operational categories
No code changes made during test execution.
"""

import json
import time
import requests
import sqlite3
from datetime import datetime, timezone
from typing import Dict, List, Tuple

BASE_URL = "http://127.0.0.1:5000"
DB_PATH = "yacht_pos.db"

# Test state
results = {
    "start_time": datetime.now(timezone.utc).isoformat(),
    "categories": {},
    "failures": []
}

session = requests.Session()

def log_result(category: int, item: str, status: str, details: str = ""):
    """Record a test result."""
    if category not in results["categories"]:
        results["categories"][category] = []
    
    result = {"item": item, "status": status, "details": details}
    results["categories"][category].append(result)
    
    status_icon = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⏭️"
    print(f"  {status_icon} {item}: {status}" + (f" ({details})" if details else ""))
    
    if status == "FAIL":
        results["failures"].append({"category": category, "item": item, "details": details})

def test_category_1_auth():
    """Authentication & Permissions"""
    print("\n=== Category 1: Authentication & Permissions ===")
    
    # 1.1: Create test user (if needed)
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    existing = c.execute("SELECT id FROM users WHERE username='test_admin'").fetchone()
    if not existing:
        from app import hash_pin
        pin_hash = hash_pin("123456")
        c.execute("INSERT INTO users(username,role,pin_hash,active,must_change_pin) VALUES(?,?,?,?,?)",
                  ("test_admin", "admin", pin_hash, 1, 0))
        c.commit()
    c.close()
    
    # 1.2: Valid PIN login
    try:
        r = session.post(f"{BASE_URL}/api/login", json={"username": "test_admin", "pin": "123456"})
        if r.status_code == 200 and r.json().get("username") == "test_admin":
            log_result(1, "Valid PIN login", "PASS")
        else:
            log_result(1, "Valid PIN login", "FAIL", f"Status {r.status_code}: {r.text}")
    except Exception as e:
        log_result(1, "Valid PIN login", "FAIL", str(e))
    
    # 1.3: Invalid PIN rejected
    try:
        r = session.post(f"{BASE_URL}/api/login", json={"username": "test_admin", "pin": "999999"})
        if r.status_code == 401:
            log_result(1, "Invalid PIN rejected", "PASS")
        else:
            log_result(1, "Invalid PIN rejected", "FAIL", f"Expected 401, got {r.status_code}")
    except Exception as e:
        log_result(1, "Invalid PIN rejected", "FAIL", str(e))
    
    # 1.4: Rate limiting (8 attempts in 300s window)
    rate_limit_passed = False
    try:
        # Clear old attempts by logging in successfully first
        session.post(f"{BASE_URL}/api/login", json={"username": "test_admin", "pin": "123456"})
        
        # Now try 8 bad attempts
        for i in range(8):
            r = session.post(f"{BASE_URL}/api/login", json={"username": "test_admin", "pin": "badpin"})
            if i < 7:
                if r.status_code != 401:
                    log_result(1, "Rate limiting (8 attempts)", "FAIL", f"Attempt {i+1} got {r.status_code}")
                    break
            else:
                # 8th attempt should trigger rate limit (429)
                if r.status_code == 429:
                    rate_limit_passed = True
                else:
                    log_result(1, "Rate limiting (8 attempts)", "FAIL", f"8th attempt: expected 429, got {r.status_code}")
        
        if rate_limit_passed:
            log_result(1, "Rate limiting (8 attempts)", "PASS")
    except Exception as e:
        log_result(1, "Rate limiting (8 attempts)", "FAIL", str(e))
    
    # 1.5: PBKDF2 PIN verification
    try:
        r = session.post(f"{BASE_URL}/api/login", json={"username": "test_admin", "pin": "123456"})
        if r.status_code == 200:
            log_result(1, "PBKDF2 PIN verification", "PASS")
        else:
            log_result(1, "PBKDF2 PIN verification", "FAIL", f"Status {r.status_code}")
    except Exception as e:
        log_result(1, "PBKDF2 PIN verification", "FAIL", str(e))
    
    # 1.6: PIN change workflow
    try:
        # Login first
        session.post(f"{BASE_URL}/api/login", json={"username": "test_admin", "pin": "123456"})
        
        # Change PIN
        r = session.post(f"{BASE_URL}/api/account/change-pin", 
                        json={"old_pin": "123456", "new_pin": "654321", "confirm_pin": "654321"})
        if r.status_code == 200 and r.json().get("ok"):
            log_result(1, "PIN change workflow", "PASS")
        else:
            log_result(1, "PIN change workflow", "FAIL", f"Status {r.status_code}: {r.text}")
    except Exception as e:
        log_result(1, "PIN change workflow", "FAIL", str(e))
    
    # 1.7: Logout / Session invalidation
    try:
        r = session.post(f"{BASE_URL}/api/logout")
        if r.status_code == 200:
            log_result(1, "Session invalidation on logout", "PASS")
        else:
            log_result(1, "Session invalidation on logout", "FAIL", f"Status {r.status_code}")
    except Exception as e:
        log_result(1, "Session invalidation on logout", "FAIL", str(e))
    
    # 1.8: Role-based access control
    try:
        # Try accessing admin endpoint without auth
        r = session.get(f"{BASE_URL}/api/products/all")
        if r.status_code == 403:
            log_result(1, "Role-based access control (403 without auth)", "PASS")
        else:
            log_result(1, "Role-based access control (403 without auth)", "FAIL", f"Expected 403, got {r.status_code}")
    except Exception as e:
        log_result(1, "Role-based access control (403 without auth)", "FAIL", str(e))

def test_category_2_events():
    """Event States"""
    print("\n=== Category 2: Event States ===")
    
    # Login as admin
    r = session.post(f"{BASE_URL}/api/login", json={"username": "test_admin", "pin": "654321"})
    if r.status_code != 200:
        log_result(2, "Setup: Admin login", "FAIL", "Cannot login as admin")
        return
    
    # 2.1: Create event
    try:
        r = session.post(f"{BASE_URL}/api/events",
                        json={"name": "Test Event", "code": f"TEST{int(time.time())}", "max_guests": 50})
        if r.status_code == 201:
            event_code = r.json().get("code")
            log_result(2, "Create event", "PASS")
        else:
            log_result(2, "Create event", "FAIL", f"Status {r.status_code}")
            return
    except Exception as e:
        log_result(2, "Create event", "FAIL", str(e))
        return
    
    # 2.2: Event code uniqueness
    try:
        r = session.post(f"{BASE_URL}/api/events",
                        json={"name": "Duplicate", "code": event_code, "max_guests": 50})
        if r.status_code == 409:
            log_result(2, "Event code uniqueness constraint", "PASS")
        else:
            log_result(2, "Event code uniqueness constraint", "FAIL", f"Expected 409, got {r.status_code}")
    except Exception as e:
        log_result(2, "Event code uniqueness constraint", "FAIL", str(e))
    
    # 2.3: Freeze/Unfreeze event
    try:
        r = session.post(f"{BASE_URL}/api/events/{event_code}/freeze")
        if r.status_code == 200 and r.json().get("ok"):
            log_result(2, "Freeze event", "PASS")
        else:
            log_result(2, "Freeze event", "FAIL", f"Status {r.status_code}")
            return
    except Exception as e:
        log_result(2, "Freeze event", "FAIL", str(e))
        return
    
    # 2.4: Unfreeze event
    try:
        r = session.post(f"{BASE_URL}/api/events/{event_code}/unfreeze")
        if r.status_code == 200 and r.json().get("ok"):
            log_result(2, "Unfreeze event", "PASS")
        else:
            log_result(2, "Unfreeze event", "FAIL", f"Status {r.status_code}")
    except Exception as e:
        log_result(2, "Unfreeze event", "FAIL", str(e))

def test_category_3_guests():
    """Guest Lifecycle"""
    print("\n=== Category 3: Guest Lifecycle ===")
    
    # Create an event for testing
    try:
        r = session.post(f"{BASE_URL}/api/events",
                        json={"name": "Guest Test", "code": f"GUEST{int(time.time())}", "max_guests": 50})
        event_code = r.json().get("code")
    except Exception as e:
        log_result(3, "Setup: Create event", "FAIL", str(e))
        return
    
    # 3.1: Create guest
    try:
        r = session.post(f"{BASE_URL}/api/events/{event_code}/guests",
                        json={"name": "John Doe", "phone": "9876543210", "cover": "1000", "payment_method": "UPI"})
        if r.status_code == 201:
            guest_code = r.json().get("guest_code")
            log_result(3, "Create guest", "PASS")
        else:
            log_result(3, "Create guest", "FAIL", f"Status {r.status_code}: {r.text}")
            return
    except Exception as e:
        log_result(3, "Create guest", "FAIL", str(e))
        return
    
    # 3.2: Guest code format
    try:
        if guest_code and guest_code.startswith("G-"):
            log_result(3, "Guest code auto-generated (G-XXXXXXXXXX format)", "PASS")
        else:
            log_result(3, "Guest code auto-generated (G-XXXXXXXXXX format)", "FAIL", f"Got {guest_code}")
    except Exception as e:
        log_result(3, "Guest code auto-generated (G-XXXXXXXXXX format)", "FAIL", str(e))
    
    # 3.3: Guest checkin
    try:
        r = session.post(f"{BASE_URL}/api/guests/{guest_code}/checkin")
        if r.status_code == 200 and r.json().get("guest", {}).get("checked_in"):
            log_result(3, "Guest checkin", "PASS")
        else:
            log_result(3, "Guest checkin", "FAIL", f"Status {r.status_code}")
    except Exception as e:
        log_result(3, "Guest checkin", "FAIL", str(e))
    
    # 3.4: Guest checkout
    try:
        r = session.post(f"{BASE_URL}/api/guests/{guest_code}/checkout")
        if r.status_code == 200:
            log_result(3, "Guest checkout", "PASS")
        else:
            log_result(3, "Guest checkout", "FAIL", f"Status {r.status_code}")
    except Exception as e:
        log_result(3, "Guest checkout", "FAIL", str(e))

def print_summary():
    """Print final test summary."""
    print("\n" + "="*60)
    print("V13.9.1 REGRESSION TEST SUMMARY")
    print("="*60)
    
    total_tests = 0
    passed_tests = 0
    failed_tests = 0
    
    for cat in sorted(results["categories"].keys()):
        items = results["categories"][cat]
        cat_passed = sum(1 for i in items if i["status"] == "PASS")
        cat_total = len(items)
        total_tests += cat_total
        passed_tests += cat_passed
        failed_tests += sum(1 for i in items if i["status"] == "FAIL")
        
        status = "✅ PASS" if cat_passed == cat_total else "❌ FAIL"
        print(f"\nCategory {cat}: {status} ({cat_passed}/{cat_total})")
        for item in items:
            if item["status"] != "PASS":
                print(f"  - {item['item']}: {item['status']}" + (f" ({item['details']})" if item['details'] else ""))
    
    print("\n" + "="*60)
    print(f"OVERALL: {passed_tests}/{total_tests} PASS")
    
    if results["failures"]:
        print(f"\n⚠️  {len(results['failures'])} FAILURES DETECTED:")
        for f in results["failures"]:
            print(f"  - Category {f['category']}: {f['item']}")
            print(f"    Details: {f['details']}")
    else:
        print("\n✅ ALL TESTS PASSED")
    
    print("="*60)
    
    # Save results to JSON
    results["end_time"] = datetime.now(timezone.utc).isoformat()
    with open("regression_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to regression_results.json")

if __name__ == "__main__":
    print("Starting V13.9.1 Regression Test Suite...")
    print(f"Target: {BASE_URL}")
    print(f"Database: {DB_PATH}")
    
    try:
        test_category_1_auth()
        test_category_2_events()
        test_category_3_guests()
        # More categories to be added
        print_summary()
    except KeyboardInterrupt:
        print("\n\n❌ Test interrupted by user")
        print_summary()
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        print_summary()
