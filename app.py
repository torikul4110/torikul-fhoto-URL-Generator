import os
import uuid
import tempfile
import json
import secrets
import shutil
from datetime import datetime
from flask import Flask, render_template_string, request, send_from_directory, jsonify, session, redirect, url_for
from functools import wraps
import qrcode
from io import BytesIO
import base64
import re
import cloudinary
import cloudinary.uploader
from supabase import create_client, Client

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))

# ============ SUPABASE SETUP ============
SUPABASE_URL = os.environ.get('SUPABASE_URL', 'https://your-project.supabase.co')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', 'your-supabase-anon-key')
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ============ CLOUDINARY SETUP ============
cloudinary.config(
    cloud_name=os.environ.get('CLOUDINARY_CLOUD_NAME', 'your-cloud-name'),
    api_key=os.environ.get('CLOUDINARY_API_KEY', 'your-api-key'),
    api_secret=os.environ.get('CLOUDINARY_API_SECRET', 'your-api-secret')
)

# ============ FILE STORAGE (For local development) ============
BASE_DIR = tempfile.gettempdir() if not os.environ.get('VERCEL') else '/tmp'
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 200 * 1024 * 1024  # 200MB

# ============ LOGIN CREDENTIALS ============
ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'Torikul')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', '@torikul_1999')

# ============ ALLOWED EXTENSIONS ============
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp', 'svg', 'ico'}

# ============ DATABASE FUNCTIONS ============

def generate_unique_id():
    """Generate unique ID with 'torikul' suffix"""
    random_part = secrets.token_hex(4)
    return f"{random_part}torikul"

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_file_size(filepath):
    size_bytes = os.path.getsize(filepath)
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} GB"

def generate_qr_code_base64(url):
    """Generate QR code and return as base64 string"""
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode()

def validate_url(url):
    """Validate if the URL is valid"""
    url_pattern = re.compile(
        r'^https?://'
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'
        r'localhost|'
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
        r'(?::\d+)?'
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    return re.match(url_pattern, url) is not None

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ============ DATABASE OPERATIONS ============

def upload_to_cloudinary(file_path, filename):
    """Upload image to Cloudinary and return URL"""
    try:
        result = cloudinary.uploader.upload(file_path, 
            public_id=filename.replace('.', '_'),
            folder='torikul_images'
        )
        return result['secure_url']
    except Exception as e:
        print(f"Cloudinary upload error: {e}")
        return None

def save_image_to_db(filename, original_name, url, size, file_type, group_id=None):
    """Save image data to Supabase"""
    try:
        data = {
            'filename': filename,
            'original_name': original_name,
            'url': url,
            'size': size,
            'type': file_type,
            'upload_date': datetime.now().isoformat(),
            'group_id': group_id,
            'views': 0
        }
        result = supabase.table('images').insert(data).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        print(f"Database save error: {e}")
        return None

def save_group_to_db(group_id, name, url, image_count, images):
    """Save group data to Supabase"""
    try:
        data = {
            'id': group_id,
            'name': name,
            'url': url,
            'image_count': image_count,
            'images': json.dumps(images),
            'created_at': datetime.now().isoformat(),
            'views': 0
        }
        result = supabase.table('groups').insert(data).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        print(f"Database save error: {e}")
        return None

def save_link_to_db(link_id, url, qr, group_id=None):
    """Save link data to Supabase"""
    try:
        data = {
            'link_id': link_id,
            'url': url,
            'qr': qr,
            'group_id': group_id,
            'created_at': datetime.now().isoformat()
        }
        result = supabase.table('links').insert(data).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        print(f"Database save error: {e}")
        return None

def save_link_group_to_db(group_id, name, url, link_count, links):
    """Save link group data to Supabase"""
    try:
        data = {
            'id': group_id,
            'name': name,
            'url': url,
            'link_count': link_count,
            'links': json.dumps(links),
            'created_at': datetime.now().isoformat(),
            'views': 0
        }
        result = supabase.table('link_groups').insert(data).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        print(f"Database save error: {e}")
        return None

def get_images_from_db():
    """Get all images from Supabase"""
    try:
        result = supabase.table('images').select('*').execute()
        images = {}
        for item in result.data:
            images[item['filename']] = {
                'filename': item['original_name'],
                'url': item['url'],
                'size': item['size'],
                'type': item['type'],
                'upload_date': item['upload_date'],
                'group_id': item.get('group_id'),
                'views': item.get('views', 0)
            }
        return images
    except Exception as e:
        print(f"Database fetch error: {e}")
        return {}

def get_groups_from_db():
    """Get all groups from Supabase"""
    try:
        result = supabase.table('groups').select('*').execute()
        groups = {}
        for item in result.data:
            groups[item['id']] = {
                'id': item['id'],
                'name': item['name'],
                'url': item['url'],
                'image_count': item['image_count'],
                'images': json.loads(item['images']) if item['images'] else [],
                'created_at': item['created_at'],
                'views': item.get('views', 0)
            }
        return groups
    except Exception as e:
        print(f"Database fetch error: {e}")
        return {}

def get_links_from_db():
    """Get all links from Supabase"""
    try:
        result = supabase.table('links').select('*').execute()
        links = {}
        for item in result.data:
            links[item['link_id']] = {
                'link_id': item['link_id'],
                'url': item['url'],
                'qr': item['qr'],
                'group_id': item.get('group_id'),
                'created_at': item['created_at']
            }
        return links
    except Exception as e:
        print(f"Database fetch error: {e}")
        return {}

def get_link_groups_from_db():
    """Get all link groups from Supabase"""
    try:
        result = supabase.table('link_groups').select('*').execute()
        link_groups = {}
        for item in result.data:
            link_groups[item['id']] = {
                'id': item['id'],
                'name': item['name'],
                'url': item['url'],
                'link_count': item['link_count'],
                'links': json.loads(item['links']) if item['links'] else [],
                'created_at': item['created_at'],
                'views': item.get('views', 0)
            }
        return link_groups
    except Exception as e:
        print(f"Database fetch error: {e}")
        return {}

def delete_image_from_db(filename):
    """Delete image from Supabase"""
    try:
        supabase.table('images').delete().eq('filename', filename).execute()
        return True
    except Exception as e:
        print(f"Database delete error: {e}")
        return False

def delete_group_from_db(group_id):
    """Delete group from Supabase"""
    try:
        # Delete all images in the group first
        supabase.table('images').delete().eq('group_id', group_id).execute()
        # Delete the group
        supabase.table('groups').delete().eq('id', group_id).execute()
        return True
    except Exception as e:
        print(f"Database delete error: {e}")
        return False

def delete_link_from_db(link_id):
    """Delete link from Supabase"""
    try:
        supabase.table('links').delete().eq('link_id', link_id).execute()
        return True
    except Exception as e:
        print(f"Database delete error: {e}")
        return False

def delete_link_group_from_db(group_id):
    """Delete link group from Supabase"""
    try:
        # Delete all links in the group first
        supabase.table('links').delete().eq('group_id', group_id).execute()
        # Delete the link group
        supabase.table('link_groups').delete().eq('id', group_id).execute()
        return True
    except Exception as e:
        print(f"Database delete error: {e}")
        return False

def increment_group_views(group_id):
    """Increment group view count"""
    try:
        group = supabase.table('groups').select('views').eq('id', group_id).execute()
        if group.data:
            current_views = group.data[0].get('views', 0) + 1
            supabase.table('groups').update({'views': current_views}).eq('id', group_id).execute()
    except Exception as e:
        print(f"View increment error: {e}")

def increment_link_group_views(group_id):
    """Increment link group view count"""
    try:
        group = supabase.table('link_groups').select('views').eq('id', group_id).execute()
        if group.data:
            current_views = group.data[0].get('views', 0) + 1
            supabase.table('link_groups').update({'views': current_views}).eq('id', group_id).execute()
    except Exception as e:
        print(f"View increment error: {e}")

def add_image_to_group_db(group_id, image_data):
    """Add image to existing group in Supabase"""
    try:
        # Get current group data
        group = supabase.table('groups').select('images, image_count').eq('id', group_id).execute()
        if group.data:
            images = json.loads(group.data[0]['images']) if group.data[0]['images'] else []
            images.append(image_data)
            image_count = group.data[0]['image_count'] + 1
            
            supabase.table('groups').update({
                'images': json.dumps(images),
                'image_count': image_count
            }).eq('id', group_id).execute()
            return True
        return False
    except Exception as e:
        print(f"Add to group error: {e}")
        return False

def add_link_to_group_db(group_id, link_data):
    """Add link to existing link group in Supabase"""
    try:
        # Get current link group data
        group = supabase.table('link_groups').select('links, link_count').eq('id', group_id).execute()
        if group.data:
            links = json.loads(group.data[0]['links']) if group.data[0]['links'] else []
            links.append(link_data)
            link_count = group.data[0]['link_count'] + 1
            
            supabase.table('link_groups').update({
                'links': json.dumps(links),
                'link_count': link_count
            }).eq('id', group_id).execute()
            return True
        return False
    except Exception as e:
        print(f"Add to link group error: {e}")
        return False

# ============ LOGIN TEMPLATE ============

LOGIN_TEMPLATE = '''
<!DOCTYPE html>
<html lang="bn">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Login - TORIKUL IMAGE • LINK • QR SYSTEM</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            background: linear-gradient(135deg, #0f0c29, #302b63, #24243e);
            overflow: hidden;
            position: relative;
        }
        .particles {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            pointer-events: none;
            z-index: 0;
        }
        .particle {
            position: absolute;
            width: 4px;
            height: 4px;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 50%;
            animation: float 15s infinite;
        }
        @keyframes float {
            0% { transform: translateY(100vh) scale(0); opacity: 0; }
            20% { opacity: 0.5; }
            80% { opacity: 0.5; }
            100% { transform: translateY(-100vh) scale(1); opacity: 0; }
        }
        .glow-orb {
            position: fixed;
            border-radius: 50%;
            filter: blur(80px);
            opacity: 0.3;
            z-index: 0;
            animation: pulse 8s ease-in-out infinite;
        }
        .glow-orb:nth-child(1) {
            width: 400px; height: 400px;
            background: #667eea;
            top: -100px; right: -100px;
        }
        .glow-orb:nth-child(2) {
            width: 300px; height: 300px;
            background: #764ba2;
            bottom: -50px; left: -50px;
            animation-delay: 2s;
        }
        .glow-orb:nth-child(3) {
            width: 200px; height: 200px;
            background: #f093fb;
            top: 50%; left: 50%;
            transform: translate(-50%, -50%);
            animation-delay: 4s;
        }
        @keyframes pulse {
            0%, 100% { transform: scale(1); opacity: 0.3; }
            50% { transform: scale(1.3); opacity: 0.5; }
        }
        .login-container {
            position: relative;
            z-index: 1;
            width: 100%;
            max-width: 420px;
            padding: 20px;
        }
        .login-box {
            background: rgba(255, 255, 255, 0.05);
            backdrop-filter: blur(20px);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 24px;
            padding: 40px 35px;
            box-shadow: 0 25px 80px rgba(0, 0, 0, 0.5);
        }
        .login-header { text-align: center; margin-bottom: 35px; }
        .login-icon { font-size: 3.5em; display: block; margin-bottom: 10px; }
        .login-title { color: #fff; font-size: 1.8em; font-weight: 700; }
        .login-subtitle { color: rgba(255, 255, 255, 0.6); font-size: 0.95em; margin-top: 5px; }
        .form-group { margin-bottom: 20px; }
        .form-group label { display: block; color: rgba(255, 255, 255, 0.7); font-size: 0.9em; margin-bottom: 8px; font-weight: 500; }
        .form-group input {
            width: 100%;
            padding: 14px 20px;
            background: rgba(255, 255, 255, 0.06);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 12px;
            color: #fff;
            font-size: 1em;
            transition: all 0.3s;
            outline: none;
        }
        .form-group input:focus {
            border-color: #667eea;
            background: rgba(255, 255, 255, 0.08);
            box-shadow: 0 0 20px rgba(102, 126, 234, 0.15);
        }
        .form-group input::placeholder { color: rgba(255, 255, 255, 0.3); }
        .btn-login {
            width: 100%;
            padding: 14px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border: none;
            border-radius: 12px;
            color: #fff;
            font-size: 1.1em;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s;
        }
        .btn-login:hover { transform: scale(1.02); box-shadow: 0 10px 30px rgba(102, 126, 234, 0.3); }
        .error-msg {
            background: rgba(255, 0, 0, 0.15);
            border: 1px solid rgba(255, 0, 0, 0.2);
            color: #ff6b6b;
            padding: 12px 16px;
            border-radius: 10px;
            margin-bottom: 20px;
            font-size: 0.9em;
            display: {{ 'block' if error else 'none' }};
        }
        .login-footer {
            text-align: center;
            margin-top: 25px;
            color: rgba(255, 255, 255, 0.3);
            font-size: 0.8em;
        }
        @media (max-width: 480px) {
            .login-box { padding: 30px 20px; }
            .login-title { font-size: 1.5em; }
            .glow-orb { display: none; }
        }
    </style>
</head>
<body>
    <div class="glow-orb"></div><div class="glow-orb"></div><div class="glow-orb"></div>
    <div class="particles" id="particles"></div>
    <div class="login-container">
        <div class="login-box">
            <div class="login-header">
                <span class="login-icon">🖼️</span>
                <h1 class="login-title">TORIKUL SYSTEM</h1>
                <p class="login-subtitle">Welcome Back, TORIKUL</p>
            </div>
            <div class="error-msg" id="errorMsg">{{ error }}</div>
            <form method="POST" action="{{ url_for('login') }}">
                <div class="form-group">
                    <label>👤 Username</label>
                    <input type="text" name="username" placeholder="Enter your username" value="{{ username or '' }}" required>
                </div>
                <div class="form-group">
                    <label>🔐 Password</label>
                    <input type="password" name="password" placeholder="Enter your password" required>
                </div>
                <button type="submit" class="btn-login">🚀 LOGIN</button>
            </form>
            <div class="login-footer">🔨 Created by TORIKUL</div>
        </div>
    </div>
    <script>
        const container = document.getElementById('particles');
        for (let i = 0; i < 50; i++) {
            const p = document.createElement('div');
            p.className = 'particle';
            p.style.left = Math.random() * 100 + '%';
            p.style.width = (Math.random() * 4 + 2) + 'px';
            p.style.height = p.style.width;
            p.style.animationDuration = (Math.random() * 20 + 10) + 's';
            p.style.animationDelay = (Math.random() * 10) + 's';
            container.appendChild(p);
        }
        {% if error %}document.getElementById('errorMsg').style.display = 'block';{% endif %}
    </script>
</body>
</html>
'''

# ============ DASHBOARD TEMPLATE ============

DASHBOARD_TEMPLATE = '''
<!DOCTYPE html>
<html lang="bn">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dashboard - TORIKUL IMAGE • LINK • QR SYSTEM</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #0a0a1a;
            min-height: 100vh;
            color: #fff;
        }
        .app-container { display: flex; min-height: 100vh; }
        .sidebar {
            width: 260px;
            background: rgba(20, 20, 40, 0.95);
            backdrop-filter: blur(10px);
            border-right: 1px solid rgba(255, 255, 255, 0.05);
            padding: 25px 0;
            position: fixed;
            height: 100vh;
            overflow-y: auto;
            z-index: 100;
            transition: transform 0.3s;
        }
        .sidebar-brand {
            text-align: center;
            padding: 0 20px 25px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
            margin-bottom: 20px;
        }
        .sidebar-brand .logo { font-size: 2.2em; }
        .sidebar-brand .brand-name {
            font-size: 1.2em;
            font-weight: 700;
            background: linear-gradient(135deg, #667eea, #764ba2);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .sidebar-brand .brand-sub {
            font-size: 0.7em;
            color: rgba(255, 255, 255, 0.4);
            -webkit-text-fill-color: rgba(255, 255, 255, 0.4);
        }
        .nav-item {
            display: flex;
            align-items: center;
            padding: 12px 25px;
            color: rgba(255, 255, 255, 0.6);
            text-decoration: none;
            transition: all 0.3s;
            border-left: 3px solid transparent;
            gap: 12px;
            cursor: pointer;
        }
        .nav-item:hover, .nav-item.active {
            background: rgba(102, 126, 234, 0.1);
            color: #fff;
            border-left-color: #667eea;
        }
        .nav-item .nav-icon { font-size: 1.2em; width: 28px; }
        .nav-item .nav-text { font-size: 0.95em; }
        .nav-item.logout {
            margin-top: 20px;
            border-top: 1px solid rgba(255, 255, 255, 0.05);
            padding-top: 20px;
            color: #ff6b6b;
        }
        .nav-item.logout:hover { border-left-color: #ff6b6b; background: rgba(255, 0, 0, 0.1); }
        .main-content {
            margin-left: 260px;
            flex: 1;
            padding: 25px 30px;
        }
        .top-bar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 30px;
            flex-wrap: wrap;
            gap: 15px;
        }
        .top-bar h1 { font-size: 1.8em; }
        .top-bar h1 span { background: linear-gradient(135deg, #667eea, #764ba2); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .user-info { color: rgba(255, 255, 255, 0.6); font-size: 0.95em; }
        .menu-toggle {
            display: none;
            background: none;
            border: none;
            color: #fff;
            font-size: 1.8em;
            cursor: pointer;
        }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .stat-card {
            background: rgba(255, 255, 255, 0.04);
            border: 1px solid rgba(255, 255, 255, 0.06);
            border-radius: 16px;
            padding: 20px 25px;
            transition: all 0.3s;
        }
        .stat-card:hover { transform: translateY(-3px); background: rgba(255, 255, 255, 0.06); }
        .stat-card .stat-icon { font-size: 2em; margin-bottom: 8px; }
        .stat-card .stat-number { font-size: 2em; font-weight: 700; }
        .stat-card .stat-label { color: rgba(255, 255, 255, 0.5); font-size: 0.85em; }
        .upload-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }
        .upload-card {
            background: rgba(255, 255, 255, 0.04);
            border: 1px solid rgba(255, 255, 255, 0.06);
            border-radius: 16px;
            padding: 30px;
            text-align: center;
            transition: all 0.3s;
            cursor: pointer;
            text-decoration: none;
            color: #fff;
        }
        .upload-card:hover { transform: translateY(-5px); background: rgba(255, 255, 255, 0.08); }
        .upload-card .uc-icon { font-size: 3em; margin-bottom: 15px; }
        .upload-card .uc-title { font-size: 1.1em; font-weight: 600; }
        .upload-card .uc-desc { color: rgba(255, 255, 255, 0.5); font-size: 0.8em; margin-top: 5px; }
        .section-title { font-size: 1.3em; margin: 30px 0 15px; color: rgba(255, 255, 255, 0.8); }
        .toast-container {
            position: fixed;
            bottom: 30px;
            right: 30px;
            z-index: 999;
            display: flex;
            flex-direction: column;
            gap: 10px;
        }
        .toast {
            padding: 14px 24px;
            border-radius: 12px;
            background: rgba(20, 20, 40, 0.95);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.1);
            color: #fff;
            font-size: 0.95em;
            animation: slideIn 0.3s ease-out;
            box-shadow: 0 10px 30px rgba(0,0,0,0.3);
        }
        .toast.success { border-left: 4px solid #51cf66; }
        .toast.error { border-left: 4px solid #ff6b6b; }
        @keyframes slideIn {
            from { transform: translateX(100px); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }
        @media (max-width: 768px) {
            .sidebar { transform: translateX(-100%); width: 280px; }
            .sidebar.open { transform: translateX(0); }
            .main-content { margin-left: 0; padding: 20px 15px; }
            .menu-toggle { display: block; }
            .stats-grid { grid-template-columns: repeat(2, 1fr); }
            .top-bar h1 { font-size: 1.3em; }
        }
        @media (max-width: 480px) {
            .stats-grid { grid-template-columns: 1fr; }
            .upload-grid { grid-template-columns: 1fr; }
        }
    </style>
</head>
<body>
    <div class="app-container">
        <nav class="sidebar" id="sidebar">
            <div class="sidebar-brand">
                <div class="logo">🖼️</div>
                <div class="brand-name">TORIKUL SYSTEM</div>
                <div class="brand-sub">Image • Link • QR</div>
            </div>
            <a href="{{ url_for('dashboard') }}" class="nav-item active">
                <span class="nav-icon">🏠</span><span class="nav-text">Dashboard</span>
            </a>
            <a href="{{ url_for('upload') }}" class="nav-item">
                <span class="nav-icon">📸</span><span class="nav-text">Upload Image</span>
            </a>
            <a href="{{ url_for('multiple_upload') }}" class="nav-item">
                <span class="nav-icon">📸📸</span><span class="nav-text">Multiple Upload</span>
            </a>
            <a href="{{ url_for('link_qr') }}" class="nav-item">
                <span class="nav-icon">🔗</span><span class="nav-text">Link to QR</span>
            </a>
            <a href="{{ url_for('multiple_link_qr') }}" class="nav-item">
                <span class="nav-icon">🔗🔗</span><span class="nav-text">Multiple Links</span>
            </a>
            <a href="{{ url_for('gallery') }}" class="nav-item">
                <span class="nav-icon">🖼️</span><span class="nav-text">My Images</span>
            </a>
            <a href="{{ url_for('groups') }}" class="nav-item">
                <span class="nav-icon">📁</span><span class="nav-text">Image Groups</span>
            </a>
            <a href="{{ url_for('link_groups') }}" class="nav-item">
                <span class="nav-icon">📁🔗</span><span class="nav-text">Link Groups</span>
            </a>
            <a href="{{ url_for('logout') }}" class="nav-item logout">
                <span class="nav-icon">🚪</span><span class="nav-text">Logout</span>
            </a>
        </nav>
        <div class="main-content">
            <div class="top-bar">
                <div style="display:flex;align-items:center;gap:15px;">
                    <button class="menu-toggle" onclick="toggleSidebar()">☰</button>
                    <h1>👋 Welcome, <span>TORIKUL</span></h1>
                </div>
                <div class="user-info">📅 {{ now.strftime('%B %d, %Y') }}</div>
            </div>
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-icon">📸</div>
                    <div class="stat-number">{{ total_images }}</div>
                    <div class="stat-label">Total Images</div>
                </div>
                <div class="stat-card">
                    <div class="stat-icon">🔗</div>
                    <div class="stat-number">{{ total_links }}</div>
                    <div class="stat-label">Total Links</div>
                </div>
                <div class="stat-card">
                    <div class="stat-icon">📁</div>
                    <div class="stat-number">{{ total_groups }}</div>
                    <div class="stat-label">Image Groups</div>
                </div>
                <div class="stat-card">
                    <div class="stat-icon">📁🔗</div>
                    <div class="stat-number">{{ total_link_groups }}</div>
                    <div class="stat-label">Link Groups</div>
                </div>
            </div>
            <h2 class="section-title">🚀 Quick Actions</h2>
            <div class="upload-grid">
                <a href="{{ url_for('upload') }}" class="upload-card">
                    <div class="uc-icon">📸</div>
                    <div class="uc-title">Single Image</div>
                    <div class="uc-desc">Upload & get URL + QR</div>
                </a>
                <a href="{{ url_for('multiple_upload') }}" class="upload-card">
                    <div class="uc-icon">📸📸</div>
                    <div class="uc-title">Multiple Images</div>
                    <div class="uc-desc">Create image group</div>
                </a>
                <a href="{{ url_for('link_qr') }}" class="upload-card">
                    <div class="uc-icon">🔗</div>
                    <div class="uc-title">Link to QR</div>
                    <div class="uc-desc">Convert any URL to QR</div>
                </a>
                <a href="{{ url_for('multiple_link_qr') }}" class="upload-card">
                    <div class="uc-icon">🔗🔗</div>
                    <div class="uc-title">Multiple Links</div>
                    <div class="uc-desc">Create link group</div>
                </a>
                <a href="{{ url_for('gallery') }}" class="upload-card">
                    <div class="uc-icon">🖼️</div>
                    <div class="uc-title">My Images</div>
                    <div class="uc-desc">View all uploaded images</div>
                </a>
                <a href="{{ url_for('groups') }}" class="upload-card">
                    <div class="uc-icon">📁</div>
                    <div class="uc-title">Image Groups</div>
                    <div class="uc-desc">Manage your image groups</div>
                </a>
            </div>
            <div style="margin-top:40px;text-align:center;color:rgba(255,255,255,0.2);font-size:0.8em;padding:20px;">
                🔨 Created by TORIKUL | 🖼️ TORIKUL IMAGE • LINK • QR SYSTEM v5.0 (Database Powered)
            </div>
        </div>
    </div>
    <div class="toast-container" id="toastContainer"></div>
    <script>
        function toggleSidebar() {
            document.getElementById('sidebar').classList.toggle('open');
        }
        function showToast(message, type = 'success') {
            const container = document.getElementById('toastContainer');
            const toast = document.createElement('div');
            toast.className = `toast ${type}`;
            toast.textContent = message;
            container.appendChild(toast);
            setTimeout(() => { toast.remove(); }, 3000);
        }
        document.addEventListener('click', function(e) {
            const sidebar = document.getElementById('sidebar');
            const toggle = document.querySelector('.menu-toggle');
            if (window.innerWidth <= 768 && sidebar.classList.contains('open') && 
                !sidebar.contains(e.target) && !toggle.contains(e.target)) {
                sidebar.classList.remove('open');
            }
        });
        {% if msg %}showToast('{{ msg }}', '{{ msg_type or "success" }}');{% endif %}
    </script>
</body>
</html>
'''

# ============ SINGLE UPLOAD TEMPLATE ============

UPLOAD_TEMPLATE = '''
<!DOCTYPE html>
<html lang="bn">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Single Upload - TORIKUL IMAGE • LINK • QR SYSTEM</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #0a0a1a;
            min-height: 100vh;
            color: #fff;
        }
        .container { max-width: 1000px; margin: 0 auto; padding: 20px; }
        .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 30px; flex-wrap: wrap; gap: 15px; }
        .header h1 { font-size: 1.8em; }
        .header h1 span { background: linear-gradient(135deg, #667eea, #764ba2); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .btn-back {
            padding: 10px 20px;
            background: rgba(255,255,255,0.06);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 10px;
            color: #fff;
            text-decoration: none;
            transition: all 0.3s;
        }
        .btn-back:hover { background: rgba(255,255,255,0.12); }
        .upload-area {
            border: 3px dashed rgba(102, 126, 234, 0.3);
            border-radius: 20px;
            padding: 60px 20px;
            text-align: center;
            background: rgba(255, 255, 255, 0.02);
            cursor: pointer;
            transition: all 0.3s;
        }
        .upload-area:hover { border-color: #667eea; background: rgba(102, 126, 234, 0.05); }
        .upload-area .icon { font-size: 4em; margin-bottom: 15px; }
        .upload-area .text { font-size: 1.2em; color: rgba(255,255,255,0.6); }
        .upload-area .sub { color: rgba(255,255,255,0.3); font-size: 0.9em; margin-top: 5px; }
        #fileInput { display: none; }
        .loading {
            display: none;
            text-align: center;
            padding: 30px;
        }
        .spinner {
            border: 4px solid rgba(255,255,255,0.1);
            border-top: 4px solid #667eea;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 0 auto;
        }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        .result-box {
            display: none;
            margin-top: 30px;
            background: rgba(255, 255, 255, 0.04);
            border: 1px solid rgba(255, 255, 255, 0.06);
            border-radius: 20px;
            padding: 30px;
        }
        .result-box .preview { text-align: center; margin-bottom: 20px; }
        .result-box .preview img { max-width: 100%; max-height: 400px; border-radius: 12px; }
        .info-row {
            display: flex;
            flex-wrap: wrap;
            gap: 15px;
            margin: 10px 0;
            padding: 12px 16px;
            background: rgba(255,255,255,0.03);
            border-radius: 10px;
            align-items: center;
        }
        .info-row .label { color: rgba(255,255,255,0.5); min-width: 100px; }
        .info-row .value { word-break: break-all; flex: 1; color: #667eea; }
        .btn {
            padding: 10px 20px;
            border: none;
            border-radius: 10px;
            font-size: 0.95em;
            cursor: pointer;
            transition: all 0.3s;
            color: #fff;
            font-weight: 500;
        }
        .btn-primary { background: linear-gradient(135deg, #667eea, #764ba2); }
        .btn-primary:hover { transform: scale(1.05); box-shadow: 0 10px 30px rgba(102, 126, 234, 0.3); }
        .btn-success { background: linear-gradient(135deg, #51cf66, #40c057); }
        .btn-success:hover { transform: scale(1.05); }
        .btn-danger { background: linear-gradient(135deg, #ff6b6b, #e03131); }
        .btn-danger:hover { transform: scale(1.05); }
        .btn-secondary { background: rgba(255,255,255,0.1); }
        .btn-secondary:hover { background: rgba(255,255,255,0.2); }
        .btn-group { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 15px; }
        .qr-container { text-align: center; padding: 15px; background: #fff; border-radius: 12px; display: inline-block; }
        .qr-container img { max-width: 200px; }
        .toast-container {
            position: fixed;
            bottom: 30px;
            right: 30px;
            z-index: 999;
            display: flex;
            flex-direction: column;
            gap: 10px;
        }
        .toast {
            padding: 14px 24px;
            border-radius: 12px;
            background: rgba(20, 20, 40, 0.95);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.1);
            color: #fff;
            font-size: 0.95em;
            animation: slideIn 0.3s ease-out;
        }
        .toast.success { border-left: 4px solid #51cf66; }
        .toast.error { border-left: 4px solid #ff6b6b; }
        @keyframes slideIn {
            from { transform: translateX(100px); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }
        .modal {
            display: none;
            position: fixed;
            top: 0; left: 0;
            width: 100%; height: 100%;
            background: rgba(0,0,0,0.7);
            backdrop-filter: blur(5px);
            z-index: 1000;
            justify-content: center;
            align-items: center;
        }
        .modal-content {
            background: #1a1a2e;
            padding: 30px;
            border-radius: 20px;
            max-width: 400px;
            width: 90%;
            text-align: center;
        }
        .modal-content h3 { margin-bottom: 15px; }
        .modal-content p { color: rgba(255,255,255,0.7); margin-bottom: 20px; }
        .modal .btn-group { justify-content: center; }
        @media (max-width: 600px) {
            .container { padding: 15px; }
            .header h1 { font-size: 1.3em; }
            .upload-area { padding: 40px 15px; }
            .result-box { padding: 20px; }
            .info-row { flex-direction: column; align-items: flex-start; }
            .info-row .label { min-width: auto; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📸 <span>Single Image Upload</span></h1>
            <a href="{{ url_for('dashboard') }}" class="btn-back">🏠 Dashboard</a>
        </div>
        
        <div class="upload-area" onclick="document.getElementById('fileInput').click()">
            <div class="icon">📷</div>
            <div class="text">Click to select an image</div>
            <div class="sub">or drag & drop here (Stored in Cloudinary)</div>
            <input type="file" id="fileInput" accept="image/*" onchange="handleFile(this.files[0])">
        </div>
        
        <div class="loading" id="loading">
            <div class="spinner"></div>
            <p style="margin-top:15px;">Uploading & generating QR code...</p>
        </div>
        
        <div class="result-box" id="resultBox">
            <div class="preview">
                <img id="previewImg" alt="Image Preview">
            </div>
            <div class="info-row">
                <span class="label">📄 Filename</span>
                <span class="value" id="fileName">-</span>
            </div>
            <div class="info-row">
                <span class="label">📦 Size</span>
                <span class="value" id="fileSize">-</span>
            </div>
            <div class="info-row">
                <span class="label">🔗 Image URL</span>
                <span class="value" id="imageUrl">-</span>
            </div>
            <div class="btn-group">
                <button class="btn btn-primary" onclick="copyLink()">📋 Copy Link</button>
                <button class="btn btn-success" onclick="downloadQR()">⬇️ Download QR</button>
                <button class="btn btn-danger" onclick="deleteImage()">🗑️ Delete Image</button>
            </div>
            <div style="margin-top:20px;text-align:center;">
                <div class="qr-container">
                    <p style="color:#333;margin-bottom:10px;">🧾 QR Code</p>
                    <img id="qrImg" alt="QR Code">
                </div>
            </div>
        </div>
        
        <div style="margin-top:30px;text-align:center;color:rgba(255,255,255,0.2);font-size:0.8em;">
            🔨 Created by TORIKUL | ✅ Data stored in Supabase + Cloudinary
        </div>
    </div>
    
    <div class="toast-container" id="toastContainer"></div>
    
    <!-- Confirmation Modal -->
    <div class="modal" id="confirmModal">
        <div class="modal-content">
            <h3>⚠️ Are You Sure?</h3>
            <p>Do you really want to delete this image?</p>
            <div class="btn-group">
                <button class="btn btn-secondary" onclick="closeModal()">Cancel</button>
                <button class="btn btn-danger" id="confirmDelete">Delete</button>
            </div>
        </div>
    </div>
    
    <script>
        let currentFile = null;
        let currentFilename = null;
        
        function handleFile(file) {
            if (!file) return;
            currentFile = file;
            
            document.getElementById('loading').style.display = 'block';
            document.getElementById('resultBox').style.display = 'none';
            
            const formData = new FormData();
            formData.append('photos', file);
            
            fetch('/api/upload', {
                method: 'POST',
                body: formData
            })
            .then(res => res.json())
            .then(data => {
                if (data.success && data.files.length > 0) {
                    const img = data.files[0];
                    currentFilename = img.filename;
                    document.getElementById('previewImg').src = img.url;
                    document.getElementById('fileName').textContent = img.original_name;
                    document.getElementById('fileSize').textContent = img.size;
                    document.getElementById('imageUrl').textContent = img.url;
                    
                    fetch('/api/qr/' + img.filename)
                        .then(res => res.json())
                        .then(qrData => {
                            document.getElementById('qrImg').src = 'data:image/png;base64,' + qrData.qr;
                            document.getElementById('resultBox').style.display = 'block';
                            document.getElementById('loading').style.display = 'none';
                            showToast('✅ Image uploaded & stored in Cloudinary!', 'success');
                        });
                }
            })
            .catch(err => {
                document.getElementById('loading').style.display = 'none';
                showToast('❌ Upload failed!', 'error');
            });
        }
        
        function copyLink() {
            const url = document.getElementById('imageUrl').textContent;
            navigator.clipboard.writeText(url).then(() => {
                showToast('✅ Link copied!', 'success');
            }).catch(() => {
                prompt('Copy this link:', url);
            });
        }
        
        function downloadQR() {
            const img = document.getElementById('qrImg');
            const link = document.createElement('a');
            link.download = 'qr_' + currentFilename + '.png';
            link.href = img.src;
            link.click();
            showToast('✅ QR Code downloaded!', 'success');
        }
        
        function deleteImage() {
            document.getElementById('confirmModal').style.display = 'flex';
            document.getElementById('confirmDelete').onclick = function() {
                closeModal();
                if (!currentFilename) return;
                fetch('/api/delete/' + currentFilename, { method: 'DELETE' })
                    .then(res => res.json())
                    .then(data => {
                        if (data.success) {
                            showToast('✅ Image deleted from Cloudinary!', 'success');
                            document.getElementById('resultBox').style.display = 'none';
                            document.getElementById('fileInput').value = '';
                        } else {
                            showToast('❌ Delete failed!', 'error');
                        }
                    });
            };
        }
        
        function closeModal() {
            document.getElementById('confirmModal').style.display = 'none';
        }
        
        function showToast(message, type = 'success') {
            const container = document.getElementById('toastContainer');
            const toast = document.createElement('div');
            toast.className = `toast ${type}`;
            toast.textContent = message;
            container.appendChild(toast);
            setTimeout(() => { toast.remove(); }, 3000);
        }
        
        const dropArea = document.querySelector('.upload-area');
        dropArea.addEventListener('dragover', (e) => {
            e.preventDefault();
            dropArea.style.borderColor = '#764ba2';
        });
        dropArea.addEventListener('dragleave', () => {
            dropArea.style.borderColor = 'rgba(102, 126, 234, 0.3)';
        });
        dropArea.addEventListener('drop', (e) => {
            e.preventDefault();
            dropArea.style.borderColor = 'rgba(102, 126, 234, 0.3)';
            const files = e.dataTransfer.files;
            if (files.length > 0) handleFile(files[0]);
        });
    </script>
</body>
</html>
'''

# ============ MULTIPLE UPLOAD TEMPLATE ============

MULTIPLE_UPLOAD_TEMPLATE = '''
<!DOCTYPE html>
<html lang="bn">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Multiple Upload - TORIKUL IMAGE • LINK • QR SYSTEM</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #0a0a1a;
            min-height: 100vh;
            color: #fff;
        }
        .container { max-width: 1100px; margin: 0 auto; padding: 20px; }
        .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 30px; flex-wrap: wrap; gap: 15px; }
        .header h1 { font-size: 1.8em; }
        .header h1 span { background: linear-gradient(135deg, #667eea, #764ba2); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .btn-back {
            padding: 10px 20px;
            background: rgba(255,255,255,0.06);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 10px;
            color: #fff;
            text-decoration: none;
            transition: all 0.3s;
        }
        .btn-back:hover { background: rgba(255,255,255,0.12); }
        .upload-area {
            border: 3px dashed rgba(102, 126, 234, 0.3);
            border-radius: 20px;
            padding: 50px 20px;
            text-align: center;
            background: rgba(255, 255, 255, 0.02);
            cursor: pointer;
            transition: all 0.3s;
        }
        .upload-area:hover { border-color: #667eea; background: rgba(102, 126, 234, 0.05); }
        .upload-area .icon { font-size: 3.5em; margin-bottom: 15px; }
        .upload-area .text { font-size: 1.1em; color: rgba(255,255,255,0.6); }
        .upload-area .sub { color: rgba(255,255,255,0.3); font-size: 0.9em; margin-top: 5px; }
        #fileInput { display: none; }
        .selected-files {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            margin-top: 15px;
        }
        .file-tag {
            background: rgba(102, 126, 234, 0.2);
            padding: 5px 15px;
            border-radius: 20px;
            font-size: 0.85em;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .file-tag .remove { cursor: pointer; color: #ff6b6b; font-weight: bold; }
        .loading {
            display: none;
            text-align: center;
            padding: 30px;
        }
        .spinner {
            border: 4px solid rgba(255,255,255,0.1);
            border-top: 4px solid #667eea;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 0 auto;
        }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        .btn {
            padding: 10px 25px;
            border: none;
            border-radius: 10px;
            font-size: 0.95em;
            cursor: pointer;
            transition: all 0.3s;
            color: #fff;
            font-weight: 500;
        }
        .btn-primary { background: linear-gradient(135deg, #667eea, #764ba2); }
        .btn-primary:hover { transform: scale(1.05); box-shadow: 0 10px 30px rgba(102, 126, 234, 0.3); }
        .btn-success { background: linear-gradient(135deg, #51cf66, #40c057); }
        .btn-success:hover { transform: scale(1.05); }
        .btn-danger { background: linear-gradient(135deg, #ff6b6b, #e03131); }
        .btn-danger:hover { transform: scale(1.05); }
        .btn-secondary { background: rgba(255,255,255,0.1); }
        .btn-secondary:hover { background: rgba(255,255,255,0.2); }
        .result-box {
            display: none;
            margin-top: 30px;
            background: rgba(255, 255, 255, 0.04);
            border: 1px solid rgba(255, 255, 255, 0.06);
            border-radius: 20px;
            padding: 30px;
        }
        .result-box .group-info { margin-bottom: 20px; }
        .result-box .group-info .label { color: rgba(255,255,255,0.5); }
        .result-box .group-info .value { color: #667eea; word-break: break-all; }
        .gallery-preview {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
            gap: 15px;
            margin: 20px 0;
        }
        .gallery-preview .thumb {
            background: rgba(255,255,255,0.03);
            border-radius: 10px;
            overflow: hidden;
        }
        .gallery-preview .thumb img { width: 100%; height: 150px; object-fit: cover; }
        .gallery-preview .thumb .name { padding: 8px; font-size: 0.75em; color: rgba(255,255,255,0.6); text-align: center; word-break: break-all; }
        .btn-group { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 15px; }
        .qr-container { text-align: center; padding: 15px; background: #fff; border-radius: 12px; display: inline-block; margin-top: 15px; }
        .qr-container img { max-width: 200px; }
        .toast-container {
            position: fixed;
            bottom: 30px;
            right: 30px;
            z-index: 999;
            display: flex;
            flex-direction: column;
            gap: 10px;
        }
        .toast {
            padding: 14px 24px;
            border-radius: 12px;
            background: rgba(20, 20, 40, 0.95);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.1);
            color: #fff;
            font-size: 0.95em;
            animation: slideIn 0.3s ease-out;
        }
        .toast.success { border-left: 4px solid #51cf66; }
        .toast.error { border-left: 4px solid #ff6b6b; }
        @keyframes slideIn {
            from { transform: translateX(100px); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }
        .modal {
            display: none;
            position: fixed;
            top: 0; left: 0;
            width: 100%; height: 100%;
            background: rgba(0,0,0,0.7);
            backdrop-filter: blur(5px);
            z-index: 1000;
            justify-content: center;
            align-items: center;
        }
        .modal-content {
            background: #1a1a2e;
            padding: 30px;
            border-radius: 20px;
            max-width: 400px;
            width: 90%;
            text-align: center;
        }
        .modal-content h3 { margin-bottom: 15px; }
        .modal-content p { color: rgba(255,255,255,0.7); margin-bottom: 20px; }
        .modal .btn-group { justify-content: center; }
        @media (max-width: 600px) {
            .container { padding: 15px; }
            .header h1 { font-size: 1.3em; }
            .upload-area { padding: 30px 15px; }
            .result-box { padding: 20px; }
            .gallery-preview { grid-template-columns: repeat(auto-fill, minmax(120px, 1fr)); }
            .gallery-preview .thumb img { height: 120px; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📸📸 <span>Multiple Image Upload</span></h1>
            <a href="{{ url_for('dashboard') }}" class="btn-back">🏠 Dashboard</a>
        </div>
        
        <div class="upload-area" onclick="document.getElementById('fileInput').click()">
            <div class="icon">📸</div>
            <div class="text">Click to select multiple images</div>
            <div class="sub">or drag & drop here (Stored in Cloudinary)</div>
            <input type="file" id="fileInput" accept="image/*" multiple onchange="handleFiles(this.files)">
        </div>
        
        <div class="selected-files" id="selectedFiles"></div>
        
        <div style="margin-top:15px;display:flex;gap:10px;flex-wrap:wrap;">
            <button class="btn btn-primary" onclick="uploadFiles()" id="uploadBtn">🚀 Create Image Group</button>
            <button class="btn btn-secondary" onclick="clearFiles()">🗑️ Clear All</button>
        </div>
        
        <div class="loading" id="loading">
            <div class="spinner"></div>
            <p style="margin-top:15px;">Uploading & generating group QR code...</p>
        </div>
        
        <div class="result-box" id="resultBox">
            <div class="group-info">
                <div><span class="label">📁 Group Name:</span> <span class="value" id="groupName">-</span></div>
                <div><span class="label">📸 Images:</span> <span class="value" id="imageCount">-</span></div>
                <div><span class="label">🔗 Group URL:</span> <span class="value" id="groupUrl">-</span></div>
            </div>
            <div class="gallery-preview" id="galleryPreview"></div>
            <div class="btn-group">
                <button class="btn btn-primary" onclick="copyGroupLink()">📋 Copy Group Link</button>
                <button class="btn btn-success" onclick="downloadGroupQR()">⬇️ Download QR</button>
                <button class="btn btn-danger" onclick="deleteGroup()">🗑️ Delete Group</button>
                <button class="btn btn-secondary" onclick="location.reload()">➕ Add More Images</button>
            </div>
            <div style="text-align:center;">
                <div class="qr-container">
                    <p style="color:#333;margin-bottom:10px;">🧾 Group QR Code</p>
                    <img id="groupQrImg" alt="Group QR Code">
                </div>
            </div>
        </div>
        
        <div style="margin-top:30px;text-align:center;color:rgba(255,255,255,0.2);font-size:0.8em;">
            🔨 Created by TORIKUL | ✅ Data stored in Supabase + Cloudinary
        </div>
    </div>
    
    <div class="toast-container" id="toastContainer"></div>
    
    <div class="modal" id="confirmModal">
        <div class="modal-content">
            <h3>⚠️ Delete Entire Group?</h3>
            <p>This will delete all images inside this group from Cloudinary.</p>
            <div class="btn-group">
                <button class="btn btn-secondary" onclick="closeModal()">Cancel</button>
                <button class="btn btn-danger" id="confirmDelete">Delete Group</button>
            </div>
        </div>
    </div>
    
    <script>
        let selectedFiles = [];
        let currentGroupId = null;
        let currentGroupUrl = '';
        
        function handleFiles(files) {
            for (let file of files) {
                if (file.type.startsWith('image/')) {
                    selectedFiles.push(file);
                    addFileTag(file);
                }
            }
            document.getElementById('fileInput').value = '';
            updateUploadBtn();
        }
        
        function addFileTag(file) {
            const container = document.getElementById('selectedFiles');
            const tag = document.createElement('div');
            tag.className = 'file-tag';
            tag.innerHTML = `📸 ${file.name.substring(0, 20)} <span class="remove" onclick="removeFile('${file.name}')">✕</span>`;
            tag.dataset.name = file.name;
            container.appendChild(tag);
        }
        
        function removeFile(name) {
            selectedFiles = selectedFiles.filter(f => f.name !== name);
            const container = document.getElementById('selectedFiles');
            const tags = container.querySelectorAll('.file-tag');
            tags.forEach(tag => {
                if (tag.dataset.name === name) tag.remove();
            });
            updateUploadBtn();
        }
        
        function clearFiles() {
            selectedFiles = [];
            document.getElementById('selectedFiles').innerHTML = '';
            updateUploadBtn();
        }
        
        function updateUploadBtn() {
            const btn = document.getElementById('uploadBtn');
            btn.textContent = selectedFiles.length > 0 ? `🚀 Create Group (${selectedFiles.length} images)` : '🚀 Create Image Group';
            btn.disabled = selectedFiles.length === 0;
        }
        
        function uploadFiles() {
            if (selectedFiles.length === 0) return;
            
            document.getElementById('loading').style.display = 'block';
            document.getElementById('resultBox').style.display = 'none';
            
            const formData = new FormData();
            for (let file of selectedFiles) {
                formData.append('photos', file);
            }
            
            fetch('/api/multiple-upload', {
                method: 'POST',
                body: formData
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    currentGroupId = data.group_id;
                    currentGroupUrl = data.group_url;
                    
                    document.getElementById('groupName').textContent = data.group_name;
                    document.getElementById('imageCount').textContent = data.count + ' images';
                    document.getElementById('groupUrl').textContent = data.group_url;
                    
                    const preview = document.getElementById('galleryPreview');
                    preview.innerHTML = '';
                    data.files.forEach(img => {
                        const div = document.createElement('div');
                        div.className = 'thumb';
                        div.innerHTML = `
                            <img src="${img.url}" alt="${img.original_name}">
                            <div class="name">${img.original_name.substring(0, 20)}</div>
                        `;
                        preview.appendChild(div);
                    });
                    
                    fetch('/api/qr-group/' + data.group_id)
                        .then(res => res.json())
                        .then(qrData => {
                            document.getElementById('groupQrImg').src = 'data:image/png;base64,' + qrData.qr;
                            document.getElementById('resultBox').style.display = 'block';
                            document.getElementById('loading').style.display = 'none';
                            selectedFiles = [];
                            document.getElementById('selectedFiles').innerHTML = '';
                            updateUploadBtn();
                            showToast('✅ Group created with ' + data.count + ' images!', 'success');
                        });
                }
            })
            .catch(err => {
                document.getElementById('loading').style.display = 'none';
                showToast('❌ Upload failed!', 'error');
            });
        }
        
        function copyGroupLink() {
            const url = document.getElementById('groupUrl').textContent;
            navigator.clipboard.writeText(url).then(() => {
                showToast('✅ Group link copied!', 'success');
            }).catch(() => {
                prompt('Copy this link:', url);
            });
        }
        
        function downloadGroupQR() {
            const img = document.getElementById('groupQrImg');
            const link = document.createElement('a');
            link.download = 'group_qr_' + currentGroupId + '.png';
            link.href = img.src;
            link.click();
            showToast('✅ QR Code downloaded!', 'success');
        }
        
        function deleteGroup() {
            if (!currentGroupId) return;
            document.getElementById('confirmModal').style.display = 'flex';
            document.getElementById('confirmDelete').onclick = function() {
                closeModal();
                fetch('/api/delete-group/' + currentGroupId, { method: 'DELETE' })
                    .then(res => res.json())
                    .then(data => {
                        if (data.success) {
                            showToast('✅ Group deleted from Cloudinary!', 'success');
                            document.getElementById('resultBox').style.display = 'none';
                        } else {
                            showToast('❌ Delete failed!', 'error');
                        }
                    });
            };
        }
        
        function closeModal() {
            document.getElementById('confirmModal').style.display = 'none';
        }
        
        function showToast(message, type = 'success') {
            const container = document.getElementById('toastContainer');
            const toast = document.createElement('div');
            toast.className = `toast ${type}`;
            toast.textContent = message;
            container.appendChild(toast);
            setTimeout(() => { toast.remove(); }, 3000);
        }
        
        const dropArea = document.querySelector('.upload-area');
        dropArea.addEventListener('dragover', (e) => {
            e.preventDefault();
            dropArea.style.borderColor = '#764ba2';
        });
        dropArea.addEventListener('dragleave', () => {
            dropArea.style.borderColor = 'rgba(102, 126, 234, 0.3)';
        });
        dropArea.addEventListener('drop', (e) => {
            e.preventDefault();
            dropArea.style.borderColor = 'rgba(102, 126, 234, 0.3)';
            handleFiles(e.dataTransfer.files);
        });
    </script>
</body>
</html>
'''

# ============ LINK TO QR TEMPLATE ============

LINK_QR_TEMPLATE = '''
<!DOCTYPE html>
<html lang="bn">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Link to QR - TORIKUL IMAGE • LINK • QR SYSTEM</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #0a0a1a;
            min-height: 100vh;
            color: #fff;
        }
        .container { max-width: 900px; margin: 0 auto; padding: 20px; }
        .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 30px; flex-wrap: wrap; gap: 15px; }
        .header h1 { font-size: 1.8em; }
        .header h1 span { background: linear-gradient(135deg, #667eea, #764ba2); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .btn-back {
            padding: 10px 20px;
            background: rgba(255,255,255,0.06);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 10px;
            color: #fff;
            text-decoration: none;
            transition: all 0.3s;
        }
        .btn-back:hover { background: rgba(255,255,255,0.12); }
        .input-area {
            background: rgba(255, 255, 255, 0.04);
            border: 1px solid rgba(255, 255, 255, 0.06);
            border-radius: 16px;
            padding: 30px;
        }
        .input-area label { display: block; color: rgba(255,255,255,0.7); margin-bottom: 8px; font-weight: 500; }
        .input-area input {
            width: 100%;
            padding: 14px 20px;
            background: rgba(255, 255, 255, 0.06);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 12px;
            color: #fff;
            font-size: 1em;
            transition: all 0.3s;
            outline: none;
        }
        .input-area input:focus { border-color: #667eea; background: rgba(255, 255, 255, 0.08); }
        .input-area input::placeholder { color: rgba(255, 255, 255, 0.3); }
        .btn {
            padding: 12px 30px;
            border: none;
            border-radius: 12px;
            font-size: 1em;
            cursor: pointer;
            transition: all 0.3s;
            color: #fff;
            font-weight: 500;
        }
        .btn-primary { background: linear-gradient(135deg, #667eea, #764ba2); }
        .btn-primary:hover { transform: scale(1.05); box-shadow: 0 10px 30px rgba(102, 126, 234, 0.3); }
        .btn-success { background: linear-gradient(135deg, #51cf66, #40c057); }
        .btn-success:hover { transform: scale(1.05); }
        .btn-danger { background: linear-gradient(135deg, #ff6b6b, #e03131); }
        .btn-danger:hover { transform: scale(1.05); }
        .btn-secondary { background: rgba(255,255,255,0.1); }
        .btn-secondary:hover { background: rgba(255,255,255,0.2); }
        .btn-group { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 15px; }
        .input-row { display: flex; gap: 15px; margin-top: 15px; flex-wrap: wrap; }
        .input-row input { flex: 1; min-width: 200px; }
        .result-box {
            display: none;
            margin-top: 30px;
            background: rgba(255, 255, 255, 0.04);
            border: 1px solid rgba(255, 255, 255, 0.06);
            border-radius: 20px;
            padding: 30px;
        }
        .qr-result {
            display: flex;
            flex-wrap: wrap;
            gap: 30px;
            align-items: center;
            justify-content: center;
        }
        .qr-result .info { flex: 1; min-width: 200px; }
        .qr-result .info .url { color: #667eea; word-break: break-all; }
        .qr-result .qr-box { text-align: center; padding: 15px; background: #fff; border-radius: 12px; }
        .qr-result .qr-box img { max-width: 200px; }
        .toast-container {
            position: fixed;
            bottom: 30px;
            right: 30px;
            z-index: 999;
            display: flex;
            flex-direction: column;
            gap: 10px;
        }
        .toast {
            padding: 14px 24px;
            border-radius: 12px;
            background: rgba(20, 20, 40, 0.95);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.1);
            color: #fff;
            font-size: 0.95em;
            animation: slideIn 0.3s ease-out;
        }
        .toast.success { border-left: 4px solid #51cf66; }
        .toast.error { border-left: 4px solid #ff6b6b; }
        @keyframes slideIn {
            from { transform: translateX(100px); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }
        .status-msg {
            padding: 12px 16px;
            border-radius: 10px;
            margin-top: 10px;
            display: none;
        }
        .status-msg.success { display: block; background: rgba(81, 207, 102, 0.15); border: 1px solid rgba(81, 207, 102, 0.2); color: #51cf66; }
        .status-msg.error { display: block; background: rgba(255, 107, 107, 0.15); border: 1px solid rgba(255, 107, 107, 0.2); color: #ff6b6b; }
        @media (max-width: 600px) {
            .container { padding: 15px; }
            .header h1 { font-size: 1.3em; }
            .input-area { padding: 20px; }
            .qr-result { flex-direction: column; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔗 <span>Link to QR Code</span></h1>
            <a href="{{ url_for('dashboard') }}" class="btn-back">🏠 Dashboard</a>
        </div>
        
        <div class="input-area">
            <label>🔗 Enter any URL</label>
            <div class="input-row">
                <input type="text" id="linkInput" placeholder="https://example.com" oninput="validateLink()">
                <button class="btn btn-primary" onclick="generateQR()">🧾 Generate QR</button>
            </div>
            <div class="status-msg" id="statusMsg"></div>
        </div>
        
        <div class="result-box" id="resultBox">
            <div class="qr-result">
                <div class="info">
                    <div><span style="color:rgba(255,255,255,0.5);">🔗 URL:</span> <span class="url" id="resultUrl">-</span></div>
                    <div style="margin-top:10px;color:rgba(255,255,255,0.4);font-size:0.85em;">✅ Valid Link</div>
                    <div class="btn-group">
                        <button class="btn btn-primary" onclick="copyResultLink()">📋 Copy Link</button>
                        <button class="btn btn-success" onclick="downloadResultQR()">⬇️ Download QR</button>
                        <button class="btn btn-danger" onclick="deleteLink()">🗑️ Delete Link</button>
                    </div>
                </div>
                <div class="qr-box">
                    <p style="color:#333;margin-bottom:10px;">🧾 QR Code</p>
                    <img id="resultQrImg" alt="QR Code">
                </div>
            </div>
        </div>
        
        <div style="margin-top:30px;text-align:center;color:rgba(255,255,255,0.2);font-size:0.8em;">
            🔨 Created by TORIKUL | ✅ Data stored in Supabase
        </div>
    </div>
    
    <div class="toast-container" id="toastContainer"></div>
    
    <div class="modal" id="confirmModal" style="display:none;position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.7);backdrop-filter:blur(5px);z-index:1000;justify-content:center;align-items:center;">
        <div class="modal-content" style="background:#1a1a2e;padding:30px;border-radius:20px;max-width:400px;width:90%;text-align:center;">
            <h3>⚠️ Are You Sure?</h3>
            <p style="color:rgba(255,255,255,0.7);margin-bottom:20px;">Do you really want to delete this link?</p>
            <div style="display:flex;gap:10px;justify-content:center;">
                <button class="btn btn-secondary" onclick="closeModal()">Cancel</button>
                <button class="btn btn-danger" id="confirmDelete">Delete</button>
            </div>
        </div>
    </div>
    
    <script>
        let currentLinkId = null;
        let currentLinkUrl = '';
        
        function validateLink() {
            const input = document.getElementById('linkInput');
            const status = document.getElementById('statusMsg');
            const url = input.value.trim();
            
            if (!url) {
                status.className = 'status-msg';
                status.textContent = '';
                return;
            }
            
            fetch('/api/validate-url', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url: url })
            })
            .then(res => res.json())
            .then(data => {
                if (data.valid) {
                    status.className = 'status-msg success';
                    status.textContent = '✅ Valid URL';
                } else {
                    status.className = 'status-msg error';
                    status.textContent = '❌ Invalid URL. Please enter a valid URL (e.g., https://example.com)';
                }
            });
        }
        
        function generateQR() {
            const input = document.getElementById('linkInput');
            const url = input.value.trim();
            
            if (!url) {
                showToast('❌ Please enter a URL!', 'error');
                return;
            }
            
            document.getElementById('resultBox').style.display = 'none';
            
            fetch('/api/link-to-qr', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url: url })
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    currentLinkId = data.link_id;
                    currentLinkUrl = data.url;
                    document.getElementById('resultUrl').textContent = data.url;
                    document.getElementById('resultQrImg').src = 'data:image/png;base64,' + data.qr;
                    document.getElementById('resultBox').style.display = 'block';
                    showToast('✅ QR Code generated & stored in Supabase!', 'success');
                } else {
                    showToast('❌ ' + data.error, 'error');
                }
            })
            .catch(err => {
                showToast('❌ Failed to generate QR!', 'error');
            });
        }
        
        function copyResultLink() {
            const url = document.getElementById('resultUrl').textContent;
            navigator.clipboard.writeText(url).then(() => {
                showToast('✅ Link copied!', 'success');
            }).catch(() => {
                prompt('Copy this link:', url);
            });
        }
        
        function downloadResultQR() {
            const img = document.getElementById('resultQrImg');
            const link = document.createElement('a');
            link.download = 'qr_' + currentLinkId + '.png';
            link.href = img.src;
            link.click();
            showToast('✅ QR Code downloaded!', 'success');
        }
        
        function deleteLink() {
            if (!currentLinkId) return;
            document.getElementById('confirmModal').style.display = 'flex';
            document.getElementById('confirmDelete').onclick = function() {
                closeModal();
                fetch('/api/delete-link/' + currentLinkId, { method: 'DELETE' })
                    .then(res => res.json())
                    .then(data => {
                        if (data.success) {
                            showToast('✅ Link deleted from Supabase!', 'success');
                            document.getElementById('resultBox').style.display = 'none';
                            document.getElementById('linkInput').value = '';
                            document.getElementById('statusMsg').className = 'status-msg';
                            document.getElementById('statusMsg').textContent = '';
                            currentLinkId = null;
                        } else {
                            showToast('❌ Delete failed!', 'error');
                        }
                    });
            };
        }
        
        function closeModal() {
            document.getElementById('confirmModal').style.display = 'none';
        }
        
        function showToast(message, type = 'success') {
            const container = document.getElementById('toastContainer');
            const toast = document.createElement('div');
            toast.className = `toast ${type}`;
            toast.textContent = message;
            container.appendChild(toast);
            setTimeout(() => { toast.remove(); }, 3000);
        }
        
        document.getElementById('linkInput').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') generateQR();
        });
    </script>
</body>
</html>
'''

# ============ MULTIPLE LINK QR TEMPLATE ============

MULTIPLE_LINK_QR_TEMPLATE = '''
<!DOCTYPE html>
<html lang="bn">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Multiple Links to QR - TORIKUL IMAGE • LINK • QR SYSTEM</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #0a0a1a;
            min-height: 100vh;
            color: #fff;
        }
        .container { max-width: 1100px; margin: 0 auto; padding: 20px; }
        .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 30px; flex-wrap: wrap; gap: 15px; }
        .header h1 { font-size: 1.8em; }
        .header h1 span { background: linear-gradient(135deg, #667eea, #764ba2); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .btn-back {
            padding: 10px 20px;
            background: rgba(255,255,255,0.06);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 10px;
            color: #fff;
            text-decoration: none;
            transition: all 0.3s;
        }
        .btn-back:hover { background: rgba(255,255,255,0.12); }
        .input-area {
            background: rgba(255, 255, 255, 0.04);
            border: 1px solid rgba(255, 255, 255, 0.06);
            border-radius: 16px;
            padding: 30px;
        }
        .input-area label { display: block; color: rgba(255,255,255,0.7); margin-bottom: 8px; font-weight: 500; }
        .input-area textarea {
            width: 100%;
            padding: 14px 20px;
            background: rgba(255, 255, 255, 0.06);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 12px;
            color: #fff;
            font-size: 1em;
            transition: all 0.3s;
            outline: none;
            min-height: 150px;
            resize: vertical;
            font-family: inherit;
        }
        .input-area textarea:focus { border-color: #667eea; background: rgba(255, 255, 255, 0.08); }
        .input-area textarea::placeholder { color: rgba(255, 255, 255, 0.3); }
        .btn {
            padding: 12px 30px;
            border: none;
            border-radius: 12px;
            font-size: 1em;
            cursor: pointer;
            transition: all 0.3s;
            color: #fff;
            font-weight: 500;
        }
        .btn-primary { background: linear-gradient(135deg, #667eea, #764ba2); }
        .btn-primary:hover { transform: scale(1.05); box-shadow: 0 10px 30px rgba(102, 126, 234, 0.3); }
        .btn-success { background: linear-gradient(135deg, #51cf66, #40c057); }
        .btn-success:hover { transform: scale(1.05); }
        .btn-danger { background: linear-gradient(135deg, #ff6b6b, #e03131); }
        .btn-danger:hover { transform: scale(1.05); }
        .btn-secondary { background: rgba(255,255,255,0.1); }
        .btn-secondary:hover { background: rgba(255,255,255,0.2); }
        .btn-group { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 15px; }
        .result-box {
            display: none;
            margin-top: 30px;
            background: rgba(255, 255, 255, 0.04);
            border: 1px solid rgba(255, 255, 255, 0.06);
            border-radius: 20px;
            padding: 30px;
        }
        .result-box .group-info { margin-bottom: 20px; }
        .result-box .group-info .label { color: rgba(255,255,255,0.5); }
        .result-box .group-info .value { color: #667eea; word-break: break-all; }
        .links-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }
        .link-card {
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid rgba(255, 255, 255, 0.06);
            border-radius: 12px;
            padding: 15px;
        }
        .link-card .link-url { color: #667eea; word-break: break-all; font-size: 0.85em; }
        .link-card .qr-small { text-align: center; padding: 10px; background: #fff; border-radius: 8px; margin-top: 10px; }
        .link-card .qr-small img { max-width: 120px; }
        .link-card .btn-group-small { display: flex; flex-wrap: wrap; gap: 5px; margin-top: 10px; }
        .link-card .btn-small {
            padding: 5px 12px;
            border: none;
            border-radius: 6px;
            font-size: 0.75em;
            cursor: pointer;
            transition: all 0.3s;
            color: #fff;
        }
        .btn-small-primary { background: linear-gradient(135deg, #667eea, #764ba2); }
        .btn-small-success { background: linear-gradient(135deg, #51cf66, #40c057); }
        .btn-small-danger { background: linear-gradient(135deg, #ff6b6b, #e03131); }
        .qr-container { text-align: center; padding: 15px; background: #fff; border-radius: 12px; display: inline-block; margin-top: 15px; }
        .qr-container img { max-width: 200px; }
        .toast-container {
            position: fixed;
            bottom: 30px;
            right: 30px;
            z-index: 999;
            display: flex;
            flex-direction: column;
            gap: 10px;
        }
        .toast {
            padding: 14px 24px;
            border-radius: 12px;
            background: rgba(20, 20, 40, 0.95);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.1);
            color: #fff;
            font-size: 0.95em;
            animation: slideIn 0.3s ease-out;
        }
        .toast.success { border-left: 4px solid #51cf66; }
        .toast.error { border-left: 4px solid #ff6b6b; }
        @keyframes slideIn {
            from { transform: translateX(100px); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }
        .modal {
            display: none;
            position: fixed;
            top: 0; left: 0;
            width: 100%; height: 100%;
            background: rgba(0,0,0,0.7);
            backdrop-filter: blur(5px);
            z-index: 1000;
            justify-content: center;
            align-items: center;
        }
        .modal-content {
            background: #1a1a2e;
            padding: 30px;
            border-radius: 20px;
            max-width: 400px;
            width: 90%;
            text-align: center;
        }
        .modal-content h3 { margin-bottom: 15px; }
        .modal-content p { color: rgba(255,255,255,0.7); margin-bottom: 20px; }
        .modal .btn-group { justify-content: center; }
        @media (max-width: 600px) {
            .container { padding: 15px; }
            .header h1 { font-size: 1.3em; }
            .input-area { padding: 20px; }
            .links-grid { grid-template-columns: 1fr; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔗🔗 <span>Multiple Links to QR</span></h1>
            <a href="{{ url_for('dashboard') }}" class="btn-back">🏠 Dashboard</a>
        </div>
        
        <div class="input-area">
            <label>🔗 Enter multiple URLs (one per line)</label>
            <textarea id="linkInput" placeholder="https://example.com&#10;https://youtube.com&#10;https://facebook.com"></textarea>
            <div style="margin-top:15px;display:flex;gap:10px;flex-wrap:wrap;">
                <button class="btn btn-primary" onclick="generateLinks()">🧾 Generate All QR</button>
                <button class="btn btn-secondary" onclick="clearLinks()">🗑️ Clear All</button>
            </div>
        </div>
        
        <div class="result-box" id="resultBox">
            <div class="group-info">
                <div><span class="label">📁 Group Name:</span> <span class="value" id="groupName">-</span></div>
                <div><span class="label">🔗 Links:</span> <span class="value" id="linkCount">-</span></div>
                <div><span class="label">🔗 Group URL:</span> <span class="value" id="groupUrl">-</span></div>
            </div>
            <div class="links-grid" id="linksGrid"></div>
            <div class="btn-group">
                <button class="btn btn-primary" onclick="copyGroupLink()">📋 Copy Group Link</button>
                <button class="btn btn-success" onclick="downloadGroupQR()">⬇️ Download QR</button>
                <button class="btn btn-danger" onclick="deleteLinkGroup()">🗑️ Delete Group</button>
                <button class="btn btn-secondary" onclick="location.reload()">➕ Add More Links</button>
            </div>
            <div style="text-align:center;">
                <div class="qr-container">
                    <p style="color:#333;margin-bottom:10px;">🧾 Group QR Code</p>
                    <img id="groupQrImg" alt="Group QR Code">
                </div>
            </div>
        </div>
        
        <div style="margin-top:30px;text-align:center;color:rgba(255,255,255,0.2);font-size:0.8em;">
            🔨 Created by TORIKUL | ✅ Data stored in Supabase
        </div>
    </div>
    
    <div class="toast-container" id="toastContainer"></div>
    
    <div class="modal" id="confirmModal">
        <div class="modal-content">
            <h3>⚠️ Delete Entire Group?</h3>
            <p>This will delete all links inside this group from Supabase.</p>
            <div class="btn-group">
                <button class="btn btn-secondary" onclick="closeModal()">Cancel</button>
                <button class="btn btn-danger" id="confirmDelete">Delete Group</button>
            </div>
        </div>
    </div>
    
    <script>
        let currentGroupId = null;
        let currentGroupUrl = '';
        
        function generateLinks() {
            const textarea = document.getElementById('linkInput');
            const lines = textarea.value.split('\\n').map(s => s.trim()).filter(s => s);
            
            if (lines.length === 0) {
                showToast('❌ Please enter at least one URL!', 'error');
                return;
            }
            
            document.getElementById('resultBox').style.display = 'none';
            
            fetch('/api/multiple-links-to-qr', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ links: lines })
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    currentGroupId = data.group_id;
                    currentGroupUrl = data.group_url;
                    
                    document.getElementById('groupName').textContent = data.group_name;
                    document.getElementById('linkCount').textContent = data.count + ' links';
                    document.getElementById('groupUrl').textContent = data.group_url;
                    
                    const grid = document.getElementById('linksGrid');
                    grid.innerHTML = '';
                    data.links.forEach(link => {
                        const card = document.createElement('div');
                        card.className = 'link-card';
                        card.innerHTML = `
                            <div class="link-url">🔗 ${link.url}</div>
                            <div class="qr-small">
                                <img src="data:image/png;base64,${link.qr}" alt="QR Code">
                            </div>
                            <div class="btn-group-small">
                                <button class="btn-small btn-small-primary" onclick="copyLink('${link.url}')">📋 Copy</button>
                                <button class="btn-small btn-small-success" onclick="downloadLinkQR('${link.link_id}')">⬇️ QR</button>
                                <button class="btn-small btn-small-danger" onclick="deleteLink('${link.link_id}')">🗑️ Delete</button>
                            </div>
                        `;
                        grid.appendChild(card);
                    });
                    
                    fetch('/api/qr-link-group/' + data.group_id)
                        .then(res => res.json())
                        .then(qrData => {
                            document.getElementById('groupQrImg').src = 'data:image/png;base64,' + qrData.qr;
                            document.getElementById('resultBox').style.display = 'block';
                            showToast('✅ Group created with ' + data.count + ' links!', 'success');
                        });
                } else {
                    showToast('❌ ' + data.error, 'error');
                }
            })
            .catch(err => {
                showToast('❌ Failed to generate QR codes!', 'error');
            });
        }
        
        function copyLink(url) {
            navigator.clipboard.writeText(url).then(() => {
                showToast('✅ Link copied!', 'success');
            }).catch(() => {
                prompt('Copy this link:', url);
            });
        }
        
        function downloadLinkQR(linkId) {
            fetch('/api/qr-link/' + linkId)
                .then(res => res.json())
                .then(data => {
                    const link = document.createElement('a');
                    link.download = 'qr_' + linkId + '.png';
                    link.href = 'data:image/png;base64,' + data.qr;
                    link.click();
                    showToast('✅ QR Code downloaded!', 'success');
                });
        }
        
        function deleteLink(linkId) {
            if (!confirm('Are you sure you want to delete this link?')) return;
            fetch('/api/delete-link/' + linkId, { method: 'DELETE' })
                .then(res => res.json())
                .then(data => {
                    if (data.success) {
                        showToast('✅ Link deleted from Supabase!', 'success');
                        location.reload();
                    } else {
                        showToast('❌ Delete failed!', 'error');
                    }
                });
        }
        
        function copyGroupLink() {
            const url = document.getElementById('groupUrl').textContent;
            navigator.clipboard.writeText(url).then(() => {
                showToast('✅ Group link copied!', 'success');
            }).catch(() => {
                prompt('Copy this link:', url);
            });
        }
        
        function downloadGroupQR() {
            const img = document.getElementById('groupQrImg');
            const link = document.createElement('a');
            link.download = 'group_qr_' + currentGroupId + '.png';
            link.href = img.src;
            link.click();
            showToast('✅ QR Code downloaded!', 'success');
        }
        
        function deleteLinkGroup() {
            if (!currentGroupId) return;
            document.getElementById('confirmModal').style.display = 'flex';
            document.getElementById('confirmDelete').onclick = function() {
                closeModal();
                fetch('/api/delete-link-group/' + currentGroupId, { method: 'DELETE' })
                    .then(res => res.json())
                    .then(data => {
                        if (data.success) {
                            showToast('✅ Group deleted from Supabase!', 'success');
                            document.getElementById('resultBox').style.display = 'none';
                        } else {
                            showToast('❌ Delete failed!', 'error');
                        }
                    });
            };
        }
        
        function clearLinks() {
            document.getElementById('linkInput').value = '';
        }
        
        function closeModal() {
            document.getElementById('confirmModal').style.display = 'none';
        }
        
        function showToast(message, type = 'success') {
            const container = document.getElementById('toastContainer');
            const toast = document.createElement('div');
            toast.className = `toast ${type}`;
            toast.textContent = message;
            container.appendChild(toast);
            setTimeout(() => { toast.remove(); }, 3000);
        }
    </script>
</body>
</html>
'''

# ============ GALLERY TEMPLATE ============

GALLERY_TEMPLATE = '''
<!DOCTYPE html>
<html lang="bn">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>My Images - TORIKUL IMAGE • LINK • QR SYSTEM</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #0a0a1a;
            min-height: 100vh;
            color: #fff;
        }
        .container { max-width: 1300px; margin: 0 auto; padding: 20px; }
        .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 30px; flex-wrap: wrap; gap: 15px; }
        .header h1 { font-size: 1.8em; }
        .header h1 span { background: linear-gradient(135deg, #667eea, #764ba2); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .btn-back {
            padding: 10px 20px;
            background: rgba(255,255,255,0.06);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 10px;
            color: #fff;
            text-decoration: none;
            transition: all 0.3s;
        }
        .btn-back:hover { background: rgba(255,255,255,0.12); }
        .gallery-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
            gap: 25px;
        }
        .image-card {
            background: rgba(255, 255, 255, 0.04);
            border: 1px solid rgba(255, 255, 255, 0.06);
            border-radius: 16px;
            overflow: hidden;
            transition: all 0.3s;
            cursor: pointer;
        }
        .image-card:hover { transform: translateY(-5px); background: rgba(255, 255, 255, 0.06); }
        .image-card .img-wrap { height: 220px; overflow: hidden; }
        .image-card .img-wrap img { width: 100%; height: 100%; object-fit: cover; transition: transform 0.3s; }
        .image-card:hover .img-wrap img { transform: scale(1.05); }
        .image-card .info { padding: 15px; }
        .image-card .info .name { font-weight: 500; word-break: break-all; font-size: 0.9em; }
        .image-card .info .meta { color: rgba(255,255,255,0.4); font-size: 0.8em; margin: 5px 0; }
        .image-card .info .url { color: #667eea; font-size: 0.75em; word-break: break-all; cursor: pointer; }
        .image-card .btn-group { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; }
        .btn {
            padding: 6px 14px;
            border: none;
            border-radius: 8px;
            font-size: 0.8em;
            cursor: pointer;
            transition: all 0.3s;
            color: #fff;
        }
        .btn-primary { background: linear-gradient(135deg, #667eea, #764ba2); }
        .btn-primary:hover { transform: scale(1.05); }
        .btn-success { background: linear-gradient(135deg, #51cf66, #40c057); }
        .btn-success:hover { transform: scale(1.05); }
        .btn-danger { background: linear-gradient(135deg, #ff6b6b, #e03131); }
        .btn-danger:hover { transform: scale(1.05); }
        .btn-secondary { background: rgba(255,255,255,0.1); }
        .btn-secondary:hover { background: rgba(255,255,255,0.2); }
        .empty-state {
            text-align: center;
            padding: 80px 20px;
        }
        .empty-state .icon { font-size: 4em; margin-bottom: 15px; }
        .empty-state h2 { margin-bottom: 10px; }
        .empty-state p { color: rgba(255,255,255,0.4); }
        .toast-container {
            position: fixed;
            bottom: 30px;
            right: 30px;
            z-index: 999;
            display: flex;
            flex-direction: column;
            gap: 10px;
        }
        .toast {
            padding: 14px 24px;
            border-radius: 12px;
            background: rgba(20, 20, 40, 0.95);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.1);
            color: #fff;
            font-size: 0.95em;
            animation: slideIn 0.3s ease-out;
        }
        .toast.success { border-left: 4px solid #51cf66; }
        .toast.error { border-left: 4px solid #ff6b6b; }
        @keyframes slideIn {
            from { transform: translateX(100px); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }
        .modal {
            display: none;
            position: fixed;
            top: 0; left: 0;
            width: 100%; height: 100%;
            background: rgba(0,0,0,0.7);
            backdrop-filter: blur(5px);
            z-index: 1000;
            justify-content: center;
            align-items: center;
        }
        .modal-content {
            background: #1a1a2e;
            padding: 30px;
            border-radius: 20px;
            max-width: 400px;
            width: 90%;
            text-align: center;
        }
        .modal-content h3 { margin-bottom: 15px; }
        .modal-content p { color: rgba(255,255,255,0.7); margin-bottom: 20px; }
        .modal .btn-group { justify-content: center; }
        @media (max-width: 600px) {
            .container { padding: 15px; }
            .header h1 { font-size: 1.3em; }
            .gallery-grid { grid-template-columns: 1fr; }
            .image-card .img-wrap { height: 180px; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🖼️ <span>My Images</span></h1>
            <div>
                <a href="{{ url_for('upload') }}" class="btn-back" style="margin-right:10px;">📸 Upload</a>
                <a href="{{ url_for('dashboard') }}" class="btn-back">🏠 Dashboard</a>
            </div>
        </div>
        
        {% if images %}
        <div class="gallery-grid">
            {% for img in images %}
            <div class="image-card" onclick="location.href='{{ url_for('single_image', filename=img.filename) }}'">
                <div class="img-wrap">
                    <img src="{{ img.url }}" alt="{{ img.filename }}" loading="lazy">
                </div>
                <div class="info">
                    <div class="name">{{ img.original_name[:35] }}{% if img.original_name|length > 35 %}...{% endif %}</div>
                    <div class="meta">📦 {{ img.size }} | 🕒 {{ img.upload_date }}</div>
                    <div class="url" onclick="event.stopPropagation();copyToClipboard('{{ img.url }}')">🔗 {{ img.url[:50] }}...</div>
                    <div class="btn-group">
                        <button class="btn btn-primary" onclick="event.stopPropagation();copyToClipboard('{{ img.url }}')">📋 Copy</button>
                        <button class="btn btn-success" onclick="event.stopPropagation();downloadQR('{{ img.filename }}')">🧾 QR</button>
                        <button class="btn btn-danger" onclick="event.stopPropagation();deleteImage('{{ img.filename }}')">🗑️ Delete</button>
                    </div>
                </div>
            </div>
            {% endfor %}
        </div>
        {% else %}
        <div class="empty-state">
            <div class="icon">📭</div>
            <h2>No Images Yet</h2>
            <p>Upload your first image to get started!</p>
            <a href="{{ url_for('upload') }}" class="btn btn-primary" style="display:inline-block;margin-top:20px;padding:12px 30px;font-size:1em;text-decoration:none;">📸 Upload Image</a>
        </div>
        {% endif %}
        
        <div style="margin-top:30px;text-align:center;color:rgba(255,255,255,0.2);font-size:0.8em;">
            🔨 Created by TORIKUL | Total: {{ images|length }} images | ✅ Stored in Cloudinary
        </div>
    </div>
    
    <div class="toast-container" id="toastContainer"></div>
    
    <div class="modal" id="confirmModal">
        <div class="modal-content">
            <h3>⚠️ Are You Sure?</h3>
            <p>Do you really want to delete this image?</p>
            <div class="btn-group">
                <button class="btn btn-secondary" onclick="closeModal()">Cancel</button>
                <button class="btn btn-danger" id="confirmDelete">Delete</button>
            </div>
        </div>
    </div>
    
    <script>
        let deleteTarget = null;
        
        function copyToClipboard(text) {
            navigator.clipboard.writeText(text).then(() => {
                showToast('✅ Link copied!', 'success');
            }).catch(() => {
                prompt('Copy this link:', text);
            });
        }
        
        function downloadQR(filename) {
            fetch('/api/qr/' + filename)
                .then(res => res.json())
                .then(data => {
                    const link = document.createElement('a');
                    link.download = 'qr_' + filename + '.png';
                    link.href = 'data:image/png;base64,' + data.qr;
                    link.click();
                    showToast('✅ QR Code downloaded!', 'success');
                });
        }
        
        function deleteImage(filename) {
            deleteTarget = filename;
            document.getElementById('confirmModal').style.display = 'flex';
            document.getElementById('confirmDelete').onclick = function() {
                closeModal();
                if (!deleteTarget) return;
                fetch('/api/delete/' + deleteTarget, { method: 'DELETE' })
                    .then(res => res.json())
                    .then(data => {
                        if (data.success) {
                            showToast('✅ Image deleted from Cloudinary!', 'success');
                            const card = document.querySelector(`.image-card[data-filename="${deleteTarget}"]`);
                            if (card) card.remove();
                            location.reload();
                        } else {
                            showToast('❌ Delete failed!', 'error');
                        }
                    });
            };
        }
        
        function closeModal() {
            document.getElementById('confirmModal').style.display = 'none';
        }
        
        function showToast(message, type = 'success') {
            const container = document.getElementById('toastContainer');
            const toast = document.createElement('div');
            toast.className = `toast ${type}`;
            toast.textContent = message;
            container.appendChild(toast);
            setTimeout(() => { toast.remove(); }, 3000);
        }
    </script>
</body>
</html>
'''

# ============ IMAGE GROUPS TEMPLATE ============

GROUPS_TEMPLATE = '''
<!DOCTYPE html>
<html lang="bn">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Image Groups - TORIKUL IMAGE • LINK • QR SYSTEM</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #0a0a1a;
            min-height: 100vh;
            color: #fff;
        }
        .container { max-width: 1300px; margin: 0 auto; padding: 20px; }
        .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 30px; flex-wrap: wrap; gap: 15px; }
        .header h1 { font-size: 1.8em; }
        .header h1 span { background: linear-gradient(135deg, #667eea, #764ba2); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .btn-back {
            padding: 10px 20px;
            background: rgba(255,255,255,0.06);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 10px;
            color: #fff;
            text-decoration: none;
            transition: all 0.3s;
        }
        .btn-back:hover { background: rgba(255,255,255,0.12); }
        .groups-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
            gap: 25px;
        }
        .group-card {
            background: rgba(255, 255, 255, 0.04);
            border: 1px solid rgba(255, 255, 255, 0.06);
            border-radius: 16px;
            overflow: hidden;
            transition: all 0.3s;
        }
        .group-card:hover { transform: translateY(-5px); background: rgba(255, 255, 255, 0.06); }
        .group-card .thumb-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 2px;
            height: 150px;
            cursor: pointer;
        }
        .group-card .thumb-grid img { width: 100%; height: 100%; object-fit: cover; }
        .group-card .thumb-grid .more { display: flex; justify-content: center; align-items: center; background: rgba(102, 126, 234, 0.2); font-size: 1.2em; }
        .group-card .info { padding: 15px; }
        .group-card .info .name { font-weight: 600; font-size: 1.1em; }
        .group-card .info .meta { color: rgba(255,255,255,0.4); font-size: 0.85em; margin: 5px 0; }
        .group-card .info .url { color: #667eea; font-size: 0.75em; word-break: break-all; cursor: pointer; }
        .group-card .info .views { color: rgba(255,255,255,0.3); font-size: 0.7em; margin-top: 5px; }
        .group-card .btn-group { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; }
        .btn {
            padding: 6px 14px;
            border: none;
            border-radius: 8px;
            font-size: 0.8em;
            cursor: pointer;
            transition: all 0.3s;
            color: #fff;
        }
        .btn-primary { background: linear-gradient(135deg, #667eea, #764ba2); }
        .btn-primary:hover { transform: scale(1.05); }
        .btn-success { background: linear-gradient(135deg, #51cf66, #40c057); }
        .btn-success:hover { transform: scale(1.05); }
        .btn-danger { background: linear-gradient(135deg, #ff6b6b, #e03131); }
        .btn-danger:hover { transform: scale(1.05); }
        .btn-secondary { background: rgba(255,255,255,0.1); }
        .btn-secondary:hover { background: rgba(255,255,255,0.2); }
        .empty-state {
            text-align: center;
            padding: 80px 20px;
        }
        .empty-state .icon { font-size: 4em; margin-bottom: 15px; }
        .empty-state h2 { margin-bottom: 10px; }
        .empty-state p { color: rgba(255,255,255,0.4); }
        .toast-container {
            position: fixed;
            bottom: 30px;
            right: 30px;
            z-index: 999;
            display: flex;
            flex-direction: column;
            gap: 10px;
        }
        .toast {
            padding: 14px 24px;
            border-radius: 12px;
            background: rgba(20, 20, 40, 0.95);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.1);
            color: #fff;
            font-size: 0.95em;
            animation: slideIn 0.3s ease-out;
        }
        .toast.success { border-left: 4px solid #51cf66; }
        .toast.error { border-left: 4px solid #ff6b6b; }
        @keyframes slideIn {
            from { transform: translateX(100px); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }
        .modal {
            display: none;
            position: fixed;
            top: 0; left: 0;
            width: 100%; height: 100%;
            background: rgba(0,0,0,0.7);
            backdrop-filter: blur(5px);
            z-index: 1000;
            justify-content: center;
            align-items: center;
        }
        .modal-content {
            background: #1a1a2e;
            padding: 30px;
            border-radius: 20px;
            max-width: 400px;
            width: 90%;
            text-align: center;
        }
        .modal-content h3 { margin-bottom: 15px; }
        .modal-content p { color: rgba(255,255,255,0.7); margin-bottom: 20px; }
        .modal .btn-group { justify-content: center; }
        @media (max-width: 600px) {
            .container { padding: 15px; }
            .header h1 { font-size: 1.3em; }
            .groups-grid { grid-template-columns: 1fr; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📁 <span>Image Groups</span></h1>
            <div>
                <a href="{{ url_for('multiple_upload') }}" class="btn-back" style="margin-right:10px;">📸 New Group</a>
                <a href="{{ url_for('dashboard') }}" class="btn-back">🏠 Dashboard</a>
            </div>
        </div>
        
        {% if groups %}
        <div class="groups-grid">
            {% for gid, group in groups.items() %}
            <div class="group-card" data-groupid="{{ gid }}">
                <div class="thumb-grid" onclick="window.open('{{ group.url }}', '_blank')">
                    {% for img in group.images[:3] %}
                    <img src="{{ img.url }}" alt="{{ img.original_name }}" loading="lazy">
                    {% endfor %}
                    {% if group.images|length > 3 %}
                    <div class="more">+{{ group.images|length - 3 }}</div>
                    {% endif %}
                </div>
                <div class="info">
                    <div class="name">📁 {{ group.name }}</div>
                    <div class="meta">📸 {{ group.image_count }} images | 🕒 {{ group.created_at }}</div>
                    <div class="views">👁️ {{ group.views }} views</div>
                    <div class="url" onclick="copyToClipboard('{{ group.url }}')">🔗 {{ group.url }}</div>
                    <div class="btn-group">
                        <button class="btn btn-primary" onclick="copyToClipboard('{{ group.url }}')">📋 Copy Link</button>
                        <button class="btn btn-success" onclick="downloadGroupQR('{{ gid }}')">🧾 QR</button>
                        <button class="btn btn-secondary" onclick="window.open('{{ group.url }}', '_blank')">👁️ View</button>
                        <button class="btn btn-danger" onclick="deleteGroup('{{ gid }}')">🗑️ Delete</button>
                    </div>
                </div>
            </div>
            {% endfor %}
        </div>
        {% else %}
        <div class="empty-state">
            <div class="icon">📭</div>
            <h2>No Groups Yet</h2>
            <p>Create your first image group by uploading multiple images!</p>
            <a href="{{ url_for('multiple_upload') }}" class="btn btn-primary" style="display:inline-block;margin-top:20px;padding:12px 30px;font-size:1em;text-decoration:none;">📸 Create Group</a>
        </div>
        {% endif %}
        
        <div style="margin-top:30px;text-align:center;color:rgba(255,255,255,0.2);font-size:0.8em;">
            🔨 Created by TORIKUL | Total: {{ groups|length }} groups | ✅ Stored in Supabase + Cloudinary
        </div>
    </div>
    
    <div class="toast-container" id="toastContainer"></div>
    
    <div class="modal" id="confirmModal">
        <div class="modal-content">
            <h3>⚠️ Delete Entire Group?</h3>
            <p>This will delete all images inside this group from Cloudinary.</p>
            <div class="btn-group">
                <button class="btn btn-secondary" onclick="closeModal()">Cancel</button>
                <button class="btn btn-danger" id="confirmDelete">Delete Group</button>
            </div>
        </div>
    </div>
    
    <script>
        let deleteTarget = null;
        
        function copyToClipboard(text) {
            navigator.clipboard.writeText(text).then(() => {
                showToast('✅ Link copied!', 'success');
            }).catch(() => {
                prompt('Copy this link:', text);
            });
        }
        
        function downloadGroupQR(groupId) {
            fetch('/api/qr-group/' + groupId)
                .then(res => res.json())
                .then(data => {
                    const link = document.createElement('a');
                    link.download = 'group_qr_' + groupId + '.png';
                    link.href = 'data:image/png;base64,' + data.qr;
                    link.click();
                    showToast('✅ QR Code downloaded!', 'success');
                });
        }
        
        function deleteGroup(groupId) {
            deleteTarget = groupId;
            document.getElementById('confirmModal').style.display = 'flex';
            document.getElementById('confirmDelete').onclick = function() {
                closeModal();
                if (!deleteTarget) return;
                fetch('/api/delete-group/' + deleteTarget, { method: 'DELETE' })
                    .then(res => res.json())
                    .then(data => {
                        if (data.success) {
                            showToast('✅ Group deleted from Cloudinary!', 'success');
                            const card = document.querySelector(`.group-card[data-groupid="${deleteTarget}"]`);
                            if (card) card.remove();
                        } else {
                            showToast('❌ Delete failed!', 'error');
                        }
                    });
            };
        }
        
        function closeModal() {
            document.getElementById('confirmModal').style.display = 'none';
        }
        
        function showToast(message, type = 'success') {
            const container = document.getElementById('toastContainer');
            const toast = document.createElement('div');
            toast.className = `toast ${type}`;
            toast.textContent = message;
            container.appendChild(toast);
            setTimeout(() => { toast.remove(); }, 3000);
        }
    </script>
</body>
</html>
'''

# ============ LINK GROUPS TEMPLATE ============

LINK_GROUPS_TEMPLATE = '''
<!DOCTYPE html>
<html lang="bn">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Link Groups - TORIKUL IMAGE • LINK • QR SYSTEM</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #0a0a1a;
            min-height: 100vh;
            color: #fff;
        }
        .container { max-width: 1300px; margin: 0 auto; padding: 20px; }
        .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 30px; flex-wrap: wrap; gap: 15px; }
        .header h1 { font-size: 1.8em; }
        .header h1 span { background: linear-gradient(135deg, #667eea, #764ba2); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .btn-back {
            padding: 10px 20px;
            background: rgba(255,255,255,0.06);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 10px;
            color: #fff;
            text-decoration: none;
            transition: all 0.3s;
        }
        .btn-back:hover { background: rgba(255,255,255,0.12); }
        .groups-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
            gap: 25px;
        }
        .group-card {
            background: rgba(255, 255, 255, 0.04);
            border: 1px solid rgba(255, 255, 255, 0.06);
            border-radius: 16px;
            overflow: hidden;
            transition: all 0.3s;
            padding: 20px;
        }
        .group-card:hover { transform: translateY(-5px); background: rgba(255, 255, 255, 0.06); }
        .group-card .name { font-weight: 600; font-size: 1.1em; cursor: pointer; }
        .group-card .meta { color: rgba(255,255,255,0.4); font-size: 0.85em; margin: 5px 0; }
        .group-card .url { color: #667eea; font-size: 0.75em; word-break: break-all; cursor: pointer; }
        .group-card .views { color: rgba(255,255,255,0.3); font-size: 0.7em; margin-top: 5px; }
        .group-card .links-preview {
            margin: 10px 0;
            padding: 10px;
            background: rgba(255,255,255,0.03);
            border-radius: 8px;
            max-height: 120px;
            overflow-y: auto;
        }
        .group-card .links-preview .link-item {
            font-size: 0.8em;
            color: rgba(255,255,255,0.6);
            padding: 3px 0;
            border-bottom: 1px solid rgba(255,255,255,0.03);
            word-break: break-all;
        }
        .group-card .btn-group { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; }
        .btn {
            padding: 6px 14px;
            border: none;
            border-radius: 8px;
            font-size: 0.8em;
            cursor: pointer;
            transition: all 0.3s;
            color: #fff;
        }
        .btn-primary { background: linear-gradient(135deg, #667eea, #764ba2); }
        .btn-primary:hover { transform: scale(1.05); }
        .btn-success { background: linear-gradient(135deg, #51cf66, #40c057); }
        .btn-success:hover { transform: scale(1.05); }
        .btn-danger { background: linear-gradient(135deg, #ff6b6b, #e03131); }
        .btn-danger:hover { transform: scale(1.05); }
        .btn-secondary { background: rgba(255,255,255,0.1); }
        .btn-secondary:hover { background: rgba(255,255,255,0.2); }
        .empty-state {
            text-align: center;
            padding: 80px 20px;
        }
        .empty-state .icon { font-size: 4em; margin-bottom: 15px; }
        .empty-state h2 { margin-bottom: 10px; }
        .empty-state p { color: rgba(255,255,255,0.4); }
        .toast-container {
            position: fixed;
            bottom: 30px;
            right: 30px;
            z-index: 999;
            display: flex;
            flex-direction: column;
            gap: 10px;
        }
        .toast {
            padding: 14px 24px;
            border-radius: 12px;
            background: rgba(20, 20, 40, 0.95);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.1);
            color: #fff;
            font-size: 0.95em;
            animation: slideIn 0.3s ease-out;
        }
        .toast.success { border-left: 4px solid #51cf66; }
        .toast.error { border-left: 4px solid #ff6b6b; }
        @keyframes slideIn {
            from { transform: translateX(100px); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }
        .modal {
            display: none;
            position: fixed;
            top: 0; left: 0;
            width: 100%; height: 100%;
            background: rgba(0,0,0,0.7);
            backdrop-filter: blur(5px);
            z-index: 1000;
            justify-content: center;
            align-items: center;
        }
        .modal-content {
            background: #1a1a2e;
            padding: 30px;
            border-radius: 20px;
            max-width: 400px;
            width: 90%;
            text-align: center;
        }
        .modal-content h3 { margin-bottom: 15px; }
        .modal-content p { color: rgba(255,255,255,0.7); margin-bottom: 20px; }
        .modal .btn-group { justify-content: center; }
        @media (max-width: 600px) {
            .container { padding: 15px; }
            .header h1 { font-size: 1.3em; }
            .groups-grid { grid-template-columns: 1fr; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📁🔗 <span>Link Groups</span></h1>
            <div>
                <a href="{{ url_for('multiple_link_qr') }}" class="btn-back" style="margin-right:10px;">🔗 New Group</a>
                <a href="{{ url_for('dashboard') }}" class="btn-back">🏠 Dashboard</a>
            </div>
        </div>
        
        {% if groups %}
        <div class="groups-grid">
            {% for gid, group in groups.items() %}
            <div class="group-card" data-groupid="{{ gid }}" onclick="window.open('{{ group.url }}', '_blank')">
                <div class="name">📁🔗 {{ group.name }}</div>
                <div class="meta">🔗 {{ group.link_count }} links | 🕒 {{ group.created_at }}</div>
                <div class="views">👁️ {{ group.views }} views</div>
                <div class="url" onclick="event.stopPropagation();copyToClipboard('{{ group.url }}')">🔗 {{ group.url }}</div>
                <div class="links-preview">
                    {% for link in group.links[:5] %}
                    <div class="link-item">🔗 {{ link.url }}</div>
                    {% endfor %}
                    {% if group.links|length > 5 %}
                    <div class="link-item" style="color:rgba(255,255,255,0.3);">... and {{ group.links|length - 5 }} more</div>
                    {% endif %}
                </div>
                <div class="btn-group">
                    <button class="btn btn-primary" onclick="event.stopPropagation();copyToClipboard('{{ group.url }}')">📋 Copy Link</button>
                    <button class="btn btn-success" onclick="event.stopPropagation();downloadGroupQR('{{ gid }}')">🧾 QR</button>
                    <button class="btn btn-secondary" onclick="event.stopPropagation();window.open('{{ group.url }}', '_blank')">👁️ View</button>
                    <button class="btn btn-danger" onclick="event.stopPropagation();deleteGroup('{{ gid }}')">🗑️ Delete</button>
                </div>
            </div>
            {% endfor %}
        </div>
        {% else %}
        <div class="empty-state">
            <div class="icon">📭</div>
            <h2>No Link Groups Yet</h2>
            <p>Create your first link group by adding multiple URLs!</p>
            <a href="{{ url_for('multiple_link_qr') }}" class="btn btn-primary" style="display:inline-block;margin-top:20px;padding:12px 30px;font-size:1em;text-decoration:none;">🔗 Create Group</a>
        </div>
        {% endif %}
        
        <div style="margin-top:30px;text-align:center;color:rgba(255,255,255,0.2);font-size:0.8em;">
            🔨 Created by TORIKUL | Total: {{ groups|length }} groups | ✅ Stored in Supabase
        </div>
    </div>
    
    <div class="toast-container" id="toastContainer"></div>
    
    <div class="modal" id="confirmModal">
        <div class="modal-content">
            <h3>⚠️ Delete Entire Group?</h3>
            <p>This will delete all links inside this group from Supabase.</p>
            <div class="btn-group">
                <button class="btn btn-secondary" onclick="closeModal()">Cancel</button>
                <button class="btn btn-danger" id="confirmDelete">Delete Group</button>
            </div>
        </div>
    </div>
    
    <script>
        let deleteTarget = null;
        
        function copyToClipboard(text) {
            navigator.clipboard.writeText(text).then(() => {
                showToast('✅ Link copied!', 'success');
            }).catch(() => {
                prompt('Copy this link:', text);
            });
        }
        
        function downloadGroupQR(groupId) {
            fetch('/api/qr-link-group/' + groupId)
                .then(res => res.json())
                .then(data => {
                    const link = document.createElement('a');
                    link.download = 'group_qr_' + groupId + '.png';
                    link.href = 'data:image/png;base64,' + data.qr;
                    link.click();
                    showToast('✅ QR Code downloaded!', 'success');
                });
        }
        
        function deleteGroup(groupId) {
            deleteTarget = groupId;
            document.getElementById('confirmModal').style.display = 'flex';
            document.getElementById('confirmDelete').onclick = function() {
                closeModal();
                if (!deleteTarget) return;
                fetch('/api/delete-link-group/' + deleteTarget, { method: 'DELETE' })
                    .then(res => res.json())
                    .then(data => {
                        if (data.success) {
                            showToast('✅ Group deleted from Supabase!', 'success');
                            const card = document.querySelector(`.group-card[data-groupid="${deleteTarget}"]`);
                            if (card) card.remove();
                        } else {
                            showToast('❌ Delete failed!', 'error');
                        }
                    });
            };
        }
        
        function closeModal() {
            document.getElementById('confirmModal').style.display = 'none';
        }
        
        function showToast(message, type = 'success') {
            const container = document.getElementById('toastContainer');
            const toast = document.createElement('div');
            toast.className = `toast ${type}`;
            toast.textContent = message;
            container.appendChild(toast);
            setTimeout(() => { toast.remove(); }, 3000);
        }
    </script>
</body>
</html>
'''

# ============ GROUP VIEW TEMPLATE (GALLERY VIEW) ============

GROUP_VIEW_TEMPLATE = '''
<!DOCTYPE html>
<html lang="bn">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ group.name }} - TORIKUL IMAGE • LINK • QR SYSTEM</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #0a0a1a;
            min-height: 100vh;
            color: #fff;
        }
        .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 30px;
            flex-wrap: wrap;
            gap: 15px;
        }
        .header h1 { font-size: 1.8em; }
        .header h1 span { background: linear-gradient(135deg, #667eea, #764ba2); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .btn-back {
            padding: 10px 20px;
            background: rgba(255,255,255,0.06);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 10px;
            color: #fff;
            text-decoration: none;
            transition: all 0.3s;
        }
        .btn-back:hover { background: rgba(255,255,255,0.12); }
        .group-meta {
            background: rgba(255, 255, 255, 0.04);
            border: 1px solid rgba(255, 255, 255, 0.06);
            border-radius: 16px;
            padding: 20px 25px;
            margin-bottom: 30px;
        }
        .group-meta .info { display: flex; flex-wrap: wrap; gap: 20px; }
        .group-meta .info div { color: rgba(255,255,255,0.6); }
        .group-meta .info div strong { color: #fff; }
        .group-meta .url { color: #667eea; word-break: break-all; margin-top: 10px; }
        .gallery-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
            gap: 20px;
        }
        .gallery-item {
            background: rgba(255, 255, 255, 0.04);
            border-radius: 12px;
            overflow: hidden;
            transition: all 0.3s;
            cursor: pointer;
            position: relative;
        }
        .gallery-item:hover { 
            transform: translateY(-5px); 
            background: rgba(255, 255, 255, 0.08);
            box-shadow: 0 10px 40px rgba(102, 126, 234, 0.2);
        }
        .gallery-item img { 
            width: 100%; 
            height: 200px; 
            object-fit: cover; 
            transition: transform 0.3s;
        }
        .gallery-item:hover img { transform: scale(1.05); }
        .gallery-item .name { 
            padding: 12px; 
            font-size: 0.85em; 
            color: rgba(255,255,255,0.7); 
            text-align: center; 
            word-break: break-all;
        }
        .gallery-item .overlay {
            position: absolute;
            top: 10px;
            right: 10px;
            background: rgba(0,0,0,0.6);
            padding: 5px 10px;
            border-radius: 8px;
            font-size: 0.7em;
            color: rgba(255,255,255,0.6);
        }
        .btn {
            padding: 8px 18px;
            border: none;
            border-radius: 8px;
            font-size: 0.9em;
            cursor: pointer;
            transition: all 0.3s;
            color: #fff;
            text-decoration: none;
            display: inline-block;
        }
        .btn-primary { background: linear-gradient(135deg, #667eea, #764ba2); }
        .btn-primary:hover { transform: scale(1.05); }
        .btn-success { background: linear-gradient(135deg, #51cf66, #40c057); }
        .btn-success:hover { transform: scale(1.05); }
        .btn-secondary { background: rgba(255,255,255,0.1); }
        .btn-secondary:hover { background: rgba(255,255,255,0.2); }
        .btn-group { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 15px; }
        .qr-container { text-align: center; padding: 15px; background: #fff; border-radius: 12px; display: inline-block; }
        .qr-container img { max-width: 180px; }
        .toast-container {
            position: fixed;
            bottom: 30px;
            right: 30px;
            z-index: 999;
            display: flex;
            flex-direction: column;
            gap: 10px;
        }
        .toast {
            padding: 14px 24px;
            border-radius: 12px;
            background: rgba(20, 20, 40, 0.95);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.1);
            color: #fff;
            font-size: 0.95em;
            animation: slideIn 0.3s ease-out;
        }
        .toast.success { border-left: 4px solid #51cf66; }
        .toast.error { border-left: 4px solid #ff6b6b; }
        @keyframes slideIn {
            from { transform: translateX(100px); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }
        .view-counter {
            color: rgba(255,255,255,0.3);
            font-size: 0.8em;
            margin-top: 10px;
        }
        @media (max-width: 600px) {
            .container { padding: 15px; }
            .header h1 { font-size: 1.3em; }
            .gallery-grid { grid-template-columns: 1fr; }
            .gallery-item img { height: 250px; }
            .group-meta .info { flex-direction: column; gap: 10px; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📁 <span>{{ group.name }}</span></h1>
            <a href="{{ url_for('groups') }}" class="btn-back">📁 All Groups</a>
        </div>
        
        <div class="group-meta">
            <div class="info">
                <div>📸 <strong>{{ group.image_count }}</strong> images</div>
                <div>🕒 <strong>{{ group.created_at }}</strong></div>
                <div>🆔 <strong>{{ group.id }}</strong></div>
                <div>👁️ <strong>{{ group.views }}</strong> views</div>
            </div>
            <div class="url">🔗 {{ group.url }}</div>
            <div class="btn-group">
                <button class="btn btn-primary" onclick="copyToClipboard('{{ group.url }}')">📋 Copy Group Link</button>
                <button class="btn btn-success" onclick="downloadGroupQR()">⬇️ Download QR</button>
            </div>
            <div style="margin-top:15px;">
                <div class="qr-container">
                    <p style="color:#333;margin-bottom:10px;">🧾 Group QR Code</p>
                    <img id="groupQrImg" alt="QR Code">
                </div>
            </div>
        </div>
        
        <div class="gallery-grid">
            {% for img in group.images %}
            <div class="gallery-item" onclick="location.href='{{ url_for('single_image', filename=img.filename) }}?group={{ group.id }}'">
                <img src="{{ img.url }}" alt="{{ img.original_name }}" loading="lazy">
                <div class="name">📸 {{ img.original_name }}</div>
                <div class="overlay">🔗 View</div>
            </div>
            {% endfor %}
        </div>
        
        <div style="margin-top:30px;text-align:center;color:rgba(255,255,255,0.2);font-size:0.8em;">
            🔨 Created by TORIKUL | 🖼️ Click any image to view in full | ✅ Stored in Cloudinary
        </div>
    </div>
    
    <div class="toast-container" id="toastContainer"></div>
    
    <script>
        function copyToClipboard(text) {
            navigator.clipboard.writeText(text).then(() => {
                showToast('✅ Link copied!', 'success');
            }).catch(() => {
                prompt('Copy this link:', text);
            });
        }
        
        function downloadGroupQR() {
            const img = document.getElementById('groupQrImg');
            if (img.src) {
                const link = document.createElement('a');
                link.download = 'group_qr_{{ group.id }}.png';
                link.href = img.src;
                link.click();
                showToast('✅ QR Code downloaded!', 'success');
            }
        }
        
        function showToast(message, type = 'success') {
            const container = document.getElementById('toastContainer');
            const toast = document.createElement('div');
            toast.className = `toast ${type}`;
            toast.textContent = message;
            container.appendChild(toast);
            setTimeout(() => { toast.remove(); }, 3000);
        }
        
        // Load QR code
        fetch('/api/qr-group/{{ group.id }}')
            .then(res => res.json())
            .then(data => {
                document.getElementById('groupQrImg').src = 'data:image/png;base64,' + data.qr;
            });
    </script>
</body>
</html>
'''

# ============ SINGLE IMAGE VIEW TEMPLATE ============

SINGLE_IMAGE_TEMPLATE = '''
<!DOCTYPE html>
<html lang="bn">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ image.original_name }} - TORIKUL IMAGE • LINK • QR SYSTEM</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #0a0a1a;
            min-height: 100vh;
            color: #fff;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }
        .container { 
            max-width: 1100px; 
            width: 100%;
            margin: 0 auto; 
        }
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 25px;
            flex-wrap: wrap;
            gap: 15px;
        }
        .header h1 { 
            font-size: 1.5em; 
            word-break: break-all;
        }
        .header h1 span { 
            background: linear-gradient(135deg, #667eea, #764ba2); 
            -webkit-background-clip: text; 
            -webkit-text-fill-color: transparent; 
        }
        .btn-back {
            padding: 10px 20px;
            background: rgba(255,255,255,0.06);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 10px;
            color: #fff;
            text-decoration: none;
            transition: all 0.3s;
            display: inline-flex;
            align-items: center;
            gap: 8px;
        }
        .btn-back:hover { background: rgba(255,255,255,0.12); }
        
        .image-container {
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid rgba(255, 255, 255, 0.06);
            border-radius: 20px;
            overflow: hidden;
            padding: 20px;
        }
        .image-wrapper {
            position: relative;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 400px;
            background: rgba(0,0,0,0.3);
            border-radius: 12px;
            overflow: hidden;
        }
        .image-wrapper img {
            max-width: 100%;
            max-height: 70vh;
            object-fit: contain;
            border-radius: 8px;
        }
        
        .image-info {
            margin-top: 20px;
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
            background: rgba(255,255,255,0.03);
            border-radius: 12px;
            padding: 20px;
        }
        .image-info .info-item {
            display: flex;
            flex-direction: column;
            gap: 5px;
        }
        .image-info .info-item .label {
            color: rgba(255,255,255,0.4);
            font-size: 0.8em;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        .image-info .info-item .value {
            color: #fff;
            word-break: break-all;
            font-size: 0.95em;
        }
        .image-info .info-item .value.url {
            color: #667eea;
            cursor: pointer;
        }
        .image-info .info-item .value.url:hover {
            text-decoration: underline;
        }
        
        .btn-group {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            margin-top: 20px;
            justify-content: center;
        }
        .btn {
            padding: 12px 25px;
            border: none;
            border-radius: 10px;
            font-size: 0.95em;
            cursor: pointer;
            transition: all 0.3s;
            color: #fff;
            font-weight: 500;
            display: inline-flex;
            align-items: center;
            gap: 8px;
            text-decoration: none;
        }
        .btn-primary { background: linear-gradient(135deg, #667eea, #764ba2); }
        .btn-primary:hover { transform: scale(1.05); box-shadow: 0 10px 30px rgba(102, 126, 234, 0.3); }
        .btn-success { background: linear-gradient(135deg, #51cf66, #40c057); }
        .btn-success:hover { transform: scale(1.05); }
        .btn-danger { background: linear-gradient(135deg, #ff6b6b, #e03131); }
        .btn-danger:hover { transform: scale(1.05); }
        .btn-secondary { background: rgba(255,255,255,0.1); }
        .btn-secondary:hover { background: rgba(255,255,255,0.2); }
        .btn-warning { background: linear-gradient(135deg, #f093fb, #f5576c); }
        .btn-warning:hover { transform: scale(1.05); }
        
        .qr-section {
            margin-top: 25px;
            text-align: center;
            padding: 20px;
            background: rgba(255,255,255,0.03);
            border-radius: 12px;
            border: 1px solid rgba(255,255,255,0.05);
        }
        .qr-section .qr-container {
            display: inline-block;
            padding: 15px;
            background: #fff;
            border-radius: 12px;
        }
        .qr-section .qr-container img {
            max-width: 200px;
        }
        .qr-section .qr-label {
            color: rgba(255,255,255,0.4);
            font-size: 0.85em;
            margin-bottom: 10px;
        }
        
        .toast-container {
            position: fixed;
            bottom: 30px;
            right: 30px;
            z-index: 999;
            display: flex;
            flex-direction: column;
            gap: 10px;
        }
        .toast {
            padding: 14px 24px;
            border-radius: 12px;
            background: rgba(20, 20, 40, 0.95);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.1);
            color: #fff;
            font-size: 0.95em;
            animation: slideIn 0.3s ease-out;
        }
        .toast.success { border-left: 4px solid #51cf66; }
        .toast.error { border-left: 4px solid #ff6b6b; }
        @keyframes slideIn {
            from { transform: translateX(100px); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }
        
        @media (max-width: 768px) {
            .container { padding: 0; }
            .header h1 { font-size: 1.2em; }
            .image-info { grid-template-columns: 1fr; }
            .image-wrapper { min-height: 250px; }
            .image-wrapper img { max-height: 50vh; }
            .btn-group .btn { padding: 10px 16px; font-size: 0.85em; }
            .btn-back { padding: 8px 14px; font-size: 0.85em; }
        }
        @media (max-width: 480px) {
            .image-wrapper { min-height: 200px; }
            .image-wrapper img { max-height: 40vh; }
            .btn-group { flex-direction: column; align-items: stretch; }
            .btn-group .btn { justify-content: center; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🖼️ <span>{{ image.original_name }}</span></h1>
            <a href="{{ back_url }}" class="btn-back">⬅️ Back to Gallery</a>
        </div>
        
        <div class="image-container">
            <div class="image-wrapper">
                <img src="{{ image.url }}" alt="{{ image.original_name }}" id="mainImage">
            </div>
            
            <div class="image-info">
                <div class="info-item">
                    <span class="label">📄 Filename</span>
                    <span class="value">{{ image.original_name }}</span>
                </div>
                <div class="info-item">
                    <span class="label">📦 Size</span>
                    <span class="value">{{ image.size }}</span>
                </div>
                <div class="info-item">
                    <span class="label">🕒 Uploaded</span>
                    <span class="value">{{ image.upload_date }}</span>
                </div>
                <div class="info-item">
                    <span class="label">🆔 Image ID</span>
                    <span class="value" style="font-size:0.85em;color:rgba(255,255,255,0.5);">{{ image.filename }}</span>
                </div>
                <div class="info-item" style="grid-column: 1 / -1;">
                    <span class="label">🔗 Image URL</span>
                    <span class="value url" onclick="copyToClipboard('{{ image.url }}')">{{ image.url }}</span>
                </div>
            </div>
            
            <div class="btn-group">
                <button class="btn btn-primary" onclick="copyToClipboard('{{ image.url }}')">📋 Copy Link</button>
                <button class="btn btn-success" onclick="downloadImage()">⬇️ Download Image</button>
                <button class="btn btn-warning" onclick="toggleQR()">🧾 View QR</button>
                <a href="{{ back_url }}" class="btn btn-secondary">⬅️ Back to Gallery</a>
                {% if session.get('logged_in') %}
                <button class="btn btn-danger" onclick="deleteImage()">🗑️ Delete Image</button>
                {% endif %}
            </div>
            
            <div class="qr-section" id="qrSection" style="display: none;">
                <div class="qr-label">🧾 QR Code for this Image</div>
                <div class="qr-container">
                    <img id="qrImg" alt="QR Code">
                </div>
                <div style="margin-top:10px;">
                    <button class="btn btn-success" onclick="downloadQR()" style="padding:8px 20px;font-size:0.85em;">⬇️ Download QR</button>
                </div>
            </div>
        </div>
        
        <div style="margin-top:25px;text-align:center;color:rgba(255,255,255,0.15);font-size:0.75em;">
            🔨 Created by TORIKUL | 🖼️ TORIKUL IMAGE • LINK • QR SYSTEM | ✅ Stored in Cloudinary
        </div>
    </div>
    
    <div class="toast-container" id="toastContainer"></div>
    
    <!-- Confirmation Modal for Delete -->
    <div class="modal" id="confirmModal" style="display:none;position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.7);backdrop-filter:blur(5px);z-index:1000;justify-content:center;align-items:center;">
        <div class="modal-content" style="background:#1a1a2e;padding:30px;border-radius:20px;max-width:400px;width:90%;text-align:center;">
            <h3 style="margin-bottom:15px;">⚠️ Are You Sure?</h3>
            <p style="color:rgba(255,255,255,0.7);margin-bottom:20px;">Do you really want to delete this image from Cloudinary?</p>
            <div style="display:flex;gap:10px;justify-content:center;">
                <button class="btn btn-secondary" onclick="closeModal()">Cancel</button>
                <button class="btn btn-danger" id="confirmDeleteBtn">Delete</button>
            </div>
        </div>
    </div>
    
    <script>
        let qrLoaded = false;
        let imageFilename = '{{ image.filename }}';
        let groupId = '{{ group_id }}';
        
        function copyToClipboard(text) {
            navigator.clipboard.writeText(text).then(() => {
                showToast('✅ Link copied!', 'success');
            }).catch(() => {
                prompt('Copy this link:', text);
            });
        }
        
        function downloadImage() {
            const img = document.getElementById('mainImage');
            const link = document.createElement('a');
            link.download = '{{ image.original_name }}';
            link.href = img.src;
            link.click();
            showToast('✅ Image downloaded!', 'success');
        }
        
        function toggleQR() {
            const section = document.getElementById('qrSection');
            if (section.style.display === 'none') {
                section.style.display = 'block';
                if (!qrLoaded) {
                    fetch('/api/qr/{{ image.filename }}')
                        .then(res => res.json())
                        .then(data => {
                            document.getElementById('qrImg').src = 'data:image/png;base64,' + data.qr;
                            qrLoaded = true;
                        });
                }
            } else {
                section.style.display = 'none';
            }
        }
        
        function downloadQR() {
            const img = document.getElementById('qrImg');
            if (img.src) {
                const link = document.createElement('a');
                link.download = 'qr_{{ image.filename }}.png';
                link.href = img.src;
                link.click();
                showToast('✅ QR Code downloaded!', 'success');
            }
        }
        
        function deleteImage() {
            document.getElementById('confirmModal').style.display = 'flex';
            document.getElementById('confirmDeleteBtn').onclick = function() {
                closeModal();
                fetch('/api/delete/{{ image.filename }}', { method: 'DELETE' })
                    .then(res => res.json())
                    .then(data => {
                        if (data.success) {
                            showToast('✅ Image deleted from Cloudinary!', 'success');
                            setTimeout(() => {
                                window.location.href = '{{ back_url }}';
                            }, 1500);
                        } else {
                            showToast('❌ Delete failed!', 'error');
                        }
                    });
            };
        }
        
        function closeModal() {
            document.getElementById('confirmModal').style.display = 'none';
        }
        
        function showToast(message, type = 'success') {
            const container = document.getElementById('toastContainer');
            const toast = document.createElement('div');
            toast.className = `toast ${type}`;
            toast.textContent = message;
            container.appendChild(toast);
            setTimeout(() => { toast.remove(); }, 3000);
        }
        
        // Keyboard shortcuts
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') {
                const modal = document.getElementById('confirmModal');
                if (modal.style.display === 'flex') {
                    closeModal();
                }
                const qrSection = document.getElementById('qrSection');
                if (qrSection.style.display === 'block') {
                    qrSection.style.display = 'none';
                }
            }
        });
    </script>
</body>
</html>
'''

# ============ LINK GROUP VIEW TEMPLATE ============

LINK_GROUP_VIEW_TEMPLATE = '''
<!DOCTYPE html>
<html lang="bn">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ group.name }} - TORIKUL IMAGE • LINK • QR SYSTEM</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #0a0a1a;
            min-height: 100vh;
            color: #fff;
        }
        .container { max-width: 1100px; margin: 0 auto; padding: 20px; }
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 30px;
            flex-wrap: wrap;
            gap: 15px;
        }
        .header h1 { font-size: 1.8em; }
        .header h1 span { background: linear-gradient(135deg, #667eea, #764ba2); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .btn-back {
            padding: 10px 20px;
            background: rgba(255,255,255,0.06);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 10px;
            color: #fff;
            text-decoration: none;
            transition: all 0.3s;
        }
        .btn-back:hover { background: rgba(255,255,255,0.12); }
        .group-meta {
            background: rgba(255, 255, 255, 0.04);
            border: 1px solid rgba(255, 255, 255, 0.06);
            border-radius: 16px;
            padding: 20px 25px;
            margin-bottom: 30px;
        }
        .group-meta .info { display: flex; flex-wrap: wrap; gap: 20px; }
        .group-meta .info div { color: rgba(255,255,255,0.6); }
        .group-meta .info div strong { color: #fff; }
        .group-meta .url { color: #667eea; word-break: break-all; margin-top: 10px; }
        .links-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
            gap: 20px;
        }
        .link-card {
            background: rgba(255, 255, 255, 0.04);
            border: 1px solid rgba(255, 255, 255, 0.06);
            border-radius: 12px;
            padding: 15px;
        }
        .link-card .link-url { color: #667eea; word-break: break-all; font-size: 0.85em; }
        .link-card .qr-small { text-align: center; padding: 10px; background: #fff; border-radius: 8px; margin-top: 10px; }
        .link-card .qr-small img { max-width: 120px; }
        .btn {
            padding: 8px 18px;
            border: none;
            border-radius: 8px;
            font-size: 0.9em;
            cursor: pointer;
            transition: all 0.3s;
            color: #fff;
            text-decoration: none;
            display: inline-block;
        }
        .btn-primary { background: linear-gradient(135deg, #667eea, #764ba2); }
        .btn-primary:hover { transform: scale(1.05); }
        .btn-success { background: linear-gradient(135deg, #51cf66, #40c057); }
        .btn-success:hover { transform: scale(1.05); }
        .btn-secondary { background: rgba(255,255,255,0.1); }
        .btn-secondary:hover { background: rgba(255,255,255,0.2); }
        .btn-group { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 15px; }
        .qr-container { text-align: center; padding: 15px; background: #fff; border-radius: 12px; display: inline-block; }
        .qr-container img { max-width: 180px; }
        .toast-container {
            position: fixed;
            bottom: 30px;
            right: 30px;
            z-index: 999;
            display: flex;
            flex-direction: column;
            gap: 10px;
        }
        .toast {
            padding: 14px 24px;
            border-radius: 12px;
            background: rgba(20, 20, 40, 0.95);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.1);
            color: #fff;
            font-size: 0.95em;
            animation: slideIn 0.3s ease-out;
        }
        .toast.success { border-left: 4px solid #51cf66; }
        .toast.error { border-left: 4px solid #ff6b6b; }
        @keyframes slideIn {
            from { transform: translateX(100px); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }
        @media (max-width: 600px) {
            .container { padding: 15px; }
            .header h1 { font-size: 1.3em; }
            .links-grid { grid-template-columns: 1fr; }
            .group-meta .info { flex-direction: column; gap: 10px; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📁🔗 <span>{{ group.name }}</span></h1>
            <a href="{{ url_for('link_groups') }}" class="btn-back">📁 All Link Groups</a>
        </div>
        
        <div class="group-meta">
            <div class="info">
                <div>🔗 <strong>{{ group.link_count }}</strong> links</div>
                <div>🕒 <strong>{{ group.created_at }}</strong></div>
                <div>🆔 <strong>{{ group.id }}</strong></div>
                <div>👁️ <strong>{{ group.views }}</strong> views</div>
            </div>
            <div class="url">🔗 {{ group.url }}</div>
            <div class="btn-group">
                <button class="btn btn-primary" onclick="copyToClipboard('{{ group.url }}')">📋 Copy Link</button>
                <button class="btn btn-success" onclick="downloadGroupQR()">⬇️ Download QR</button>
            </div>
            <div style="margin-top:15px;">
                <div class="qr-container">
                    <p style="color:#333;margin-bottom:10px;">🧾 Group QR Code</p>
                    <img id="groupQrImg" alt="QR Code">
                </div>
            </div>
        </div>
        
        <div class="links-grid">
            {% for link in group.links %}
            <div class="link-card" data-linkid="{{ link.link_id }}">
                <div class="link-url">🔗 {{ link.url }}</div>
                <div class="qr-small">
                    <img src="data:image/png;base64,{{ link.qr }}" alt="QR Code">
                </div>
                <div style="display:flex;gap:8px;margin-top:10px;flex-wrap:wrap;">
                    <button class="btn btn-primary" style="padding:4px 12px;font-size:0.8em;" onclick="copyToClipboard('{{ link.url }}')">📋 Copy</button>
                    <button class="btn btn-success" style="padding:4px 12px;font-size:0.8em;" onclick="downloadLinkQR('{{ link.link_id }}')">⬇️ QR</button>
                    <button class="btn btn-danger" style="padding:4px 12px;font-size:0.8em;" onclick="deleteLink('{{ link.link_id }}')">🗑️ Delete</button>
                </div>
            </div>
            {% endfor %}
        </div>
        
        <div style="margin-top:30px;text-align:center;color:rgba(255,255,255,0.2);font-size:0.8em;">
            🔨 Created by TORIKUL | ✅ Stored in Supabase
        </div>
    </div>
    
    <div class="toast-container" id="toastContainer"></div>
    
    <script>
        let groupId = '{{ group.id }}';
        
        function copyToClipboard(text) {
            navigator.clipboard.writeText(text).then(() => {
                showToast('✅ Link copied!', 'success');
            }).catch(() => {
                prompt('Copy this link:', text);
            });
        }
        
        function downloadGroupQR() {
            const img = document.getElementById('groupQrImg');
            if (img.src) {
                const link = document.createElement('a');
                link.download = 'group_qr_{{ group.id }}.png';
                link.href = img.src;
                link.click();
                showToast('✅ QR Code downloaded!', 'success');
            }
        }
        
        function downloadLinkQR(linkId) {
            fetch('/api/qr-link/' + linkId)
                .then(res => res.json())
                .then(data => {
                    const link = document.createElement('a');
                    link.download = 'qr_' + linkId + '.png';
                    link.href = 'data:image/png;base64,' + data.qr;
                    link.click();
                    showToast('✅ QR Code downloaded!', 'success');
                });
        }
        
        function deleteLink(linkId) {
            if (!confirm('Are you sure you want to delete this link?')) return;
            fetch('/api/delete-link/' + linkId, { method: 'DELETE' })
                .then(res => res.json())
                .then(data => {
                    if (data.success) {
                        showToast('✅ Link deleted from Supabase!', 'success');
                        const card = document.querySelector(`.link-card[data-linkid="${linkId}"]`);
                        if (card) card.remove();
                    } else {
                        showToast('❌ Delete failed!', 'error');
                    }
                });
        }
        
        function showToast(message, type = 'success') {
            const container = document.getElementById('toastContainer');
            const toast = document.createElement('div');
            toast.className = `toast ${type}`;
            toast.textContent = message;
            container.appendChild(toast);
            setTimeout(() => { toast.remove(); }, 3000);
        }
        
        // Load group QR
        fetch('/api/qr-link-group/{{ group.id }}')
            .then(res => res.json())
            .then(data => {
                document.getElementById('groupQrImg').src = 'data:image/png;base64,' + data.qr;
            });
    </script>
</body>
</html>
'''

# ============ ROUTES ============

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['logged_in'] = True
            session['username'] = username
            return redirect(url_for('dashboard'))
        elif username != ADMIN_USERNAME:
            return render_template_string(LOGIN_TEMPLATE, error='❌ Invalid Username! Please try again.', username=username)
        else:
            return render_template_string(LOGIN_TEMPLATE, error='❌ Invalid Password! Please try again.', username=username)
    
    if session.get('logged_in'):
        return redirect(url_for('dashboard'))
    return render_template_string(LOGIN_TEMPLATE, error=None)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
def home():
    if session.get('logged_in'):
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    images = get_images_from_db()
    groups = get_groups_from_db()
    links = get_links_from_db()
    link_groups = get_link_groups_from_db()
    
    # Count only non-group images
    single_images = {k: v for k, v in images.items() if 'group_id' not in v or v['group_id'] is None}
    
    return render_template_string(DASHBOARD_TEMPLATE,
        total_images=len(single_images),
        total_links=len(links),
        total_groups=len(groups),
        total_link_groups=len(link_groups),
        now=datetime.now()
    )

@app.route('/upload')
@login_required
def upload():
    return render_template_string(UPLOAD_TEMPLATE)

@app.route('/multiple-upload')
@login_required
def multiple_upload():
    return render_template_string(MULTIPLE_UPLOAD_TEMPLATE)

@app.route('/link-to-qr')
@login_required
def link_qr():
    return render_template_string(LINK_QR_TEMPLATE)

@app.route('/multiple-links-to-qr')
@login_required
def multiple_link_qr():
    return render_template_string(MULTIPLE_LINK_QR_TEMPLATE)

@app.route('/gallery')
@login_required
def gallery():
    images_data = get_images_from_db()
    images = []
    for filename, data in images_data.items():
        if 'group_id' not in data or data['group_id'] is None:
            images.append({
                'filename': filename,
                'url': data['url'],
                'original_name': data.get('filename', filename),
                'size': data.get('size', 'Unknown'),
                'upload_date': data.get('upload_date', 'Unknown')[:10] if data.get('upload_date') else 'Unknown'
            })
    return render_template_string(GALLERY_TEMPLATE, images=images)

@app.route('/groups')
@login_required
def groups():
    groups_data = get_groups_from_db()
    return render_template_string(GROUPS_TEMPLATE, groups=groups_data)

@app.route('/link-groups')
@login_required
def link_groups():
    link_groups_data = get_link_groups_from_db()
    return render_template_string(LINK_GROUPS_TEMPLATE, groups=link_groups_data)

# ============ GROUP VIEW ROUTE (GALLERY) ============

@app.route('/group/<group_id>')
def view_group(group_id):
    groups_data = get_groups_from_db()
    if group_id not in groups_data:
        return "Group not found", 404
    
    # Increment view count
    increment_group_views(group_id)
    
    # Reload group data with updated views
    groups_data = get_groups_from_db()
    group = groups_data[group_id]
    
    return render_template_string(GROUP_VIEW_TEMPLATE, group=group)

# ============ SINGLE IMAGE VIEW ROUTE ============

@app.route('/image/<filename>')
def single_image(filename):
    images_data = get_images_from_db()
    
    if filename not in images_data:
        return "Image not found", 404
    
    image_data = images_data[filename]
    
    # Get back URL - if coming from group, go back to group
    group_id = request.args.get('group')
    back_url = url_for('view_group', group_id=group_id) if group_id and group_id in get_groups_from_db() else url_for('gallery')
    
    return render_template_string(SINGLE_IMAGE_TEMPLATE,
        image=image_data,
        back_url=back_url,
        group_id=group_id
    )

@app.route('/link-group/<group_id>')
def view_link_group(group_id):
    link_groups_data = get_link_groups_from_db()
    if group_id not in link_groups_data:
        return "Link Group not found", 404
    
    # Increment view count
    increment_link_group_views(group_id)
    
    # Reload group data with updated views
    link_groups_data = get_link_groups_from_db()
    group = link_groups_data[group_id]
    
    return render_template_string(LINK_GROUP_VIEW_TEMPLATE, group=group)

# ============ API ROUTES ============

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
            unique_id = generate_unique_id()
            unique_name = f"{unique_id}.{ext}"
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_name)
            file.save(file_path)
            
            # Upload to Cloudinary
            cloudinary_url = upload_to_cloudinary(file_path, unique_name)
            
            if cloudinary_url:
                file_size = get_file_size(file_path)
                
                # Save to database
                save_image_to_db(
                    filename=unique_name,
                    original_name=file.filename,
                    url=cloudinary_url,
                    size=file_size,
                    file_type=ext.upper(),
                    group_id=None
                )
                
                uploaded_files.append({
                    'original_name': file.filename,
                    'url': cloudinary_url,
                    'size': file_size,
                    'type': ext.upper(),
                    'filename': unique_name
                })
                
                # Clean up local file
                if os.path.exists(file_path):
                    os.remove(file_path)
    
    return jsonify({'success': True, 'files': uploaded_files})

@app.route('/api/multiple-upload', methods=['POST'])
@login_required
def api_multiple_upload():
    if 'photos' not in request.files:
        return jsonify({'error': 'No files uploaded'}), 400
    
    files = request.files.getlist('photos')
    if not files or files[0].filename == '':
        return jsonify({'error': 'No files selected'}), 400
    
    group_id = generate_unique_id()
    group_name = f"Image_Group_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    uploaded_files = []
    
    for file in files:
        if file and file.filename != '' and allowed_file(file.filename):
            ext = file.filename.rsplit('.', 1)[1].lower()
            unique_id = generate_unique_id()
            unique_name = f"{unique_id}.{ext}"
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_name)
            file.save(file_path)
            
            # Upload to Cloudinary
            cloudinary_url = upload_to_cloudinary(file_path, unique_name)
            
            if cloudinary_url:
                file_size = get_file_size(file_path)
                
                # Save to database with group_id
                save_image_to_db(
                    filename=unique_name,
                    original_name=file.filename,
                    url=cloudinary_url,
                    size=file_size,
                    file_type=ext.upper(),
                    group_id=group_id
                )
                
                uploaded_files.append({
                    'original_name': file.filename,
                    'url': cloudinary_url,
                    'size': file_size,
                    'type': ext.upper(),
                    'filename': unique_name
                })
                
                # Clean up local file
                if os.path.exists(file_path):
                    os.remove(file_path)
    
    if uploaded_files:
        group_url = request.host_url + 'group/' + group_id
        save_group_to_db(
            group_id=group_id,
            name=group_name,
            url=group_url,
            image_count=len(uploaded_files),
            images=uploaded_files
        )
        
        return jsonify({
            'success': True,
            'group_id': group_id,
            'group_url': group_url,
            'group_name': group_name,
            'files': uploaded_files,
            'count': len(uploaded_files)
        })
    
    return jsonify({'success': False, 'error': 'No files uploaded successfully'}), 400

@app.route('/api/add-to-image-group', methods=['POST'])
@login_required
def api_add_to_image_group():
    group_id = request.form.get('group_id')
    if not group_id:
        return jsonify({'error': 'Group ID required'}), 400
    
    if 'photos' not in request.files:
        return jsonify({'error': 'No files uploaded'}), 400
    
    files = request.files.getlist('photos')
    added = 0
    
    for file in files:
        if file and file.filename != '' and allowed_file(file.filename):
            ext = file.filename.rsplit('.', 1)[1].lower()
            unique_id = generate_unique_id()
            unique_name = f"{unique_id}.{ext}"
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_name)
            file.save(file_path)
            
            # Upload to Cloudinary
            cloudinary_url = upload_to_cloudinary(file_path, unique_name)
            
            if cloudinary_url:
                file_size = get_file_size(file_path)
                
                # Save to database with group_id
                save_image_to_db(
                    filename=unique_name,
                    original_name=file.filename,
                    url=cloudinary_url,
                    size=file_size,
                    file_type=ext.upper(),
                    group_id=group_id
                )
                
                image_data = {
                    'original_name': file.filename,
                    'url': cloudinary_url,
                    'size': file_size,
                    'type': ext.upper(),
                    'filename': unique_name
                }
                
                # Add to group
                if add_image_to_group_db(group_id, image_data):
                    added += 1
                
                # Clean up local file
                if os.path.exists(file_path):
                    os.remove(file_path)
    
    return jsonify({'success': True, 'count': added})

@app.route('/api/link-to-qr', methods=['POST'])
@login_required
def api_link_to_qr():
    data = request.get_json()
    url = data.get('url', '').strip()
    
    if not url:
        return jsonify({'success': False, 'error': 'URL is required'}), 400
    
    if not validate_url(url):
        return jsonify({'success': False, 'error': 'Invalid URL format'}), 400
    
    link_id = generate_unique_id()
    qr_base64 = generate_qr_code_base64(url)
    
    # Save to database
    save_link_to_db(link_id=link_id, url=url, qr=qr_base64)
    
    return jsonify({
        'success': True,
        'link_id': link_id,
        'url': url,
        'qr': qr_base64
    })

@app.route('/api/multiple-links-to-qr', methods=['POST'])
@login_required
def api_multiple_links_to_qr():
    data = request.get_json()
    links = data.get('links', [])
    
    if not links:
        return jsonify({'success': False, 'error': 'No links provided'}), 400
    
    valid_links = []
    for url in links:
        url = url.strip()
        if url and validate_url(url):
            valid_links.append(url)
    
    if not valid_links:
        return jsonify({'success': False, 'error': 'No valid URLs found'}), 400
    
    group_id = generate_unique_id()
    group_name = f"Link_Group_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    processed_links = []
    for url in valid_links:
        link_id = generate_unique_id()
        qr_base64 = generate_qr_code_base64(url)
        
        # Save to database with group_id
        save_link_to_db(
            link_id=link_id,
            url=url,
            qr=qr_base64,
            group_id=group_id
        )
        
        processed_links.append({
            'link_id': link_id,
            'url': url,
            'qr': qr_base64
        })
    
    if processed_links:
        group_url = request.host_url + 'link-group/' + group_id
        save_link_group_to_db(
            group_id=group_id,
            name=group_name,
            url=group_url,
            link_count=len(processed_links),
            links=processed_links
        )
        
        return jsonify({
            'success': True,
            'group_id': group_id,
            'group_url': group_url,
            'group_name': group_name,
            'links': processed_links,
            'count': len(processed_links)
        })
    
    return jsonify({'success': False, 'error': 'No links processed successfully'}), 400

@app.route('/api/add-to-link-group', methods=['POST'])
@login_required
def api_add_to_link_group():
    data = request.get_json()
    group_id = data.get('group_id')
    url = data.get('url', '').strip()
    
    if not group_id:
        return jsonify({'error': 'Group ID required'}), 400
    
    if not url:
        return jsonify({'error': 'URL is required'}), 400
    
    if not validate_url(url):
        return jsonify({'error': 'Invalid URL format'}), 400
    
    link_id = generate_unique_id()
    qr_base64 = generate_qr_code_base64(url)
    
    # Save to database with group_id
    save_link_to_db(
        link_id=link_id,
        url=url,
        qr=qr_base64,
        group_id=group_id
    )
    
    link_data = {
        'link_id': link_id,
        'url': url,
        'qr': qr_base64
    }
    
    # Add to group
    if add_link_to_group_db(group_id, link_data):
        return jsonify({'success': True, 'link_id': link_id, 'url': url})
    
    return jsonify({'success': False, 'error': 'Failed to add link to group'}), 400

@app.route('/api/validate-url', methods=['POST'])
@login_required
def api_validate_url():
    data = request.get_json()
    url = data.get('url', '').strip()
    
    if not url:
        return jsonify({'valid': False})
    
    is_valid = validate_url(url)
    return jsonify({'valid': is_valid})

@app.route('/api/qr/<filename>')
def generate_qr(filename):
    images_data = get_images_from_db()
    if filename not in images_data:
        return jsonify({'error': 'Image not found'}), 404
    
    url = images_data[filename]['url']
    qr_base64 = generate_qr_code_base64(url)
    return jsonify({'qr': qr_base64})

@app.route('/api/qr-group/<group_id>')
def generate_group_qr(group_id):
    groups_data = get_groups_from_db()
    if group_id not in groups_data:
        return jsonify({'error': 'Group not found'}), 404
    
    url = groups_data[group_id]['url']
    qr_base64 = generate_qr_code_base64(url)
    return jsonify({'qr': qr_base64})

@app.route('/api/qr-link/<link_id>')
@login_required
def generate_link_qr(link_id):
    links_data = get_links_from_db()
    if link_id not in links_data:
        return jsonify({'error': 'Link not found'}), 404
    
    return jsonify({'qr': links_data[link_id]['qr']})

@app.route('/api/qr-link-group/<group_id>')
def generate_link_group_qr(group_id):
    link_groups_data = get_link_groups_from_db()
    if group_id not in link_groups_data:
        return jsonify({'error': 'Link Group not found'}), 404
    
    url = link_groups_data[group_id]['url']
    qr_base64 = generate_qr_code_base64(url)
    return jsonify({'qr': qr_base64})

@app.route('/api/delete/<filename>', methods=['DELETE'])
@login_required
def delete_image(filename):
    images_data = get_images_from_db()
    
    if filename in images_data:
        group_id = images_data[filename].get('group_id')
        
        # Delete from Cloudinary
        try:
            public_id = filename.replace('.', '_')
            cloudinary.uploader.destroy(f"torikul_images/{public_id}")
        except Exception as e:
            print(f"Cloudinary delete error: {e}")
        
        # Delete from database
        delete_image_from_db(filename)
        
        # Remove from group if exists
        if group_id:
            groups_data = get_groups_from_db()
            if group_id in groups_data:
                groups_data[group_id]['images'] = [img for img in groups_data[group_id]['images'] if img['filename'] != filename]
                groups_data[group_id]['image_count'] = len(groups_data[group_id]['images'])
                # Update group in database
                try:
                    supabase.table('groups').update({
                        'images': json.dumps(groups_data[group_id]['images']),
                        'image_count': groups_data[group_id]['image_count']
                    }).eq('id', group_id).execute()
                except Exception as e:
                    print(f"Group update error: {e}")
        
        return jsonify({'success': True, 'message': 'Image deleted successfully from Cloudinary'})
    
    return jsonify({'success': False, 'message': 'Image not found'}), 404

@app.route('/api/delete-link/<link_id>', methods=['DELETE'])
@login_required
def delete_link(link_id):
    links_data = get_links_from_db()
    
    if link_id in links_data:
        group_id = links_data[link_id].get('group_id')
        
        # Delete from database
        delete_link_from_db(link_id)
        
        # Remove from group if exists
        if group_id:
            link_groups_data = get_link_groups_from_db()
            if group_id in link_groups_data:
                link_groups_data[group_id]['links'] = [l for l in link_groups_data[group_id]['links'] if l['link_id'] != link_id]
                link_groups_data[group_id]['link_count'] = len(link_groups_data[group_id]['links'])
                # Update group in database
                try:
                    supabase.table('link_groups').update({
                        'links': json.dumps(link_groups_data[group_id]['links']),
                        'link_count': link_groups_data[group_id]['link_count']
                    }).eq('id', group_id).execute()
                except Exception as e:
                    print(f"Link group update error: {e}")
        
        return jsonify({'success': True, 'message': 'Link deleted successfully'})
    
    return jsonify({'success': False, 'message': 'Link not found'}), 404

@app.route('/api/delete-group/<group_id>', methods=['DELETE'])
@login_required
def delete_group(group_id):
    groups_data = get_groups_from_db()
    
    if group_id not in groups_data:
        return jsonify({'success': False, 'message': 'Group not found'}), 404
    
    # Delete all images in the group from Cloudinary
    for img in groups_data[group_id].get('images', []):
        filename = img.get('filename')
        if filename:
            try:
                public_id = filename.replace('.', '_')
                cloudinary.uploader.destroy(f"torikul_images/{public_id}")
            except Exception as e:
                print(f"Cloudinary delete error: {e}")
    
    # Delete group from database (will also delete images)
    delete_group_from_db(group_id)
    
    return jsonify({'success': True, 'message': 'Group deleted successfully'})

@app.route('/api/delete-link-group/<group_id>', methods=['DELETE'])
@login_required
def delete_link_group(group_id):
    link_groups_data = get_link_groups_from_db()
    
    if group_id not in link_groups_data:
        return jsonify({'success': False, 'message': 'Link Group not found'}), 404
    
    # Delete link group from database (will also delete links)
    delete_link_group_from_db(group_id)
    
    return jsonify({'success': True, 'message': 'Link Group deleted successfully'})

# ============ MAIN ============

# This is what Vercel needs
app = app

if __name__ == '__main__':
    print("\n" + "="*60)
    print("🖼️ TORIKUL IMAGE • LINK • QR SYSTEM v5.0 (Database Powered)")
    print("="*60)
    print(f"📁 Upload folder: {os.path.abspath(UPLOAD_FOLDER)}")
    print(f"🌐 Server: http://127.0.0.1:5000")
    print(f"🔑 Login: {ADMIN_USERNAME} / {ADMIN_PASSWORD}")
    print("="*60)
    print("📌 Features:")
    print("  📸 Single Image → URL + QR (Stored in Cloudinary)")
    print("  📸📸 Multiple Images → Group + URL + QR (Stored in Cloudinary)")
    print("  🔗 Single Link → QR (Stored in Supabase)")
    print("  🔗🔗 Multiple Links → Link Group + QR (Stored in Supabase)")
    print("  📁 Unlimited Groups")
    print("  ➕ Add More to Existing Groups")
    print("  🆔 All URLs have 'torikul' in ID")
    print("  👁️ Group Gallery View")
    print("  🖼️ Single Image View with Actions")
    print("  ✅ Persistent Storage: Supabase + Cloudinary")
    print("="*60)
    print("⚠️ IMPORTANT: Set these environment variables:")
    print("  SUPABASE_URL, SUPABASE_KEY")
    print("  CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET")
    print("  ADMIN_USERNAME, ADMIN_PASSWORD, SECRET_KEY")
    print("="*60)
    print("Press CTRL+C to stop\n")
    app.run(debug=True, host='0.0.0.0', port=5000)