@echo off
REM PISONET Master Installer for Orange Pi One
REM This batch file automates the complete installation of the PISONET server
REM Run this on a Windows machine with SSH access to your Orange Pi One

echo ========================================
echo   PISONET Master Installer v1.3
echo   Orange Pi One Setup Automation
echo ========================================
echo.

REM Configuration - Update these values for your setup
set ORANGE_PI_IP=192.168.1.100
set ORANGE_PI_USER=root
set ORANGE_PI_PASS=1234
set PROJECT_DIR=/root/project_centralize

echo Target Orange Pi: %ORANGE_PI_IP%
echo Username: %ORANGE_PI_USER%
echo Project Directory: %PROJECT_DIR%
echo.

REM Check if SSH is available
where ssh >nul 2>nul
if %errorlevel% neq 0 (
    echo ERROR: SSH client not found. Please install OpenSSH for Windows.
    echo You can install it from: https://learn.microsoft.com/en-us/windows-server/administration/openssh/openssh_install_firstuse
    pause
    exit /b 1
)

echo Checking SSH connection...
ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no %ORANGE_PI_USER%@%ORANGE_PI_IP% "echo SSH connection successful" 2>nul
if %errorlevel% neq 0 (
    echo ERROR: Cannot connect to Orange Pi at %ORANGE_PI_IP%
    echo Please check:
    echo - Orange Pi is powered on
    echo - IP address is correct
    echo - SSH service is running
    echo - Firewall allows SSH connections
    pause
    exit /b 1
)

echo SSH connection verified.
echo.

REM Create installation script on Orange Pi
echo Creating installation script on Orange Pi...
ssh %ORANGE_PI_USER%@%ORANGE_PI_IP% "cat > /tmp/pisonet_install.sh << 'EOF'
#!/bin/bash
set -e

echo "========================================="
echo "  PISONET Server Installation Script"
echo "  Orange Pi One - Automated Setup"
echo "========================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to run commands with error checking
run_cmd() {
    echo "Running: $1"
    if ! eval "$1"; then
        error "Command failed: $1"
        return 1
    fi
}

log "Starting PISONET installation..."

# Step 1: Update system
log "Step 1: Updating system packages..."
run_cmd "apt update"
run_cmd "apt upgrade -y"
run_cmd "apt install curl wget git -y"

# Step 2: Install Python and dependencies
log "Step 2: Installing Python and system dependencies..."
run_cmd "apt install python3 python3-pip python3.13-venv python3-gpiozero -y"

# Step 3: Clone or update project
if [ -d "/root/project_centralize" ]; then
    log "Project directory exists, updating..."
    cd /root/project_centralize
    run_cmd "git pull origin main"
else
    log "Cloning PISONET project..."
    run_cmd "git clone https://github.com/Sonjii99x-Glitch/project_centralize.git /root/project_centralize"
fi

cd /root/project_centralize

# Step 4: Set up virtual environment
log "Step 4: Setting up Python virtual environment..."
if [ -d "pisonet_env" ]; then
    warn "Virtual environment already exists, recreating..."
    rm -rf pisonet_env
fi
run_cmd "python3 -m venv pisonet_env"

# Step 5: Install Python packages
log "Step 5: Installing Python dependencies..."
run_cmd "source pisonet_env/bin/activate && pip install -r requirements.txt"

# Step 6: Configure systemd service
log "Step 6: Configuring systemd service..."
run_cmd "cp pisonet.service /etc/systemd/system/"
run_cmd "systemctl daemon-reload"
run_cmd "systemctl enable pisonet"

# Step 7: Test GPIO access
log "Step 7: Testing GPIO functionality..."
if source pisonet_env/bin/activate && python3 -c "import gpiozero; print('GPIO test passed')" 2>/dev/null; then
    log "GPIO access test: PASSED"
else
    warn "GPIO access test: FAILED (this may be normal if no GPIO hardware connected)"
fi

# Step 8: Start service
log "Step 8: Starting PISONET service..."
run_cmd "systemctl start pisonet"

# Step 9: Verify installation
log "Step 9: Verifying installation..."
sleep 3

if systemctl is-active --quiet pisonet; then
    log "PISONET service: RUNNING"
else
    error "PISONET service: FAILED TO START"
    systemctl status pisonet
    exit 1
fi

# Get IP address for admin access
IP_ADDR=$(ip route get 1 | awk '{print $7}')
if [ -z "$IP_ADDR" ]; then
    IP_ADDR=$(hostname -I | awk '{print $1}')
fi

log "Installation completed successfully!"
echo ""
echo "========================================="
echo "  PISONET Server Ready!"
echo "========================================="
echo "Admin Panel: http://$IP_ADDR/admin"
echo "Service Status: systemctl status pisonet"
echo "Service Logs: journalctl -u pisonet -f"
echo ""
echo "Next Steps:"
echo "1. Update GPIO pin numbers in server.py for your hardware"
echo "2. Connect coin sensor and relay to GPIO pins"
echo "3. Install client software on PC workstations"
echo "4. Test coin insertion and client locking"
echo "========================================="

EOF

chmod +x /tmp/pisonet_install.sh"

if %errorlevel% neq 0 (
    echo ERROR: Failed to create installation script on Orange Pi
    pause
    exit /b 1
)

echo Installation script created successfully.
echo.

REM Run the installation script
echo ========================================
echo   Starting Automated Installation
echo   This may take 10-15 minutes...
echo ========================================
echo.

ssh %ORANGE_PI_USER%@%ORANGE_PI_IP% "/tmp/pisonet_install.sh"

if %errorlevel% neq 0 (
    echo.
    echo ERROR: Installation failed!
    echo Check the output above for error details.
    echo You may need to run individual commands manually.
    pause
    exit /b 1
)

echo.
echo ========================================
echo   INSTALLATION COMPLETED SUCCESSFULLY!
echo ========================================
echo.
echo Your PISONET server is now running on Orange Pi One.
echo.
echo IMPORTANT NEXT STEPS:
echo 1. Update GPIO pin numbers in /root/project_centralize/server.py
echo 2. Connect hardware (coin sensor and relay) to GPIO pins
echo 3. Access admin panel: http://%ORANGE_PI_IP%/admin
echo 4. Install client software on workstations
echo.
echo Useful commands:
echo - Check status: ssh %ORANGE_PI_USER%@%ORANGE_PI_IP% "systemctl status pisonet"
echo - View logs: ssh %ORANGE_PI_USER%@%ORANGE_PI_IP% "journalctl -u pisonet -f"
echo - Restart service: ssh %ORANGE_PI_USER%@%ORANGE_PI_IP% "systemctl restart pisonet"
echo.
pause