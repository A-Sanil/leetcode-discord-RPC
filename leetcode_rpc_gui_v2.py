
# LeetCode Rich Presence GUI App - Updated with correct image keys
import os
import sys
import time
import threading
import json
import requests
from tkinter import *
from tkinter import messagebox
from pypresence import Presence
from datetime import datetime

CLIENT_ID = "758394403890003988"
CHROME_REMOTE_URL = "http://localhost:9222/json"
CHECK_INTERVAL = 5

IMAGE_KEYS = {
    "easy": "easy",
    "medium": "medium",
    "hard": "hard"
}

class LeetCodeRPCApp:
    def __init__(self, root):
        self.root = root
        self.root.title("LeetCode Simple RPC")
        self.root.geometry("320x280")
        self.root.resizable(False, False)
        try:
            self.root.iconphoto(False, PhotoImage(file="icon.png"))
        except:
            pass

        self.rpc = None
        self.running = False
        self.start_time = None

        self.status_label = Label(root, text="Status: Disconnected", fg="red")
        self.status_label.pack(pady=10)

        self.activity_label = Label(root, text="No activity yet", font=("Segoe UI", 10))
        self.activity_label.pack(pady=5)

        self.connect_btn = Button(root, text="Connect to Discord", width=25, command=self.connect_to_discord)
        self.connect_btn.pack(pady=5)

        self.start_btn = Button(root, text="Start LeetCode Presence", width=25, command=self.toggle_presence)
        self.start_btn.pack(pady=5)

        self.quit_btn = Button(root, text="Exit", width=25, command=self.quit_app)
        self.quit_btn.pack(pady=15)

    def connect_to_discord(self):
        try:
            self.rpc = Presence(CLIENT_ID)
            self.rpc.connect()
            self.status_label.config(text="Status: Connected", fg="green")
        except Exception as e:
            messagebox.showerror("Connection Failed", f"Failed to connect to Discord: {e}")

    def toggle_presence(self):
        if self.running:
            self.running = False
            self.start_btn.config(text="Start LeetCode Presence")
            self.activity_label.config(text="Presence stopped.")
            if self.rpc:
                try:
                    self.rpc.clear()
                except:
                    pass
        else:
            self.running = True
            self.start_time = int(time.time())
            self.start_btn.config(text="Stop LeetCode Presence")
            threading.Thread(target=self.monitor_tabs, daemon=True).start()

    def monitor_tabs(self):
        while self.running:
            try:
                response = requests.get(CHROME_REMOTE_URL)
                tabs = response.json()
                for tab in tabs:
                    url = tab.get("url", "")
                    if "leetcode.com/problems/" in url:
                        problem = url.split("/problems/")[1].split("/")[0].replace("-", " ").title()
                        difficulty = self.get_difficulty_from_url(url)
                        self.update_presence(problem, difficulty)
                        break
            except Exception as e:
                self.activity_label.config(text=f"Error: {e}")
            time.sleep(CHECK_INTERVAL)

    def update_presence(self, title, difficulty):
        if getattr(self, "last_title", None) != title:
            self.start_time = int(time.time())
            self.last_title = title
        image_key = IMAGE_KEYS.get(difficulty.lower(), "leetcode_logo")
        self.activity_label.config(text=f"Solving: {title} ({difficulty})")
        self.rpc.update(
            details=f"Solving: {title}",
            state=f"Difficulty: {difficulty}",
            start=self.start_time,
            large_image=image_key
        )

    def get_difficulty_from_url(self, url):
        if "/problems/" in url:
            if "easy" in url.lower():
                return "Easy"
            elif "medium" in url.lower():
                return "Medium"
            elif "hard" in url.lower():
                return "Hard"
        return "Medium"

    def quit_app(self):
        self.running = False
        try:
            if self.rpc:
                self.rpc.clear()
                self.rpc.close()
        except:
            pass
        self.root.destroy()

if __name__ == '__main__':
    root = Tk()
    app = LeetCodeRPCApp(root)
    root.mainloop()
