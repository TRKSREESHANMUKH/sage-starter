# SAGE 8:00 PM Daily Email — Real Sending Setup & Scheduling Guide (Stage 9 Prompt 1)

This guide provides copy-paste steps to configure automated, unattended, two-phase daily email dispatch for SAGE with real Gmail SMTP.

---

## 1. Configure Email Credentials (.env)

Edit `/Users/asl/Desktop/sage-starter/.env`:

```bash
# SMTP Configuration (Gmail)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=thotaramakrishnasreeshanmukh@gmail.com
SMTP_PASSWORD=your_16_character_app_password
SMTP_FROM=thotaramakrishnasreeshanmukh@gmail.com

# Enable Live Sending
SAGE_SEND_ENABLED=true

# Authorized Recipients (Refuses any address not on this list)
SAGE_ALLOWED_RECIPIENTS=sreeshanmukhtrk@gmail.com,thotaramakrishnasreeshanmukh@gmail.com
SAGE_OWNER_EMAIL=thotaramakrishnasreeshanmukh@gmail.com
SAGE_DEMO_RECIPIENT=sreeshanmukhtrk@gmail.com

# Live Store Mode
SAGE_SOURCE=live
SAGE_DEMO=true
```

### Exact Steps to Generate a Gmail App Password
1. Open your Google Account Security settings: https://myaccount.google.com/security
2. Enable **2-Step Verification** on your Google account (mandatory prerequisite; Gmail will not generate app passwords without 2-Step Verification enabled).
3. Open **App passwords** directly: https://myaccount.google.com/apppasswords
4. In the "App name" field, enter `SAGE Daily Brief`.
5. Click **Create**. Google displays a yellow box with a 16-character password (e.g., `abcd efgh ijkl mnop`).
6. Copy the password and remove all spaces (exactly 16 characters).
7. Paste into `.env`:
   ```bash
   SMTP_USER=thotaramakrishnasreeshanmukh@gmail.com
   SMTP_PASSWORD=abcdefghijklmnop
   SMTP_FROM=thotaramakrishnasreeshanmukh@gmail.com
   ```
   *Note: `SMTP_USER` must be your full Gmail address, and the `From` header must match this address to satisfy Gmail's authentication policies.*

---

## 2. Test Real Live Sending & Verification

### A. Controller UI Verification (Port 8001)
1. Open http://localhost:8001 (Controller).
2. By default after every restart, mode is **Dry Run** and a red banner `DRY-RUN: emails are NOT being delivered` is permanently shown.
3. To switch to **Live**: toggle "Send Mode" to Live. A security prompt will ask you to review the recipient list (`sreeshanmukhtrk@gmail.com`) and type `LIVE` to confirm.
4. Click **👁 Preview** to inspect the rendered briefing HTML and verify the strictly 1-page A4 PDF page assertion.
5. Click **📤 Send Report Now**. In Live mode, this immediately delivers the report via Gmail SMTP and records `SUCCESS_LIVE` with response code 250, connection time in ms, and unique Message-ID header.

### B. Terminal / CLI Verification
Test live dispatch directly using the virtual environment:

```bash
# 1. Prepare / ensure current day's report
./venv/bin/python -c "from stage9.ops import ensure_report; print(ensure_report())"

# 2. Test live dispatch directly to allowlisted demo recipient
./venv/bin/python -c "from stage9.ops import send_report_now_v6; print(send_report_now_v6(recipient='sreeshanmukhtrk@gmail.com', force_live=True))"
```

Logs in `stage9/state/sent_log.jsonl` will record:
```json
{
  "timestamp": "2026-10-22T06:50:00.123Z",
  "job": "nightly_digest",
  "as_of": "2025-12-31",
  "recipient": "sreeshanmukhtrk@gmail.com",
  "status": "SUCCESS_LIVE",
  "mode": "manual",
  "subject": "SAGE Daily Brief | 31 Dec 2025 | 11 need action",
  "message_id": "<...>",
  "smtp_code": 250,
  "connection_time_ms": 142.5
}
```

---

## 3. Two-Phase Execution Architecture (Exact 8:00:00 PM Dispatch)

To guarantee the email leaves at **20:00:00** rather than minutes later due to PDF compilation:
1. **Prepare Job (19:45 IST):**
   - Ingests the next day pack from `demo_data/queue/`.
   - Computes snapshot, priorities, executive narration.
   - Compiles HTML and strictly 1-page A4 PDF under `reports/<YYYY-MM-DD>/`.
   - If the queue is empty, generates report with "No new data received today" flagged for the owner only.
   - Sends nothing!
2. **Send Job (20:00 IST):**
   - Fast dispatch (< 10 seconds).
   - Reads the already prepared report files and dispatches to `sreeshanmukhtrk@gmail.com`.
   - If prepare failed, alerts owner and exits non-zero without sending stale data.

---

## 4. Unattended Setup: Operating System Schedulers

> [!IMPORTANT]
> **Keep Laptop Awake:** To ensure jobs trigger on time, keep the laptop awake between 19:40 and 20:05.
> On macOS, run:
> ```bash
> caffeinate -s -t 3600 &
> ```
> Or adjust System Settings → Displays / Energy Saver → "Prevent automatic sleeping on power adapter".

---

### A. macOS (`launchd`) — Two Plist Files

#### 1. Prepare Job: `~/Library/LaunchAgents/com.sage.prepare.plist`
Create file `~/Library/LaunchAgents/com.sage.prepare.plist`:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.sage.prepare</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/asl/Desktop/sage-starter/venv/bin/python</string>
        <string>-m</string>
        <string>stage9.daily_run</string>
        <string>--prepare</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/Users/asl/Desktop/sage-starter</string>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>19</integer>
        <key>Minute</key>
        <integer>45</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>/Users/asl/Desktop/sage-starter/reports/prepare.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/asl/Desktop/sage-starter/reports/prepare_err.log</string>
</dict>
</plist>
```

#### 2. Send Job: `~/Library/LaunchAgents/com.sage.send.plist`
Create file `~/Library/LaunchAgents/com.sage.send.plist`:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.sage.send</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/asl/Desktop/sage-starter/venv/bin/python</string>
        <string>-m</string>
        <string>stage9.daily_run</string>
        <string>--send</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/Users/asl/Desktop/sage-starter</string>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>20</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>/Users/asl/Desktop/sage-starter/reports/send.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/asl/Desktop/sage-starter/reports/send_err.log</string>
</dict>
</plist>
```

#### Load Both macOS Jobs:
```bash
launchctl load ~/Library/LaunchAgents/com.sage.prepare.plist
launchctl load ~/Library/LaunchAgents/com.sage.send.plist
```

---

### B. Linux (`cron`) — Crontab Pair

Open crontab:
```bash
crontab -e
```

Add these two entries:
```bash
# SAGE Two-Phase Daily Intelligence Run (Asia/Kolkata 19:45 and 20:00)
45 19 * * * cd /Users/asl/Desktop/sage-starter && ./venv/bin/python -m stage9.daily_run --prepare >> reports/cron_prepare.log 2>&1
0 20 * * * cd /Users/asl/Desktop/sage-starter && ./venv/bin/python -m stage9.daily_run --send >> reports/cron_send.log 2>&1
```

---

### C. Windows Task Scheduler

Run the following in PowerShell (Administrator):

```powershell
# 1. SAGE Prepare Task (19:45 Daily)
$Action1 = New-ScheduledTaskAction -Execute "C:\Users\asl\Desktop\sage-starter\venv\Scripts\python.exe" -Argument "-m stage9.daily_run --prepare" -WorkingDirectory "C:\Users\asl\Desktop\sage-starter"
$Trigger1 = New-ScheduledTaskTrigger -Daily -At "7:45 PM"
Register-ScheduledTask -TaskName "SAGE_Prepare" -Action $Action1 -Trigger $Trigger1 -Description "SAGE Operational Intelligence Report Preparation"

# 2. SAGE Send Task (20:00 Daily)
$Action2 = New-ScheduledTaskAction -Execute "C:\Users\asl\Desktop\sage-starter\venv\Scripts\python.exe" -Argument "-m stage9.daily_run --send" -WorkingDirectory "C:\Users\asl\Desktop\sage-starter"
$Trigger2 = New-ScheduledTaskTrigger -Daily -At "8:00 PM"
Register-ScheduledTask -TaskName "SAGE_Send" -Action $Action2 -Trigger $Trigger2 -Description "SAGE 8:00 PM Daily Brief Dispatch"
```

---

## 5. Audit & Log Telemetry

Every email dispatch is permanently recorded in `stage9/state/sent_log.jsonl` with millisecond precision:
```json
{
  "timestamp": "2026-10-12T14:30:00.016Z",
  "job": "nightly_digest",
  "as_of": "2025-02-03",
  "recipient": "sreeshanmukhtrk@gmail.com",
  "status": "SUCCESS",
  "mode": "scheduled",
  "subject": "SAGE Daily Brief | 3 Feb 2025 | 1 need action"
}
```
