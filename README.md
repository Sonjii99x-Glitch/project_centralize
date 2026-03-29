# Centralized PISONET Server
# Complete Setup Guide for Orange Pi One Coin-Operated Internet Cafe System

## Quick Start (Automated Installation)

For the fastest setup, use the automated installer:

### Windows Users:
1. Download `PISONET_Installer.bat` from the repository
2. Edit the file and update the Orange Pi IP address (line 12: `set ORANGE_PI_IP=192.168.1.100`)
3. Double-click `PISONET_Installer.bat` to run
4. Follow the on-screen instructions

### Manual Installation:
If automated installation doesn't work, follow the detailed steps below.

## Overview
This project provides a centralized coin-operated internet cafe (PISONET) management system using an Orange Pi One as the server. The system supports up to 50+ client computers with automatic locking when credits expire.

### Key Features
- Centralized coin management for multiple clients
- Web-based admin dashboard
- GPIO-controlled coin detection and relay management
- Client-side fullscreen lockscreen with security features
- Real-time statistics and maintenance tools
- DHCP-compatible networking

## System Requirements

### Server (Orange Pi One)
- Orange Pi One board with 512MB RAM and 16GB storage
- Armbian 26.2.1 or compatible Debian-based OS installed
- Root SSH access (default user: root, password: 1234)
- Internet connection for initial setup
- Coin acceptor machine with signal output
- Relay module for controlling coin acceptor power

### Client Computers
- Windows 10/11 or Linux operating system
- Python 3.7 or higher
- Internet connection
- Administrative privileges for installation

### Hardware Components
- Coin sensor (connected to GPIO pin - verify Orange Pi One mapping)
- Relay module (connected to GPIO pin - verify Orange Pi One mapping)
- Ethernet cable for networking
- Power supply for Orange Pi One

**CRITICAL GPIO NOTE**: Orange Pi One uses Allwinner H3 chip with different GPIO numbering than Raspberry Pi. The code uses gpiozero's native backend for compatibility. You MUST verify the actual GPIO pin mappings for your specific Orange Pi One board revision. Use the pinout diagram from the official Orange Pi documentation.

## Step-by-Step Server Installation on Orange Pi One

### Step 1: Initial Connection
1. Power on your Orange Pi One with the Armbian OS installed
2. Connect the Orange Pi to your network via Ethernet cable
3. Find the IP address of your Orange Pi:
   - Check your router's admin panel for connected devices
   - Or use network scanning tools like `nmap` from another computer
4. Open a terminal/command prompt on your computer
5. Connect via SSH:
   ```
   ssh root@<orange_pi_ip_address>
   ```
   When prompted for password, enter: `1234`

### Step 2: System Update
1. Update the package list:
   ```
   apt update
   ```
2. Upgrade all installed packages:
   ```
   apt upgrade -y
   ```
3. Install essential tools:
   ```
   apt install curl wget git -y
   ```

### Step 3: Install Python and Dependencies
1. Install Python 3 and pip:
   ```
   apt install python3 python3-pip python3.13-venv -y
   ```
2. Create a virtual environment for the project:
   ```
   python3 -m venv pisonet_env
   ```
3. Activate the virtual environment:
   ```
   source pisonet_env/bin/activate
   ```
4. Install GPIO library system-wide (required for GPIO access):
   ```
   apt install python3-gpiozero -y
   ```
5. Install Python dependencies in the virtual environment:
   ```
   pip install -r requirements.txt
   ```
6. Deactivate the virtual environment (we'll configure the service to activate it):
   ```
   deactivate
   ```

### Step 4: Download Project Files
1. Clone the repository to your Orange Pi:
   ```
   git clone https://github.com/Sonjii99x-Glitch/project_centralize.git
   ```
2. Navigate to the project directory:
   ```
   cd project_centralize
   ```
3. Install Python dependencies:
   ```
   pip3 install -r requirements.txt
   ```

### Step 5: Hardware Wiring
**CRITICAL: Verify GPIO pin mappings before connecting anything!**

1. **Find Your Orange Pi One GPIO Pinout**:
   - Visit: https://linux-sunxi.org/Xunlong_Orange_Pi_One
   - Or search for "Orange Pi One GPIO pinout Allwinner H3"
   - Note the physical pin numbers and their GPIO functions

2. **Identify Correct GPIO Pins**:
   - Look for pins labeled as GPIO or with PA/PB/PC/PD prefixes
   - Common GPIO pins on Orange Pi One: PA0-PA21, PG0-PG13
   - Avoid power pins (3.3V, 5V) and ground pins

3. **Coin Sensor Connection**:
   - Find a suitable GPIO pin for coin sensor signal
   - Connect coin sensor signal wire → Chosen GPIO pin
   - Connect coin sensor ground → Orange Pi ground pin
   - Connect coin sensor power → 3.3V pin (check sensor specs)

4. **Relay Module Connection**:
   - Find a suitable GPIO pin for relay control
   - Connect relay control wire → Chosen GPIO pin
   - Connect relay ground → Orange Pi ground pin
   - Connect relay power → 3.3V pin (check relay specs)

5. **Coin Acceptor Power Control**:
   - Coin acceptor power input → Normally Open (NO) contacts of relay
   - Power source → Common (COM) contact of relay

**VERIFICATION STEPS**:
- Update the pin numbers in server.py (lines with gpiozero.Button() and gpiozero.OutputDevice())
- Test GPIO access: `python3 -c "import gpiozero; print('GPIO working')"`
- Check /sys/class/gpio/ directory for available GPIO pins

### Step 5.5: GPIO Pin Number Configuration
After identifying your GPIO pins, update the server.py file:

1. Edit the server configuration:
   ```
   nano /root/project_centralize/server.py
   ```

2. Find these lines (around line 10-12):
   ```python
   coin_pin = gpiozero.Button(3)  # Coin sensor - UPDATE THIS NUMBER
   relay_pin = gpiozero.OutputDevice(5, active_high=False)  # Relay - UPDATE THIS NUMBER
   ```

3. Replace the numbers (3 and 5) with your actual GPIO pin numbers from the pinout diagram

4. Save and exit: Ctrl+X, Y, Enter

**Example**: If your coin sensor should connect to physical pin 12 (GPIO PA12), and relay to physical pin 16 (GPIO PA16), change the code to:
```python
coin_pin = gpiozero.Button(12)
relay_pin = gpiozero.OutputDevice(16, active_high=False)
```

### Step 6: Configure and Start the Service
1. Copy the systemd service file:
   ```
   cp pisonet.service /etc/systemd/system/
   ```
2. Reload systemd daemon:
   ```
   systemctl daemon-reload
   ```
3. Enable the service to start on boot:
   ```
   systemctl enable pisonet
   ```
4. Start the service:
   ```
   systemctl start pisonet
   ```
5. Check service status:
   ```
   systemctl status pisonet
   ```
   You should see "active (running)"

### Step 7: Verify Server Operation
1. Find your Orange Pi's IP address:
   ```
   ip addr show
   ```
   Look for the IP address under `eth0` or similar network interface
2. Test the admin panel:
   - Open a web browser on any computer in the same network
   - Navigate to: `http://<orange_pi_ip>/admin`
   - You should see the admin dashboard

## Step-by-Step Client Installation

### For Windows Clients

#### Step 1: Install Python
1. Download Python 3.10+ from https://www.python.org/downloads/
2. Run the installer
3. **Important**: Check "Add Python to PATH" during installation
4. Click "Install Now"
5. Verify installation: Open Command Prompt and run `python --version`

#### Step 2: Install Dependencies
1. Open Command Prompt as Administrator
2. Install required packages:
   ```
   pip install requests keyboard
   ```

#### Step 3: Download and Run Client
1. Download `client.py` from the GitHub repository
2. Save it to a folder (e.g., `C:\PISONET\`)
3. Create a batch file for easy startup:
   - Create a new text file named `start_client.bat`
   - Add this content: `python client.py <server_ip>`
   - Replace `<server_ip>` with your Orange Pi's IP address
4. Run the client:
   - Double-click `start_client.bat`
   - The lockscreen should appear immediately

### For Linux Clients

#### Step 1: Install Python
1. Open terminal
2. Update package list:
   ```
   sudo apt update
   ```
3. Install Python:
   ```
   sudo apt install python3 python3-pip -y
   ```

#### Step 2: Install Dependencies
1. Install required packages:
   ```
   pip3 install requests keyboard
   ```

#### Step 3: Download and Run Client
1. Download `client.py` from the GitHub repository
2. Save it to a folder (e.g., `~/pisonet/`)
3. Make the script executable:
   ```
   chmod +x client.py
   ```
4. Run the client:
   ```
   python3 client.py <server_ip>
   ```
   Replace `<server_ip>` with your Orange Pi's IP address

## Configuration

### Server Configuration
- Access the admin panel at `http://<server_ip>/admin`
- Set coin value (minutes per peso) in the settings section
- Monitor connected clients and queue status
- View system statistics and performance

### Client Configuration
- The client automatically registers with the server on startup
- No additional configuration required
- Use F10 hotkey with password "1234" for client admin functions

## Usage Guide

### For Administrators
1. **Monitor System**: Check the admin dashboard regularly
2. **Manage Clients**: View connected clients, reset credits if needed
3. **Adjust Settings**: Change coin value as required
4. **Maintenance**: Use the maintenance tools for system management

### For Users
1. **Start Session**: Click "INSERT COIN" button on the lockscreen
2. **Insert Coin**: Place coin in the acceptor when prompted
3. **Use Computer**: The lockscreen disappears when credit is available
4. **Monitor Time**: Check the timer window for remaining session time

### Admin Panel Features
- **Settings**: Configure coin value
- **Statistics**: View total coins and revenue
- **Clients**: List all connected computers with credit status
- **Queue**: See pending coin requests
- **System Status**: Monitor server performance
- **Maintenance**: Clear credits or restart server

## Troubleshooting

### Server Issues
1. **Service not starting**:
   - Check GPIO connections
   - Verify Python dependencies: `pip3 list`
   - Check logs: `journalctl -u pisonet`

2. **Cannot access admin panel**:
   - Verify server IP address
   - Check firewall settings
   - Ensure service is running: `systemctl status pisonet`

3. **Coin detection not working**:
   - Test GPIO pins with simple script
   - Check wiring connections
   - Verify coin sensor voltage compatibility

### Client Issues
1. **Lockscreen not appearing**:
   - Ensure Python is in PATH
   - Check server connectivity: `ping <server_ip>`
   - Run as administrator (Windows)

2. **Cannot connect to server**:
   - Verify server IP address
   - Check network connectivity
   - Ensure server service is running

3. **Hotkey not working**:
   - Run client with administrative privileges
   - Check for keyboard conflicts

### Common Problems
- **High CPU usage**: Reduce client polling frequency in code
- **Memory issues**: Monitor with `htop` on server
- **Network timeouts**: Check DHCP settings and IP conflicts

## Security Notes
- Change default passwords after setup
- Keep the server in a secure location
- Regularly update the system
- Monitor access logs

## Support
For issues or questions:
1. Check the troubleshooting section above
2. Review server logs: `journalctl -u pisonet`
3. Verify all installation steps were followed
4. Check GitHub repository for updates

## License
This project is open-source. Use at your own risk.
- Admin can change coin value via web interface
