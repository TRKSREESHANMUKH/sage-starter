# SAGE — Owner's Quick Reference & Presentation Checklist

> **Mandatory Scientific Framing Statement:**  
> *"SAGE performs controlled synthetic causal-attribution evaluation under an expert-defined causal model; it does not claim to prove real-world causality."*

---

## 1. Quick Start Commands (Terminal Setup)

```bash
# 1. Navigate to project root and activate virtual environment
cd /Users/asl/Desktop/sage-starter
source venv/bin/activate

# 2. Run full automated verification suite (~25 seconds)
./verify_all.sh

# 2b. Print complete test inventory by suite (217 unified checks)
./verify_all.sh --list

# 3. Verify weekly order forecast and consistency test suites
./venv/bin/python -m unittest stage10/test_outlook.py stage9/test_consistency_fixes.py

# 4. Start SAGE platform (binds to 127.0.0.1 only; starts in DRY-RUN mode)
./run_sage.sh
```

### Server URLs & Authentication:
* **Executive Dashboard (Viewer):** [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
  * Authenticate at `/login` with an email and password, or visit `http://127.0.0.1:8000/?token=<SAGE_WEB_TOKEN>`.
  * *(The session is persisted via a secure, HttpOnly, SameSite=Strict cookie `sage_session`).*
* **Operator Control Panel (Controller):** [http://127.0.0.1:8001/ctrl/](http://127.0.0.1:8001/ctrl/)
  * Authenticate at `/ctrl/login` using `SAGE_CONTROLLER_TOKEN` from `.env`.

### User Management (Creating the First User):
To create or manage viewer accounts (roles: `viewer`, `operator`, `admin`):
```bash
# Seed the default admin user (sreeshanmukhtrk@gmail.com / sageadmin2026!)
python web/manage_users.py seed

# Add a custom user with secure salted scrypt password hashing
python web/manage_users.py add user@company.com viewer

# List registered users
python web/manage_users.py list

# Reset a user's password
python web/manage_users.py passwd user@company.com
```

### Token Configuration in `.env`:
* Tokens are stored in `.env` as `SAGE_WEB_TOKEN` and `SAGE_CONTROLLER_TOKEN`.
* The controller token is independent and never derived from the viewer token.
* **Security Note:** Never display or read token values aloud to an audience.

---

## 2. Live Operator Controls (Controller UI)

1. **Feeding Scenario Days (1–10 January 2026):**
   * On the Controller Dashboard under **Demo Feed**, click **"Feed next day"** once per day.
   * Advances current day sequentially (`2026-01-01` $\rightarrow$ `2026-01-10`).
   * The Executive Viewer reflects each day's new briefing within 5 seconds.
2. **Switching to LIVE Email Mode & Nightly Dispatch (19:45 / 20:00 IST):**
   * In the Controller modal, switching to LIVE mode requires typing the exact word `LIVE`.
   * On restart, SAGE **always resets to DRY-RUN mode** automatically.
   * **Automatic Daily Email Requirement:** Automatic email delivery requires:
     1. `./run_sage.sh` running in terminal.
     2. Laptop awake and plugged into power between **19:45 IST (prepare)** and **20:00 IST (send)**. (`run_sage.sh` automatically engages `caffeinate -i` on macOS to prevent idle sleep).
     3. Mode explicitly switched to **LIVE** in the controller by typing `LIVE` (otherwise report dispatches in Dry-run mode without reaching Gmail).
3. **Dispatching a Real Email (CLI Command):**
   * Automated tests and `verify_all.sh` **never send live email**.
   * To dispatch a real live email to the verified recipient:
     ```bash
     python -m stage9.send_check --live --as-of 2025-12-31 [--recipient sreeshanmukhtrk@gmail.com]
     ```
   * *Output shows:* `Mode: LIVE`, `Status: SUCCESS_LIVE`, `SMTP Code: 250`, and the delivery duration.
4. **Resetting Demo to Baseline:**
   * In Controller, click **"Reset Demo"** (or run `python -c "from stage9.ops import reset_demo_v6; reset_demo_v6()"`).
   * Restores live SQLite DB to `2025-12-31` (Day 0) in under 1 second with all 10 packs queued.

---

## 3. Teardown / Clean Exit

```bash
# Stop both servers cleanly and verify ports 8000 and 8001 are free
./stop_sage.sh
```

*Output shows:* `SAGE servers stopped successfully. Ports 8000 and 8001 are FREE.`

---

## 4. Expected Display Summary Table

| Screen / Step | Target URL / Command | What It Must Show |
| :--- | :--- | :--- |
| **`./verify_all.sh`** | CLI | `✓ ALL VERIFICATION CHECKS PASSED (100% SUITE PASS, ZERO FAILURES, EXIT 0)` |
| **`./run_sage.sh`** | CLI | `SAGE Operations Platform is RUNNING (Verified Healthy)` (Port 8000 & 8001 on `127.0.0.1`) |
| **Viewer Home** | `http://127.0.0.1:8000/` | Morning Briefing editorial layout, verbatim framing sentence in footer |
| **Viewer Insights (2025-12-31)** | `http://127.0.0.1:8000/insights` | **78.3%** on-time (173 of 221), 48 unfulfilled orders (652 units), PO #18 139d overdue |
| **Viewer Insights (2025-03-01)** | `http://127.0.0.1:8000/insights?date=2025-03-01` | **100.0%** on-time, 4 supplier deliveries == 4 goods receipts |
| **Controller Dashboard** | `http://127.0.0.1:8001/ctrl/` | Operator status, Mode: DRY-RUN, Next queue: Day 1 of 10 |
| **Day 6 Feed** | Controller / Viewer | Status: `CRITICAL`, Headline: *"Steel Rod 10mm at safety stock (47 kg remaining)"* |
| **Day 7 Feed** | Controller / Viewer | Status: `CRITICAL`, Headline: *"Raw material stockout on Steel Rod 10mm (0 kg in stock)"* |
| **Scoring Rehearsal** | `python stage10/demo_feed/score.py` | `TOTAL SCORE (V3): 9 HITS, 0 PARTIALS, 1 MISSES` |
| **`./stop_sage.sh`** | CLI | `Ports 8000 and 8001 are FREE` |
