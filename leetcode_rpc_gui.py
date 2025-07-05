# LeetCode Rich Presence GUI App with Language & Timer Reset Support
import os
import sys
import time
import threading
import json
import requests
from tkinter import *
from tkinter import ttk, messagebox
from pypresence import Presence
from datetime import datetime

CLIENT_ID = "Enter your own discord dev app ID"
CHROME_REMOTE_URL = "http://localhost:9222/json"
CHECK_INTERVAL = 5

class LeetCodeRPCApp:
    def __init__(self, root):
        self.root = root
        self.root.title("LeetCode Simple RPC")
        self.root.geometry("320x300")
        self.root.resizable(False, False)
        try:
            self.root.iconphoto(False, PhotoImage(file="icon.png"))
        except:
            pass

        self.rpc = None
        self.running = False
        self.current_problem = ""
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
            self.current_problem = ""
            self.start_time = int(time.time())
            self.start_btn.config(text="Stop LeetCode Presence")
            threading.Thread(target=self.monitor_tabs, daemon=True).start()

    def monitor_tabs(self):
        while self.running:
            try:
                response = requests.get(CHROME_REMOTE_URL)
                tabs = response.json()
                found = False
                for tab in tabs:
                    url = tab.get("url", "")
                    title = tab.get("title", "")
                    print(f"Tab URL: {url}, Title: {title}")  # Debug
                    if "leetcode.com/problems/" in url:
                        problem_slug = url.split("/problems/")[1].split("/")[0]
                        problem_name = problem_slug.replace("-", " ").title()
                        language = self.get_language_from_tab(tab)
                        difficulty = self.fetch_difficulty(problem_slug)

                        print(f"Detected problem: {problem_name}, Language: {language}, Difficulty: {difficulty}")  # Debug

                        if problem_slug != self.current_problem:
                            self.current_problem = problem_slug
                            self.start_time = int(time.time())

                        self.update_presence(problem_name, difficulty, language)
                        found = True
                        break
                if not found:
                    self.activity_label.config(text="No LeetCode problem detected.")
            except Exception as e:
                self.activity_label.config(text=f"Error: {e}")
                print(f"Error in monitor_tabs: {e}")
            time.sleep(CHECK_INTERVAL)

    def get_language_from_tab(self, tab):
        # Try to extract language from the tab's title or URL fragment, but avoid false positives for 'c'
        try:
            title = tab.get("title", "").lower()
            url = tab.get("url", "").lower()
            langs = ["cpp", "java", "python", "python3", "c#", "javascript", "typescript", "php", "swift",
                     "kotlin", "dart", "go", "ruby", "scala", "rust", "racket", "elixir", "erlang"]
            # Only match 'c' as a standalone word (very rare in titles/urls)
            for lang in langs:
                if lang in title or lang in url:
                    return lang.capitalize()
            # Special case for 'c' (standalone)
            for part in title.split():
                if part == 'c':
                    return 'C'
            for part in url.split('/'):
                if part == 'c':
                    return 'C'
        except Exception as e:
            print(f"Error in get_language_from_tab: {e}")
        return "Unknown"

    def fetch_difficulty(self, slug):
        try:
            api_url = f"https://leetcode.com/api/problems/all/"
            resp = requests.get(api_url)
            data = resp.json()
            for item in data["stat_status_pairs"]:
                if item["stat"]["question__title_slug"] == slug:
                    level = item["difficulty"]["level"]
                    difficulty = {1: "Easy", 2: "Medium", 3: "Hard"}.get(level, "Unknown")
                    print(f"Fetched difficulty for {slug}: {difficulty}")  # Debug
                    return difficulty
            print(f"Problem slug {slug} not found in API data.")
        except Exception as e:
            print(f"Error in fetch_difficulty: {e}")
        return "Medium"

    def update_presence(self, title, difficulty, language):
        self.activity_label.config(text=f"Solving: {title} ({difficulty}, {language})")
        try:
            # Only use allowed image keys for large_image
            image_key = difficulty.lower() if difficulty.lower() in ["easy", "medium", "hard"] else "medium"
            print(f"Updating presence: {title}, {difficulty}, {language}, image: {image_key}")  # Debug
            self.rpc.update(
                details=f"Solving: {title}",
                state=f"Difficulty: {difficulty} • Language: {language}",
                start=self.start_time,
                large_image=image_key,
            )
        except Exception as e:
            self.activity_label.config(text=f"RPC Error: {e}")
            print(f"RPC Error: {e}")

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
