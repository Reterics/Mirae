#!/usr/bin/env bash
# Install Mirae on a Raspberry Pi 5 running Raspberry Pi OS (64-bit).
# Run from a checkout of the repository: sudo bash deploy/pi/install.sh [extras]
#   extras: comma-separated pip extras, default "pi" (e.g. "pi,vision,speech")
set -euo pipefail

EXTRAS="${1:-pi}"
PREFIX=/opt/mirae
REPO="$(cd "$(dirname "$0")/../.." && pwd)"

# picamera2/libcamera and lgpio are only packaged for apt, so the venv must be
# able to see the system site-packages.
apt-get update
apt-get install -y --no-install-recommends \
    python3-venv python3-dev build-essential cmake \
    python3-picamera2 python3-lgpio \
    i2c-tools libportaudio2 alsa-utils rsync

id -u mirae >/dev/null 2>&1 || useradd --system --create-home --groups gpio,i2c,video,audio mirae

mkdir -p "$PREFIX" /etc/mirae
if systemctl cat mirae.service >/dev/null 2>&1; then
    # Finish motor shutdown before replacing code used by a running robot.
    systemctl stop mirae.service
fi
rsync -a --delete --exclude .git --exclude .venv --exclude /var/ \
    --exclude .pytest_cache --exclude .mypy_cache --exclude .ruff_cache "$REPO/" "$PREFIX/"
python3 -m venv --system-site-packages "$PREFIX/.venv"
"$PREFIX/.venv/bin/pip" install --upgrade pip
"$PREFIX/.venv/bin/pip" install "$PREFIX[$EXTRAS]"
chown -R mirae:mirae "$PREFIX"

[ -f /etc/mirae/mirae.toml ] || cat > /etc/mirae/mirae.toml <<'TOML'
# Local overrides for this robot, merged over the "pi" profile.
# [hardware.motor_pins]
# pwma = 12
# [ai]
# provider = "openai_compat"
# base_url = "http://my-ollama-box.local:11434/v1"
TOML

install -m 0644 "$REPO/deploy/systemd/mirae.service" /etc/systemd/system/mirae.service
systemctl daemon-reload
systemctl enable --now mirae.service
echo "Mirae installed. Logs: journalctl -u mirae -f"
