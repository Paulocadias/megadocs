#!/bin/bash
# Deployment script for DocsSite on Ubuntu (GCP e2-micro)
# Usage: ./deploy.sh

set -e

echo "========================================"
echo "   DocsSite Deployment Script"
echo "========================================"

# 1. Install Dependencies
echo "[1/5] Checking system dependencies..."
if ! command -v docker &> /dev/null; then
    echo "Docker not found. Installing Docker..."
    sudo apt-get update
    sudo apt-get install -y docker.io
    sudo systemctl start docker
    sudo systemctl enable docker
else
    echo "Docker is already installed."
fi

if ! command -v git &> /dev/null; then
    echo "Git not found. Installing Git..."
    sudo apt-get install -y git
else
    echo "Git is already installed."
fi

# 1.5 Security Hardening & System Stability
echo "[1.5/5] Hardening system..."

# Setup Swap (Critical for micro instances)
if [ ! -f /swapfile ]; then
    echo "Creating 1GB swap file..."
    sudo fallocate -l 1G /swapfile
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile
    sudo swapon /swapfile
    echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
    echo "Swap created."
fi

# Setup UFW Firewall
if ! sudo ufw status | grep -q "Status: active"; then
    echo "Configuring Firewall..."
    sudo ufw default deny incoming
    sudo ufw default allow outgoing
    sudo ufw allow ssh
    sudo ufw allow http
    sudo ufw allow https
    # Force enable without prompt
    echo "y" | sudo ufw enable
    echo "Firewall enabled."
fi

# Setup Fail2Ban
if ! command -v fail2ban-client &> /dev/null; then
    echo "Installing Fail2Ban..."
    sudo apt-get install -y fail2ban
    sudo systemctl enable fail2ban
    sudo systemctl start fail2ban
    echo "Fail2Ban installed."
fi

# 2. Setup Docker permissions
if ! groups $USER | grep &>/dev/null '\bdocker\b'; then
    echo "[2/5] Adding user to docker group..."
    sudo usermod -aG docker $USER
    echo "CRITICAL: You have been added to the docker group."
    echo "Please log out and log back in to apply changes, then run this script again."
    exit 1
fi
echo "User permissions are correct."

# 3. Setup Environment
echo "[3/5] Setting up environment..."
if [ ! -f .env ]; then
    echo "Creating .env from example..."
    cp .env.example .env
    # Generate random secret key using python
    if command -v python3 &> /dev/null; then
        SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
        sed -i "s/SECRET_KEY=.*/SECRET_KEY=$SECRET/" .env
        echo "Generated new SECRET_KEY."
    else
        echo "Python3 not found, using default (insecure) key. Please update .env manually."
    fi
else
    echo ".env file already exists."
fi

# Create data directory if it doesn't exist
mkdir -p data

# 4. Build Docker Image
echo "[4/5] Building Docker image..."
docker build -t docssite .

# 5. Run Container
echo "[5/5] Starting container..."
# Stop existing container if running
if [ "$(docker ps -q -f name=docssite)" ]; then
    echo "Stopping running container..."
    docker stop docssite
fi
# Remove existing container if exists (running or stopped)
if [ "$(docker ps -aq -f name=docssite)" ]; then
    echo "Removing old container..."
    docker rm docssite
fi

# Run new container
# Mapping port 80 (host) to 5000 (container)
docker run -d \
  --name docssite \
  --restart always \
  -p 80:5000 \
  -v $(pwd)/data:/app/data \
  --env-file .env \
  docssite

echo "========================================"
echo "   Deployment Complete!"
echo "   App is running at http://$(curl -s ifconfig.me)"
echo "========================================"
