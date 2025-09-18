# dashboard.py
import tkinter as tk
from tkinter import ttk, scrolledtext
import time
import os
import requests
import json
from dotenv import load_dotenv

load_dotenv() 

USER_HOME = os.path.expanduser("~")
LOG_FILE = os.path.join(USER_HOME, "error_dashboard.log")
API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY:
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    load_dotenv(dotenv_path=env_path)
    API_KEY = os.getenv("GEMINI_API_KEY")
    if not API_KEY:
        raise ValueError("API Key not found in .env file next to dashboard.py")

# Change this line in dashboard.py
API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={API_KEY}"
class ErrorDashboard:
    def __init__(self, root):
        self.root = root
        self.root.title("🚀 AI Assistant Dashboard")
        self.root.geometry("1200x700")
        self.root.configure(bg="#2c2c2c")

        # --- Mode Selection Frame ---
        self.mode = tk.StringVar(value="general")
        mode_frame = tk.Frame(root, bg="#2c2c2c")
        mode_frame.pack(pady=10, fill="x")
        
        tk.Label(mode_frame, text="Select Mode:", font=("Helvetica", 12), fg="white", bg="#2c2c2c").pack(side="left", padx=(20, 10))
        ttk.Radiobutton(mode_frame, text="🛠️ General Helper (Any Language)", variable=self.mode, value="general").pack(side="left", padx=10)
        ttk.Radiobutton(mode_frame, text="💡 DSA Tutor (Hints Only)", variable=self.mode, value="dsa").pack(side="left", padx=10)

        # --- Display Area ---
        self.display_text = scrolledtext.ScrolledText(root, wrap=tk.WORD, bg="#1e1e1e", fg="white", font=("Consolas", 10), insertbackground="white")
        self.display_text.pack(fill="both", expand=True, padx=10, pady=10)

        # --- Tag configurations for colors ---
        self.display_text.tag_config("title", foreground="#8be9fd", font=("Consolas", 12, "bold"))
        self.display_text.tag_config("error", foreground="#ff5555")
        self.display_text.tag_config("ai_response", foreground="#50fa7b")

        self.last_mtime = 0
        if not os.path.exists(LOG_FILE):
            open(LOG_FILE, 'w').close()
        self.update_dashboard()

    def update_dashboard(self):
        try:
            current_mtime = os.path.getmtime(LOG_FILE)
            if current_mtime != self.last_mtime:
                self.last_mtime = current_mtime
                with open(LOG_FILE, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if content.strip():
                        data = json.loads(content)
                        self.process_error_data(data)
        except (json.JSONDecodeError, FileNotFoundError):
            pass 
        except Exception as e:
            print(f"Error reading log file: {e}")
        
        self.root.after(5000, self.update_dashboard)

    def process_error_data(self, data):
        self.display_text.delete('1.0', tk.END)
        self.display_text.insert(tk.END, "--- ERROR DETECTED ---\n", "title")
        self.display_text.insert(tk.END, f"{data.get('stderr', 'No error output.')}\n\n")

        self.display_text.insert(tk.END, "Thinking...\n", "ai_response")
        self.root.update_idletasks()
        
        suggestion = self.get_gemini_suggestion(data)
        
        self.display_text.delete('1.0', tk.END) # Clear everything for final display
        self.display_text.insert(tk.END, "--- ERROR DETECTED ---\n", "title")
        self.display_text.insert(tk.END, f"{data.get('stderr', 'No error output.')}\n\n")
        self.display_text.insert(tk.END, "--- AI RESPONSE ---\n", "title")
        self.display_text.insert(tk.END, suggestion, "ai_response")

    def get_gemini_suggestion(self, data):
        selected_mode = self.mode.get()
        
        if selected_mode == "dsa":
            # DSA Mode: Asks for a hint only.
            prompt = f"""You are a Socratic tutor for Data Structures and Algorithms. The user has provided their code and an error. 
            Your goal is to guide them to the solution **without giving the answer away**. 
            Ask a leading question or provide a short, conceptual hint about the logic causing the error. 
            **DO NOT provide the corrected code.**

            CODE:
            ```{data.get('source_code')}
            ```

            ERROR:
            ```
            {data['stderr']}
            ```

            Provide a short, helpful hint:"""
        else: # General Mode
            # General Mode: Asks for an explanation and solution for any language.
            prompt = f"""You are an expert developer. The user has provided code from a file named '{data.get('file_path', 'unknown')}' and an error message. The language could be anything (Python, JS, Java, etc).
            Analyze the code, identify the bug, explain it clearly, and provide the fully corrected code block.

            CODE:
            ```{data.get('source_code')}
            ```

            ERROR:
            ```
            {data['stderr']}
            ```
            
            Provide your analysis and the corrected code:"""

        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        try:
            response = requests.post(API_URL, headers={"Content-Type": "application/json"}, json=payload, timeout=30)
            response.raise_for_status()
            api_data = response.json()
            return api_data['candidates'][0]['content']['parts'][0]['text'].strip()
        except Exception as e:
            return f"API request failed: {e}"

if __name__ == "__main__":
    root = tk.Tk()
    dashboard = ErrorDashboard(root)
    root.mainloop()