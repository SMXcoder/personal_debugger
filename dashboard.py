# dashboard.py
import tkinter as tk
from tkinter import ttk
import os
import json
import requests
import time
from dotenv import load_dotenv
import threading

# --- UI & MARKDOWN LIBRARIES ---
from markdown_it import MarkdownIt
from mdit_py_plugins.front_matter import front_matter_plugin
from pygments import highlight
from pygments.lexers import get_lexer_by_name
from pygments.formatters import HtmlFormatter
from tkinterweb import HtmlFrame

# --- CONFIGURATION ---
load_dotenv()
USER_HOME = os.path.expanduser("~")
LOG_FILE = os.path.join(USER_HOME, "error_dashboard.log")

# Load Both Gemini API Keys
GEMINI_API_KEY_PRIMARY = os.getenv("GEMINI_API_KEY_PRIMARY")
GEMINI_API_KEY_SECONDARY = os.getenv("GEMINI_API_KEY_SECONDARY")
if not GEMINI_API_KEY_PRIMARY or not GEMINI_API_KEY_SECONDARY:
    raise ValueError("Please provide both GEMINI_API_KEY_PRIMARY and GEMINI_API_KEY_SECONDARY in your .env file.")

# --- MARKDOWN & SYNTAX HIGHLIGHTING SETUP ---
def pygments_highlight(code, lang, _):
    try: lexer = get_lexer_by_name(lang, stripall=True)
    except: lexer = get_lexer_by_name('text', stripall=True)
    formatter = HtmlFormatter(noclasses=True, style='dracula') 
    return highlight(code, lexer, formatter)

md = MarkdownIt().use(front_matter_plugin)
md.options["highlight"] = pygments_highlight

# --- HTML TEMPLATE ---
HTML_TEMPLATE = """
<style>
    body {{ font-family: Segoe UI, sans-serif; background-color: #282a36; color: #f8f8f2; margin: 15px; line-height: 1.6; }}
    h1, h2, h3 {{ color: #8be9fd; border-bottom: 1px solid #44475a; padding-bottom: 5px; }}
    pre {{ background-color: #1e1e1e; padding: 15px; border-radius: 8px; border: 1px solid #44475a; white-space: pre-wrap; word-wrap: break-word; }}
    code {{ font-family: Fira Code, Consolas, monospace; }}
    ::-webkit-scrollbar {{ width: 10px; }}
    ::-webkit-scrollbar-track {{ background: #282a36; }}
    ::-webkit-scrollbar-thumb {{ background-color: #44475a; border-radius: 5px; }}
</style>
{content}
"""

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("🚀 AI Coding Assistant")
        self.geometry("900x700")
        self.configure(bg="#2c2c2c")
        
        top_frame = tk.Frame(self, bg="#2c2c2c")
        top_frame.pack(pady=10, fill="x")

        self.mode = tk.StringVar(value="general")
        style = ttk.Style()
        style.configure("TFrame", background="#2c2c2c")
        style.configure("TRadiobutton", background="#2c2c2c", foreground="white", font=("Segoe UI", 10))
        style.configure("TLabel", background="#2c2c2c", foreground="white", font=("Segoe UI", 12))

        ttk.Label(top_frame, text="Select Mode:").pack(side="left", padx=(20, 10))
        ttk.Radiobutton(top_frame, text="General Helper (Gemini)", variable=self.mode, value="general").pack(side="left", padx=10)
        ttk.Radiobutton(top_frame, text="DSA Tutor (Gemini)", variable=self.mode, value="dsa").pack(side="left", padx=10)
        ttk.Radiobutton(top_frame, text="🛠️ Developer (Gemini Pro)", variable=self.mode, value="developer").pack(side="left", padx=10)

        self.html_frame = HtmlFrame(self, messages_enabled=False)
        self.html_frame.pack(fill="both", expand=True, padx=10, pady=10)
        self.show_message("<h1>Waiting for an error...</h1>")

        self.last_mtime = 0
        self.last_error_data = None
        if not os.path.exists(LOG_FILE): open(LOG_FILE, 'w').close()
        
        self.update_dashboard()

    def show_message(self, html_content):
        self.html_frame.load_html(HTML_TEMPLATE.format(content=html_content))

    def update_dashboard(self):
        try:
            current_mtime = os.path.getmtime(LOG_FILE)
            if current_mtime != self.last_mtime:
                self.last_mtime = current_mtime
                with open(LOG_FILE, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if content.strip():
                        data = json.loads(content)
                        self.last_error_data = data
                        
                        selected_mode = self.mode.get()
                        if selected_mode == "developer":
                            self.show_message("<h1>Project context analysis triggered...</h1><p>Running deep analysis with Gemini Pro. This may take a moment.</p>")
                            threading.Thread(target=self.run_project_analysis).start()
                        else:
                            self.show_message("<h1>Analyzing error...</h1>")
                            threading.Thread(target=self.run_single_file_analysis, args=(data, selected_mode)).start()
        except Exception:
            pass 
        self.after(2000, self.update_dashboard)

    def run_single_file_analysis(self, data, mode):
        ai_markdown = self._call_gemini_flash_api(data, mode)
        ai_html = md.render(ai_markdown)
        self.show_message(ai_html)

    def run_project_analysis(self):
        if not self.last_error_data or not self.last_error_data.get('file_path'):
            self.show_message("<h1>No file context. Run the 'explain' command on a file first.</h1>")
            return

        project_root = os.path.dirname(self.last_error_data['file_path'])
        
        project_context, file_count = "", 0
        ignore_dirs = {'.git', 'node_modules', '__pycache__', '.vscode', 'venv'}
        
        for root, dirs, files in os.walk(project_root):
            dirs[:] = [d for d in dirs if d not in ignore_dirs]
            for file in files:
                if file_count >= 20: break
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        project_context += f"--- File: {os.path.relpath(file_path, project_root)} ---\n{f.read()}\n\n"
                except Exception: continue
                file_count += 1
            if file_count >= 20: break
        
        ai_markdown = self._call_gemini_pro_api(self.last_error_data, project_context)
        ai_html = md.render(ai_markdown)
        self.show_message(ai_html)

    def _call_gemini_flash_api(self, data, mode):
        api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY_PRIMARY}"
        if mode == "dsa":
            prompt = f"You are a Socratic tutor... DO NOT provide corrected code.\n\nCODE:```{data['source_code']}```\n\nERROR:```{data['stderr']}```\n\nProvide a short, helpful hint:"
        else: # General mode
            prompt = f"You are an expert developer... explain the bug and provide corrected code.\n\nCODE:```{data['source_code']}```\n\nERROR:```{data['stderr']}```\n\nProvide your analysis and corrected code:"
        
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        try:
            response = requests.post(api_url, headers={"Content-Type": "application/json"}, json=payload, timeout=45)
            response.raise_for_status()
            return response.json()['candidates'][0]['content']['parts'][0]['text'].strip()
        except Exception as e:
            return f"### Google Gemini (Flash) API Request Failed\n\n```\n{e}\n```"

    def _call_gemini_pro_api(self, error_data, project_context):
        api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro:generateContent?key={GEMINI_API_KEY_SECONDARY}"
        prompt = f"""You are a senior software architect. Analyze the full project context to find the root cause of an error, which may be in a different file than where the error appeared. Provide a deep analysis of file interactions and a solution.

THE INITIAL ERROR (in '{error_data.get('file_path')}'):
```{error_data.get('stderr')}```

THE FULL PROJECT CONTEXT:
{project_context}"""
        
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        try:
            response = requests.post(api_url, headers={"Content-Type": "application/json"}, json=payload, timeout=60)
            response.raise_for_status()
            return response.json()['candidates'][0]['content']['parts'][0]['text'].strip()
        except Exception as e:
            return f"### Google Gemini (Pro) API Request Failed\n\n```\n{e}\n```"

if __name__ == "__main__":
    app = App()
    app.mainloop()