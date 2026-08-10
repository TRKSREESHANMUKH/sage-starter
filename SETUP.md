# SAGE — Local Setup Guide

Follow this once on your machine. Every teammate should end up with an
identical setup, verified by the same final check at the bottom.

## 1. Install prerequisites

### On the Intel Mac
1. Install Docker Desktop for Mac (Intel chip): https://www.docker.com/products/docker-desktop/
2. Install Python 3.11+: https://www.python.org/downloads/macos/
3. Install Git (Terminal will prompt you the first time you use a git command)

### On each Windows laptop
1. Install Docker Desktop for Windows: https://www.docker.com/products/docker-desktop/
2. Install Python 3.11+ from https://www.python.org/downloads/windows/
   (check "Add python.exe to PATH" during install)
3. Install Git for Windows: https://git-scm.com/download/win

## 2. Clone the repo

Use GitHub Desktop (File → Clone Repository) — simpler than Terminal for this step.

## 3. Create and activate a virtual environment

Mac:

    python3 -m venv venv
    source venv/bin/activate

Windows (PowerShell):

    python -m venv venv
    venv\Scripts\Activate.ps1

If PowerShell blocks the activation with a permissions error, run:

    Set-ExecutionPolicy -Scope CurrentUser RemoteSigned

then try activating again.

## 4. Install dependencies

    pip install -r requirements.txt

## 5. Set up your environment file

    cp .env.example .env        # Mac
    copy .env.example .env      # Windows

## 6. Start Postgres

    docker-compose up -d
    docker ps

Check that `sage_postgres` shows status "healthy."

## 7. Run the API

    uvicorn app.main:app --reload

## 8. Verify everything is connected

Open http://localhost:8000/docs in your browser — you should see two
endpoints listed: `/health` and `/health/db`.

Click each one → "Try it out" → "Execute" — both should return
`"status": "ok"`.

## Daily workflow from here on

Every time you come back to work, just run these three:

    docker-compose up -d
    source venv/bin/activate      # Mac
    venv\Scripts\Activate.ps1     # Windows
    uvicorn app.main:app --reload

Then confirm http://localhost:8000/docs still loads.