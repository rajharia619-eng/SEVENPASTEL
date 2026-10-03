# V13.9.1 Production Regression Test Plan

**Build:** V13.9.1 (Known-Good)  
**Date Started:** 2026-10-03  
**Test Scope:** Full operational verification across all critical systems

---

## Test Categories

### 1. Authentication & Permissions
- [ ] User login with valid PIN (6-12 digits)
- [ ] PIN login rate limiting (max 8 attempts per 5 minutes)
- [ ] Legacy SHA-256 PIN migration forces must_change_pin=1 on next login
- [ ] PBKDF2 PIN verification succeeds for modern hashes
- [ ] PIN change workflow (old PIN → new PIN → confirm)
- [ ] Session invalidation on logout
- [ ] Role-based access control: admin > manager > bartender > host
- [ ] Requests without valid role return 403 authorization error
- [ ] must_change_pin flag blocks all routes except /api/account/change-pin

**Status:** ⏳ Pending

---

### 2. Event States
- [ ] Create event with code, name, max_guests, default_cover
- [ ] Event code uniqueness constraint enforced
- [ ] Event status transitions: OPEN → CLOSED (one-way)
- [ ] Event frozen flag prevents config changes
- [ ] Freeze event (frozen=1, status unchanged)
- [ ] Unfreeze event (frozen=0, status must be OPEN)
- [ ] Reopen event (status CLOSED → OPEN, frozen reset to 0)
- [ ] Guest capacity max enforced (capacity check on guest add)
- [ ] Closed events are read-only (all mutations rejected)

**Status:** ⏳ Pending

---

### 3. Guest Lifecycle
- [ ] Create guest with name, phone, cover amount, payment method
- [ ] Guest code auto-generated (G-XXXXXXXXXX format, unique per event)
- [ ] Initial wallet created with cover balance
- [ ] Initial LOAD ledger entry recorded
- [ ] Initial COVER payment recorded as SETTLED
- [ ] Bulk import guests from CSV/XLSX (max 1000 per import)
- [ ] Guest checkin updates checkin_status=CHECKED_IN, checked_in_at=now()
- [ ] Guest checkout updates checkin_status=CHECKED_OUT, checked_out_at=now()
- [ ] Guest suspend (status=SUSPENDED, reason recorded)
- [ ] Guest reactivate (status=ACTIVE, checkin reset to NOT_CHECKED_IN)
- [ ] Update guest name/phone (admin only, event must be OPEN)
- [ ] Update guest cover (delta applied as LOAD or REFUND)

**Status:** ⏳ Pending

---

### 4. Cover/Wallet Accounting
- [ ] Guest balance = sum of LOAD amounts - sum of (SALE + REFUND) amounts
- [ ] Topup adds to balance and loaded_paise (LOAD ledger entry)
- [ ] Sale deducts from balance (SALE ledger entry)
- [ ] Void reversal restores deducted amount (VOID_REVERSAL ledger entry)
- [ ] Refund (e.g., cover correction) updates balance (REFUND ledger entry)
- [ ] Razorpay topup order creates PENDING payment
- [ ] Razorpay verify settles payment and adds wallet LOAD
- [ ] Razorpay webhook (payment.captured) settles and adds LOAD
- [ ] Wallet control identity: (LOAD - REFUND) - SALE + VOID_REVERSAL = outstanding balances
- [ ] Negative balance prevention on sale (insufficient_guest_balance error)

**Status:** ⏳ Pending

---

### 5. Final Close
- [ ] Close checks identify: pending payments, uncounted inventory, wallet/payment gaps, failed payments, checked-out guests
- [ ] At least one check must fail to block close
- [ ] Close fails with descriptive error listing failed checks and values
- [ ] Close succeeds only when all checks pass
- [ ] On successful close: status=CLOSED, frozen=1, closed_at=now()
- [ ] Closed events reject all mutations (read-only confirmed)

**Status:** ⏳ Pending

---

### 6. Offline Queue
- [ ] Order created with idempotency_key
- [ ] Duplicate idempotency_key returns existing order (200, duplicate=true)
- [ ] Order snapshot captures price_paise and recipe at order time
- [ ] Stale snapshot (menu price or recipe changed) rejects order
- [ ] Order source defaults to ONLINE, can be set to OFFLINE
- [ ] Offline order accepted when guest checked_in and sufficient balance

**Status:** ⏳ Pending

---

### 7. Inventory Isolation
- [ ] event_inventory_state created per event per ingredient
- [ ] Opening stock set per event (immutable after activity)
- [ ] Opening stock locked after SALE_CONSUMPTION/WASTAGE/ADJUSTMENT exists
- [ ] Inventory consumption deducted from event_inventory_state.current_ml
- [ ] Inventory ledger records OPENING, SALE_CONSUMPTION, VOID_RESTORE, WASTAGE, ADJUSTMENT
- [ ] Void order restores inventory (VOID_RESTORE ledger entry)
- [ ] Event A inventory isolated from Event B
- [ ] Closing inventory count captures theoretical vs. physical variance
- [ ] Wastage logged with reason and approved_by

**Status:** ⏳ Pending

---

### 8. Audit Verification
- [ ] Audit log records every mutation: guest created, sale posted, cover adjusted, etc.
- [ ] Audit entries chained: prev_hash → current row_hash → next prev_hash
- [ ] Audit verify endpoint validates chain integrity (SHA-256)
- [ ] Tampered audit log detected by chain break
- [ ] All events in scope, NULL event_id allowed for system actions (user creation, etc.)

**Status:** ⏳ Pending

---

### 9. Backup
- [ ] Database file (yacht_pos.db) can be copied while Flask is running (WAL mode)
- [ ] Backup file is valid SQLite (can be opened with sqlite3)
- [ ] All tables present: events, guests, wallets, orders, payments, inventory_items, recipes, etc.
- [ ] No data loss observed in backup (row counts match)

**Status:** ⏳ Pending

---

### 10. Restore
- [ ] Backup file can be restored by replacing yacht_pos.db
- [ ] Restored database schema is correct (PRAGMA table_info matches)
- [ ] Restored data is readable (queries execute without error)
- [ ] Event state, guest balances, orders, audit log all restored
- [ ] Application boots without migration errors after restore

**Status:** ⏳ Pending

---

## Test Results Summary

| Category | Status | Notes |
|----------|--------|-------|
| 1. Authentication & Permissions | ⏳ | |
| 2. Event States | ⏳ | |
| 3. Guest Lifecycle | ⏳ | |
| 4. Cover/Wallet Accounting | ⏳ | |
| 5. Final Close | ⏳ | |
| 6. Offline Queue | ⏳ | |
| 7. Inventory Isolation | ⏳ | |
| 8. Audit Verification | ⏳ | |
| 9. Backup | ⏳ | |
| 10. Restore | ⏳ | |

**Overall Status:** ⏳ Pending

---

## Environment
- **App:** Flask + SQLite3 (WAL mode, PRAGMA foreign_keys=ON)
- **Python:** 3.13+
- **Database:** yacht_pos.db (auto-created on first run)
- **Secret Key:** YACHT_POS_SECRET (set for production)

## Failure Handling
**Policy:** No code changes during test. If any test case fails:
1. Document the failure in this file
2. Note the exact error, stack trace, and reproduction steps
3. Create a GitHub issue with the label `regression-v13.9.1`
4. Stop further testing until root cause is analyzed

## Sign-Off
Once all 10 categories pass, mark overall status as ✅ PASS and merge this to main.

---

**Test Date:** [To be filled]  
**Tester:** [To be filled]  
**Build Verified:** V13.9.1  
