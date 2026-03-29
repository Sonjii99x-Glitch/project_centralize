# Centralized PISONET Server
# Orange Pi One setup for coin-operated internet cafe management

## Requirements
- Orange Pi One with Armbian 26.2.1 or compatible OS
- Python 3.7+
- GPIO pins: Coin sensor on BCM pin 3, Relay on BCM pin 5
- Root SSH access (user: root, password: 1234)

## Installation on Orange Pi One
1. SSH into Orange Pi: `ssh root@<opi_ip>` (password: 1234)
2. Update system: `apt update && apt upgrade -y`
3. Install Python and pip: `apt install python3 python3-pip -y`
4. Install GPIO library: `apt install python3-gpiozero -y`
5. Clone or copy the project files to the OPI (e.g., /root/pisonet/)
6. Install dependencies: `pip3 install -r requirements.txt`
7. Copy systemd service: `cp pisonet.service /etc/systemd/system/`
8. Enable and start: `systemctl enable pisonet && systemctl start pisonet`

## Client Setup
1. On each client PC (Windows/Linux), install Python 3.
2. Install dependencies: `pip install requests keyboard`
3. For sound effects on Windows: `pip install winsound` (built-in)
4. Copy client.py to client PC.
5. Run: `python client.py <server_ip>` (e.g., python client.py 192.168.1.100)

## Client Features
- Fullscreen lockscreen with gradient background
- Animated INSERT COIN button with sound effects
- Real-time credit display
- Session timer window when unlocked
- Security: topmost window, prevents closing/right-click
- Hotkey F10 for admin panel (password: 1234)

## Features
- Centralized coin management for multiple clients (up to 50+)
- Web admin dashboard at http://<opi_ip>/admin
- Client-side locking with INSERT COIN button
- Hotkey F10 for client admin panel (password: 1234)
- Configurable coin value (default: 10 minutes per peso)
- DHCP compatible - works with any IP assigned by router

## Hardware Wiring
- Connect coin sensor signal to GPIO pin 3 (BCM)
- Connect relay control to GPIO pin 5 (BCM), active low to enable coinslot power

## Usage
- Access admin panel: http://<opi_ip>/admin
- Clients register automatically on startup
- Insert coin: Click INSERT COIN button on client, insert coin, credit added
- Admin can change coin value via web interface
