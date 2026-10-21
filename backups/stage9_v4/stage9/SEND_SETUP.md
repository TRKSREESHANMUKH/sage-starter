# SAGE 8:00 PM Daily Email — Real Sending Setup & Scheduling Guide

This guide explains how to enable live email delivery and configure automated daily scheduling for the SAGE 8:00 PM Daily Operations Brief.

---

## 1. Configure Email Credentials (.env)

Ensure your `.env` file contains the following keys:

```bash
# SMTP Configuration
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_16_character_app_password
SMTP_FROM=your_email@gmail.com

# Enable Live Sending
SAGE_SEND_ENABLED=true

# Dashboard Base URL (used in email links, no token attached)
SAGE_BASE_URL=http://127.0.0.1:8000

# Authentication Token (stored in .env only)
SAGE_WEB_TOKEN=your_secure_secret_token
```

### How to Create a Gmail App Password
1. Open your **Google Account** settings (https://myaccount.google.com).
2. Navigate to **Security** on the left menu.
3. Under **How you sign in to Google**, ensure **2-Step Verification** is turned **ON**.
4. In the search box or security section, select **App passwords** (or go to https://myaccount.google.com/apppasswords).
5. Name the app password (e.g. `SAGE Plant Alerts`) and click **Create**.
6. Copy the generated 16-character code (without spaces) and paste it into `.env` as `SMTP_PASSWORD`.

---

## 2. Test Real Live Sending

Run the test send CLI command:

```bash
python -m stage9.scheduler --test-send
```

- This sends exactly **one** email with the 1-page PDF attached directly to `SMTP_USER` (your own address).
- When configured correctly with `SAGE_SEND_ENABLED=true`, the terminal log will show `SUCCESS`:
  ```
  [INFO] Attempting live SMTP delivery for test_send to ['your_email@gmail.com']...
  [INFO] SMTP delivery successful for test_send: SUCCESS
  ```

---

## 3. Automated Daily Execution (At 20:00 Daily)

A laptop or desktop that sleeps may miss the exact 20:00 trigger. SAGE handles this with **catch-up logic**:
- Running `python -m stage9.scheduler --run-due` checks if today's email has already been dispatched.
- If not yet sent today, it dispatches the digest for the current simulated replay date, logs `SUCCESS`, advances the replay clock by 1 day, and exits.
- If already sent today, it outputs `already sent` and immediately exits with no duplicate emails.

### Option 1 (Recommended): OS-Level Scheduled Task

#### A. macOS (`launchd`)
Create file `~/Library/LaunchAgents/com.sage.dailybrief.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.sage.dailybrief</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/asl/Desktop/sage-starter/venv/bin/python</string>
        <string>-m</string>
        <string>stage9.scheduler</string>
        <string>--run-due</string>
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
    <string>/Users/asl/Desktop/sage-starter/analytics/launchd_output.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/asl/Desktop/sage-starter/analytics/launchd_error.log</string>
</dict>
</plist>
```

Load the job:
```bash
launchctl load ~/Library/LaunchAgents/com.sage.dailybrief.plist
```

#### B. Linux (`cron`)
Add the following line to `crontab -e`:

```bash
0 20 * * * cd /path/to/sage-starter && ./venv/bin/python -m stage9.scheduler --run-due >> analytics/cron_scheduler.log 2>&1
```

#### C. Windows Task Scheduler
In PowerShell (Administrator):

```powershell
$Action = New-ScheduledTaskAction -Execute "C:\path\to\sage-starter\venv\Scripts\python.exe" -Argument "-m stage9.scheduler --run-due" -WorkingDirectory "C:\path\to\sage-starter"
$Trigger = New-ScheduledTaskTrigger -Daily -At 8:00PM
Register-ScheduledTask -TaskName "SAGE_Daily_Operations_Brief" -Action $Action -Trigger $Trigger -Description "SAGE 8:00 PM Nightly Digest"
```

---

### Option 2: Long-Running Service in Docker

Run SAGE inside Docker with automatic container restarts:

```yaml
version: "3.8"
services:
  sage-scheduler:
    build: .
    restart: unless-stopped
    command: python -m stage9.scheduler
    env_file:
      - .env
    volumes:
      - .:/app
```

---

## 4. Replay Clock & Catch-Up Behavior

1. **Replay Advancement**: Each successful execution of `--run-due` or scheduled nightly send advances the simulation date in `stage9/state/replay_pointer.json` by exactly 1 day.
2. **Idempotency Protection**: Execution records are appended to `stage9/state/sent_log.jsonl`. Running `--run-due` multiple times on the same day is completely safe and skips duplicate sends.
3. **Simulated Notice**: All emails explicitly state in the footer: `Simulated data as of <date>`.
