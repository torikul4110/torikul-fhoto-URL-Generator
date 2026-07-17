import os
import uuid
import base64
import tempfile
from datetime import datetime
from flask import Flask, render_template_string, request, send_from_directory, jsonify, session, redirect, url_for
from functools import wraps
from github import Github

app = Flask(__name__)
app.secret_key = os.urandom(24)

# ============ Login Credentials ============
USERNAME = "TORIKUL"
PASSWORD = "torikul_1999"

# ============ GitHub Config ============
GITHUB_TOKEN = "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"
REPO_NAME = "torikul4110/torikul-fhoto-URL-Generator"
BRANCH = "main"
IMAGES_FOLDER = "images"

# ============ Init GitHub ============
g = Github(GITHUB_TOKEN)
repo = g.get_repo(REPO_NAME)

try:
    repo.get_contents(IMAGES_FOLDER, ref=BRANCH)
except:
    repo.create_file(
        f"{IMAGES_FOLDER}/.gitkeep",
        "Create images folder",
        "",
        branch=BRANCH
    )

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp', 'svg', 'ico'}

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def upload_to_github(file_data, filename):
    try:
        file_path = f"{IMAGES_FOLDER}/{filename}"
        content = base64.b64encode(file_data).decode('utf-8')
        
        try:
            existing = repo.get_contents(file_path, ref=BRANCH)
            repo.update_file(
                file_path,
                f"Update: {filename}",
                content,
                existing.sha,
                branch=BRANCH
            )
        except:
            repo.create_file(
                file_path,
                f"Upload: {filename}",
                content,
                branch=BRANCH
            )
        return True
    except Exception as e:
        print(f"GitHub Upload Error: {e}")
        return False

def get_all_images():
    try:
        contents = repo.get_contents(IMAGES_FOLDER, ref=BRANCH)
        images = []
        for content in contents:
            if content.type == "file" and content.name.lower().endswith(('.png','.jpg','.jpeg','.gif','.webp','.bmp','.svg','.ico')):
                raw_url = f"https://raw.githubusercontent.com/{REPO_NAME}/{BRANCH}/{IMAGES_FOLDER}/{content.name}"
                images.append({
                    'filename': content.name,
                    'url': raw_url,
                    'size': f"{content.size/1024:.1f} KB",
                    'upload_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                })
        return images
    except Exception as e:
        print(f"Error getting images: {e}")
        return []

def delete_from_github(filename):
    try:
        file_path = f"{IMAGES_FOLDER}/{filename}"
        contents = repo.get_contents(file_path, ref=BRANCH)
        repo.delete_file(
            file_path,
            f"Delete: {filename}",
            contents.sha,
            branch=BRANCH
        )
        return True
    except:
        return False

def get_file_size(file_data):
    size_bytes = len(file_data)
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} GB"

# ============ HTML Templates ============

LOGIN_TEMPLATE = '''
<!DOCTYPE html>
<html lang="bn">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🔐 Login - TORIKUL Photo URL</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }

        .login-container {
            background: linear-gradient(145deg, #1a1a2e, #16213e);
            border-radius: 30px;
            padding: 50px 40px;
            max-width: 440px;
            width: 100%;
            box-shadow: 0 30px 80px rgba(0,0,0,0.6), 0 0 40px rgba(102, 126, 234, 0.1);
            animation: fadeIn 0.6s ease-in;
            border: 1px solid rgba(255,255,255,0.05);
        }

        @keyframes fadeIn {
            from {
                opacity: 0;
                transform: translateY(-30px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }

        .logo {
            text-align: center;
            margin-bottom: 30px;
        }

        .logo-icon {
            font-size: 3.5em;
            display: block;
            margin-bottom: 5px;
        }

        .logo h1 {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-size: 2.2em;
            font-weight: 800;
            letter-spacing: 2px;
        }

        .logo .subtitle {
            color: #8892b0;
            font-size: 0.9em;
            margin-top: 5px;
            letter-spacing: 3px;
            -webkit-text-fill-color: #8892b0;
        }

        .logo .crown {
            color: #f7d44a;
            font-size: 1.5em;
            -webkit-text-fill-color: #f7d44a;
        }

        .brand-line {
            text-align: center;
            color: #4a5568;
            font-size: 0.7em;
            letter-spacing: 5px;
            margin: 5px 0 20px 0;
            -webkit-text-fill-color: #4a5568;
            border-top: 1px solid rgba(255,255,255,0.05);
            padding-top: 15px;
        }

        .form-group {
            margin-bottom: 20px;
        }

        .form-group label {
            display: block;
            color: #a8b2d1;
            font-weight: 600;
            margin-bottom: 8px;
            font-size: 0.9em;
            letter-spacing: 1px;
        }

        .form-group input {
            width: 100%;
            padding: 14px 18px;
            border: 2px solid #233554;
            border-radius: 12px;
            font-size: 1em;
            transition: all 0.3s;
            background: #0a0a1a;
            color: #e6f1ff;
        }

        .form-group input:focus {
            border-color: #667eea;
            outline: none;
            box-shadow: 0 0 0 4px rgba(102, 126, 234, 0.15);
            background: #0f0f2a;
        }

        .form-group input::placeholder {
            color: #4a5568;
        }

        .btn-login {
            width: 100%;
            padding: 14px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 12px;
            font-size: 1.1em;
            font-weight: 700;
            cursor: pointer;
            transition: all 0.3s;
            letter-spacing: 2px;
            margin-top: 10px;
        }

        .btn-login:hover {
            transform: scale(1.02);
            box-shadow: 0 10px 30px rgba(102, 126, 234, 0.3);
        }

        .error-message {
            background: rgba(255, 0, 0, 0.1);
            color: #f87171;
            padding: 12px;
            border-radius: 10px;
            margin-bottom: 20px;
            text-align: center;
            border: 1px solid rgba(255, 0, 0, 0.2);
            display: none;
        }

        .footer {
            text-align: center;
            margin-top: 25px;
            color: #4a5568;
            font-size: 0.8em;
            letter-spacing: 2px;
        }

        .footer .heart {
            color: #f5576c;
        }

        .lock-icon {
            text-align: center;
            font-size: 2em;
            margin-bottom: 10px;
            color: #667eea;
        }
    </style>
</head>
<body>
    <div class="login-container">
        <div class="logo">
            <span class="logo-icon">👑</span>
            <h1>TORIKUL</h1>
            <div class="subtitle">PHOTO URL SYSTEM</div>
        </div>

        <div class="brand-line">━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━</div>

        <div id="errorMessage" class="error-message">
            ❌ ভুল ইউজারনেম বা পাসওয়ার্ড!
        </div>

        <form method="POST" action="/login" onsubmit="return validateForm()">
            <div class="form-group">
                <label>👤 USERNAME</label>
                <input type="text" name="username" placeholder="Enter your username" required>
            </div>

            <div class="form-group">
                <label>🔑 PASSWORD</label>
                <input type="password" name="password" placeholder="Enter your password" required>
            </div>

            <button type="submit" class="btn-login">🚀 LOGIN</button>
        </form>

        <div class="footer">
            <span class="heart">❤️</span> TORIKUL PHOTO URL SYSTEM <span class="heart">❤️</span>
        </div>
    </div>

    <script>
        function validateForm() {
            const errorDiv = document.getElementById('errorMessage');
            errorDiv.style.display = 'none';
            
            const username = document.querySelector('input[name="username"]').value.trim();
            const password = document.querySelector('input[name="password"]').value.trim();
            
            if (!username || !password) {
                errorDiv.textContent = '❌ দয়া করে ইউজারনেম এবং পাসওয়ার্ড দিন!';
                errorDiv.style.display = 'block';
                return false;
            }
            return true;
        }

        const urlParams = new URLSearchParams(window.location.search);
        if (urlParams.get('error') === '1') {
            const errorDiv = document.getElementById('errorMessage');
            errorDiv.textContent = '❌ ভুল ইউজারনেম বা পাসওয়ার্ড!';
            errorDiv.style.display = 'block';
        }
    </script>
</body>
</html>
'''

INDEX_TEMPLATE = '''
<!DOCTYPE html>
<html lang="bn">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>📸 TORIKUL - Photo URL Generator</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
            min-height: 100vh;
            padding: 20px;
        }

        .container {
            max-width: 1200px;
            margin: 0 auto;
        }

        .top-bar {
            background: linear-gradient(145deg, #1a1a2e, #16213e);
            border-radius: 20px;
            padding: 15px 25px;
            margin-bottom: 30px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 15px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.4);
            border: 1px solid rgba(255,255,255,0.05);
        }

        .top-bar .user-info {
            display: flex;
            align-items: center;
            gap: 12px;
        }

        .user-avatar {
            width: 45px;
            height: 45px;
            border-radius: 50%;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: bold;
            font-size: 1.2em;
            box-shadow: 0 5px 15px rgba(102, 126, 234, 0.3);
        }

        .user-name {
            font-weight: 600;
            color: #e6f1ff;
        }

        .user-name small {
            color: #8892b0;
            font-weight: 400;
            font-size: 0.8em;
        }

        .btn-logout {
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
            color: white;
            border: none;
            padding: 8px 20px;
            border-radius: 50px;
            cursor: pointer;
            font-weight: 600;
            transition: all 0.3s;
            text-decoration: none;
        }

        .btn-logout:hover {
            transform: scale(1.05);
            box-shadow: 0 5px 20px rgba(245, 87, 108, 0.4);
        }

        .header {
            text-align: center;
            margin-bottom: 40px;
            padding: 20px;
        }

        .header .brand {
            color: #667eea;
            font-size: 0.8em;
            letter-spacing: 5px;
            font-weight: 300;
        }

        .header h1 {
            font-size: 3em;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 10px;
            text-shadow: none;
        }

        .header h1 .crown {
            -webkit-text-fill-color: #f7d44a;
        }

        .header p {
            color: #a8b2d1;
            font-size: 1.1em;
            -webkit-text-fill-color: #a8b2d1;
        }

        .upload-card {
            background: linear-gradient(145deg, #1a1a2e, #16213e);
            border-radius: 25px;
            padding: 40px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            margin-bottom: 30px;
            transition: transform 0.3s;
            border: 1px solid rgba(255,255,255,0.05);
        }

        .upload-card:hover {
            transform: translateY(-5px);
        }

        .upload-area {
            border: 3px dashed #233554;
            border-radius: 18px;
            padding: 60px 20px;
            text-align: center;
            background: rgba(10, 10, 26, 0.5);
            cursor: pointer;
            transition: all 0.3s;
        }

        .upload-area:hover {
            border-color: #667eea;
            background: rgba(102, 126, 234, 0.05);
            box-shadow: 0 0 40px rgba(102, 126, 234, 0.05);
        }

        .upload-icon {
            font-size: 4em;
            margin-bottom: 20px;
        }

        .upload-text {
            font-size: 1.2em;
            color: #a8b2d1;
            margin-bottom: 10px;
            font-weight: 500;
        }

        .upload-subtext {
            color: #4a5568;
            font-size: 0.9em;
        }

        #fileInput {
            display: none;
        }

        .btn {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 12px 30px;
            font-size: 1em;
            border-radius: 50px;
            cursor: pointer;
            transition: all 0.3s;
            margin: 10px 5px;
            font-weight: 600;
        }

        .btn:hover {
            transform: scale(1.05);
            box-shadow: 0 10px 30px rgba(102, 126, 234, 0.3);
        }

        .btn-secondary {
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        }

        .btn-secondary:hover {
            box-shadow: 0 10px 30px rgba(245, 87, 108, 0.3);
        }

        .btn-gallery {
            background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
        }

        .btn-gallery:hover {
            box-shadow: 0 10px 30px rgba(79, 172, 254, 0.3);
        }

        .preview-area {
            margin-top: 30px;
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
            gap: 20px;
        }

        .preview-card {
            background: linear-gradient(145deg, #1a1a2e, #16213e);
            border-radius: 18px;
            overflow: hidden;
            box-shadow: 0 8px 25px rgba(0,0,0,0.3);
            transition: all 0.3s;
            border: 1px solid rgba(255,255,255,0.05);
        }

        .preview-card:hover {
            transform: translateY(-8px);
            box-shadow: 0 12px 40px rgba(0,0,0,0.4);
            border-color: rgba(102, 126, 234, 0.2);
        }

        .preview-image {
            width: 100%;
            height: 220px;
            object-fit: cover;
        }

        .preview-info {
            padding: 15px;
        }

        .preview-name {
            font-weight: 600;
            margin-bottom: 5px;
            color: #e6f1ff;
            word-break: break-all;
            font-size: 0.9em;
        }

        .preview-size {
            color: #4a5568;
            font-size: 0.85em;
            margin-bottom: 10px;
        }

        .url-link {
            background: rgba(255,255,255,0.05);
            padding: 10px;
            border-radius: 10px;
            font-size: 0.8em;
            word-break: break-all;
            margin: 10px 0;
            cursor: pointer;
            transition: background 0.2s;
            color: #a8b2d1;
            border: 1px solid rgba(255,255,255,0.05);
        }

        .url-link:hover {
            background: rgba(255,255,255,0.1);
        }

        .copy-btn {
            background: #667eea;
            color: white;
            border: none;
            padding: 6px 14px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 0.85em;
            transition: background 0.2s;
        }

        .copy-btn:hover {
            background: #764ba2;
        }

        .result-card {
            background: linear-gradient(145deg, #1a1a2e, #16213e);
            border-radius: 25px;
            padding: 30px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            margin-top: 30px;
            display: none;
            border: 1px solid rgba(255,255,255,0.05);
        }

        .result-title {
            font-size: 1.5em;
            margin-bottom: 20px;
            color: #667eea;
        }

        .link-list {
            list-style: none;
        }

        .link-item {
            background: rgba(255,255,255,0.03);
            padding: 15px;
            margin-bottom: 10px;
            border-radius: 12px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 10px;
            border: 1px solid rgba(255,255,255,0.05);
        }

        .link-url {
            font-family: monospace;
            color: #667eea;
            word-break: break-all;
            flex: 1;
            font-size: 0.9em;
        }

        .loading {
            text-align: center;
            padding: 20px;
            display: none;
        }

        .spinner {
            border: 4px solid rgba(255,255,255,0.1);
            border-top: 4px solid #667eea;
            border-radius: 50%;
            width: 50px;
            height: 50px;
            animation: spin 1s linear infinite;
            margin: 0 auto;
        }

        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }

        .nav-buttons {
            display: flex;
            justify-content: center;
            gap: 15px;
            margin-top: 25px;
            flex-wrap: wrap;
        }

        .progress-bar {
            width: 100%;
            height: 6px;
            background: rgba(255,255,255,0.05);
            border-radius: 10px;
            overflow: hidden;
            margin-top: 15px;
        }

        .progress-fill {
            height: 100%;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            width: 0%;
            transition: width 0.3s;
        }

        .brand-footer {
            text-align: center;
            padding: 20px;
            color: #4a5568;
            font-size: 0.8em;
            letter-spacing: 3px;
        }

        .brand-footer .crown {
            color: #f7d44a;
        }

        @media (max-width: 768px) {
            .header h1 {
                font-size: 2em;
            }
            
            .upload-card {
                padding: 20px;
            }
            
            .preview-area {
                grid-template-columns: 1fr;
            }

            .top-bar {
                flex-direction: column;
                text-align: center;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="top-bar">
            <div class="user-info">
                <div class="user-avatar">T</div>
                <div>
                    <div class="user-name">👋 স্বাগতম, TORIKUL <small>| Admin</small></div>
                    <div style="font-size: 0.8em; color: #4a5568;">📸 Photo URL System</div>
                </div>
            </div>
            <div>
                <a href="/gallery" class="btn btn-gallery" style="margin-right: 10px;">🎨 গ্যালারি</a>
                <a href="/logout" class="btn-logout">🚪 লগআউট</a>
            </div>
        </div>

        <div class="header">
            <div class="brand">━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━</div>
            <h1><span class="crown">👑</span> TORIKUL <span class="crown">👑</span></h1>
            <p style="color: #667eea; font-size: 0.9em; letter-spacing: 3px; -webkit-text-fill-color: #667eea;">PHOTO URL SYSTEM</p>
            <div class="brand">━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━</div>
            <p style="margin-top: 10px;">📸 Upload your image and get <br>Permanent URL instantly.</p>
            <p style="font-size: 0.8em; color: #4a5568; margin-top: 5px;">✅ GitHub এ সুরক্ষিতভাবে সংরক্ষণ করা হবে</p>
        </div>

        <div class="upload-card">
            <div class="upload-area" onclick="document.getElementById('fileInput').click()">
                <div class="upload-icon">📷</div>
                <div class="upload-text">ক্লিক করুন ছবি নির্বাচন করতে</div>
                <div class="upload-subtext">অথবা এখানে ড্র্যাগ করুন (একাধিক ছবি আপলোড করতে পারবেন)</div>
                <input type="file" id="fileInput" multiple accept="image/*" onchange="handleFiles(this.files)">
            </div>

            <div id="loading" class="loading">
                <div class="spinner"></div>
                <p style="margin-top: 15px; color: #667eea; font-weight: 500;">⏳ আপলোড হচ্ছে... GitHub এ সেভ করা হচ্ছে</p>
                <div class="progress-bar">
                    <div class="progress-fill" id="progressFill"></div>
                </div>
            </div>

            <div id="preview" class="preview-area"></div>
        </div>

        <div id="result" class="result-card">
            <h3 class="result-title">✅ জেনারেটেড লিংকসমূহ</h3>
            <div id="linkList"></div>
            <div class="nav-buttons">
                <button class="btn" onclick="window.location.href='/gallery'">🎨 গ্যালারি দেখুন</button>
                <button class="btn btn-secondary" onclick="resetForm()">🔄 নতুন করে আপলোড করুন</button>
            </div>
        </div>

        <div class="brand-footer">
            <span class="crown">👑</span> TORIKUL PHOTO URL SYSTEM <span class="crown">👑</span>
        </div>
    </div>

    <script>
        let uploadedFiles = [];

        async function handleFiles(files) {
            if (files.length === 0) return;
            
            const formData = new FormData();
            let validFiles = 0;
            
            for (let file of files) {
                if (file.type.startsWith('image/')) {
                    formData.append('photos', file);
                    validFiles++;
                }
            }

            if (validFiles === 0) {
                alert('❌ শুধু ইমেজ ফাইল আপলোড করুন!');
                return;
            }
            
            document.getElementById('loading').style.display = 'block';
            document.getElementById('preview').innerHTML = '';
            document.getElementById('result').style.display = 'none';
            
            let progress = 0;
            const progressFill = document.getElementById('progressFill');
            const interval = setInterval(() => {
                progress += 5;
                if (progress >= 90) {
                    clearInterval(interval);
                }
                progressFill.style.width = progress + '%';
            }, 200);
            
            try {
                const response = await fetch('/api/upload', {
                    method: 'POST',
                    body: formData
                });
                
                const data = await response.json();
                
                clearInterval(interval);
                progressFill.style.width = '100%';
                
                if (data.success) {
                    uploadedFiles = data.files;
                    displayPreview(data.files);
                    displayLinks(data.files);
                    document.getElementById('result').style.display = 'block';
                    
                    setTimeout(() => {
                        progressFill.style.width = '0%';
                    }, 1000);
                } else {
                    alert('❌ আপলোড করতে সমস্যা হয়েছে!');
                }
            } catch (error) {
                console.error('Error:', error);
                alert('❌ আপলোড করতে সমস্যা হয়েছে!');
            } finally {
                setTimeout(() => {
                    document.getElementById('loading').style.display = 'none';
                }, 500);
            }
        }
        
        function displayPreview(files) {
            const preview = document.getElementById('preview');
            preview.innerHTML = '';
            
            files.forEach(file => {
                const card = document.createElement('div');
                card.className = 'preview-card';
                card.innerHTML = `
                    <img src="${file.url}" class="preview-image" alt="${file.original_name}">
                    <div class="preview-info">
                        <div class="preview-name">📄 ${file.original_name.substring(0, 30)}</div>
                        <div class="preview-size">📦 ${file.size}</div>
                        <div class="url-link" onclick="copyToClipboard('${file.url}')">
                            🔗 ক্লিক করে URL কপি করুন
                        </div>
                    </div>
                `;
                preview.appendChild(card);
            });
        }
        
        function displayLinks(files) {
            const linkList = document.getElementById('linkList');
            linkList.innerHTML = '';
            
            files.forEach((file, index) => {
                const item = document.createElement('div');
                item.className = 'link-item';
                item.innerHTML = `
                    <div class="link-url">${file.url}</div>
                    <button class="copy-btn" onclick="copyToClipboard('${file.url}')">📋 কপি</button>
                `;
                linkList.appendChild(item);
            });
        }
        
        async function copyToClipboard(text) {
            try {
                await navigator.clipboard.writeText(text);
                alert('✅ লিংক কপি হয়েছে!');
            } catch (err) {
                prompt('📋 ম্যানুয়ালি কপি করুন:', text);
            }
        }
        
        function resetForm() {
            document.getElementById('fileInput').value = '';
            document.getElementById('preview').innerHTML = '';
            document.getElementById('result').style.display = 'none';
            uploadedFiles = [];
            location.reload();
        }
        
        const dropZone = document.querySelector('.upload-area');
        
        dropZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            dropZone.style.borderColor = '#764ba2';
            dropZone.style.background = 'rgba(102, 126, 234, 0.08)';
            dropZone.style.transform = 'scale(1.02)';
        });
        
        dropZone.addEventListener('dragleave', (e) => {
            e.preventDefault();
            dropZone.style.borderColor = '#233554';
            dropZone.style.background = 'rgba(10, 10, 26, 0.5)';
            dropZone.style.transform = 'scale(1)';
        });
        
        dropZone.addEventListener('drop', (e) => {
            e.preventDefault();
            dropZone.style.borderColor = '#233554';
            dropZone.style.background = 'rgba(10, 10, 26, 0.5)';
            dropZone.style.transform = 'scale(1)';
            const files = e.dataTransfer.files;
            handleFiles(files);
        });
    </script>
</body>
</html>
'''

GALLERY_TEMPLATE = '''
<!DOCTYPE html>
<html lang="bn">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🎨 TORIKUL - Gallery</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
            min-height: 100vh;
            padding: 20px;
        }

        .container {
            max-width: 1400px;
            margin: 0 auto;
        }

        .top-bar {
            background: linear-gradient(145deg, #1a1a2e, #16213e);
            border-radius: 20px;
            padding: 15px 25px;
            margin-bottom: 30px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 15px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.4);
            border: 1px solid rgba(255,255,255,0.05);
        }

        .top-bar .user-info {
            display: flex;
            align-items: center;
            gap: 12px;
        }

        .user-avatar {
            width: 45px;
            height: 45px;
            border-radius: 50%;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: bold;
            font-size: 1.2em;
            box-shadow: 0 5px 15px rgba(102, 126, 234, 0.3);
        }

        .user-name {
            font-weight: 600;
            color: #e6f1ff;
        }

        .user-name small {
            color: #8892b0;
            font-weight: 400;
            font-size: 0.8em;
        }

        .btn {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 8px 20px;
            border-radius: 50px;
            cursor: pointer;
            font-weight: 600;
            transition: all 0.3s;
            text-decoration: none;
            display: inline-block;
        }

        .btn:hover {
            transform: scale(1.05);
            box-shadow: 0 10px 30px rgba(102, 126, 234, 0.3);
        }

        .btn-logout {
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
            color: white;
            border: none;
            padding: 8px 20px;
            border-radius: 50px;
            cursor: pointer;
            font-weight: 600;
            transition: all 0.3s;
            text-decoration: none;
        }

        .btn-logout:hover {
            transform: scale(1.05);
            box-shadow: 0 5px 20px rgba(245, 87, 108, 0.4);
        }

        .btn-danger {
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        }

        .btn-danger:hover {
            box-shadow: 0 10px 30px rgba(245, 87, 108, 0.3);
        }

        .btn-primary {
            background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
        }

        .btn-primary:hover {
            box-shadow: 0 10px 30px rgba(79, 172, 254, 0.3);
        }

        .header {
            background: linear-gradient(145deg, #1a1a2e, #16213e);
            border-radius: 25px;
            padding: 25px 30px;
            margin-bottom: 30px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 15px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.3);
            border: 1px solid rgba(255,255,255,0.05);
        }

        .header h1 {
            color: #667eea;
            font-size: 2em;
        }

        .header h1 .crown {
            color: #f7d44a;
        }

        .stats {
            color: #a8b2d1;
            font-size: 1.1em;
        }

        .stats span {
            font-weight: 700;
            color: #667eea;
        }

        .gallery-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
            gap: 25px;
        }

        .gallery-card {
            background: linear-gradient(145deg, #1a1a2e, #16213e);
            border-radius: 20px;
            overflow: hidden;
            box-shadow: 0 10px 40px rgba(0,0,0,0.3);
            transition: all 0.3s;
            animation: fadeIn 0.5s ease-in;
            border: 1px solid rgba(255,255,255,0.05);
        }

        @keyframes fadeIn {
            from {
                opacity: 0;
                transform: translateY(30px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }

        .gallery-card:hover {
            transform: translateY(-8px);
            box-shadow: 0 15px 50px rgba(0,0,0,0.4);
            border-color: rgba(102, 126, 234, 0.2);
        }

        .image-container {
            position: relative;
            cursor: pointer;
            overflow: hidden;
            height: 260px;
        }

        .gallery-image {
            width: 100%;
            height: 100%;
            object-fit: cover;
            transition: transform 0.4s;
        }

        .gallery-card:hover .gallery-image {
            transform: scale(1.08);
        }

        .overlay {
            position: absolute;
            bottom: -100%;
            left: 0;
            right: 0;
            background: linear-gradient(to top, rgba(0,0,0,0.9), transparent);
            padding: 25px 20px 20px;
            transition: bottom 0.4s ease;
        }

        .gallery-card:hover .overlay {
            bottom: 0;
        }

        .overlay .url-box {
            background: rgba(255,255,255,0.05);
            backdrop-filter: blur(10px);
            padding: 12px;
            border-radius: 10px;
            font-size: 0.8em;
            word-break: break-all;
            color: #a8b2d1;
            cursor: pointer;
            border: 1px solid rgba(255,255,255,0.05);
            transition: background 0.2s;
        }

        .overlay .url-box:hover {
            background: rgba(255,255,255,0.1);
        }

        .card-info {
            padding: 18px;
        }

        .filename {
            font-weight: 600;
            color: #e6f1ff;
            margin-bottom: 8px;
            word-break: break-all;
            font-size: 0.95em;
        }

        .meta {
            color: #4a5568;
            font-size: 0.85em;
            margin-bottom: 12px;
        }

        .button-group {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }

        .btn-small {
            flex: 1;
            padding: 8px 15px;
            font-size: 0.85em;
            min-width: 80px;
            text-align: center;
        }

        .empty-state {
            text-align: center;
            padding: 80px 20px;
            background: linear-gradient(145deg, #1a1a2e, #16213e);
            border-radius: 25px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.3);
            border: 1px solid rgba(255,255,255,0.05);
        }

        .empty-icon {
            font-size: 5em;
            margin-bottom: 20px;
        }

        .empty-state h2 {
            color: #e6f1ff;
            margin-bottom: 10px;
        }

        .empty-state p {
            color: #4a5568;
            margin-bottom: 20px;
        }

        .modal {
            display: none;
            position: fixed;
            z-index: 1000;
            left: 0;
            top: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.95);
            animation: fadeIn 0.3s;
        }

        .modal-content {
            position: relative;
            margin: auto;
            padding: 20px;
            width: 95%;
            max-width: 95%;
            top: 50%;
            transform: translateY(-50%);
        }

        .modal-image {
            width: 100%;
            max-height: 85vh;
            object-fit: contain;
            border-radius: 12px;
        }

        .modal-close {
            position: absolute;
            top: 20px;
            right: 40px;
            color: white;
            font-size: 45px;
            cursor: pointer;
            transition: transform 0.2s;
        }

        .modal-close:hover {
            transform: rotate(90deg);
        }

        .modal-download {
            position: absolute;
            bottom: 30px;
            left: 50%;
            transform: translateX(-50%);
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 12px 30px;
            border-radius: 50px;
            font-size: 1em;
            cursor: pointer;
            transition: all 0.3s;
        }

        .modal-download:hover {
            transform: translateX(-50%) scale(1.05);
            box-shadow: 0 10px 30px rgba(102, 126, 234, 0.3);
        }

        .brand-footer {
            text-align: center;
            padding: 20px;
            color: #4a5568;
            font-size: 0.8em;
            letter-spacing: 3px;
            margin-top: 30px;
        }

        .brand-footer .crown {
            color: #f7d44a;
        }

        @media (max-width: 768px) {
            .gallery-grid {
                grid-template-columns: 1fr;
            }
            
            .header {
                flex-direction: column;
                text-align: center;
            }

            .top-bar {
                flex-direction: column;
                text-align: center;
            }

            .modal-close {
                right: 20px;
                font-size: 35px;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="top-bar">
            <div class="user-info">
                <div class="user-avatar">T</div>
                <div>
                    <div class="user-name">👋 স্বাগতম, TORIKUL <small>| Admin</small></div>
                    <div style="font-size: 0.8em; color: #4a5568;">🎨 ফটো গ্যালারি</div>
                </div>
            </div>
            <div>
                <a href="/" class="btn btn-primary" style="margin-right: 10px;">📸 আপলোড</a>
                <a href="/logout" class="btn-logout">🚪 লগআউট</a>
            </div>
        </div>

        <div class="header">
            <h1><span class="crown">👑</span> TORIKUL GALLERY <span class="crown">👑</span></h1>
            <div class="stats">
                📸 মোট ছবি: <span>{{ images|length }}</span> টি
            </div>
        </div>

        {% if images %}
        <div class="gallery-grid">
            {% for image in images %}
            <div class="gallery-card">
                <div class="image-container" onclick="openModal('{{ image.url }}', '{{ image.filename }}')">
                    <img src="{{ image.url }}" class="gallery-image" alt="{{ image.filename }}" loading="lazy">
                    <div class="overlay">
                        <div class="url-box" onclick="event.stopPropagation(); copyToClipboard('{{ image.url }}')">
                            🔗 ক্লিক করে URL কপি করুন
                        </div>
                    </div>
                </div>
                <div class="card-info">
                    <div class="filename">📄 {{ image.filename[:35] }}{% if image.filename|length > 35 %}...{% endif %}</div>
                    <div class="meta">📦 {{ image.size }} | 🕒 {{ image.upload_date }}</div>
                    <div class="button-group">
                        <button class="btn btn-small" onclick="copyToClipboard('{{ image.url }}')">📋 কপি URL</button>
                        <button class="btn btn-small btn-danger" onclick="deleteImage('{{ image.filename }}')">🗑️ ডিলিট</button>
                    </div>
                </div>
            </div>
            {% endfor %}
        </div>
        {% else %}
        <div class="empty-state">
            <div class="empty-icon">📭</div>
            <h2>কোনো ছবি নেই!</h2>
            <p>প্রথমে কিছু ছবি আপলোড করুন 📸</p>
            <a href="/" class="btn">📸 ছবি আপলোড করুন</a>
        </div>
        {% endif %}

        <div class="brand-footer">
            <span class="crown">👑</span> TORIKUL PHOTO URL SYSTEM <span class="crown">👑</span>
        </div>
    </div>

    <div id="imageModal" class="modal">
        <span class="modal-close" onclick="closeModal()">&times;</span>
        <div class="modal-content">
            <img id="modalImage" class="modal-image">
            <button class="modal-download" onclick="downloadImage()">💾 ডাউনলোড করুন</button>
        </div>
    </div>

    <script>
        let currentImageUrl = '';
        let currentImageName = '';

        function copyToClipboard(text) {
            navigator.clipboard.writeText(text).then(() => {
                alert('✅ URL কপি হয়েছে!');
            }).catch(() => {
                prompt('📋 ম্যানুয়ালি কপি করুন:', text);
            });
        }
        
        function openModal(url, filename) {
            currentImageUrl = url;
            currentImageName = filename;
            document.getElementById('modalImage').src = url;
            document.getElementById('imageModal').style.display = 'block';
            document.body.style.overflow = 'hidden';
        }
        
        function closeModal() {
            document.getElementById('imageModal').style.display = 'none';
            document.body.style.overflow = 'auto';
        }

        function downloadImage() {
            fetch(currentImageUrl)
                .then(response => response.blob())
                .then(blob => {
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = currentImageName;
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                    window.URL.revokeObjectURL(url);
                })
                .catch(() => {
                    window.open(currentImageUrl, '_blank');
                });
        }
        
        async function deleteImage(filename) {
            if (confirm('⚠️ আপনি কি এই ছবিটি ডিলিট করতে চান?')) {
                try {
                    const response = await fetch('/delete/' + filename, {
                        method: 'DELETE'
                    });
                    const data = await response.json();
                    if (data.success) {
                        alert('✅ ছবি ডিলিট হয়েছে!');
                        location.reload();
                    } else {
                        alert('❌ ডিলিট করতে সমস্যা হয়েছে!');
                    }
                } catch (error) {
                    alert('❌ ডিলিট করতে সমস্যা হয়েছে!');
                }
            }
        }
        
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') {
                closeModal();
            }
        });

        document.getElementById('imageModal').addEventListener('click', function(e) {
            if (e.target === this) {
                closeModal();
            }
        });
    </script>
</body>
</html>
'''

# ============ Routes ============

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        
        if username == USERNAME and password == PASSWORD:
            session['logged_in'] = True
            session['username'] = username
            return redirect(url_for('index'))
        else:
            return redirect(url_for('login', error=1))
    
    error = request.args.get('error')
    return render_template_string(LOGIN_TEMPLATE, error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    return render_template_string(INDEX_TEMPLATE)

@app.route('/api/upload', methods=['POST'])
@login_required
def api_upload():
    if 'photos' not in request.files:
        return jsonify({'error': 'No files uploaded'}), 400
    
    files = request.files.getlist('photos')
    uploaded_files = []
    
    for file in files:
        if file and file.filename != '' and allowed_file(file.filename):
            ext = file.filename.rsplit('.', 1)[1].lower()
            unique_name = f"{uuid.uuid4().hex}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{ext}"
            
            file_data = file.read()
            
            if upload_to_github(file_data, unique_name):
                full_url = f"https://raw.githubusercontent.com/{REPO_NAME}/{BRANCH}/{IMAGES_FOLDER}/{unique_name}"
                
                uploaded_files.append({
                    'original_name': file.filename,
                    'url': full_url,
                    'size': get_file_size(file_data),
                    'type': ext.upper(),
                    'filename': unique_name
                })
    
    if not uploaded_files:
        return jsonify({'error': 'No valid files uploaded'}), 400
    
    return jsonify({'success': True, 'files': uploaded_files})

@app.route('/gallery')
@login_required
def gallery():
    images = get_all_images()
    return render_template_string(GALLERY_TEMPLATE, images=images)

@app.route('/delete/<filename>', methods=['DELETE'])
@login_required
def delete_file(filename):
    if delete_from_github(filename):
        return jsonify({'success': True, 'message': 'File deleted successfully'})
    return jsonify({'success': False, 'message': 'File not found'}), 404

@app.route('/image/<filename>')
@login_required
def serve_image(filename):
    try:
        file_path = f"{IMAGES_FOLDER}/{filename}"
        contents = repo.get_contents(file_path, ref=BRANCH)
        image_data = base64.b64decode(contents.content)
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{filename.split('.')[-1]}") as tmp:
            tmp.write(image_data)
            tmp_path = tmp.name
        
        return send_from_directory(os.path.dirname(tmp_path), os.path.basename(tmp_path))
    except Exception as e:
        return f"Image not found: {str(e)}", 404

@app.route('/cleanup', methods=['POST'])
@login_required
def cleanup():
    try:
        contents = repo.get_contents(IMAGES_FOLDER, ref=BRANCH)
        deleted = 0
        current_time = datetime.now().timestamp()
        
        for content in contents:
            if content.type == "file" and content.name.lower().endswith(('.png','.jpg','.jpeg','.gif','.webp','.bmp','.svg','.ico')):
                commit = repo.get_commits(path=f"{IMAGES_FOLDER}/{content.name}", sha=BRANCH)[0]
                commit_time = commit.commit.author.date.timestamp()
                
                if current_time - commit_time > 604800:
                    repo.delete_file(
                        f"{IMAGES_FOLDER}/{content.name}",
                        f"Cleanup: {content.name}",
                        content.sha,
                        branch=BRANCH
                    )
                    deleted += 1
        
        return jsonify({'success': True, 'deleted': deleted})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ============ Main ============
if __name__ == '__main__':
    print("\n" + "="*60)
    print("👑 TORIKUL PHOTO URL SYSTEM 👑")
    print("="*60)
    print(f"📁 GitHub Repo: {REPO_NAME}")
    print(f"📂 Images Folder: {IMAGES_FOLDER}")
    print(f"🌐 Server: http://127.0.0.1:5000")
    print(f"🔐 Login: {USERNAME} / {PASSWORD}")
    print("="*60)
    print("✅ Images stored permanently on GitHub!")
    print("💡 Press CTRL+C to stop\n")
    app.run(debug=True, host='0.0.0.0', port=5002)