#!/usr/bin/env bash
set -euo pipefail

echo "[system] installing ubuntu packages required by browser automation"
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y \
  python3 \
  python3-pip \
  python3-venv \
  xvfb \
  curl \
  unzip \
  libnss3 \
  libatk-bridge2.0-0 \
  libxkbcommon0 \
  libgtk-3-0 \
  libgbm1 \
  libasound2t64 \
  libxshmfence1 \
  libxcomposite1 \
  libxdamage1 \
  libxfixes3 \
  libxrandr2 \
  libdrm2 \
  libatk1.0-0 \
  libcups2 \
  libdbus-1-3 \
  libnspr4

echo "[system] done"
