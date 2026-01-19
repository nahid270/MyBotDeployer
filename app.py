import os
import sys
import subprocess
import shutil
import threading
import ast
import time
from flask import Flask, render_template, request, redirect, url_for, jsonify

app = Flask(__name__)

# কনফিগারেশন
CLONE_DIR = "cloned_repos"
if not os.path.exists(CLONE_DIR):
    os.makedirs(CLONE_DIR)

running_processes = {}
# রিয়েল-টাইম স্ট্যাটাস রাখার ডিকশনারি
deployment_status = {} 

STANDARD_LIBS = {
    "os", "sys", "time", "json", "math", "random", "datetime", "subprocess", "threading",
    "collections", "re", "ftplib", "http", "urllib", "email", "shutil", "logging", "typing",
    "traceback", "asyncio", "html", "socket", "base64", "io", "platform", "signal"
}

PIP_MAPPING = {
    "telebot": "pyTelegramBotAPI",
    "telegram": "python-telegram-bot",
    "bs4": "beautifulsoup4",
    "cv2": "opencv-python",
    "PIL": "Pillow",
    "dotenv": "python-dotenv",
    "discord": "discord.py",
    "aiogram": "aiogram"
}

def clean_url(url):
    return url.strip().rstrip("/")

def get_imports_from_folder(folder_path):
    imports = set()
    for root, dirs, files in os.walk(folder_path):
        for file in files:
            if file.endswith(".py"):
                try:
                    with open(os.path.join(root, file), "r", encoding="utf-8", errors="ignore") as f:
                        tree = ast.parse(f.read())
                    for node in ast.walk(tree):
                        if isinstance(node, ast.Import):
                            for alias in node.names:
                                imports.add(alias.name.split('.')[0])
                        elif isinstance(node, ast.ImportFrom):
                            if node.module:
                                imports.add(node.module.split('.')[0])
                except:
                    pass
    return imports

def install_and_run(repo_link, start_file, folder_name):
    """স্ট্যাটাস আপডেট সহ স্মার্ট ইনস্টলার"""
    global deployment_status
    repo_path = os.path.join(CLONE_DIR, folder_name)

    try:
        # ১. ক্লোন করা
        if not os.path.exists(repo_path):
            deployment_status[folder_name] = "⬇️ Cloning Repo..."
            subprocess.run(["git", "clone", repo_link, repo_path], check=True)
        
        # ২. লাইব্রেরি ইনস্টল
        req_file = os.path.join(repo_path, "requirements.txt")
        
        if os.path.exists(req_file):
            deployment_status[folder_name] = "📦 Installing Requirements..."
            subprocess.run(["pip", "install", "-r", "requirements.txt"], cwd=repo_path, stdout=subprocess.DEVNULL)
        else:
            deployment_status[folder_name] = "🔍 Scanning & Installing..."
            detected_imports = get_imports_from_folder(repo_path)
            packages_to_install = []
            for lib in detected_imports:
                if lib not in STANDARD_LIBS and not lib.startswith("_"):
                    packages_to_install.append(PIP_MAPPING.get(lib, lib))
            
            if packages_to_install:
                deployment_status[folder_name] = f"📦 Installing {len(packages_to_install)} Libs..."
                subprocess.run(["pip", "install"] + packages_to_install, cwd=repo_path, stdout=subprocess.DEVNULL)

        # ৩. মেইন ফাইল চেক
        run_path = os.path.join(repo_path, start_file)
        if not os.path.exists(run_path):
            deployment_status[folder_name] = "⚠️ Finding Main File..."
            possible_files = ["app.py", "main.py", "bot.py", "start.py"]
            for f in possible_files:
                if os.path.exists(os.path.join(repo_path, f)):
                    start_file = f
                    run_path = os.path.join(repo_path, start_file)
                    break

        # ৪. রান করা
        if os.path.exists(run_path):
            deployment_status[folder_name] = "🚀 Starting..."
            proc = subprocess.Popen(["python", start_file], cwd=repo_path)
            running_processes[folder_name] = proc
            
            # একটু অপেক্ষা করে চেক করা প্রসেস ক্র্যাশ করল কিনা
            time.sleep(3)
            if proc.poll() is None:
                deployment_status[folder_name] = "Running 🟢"
            else:
                deployment_status[folder_name] = "❌ Crashed Immediately"
        else:
            deployment_status[folder_name] = "❌ Start File Missing"

    except Exception as e:
        print(f"Error: {e}")
        deployment_status[folder_name] = f"❌ Error: {str(e)[:20]}..."

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/status')
def status_api():
    """AJAX দিয়ে লাইভ স্ট্যাটাস চেক করার এপিআই"""
    bots_data = []
    
    # ফোল্ডার লিস্ট থেকে স্ট্যাটাস জেনারেট করা
    if os.path.exists(CLONE_DIR):
        folders = os.listdir(CLONE_DIR)
        for folder in folders:
            # বর্তমান স্ট্যাটাস কি?
            current_status = deployment_status.get(folder, "Unknown")
            
            # যদি প্রসেস লিস্টে থাকে এবং রানিং থাকে
            if folder in running_processes:
                if running_processes[folder].poll() is None:
                    current_status = "Running 🟢"
                else:
                    current_status = "Stopped 🔴"
            
            bots_data.append({
                "name": folder,
                "status": current_status
            })
    
    return jsonify(bots_data)

@app.route('/deploy', methods=['POST'])
def deploy():
    repo_link = request.form.get('repo_link')
    start_file = request.form.get('start_file') or "main.py"
    
    if not repo_link: return "Link required", 400
    
    repo_link = clean_url(repo_link)
    folder_name = repo_link.split("/")[-1].replace(".git", "")

    if folder_name in running_processes and running_processes[folder_name].poll() is None:
        return f"{folder_name} is already running!", 400

    deployment_status[folder_name] = "⏳ Queued..."
    thread = threading.Thread(target=install_and_run, args=(repo_link, start_file, folder_name))
    thread.start()

    return redirect(url_for('home'))

@app.route('/stop/<folder_name>')
def stop_bot(folder_name):
    if folder_name in running_processes:
        running_processes[folder_name].terminate()
        del running_processes[folder_name]
    deployment_status[folder_name] = "Stopped 🔴"
    return redirect(url_for('home'))

@app.route('/delete/<folder_name>')
def delete_bot(folder_name):
    if folder_name in running_processes:
        stop_bot(folder_name)
    repo_path = os.path.join(CLONE_DIR, folder_name)
    if os.path.exists(repo_path):
        shutil.rmtree(repo_path)
    if folder_name in deployment_status:
        del deployment_status[folder_name]
    return redirect(url_for('home'))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port, debug=True)
