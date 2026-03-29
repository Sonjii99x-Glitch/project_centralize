import tkinter as tk
from tkinter import simpledialog, Canvas
import requests
import threading
import time
import keyboard
import sys
try:
    import winsound
    HAS_SOUND = True
except ImportError:
    HAS_SOUND = False

server_ip = sys.argv[1] if len(sys.argv) > 1 else '192.168.1.100'
client_id = None

def register():
    global client_id
    try:
        resp = requests.post(f'http://{server_ip}/register')
        client_id = resp.json()['client_id']
        print(f"Registered with ID: {client_id}")
    except Exception as e:
        print(f"Registration failed: {e}")

register()

root = tk.Tk()
root.attributes('-fullscreen', True)
root.attributes('-topmost', True)  # Keep on top
root.protocol("WM_DELETE_WINDOW", lambda: None)  # Prevent closing
root.bind('<Button-3>', lambda e: None)  # Disable right-click
root.title("PISONET Lock")

# Create canvas for gradient background
canvas = Canvas(root, width=root.winfo_screenwidth(), height=root.winfo_screenheight())
canvas.pack(fill="both", expand=True)

# Create gradient background
def create_gradient(canvas, width, height):
    for i in range(height):
        color = "#%02x%02x%02x" % (int(20 + 40 * (i / height)), int(20 + 40 * (i / height)), int(50 + 100 * (i / height)))
        canvas.create_line(0, i, width, i, fill=color)

create_gradient(canvas, root.winfo_screenwidth(), root.winfo_screenheight())

# Labels
title_label = canvas.create_text(root.winfo_screenwidth()//2, root.winfo_screenheight()//2 - 100, 
                                text="PISONET", font=('Arial', 60, 'bold'), fill='white')
message_label = canvas.create_text(root.winfo_screenwidth()//2, root.winfo_screenheight()//2 - 20, 
                                  text="Please insert coin to start your session", font=('Arial', 24), fill='white')
credit_label = canvas.create_text(root.winfo_screenwidth()//2, root.winfo_screenheight()//2 + 20, 
                                 text="", font=('Arial', 18), fill='yellow')

# Timer window for when unlocked
timer_window = None
timer_label = None

def update_timer():
    global timer_window, timer_label
    if client_id:
        try:
            resp = requests.get(f'http://{server_ip}/get_credit', params={'client_id': client_id})
            credit = resp.json()['credit']
            if credit > 0:
                if timer_window is None:
                    timer_window = tk.Toplevel(root)
                    timer_window.title("Session Time")
                    timer_window.geometry("300x100+10+10")
                    timer_label = tk.Label(timer_window, font=('Arial', 20))
                    timer_label.pack()
                timer_window.deiconify()
                timer_label.config(text=f"Time Left: {credit:.1f} min")
                root.withdraw()
            else:
                if timer_window:
                    timer_window.withdraw()
                root.deiconify()
        except:
            pass
    root.after(1000, update_timer)  # Update every second

update_timer()

# Button
button = tk.Button(root, text="INSERT COIN", command=request_coin, font=('Arial', 30, 'bold'), 
                  bg='#FFD700', fg='black', activebackground='#FFA500', activeforeground='white',
                  relief='raised', bd=5, padx=20, pady=10)
button_window = canvas.create_window(root.winfo_screenwidth()//2, root.winfo_screenheight()//2 + 100, window=button)

def request_coin():
    if client_id:
        # Sound effect
        if HAS_SOUND:
            winsound.Beep(800, 200)
        # Animation: change button color temporarily
        button.config(bg='#FF4500', text="REQUESTING...")
        root.after(1000, lambda: button.config(bg='#FFD700', text="INSERT COIN"))
        try:
            resp = requests.post(f'http://{server_ip}/request_coin', json={'client_id': client_id})
            print("Coin request sent")
        except Exception as e:
            print(f"Request failed: {e}")

def check_credit():
    while True:
        if client_id:
            try:
                resp = requests.get(f'http://{server_ip}/get_credit', params={'client_id': client_id})
                credit = resp.json()['credit']
                canvas.itemconfig(credit_label, text=f"Credit: {credit:.1f} minutes" if credit > 0 else "")
            except Exception as e:
                print(f"Credit check failed: {e}")
        time.sleep(30)  # Less frequent

threading.Thread(target=check_credit, daemon=True).start()

def on_f10():
    password = simpledialog.askstring("Admin", "Enter password:", show='*')
    if password == '1234':
        admin_win = tk.Toplevel(root)
        admin_win.title("Client Admin")
        btn = tk.Button(admin_win, text="Force Close App", command=force_close)
        btn.pack()
        admin_win.mainloop()

def force_close():
    if client_id:
        try:
            requests.post(f'http://{server_ip}/force_unlock', json={'client_id': client_id})
            print("Force unlock requested")
        except Exception as e:
            print(f"Force unlock failed: {e}")
    root.destroy()

keyboard.add_hotkey('f10', on_f10)

root.mainloop()

def on_f10():
    password = simpledialog.askstring("Admin", "Enter password:", show='*')
    if password == '1234':
        admin_win = tk.Toplevel(root)
        admin_win.title("Client Admin")
        btn = tk.Button(admin_win, text="Force Close App", command=force_close)
        btn.pack()
        admin_win.mainloop()

def force_close():
    if client_id:
        try:
            requests.post(f'http://{server_ip}/force_unlock', json={'client_id': client_id})
            print("Force unlock requested")
        except Exception as e:
            print(f"Force unlock failed: {e}")
    root.destroy()

keyboard.add_hotkey('f10', on_f10)

root.mainloop()