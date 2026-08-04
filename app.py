import os
import secrets
from datetime import datetime
from flask import Flask, render_template_string, request, jsonify, session, redirect, url_for
from functools import wraps
from io import BytesIO
import base64
import re
from sqlalchemy import create_engine, Column, String, DateTime, Text, LargeBinary, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
import qrcode

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))

# ============ DATABASE SETUP ============
DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:////tmp/data.db')
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

# ============ MODELS ============
class Image(Base):
    __tablename__ = 'images'
    id = Column(String(64), primary_key=True)
    filename = Column(String(255))
    data = Column(LargeBinary)
    size = Column(String(20))
    type = Column(String(10))
    upload_date = Column(DateTime, default=datetime.utcnow)
    group_id = Column(String(64), ForeignKey('groups.id'), nullable=True)

class Group(Base):
    __tablename__ = 'groups'
    id = Column(String(64), primary_key=True)
    name = Column(String(255))
    url = Column(String(500))
    created_at = Column(DateTime, default=datetime.utcnow)
    images = relationship('Image', backref='group', lazy='dynamic')

    @property
    def image_count(self):
        return self.images.count()

    @property
    def image_list(self):
        return [{'filename': img.id, 'url': request.host_url + 'image/' + img.id,
                 'original_name': img.filename, 'size': img.size} for img in self.images]

class Link(Base):
    __tablename__ = 'links'
    id = Column(String(64), primary_key=True)
    url = Column(String(500))
    qr = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    group_id = Column(String(64), ForeignKey('link_groups.id'), nullable=True)

class LinkGroup(Base):
    __tablename__ = 'link_groups'
    id = Column(String(64), primary_key=True)
    name = Column(String(255))
    url = Column(String(500))
    created_at = Column(DateTime, default=datetime.utcnow)
    links = relationship('Link', backref='link_group', lazy='dynamic')

    @property
    def link_count(self):
        return self.links.count()

    @property
    def link_list(self):
        return [{'link_id': l.id, 'url': l.url, 'qr': l.qr} for l in self.links]

Base.metadata.create_all(bind=engine)

# ============ HELPERS ============
def generate_unique_id():
    return secrets.token_hex(4) + 'torikul'

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp', 'svg', 'ico'}

def get_file_size(data):
    size_bytes = len(data)
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} GB"

def generate_qr_code_base64(url):
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode()

def validate_url(url):
    pattern = re.compile(
        r'^https?://'
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'
        r'localhost|'
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
        r'(?::\d+)?'
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    return re.match(pattern, url) is not None

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

# ============ TEMPLATES ============

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
                🔨 Created by TORIKUL | 🖼️ TORIKUL IMAGE • LINK • QR SYSTEM v5.0
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
            <div class="sub">or drag & drop here</div>
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
            🔨 Created by TORIKUL
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
                            showToast('✅ Image uploaded & QR generated!', 'success');
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
                            showToast('✅ Image deleted!', 'success');
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
            <div class="sub">or drag & drop here</div>
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
            🔨 Created by TORIKUL
        </div>
    </div>
    
    <div class="toast-container" id="toastContainer"></div>
    
    <div class="modal" id="confirmModal">
        <div class="modal-content">
            <h3>⚠️ Delete Entire Group?</h3>
            <p>This will delete all images inside this group.</p>
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
                            showToast('✅ Group deleted!', 'success');
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
            🔨 Created by TORIKUL
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
                    showToast('✅ QR Code generated!', 'success');
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
                            showToast('✅ Link deleted!', 'success');
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
            🔨 Created by TORIKUL
        </div>
    </div>
    
    <div class="toast-container" id="toastContainer"></div>
    
    <div class="modal" id="confirmModal">
        <div class="modal-content">
            <h3>⚠️ Delete Entire Group?</h3>
            <p>This will delete all links inside this group.</p>
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
                        showToast('✅ Link deleted!', 'success');
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
                            showToast('✅ Group deleted!', 'success');
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
            <div class="image-card" data-filename="{{ img.filename }}">
                <div class="img-wrap">
                    <img src="{{ img.url }}" alt="{{ img.filename }}">
                </div>
                <div class="info">
                    <div class="name">{{ img.original_name[:35] }}{% if img.original_name|length > 35 %}...{% endif %}</div>
                    <div class="meta">📦 {{ img.size }} | 🕒 {{ img.upload_date }}</div>
                    <div class="url" onclick="copyToClipboard('{{ img.url }}')">🔗 {{ img.url[:50] }}...</div>
                    <div class="btn-group">
                        <button class="btn btn-primary" onclick="copyToClipboard('{{ img.url }}')">📋 Copy</button>
                        <button class="btn btn-success" onclick="downloadQR('{{ img.filename }}')">🧾 QR</button>
                        <button class="btn btn-danger" onclick="deleteImage('{{ img.filename }}')">🗑️ Delete</button>
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
            🔨 Created by TORIKUL | Total: {{ images|length }} images
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
                            showToast('✅ Image deleted!', 'success');
                            const card = document.querySelector(`.image-card[data-filename="${deleteTarget}"]`);
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
        }
        .group-card .thumb-grid img { width: 100%; height: 100%; object-fit: cover; }
        .group-card .thumb-grid .more { display: flex; justify-content: center; align-items: center; background: rgba(102, 126, 234, 0.2); font-size: 1.2em; }
        .group-card .info { padding: 15px; }
        .group-card .info .name { font-weight: 600; font-size: 1.1em; }
        .group-card .info .meta { color: rgba(255,255,255,0.4); font-size: 0.85em; margin: 5px 0; }
        .group-card .info .url { color: #667eea; font-size: 0.75em; word-break: break-all; cursor: pointer; }
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
                <div class="thumb-grid">
                    {% for img in group.images[:3] %}
                    <img src="{{ img.url }}" alt="{{ img.original_name }}">
                    {% endfor %}
                    {% if group.images|length > 3 %}
                    <div class="more">+{{ group.images|length - 3 }}</div>
                    {% endif %}
                </div>
                <div class="info">
                    <div class="name">📁 {{ group.name }}</div>
                    <div class="meta">📸 {{ group.image_count }} images | 🕒 {{ group.created_at }}</div>
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
            🔨 Created by TORIKUL | Total: {{ groups|length }} groups
        </div>
    </div>
    
    <div class="toast-container" id="toastContainer"></div>
    
    <div class="modal" id="confirmModal">
        <div class="modal-content">
            <h3>⚠️ Delete Entire Group?</h3>
            <p>This will delete all images inside this group.</p>
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
                            showToast('✅ Group deleted!', 'success');
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
        .group-card .name { font-weight: 600; font-size: 1.1em; }
        .group-card .meta { color: rgba(255,255,255,0.4); font-size: 0.85em; margin: 5px 0; }
        .group-card .url { color: #667eea; font-size: 0.75em; word-break: break-all; cursor: pointer; }
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
            <div class="group-card" data-groupid="{{ gid }}">
                <div class="name">📁🔗 {{ group.name }}</div>
                <div class="meta">🔗 {{ group.link_count }} links | 🕒 {{ group.created_at }}</div>
                <div class="url" onclick="copyToClipboard('{{ group.url }}')">🔗 {{ group.url }}</div>
                <div class="links-preview">
                    {% for link in group.links[:5] %}
                    <div class="link-item">🔗 {{ link.url }}</div>
                    {% endfor %}
                    {% if group.links|length > 5 %}
                    <div class="link-item" style="color:rgba(255,255,255,0.3);">... and {{ group.links|length - 5 }} more</div>
                    {% endif %}
                </div>
                <div class="btn-group">
                    <button class="btn btn-primary" onclick="copyToClipboard('{{ group.url }}')">📋 Copy Link</button>
                    <button class="btn btn-success" onclick="downloadGroupQR('{{ gid }}')">🧾 QR</button>
                    <button class="btn btn-secondary" onclick="window.open('{{ group.url }}', '_blank')">👁️ View</button>
                    <button class="btn btn-danger" onclick="deleteGroup('{{ gid }}')">🗑️ Delete</button>
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
            🔨 Created by TORIKUL | Total: {{ groups|length }} groups
        </div>
    </div>
    
    <div class="toast-container" id="toastContainer"></div>
    
    <div class="modal" id="confirmModal">
        <div class="modal-content">
            <h3>⚠️ Delete Entire Group?</h3>
            <p>This will delete all links inside this group.</p>
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
                            showToast('✅ Group deleted!', 'success');
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
        }
        .gallery-item:hover { transform: translateY(-5px); background: rgba(255, 255, 255, 0.06); }
        .gallery-item img { width: 100%; height: 200px; object-fit: cover; }
        .gallery-item .name { padding: 10px; font-size: 0.85em; color: rgba(255,255,255,0.6); text-align: center; word-break: break-all; }
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
        .add-area {
            margin-top: 20px;
            padding: 20px;
            background: rgba(255,255,255,0.03);
            border-radius: 12px;
            border: 1px dashed rgba(102, 126, 234, 0.3);
        }
        .add-area input[type="file"] { display: none; }
        .add-area .upload-btn {
            padding: 10px 25px;
            background: rgba(102, 126, 234, 0.2);
            border: 1px solid rgba(102, 126, 234, 0.3);
            border-radius: 10px;
            color: #fff;
            cursor: pointer;
            transition: all 0.3s;
        }
        .add-area .upload-btn:hover { background: rgba(102, 126, 234, 0.3); }
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
            .gallery-grid { grid-template-columns: 1fr; }
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
        
        <div class="add-area">
            <p style="margin-bottom:10px;color:rgba(255,255,255,0.6);">➕ Add More Images to this Group</p>
            <div style="display:flex;gap:10px;flex-wrap:wrap;align-items:center;">
                <button class="upload-btn" onclick="document.getElementById('addFileInput').click()">📸 Select Images</button>
                <span id="addFileCount" style="color:rgba(255,255,255,0.4);font-size:0.9em;">No images selected</span>
                <button class="btn btn-primary" onclick="addImagesToGroup()">📤 Upload to Group</button>
            </div>
            <input type="file" id="addFileInput" accept="image/*" multiple onchange="updateAddFiles(this.files)">
            <div id="addFileList" style="margin-top:10px;display:flex;flex-wrap:wrap;gap:5px;"></div>
        </div>
        
        <div class="gallery-grid">
            {% for img in group.images %}
            <div class="gallery-item" data-filename="{{ img.filename }}">
                <img src="{{ img.url }}" alt="{{ img.original_name }}">
                <div class="name">{{ img.original_name }}</div>
            </div>
            {% endfor %}
        </div>
        
        <div style="margin-top:30px;text-align:center;color:rgba(255,255,255,0.2);font-size:0.8em;">
            🔨 Created by TORIKUL
        </div>
    </div>
    
    <div class="toast-container" id="toastContainer"></div>
    
    <script>
        let addFiles = [];
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
        
        function updateAddFiles(files) {
            addFiles = [];
            for (let f of files) {
                if (f.type.startsWith('image/')) {
                    addFiles.push(f);
                }
            }
            document.getElementById('addFileCount').textContent = addFiles.length + ' images selected';
            
            const list = document.getElementById('addFileList');
            list.innerHTML = '';
            addFiles.forEach((file, i) => {
                const tag = document.createElement('span');
                tag.style.cssText = 'background:rgba(102,126,234,0.2);padding:3px 12px;border-radius:15px;font-size:0.8em;';
                tag.textContent = '📸 ' + file.name.substring(0, 20);
                list.appendChild(tag);
            });
        }
        
        function addImagesToGroup() {
            if (addFiles.length === 0) {
                showToast('❌ Please select images!', 'error');
                return;
            }
            
            const formData = new FormData();
            formData.append('group_id', groupId);
            for (let file of addFiles) {
                formData.append('photos', file);
            }
            
            showToast('⏳ Uploading images...', 'success');
            
            fetch('/api/add-to-image-group', {
                method: 'POST',
                body: formData
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    showToast('✅ ' + data.count + ' images added to group!', 'success');
                    setTimeout(() => location.reload(), 1500);
                } else {
                    showToast('❌ ' + data.error, 'error');
                }
            })
            .catch(err => {
                showToast('❌ Upload failed!', 'error');
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
        .add-area {
            margin-top: 20px;
            padding: 20px;
            background: rgba(255,255,255,0.03);
            border-radius: 12px;
            border: 1px dashed rgba(102, 126, 234, 0.3);
        }
        .add-area input[type="text"] {
            flex: 1;
            padding: 10px 16px;
            background: rgba(255,255,255,0.06);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 8px;
            color: #fff;
            outline: none;
            min-width: 200px;
        }
        .add-area input[type="text"]:focus { border-color: #667eea; }
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
            .add-area .add-row { flex-direction: column; }
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
        
        <div class="add-area">
            <p style="margin-bottom:10px;color:rgba(255,255,255,0.6);">➕ Add More Links to this Group</p>
            <div class="add-row" style="display:flex;gap:10px;flex-wrap:wrap;">
                <input type="text" id="addLinkInput" placeholder="https://example.com">
                <button class="btn btn-primary" onclick="addLinkToGroup()">➕ Add Link</button>
            </div>
            <div id="addLinkStatus" style="margin-top:8px;color:rgba(255,255,255,0.4);font-size:0.85em;"></div>
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
            🔨 Created by TORIKUL
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
        
        function addLinkToGroup() {
            const input = document.getElementById('addLinkInput');
            const url = input.value.trim();
            
            if (!url) {
                showToast('❌ Please enter a URL!', 'error');
                return;
            }
            
            document.getElementById('addLinkStatus').textContent = '⏳ Adding link...';
            
            fetch('/api/add-to-link-group', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ group_id: groupId, url: url })
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    showToast('✅ Link added to group!', 'success');
                    document.getElementById('addLinkStatus').textContent = '✅ Link added!';
                    input.value = '';
                    setTimeout(() => location.reload(), 1500);
                } else {
                    showToast('❌ ' + data.error, 'error');
                    document.getElementById('addLinkStatus').textContent = '❌ ' + data.error;
                }
            })
            .catch(err => {
                showToast('❌ Failed to add link!', 'error');
                document.getElementById('addLinkStatus').textContent = '❌ Failed to add link!';
            });
        }
        
        function deleteLink(linkId) {
            if (!confirm('Are you sure you want to delete this link?')) return;
            fetch('/api/delete-link/' + linkId, { method: 'DELETE' })
                .then(res => res.json())
                .then(data => {
                    if (data.success) {
                        showToast('✅ Link deleted!', 'success');
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
        
        document.getElementById('addLinkInput').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') addLinkToGroup();
        });
        
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

PUBLIC_GROUP_VIEW_TEMPLATE = '''
<!DOCTYPE html>
<html lang="bn">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>📸 Group Gallery</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        html, body {
            width: 100%;
            min-height: 100vh;
            background: #0a0a1a;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            color: #fff;
            overflow-x: hidden;
            touch-action: pan-y;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 10px 0 20px;
            border-bottom: 1px solid rgba(255,255,255,0.05);
            margin-bottom: 25px;
        }
        .header h1 {
            font-size: 1.5em;
            font-weight: 600;
            background: linear-gradient(135deg, #667eea, #764ba2);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .header .count {
            color: rgba(255,255,255,0.5);
            font-size: 0.9em;
            background: rgba(255,255,255,0.06);
            padding: 6px 16px;
            border-radius: 20px;
        }
        .gallery-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
            gap: 12px;
        }
        .gallery-grid .thumb {
            position: relative;
            aspect-ratio: 1 / 1;
            overflow: hidden;
            border-radius: 12px;
            background: rgba(255,255,255,0.03);
            cursor: pointer;
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        }
        .gallery-grid .thumb:hover {
            transform: scale(1.02);
            box-shadow: 0 8px 25px rgba(0,0,0,0.5);
            z-index: 2;
        }
        .gallery-grid .thumb img {
            width: 100%;
            height: 100%;
            object-fit: cover;
            display: block;
            transition: filter 0.3s;
        }
        .gallery-grid .thumb:hover img {
            filter: brightness(0.85);
        }
        .gallery-grid .thumb .overlay {
            position: absolute;
            bottom: 0;
            left: 0;
            right: 0;
            padding: 10px;
            background: linear-gradient(transparent, rgba(0,0,0,0.6));
            opacity: 0;
            transition: opacity 0.3s;
            pointer-events: none;
        }
        .gallery-grid .thumb:hover .overlay {
            opacity: 1;
        }
        .gallery-grid .thumb .overlay span {
            font-size: 0.8em;
            color: rgba(255,255,255,0.8);
        }
        .lightbox {
            display: none;
            position: fixed;
            top: 0; left: 0;
            width: 100%; height: 100%;
            background: rgba(0,0,0,0.92);
            backdrop-filter: blur(8px);
            z-index: 1000;
            justify-content: center;
            align-items: center;
            flex-direction: column;
            touch-action: none;
        }
        .lightbox.active {
            display: flex;
        }
        .lightbox .close-btn {
            position: absolute;
            top: 20px;
            right: 25px;
            font-size: 2.2em;
            color: #fff;
            cursor: pointer;
            z-index: 10;
            width: 50px;
            height: 50px;
            display: flex;
            justify-content: center;
            align-items: center;
            border-radius: 50%;
            background: rgba(255,255,255,0.1);
            transition: background 0.2s;
            border: none;
            outline: none;
            font-weight: 300;
            user-select: none;
        }
        .lightbox .close-btn:hover {
            background: rgba(255,255,255,0.2);
        }
        .lightbox .nav-btn {
            position: absolute;
            top: 50%;
            transform: translateY(-50%);
            background: rgba(255,255,255,0.08);
            border: none;
            color: #fff;
            font-size: 2.5em;
            padding: 15px 10px;
            cursor: pointer;
            border-radius: 8px;
            transition: background 0.2s;
            z-index: 10;
            user-select: none;
            backdrop-filter: blur(4px);
        }
        .lightbox .nav-btn:hover {
            background: rgba(255,255,255,0.2);
        }
        .lightbox .nav-btn.prev { left: 15px; }
        .lightbox .nav-btn.next { right: 15px; }
        .lightbox .image-wrapper {
            display: flex;
            justify-content: center;
            align-items: center;
            width: 100%;
            height: 100%;
            padding: 20px 60px;
        }
        .lightbox .image-wrapper img {
            max-width: 100%;
            max-height: 100%;
            object-fit: contain;
            user-select: none;
            -webkit-user-drag: none;
            pointer-events: none;
            transition: opacity 0.25s ease;
            border-radius: 4px;
        }
        .lightbox .dots {
            position: absolute;
            bottom: 30px;
            left: 50%;
            transform: translateX(-50%);
            display: flex;
            gap: 10px;
            background: rgba(0,0,0,0.5);
            padding: 8px 14px;
            border-radius: 30px;
            backdrop-filter: blur(4px);
            z-index: 10;
        }
        .lightbox .dots .dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: rgba(255,255,255,0.25);
            transition: background 0.3s, transform 0.2s;
            cursor: default;
        }
        .lightbox .dots .dot.active {
            background: #fff;
            transform: scale(1.3);
        }
        .lightbox .counter {
            position: absolute;
            top: 20px;
            left: 25px;
            color: rgba(255,255,255,0.5);
            font-size: 0.95em;
            background: rgba(0,0,0,0.4);
            padding: 5px 14px;
            border-radius: 20px;
            backdrop-filter: blur(4px);
            z-index: 10;
            user-select: none;
        }
        @media (max-width: 600px) {
            .container { padding: 12px; }
            .gallery-grid { grid-template-columns: repeat(auto-fill, minmax(120px, 1fr)); gap: 8px; }
            .header h1 { font-size: 1.2em; }
            .lightbox .nav-btn { font-size: 1.8em; padding: 10px 6px; }
            .lightbox .nav-btn.prev { left: 5px; }
            .lightbox .nav-btn.next { right: 5px; }
            .lightbox .image-wrapper { padding: 10px 30px; }
            .lightbox .close-btn { top: 10px; right: 15px; font-size: 1.8em; width: 40px; height: 40px; }
            .lightbox .counter { font-size: 0.8em; padding: 4px 12px; left: 15px; top: 12px; }
            .lightbox .dots { bottom: 15px; gap: 8px; padding: 6px 12px; }
            .lightbox .dots .dot { width: 6px; height: 6px; }
        }
        @media (max-width: 400px) {
            .gallery-grid { grid-template-columns: repeat(auto-fill, minmax(90px, 1fr)); }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🖼️ Group Gallery</h1>
            <span class="count">{{ images|length }} images</span>
        </div>
        <div class="gallery-grid" id="galleryGrid">
            {% for img in images %}
            <div class="thumb" data-index="{{ loop.index0 }}">
                <img src="{{ img.url }}" alt="{{ img.original_name or 'Image' }}" loading="lazy">
                <div class="overlay"><span>🔍 View</span></div>
            </div>
            {% endfor %}
        </div>
    </div>

    <!-- Lightbox -->
    <div class="lightbox" id="lightbox">
        <button class="close-btn" id="closeLightbox" aria-label="Close">✕</button>
        <button class="nav-btn prev" id="prevBtn" aria-label="Previous">‹</button>
        <button class="nav-btn next" id="nextBtn" aria-label="Next">›</button>
        <div class="counter" id="lightboxCounter">1 / {{ images|length }}</div>
        <div class="image-wrapper" id="lightboxImageWrapper">
            <img id="lightboxImg" src="" alt="Lightbox image">
        </div>
        <div class="dots" id="lightboxDots">
            {% for _ in images %}
            <span class="dot"></span>
            {% endfor %}
        </div>
    </div>

    <script>
        (function() {
            const images = {{ images|tojson }};
            const total = images.length;
            if (total === 0) {
                document.querySelector('.gallery-grid').innerHTML = '<p style="color:rgba(255,255,255,0.4);text-align:center;padding:40px;">No images in this group.</p>';
                return;
            }

            let currentIndex = 0;
            const galleryGrid = document.getElementById('galleryGrid');
            const lightbox = document.getElementById('lightbox');
            const lightboxImg = document.getElementById('lightboxImg');
            const counter = document.getElementById('lightboxCounter');
            const dots = document.querySelectorAll('#lightboxDots .dot');
            const closeBtn = document.getElementById('closeLightbox');
            const prevBtn = document.getElementById('prevBtn');
            const nextBtn = document.getElementById('nextBtn');

            function openLightbox(index) {
                if (index < 0) index = total - 1;
                if (index >= total) index = 0;
                currentIndex = index;
                const imgData = images[currentIndex];
                lightboxImg.src = imgData.url;
                lightboxImg.alt = imgData.original_name || 'Image';
                counter.textContent = (currentIndex + 1) + ' / ' + total;
                dots.forEach((dot, i) => {
                    dot.classList.toggle('active', i === currentIndex);
                });
                lightbox.classList.add('active');
                document.body.style.overflow = 'hidden';
                preload(currentIndex);
            }

            function closeLightbox() {
                lightbox.classList.remove('active');
                document.body.style.overflow = '';
            }

            function goTo(index) {
                if (index < 0) index = total - 1;
                if (index >= total) index = 0;
                openLightbox(index);
            }

            function next() {
                goTo(currentIndex + 1);
            }

            function prev() {
                goTo(currentIndex - 1);
            }

            function preload(index) {
                const nextIdx = (index + 1) % total;
                const prevIdx = (index - 1 + total) % total;
                const preloadNext = new Image();
                preloadNext.src = images[nextIdx].url;
                const preloadPrev = new Image();
                preloadPrev.src = images[prevIdx].url;
            }

            document.querySelectorAll('.thumb').forEach((thumb, idx) => {
                thumb.addEventListener('click', function(e) {
                    e.preventDefault();
                    openLightbox(idx);
                });
            });

            closeBtn.addEventListener('click', closeLightbox);
            prevBtn.addEventListener('click', prev);
            nextBtn.addEventListener('click', next);

            document.addEventListener('keydown', function(e) {
                if (!lightbox.classList.contains('active')) return;
                if (e.key === 'Escape') {
                    closeLightbox();
                } else if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
                    e.preventDefault();
                    next();
                } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
                    e.preventDefault();
                    prev();
                }
            });

            let startX = 0, startY = 0;
            let isSwiping = false;
            lightbox.addEventListener('touchstart', function(e) {
                const touch = e.touches[0];
                startX = touch.clientX;
                startY = touch.clientY;
                isSwiping = true;
            }, { passive: true });

            lightbox.addEventListener('touchmove', function(e) {
                if (!isSwiping) return;
                const touch = e.touches[0];
                const diffX = touch.clientX - startX;
                const diffY = touch.clientY - startY;
                if (Math.abs(diffX) > Math.abs(diffY) && Math.abs(diffX) > 30) {
                    e.preventDefault();
                }
            }, { passive: false });

            lightbox.addEventListener('touchend', function(e) {
                if (!isSwiping) return;
                isSwiping = false;
                if (!e.changedTouches || e.changedTouches.length === 0) return;
                const touch = e.changedTouches[0];
                const diffX = touch.clientX - startX;
                const diffY = touch.clientY - startY;
                if (Math.abs(diffX) > Math.abs(diffY) && Math.abs(diffX) > 50) {
                    if (diffX < 0) next();
                    else prev();
                }
            }, { passive: true });

            document.addEventListener('contextmenu', function(e) {
                if (e.target.tagName === 'IMG' || lightbox.classList.contains('active')) {
                    e.preventDefault();
                }
            });

            lightbox.addEventListener('click', function(e) {
                if (e.target === lightbox || e.target === lightbox.querySelector('.image-wrapper')) {
                    closeLightbox();
                }
            });

            preload(0);
            console.log('📸 Group Gallery loaded: ' + total + ' images');
        })();
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
        if username == 'Torikul' and password == '@torikul_1999':
            session['logged_in'] = True
            session['username'] = username
            return redirect(url_for('dashboard'))
        else:
            return render_template_string(LOGIN_TEMPLATE, error='Invalid credentials', username=username)
    if session.get('logged_in'):
        return redirect(url_for('dashboard'))
    return render_template_string(LOGIN_TEMPLATE, error=None)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
def home():
    return redirect(url_for('login') if not session.get('logged_in') else url_for('dashboard'))

@app.route('/dashboard')
@login_required
def dashboard():
    db = SessionLocal()
    total_images = db.query(Image).filter(Image.group_id == None).count()
    total_links = db.query(Link).filter(Link.group_id == None).count()
    total_groups = db.query(Group).count()
    total_link_groups = db.query(LinkGroup).count()
    db.close()
    return render_template_string(DASHBOARD_TEMPLATE,
        total_images=total_images,
        total_links=total_links,
        total_groups=total_groups,
        total_link_groups=total_link_groups,
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
    db = SessionLocal()
    imgs = db.query(Image).filter(Image.group_id == None).all()
    images = [{'filename': img.id, 'url': request.host_url + 'image/' + img.id,
               'original_name': img.filename, 'size': img.size,
               'upload_date': img.upload_date.strftime('%Y-%m-%d %H:%M:%S')} for img in imgs]
    db.close()
    return render_template_string(GALLERY_TEMPLATE, images=images)

@app.route('/groups')
@login_required
def groups():
    db = SessionLocal()
    groups_data = {}
    for g in db.query(Group).all():
        groups_data[g.id] = {
            'id': g.id, 'name': g.name, 'url': g.url,
            'image_count': g.image_count,
            'created_at': g.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'images': g.image_list
        }
    db.close()
    return render_template_string(GROUPS_TEMPLATE, groups=groups_data)

@app.route('/link-groups')
@login_required
def link_groups():
    db = SessionLocal()
    groups_data = {}
    for lg in db.query(LinkGroup).all():
        groups_data[lg.id] = {
            'id': lg.id, 'name': lg.name, 'url': lg.url,
            'link_count': lg.link_count,
            'created_at': lg.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'links': lg.link_list
        }
    db.close()
    return render_template_string(LINK_GROUPS_TEMPLATE, groups=groups_data)

@app.route('/group/<group_id>')
@login_required
def view_group(group_id):
    db = SessionLocal()
    group = db.query(Group).filter_by(id=group_id).first()
    db.close()
    if not group:
        return "Group not found", 404
    return render_template_string(GROUP_VIEW_TEMPLATE, group={
        'id': group.id, 'name': group.name, 'url': group.url,
        'image_count': group.image_count,
        'created_at': group.created_at.strftime('%Y-%m-%d %H:%M:%S'),
        'images': group.image_list
    })

@app.route('/link-group/<group_id>')
@login_required
def view_link_group(group_id):
    db = SessionLocal()
    lg = db.query(LinkGroup).filter_by(id=group_id).first()
    db.close()
    if not lg:
        return "Link Group not found", 404
    return render_template_string(LINK_GROUP_VIEW_TEMPLATE, group={
        'id': lg.id, 'name': lg.name, 'url': lg.url,
        'link_count': lg.link_count,
        'created_at': lg.created_at.strftime('%Y-%m-%d %H:%M:%S'),
        'links': lg.link_list
    })

@app.route('/view-group/<group_id>')
def view_group_public(group_id):
    db = SessionLocal()
    group = db.query(Group).filter_by(id=group_id).first()
    db.close()
    if not group:
        return "Group not found", 404
    images = group.image_list
    if not images:
        return "No images in this group", 404
    return render_template_string(PUBLIC_GROUP_VIEW_TEMPLATE, group=group, images=images)

# ============ IMAGE SERVING ============
@app.route('/image/<filename>')
def serve_image(filename):
    db = SessionLocal()
    img = db.query(Image).filter_by(id=filename).first()
    db.close()
    if not img:
        return "Image not found", 404
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else 'png'
    mime = 'image/' + ext
    if ext in ['jpg', 'jpeg']:
        mime = 'image/jpeg'
    elif ext == 'png':
        mime = 'image/png'
    elif ext == 'gif':
        mime = 'image/gif'
    elif ext == 'webp':
        mime = 'image/webp'
    elif ext == 'svg':
        mime = 'image/svg+xml'
    elif ext == 'ico':
        mime = 'image/x-icon'
    return app.response_class(img.data, mimetype=mime)

# ============ API ROUTES ============

@app.route('/api/upload', methods=['POST'])
@login_required
def api_upload():
    if 'photos' not in request.files:
        return jsonify({'error': 'No files'}), 400
    files = request.files.getlist('photos')
    db = SessionLocal()
    uploaded = []
    for file in files:
        if file and allowed_file(file.filename):
            ext = file.filename.rsplit('.', 1)[1].lower()
            fid = generate_unique_id() + '.' + ext
            data = file.read()
            size_str = get_file_size(data)
            img = Image(id=fid, filename=file.filename, data=data, size=size_str, type=ext.upper())
            db.add(img)
            uploaded.append({'original_name': file.filename, 'url': request.host_url + 'image/' + fid,
                             'size': size_str, 'type': ext.upper(), 'filename': fid})
    db.commit()
    db.close()
    return jsonify({'success': True, 'files': uploaded})

@app.route('/api/multiple-upload', methods=['POST'])
@login_required
def api_multiple_upload():
    if 'photos' not in request.files:
        return jsonify({'error': 'No files'}), 400
    files = request.files.getlist('photos')
    if not files or files[0].filename == '':
        return jsonify({'error': 'No files selected'}), 400

    db = SessionLocal()
    group_id = generate_unique_id()
    group_name = f"Image_Group_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    uploaded = []

    for file in files:
        if file and allowed_file(file.filename):
            ext = file.filename.rsplit('.', 1)[1].lower()
            fid = generate_unique_id() + '.' + ext
            data = file.read()
            size_str = get_file_size(data)
            img = Image(id=fid, filename=file.filename, data=data, size=size_str, type=ext.upper(), group_id=group_id)
            db.add(img)
            uploaded.append({'original_name': file.filename, 'url': request.host_url + 'image/' + fid,
                             'size': size_str, 'type': ext.upper(), 'filename': fid})

    group_url = request.host_url + 'view-group/' + group_id
    group = Group(id=group_id, name=group_name, url=group_url)
    db.add(group)
    db.commit()
    db.close()

    return jsonify({
        'success': True,
        'group_id': group_id,
        'group_url': group_url,
        'group_name': group_name,
        'files': uploaded,
        'count': len(uploaded)
    })

@app.route('/api/add-to-image-group', methods=['POST'])
@login_required
def api_add_to_image_group():
    group_id = request.form.get('group_id')
    if not group_id:
        return jsonify({'error': 'Group ID required'}), 400
    if 'photos' not in request.files:
        return jsonify({'error': 'No files'}), 400

    db = SessionLocal()
    group = db.query(Group).filter_by(id=group_id).first()
    if not group:
        db.close()
        return jsonify({'error': 'Group not found'}), 404

    files = request.files.getlist('photos')
    added = 0
    for file in files:
        if file and allowed_file(file.filename):
            ext = file.filename.rsplit('.', 1)[1].lower()
            fid = generate_unique_id() + '.' + ext
            data = file.read()
            size_str = get_file_size(data)
            img = Image(id=fid, filename=file.filename, data=data, size=size_str, type=ext.upper(), group_id=group_id)
            db.add(img)
            added += 1
    db.commit()
    db.close()
    return jsonify({'success': True, 'count': added})

@app.route('/api/link-to-qr', methods=['POST'])
@login_required
def api_link_to_qr():
    data = request.get_json()
    url = data.get('url', '').strip()
    if not url:
        return jsonify({'success': False, 'error': 'URL required'}), 400
    if not validate_url(url):
        return jsonify({'success': False, 'error': 'Invalid URL'}), 400

    db = SessionLocal()
    link_id = generate_unique_id()
    qr = generate_qr_code_base64(url)
    link = Link(id=link_id, url=url, qr=qr)
    db.add(link)
    db.commit()
    db.close()
    return jsonify({'success': True, 'link_id': link_id, 'url': url, 'qr': qr})

@app.route('/api/multiple-links-to-qr', methods=['POST'])
@login_required
def api_multiple_links_to_qr():
    data = request.get_json()
    links = data.get('links', [])
    valid_links = [url.strip() for url in links if url.strip() and validate_url(url.strip())]
    if not valid_links:
        return jsonify({'success': False, 'error': 'No valid URLs'}), 400

    db = SessionLocal()
    group_id = generate_unique_id()
    group_name = f"Link_Group_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    processed = []

    for url in valid_links:
        lid = generate_unique_id()
        qr = generate_qr_code_base64(url)
        link = Link(id=lid, url=url, qr=qr, group_id=group_id)
        db.add(link)
        processed.append({'link_id': lid, 'url': url, 'qr': qr})

    group_url = request.host_url + 'link-group/' + group_id
    lg = LinkGroup(id=group_id, name=group_name, url=group_url)
    db.add(lg)
    db.commit()
    db.close()

    return jsonify({
        'success': True,
        'group_id': group_id,
        'group_url': group_url,
        'group_name': group_name,
        'links': processed,
        'count': len(processed)
    })

@app.route('/api/add-to-link-group', methods=['POST'])
@login_required
def api_add_to_link_group():
    data = request.get_json()
    group_id = data.get('group_id')
    url = data.get('url', '').strip()
    if not group_id or not url:
        return jsonify({'error': 'Group ID and URL required'}), 400
    if not validate_url(url):
        return jsonify({'error': 'Invalid URL'}), 400

    db = SessionLocal()
    lg = db.query(LinkGroup).filter_by(id=group_id).first()
    if not lg:
        db.close()
        return jsonify({'error': 'Group not found'}), 404

    lid = generate_unique_id()
    qr = generate_qr_code_base64(url)
    link = Link(id=lid, url=url, qr=qr, group_id=group_id)
    db.add(link)
    db.commit()
    db.close()
    return jsonify({'success': True, 'link_id': lid, 'url': url})

@app.route('/api/validate-url', methods=['POST'])
@login_required
def api_validate_url():
    data = request.get_json()
    url = data.get('url', '').strip()
    return jsonify({'valid': validate_url(url)})

@app.route('/api/qr/<filename>')
@login_required
def api_qr(filename):
    db = SessionLocal()
    img = db.query(Image).filter_by(id=filename).first()
    db.close()
    if not img:
        return jsonify({'error': 'Image not found'}), 404
    qr = generate_qr_code_base64(request.host_url + 'image/' + filename)
    return jsonify({'qr': qr})

@app.route('/api/qr-group/<group_id>')
def api_qr_group(group_id):
    db = SessionLocal()
    group = db.query(Group).filter_by(id=group_id).first()
    db.close()
    if not group:
        return jsonify({'error': 'Group not found'}), 404
    qr = generate_qr_code_base64(group.url)
    return jsonify({'qr': qr})

@app.route('/api/qr-link/<link_id>')
@login_required
def api_qr_link(link_id):
    db = SessionLocal()
    link = db.query(Link).filter_by(id=link_id).first()
    db.close()
    if not link:
        return jsonify({'error': 'Link not found'}), 404
    return jsonify({'qr': link.qr})

@app.route('/api/qr-link-group/<group_id>')
def api_qr_link_group(group_id):
    db = SessionLocal()
    lg = db.query(LinkGroup).filter_by(id=group_id).first()
    db.close()
    if not lg:
        return jsonify({'error': 'Link Group not found'}), 404
    qr = generate_qr_code_base64(lg.url)
    return jsonify({'qr': qr})

@app.route('/api/delete/<filename>', methods=['DELETE'])
@login_required
def delete_image(filename):
    db = SessionLocal()
    img = db.query(Image).filter_by(id=filename).first()
    if img:
        db.delete(img)
        db.commit()
    db.close()
    return jsonify({'success': True})

@app.route('/api/delete-link/<link_id>', methods=['DELETE'])
@login_required
def delete_link(link_id):
    db = SessionLocal()
    link = db.query(Link).filter_by(id=link_id).first()
    if link:
        db.delete(link)
        db.commit()
    db.close()
    return jsonify({'success': True})

@app.route('/api/delete-group/<group_id>', methods=['DELETE'])
@login_required
def delete_group(group_id):
    db = SessionLocal()
    group = db.query(Group).filter_by(id=group_id).first()
    if group:
        for img in group.images:
            db.delete(img)
        db.delete(group)
        db.commit()
    db.close()
    return jsonify({'success': True})

@app.route('/api/delete-link-group/<group_id>', methods=['DELETE'])
@login_required
def delete_link_group(group_id):
    db = SessionLocal()
    lg = db.query(LinkGroup).filter_by(id=group_id).first()
    if lg:
        for link in lg.links:
            db.delete(link)
        db.delete(lg)
        db.commit()
    db.close()
    return jsonify({'success': True})

# ============ MAIN ============
if __name__ == '__main__':
    print("\n" + "="*60)
    print("🖼️ TORIKUL IMAGE • LINK • QR SYSTEM v5.0 (Persistent DB)")
    print("="*60)
    print(f"🌐 Server: http://127.0.0.1:5000")
    print(f"🔑 Login: Torikul / @torikul_1999")
    print("="*60)
    print("✅ Now uses SQLite (or PostgreSQL) – data persists across restarts!")
    print("Press CTRL+C to stop\n")
    app.run(debug=True, host='0.0.0.0', port=5000)