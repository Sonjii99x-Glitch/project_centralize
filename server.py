from flask import Flask, request, jsonify
import gpiozero
import sqlite3
import threading
import time
from datetime import datetime, timedelta
import psutil
import os
import subprocess

# GPIO setup
coin_pin = gpiozero.Button(3)  # Coin sensor on BCM pin 3
relay_pin = gpiozero.OutputDevice(5, active_high=False)  # Relay on BCM pin 5, active low

# Database setup
conn = sqlite3.connect('pisonet.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS config (key TEXT PRIMARY KEY, value TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS clients (id INTEGER PRIMARY KEY, ip TEXT UNIQUE, credit REAL, last_active DATETIME)''')
c.execute('''CREATE TABLE IF NOT EXISTS queue (id INTEGER PRIMARY KEY, client_id INTEGER)''')
c.execute("INSERT OR IGNORE INTO config (key, value) VALUES ('coin_value', '10')")
conn.commit()

# Coin detection
def coin_inserted():
    c = conn.cursor()
    c.execute("SELECT client_id FROM queue ORDER BY id LIMIT 1")
    row = c.fetchone()
    if row:
        client_id = row[0]
        c.execute("SELECT value FROM config WHERE key='coin_value'")
        coin_val = float(c.fetchone()[0])
        c.execute("UPDATE clients SET credit = credit + ? WHERE id=?", (coin_val, client_id))
        c.execute("DELETE FROM queue WHERE id=?", (row[0],))
        # Update totals
        c.execute("INSERT OR IGNORE INTO config (key, value) VALUES ('total_coins', '0')")
        c.execute("INSERT OR IGNORE INTO config (key, value) VALUES ('total_revenue', '0')")
        c.execute("UPDATE config SET value = CAST(value AS REAL) + 1 WHERE key='total_coins'")
        c.execute("UPDATE config SET value = CAST(value AS REAL) + 1 WHERE key='total_revenue'")  # P1 per coin
        conn.commit()
        # Log coin insertion
        with open('coin_log.txt', 'a') as f:
            f.write(f"{datetime.now()}: Coin inserted for client {client_id}\n")
        # Check if queue empty
        c.execute("SELECT COUNT(*) FROM queue")
        if c.fetchone()[0] == 0:
            relay_pin.off()  # Disable relay

coin_pin.when_pressed = coin_inserted

# Decrement credits thread
def decrement_credits():
    cleanup_counter = 0
    while True:
        c = conn.cursor()
        c.execute("UPDATE clients SET credit = MAX(0, credit - 1) WHERE credit > 0")
        # Cleanup inactive clients every hour (60 minutes)
        cleanup_counter += 1
        if cleanup_counter >= 60:
            cutoff = datetime.now() - timedelta(hours=24)
            c.execute("DELETE FROM clients WHERE last_active < ?", (cutoff,))
            cleanup_counter = 0
        conn.commit()
        time.sleep(60)

threading.Thread(target=decrement_credits, daemon=True).start()

# Flask app
app = Flask(__name__)

@app.route('/register', methods=['POST'])
def register():
    ip = request.remote_addr
    c = conn.cursor()
    c.execute("SELECT id FROM clients WHERE ip=?", (ip,))
    row = c.fetchone()
    if row:
        client_id = row[0]
        c.execute("UPDATE clients SET last_active=? WHERE id=?", (datetime.now(), client_id))
    else:
        c.execute("INSERT INTO clients (ip, credit, last_active) VALUES (?, 0, ?)", (ip, datetime.now()))
        client_id = c.lastrowid
    conn.commit()
    return jsonify({'client_id': client_id})

@app.route('/request_coin', methods=['POST'])
def request_coin():
    client_id = request.json.get('client_id')
    c = conn.cursor()
    c.execute("INSERT INTO queue (client_id) VALUES (?)", (client_id,))
    c.execute("SELECT COUNT(*) FROM queue")
    count = c.fetchone()[0]
    if count == 1:  # First in queue
        relay_pin.on()  # Enable relay
    conn.commit()
    return jsonify({'status': 'queued'})

@app.route('/get_credit', methods=['GET'])
def get_credit():
    client_id = request.args.get('client_id')
    c = conn.cursor()
    c.execute("SELECT credit FROM clients WHERE id=?", (client_id,))
    row = c.fetchone()
    credit = row[0] if row else 0
    return jsonify({'credit': credit})

@app.route('/admin/reset_credit/<int:client_id>', methods=['POST'])
def reset_credit(client_id):
    c = conn.cursor()
    c.execute("UPDATE clients SET credit = 0 WHERE id=?", (client_id,))
    conn.commit()
    return '<script>alert("Credit reset!"); window.location.href="/admin";</script>'

@app.route('/admin/force_unlock/<int:client_id>', methods=['POST'])
def force_unlock_client(client_id):
    c = conn.cursor()
    c.execute("UPDATE clients SET credit = 999999 WHERE id=?", (client_id,))
    conn.commit()
    return '<script>alert("Client force unlocked!"); window.location.href="/admin";</script>'

@app.route('/admin/clear_all_credits', methods=['POST'])
def clear_all_credits():
    c = conn.cursor()
    c.execute("UPDATE clients SET credit = 0")
    conn.commit()
    return '<script>alert("All credits cleared!"); window.location.href="/admin";</script>'

@app.route('/admin/restart_server', methods=['POST'])
def restart_server():
    subprocess.call(['systemctl', 'restart', 'pisonet'])
    return '<script>alert("Server restarting..."); window.location.href="/admin";</script>'

@app.route('/version')
def version():
    return jsonify({'version': '1.0'})

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    c = conn.cursor()
    if request.method == 'POST':
        coin_value = request.form.get('coin_value')
        if coin_value:
            c.execute("UPDATE config SET value=? WHERE key='coin_value'", (coin_value,))
            conn.commit()
            return '<script>alert("Coin value updated!"); window.location.href="/admin";</script>'
    
    c.execute("SELECT value FROM config WHERE key='coin_value'")
    coin_val = c.fetchone()[0]
    
    # Get clients
    c.execute("SELECT id, ip, credit, last_active FROM clients ORDER BY last_active DESC")
    clients = c.fetchall()
    
    # Get queue
    c.execute("SELECT clients.ip FROM queue JOIN clients ON queue.client_id = clients.id")
    queue = c.fetchall()
    
    # Get stats
    c.execute("SELECT value FROM config WHERE key='total_coins'")
    total_coins = c.fetchone()
    total_coins = float(total_coins[0]) if total_coins else 0
    c.execute("SELECT value FROM config WHERE key='total_revenue'")
    total_revenue = c.fetchone()
    total_revenue = float(total_revenue[0]) if total_revenue else 0
    
    # System status
    uptime = time.time() - psutil.boot_time()
    uptime_str = f"{int(uptime // 3600)}h {int((uptime % 3600) // 60)}m"
    cpu_percent = psutil.cpu_percent()
    ram_percent = psutil.virtual_memory().percent
    relay_status = "On" if relay_pin.value == 0 else "Off"  # Since active_high=False, 0 is on
    
    clients_html = ''.join(f'''
    <tr>
        <td>{cl[0]}</td>
        <td>{cl[1]}</td>
        <td>{cl[2]:.1f} min</td>
        <td>{cl[3]}</td>
        <td>
            <form method="post" action="/admin/reset_credit/{cl[0]}" style="display:inline;">
                <button type="submit" onclick="return confirm('Reset credit for {cl[1]}?')">Reset</button>
            </form>
            <form method="post" action="/admin/force_unlock/{cl[0]}" style="display:inline;">
                <button type="submit" onclick="return confirm('Force unlock {cl[1]}?')">Unlock</button>
            </form>
        </td>
    </tr>''' for cl in clients)
    queue_html = ''.join(f'<li>{q[0]}</li>' for q in queue)
    
    html = f'''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>PISONET Admin Panel</title>
        <style>
            body {{ font-family: Arial, sans-serif; background-color: #f4f4f4; margin: 0; padding: 20px; }}
            .container {{ max-width: 1200px; margin: auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 0 10px rgba(0,0,0,0.1); }}
            h1 {{ color: #333; text-align: center; }}
            .section {{ margin-bottom: 30px; }}
            .section h2 {{ color: #555; border-bottom: 2px solid #007bff; padding-bottom: 5px; }}
            form {{ display: flex; align-items: center; gap: 10px; }}
            input[type="number"] {{ padding: 8px; border: 1px solid #ccc; border-radius: 4px; }}
            button {{ background-color: #007bff; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; }}
            button:hover {{ background-color: #0056b3; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
            th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }}
            th {{ background-color: #f8f9fa; }}
            ul {{ list-style-type: none; padding: 0; }}
            li {{ background: #e9ecef; margin: 5px 0; padding: 5px; border-radius: 4px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>PISONET Admin Panel</h1>
            
            <div class="section">
                <h2>Settings</h2>
                <form method="post">
                    <label for="coin_value">Coin Value (minutes per peso):</label>
                    <input id="coin_value" name="coin_value" value="{coin_val}" type="number" step="0.1" min="0.1">
                    <button type="submit">Update</button>
                </form>
            </div>
            
            <div class="section">
                <h2>Statistics</h2>
                <p>Total Coins Inserted: {total_coins:.0f}</p>
                <p>Total Revenue: ₱{total_revenue:.2f}</p>
            </div>
            
            <div class="section">
                <h2>System Status</h2>
                <p>Uptime: {uptime_str}</p>
                <p>CPU Usage: {cpu_percent:.1f}%</p>
                <p>RAM Usage: {ram_percent:.1f}%</p>
                <p>Relay Status: {relay_status}</p>
            </div>
            
            <div class="section">
                <h2>Maintenance</h2>
                <form method="post" action="/admin/clear_all_credits" style="display:inline;">
                    <button type="submit" onclick="return confirm('Clear all client credits?')">Clear All Credits</button>
                </form>
                <form method="post" action="/admin/restart_server" style="display:inline;">
                    <button type="submit" onclick="return confirm('Restart server?')">Restart Server</button>
                </form>
            </div>
            
            <div class="section">
                <h2>Connected Clients ({len(clients)})</h2>
                <table>
                    <tr><th>ID</th><th>IP Address</th><th>Remaining Credit</th><th>Last Active</th><th>Actions</th></tr>
                    {clients_html}
                </table>
            </div>
            
            <div class="section">
                <h2>Coin Request Queue ({len(queue)})</h2>
                <ul>
                    {queue_html if queue_html else '<li>No requests in queue</li>'}
                </ul>
            </div>
        </div>
    </body>
    </html>
    '''
    return html

@app.route('/force_unlock', methods=['POST'])
def force_unlock():
    client_id = request.json.get('client_id')
    c = conn.cursor()
    c.execute("UPDATE clients SET credit = 999999 WHERE id=?", (client_id,))
    conn.commit()
    return jsonify({'status': 'unlocked'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80)