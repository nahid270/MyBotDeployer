import os
import subprocess
import shutil
import threading
from flask import Flask, render_template, request, jsonify, redirect, url_for

app = Flask(__name__)

# কনফিগারেশন
CLONE_DIR = "cloned_repos"
if not os.path.exists(CLONE_DIR):
    os.makedirs(CLONE_DIR)

# চলমান প্রসেসগুলো সেভ করে রাখার ডিকশনারি
# Format: { "folder_name": subprocess_object }
running_processes = {}

def clean_url(url):
    return url.strip().rstrip("/")

def install_and_run(repo_link, start_file, folder_name):
    """ব্যাকগ্রাউন্ডে ক্লোন, ইনস্টল এবং রান করার ফাংশন"""
    repo_path = os.path.join(CLONE_DIR, folder_name)

    # ১. ক্লোন করা
    if not os.path.exists(repo_path):
        print(f"⬇️ Cloning {repo_link}...")
        subprocess.run(["git", "clone", repo_link, repo_path])
    
    # ২. রিকোয়ারমেন্টস ইনস্টল
    req_file = os.path.join(repo_path, "requirements.txt")
    if os.path.exists(req_file):
        print(f"📦 Installing requirements for {folder_name}...")
        subprocess.run(["pip", "install", "-r", req_file], cwd=repo_path, stdout=subprocess.DEVNULL)

    # ৩. বট রান করা
    run_path = os.path.join(repo_path, start_file)
    if os.path.exists(run_path):
        print(f"✅ Starting {folder_name}...")
        # প্রসেস শুরু করা এবং গ্লোবাল ডিকশনারিতে রাখা
        proc = subprocess.Popen(["python", start_file], cwd=repo_path)
        running_processes[folder_name] = proc
    else:
        print(f"❌ File {start_file} not found in {folder_name}")

@app.route('/')
def home():
    # ড্যাশবোর্ডে বর্তমান স্ট্যাটাস দেখানো
    bots_status = []
    
    # ফোল্ডারগুলো চেক করি
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

    if not repo_link or not start_file:
        return "Missing data", 400

    repo_link = clean_url(repo_link)
    folder_name = repo_link.split("/")[-1].replace(".git", "")

    # যদি অলরেডি রানিং থাকে
    if folder_name in running_processes and running_processes[folder_name].poll() is None:
        return f"{folder_name} is already running!", 400

    # ব্যাকগ্রাউন্ড থ্রেডে কাজ শুরু করা (যাতে ওয়েবসাইট স্লো না হয়)
    thread = threading.Thread(target=install_and_run, args=(repo_link, start_file, folder_name))
    thread.start()

    return redirect(url_for('home'))

@app.route('/stop/<folder_name>')
def stop_bot(folder_name):
    if folder_name in running_processes:
        proc = running_processes[folder_name]
        proc.terminate() # প্রসেস বন্ধ করা
        # proc.kill() # জোর করে বন্ধ করতে চাইলে এটি ব্যবহার করুন
        del running_processes[folder_name]
        print(f"🛑 Stopped {folder_name}")
    
    return redirect(url_for('home'))

@app.route('/delete/<folder_name>')
def delete_bot(folder_name):
    # আগে স্টপ করা
    if folder_name in running_processes:
        stop_bot(folder_name)
    
    # ফোল্ডার ডিলিট করা
    repo_path = os.path.join(CLONE_DIR, folder_name)
    if os.path.exists(repo_path):
        shutil.rmtree(repo_path) # পুরো ফোল্ডার ডিলিট
        
    return redirect(url_for('home'))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
