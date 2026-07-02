#!/bin/bash
set -e

# Online Everywhere — Deploy LinkedIn Agent to VM
# Usage: ./deploy.sh <vm-ip> <ssh-user>
# Example: ./deploy.sh 35.206.80.189 devon

VM_IP="${1:-35.206.80.189}"
SSH_USER="${2:-devon}"
REMOTE_DIR="/home/${SSH_USER}/social-agent"
LOCAL_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== Deploying Online Everywhere LinkedIn Agent ==="
echo "VM: ${SSH_USER}@${VM_IP}"
echo "Local: ${LOCAL_DIR} -> Remote: ${REMOTE_DIR}"

# 1. Rsync the entire social-agent directory (excluding heavy/cache files)
echo "--- Syncing files ---"
rsync -avz \
    --exclude='__pycache__/' \
    --exclude='*.pyc' \
    --exclude='.git/' \
    --exclude='node_modules/' \
    --exclude='.env' \
    --exclude='data/' \
    --exclude='assets/' \
    -e "ssh -o StrictHostKeyChecking=no" \
    "${LOCAL_DIR}/" "${SSH_USER}@${VM_IP}:${REMOTE_DIR}/"

# 2. SSH in to set up
echo "--- Setting up on VM ---"
ssh -t "${SSH_USER}@${VM_IP}" "
set -e

echo 'Creating data and assets directories...'
mkdir -p ${REMOTE_DIR}/data ${REMOTE_DIR}/assets

echo 'Installing Python dependencies...'
cd ${REMOTE_DIR}
pip3 install --user -r requirements.txt 2>/dev/null || pip3 install -r requirements.txt

echo 'Setting up .env file...'
if [ ! -f ${REMOTE_DIR}/.env ]; then
    cat > ${REMOTE_DIR}/.env << 'ENVEOF'
# Linkedin
LINKEDIN_ACCESS_TOKEN=
LINKEDIN_ORG_ID=125564340

# Google Gemini
GOOGLE_API_KEY=

# Telegram
TELEGRAM_BOT_TOKEN=

# Data directory (leave as-is for Docker, or change for local)
OLE_DATA_DIR=${REMOTE_DIR}

# Optional
NVIDIA_API_KEY=
OPENAI_API_KEY=
ENVEOF
    echo 'Created .env — EDIT IT with your tokens: nano ${REMOTE_DIR}/.env'
else
    echo '.env already exists, keeping it'
fi

echo ''
echo '=== Setup complete ==='
echo ''
echo 'Next steps:'
echo '  1. Edit .env: nano ${REMOTE_DIR}/.env'
echo '  2. Test the bot: cd ${REMOTE_DIR} && python3 telegram_bot.py'
echo '  3. Or run as service (see HANDOFF.md)'
echo ''
echo 'To run 24/7 as a systemd service:'
echo '  sudo tee /etc/systemd/system/ole-agent.service << EOF'
echo '[Unit]'
echo 'Description=Online Everywhere LinkedIn Telegram Bot'
echo 'After=network.target'
echo ''
echo '[Service]'
echo 'Type=simple'
echo 'User=${SSH_USER}'
echo 'WorkingDirectory=${REMOTE_DIR}'
echo 'ExecStart=$(which python3) ${REMOTE_DIR}/telegram_bot.py'
echo 'Restart=always'
echo 'EnvironmentFile=${REMOTE_DIR}/.env'
echo ''
echo '[Install]'
echo 'WantedBy=multi-user.target'
echo 'EOF'
echo '  sudo systemctl daemon-reload && sudo systemctl enable --now ole-agent'
"
echo "=== Deployment complete ==="
