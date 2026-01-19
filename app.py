import os
import sys
import subprocess
import shutil
import threading
import ast
from flask import Flask, render_template, request, redirect, url_for

app = Flask(__name__)

# কনফিগারেশন
CLONE_DIR = "cloned_repos"
if not os.path.exists(CLONE_DIR):
    os.makedirs(CLONE_DIR)

running_processes = {}

# সাধারণ পাইথন লাইব্রেরি যা ইনস্টল করার দরকার নেই
STANDARD_LIBS = {
    "os", "sys", "time", "json", "math", "random", "datetime", "subprocess", "threading",
    "collections", "re", "ftplib", "http", "urllib", "email", "shutil", "logging", "typing",
    "traceback", "asyncio", "html", "socket", "base64", "io", "platform", "signal"
}

# ইমপোর্ট নাম এবং পিপ প্যাকেজ নামের পার্থক্য ঠিক করার তালিকা
PIP_MAPPING = {
    "telebot": "pyTelegramBotAPI",
    "telegram": "python-telegram-bot",
    "bs4": "beautifulsoup4",
    "cv2": "opencv-python",
    "PIL": "Pillow",
    "dotenv": "python-dotenv",
    "youtube_dl": "youtube_dl",
    "yt_dlp": "yt_dlp",
    "googleapiclient": "google-api-python-client",
    "sklearn": "scikit-learn",
    "discord": "discord.py",
    "aiogram": "aiogram"
}

def clean_url(url):
    return url.strip().rstrip("/")

def get_imports_from_folder(folder_path):
    """ফোল্ডারের সব .py ফাইল স্ক্যান করে লাইব্রেরি খুঁজে বের করে"""
    imports = set()
    
    for root, dirs, files in os.walk(folder_path):
        for file in files:
            if file.endswith(".py"):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        tree = ast.parse(f.read())
                        
                    for node in ast.walk(tree):
                        # import library
                        if isinstance(node, ast.Import):
                            for alias in node.names:
                                imports.add(alias.name.split('.')[0])
                        # from library import module
                        elif isinstance(node, ast.ImportFrom):
                            if node.module:
                                imports.add(node.module.split('.')[0])
                except Exception as e:
                    print(f"⚠️ Could not parse {file}: {e}")
    return imports

def install_and_run(repo_link, start_file, folder_name):
    """স্মার্ট ইনস্টলেশন এবং রান প্রসেস"""
    repo_path = os.path.join(CLONE_DIR, folder_name)

    # ১. ক্লোন করা
    if not os.path.exists(repo_path):
        print(f"⬇️ Cloning {repo_link}...")
        subprocess.run(["git", "clone", repo_link, repo_path])
    
    # ২. লাইব্রেরি ইনস্টল (Smart Mode)
    req_file = os.path.join(repo_path, "requirements.txt")
    
    if os.path.exists(req_file):
        print(f"📦 Found requirements.txt. Installing...")
        subprocess.run(["pip", "install", "-r", "requirements.txt"], cwd=repo_path, stdout=subprocess.DEVNULL)
    else:
        print(f"🔍 requirements.txt not found. Scanning code for libraries...")
        
        # কোড স্ক্যান করে ইমপোর্ট বের করা
        detected_imports = get_imports_from_folder(repo_path)
        
        # ফিল্টার করা (সিস্টেম লাইব্রেরি বাদ দেওয়া)
        packages_to_install = []
        for lib in detected_imports:
            if lib not in STANDARD_LIBS and not lib.startswith("_"):
                # ম্যাপিং চেক করা (যেমন telebot -> pyTelegramBotAPI)
                package_name = PIP_MAPPING.get(lib, lib)
                packages_to_install.append(package_name)
        
        if packages_to_install:
            print(f"💡 Detected libraries: {', '.join(packages_to_install)}")
            print(f"⬇️ Installing detected libraries...")
            # সব একসাথে ইনস্টল
            subprocess.run(["pip", "install"] + packages_to_install, cwd=repo_path, stdout=subprocess.DEVNULL)
        else:
            print("✅ No external libraries detected.")

    # ৩. বট রান করা
    run_path = os.path.join(repo_path, start_file)
    
    # যদি start_file না পাওয়া যায়, অটোমেটিক খোঁজার চেষ্টা
    if not os.path.exists(run_path):
        print(f"⚠️ '{start_file}' not found. Searching for main file...")
        possible_files = ["app.py", "main.py", "bot.py", "start.py"]
        for f in possible_files:
            if os.path.exists(os.path.join(repo_path, f)):
                start_file = f
                run_path = os.path.join(repo_path, start_file)
                print(f"👉 Found '{start_file}'. Using it.")
                break

    if os.path.exists(run_path):
        print(f"🚀 Starting {folder_name} ({start_file})...")
        proc = subprocess.Popen(["python", start_file], cwd=repo_path)
        running_processes[folder_name] = proc
    else:
        print(f"❌ Critical Error: Could not find start file in {folder_name}")

@app.route('/')
def home():
    bots_status = []
    if os.path.exists(CLONE_DIR):
        folders = os.listdir(CLONE_DIR)
        for folder in folders:
            is_running = folder in running_processes and running_processes[folder].poll() is None
            bots_status.append({
                "name": folder,
                "status": "Running 🟢" if is_running else "Stopped 🔴",
                "running": is_running
            })
    return render_template('index.html', bots=bots_status)

@app.route('/deploy', methods=['POST'])
def deploy():
    repo_link = request.form.get('repo_link')
    start_file = request.form.get('start_file')

    if not repo_link:
        return "Repo Link is required!", 400
    
    if not start_file:
        start_file = "main.py" # ডিফল্ট ভ্যালু

    repo_link = clean_url(repo_link)
    folder_name = repo_link.split("/")[-1].replace(".git", "")

    if folder_name in running_processes and running_processes[folder_name].poll() is None:
        return f"{folder_name} is already running!", 400

    thread = threading.Thread(target=install_and_run, args=(repo_link, start_file, folder_name))
    thread.start()

    return redirect(url_for('home'))

@app.route('/stop/<folder_name>')
def stop_bot(folder_name):
    if folder_name in running_processes:
        proc = running_processes[folder_name]
        proc.terminate()
        del running_processes[folder_name]
    return redirect(url_for('home'))

@app.route('/delete/<folder_name>')
def delete_bot(folder_name):
    if folder_name in running_processes:
        stop_bot(folder_name)
    repo_path = os.path.join(CLONE_DIR, folder_name)
    if os.path.exists(repo_path):
        shutil.rmtree(repo_path)
    return redirect(url_for('home'))

if __name__ == "__main__":
    # পোর্ট ফিক্স: সার্ভারের পোর্ট বা ডিফল্ট ৮০০০
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port, debug=True)
