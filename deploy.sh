#!/bin/bash
# PISONET Auto-Deploy Script for Armbian 26.2.1 Orangepione
# This script automatically deploys PISONET to Orange Pi One via SSH

set -e

# Configuration
OPI_HOST=${1:-"192.168.1.100"}
OPI_USER=${2:-"root"}
OPI_PASS=${3:-"1234"}
ADMIN_USER=${4:-"pisonet"}
ADMIN_PASS=${5:-"pisonet123"}

echo "=========================================="
echo "  PISONET Auto-Deploy to Orange Pi One"
echo "=========================================="
echo "Target: $OPI_USER@$OPI_HOST"
echo "Admin User: $ADMIN_USER"
echo ""

# Check if SSH is available
if ! command -v sshpass &> /dev/null; then
    echo "Installing sshpass for automated SSH..."
    sudo apt update && sudo apt install -y sshpass
fi

# Test connection
echo "Testing SSH connection..."
if ! sshpass -p "$OPI_PASS" ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 "$OPI_USER@$OPI_HOST" "echo 'SSH connection successful'" &>/dev/null; then
    echo "ERROR: Cannot connect to Orange Pi at $OPI_HOST"
    echo "Please check:"
    echo "  - Orange Pi is powered on"
    echo "  - IP address is correct"
    echo "  - SSH service is running"
    exit 1
fi

echo "SSH connection verified."

# System verification
echo "Running system verification..."
sshpass -p "$OPI_PASS" ssh -o StrictHostKeyChecking=no "$OPI_USER@$OPI_HOST" << 'EOF'
#!/bin/bash

echo "=========================================="
echo "  SYSTEM VERIFICATION"
echo "=========================================="

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

check_pass() {
    echo -e "${GREEN}✓${NC} $1"
}

check_fail() {
    echo -e "${RED}✗${NC} $1"
}

check_warn() {
    echo -e "${YELLOW}⚠${NC} $1"
}

# Check OS and version
echo "Checking Operating System..."
if [ -f /etc/os-release ]; then
    . /etc/os-release
    if [[ "$PRETTY_NAME" == *"Armbian"* ]] && [[ "$PRETTY_NAME" == *"26.2.1"* ]]; then
        check_pass "Armbian 26.2.1 detected: $PRETTY_NAME"
    else
        check_warn "OS detected: $PRETTY_NAME (Expected: Armbian 26.2.1)"
    fi
else
    check_fail "Cannot determine OS version"
fi

# Check kernel version
KERNEL=$(uname -r)
if [[ "$KERNEL" == *"6.12.74"* ]]; then
    check_pass "Kernel version: $KERNEL"
else
    check_warn "Kernel version: $KERNEL (Expected: 6.12.74)"
fi

# Check architecture
ARCH=$(uname -m)
if [ "$ARCH" = "armv7l" ] || [ "$ARCH" = "aarch64" ]; then
    check_pass "Architecture: $ARCH (ARM)"
else
    check_fail "Unsupported architecture: $ARCH"
fi

# Check internet connectivity
echo "Checking Internet Connectivity..."
if ping -c 1 -W 3 8.8.8.8 &>/dev/null; then
    check_pass "Internet connection available"
else
    check_fail "No internet connection"
fi

# Check package manager
if command -v apt &>/dev/null; then
    check_pass "APT package manager available"
else
    check_fail "APT package manager not found"
fi

# Check Python
if command -v python3 &>/dev/null; then
    PYTHON_VER=$(python3 --version 2>&1 | cut -d' ' -f2)
    if [[ "$PYTHON_VER" =~ ^3\.(11|12) ]]; then
        check_pass "Python $PYTHON_VER installed"
    else
        check_warn "Python $PYTHON_VER (Recommended: 3.11+)"
    fi
else
    check_fail "Python 3 not found"
fi

# Check pip
if command -v pip3 &>/dev/null; then
    check_pass "pip3 available"
else
    check_fail "pip3 not found"
fi

# Check GPIO support
echo "Checking GPIO Support..."
if [ -d "/sys/class/gpio" ]; then
    check_pass "GPIO sysfs interface available"
else
    check_warn "GPIO sysfs interface not found (may be loaded later)"
fi

# Check available memory
MEM_TOTAL=$(free -m | awk 'NR==2{printf "%.0f", $2}')
if [ "$MEM_TOTAL" -ge 512 ]; then
    check_pass "Memory: ${MEM_TOTAL}MB available"
else
    check_warn "Memory: ${MEM_TOTAL}MB (Recommended: 512MB+)"
fi

# Check available storage
STORAGE=$(df / | awk 'NR==2{printf "%.0f", $4/1024}')
if [ "$STORAGE" -ge 4 ]; then
    check_pass "Storage: ${STORAGE}GB available"
else
    check_warn "Storage: ${STORAGE}GB (Recommended: 4GB+)"
fi

# Check SSH service
if systemctl is-active --quiet ssh; then
    check_pass "SSH service is running"
else
    check_fail "SSH service is not running"
fi

# Check required ports
echo "Checking Network Ports..."
if command -v netstat &>/dev/null || command -v ss &>/dev/null; then
    if ss -tln | grep -q ":22 "; then
        check_pass "SSH port 22 is listening"
    else
        check_fail "SSH port 22 is not listening"
    fi
else
    check_warn "Cannot check ports (netstat/ss not available)"
fi

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    check_pass "Running as root (required for installation)"
else
    check_fail "Not running as root (installation requires root)"
fi

echo ""
echo "=========================================="
echo "  VERIFICATION COMPLETE"
echo "=========================================="

EOF

if [ $? -ne 0 ]; then
    echo "System verification failed!"
    exit 1
fi

echo "System verification passed."

# Create deployment script
cat > /tmp/deploy_pisonet.sh << 'EOF'
#!/bin/bash
set -e

echo "=========================================="
echo "  Deploying PISONET Server"
echo "  Orange Pi One - Automated Setup"
echo "=========================================="

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

success() {
    echo -e "${BLUE}[SUCCESS]${NC} $1"
}

# Create admin user
log "Creating admin user: '$ADMIN_USER'"
if id "$ADMIN_USER" &>/dev/null; then
    warn "User '$ADMIN_USER' already exists, updating password..."
    echo "$ADMIN_USER:$ADMIN_PASS" | chpasswd
else
    useradd -m -s /bin/bash "$ADMIN_USER"
    echo "$ADMIN_USER:$ADMIN_PASS" | chpasswd
    usermod -aG sudo "$ADMIN_USER"
    log "Admin user '$ADMIN_USER' created with sudo privileges"
fi

# Add admin user to GPIO group if it exists
if getent group gpio >/dev/null 2>&1; then
    usermod -aG gpio "$ADMIN_USER"
    log "Added $ADMIN_USER to gpio group"
fi

# System update
log "Updating system packages..."
apt update && apt upgrade -y

# Install dependencies
log "Installing system dependencies..."
apt install -y \
    python3 python3-pip python3-venv python3-dev gcc \
    sqlite3 nginx certbot python3-certbot-nginx \
    git curl wget unzip build-essential

# Install GPIO libraries
log "Installing GPIO libraries..."
apt install -y python3-gpiozero

# Create project directory
PROJECT_DIR="/opt/pisonet"
log "Setting up project directory: $PROJECT_DIR"
mkdir -p "$PROJECT_DIR"
chown "$ADMIN_USER:$ADMIN_USER" "$PROJECT_DIR"

# Clone repository
cd "$PROJECT_DIR"
if [ -d ".git" ]; then
    log "Updating existing repository..."
    git pull origin main
else
    log "Cloning PISONET repository..."
    git clone https://github.com/Sonjii99x-Glitch/project_centralize.git .
fi

chown -R "$ADMIN_USER:$ADMIN_USER" "$PROJECT_DIR"

# Setup virtual environment
log "Creating Python virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
log "Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Setup database
log "Setting up database..."
mkdir -p data
if [ ! -f "data/pisonet.db" ]; then
    python3 -c "
import sqlite3
import os

# Create database
db_path = 'data/pisonet.db'
os.makedirs(os.path.dirname(db_path), exist_ok=True)

conn = sqlite3.connect(db_path)
c = conn.cursor()

# Create tables
c.execute('''CREATE TABLE IF NOT EXISTS config (
    key TEXT PRIMARY KEY,
    value TEXT,
    description TEXT
)''')

c.execute('''CREATE TABLE IF NOT EXISTS clients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id TEXT UNIQUE,
    ip_address TEXT,
    mac_address TEXT,
    hostname TEXT,
    credit REAL DEFAULT 0,
    total_credit REAL DEFAULT 0,
    sessions INTEGER DEFAULT 0,
    last_seen DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'active'
)''')

c.execute('''CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER,
    start_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    end_time DATETIME,
    duration INTEGER, -- in minutes
    credit_used REAL,
    FOREIGN KEY (client_id) REFERENCES clients(id)
)''')

c.execute('''CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER,
    amount REAL,
    type TEXT, -- 'credit', 'debit'
    description TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (client_id) REFERENCES clients(id)
)''')

c.execute('''CREATE TABLE IF NOT EXISTS system_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    level TEXT,
    message TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
)''')

# Insert default config
configs = [
    ('coin_value', '10', 'Minutes per peso'),
    ('max_credit', '480', 'Maximum credit per client (minutes)'),
    ('session_timeout', '1440', 'Session timeout (minutes)'),
    ('cleanup_interval', '60', 'Inactive client cleanup (minutes)'),
    ('relay_pin', '5', 'GPIO pin for relay control'),
    ('coin_pin', '3', 'GPIO pin for coin sensor'),
    ('admin_password', '1234', 'Admin panel password'),
    ('system_name', 'PISONET Cafe', 'System display name'),
    ('timezone', 'Asia/Manila', 'System timezone'),
    ('maintenance_mode', 'false', 'Maintenance mode flag')
]

for key, value, desc in configs:
    c.execute('INSERT OR IGNORE INTO config (key, value, description) VALUES (?, ?, ?)',
             (key, value, desc))

conn.commit()
conn.close()
print('Database initialized successfully')
"
fi

# Setup systemd service
log "Setting up systemd service..."
cat > /etc/systemd/system/pisonet.service << EOF
[Unit]
Description=PISONET Internet Cafe Management System
After=network.target
Wants=network.target

[Service]
Type=simple
User=$ADMIN_USER
Group=$ADMIN_USER
WorkingDirectory=$PROJECT_DIR
Environment=PATH=$PROJECT_DIR/venv/bin
ExecStart=$PROJECT_DIR/venv/bin/python server.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=pisonet

# Security settings
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=strict
ReadWritePaths=$PROJECT_DIR/data $PROJECT_DIR/backups
ProtectHome=yes
PrivateDevices=no

# GPIO access for Orange Pi
SupplementaryGroups=gpio i2c spi

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable pisonet

# Setup nginx
log "Configuring nginx web server..."
cat > /etc/nginx/sites-available/pisonet << EOF
server {
    listen 80;
    server_name _;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "no-referrer-when-downgrade" always;
    add_header Content-Security-Policy "default-src 'self' http: https: data: blob: 'unsafe-inline'" always;

    # Root directory
    root $PROJECT_DIR/static;
    index index.html;

    # API endpoints
    location /api/ {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    # Admin panel
    location /admin/ {
        proxy_pass http://127.0.0.1:5000/admin/;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    # Static files
    location /static/ {
        alias $PROJECT_DIR/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # Main application
    location / {
        try_files \$uri \$uri/ /index.html;
    }

    # Health check
    location /health {
        access_log off;
        return 200 "healthy\n";
        add_header Content-Type text/plain;
    }
}
EOF

ln -sf /etc/nginx/sites-available/pisonet /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx

# Setup firewall
log "Configuring firewall..."
apt install -y ufw
ufw --force enable
ufw allow ssh
ufw allow 80
ufw allow 443

# Create backup script
log "Setting up backup system..."
mkdir -p backups
cat > backup.sh << 'EOF'
#!/bin/bash
# PISONET Backup Script
BACKUP_DIR="/opt/pisonet/backups"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/pisonet_$DATE.tar.gz"

mkdir -p "$BACKUP_DIR"

# Create backup
tar -czf "$BACKUP_FILE" \
    --exclude='*.log' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    data/ \
    config/ \
    logs/

# Keep only last 7 backups
cd "$BACKUP_DIR"
ls -t *.tar.gz | tail -n +8 | xargs -r rm

echo "Backup created: $BACKUP_FILE"
EOF

chmod +x backup.sh

# Setup cron for backups
(crontab -l ; echo "0 2 * * * /opt/pisonet/backup.sh") | crontab -

# Start service
log "Starting PISONET service..."
systemctl start pisonet

# Wait for service to start
sleep 5

# Verify installation
if systemctl is-active --quiet pisonet; then
    success "PISONET service is running!"
else
    error "PISONET service failed to start"
    systemctl status pisonet
    exit 1
fi

if systemctl is-active --quiet nginx; then
    success "Nginx web server is running!"
else
    error "Nginx failed to start"
    systemctl status nginx
    exit 1
fi

# Get IP address
IP_ADDR=$(ip route get 1 | awk '{print $7}' || hostname -I | awk '{print $1}')

success "=========================================="
success "  PISONET Installation Complete!"
success "=========================================="
echo ""
echo "🌐 Web Interface: http://$IP_ADDR"
echo "🔧 Admin Panel: http://$IP_ADDR/admin"
echo "📊 API Endpoint: http://$IP_ADDR/api"
echo ""
echo "� Admin User: $ADMIN_USER"
echo "📁 Project Location: $PROJECT_DIR"
echo "🗄️  Database: $PROJECT_DIR/data/pisonet.db"
echo "📋 Service Logs: journalctl -u pisonet -f"
echo "📋 User Logs: journalctl -u pisonet -f --user"
echo ""
echo "🔑 Admin Password: 1234 (change this immediately!)"
echo "⚙️  GPIO Pins: Coin=3, Relay=5 (verify for your Orange Pi One)"
echo ""
echo "Next Steps:"
echo "1. Access http://$IP_ADDR to complete setup wizard"
echo "2. Change default admin password in settings"
echo "3. Configure GPIO pins for your Orange Pi One board"
echo "4. Connect coin sensor and relay hardware"
echo "5. Install client software on workstations"
echo ""
echo "SSH Access:"
echo "  ssh $ADMIN_USER@$IP_ADDR"
echo "  sudo systemctl status pisonet"
echo ""
success "=========================================="

EOF

# Execute deployment
echo "Executing deployment script on Orange Pi..."
sshpass -p "$OPI_PASS" ssh -o StrictHostKeyChecking=no "$OPI_USER@$OPI_HOST" "bash" < /tmp/deploy_pisonet.sh

if [ $? -eq 0 ]; then
    echo ""
    echo "=========================================="
    echo "  DEPLOYMENT SUCCESSFUL!"
    echo "=========================================="
    echo ""
    echo "Your PISONET server is now running at:"
    echo "🌐 http://$OPI_HOST"
    echo ""
    echo "Access the web interface to complete setup."
    echo "Default admin password: 1234"
else
    echo ""
    echo "=========================================="
    echo "  DEPLOYMENT FAILED!"
    echo "=========================================="
    echo ""
    echo "Check the error messages above and try again."
    exit 1
fi