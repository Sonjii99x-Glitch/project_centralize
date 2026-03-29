# PISONET - Centralized Internet Cafe Management System

A complete coin-operated internet cafe management system designed for Orange Pi One with centralized server architecture, web-based administration, and secure client locking.

## 🚀 Features

### Server Features
- **Web-based Setup Wizard**: Easy initial configuration through browser
- **Real-time Admin Dashboard**: Monitor clients, manage credits, view analytics
- **GPIO Coin Detection**: Native GPIO support for Orange Pi One (Allwinner H3)
- **SQLite Database**: Robust data storage with comprehensive logging
- **RESTful API**: Clean API for client communication
- **Systemd Integration**: Production-ready service management
- **Automatic Backups**: Scheduled database backups
- **Firewall Integration**: Secure network configuration

### Client Features
- **Full-screen Lock Screen**: Secure workstation locking
- **Real-time Credit Display**: Live credit countdown
- **Admin Hotkeys**: Emergency admin access (Ctrl+Shift+A)
- **Network Monitoring**: Automatic server reconnection
- **System Integration**: Prevents common exit methods
- **Cross-platform**: Windows/Linux client support

### Hardware Support
- **Orange Pi One**: Primary target with GPIO coin/relay control
- **Coin Acceptors**: Standard coin mechanisms with GPIO interface
- **Relay Modules**: Control power/reset for client machines
- **Network**: Ethernet-based client communication

## 📋 Requirements

### Server Requirements
- **Hardware**: Orange Pi One or compatible SBC
- **OS**: Armbian 26.2.1 or Debian 12 (Bookworm)
- **Python**: 3.11 or higher
- **GPIO**: Physical pins for coin sensor and relay control

### Client Requirements
- **OS**: Windows 10/11 or Linux
- **Python**: 3.8 or higher
- **Network**: Ethernet connection to server
- **Display**: Full HD monitor (1920x1080 recommended)

## 🔧 Installation

### Option 1: Automated SSH Deployment (Recommended)

1. **Prepare your Orange Pi One:**
   ```bash
   # Update system
   sudo apt update && sudo apt upgrade -y

   # Install required packages
   sudo apt install -y python3 python3-pip python3-venv git curl wget
   ```

2. **Run the automated deployment script:**
   ```bash
   # Download and run deployment script
   curl -fsSL https://raw.githubusercontent.com/your-repo/pisonet/main/deploy.sh | bash
   ```

3. **Access the setup wizard:**
   - Open `http://[orange-pi-ip]:5000/setup` in your browser
   - Complete the configuration wizard
   - Access admin panel at `http://[orange-pi-ip]:5000/admin`

### Option 2: Manual Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/your-repo/pisonet.git
   cd pisonet
   ```

2. **Create virtual environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Initialize database:**
   ```bash
   python3 -c "from server import init_db; init_db()"
   ```

5. **Configure GPIO pins:**
   - Edit `server.py` and verify GPIO pin numbers for your Orange Pi One
   - Default: Coin sensor (GPIO 3), Relay control (GPIO 5)

6. **Start the server:**
   ```bash
   python3 server.py
   ```

### Option 3: Windows Development Setup

1. **Run the installer:**
   ```batch
   PISONET_Installer.bat
   ```

2. **Start the server:**
   ```batch
   python server.py
   ```

## ⚙️ Configuration

### GPIO Pin Configuration
Verify your Orange Pi One pinout diagram and update these settings:

```python
# In server.py or via web interface
coin_pin = 3    # GPIO pin connected to coin sensor
relay_pin = 5   # GPIO pin connected to relay module
```

### System Settings
Configure through the web interface (`/admin`):

- **Coin Value**: Minutes per peso (default: 10)
- **Max Credit**: Maximum credit per client (default: 480 minutes)
- **Session Timeout**: Automatic logout time (default: 1440 minutes)
- **Admin Password**: Web interface access password

## 🔌 Hardware Wiring

### Coin Acceptor Connection
```
Coin Acceptor Signal → Orange Pi GPIO 3 (Physical Pin 5)
Coin Acceptor GND   → Orange Pi GND (Physical Pin 6)
Coin Acceptor VCC   → Orange Pi 3.3V (Physical Pin 1)
```

### Relay Module Connection
```
Orange Pi GPIO 5 (Physical Pin 29) → Relay Module Signal
Orange Pi GND (Physical Pin 30)     → Relay Module GND
Orange Pi 5V (Physical Pin 2)       → Relay Module VCC
```

### Network Setup
- Connect Orange Pi to your network via Ethernet
- Configure static IP or use DHCP reservation
- Ensure all client machines can reach the server

## 🖥️ Client Setup

### Windows Client
1. **Install Python 3.8+** from python.org
2. **Download client.py** to each client machine
3. **Run the client:**
   ```batch
   python client.py http://[server-ip]:5000
   ```

### Linux Client
1. **Install dependencies:**
   ```bash
   sudo apt install python3 python3-tk python3-requests
   ```

2. **Run the client:**
   ```bash
   python3 client.py http://[server-ip]:5000
   ```

### Auto-start Configuration

#### Windows (Registry)
Create a scheduled task to run on startup:
```batch
schtasks /create /tn "PISONET Client" /tr "python C:\path\to\client.py" /sc onlogon /rl highest
```

#### Linux (Systemd)
Create `/etc/systemd/system/pisonet-client.service`:
```ini
[Unit]
Description=PISONET Client
After=network.target

[Service]
Type=simple
User=clientuser
ExecStart=/usr/bin/python3 /path/to/client.py
Restart=always

[Install]
WantedBy=multi-user.target
```

## 🔐 Security Features

### Server Security
- **Firewall**: Automatic UFW configuration
- **User Isolation**: Dedicated pisonet user
- **File Permissions**: Restricted access to data directories
- **HTTPS Ready**: SSL certificate support

### Client Security
- **Screen Lock**: Full-screen tkinter application
- **Key Blocking**: Prevents Alt+F4, Ctrl+W, etc.
- **Admin Override**: Secure admin access with password
- **Process Protection**: Automatic restart on termination

## 📊 Administration

### Web Interface
Access the admin panel at `http://[server-ip]:5000/admin`

#### Dashboard Features
- **Real-time Statistics**: Active clients, revenue, coin count
- **Client Management**: View, add credit, reset, ban clients
- **System Monitoring**: CPU, RAM, uptime, GPIO status
- **Transaction History**: Complete audit trail
- **System Logs**: Debug and error logging

#### Management Functions
- **Credit Management**: Add/remove credit manually
- **Client Control**: Reset, ban, or monitor clients
- **System Settings**: Configure rates and limits
- **Backup/Restore**: Database maintenance
- **Service Control**: Restart server components

### API Endpoints
- `POST /api/register` - Register new client
- `POST /api/get_credit` - Get client credit balance
- `POST /api/request_coin` - Enable coin slot
- `POST /api/add_credit` - Admin credit management
- `POST /api/clear_all_credits` - Emergency credit reset

## 🔧 Troubleshooting

### GPIO Issues
```bash
# Check GPIO status
gpio readall

# Test coin sensor
python3 -c "import gpiozero; pin = gpiozero.Button(3); print('Testing coin pin...'); pin.wait_for_press(); print('Coin detected!')"

# Test relay
python3 -c "import gpiozero; pin = gpiozero.OutputDevice(5); pin.on(); time.sleep(1); pin.off()"
```

### Network Issues
```bash
# Check server connectivity
curl http://localhost:5000/api/status

# Test client registration
curl -X POST http://localhost:5000/api/register -H "Content-Type: application/json" -d '{"client_id":"test"}'
```

### Database Issues
```bash
# Check database integrity
sqlite3 data/pisonet.db "PRAGMA integrity_check;"

# View recent logs
sqlite3 data/pisonet.db "SELECT * FROM system_logs ORDER BY timestamp DESC LIMIT 10;"
```

### Client Issues
- **Client won't connect**: Check firewall settings and server IP
- **Credit not updating**: Verify client ID and server API
- **Screen won't lock**: Check tkinter installation and permissions

## 📈 Monitoring & Analytics

### System Metrics
- **Revenue Tracking**: Daily/weekly/monthly earnings
- **Usage Statistics**: Peak hours, average session length
- **Client Analytics**: Most active clients, credit consumption
- **System Health**: CPU, memory, disk usage monitoring

### Log Analysis
```bash
# View recent activity
tail -f /var/log/pisonet.log

# Search for specific events
grep "coin inserted" /var/log/pisonet.log

# Count daily transactions
grep "$(date +%Y-%m-%d)" /var/log/pisonet.log | grep "credit" | wc -l
```

## 🚀 Production Deployment

### Systemd Service
```bash
# Install service
sudo cp pisonet.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable pisonet
sudo systemctl start pisonet

# Check status
sudo systemctl status pisonet
```

### Nginx Reverse Proxy
```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### SSL Configuration
```bash
# Install certbot
sudo apt install certbot python3-certbot-nginx

# Get SSL certificate
sudo certbot --nginx -d your-domain.com
```

## 📝 API Documentation

### Client Registration
```http
POST /api/register
Content-Type: application/json

{
    "client_id": "client_123",
    "hostname": "PC-01",
    "ip_address": "192.168.1.100"
}
```

### Credit Check
```http
POST /api/get_credit
Content-Type: application/json

{
    "client_id": "client_123"
}
```

### Coin Request
```http
POST /api/request_coin
Content-Type: application/json

{
    "client_id": "client_123"
}
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For support and questions:
- Check the troubleshooting section
- Review system logs
- Open an issue on GitHub
- Contact the development team

## 🔄 Changelog

### Version 7.0.0 (Current)
- Complete repository recreation
- HTML-based setup wizard
- Enhanced web admin interface
- Improved database schema
- Automated SSH deployment
- Better client application
- Comprehensive documentation

### Previous Versions
- GPIO compatibility fixes
- Virtual environment improvements
- Package management updates
- Installation automation
- Basic web interface
- Core functionality implementation

---

**PISONET** - Making internet cafe management simple, secure, and profitable.
