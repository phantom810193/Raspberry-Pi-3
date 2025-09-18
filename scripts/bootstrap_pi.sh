#!/usr/bin/env bash
set -euo pipefail

sudo apt update
sudo apt install -y git python3-venv python3-dev build-essential cmake \
  libopenblas-dev liblapack-dev libatlas-base-dev \
  libjpeg-dev libpng-dev libtiff5-dev libavcodec-dev libavformat-dev \
  libswscale-dev libv4l-dev libgtk-3-dev

mkdir -p data models templates static
cp -n .env.sample .env || true
