#!/usr/bin/env python3
"""
PISONET Client Application
Full-screen lockscreen for internet cafe management
"""

import tkinter as tk
from tkinter import messagebox, simpledialog
import requests
import threading
import time
import socket
import platform
import psutil
import os
import sys
import json
import uuid
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    filename='pisonet_client.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class PisonetClient:
    def __init__(self, server_url="http://localhost:5000"):
        self.server_url = server_url
        self.client_id = self.get_or_create_client_id()
        self.credit = 0
        self.is_locked = True
        self.timer_running = False

        # Create main window
        self.root = tk.Tk()
        self.root.title("PISONET Client")
        self.root.attributes('-fullscreen', True)
        self.root.attributes('-topmost', True)
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.bind('<Key>', self.on_key_press)
        self.root.bind('<Button>', self.on_mouse_click)

        # Prevent alt+tab and other window switching
        self.root.bind('<Alt-Key>', lambda e: 'break')
        self.root.bind('<F4>', lambda e: 'break')

        # Create UI elements
        self.create_ui()

        # Start background threads
        self.update_thread = threading.Thread(target=self.update_loop, daemon=True)
        self.update_thread.start()

        # Register with server
        self.register_with_server()

    def get_or_create_client_id(self):
        """Get or create unique client ID"""
        try:
            if os.path.exists('client_config.json'):
                with open('client_config.json', 'r') as f:
                    config = json.load(f)
                    return config.get('client_id')
            else:
                client_id = f"client_{uuid.uuid4().hex[:8]}"
                config = {'client_id': client_id}
                with open('client_config.json', 'w') as f:
                    json.dump(config, f)
                return client_id
        except Exception as e:
            logging.error(f"Error getting client ID: {e}")
            return f"client_{uuid.uuid4().hex[:8]}"

    def create_ui(self):
        """Create the user interface"""
        # Main frame
        self.main_frame = tk.Frame(self.root, bg='#667eea')
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # Header
        header_frame = tk.Frame(self.main_frame, bg='rgba(0,0,0,0.3)')
        header_frame.pack(fill=tk.X, pady=20)

        title_label = tk.Label(
            header_frame,
            text="PISONET",
            font=('Arial', 48, 'bold'),
            fg='white',
            bg='rgba(0,0,0,0.3)'
        )
        title_label.pack(pady=10)

        self.status_label = tk.Label(
            header_frame,
            text="Connecting to server...",
            font=('Arial', 16),
            fg='white',
            bg='rgba(0,0,0,0.3)'
        )
        self.status_label.pack()

        # Credit display
        self.credit_label = tk.Label(
            self.main_frame,
            text="0:00",
            font=('Arial', 72, 'bold'),
            fg='white',
            bg='#667eea'
        )
        self.credit_label.pack(pady=40)

        # Message
        self.message_label = tk.Label(
            self.main_frame,
            text="Welcome to PISONET Internet Cafe",
            font=('Arial', 24),
            fg='white',
            bg='#667eea',
            wraplength=800
        )
        self.message_label.pack(pady=20)

        # Coin button
        self.coin_button = tk.Button(
            self.main_frame,
            text="🪙 INSERT COIN",
            command=self.request_coin,
            font=('Arial', 32, 'bold'),
            bg='#FFD700',
            fg='black',
            relief=tk.RAISED,
            bd=5,
            padx=40,
            pady=20
        )
        self.coin_button.pack(pady=30)

        # Timer (hidden initially)
        self.timer_label = tk.Label(
            self.main_frame,
            text="Session Time: 0:00",
            font=('Arial', 28),
            fg='white',
            bg='#667eea'
        )
        self.timer_label.pack(pady=20)
        self.timer_label.pack_forget()

        # Admin button (hidden)
        self.admin_button = tk.Button(
            self.main_frame,
            text="Admin",
            command=self.show_admin_login,
            font=('Arial', 12),
            bg='rgba(255,255,255,0.2)',
            fg='white',
            relief=tk.FLAT
        )
        self.admin_button.place(relx=0.95, rely=0.05, anchor=tk.NE)

        # Instructions
        instructions = tk.Label(
            self.main_frame,
            text="Click 'INSERT COIN' to enable the coin slot\nInsert coin at the server to start your session",
            font=('Arial', 16),
            fg='white',
            bg='#667eea',
            justify=tk.CENTER
        )
        instructions.pack(pady=20)

    def register_with_server(self):
        """Register this client with the server"""
        try:
            data = {
                'client_id': self.client_id,
                'hostname': platform.node(),
                'ip_address': self.get_local_ip()
            }

            response = requests.post(f"{self.server_url}/api/register", json=data, timeout=5)
            result = response.json()

            if result.get('success'):
                self.status_label.config(text="Connected", fg="#27ae60")
                logging.info("Successfully registered with server")
            else:
                self.status_label.config(text="Registration Failed", fg="#e74c3c")
                logging.error(f"Registration failed: {result.get('message')}")

        except Exception as e:
            self.status_label.config(text="Connection Failed", fg="#e74c3c")
            logging.error(f"Registration error: {e}")

    def get_local_ip(self):
        """Get local IP address"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"

    def update_loop(self):
        """Main update loop to check credit and server status"""
        while True:
            try:
                self.check_credit()
                time.sleep(5)  # Check every 5 seconds
            except Exception as e:
                logging.error(f"Update loop error: {e}")
                time.sleep(10)  # Wait longer on error

    def check_credit(self):
        """Check current credit from server"""
        try:
            response = requests.post(
                f"{self.server_url}/api/get_credit",
                json={'client_id': self.client_id},
                timeout=5
            )
            result = response.json()

            if result.get('success'):
                new_credit = result.get('credit', 0)
                if new_credit != self.credit:
                    self.credit = new_credit
                    self.update_display()

                    if self.credit > 0 and self.is_locked:
                        self.unlock()
                    elif self.credit <= 0 and not self.is_locked:
                        self.lock()

        except Exception as e:
            logging.error(f"Credit check error: {e}")

    def update_display(self):
        """Update the credit display"""
        minutes = int(self.credit)
        seconds = int((self.credit % 1) * 60)
        time_str = f"{minutes}:{seconds:02d}"

        self.credit_label.config(text=time_str)

        if self.credit > 0:
            self.message_label.config(text="Session Active - Enjoy your internet!")
            self.coin_button.pack_forget()
            self.timer_label.pack(pady=20)
            self.main_frame.config(bg='#27ae60')
        else:
            self.message_label.config(text="Please insert coin to start your session")
            self.coin_button.pack(pady=30)
            self.timer_label.pack_forget()
            self.main_frame.config(bg='#667eea')

    def request_coin(self):
        """Request coin insertion from server"""
        try:
            self.coin_button.config(text="REQUESTING...", state=tk.DISABLED)

            response = requests.post(
                f"{self.server_url}/api/request_coin",
                json={'client_id': self.client_id},
                timeout=5
            )
            result = response.json()

            if result.get('success'):
                self.message_label.config(text="Coin slot enabled - Please insert coin at the server")
                logging.info("Coin request successful")
            else:
                self.message_label.config(text="Failed to enable coin slot - Please try again")
                logging.error(f"Coin request failed: {result.get('message')}")

        except Exception as e:
            self.message_label.config(text="Connection error - Please try again")
            logging.error(f"Coin request error: {e}")

        finally:
            # Re-enable button after 3 seconds
            self.root.after(3000, lambda: self.coin_button.config(
                text="🪙 INSERT COIN", state=tk.NORMAL
            ))

    def lock(self):
        """Lock the workstation"""
        self.is_locked = True
        self.main_frame.config(bg='#667eea')
        self.stop_timer()
        logging.info("Workstation locked")

    def unlock(self):
        """Unlock the workstation"""
        self.is_locked = False
        self.main_frame.config(bg='#27ae60')
        self.start_timer()
        logging.info("Workstation unlocked")

    def start_timer(self):
        """Start the session timer"""
        if not self.timer_running:
            self.timer_running = True
            self.update_timer()

    def stop_timer(self):
        """Stop the session timer"""
        self.timer_running = False

    def update_timer(self):
        """Update the timer display"""
        if self.timer_running and self.credit > 0:
            minutes = int(self.credit)
            seconds = int((self.credit % 1) * 60)
            time_str = f"Session Time: {minutes}:{seconds:02d}"
            self.timer_label.config(text=time_str)

            # Schedule next update in 1 second
            self.root.after(1000, self.update_timer)
        else:
            self.timer_running = False

    def show_admin_login(self):
        """Show admin login dialog"""
        password = simpledialog.askstring("Admin Login", "Enter admin password:", show='*')
        if password:
            try:
                # In a real implementation, this should verify with the server
                if password == "1234":  # Default password
                    self.show_admin_menu()
                else:
                    messagebox.showerror("Error", "Incorrect password")
            except Exception as e:
                messagebox.showerror("Error", f"Login failed: {e}")

    def show_admin_menu(self):
        """Show admin menu"""
        admin_window = tk.Toplevel(self.root)
        admin_window.title("PISONET Admin")
        admin_window.geometry("400x300")
        admin_window.attributes('-topmost', True)

        tk.Label(admin_window, text="Admin Menu", font=('Arial', 16, 'bold')).pack(pady=10)

        tk.Button(admin_window, text="Add Credit", command=lambda: self.admin_add_credit(admin_window)).pack(pady=5)
        tk.Button(admin_window, text="Reset Credit", command=lambda: self.admin_reset_credit(admin_window)).pack(pady=5)
        tk.Button(admin_window, text="View Logs", command=self.view_logs).pack(pady=5)
        tk.Button(admin_window, text="System Info", command=self.show_system_info).pack(pady=5)
        tk.Button(admin_window, text="Exit Admin", command=admin_window.destroy).pack(pady=5)

    def admin_add_credit(self, parent):
        """Admin function to add credit"""
        amount = simpledialog.askinteger("Add Credit", "Enter minutes to add:")
        if amount and amount > 0:
            try:
                response = requests.post(
                    f"{self.server_url}/api/add_credit",
                    json={'client_id': self.client_id, 'amount': amount},
                    timeout=5
                )
                result = response.json()
                if result.get('success'):
                    messagebox.showinfo("Success", f"Added {amount} minutes")
                    self.check_credit()  # Refresh credit
                else:
                    messagebox.showerror("Error", result.get('message', 'Failed to add credit'))
            except Exception as e:
                messagebox.showerror("Error", f"Failed to add credit: {e}")

    def admin_reset_credit(self, parent):
        """Admin function to reset credit"""
        if messagebox.askyesno("Confirm", "Reset credit to zero?"):
            try:
                response = requests.post(
                    f"{self.server_url}/api/reset_credit",
                    json={'client_id': self.client_id},
                    timeout=5
                )
                result = response.json()
                if result.get('success'):
                    messagebox.showinfo("Success", "Credit reset")
                    self.check_credit()  # Refresh credit
                else:
                    messagebox.showerror("Error", result.get('message', 'Failed to reset credit'))
            except Exception as e:
                messagebox.showerror("Error", f"Failed to reset credit: {e}")

    def view_logs(self):
        """View client logs"""
        try:
            if os.path.exists('pisonet_client.log'):
                with open('pisonet_client.log', 'r') as f:
                    logs = f.read()

                log_window = tk.Toplevel(self.root)
                log_window.title("Client Logs")
                log_window.geometry("600x400")

                text_widget = tk.Text(log_window, wrap=tk.WORD)
                text_widget.insert(tk.END, logs)
                text_widget.config(state=tk.DISABLED)

                scrollbar = tk.Scrollbar(log_window, command=text_widget.yview)
                text_widget.config(yscrollcommand=scrollbar.set)

                text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
                scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            else:
                messagebox.showinfo("Logs", "No logs found")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to read logs: {e}")

    def show_system_info(self):
        """Show system information"""
        try:
            info = f"""
System Information:

Hostname: {platform.node()}
IP Address: {self.get_local_ip()}
Platform: {platform.platform()}
Python: {sys.version}

CPU Usage: {psutil.cpu_percent()}%
Memory Usage: {psutil.virtual_memory().percent}%
Disk Usage: {psutil.disk_usage('/').percent}%

Client ID: {self.client_id}
Server URL: {self.server_url}
Current Credit: {self.credit} minutes
Status: {'Locked' if self.is_locked else 'Unlocked'}
"""
            messagebox.showinfo("System Info", info)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to get system info: {e}")

    def on_key_press(self, event):
        """Handle key press events"""
        # Prevent common exit combinations
        if event.keysym in ['Escape', 'F4'] or (event.state & 0x4 and event.keysym == 'c'):
            return 'break'

        # Admin hotkey (Ctrl+Shift+A)
        if event.state & 0x5 and event.keysym.lower() == 'a':  # Ctrl+Shift+A
            self.show_admin_login()
            return 'break'

    def on_mouse_click(self, event):
        """Handle mouse click events"""
        # Prevent right-click context menu
        if event.num == 3:
            return 'break'

    def on_closing(self):
        """Handle window close event"""
        # Prevent closing
        pass

    def run(self):
        """Start the application"""
        logging.info("PISONET Client started")
        self.root.mainloop()

def main():
    # Allow custom server URL
    server_url = "http://localhost:5000"
    if len(sys.argv) > 1:
        server_url = sys.argv[1]

    client = PisonetClient(server_url)
    client.run()

if __name__ == "__main__":
    main()