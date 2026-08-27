#!/bin/sh
set -eu

if [ "$(id -u)" -eq 0 ]; then
  echo "Run this script as the login user, not root." >&2
  exit 1
fi

sudo install -m 0755 -d /etc/apt/keyrings
sudo apt-get update
sudo apt-get install -y ca-certificates curl git

sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
. /etc/os-release
printf '%s\n' \
  "Types: deb" \
  "URIs: https://download.docker.com/linux/ubuntu" \
  "Suites: ${UBUNTU_CODENAME:-$VERSION_CODENAME}" \
  "Components: stable" \
  "Architectures: $(dpkg --print-architecture)" \
  "Signed-By: /etc/apt/keyrings/docker.asc" \
  | sudo tee /etc/apt/sources.list.d/docker.sources >/dev/null

sudo curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg \
  -o /usr/share/keyrings/cloudflare-main.gpg
printf '%s\n' \
  "deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] https://pkg.cloudflare.com/cloudflared noble main" \
  | sudo tee /etc/apt/sources.list.d/cloudflared.list >/dev/null

sudo apt-get update
sudo apt-get install -y \
  cloudflared containerd.io docker-buildx-plugin docker-ce docker-ce-cli \
  docker-compose-plugin
sudo usermod -aG docker "$USER"
sudo systemctl enable --now docker

docker --version
docker compose version
cloudflared --version
echo "Sign out and reconnect once so Docker group membership takes effect."
