# Raspberry Pi Face Ad MVP

This project demonstrates an end-to-end prototype for a privacy-conscious in-store advertisement system running on a Raspberry Pi. A USB camera captures visitors, the `dlib`-powered [`face_recognition`](https://github.com/ageitgey/face_recognition) library extracts embeddings, a salted HMAC produces an anonymous member ID, and a lightweight Flask web page renders personalised ads using data stored in SQLite.

## Features
- **Real-time face capture** via OpenCV and `face_recognition` on the Raspberry Pi camera feed.
- **Anonymous member IDs** generated from face embeddings using an HMAC salt (no images written to disk).
- **SQLite backend** storing members with mock purchase histories for quick demos.
- **Flask web app** that polls for the latest visitor and displays a templated ad page suitable for tablets/monitors.
- **Bootstrap and run scripts** to simplify Raspberry Pi provisioning and local development.

## Project layout
```
├── app.py                # Flask API + polling display page
├── camera_loop.py        # Camera loop generating member IDs
├── db.py                 # SQLite schema helpers and fake data seeding
├── services/
│   └── id_hash.py        # HMAC helper used by the camera loop
├── templates/
│   └── ad.html           # Customisable advertisement template
├── scripts/
│   ├── bootstrap_pi.sh   # One-time dependency install on Raspberry Pi
│   └── run_all.sh        # Start camera loop + Flask app in the background
├── .env.sample           # Configuration template
└── requirements.txt
```

## Quick start
1. Copy the environment template and adjust secrets:
   ```bash
   cp .env.sample .env
   # edit SECRET_KEY, ID_HASH_SALT, SQLITE_PATH etc.
   ```
2. (Optional) Prime a virtual environment and install dependencies:
   ```bash
   python3 -m venv .venv
   . .venv/bin/activate
   pip install -r requirements.txt
   ```
3. Start the camera loop and web server (runs both processes in the background):
   ```bash
   bash scripts/run_all.sh
   ```
4. Open `http://raspberrypi.local:8000/` (or the Pi IP) in a browser to view the live ad feed.

## Raspberry Pi provisioning
For a clean Raspberry Pi OS installation, run the bootstrap script once to install build dependencies required by `dlib`/OpenCV and create the project folders:
```bash
bash scripts/bootstrap_pi.sh
```

## Database
- The first time a member ID is created, `ensure_member_and_seed` inserts five random purchase rows so the ad page has content for demos.
- Existing members simply update their `last_seen_ts`. The `/latest` endpoint returns the most recently seen member to drive the polling UI.

## Privacy notes
- Only salted HMAC IDs and aggregated purchase records are persisted.
- No images or raw embeddings are written to disk, aligning with GDPR-friendly practices.

## Deployment via GitHub Actions
A sample GitHub Actions workflow can rsync the repository to a Raspberry Pi over SSH and restart the processes. Populate `PI_HOST`, `PI_USER`, `PI_SSH_KEY`, and `PI_APP_DIR` secrets/variables in your repository settings before enabling the workflow.
