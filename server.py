from flask import Flask, request, jsonify, render_template_string, send_from_directory, redirect, url_for
import sqlite3
import gpiozero
import gpiozero.pins.native
import threading
import time
import psutil
import os
import json
from datetime import datetime, timedelta
import logging
import secrets

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Initialize Flask app
app = Flask(__name__)
app.secret_key = secrets.token_hex(32)

# GPIO setup
gpiozero.Device.pin_factory = gpiozero.pins.native.NativeFactory()
coin_pin = None
relay_pin = None

# Database setup
DB_PATH = 'data/pisonet.db'

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        c = conn.cursor()

        # Config table
        c.execute('''CREATE TABLE IF NOT EXISTS config (
            key TEXT PRIMARY KEY,
            value TEXT,
            description TEXT
        )''')

        # Clients table
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

        # Sessions table
        c.execute('''CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER,
            start_time DATETIME DEFAULT CURRENT_TIMESTAMP,
            end_time DATETIME,
            duration INTEGER,
            credit_used REAL,
            FOREIGN KEY (client_id) REFERENCES clients(id)
        )''')

        # Transactions table
        c.execute('''CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER,
            amount REAL,
            type TEXT,
            description TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (client_id) REFERENCES clients(id)
        )''')

        # System logs table
        c.execute('''CREATE TABLE IF NOT EXISTS system_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            level TEXT,
            message TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )''')

        # Insert default config
        default_configs = [
            ('coin_value', '10', 'Minutes per peso'),
            ('max_credit', '480', 'Maximum credit per client (minutes)'),
            ('session_timeout', '1440', 'Session timeout (minutes)'),
            ('cleanup_interval', '60', 'Inactive client cleanup (minutes)'),
            ('relay_pin', '5', 'GPIO pin for relay control'),
            ('coin_pin', '3', 'GPIO pin for coin sensor'),
            ('admin_password', '1234', 'Admin panel password'),
            ('system_name', 'PISONET Cafe', 'System display name'),
            ('timezone', 'Asia/Manila', 'System timezone'),
            ('maintenance_mode', 'false', 'Maintenance mode flag'),
            ('setup_complete', 'false', 'Setup wizard completion flag')
        ]

        for key, value, desc in default_configs:
            c.execute('INSERT OR IGNORE INTO config (key, value, description) VALUES (?, ?, ?)',
                     (key, value, desc))

        conn.commit()

def get_config(key, default=None):
    with get_db() as conn:
        c = conn.cursor()
        c.execute('SELECT value FROM config WHERE key = ?', (key,))
        row = c.fetchone()
        return row[0] if row else default

def set_config(key, value):
    with get_db() as conn:
        c = conn.cursor()
        c.execute('INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)', (key, value))
        conn.commit()

def log_system(level, message):
    with get_db() as conn:
        c = conn.cursor()
        c.execute('INSERT INTO system_logs (level, message) VALUES (?, ?)', (level, message))
        conn.commit()

# Initialize database
init_db()

# GPIO initialization
def init_gpio():
    global coin_pin, relay_pin
    try:
        # Check if we're on a Raspberry Pi
        try:
            with open('/proc/device-tree/model', 'r') as f:
                model = f.read().lower()
                is_pi = 'raspberry pi' in model or 'orange pi' in model
        except:
            is_pi = False

        if not is_pi:
            print("Not running on a Pi - GPIO functionality disabled")
            coin_pin = None
            relay_pin = None
            return

        coin_pin_num = int(get_config('coin_pin', 3))
        relay_pin_num = int(get_config('relay_pin', 5))

        coin_pin = gpiozero.Button(coin_pin_num)
        relay_pin = gpiozero.OutputDevice(relay_pin_num, active_high=False)

        coin_pin.when_pressed = coin_inserted
        log_system('INFO', f'GPIO initialized: coin_pin={coin_pin_num}, relay_pin={relay_pin_num}')
    except Exception as e:
        log_system('ERROR', f'GPIO initialization failed: {str(e)}')
        coin_pin = None
        relay_pin = None

def coin_inserted():
    try:
        # Find client in queue (first in queue gets credit)
        with get_db() as conn:
            c = conn.cursor()
            c.execute('SELECT client_id FROM clients WHERE status = ? ORDER BY last_seen DESC LIMIT 1',
                     ('waiting_for_coin',))
            row = c.fetchone()

            if row:
                client_id = row[0]
                coin_value = float(get_config('coin_value', 10))

                # Update client credit
                c.execute('UPDATE clients SET credit = credit + ?, total_credit = total_credit + ?, status = ? WHERE client_id = ?',
                         (coin_value, coin_value, 'active', client_id))

                # Log transaction
                c.execute('INSERT INTO transactions (client_id, amount, type, description) VALUES (?, ?, ?, ?)',
                         (client_id, coin_value, 'credit', f'Coin inserted - {coin_value} minutes'))

                # Update stats
                current_coins = int(get_config('total_coins', 0)) + 1
                current_revenue = float(get_config('total_revenue', 0)) + 1
                set_config('total_coins', str(current_coins))
                set_config('total_revenue', str(current_revenue))

                conn.commit()

                # Turn off relay
                if relay_pin:
                    relay_pin.off()

                log_system('INFO', f'Coin inserted for client {client_id}: +{coin_value} minutes')
            else:
                log_system('WARN', 'Coin inserted but no client waiting')

    except Exception as e:
        log_system('ERROR', f'Coin processing error: {str(e)}')

# Background tasks
def credit_decrement():
    while True:
        try:
            with get_db() as conn:
                c = conn.cursor()
                # Decrement active client credits
                c.execute('UPDATE clients SET credit = MAX(0, credit - 1) WHERE credit > 0 AND status = ?', ('active',))
                # Mark clients with no credit as inactive
                c.execute('UPDATE clients SET status = ? WHERE credit <= 0 AND status = ?', ('inactive', 'active'))
                conn.commit()
        except Exception as e:
            log_system('ERROR', f'Credit decrement error: {str(e)}')

        time.sleep(60)  # Run every minute

def cleanup_inactive_clients():
    while True:
        try:
            cleanup_interval = int(get_config('cleanup_interval', 60))
            cutoff = datetime.now() - timedelta(minutes=cleanup_interval)

            with get_db() as conn:
                c = conn.cursor()
                c.execute('DELETE FROM clients WHERE last_seen < ? AND status != ?', (cutoff, 'active'))
                deleted_count = c.rowcount
                if deleted_count > 0:
                    conn.commit()
                    log_system('INFO', f'Cleaned up {deleted_count} inactive clients')
        except Exception as e:
            log_system('ERROR', f'Cleanup error: {str(e)}')

        time.sleep(300)  # Run every 5 minutes

# Start background threads
threading.Thread(target=credit_decrement, daemon=True).start()
threading.Thread(target=cleanup_inactive_clients, daemon=True).start()

# Initialize GPIO after config is loaded
init_gpio()

# HTML Templates
SETUP_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PISONET Setup Wizard</title>
    <style>
        body { font-family: Arial, sans-serif; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); margin: 0; padding: 20px; min-height: 100vh; }
        .container { max-width: 800px; margin: 0 auto; background: white; border-radius: 10px; box-shadow: 0 10px 30px rgba(0,0,0,0.3); overflow: hidden; }
        .header { background: #2c3e50; color: white; padding: 20px; text-align: center; }
        .content { padding: 30px; }
        .form-group { margin-bottom: 20px; }
        label { display: block; margin-bottom: 5px; font-weight: bold; color: #333; }
        input, select { width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 5px; font-size: 16px; }
        .btn { background: #3498db; color: white; padding: 12px 30px; border: none; border-radius: 5px; cursor: pointer; font-size: 16px; margin: 10px 5px 10px 0; }
        .btn:hover { background: #2980b9; }
        .btn-primary { background: #27ae60; }
        .btn-primary:hover { background: #229954; }
        .step { margin-bottom: 30px; padding: 20px; border-left: 4px solid #3498db; background: #f8f9fa; }
        .step h3 { margin-top: 0; color: #2c3e50; }
        .progress { background: #ecf0f1; border-radius: 10px; height: 20px; margin: 20px 0; }
        .progress-bar { background: #3498db; height: 100%; border-radius: 10px; transition: width 0.3s; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 PISONET Setup Wizard</h1>
            <p>Welcome to the PISONET centralized internet cafe system</p>
        </div>
        <div class="content">
            <div class="progress">
                <div class="progress-bar" style="width: {{ progress }}%"></div>
            </div>

            <form method="post" action="/setup">
                <div class="step">
                    <h3>📋 Basic Configuration</h3>
                    <div class="form-group">
                        <label for="system_name">System Name:</label>
                        <input type="text" id="system_name" name="system_name" value="{{ config.system_name }}" required>
                    </div>
                    <div class="form-group">
                        <label for="admin_password">Admin Password:</label>
                        <input type="password" id="admin_password" name="admin_password" value="{{ config.admin_password }}" required>
                    </div>
                    <div class="form-group">
                        <label for="timezone">Timezone:</label>
                        <select id="timezone" name="timezone">
                            <option value="Asia/Manila" {% if config.timezone == 'Asia/Manila' %}selected{% endif %}>Asia/Manila</option>
                            <option value="UTC" {% if config.timezone == 'UTC' %}selected{% endif %}>UTC</option>
                        </select>
                    </div>
                </div>

                <div class="step">
                    <h3>💰 Coin Configuration</h3>
                    <div class="form-group">
                        <label for="coin_value">Minutes per Peso:</label>
                        <input type="number" id="coin_value" name="coin_value" value="{{ config.coin_value }}" min="1" max="60" required>
                    </div>
                    <div class="form-group">
                        <label for="max_credit">Maximum Credit (minutes):</label>
                        <input type="number" id="max_credit" name="max_credit" value="{{ config.max_credit }}" min="60" max="1440" required>
                    </div>
                </div>

                <div class="step">
                    <h3>🔌 Hardware Configuration</h3>
                    <p><strong>Important:</strong> Verify GPIO pin numbers for your Orange Pi One board!</p>
                    <div class="form-group">
                        <label for="coin_pin">Coin Sensor GPIO Pin:</label>
                        <input type="number" id="coin_pin" name="coin_pin" value="{{ config.coin_pin }}" min="0" max="40" required>
                        <small>Check your Orange Pi One pinout diagram</small>
                    </div>
                    <div class="form-group">
                        <label for="relay_pin">Relay Control GPIO Pin:</label>
                        <input type="number" id="relay_pin" name="relay_pin" value="{{ config.relay_pin }}" min="0" max="40" required>
                        <small>Check your Orange Pi One pinout diagram</small>
                    </div>
                </div>

                <div class="step">
                    <h3>⚙️ System Settings</h3>
                    <div class="form-group">
                        <label for="session_timeout">Session Timeout (minutes):</label>
                        <input type="number" id="session_timeout" name="session_timeout" value="{{ config.session_timeout }}" min="60" max="10080" required>
                    </div>
                    <div class="form-group">
                        <label for="cleanup_interval">Cleanup Interval (minutes):</label>
                        <input type="number" id="cleanup_interval" name="cleanup_interval" value="{{ config.cleanup_interval }}" min="30" max="1440" required>
                    </div>
                </div>

                <button type="submit" class="btn btn-primary">Complete Setup</button>
            </form>
        </div>
    </div>
</body>
</html>
"""

ADMIN_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PISONET Admin Panel</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #f5f7fa; }
        .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .header h1 { margin-bottom: 10px; }
        .nav { background: white; padding: 10px 20px; border-bottom: 1px solid #e1e5e9; }
        .nav-tabs { display: flex; list-style: none; }
        .nav-tab { padding: 10px 20px; cursor: pointer; border-bottom: 3px solid transparent; }
        .nav-tab.active { border-bottom-color: #3498db; color: #3498db; font-weight: bold; }
        .container { display: flex; min-height: calc(100vh - 120px); }
        .sidebar { width: 250px; background: white; padding: 20px; border-right: 1px solid #e1e5e9; }
        .sidebar h3 { margin-bottom: 15px; color: #2c3e50; }
        .sidebar ul { list-style: none; }
        .sidebar li { padding: 8px 0; cursor: pointer; border-radius: 5px; padding-left: 10px; }
        .sidebar li:hover { background: #f8f9fa; }
        .sidebar li.active { background: #3498db; color: white; }
        .main { flex: 1; padding: 20px; }
        .card { background: white; border-radius: 8px; padding: 20px; margin-bottom: 20px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .card h3 { margin-bottom: 15px; color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 5px; }
        .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; }
        .stat-card { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 8px; text-align: center; }
        .stat-value { font-size: 2em; font-weight: bold; margin: 10px 0; }
        .table { width: 100%; border-collapse: collapse; margin-top: 15px; }
        .table th, .table td { padding: 12px; text-align: left; border-bottom: 1px solid #e1e5e9; }
        .table th { background: #f8f9fa; font-weight: bold; }
        .btn { padding: 8px 16px; border: none; border-radius: 5px; cursor: pointer; margin: 2px; }
        .btn-primary { background: #3498db; color: white; }
        .btn-danger { background: #e74c3c; color: white; }
        .btn-success { background: #27ae60; color: white; }
        .form-group { margin-bottom: 15px; }
        .form-group label { display: block; margin-bottom: 5px; font-weight: bold; }
        .form-group input, .form-group select { width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; }
        .modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); z-index: 1000; }
        .modal-content { background: white; margin: 10% auto; padding: 20px; border-radius: 8px; width: 90%; max-width: 500px; }
        .status-online { color: #27ae60; }
        .status-offline { color: #e74c3c; }
        .status-waiting { color: #f39c12; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🎮 PISONET Admin Panel</h1>
        <p>Centralized Internet Cafe Management System</p>
    </div>

    <div class="nav">
        <ul class="nav-tabs">
            <li class="nav-tab active" onclick="showTab('dashboard')">Dashboard</li>
            <li class="nav-tab" onclick="showTab('clients')">Clients</li>
            <li class="nav-tab" onclick="showTab('settings')">Settings</li>
            <li class="nav-tab" onclick="showTab('logs')">System Logs</li>
        </ul>
    </div>

    <div class="container">
        <div class="sidebar">
            <h3>Quick Actions</h3>
            <ul>
                <li onclick="clearAllCredits()">Clear All Credits</li>
                <li onclick="restartService()">Restart Service</li>
                <li onclick="backupDatabase()">Backup Database</li>
                <li onclick="showModal('maintenance')">Maintenance Mode</li>
            </ul>

            <h3>System Status</h3>
            <ul>
                <li class="{{ 'status-online' if gpio_status.coin_pin else 'status-offline' }}">Coin Sensor: {{ 'Online' if gpio_status.coin_pin else 'Offline' }}</li>
                <li class="{{ 'status-online' if gpio_status.relay_pin else 'status-offline' }}">Relay: {{ 'Online' if gpio_status.relay_pin else 'Offline' }}</li>
                <li>CPU: {{ system_stats.cpu }}%</li>
                <li>RAM: {{ system_stats.ram }}%</li>
                <li>Uptime: {{ system_stats.uptime }}</li>
            </ul>
        </div>

        <div class="main">
            <!-- Dashboard Tab -->
            <div id="dashboard-tab" class="tab-content">
                <div class="stats">
                    <div class="stat-card">
                        <h4>Active Clients</h4>
                        <div class="stat-value">{{ stats.active_clients }}</div>
                    </div>
                    <div class="stat-card">
                        <h4>Total Revenue</h4>
                        <div class="stat-value">₱{{ stats.total_revenue }}</div>
                    </div>
                    <div class="stat-card">
                        <h4>Coins Today</h4>
                        <div class="stat-value">{{ stats.coins_today }}</div>
                    </div>
                    <div class="stat-card">
                        <h4>System Uptime</h4>
                        <div class="stat-value">{{ system_stats.uptime }}</div>
                    </div>
                </div>

                <div class="card">
                    <h3>Recent Activity</h3>
                    <table class="table">
                        <thead>
                            <tr>
                                <th>Time</th>
                                <th>Client</th>
                                <th>Action</th>
                                <th>Amount</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% for transaction in recent_transactions %}
                            <tr>
                                <td>{{ transaction.timestamp }}</td>
                                <td>{{ transaction.client_id }}</td>
                                <td>{{ transaction.description }}</td>
                                <td>{{ transaction.amount }}</td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
            </div>

            <!-- Clients Tab -->
            <div id="clients-tab" class="tab-content" style="display: none;">
                <div class="card">
                    <h3>Connected Clients ({{ clients|length }})</h3>
                    <table class="table">
                        <thead>
                            <tr>
                                <th>ID</th>
                                <th>IP Address</th>
                                <th>Hostname</th>
                                <th>Credit (min)</th>
                                <th>Status</th>
                                <th>Last Seen</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% for client in clients %}
                            <tr>
                                <td>{{ client.client_id }}</td>
                                <td>{{ client.ip_address }}</td>
                                <td>{{ client.hostname or 'Unknown' }}</td>
                                <td>{{ client.credit }}</td>
                                <td class="status-{{ client.status }}">{{ client.status }}</td>
                                <td>{{ client.last_seen }}</td>
                                <td>
                                    <button class="btn btn-primary" onclick="addCredit('{{ client.client_id }}')">Add Credit</button>
                                    <button class="btn btn-danger" onclick="resetCredit('{{ client.client_id }}')">Reset</button>
                                    <button class="btn btn-danger" onclick="banClient('{{ client.client_id }}')">Ban</button>
                                </td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
            </div>

            <!-- Settings Tab -->
            <div id="settings-tab" class="tab-content" style="display: none;">
                <div class="card">
                    <h3>System Configuration</h3>
                    <form id="settings-form">
                        <div class="form-group">
                            <label>System Name:</label>
                            <input type="text" name="system_name" value="{{ config.system_name }}">
                        </div>
                        <div class="form-group">
                            <label>Coin Value (minutes per peso):</label>
                            <input type="number" name="coin_value" value="{{ config.coin_value }}" min="1">
                        </div>
                        <div class="form-group">
                            <label>Maximum Credit (minutes):</label>
                            <input type="number" name="max_credit" value="{{ config.max_credit }}" min="60">
                        </div>
                        <div class="form-group">
                            <label>Coin Sensor GPIO Pin:</label>
                            <input type="number" name="coin_pin" value="{{ config.coin_pin }}" min="0" max="40">
                        </div>
                        <div class="form-group">
                            <label>Relay GPIO Pin:</label>
                            <input type="number" name="relay_pin" value="{{ config.relay_pin }}" min="0" max="40">
                        </div>
                        <div class="form-group">
                            <label>Admin Password:</label>
                            <input type="password" name="admin_password" value="{{ config.admin_password }}">
                        </div>
                        <button type="submit" class="btn btn-primary">Save Settings</button>
                    </form>
                </div>
            </div>

            <!-- Logs Tab -->
            <div id="logs-tab" class="tab-content" style="display: none;">
                <div class="card">
                    <h3>System Logs</h3>
                    <div id="logs-container">
                        {% for log in system_logs %}
                        <div class="log-entry log-{{ log.level.lower() }}">
                            <span class="timestamp">{{ log.timestamp }}</span>
                            <span class="level">[{{ log.level }}]</span>
                            <span class="message">{{ log.message }}</span>
                        </div>
                        {% endfor %}
                    </div>
                    <button class="btn btn-primary" onclick="refreshLogs()">Refresh Logs</button>
                </div>
            </div>
        </div>
    </div>

    <!-- Modals -->
    <div id="modal" class="modal">
        <div class="modal-content">
            <h3 id="modal-title">Modal Title</h3>
            <div id="modal-body">Modal content</div>
            <button class="btn btn-primary" onclick="closeModal()">Close</button>
        </div>
    </div>

    <script>
        let currentTab = 'dashboard';

        function showTab(tabName) {
            document.querySelectorAll('.tab-content').forEach(tab => tab.style.display = 'none');
            document.querySelectorAll('.nav-tab').forEach(tab => tab.classList.remove('active'));
            document.querySelectorAll('.sidebar li').forEach(li => li.classList.remove('active'));

            document.getElementById(tabName + '-tab').style.display = 'block';
            document.querySelector(`[onclick="showTab('${tabName}')"]`).classList.add('active');
            currentTab = tabName;
        }

        function showModal(title, content) {
            document.getElementById('modal-title').textContent = title;
            document.getElementById('modal-body').innerHTML = content;
            document.getElementById('modal').style.display = 'block';
        }

        function closeModal() {
            document.getElementById('modal').style.display = 'none';
        }

        // API functions
        async function apiRequest(endpoint, data = {}) {
            const response = await fetch('/api/' + endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
            return response.json();
        }

        async function clearAllCredits() {
            if (confirm('Clear all client credits?')) {
                const result = await apiRequest('clear_all_credits');
                alert(result.message);
                location.reload();
            }
        }

        async function restartService() {
            if (confirm('Restart PISONET service?')) {
                const result = await apiRequest('restart_service');
                alert(result.message);
            }
        }

        async function backupDatabase() {
            const result = await apiRequest('backup_database');
            alert(result.message);
        }

        async function addCredit(clientId) {
            const amount = prompt('Enter credit amount (minutes):');
            if (amount && amount > 0) {
                const result = await apiRequest('add_credit', { client_id: clientId, amount: parseInt(amount) });
                alert(result.message);
                location.reload();
            }
        }

        async function resetCredit(clientId) {
            if (confirm('Reset credit for this client?')) {
                const result = await apiRequest('reset_credit', { client_id: clientId });
                alert(result.message);
                location.reload();
            }
        }

        async function banClient(clientId) {
            if (confirm('Ban this client?')) {
                const result = await apiRequest('ban_client', { client_id: clientId });
                alert(result.message);
                location.reload();
            }
        }

        async function refreshLogs() {
            const response = await fetch('/api/get_logs');
            const logs = await response.json();
            const container = document.getElementById('logs-container');
            container.innerHTML = logs.map(log =>
                `<div class="log-entry log-${log.level.toLowerCase()}">
                    <span class="timestamp">${log.timestamp}</span>
                    <span class="level">[${log.level}]</span>
                    <span class="message">${log.message}</span>
                </div>`
            ).join('');
        }

        // Settings form
        document.getElementById('settings-form').addEventListener('submit', async (e) => {
            e.preventDefault();
            const formData = new FormData(e.target);
            const data = Object.fromEntries(formData);
            const result = await apiRequest('update_settings', data);
            alert(result.message);
        });

        // Auto-refresh dashboard every 30 seconds
        setInterval(() => {
            if (currentTab === 'dashboard') {
                location.reload();
            }
        }, 30000);
    </script>
</body>
</html>
"""

CLIENT_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PISONET Client</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; overflow: hidden; }
        .container { display: flex; flex-direction: column; height: 100vh; }
        .header { text-align: center; padding: 20px; background: rgba(0,0,0,0.3); }
        .header h1 { font-size: 3em; margin-bottom: 10px; }
        .status { font-size: 1.2em; opacity: 0.9; }
        .main { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 20px; }
        .credit-display { font-size: 4em; font-weight: bold; margin: 20px 0; text-shadow: 2px 2px 4px rgba(0,0,0,0.5); }
        .message { font-size: 1.5em; text-align: center; margin: 20px 0; opacity: 0.9; }
        .insert-coin { text-align: center; }
        .coin-button { font-size: 2em; padding: 20px 40px; background: linear-gradient(45deg, #FFD700, #FFA500); color: black; border: none; border-radius: 15px; cursor: pointer; box-shadow: 0 8px 15px rgba(0,0,0,0.3); transition: all 0.3s; margin: 20px; }
        .coin-button:hover { transform: translateY(-2px); box-shadow: 0 12px 20px rgba(0,0,0,0.4); }
        .coin-button:active { transform: translateY(0); }
        .coin-button:disabled { opacity: 0.6; cursor: not-allowed; }
        .timer { font-size: 2em; margin: 20px 0; }
        .admin-btn { position: absolute; top: 10px; right: 10px; padding: 10px 20px; background: rgba(255,255,255,0.2); border: 1px solid white; border-radius: 5px; color: white; cursor: pointer; }
        .admin-btn:hover { background: rgba(255,255,255,0.3); }
        .pulse { animation: pulse 2s infinite; }
        @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.5; } 100% { opacity: 1; } }
        .fade-in { animation: fadeIn 0.5s; }
        @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>PISONET</h1>
            <div class="status" id="status">Connecting...</div>
        </div>

        <div class="main">
            <div class="credit-display" id="credit">0:00</div>
            <div class="message" id="message">Welcome to PISONET Internet Cafe</div>

            <div class="insert-coin" id="coin-section">
                <button class="coin-button pulse" id="coin-btn" onclick="requestCoin()">
                    🪙 INSERT COIN
                </button>
                <div class="message">Click to enable coin slot</div>
            </div>

            <div class="timer" id="timer" style="display: none;">
                Session Time: <span id="time-left">0:00</span>
            </div>
        </div>

        <button class="admin-btn" onclick="showAdmin()">Admin</button>
    </div>

    <script>
        let clientId = localStorage.getItem('pisonet_client_id') || generateClientId();
        let credit = 0;
        let timerInterval;
        let isLocked = true;

        function generateClientId() {
            const id = 'client_' + Math.random().toString(36).substr(2, 9);
            localStorage.setItem('pisonet_client_id', id);
            return id;
        }

        async function apiRequest(endpoint, data = {}) {
            try {
                const response = await fetch('/api/' + endpoint, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ client_id: clientId, ...data })
                });
                return await response.json();
            } catch (error) {
                console.error('API request failed:', error);
                return { success: false, message: 'Connection failed' };
            }
        }

        async function register() {
            const result = await apiRequest('register');
            if (result.success) {
                document.getElementById('status').textContent = 'Connected';
                document.getElementById('status').style.color = '#27ae60';
            } else {
                document.getElementById('status').textContent = 'Connection Failed';
                document.getElementById('status').style.color = '#e74c3c';
            }
        }

        async function checkCredit() {
            const result = await apiRequest('get_credit');
            if (result.success) {
                const newCredit = result.credit || 0;
                if (newCredit !== credit) {
                    credit = newCredit;
                    updateDisplay();

                    if (credit > 0 && isLocked) {
                        unlock();
                    } else if (credit <= 0 && !isLocked) {
                        lock();
                    }
                }
            }
        }

        function updateDisplay() {
            const minutes = Math.floor(credit);
            const seconds = Math.floor((credit % 1) * 60);
            document.getElementById('credit').textContent = `${minutes}:${seconds.toString().padStart(2, '0')}`;

            if (credit > 0) {
                document.getElementById('message').textContent = 'Session Active - Enjoy your internet!';
                document.getElementById('coin-section').style.display = 'none';
                document.getElementById('timer').style.display = 'block';
            } else {
                document.getElementById('message').textContent = 'Please insert coin to start your session';
                document.getElementById('coin-section').style.display = 'block';
                document.getElementById('timer').style.display = 'none';
            }
        }

        function lock() {
            isLocked = true;
            document.body.style.background = 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)';
            clearInterval(timerInterval);
        }

        function unlock() {
            isLocked = false;
            document.body.style.background = 'linear-gradient(135deg, #27ae60 0%, #2ecc71 100%)';
            startTimer();
        }

        function startTimer() {
            clearInterval(timerInterval);
            timerInterval = setInterval(() => {
                if (credit > 0) {
                    credit -= 1/60; // Decrement by 1 second
                    updateDisplay();
                } else {
                    lock();
                }
            }, 1000);
        }

        async function requestCoin() {
            const btn = document.getElementById('coin-btn');
            btn.disabled = true;
            btn.textContent = 'REQUESTING...';
            btn.classList.remove('pulse');

            const result = await apiRequest('request_coin');
            if (result.success) {
                document.getElementById('message').textContent = 'Coin slot enabled - Please insert coin';
                setTimeout(() => {
                    btn.disabled = false;
                    btn.textContent = '🪙 INSERT COIN';
                    btn.classList.add('pulse');
                }, 3000);
            } else {
                document.getElementById('message').textContent = 'Failed to enable coin slot - Please try again';
                btn.disabled = false;
                btn.textContent = '🪙 INSERT COIN';
                btn.classList.add('pulse');
            }
        }

        function showAdmin() {
            const password = prompt('Enter admin password:');
            if (password === '1234') { // In production, this should be fetched from server
                window.open('/admin', '_blank');
            } else {
                alert('Incorrect password');
            }
        }

        // Initialize
        register();
        setInterval(checkCredit, 5000); // Check every 5 seconds
        checkCredit(); // Initial check

        // Prevent common exit methods
        document.addEventListener('keydown', (e) => {
            // Prevent Alt+F4, Ctrl+W, etc.
            if ((e.altKey && e.key === 'F4') ||
                (e.ctrlKey && e.key === 'w') ||
                (e.ctrlKey && e.key === 'W')) {
                e.preventDefault();
            }
        });

        // Prevent right-click
        document.addEventListener('contextmenu', (e) => {
            e.preventDefault();
        });

        // Keep window focused and prevent minimization
        window.addEventListener('blur', () => {
            setTimeout(() => window.focus(), 100);
        });

        // Fullscreen mode
        if (!document.fullscreenElement) {
            document.documentElement.requestFullscreen().catch(() => {
                // Fallback for browsers that don't support fullscreen
            });
        }
    </script>
</body>
</html>
"""

# Routes
@app.route('/')
def index():
    if get_config('setup_complete', 'false') == 'false':
        return redirect('/setup')
    return render_template_string(CLIENT_HTML)

@app.route('/setup', methods=['GET', 'POST'])
def setup():
    if request.method == 'POST':
        # Save configuration
        config_data = request.form.to_dict()
        for key, value in config_data.items():
            set_config(key, value)

        set_config('setup_complete', 'true')

        # Reinitialize GPIO with new pins
        init_gpio()

        log_system('INFO', 'Setup completed successfully')
        return redirect('/admin')

    # Get current config for template
    config = {}
    with get_db() as conn:
        c = conn.cursor()
        c.execute('SELECT key, value FROM config')
        for row in c.fetchall():
            config[row[0]] = row[1]

    progress = 25  # Basic setup progress
    return render_template_string(SETUP_HTML, config=config, progress=progress)

@app.route('/admin')
def admin():
    # Simple password check (in production, use proper authentication)
    auth = request.args.get('auth')
    if auth != get_config('admin_password', '1234'):
        return '''
        <form method="get">
            <label>Admin Password: <input type="password" name="auth"></label>
            <button type="submit">Login</button>
        </form>
        '''

    # Gather data for admin panel
    with get_db() as conn:
        c = conn.cursor()

        # Stats
        c.execute('SELECT COUNT(*) FROM clients WHERE status = ?', ('active',))
        active_clients = c.fetchone()[0]

        total_revenue = get_config('total_revenue', '0')

        # Recent transactions
        c.execute('''SELECT t.*, c.ip_address
                    FROM transactions t
                    JOIN clients c ON t.client_id = c.id
                    ORDER BY t.timestamp DESC LIMIT 10''')
        recent_transactions = c.fetchall()

        # Clients
        c.execute('SELECT * FROM clients ORDER BY last_seen DESC')
        clients = c.fetchall()

        # System logs
        c.execute('SELECT * FROM system_logs ORDER BY timestamp DESC LIMIT 50')
        system_logs = c.fetchall()

    # System stats
    system_stats = {
        'cpu': psutil.cpu_percent(),
        'ram': psutil.virtual_memory().percent,
        'uptime': f"{int(psutil.boot_time() / 3600)}h {int((psutil.boot_time() % 3600) / 60)}m"
    }

    # GPIO status
    gpio_status = {
        'coin_pin': coin_pin is not None,
        'relay_pin': relay_pin is not None
    }

    # Config
    config = {}
    with get_db() as conn:
        c = conn.cursor()
        c.execute('SELECT key, value FROM config')
        for row in c.fetchall():
            config[row[0]] = row[1]

    stats = {
        'active_clients': active_clients,
        'total_revenue': total_revenue,
        'coins_today': get_config('total_coins', '0')
    }

    return render_template_string(ADMIN_HTML,
                                stats=stats,
                                clients=clients,
                                system_logs=system_logs,
                                system_stats=system_stats,
                                gpio_status=gpio_status,
                                config=config,
                                recent_transactions=recent_transactions)

# API Routes
@app.route('/api/register', methods=['POST'])
def api_register():
    data = request.get_json()
    client_id = data.get('client_id')
    ip = request.remote_addr

    try:
        with get_db() as conn:
            c = conn.cursor()
            c.execute('''INSERT OR REPLACE INTO clients
                        (client_id, ip_address, last_seen, status)
                        VALUES (?, ?, ?, ?)''',
                     (client_id, ip, datetime.now(), 'waiting_for_coin'))
            conn.commit()

        log_system('INFO', f'Client registered: {client_id} from {ip}')
        return jsonify({'success': True, 'message': 'Registered successfully'})
    except Exception as e:
        log_system('ERROR', f'Registration failed: {str(e)}')
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/get_credit', methods=['POST'])
def api_get_credit():
    data = request.get_json()
    client_id = data.get('client_id')

    try:
        with get_db() as conn:
            c = conn.cursor()
            c.execute('SELECT credit FROM clients WHERE client_id = ?', (client_id,))
            row = c.fetchone()
            credit = row[0] if row else 0

        return jsonify({'success': True, 'credit': credit})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/request_coin', methods=['POST'])
def api_request_coin():
    data = request.get_json()
    client_id = data.get('client_id')

    try:
        with get_db() as conn:
            c = conn.cursor()
            c.execute('UPDATE clients SET status = ? WHERE client_id = ?',
                     ('waiting_for_coin', client_id))
            conn.commit()

        # Enable relay for coin insertion
        if relay_pin:
            relay_pin.on()
            log_system('INFO', f'Coin request from client: {client_id}')

        return jsonify({'success': True, 'message': 'Coin slot enabled'})
    except Exception as e:
        log_system('ERROR', f'Coin request failed: {str(e)}')
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/clear_all_credits', methods=['POST'])
def api_clear_all_credits():
    try:
        with get_db() as conn:
            c = conn.cursor()
            c.execute('UPDATE clients SET credit = 0, status = ?', ('inactive',))
            conn.commit()

        log_system('INFO', 'All credits cleared by admin')
        return jsonify({'success': True, 'message': 'All credits cleared'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/restart_service', methods=['POST'])
def api_restart_service():
    try:
        os.system('systemctl restart pisonet')
        log_system('INFO', 'Service restarted by admin')
        return jsonify({'success': True, 'message': 'Service restarted'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/backup_database', methods=['POST'])
def api_backup_database():
    try:
        # Create backup
        backup_dir = 'backups'
        os.makedirs(backup_dir, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_file = f'{backup_dir}/pisonet_backup_{timestamp}.db'

        # Copy database
        import shutil
        shutil.copy('data/pisonet.db', backup_file)

        log_system('INFO', f'Database backup created: {backup_file}')
        return jsonify({'success': True, 'message': f'Backup created: {backup_file}'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/add_credit', methods=['POST'])
def api_add_credit():
    data = request.get_json()
    client_id = data.get('client_id')
    amount = data.get('amount', 0)

    try:
        with get_db() as conn:
            c = conn.cursor()
            c.execute('UPDATE clients SET credit = credit + ? WHERE client_id = ?',
                     (amount, client_id))
            c.execute('INSERT INTO transactions (client_id, amount, type, description) VALUES (?, ?, ?, ?)',
                     (client_id, amount, 'credit', f'Admin added {amount} minutes'))
            conn.commit()

        log_system('INFO', f'Admin added {amount} minutes to client {client_id}')
        return jsonify({'success': True, 'message': f'Added {amount} minutes to client'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/reset_credit', methods=['POST'])
def api_reset_credit():
    data = request.get_json()
    client_id = data.get('client_id')

    try:
        with get_db() as conn:
            c = conn.cursor()
            c.execute('UPDATE clients SET credit = 0, status = ? WHERE client_id = ?',
                     ('inactive', client_id))
            conn.commit()

        log_system('INFO', f'Credit reset for client {client_id}')
        return jsonify({'success': True, 'message': 'Credit reset'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/ban_client', methods=['POST'])
def api_ban_client():
    data = request.get_json()
    client_id = data.get('client_id')

    try:
        with get_db() as conn:
            c = conn.cursor()
            c.execute('UPDATE clients SET status = ? WHERE client_id = ?',
                     ('banned', client_id))
            conn.commit()

        log_system('INFO', f'Client banned: {client_id}')
        return jsonify({'success': True, 'message': 'Client banned'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/update_settings', methods=['POST'])
def api_update_settings():
    data = request.get_json()

    try:
        for key, value in data.items():
            set_config(key, value)

        # Reinitialize GPIO if pins changed
        init_gpio()

        log_system('INFO', 'Settings updated by admin')
        return jsonify({'success': True, 'message': 'Settings updated'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/get_logs', methods=['GET'])
def api_get_logs():
    try:
        with get_db() as conn:
            c = conn.cursor()
            c.execute('SELECT * FROM system_logs ORDER BY timestamp DESC LIMIT 100')
            logs = c.fetchall()

        return jsonify([{
            'timestamp': row[3],
            'level': row[1],
            'message': row[2]
        } for row in logs])
    except Exception as e:
        return jsonify({'error': str(e)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)