#!/usr/bin/env bash
set -e

python3 -m venv .venv
. .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

nohup .venv/bin/python camera_loop.py > cam.log 2>&1 &
nohup .venv/bin/python app.py > web.log 2>&1 &

echo "running. open http://raspberrypi.local:8000/"
