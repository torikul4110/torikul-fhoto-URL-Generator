import os
import secrets
from datetime import datetime
from flask import Flask, render_template_string, request, jsonify, session, redirect, url_for
from functools import wraps
from io import BytesIO
import base64
import re
import cloudinary
import cloudinary.uploader
from supabase import create_client, Client
import qrcode
import json
import tempfile

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))

# ============ CONFIGURATION ============
CLOUDINARY_CLOUD_NAME = "dzn0efzl1"
CLOUDINARY_API_KEY = "234878757997651"
CLOUDINARY_API_SECRET = "lnUtuTC0Y8sditFGBubIGpCx37c"
SUPABASE_URL = "https://cfvbtuiszdhfcugqnlzt.supabase.co"
SUPABASE_KEY = "sb_publishable__9p2gniXYBGlgzbPVG2RmA_6hH4GPqe"
ADMIN_USERNAME = "Torikul"
ADMIN_PASSWORD = "@torikul_1999"
BASE_URL = os.environ.get('BASE_URL', 'http://127.0.0.1:5000')

# ============ SUPABASE & CLOUDINARY ============
try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    print("✅ Supabase connected")
except Exception as e:
    print(f"❌ Supabase error: {e}")
    supabase = None

try:
    cloudinary.config(
        cloud_name=CLOUDINARY_CLOUD_NAME,
        api_key=CLOUDINARY_API_KEY,
        api_secret=CLOUDINARY_API_SECRET
    )
    print("✅ Cloudinary configured")
except Exception as e:
    print(f"❌ Cloudinary error: {e}")

# ============ FILE STORAGE ============
BASE_DIR = tempfile.gettempdir() if not os.environ.get('VERCEL') else '/tmp'
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 200 * 1024 * 1024
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp', 'svg', 'ico'}

# ============ LOCAL JSON FALLBACK ============
LOCAL_DATA_DIR = os.path.join(tempfile.gettempdir(), 'torikul_data')
os.makedirs(LOCAL_DATA_DIR, exist_ok=True)
IMAGES_JSON = os.path.join(LOCAL_DATA_DIR, 'images.json')
GROUPS_JSON = os.path.join(LOCAL_DATA_DIR, 'groups.json')
LINKS_JSON = os.path.join(LOCAL_DATA_DIR, 'links.json')
LINK_GROUPS_JSON = os.path.join(LOCAL_DATA_DIR, 'link_groups.json')

def load_local_json(filepath):
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_local_json(filepath, data):
    try:
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"Error saving local JSON: {e}")

# ============ HELPERS ============
def generate_unique_id():
    return secrets.token_hex(4) + 'torikul'

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

def upload_to_cloudinary(file_path, public_id):
    try:
        result = cloudinary.uploader.upload(
            file_path,
            public_id=f"torikul_images/{public_id}",
            folder="torikul_images",
            overwrite=True
        )
        return result.get('secure_url')
    except Exception as e:
        print(f"Cloudinary upload error: {e}")
        return None

# ============ DATABASE FUNCTIONS ============
def save_image_to_db(filename, original_name, url, size, file_type, group_id=None, link_id=None):
    data = {
        'filename': filename,
        'original_name': original_name,
        'url': url,
        'size': size,
        'type': file_type,
        'upload_date': datetime.now().isoformat(),
        'group_id': group_id,
        'link_id': link_id or generate_unique_id(),
        'views': 0,
        'is_active': True
    }
    if supabase:
        try:
            result = supabase.table('images').insert(data).execute()
            if result.data:
                return result.data[0]
        except Exception as e:
            print(f"Supabase save error: {e}")
    images = load_local_json(IMAGES_JSON)
    images[filename] = data
    save_local_json(IMAGES_JSON, images)
    return data

def get_images_from_db():
    if supabase:
        try:
            result = supabase.table('images').select('*').execute()
            images = {}
            for item in result.data:
                if item.get('is_active', True):
                    images[item['filename']] = {
                        'filename': item['original_name'],
                        'url': item['url'],
                        'size': item['size'],
                        'type': item['type'],
                        'upload_date': item['upload_date'],
                        'group_id': item.get('group_id'),
                        'link_id': item.get('link_id'),
                        'views': item.get('views', 0),
                        'is_active': item.get('is_active', True)
                    }
            return images
        except Exception as e:
            print(f"Supabase fetch error: {e}")
    return load_local_json(IMAGES_JSON)

def save_group_to_db(group_id, name, url, image_count, images, link_id=None):
    data = {
        'id': group_id,
        'name': name,
        'url': url,
        'image_count': image_count,
        'images': images,
        'created_at': datetime.now().isoformat(),
        'views': 0,
        'link_id': link_id or generate_unique_id(),
        'is_active': True
    }
    if supabase:
        try:
            supabase_data = data.copy()
            supabase_data['images'] = json.dumps(images)
            result = supabase.table('groups').insert(supabase_data).execute()
            if result.data:
                return result.data[0]
        except Exception as e:
            print(f"Supabase group save error: {e}")
    groups = load_local_json(GROUPS_JSON)
    groups[group_id] = data
    save_local_json(GROUPS_JSON, groups)
    return data

def get_groups_from_db():
    if supabase:
        try:
            result = supabase.table('groups').select('*').execute()
            groups = {}
            for item in result.data:
                if item.get('is_active', True):
                    groups[item['id']] = {
                        'id': item['id'],
                        'name': item['name'],
                        'url': item['url'],
                        'image_count': item['image_count'],
                        'images': json.loads(item['images']) if item['images'] else [],
                        'created_at': item['created_at'],
                        'views': item.get('views', 0),
                        'link_id': item.get('link_id'),
                        'is_active': item.get('is_active', True)
                    }
            return groups
        except Exception as e:
            print(f"Supabase group fetch error: {e}")
    return load_local_json(GROUPS_JSON)

def save_link_to_db(link_id, url, qr, group_id=None, image_id=None, link_type='image'):
    data = {
        'link_id': link_id,
        'url': url,
        'qr': qr,
        'group_id': group_id,
        'image_id': image_id,
        'link_type': link_type,
        'created_at': datetime.now().isoformat(),
        'is_active': True
    }
    if supabase:
        try:
            result = supabase.table('links').insert(data).execute()
            if result.data:
                return result.data[0]
        except Exception as e:
            print(f"Supabase link save error: {e}")
    links = load_local_json(LINKS_JSON)
    links[link_id] = data
    save_local_json(LINKS_JSON, links)
    return data

def get_links_from_db():
    if supabase:
        try:
            result = supabase.table('links').select('*').execute()
            links = {}
            for item in result.data:
                if item.get('is_active', True):
                    links[item['link_id']] = {
                        'link_id': item['link_id'],
                        'url': item['url'],
                        'qr': item['qr'],
                        'group_id': item.get('group_id'),
                        'image_id': item.get('image_id'),
                        'link_type': item.get('link_type', 'image'),
                        'created_at': item['created_at'],
                        'is_active': item.get('is_active', True)
                    }
            return links
        except Exception as e:
            print(f"Supabase link fetch error: {e}")
    return load_local_json(LINKS_JSON)

def save_link_group_to_db(group_id, name, url, link_count, links, link_id=None):
    data = {
        'id': group_id,
        'name': name,
        'url': url,
        'link_count': link_count,
        'links': links,
        'created_at': datetime.now().isoformat(),
        'views': 0,
        'link_id': link_id or generate_unique_id(),
        'is_active': True
    }
    if supabase:
        try:
            supabase_data = data.copy()
            supabase_data['links'] = json.dumps(links)
            result = supabase.table('link_groups').insert(supabase_data).execute()
            if result.data:
                return result.data[0]
        except Exception as e:
            print(f"Supabase link group save error: {e}")
    link_groups = load_local_json(LINK_GROUPS_JSON)
    link_groups[group_id] = data
    save_local_json(LINK_GROUPS_JSON, link_groups)
    return data

def get_link_groups_from_db():
    if supabase:
        try:
            result = supabase.table('link_groups').select('*').execute()
            link_groups = {}
            for item in result.data:
                if item.get('is_active', True):
                    link_groups[item['id']] = {
                        'id': item['id'],
                        'name': item['name'],
                        'url': item['url'],
                        'link_count': item['link_count'],
                        'links': json.loads(item['links']) if item['links'] else [],
                        'created_at': item['created_at'],
                        'views': item.get('views', 0),
                        'link_id': item.get('link_id'),
                        'is_active': item.get('is_active', True)
                    }
            return link_groups
        except Exception as e:
            print(f"Supabase link group fetch error: {e}")
    return load_local_json(LINK_GROUPS_JSON)

def delete_image_from_db(filename):
    if supabase:
        try:
            supabase.table('images').update({'is_active': False}).eq('filename', filename).execute()
        except Exception as e:
            print(f"Supabase delete error: {e}")
    images = load_local_json(IMAGES_JSON)
    if filename in images:
        images[filename]['is_active'] = False
        save_local_json(IMAGES_JSON, images)
    return True

def delete_group_from_db(group_id):
    if supabase:
        try:
            supabase.table('images').update({'is_active': False}).eq('group_id', group_id).execute()
            supabase.table('groups').update({'is_active': False}).eq('id', group_id).execute()
        except Exception as e:
            print(f"Supabase delete error: {e}")
    groups = load_local_json(GROUPS_JSON)
    if group_id in groups:
        groups[group_id]['is_active'] = False
        save_local_json(GROUPS_JSON, groups)
    return True

def delete_link_from_db(link_id):
    if supabase:
        try:
            supabase.table('links').update({'is_active': False}).eq('link_id', link_id).execute()
        except Exception as e:
            print(f"Supabase delete error: {e}")
    links = load_local_json(LINKS_JSON)
    if link_id in links:
        links[link_id]['is_active'] = False
        save_local_json(LINKS_JSON, links)
    return True

def delete_link_group_from_db(group_id):
    if supabase:
        try:
            supabase.table('links').update({'is_active': False}).eq('group_id', group_id).execute()
            supabase.table('link_groups').update({'is_active': False}).eq('id', group_id).execute()
        except Exception as e:
            print(f"Supabase delete error: {e}")
    link_groups = load_local_json(LINK_GROUPS_JSON)
    if group_id in link_groups:
        link_groups[group_id]['is_active'] = False
        save_local_json(LINK_GROUPS_JSON, link_groups)
    return True

def add_image_to_group_db(group_id, image_data):
    if supabase:
        try:
            group = supabase.table('groups').select('images, image_count').eq('id', group_id).execute()
            if group.data:
                images = json.loads(group.data[0]['images']) if group.data[0]['images'] else []
                images.append(image_data)
                image_count = group.data[0]['image_count'] + 1
                supabase.table('groups').update({
                    'images': json.dumps(images),
                    'image_count': image_count
                }).eq('id', group_id).execute()
        except Exception as e:
            print(f"Add to group error: {e}")
    groups = load_local_json(GROUPS_JSON)
    if group_id in groups:
        groups[group_id]['images'].append(image_data)
        groups[group_id]['image_count'] = len(groups[group_id]['images'])
        save_local_json(GROUPS_JSON, groups)
    return True

def delete_single_image_from_group(group_id, filename):
    if supabase:
        try:
            group = supabase.table('groups').select('images, image_count').eq('id', group_id).execute()
            if group.data:
                images = json.loads(group.data[0]['images']) if group.data[0]['images'] else []
                images = [img for img in images if img['filename'] != filename]
                image_count = len(images)
                supabase.table('groups').update({
                    'images': json.dumps(images),
                    'image_count': image_count
                }).eq('id', group_id).execute()
        except Exception as e:
            print(f"Delete from group error: {e}")
    groups = load_local_json(GROUPS_JSON)
    if group_id in groups:
        groups[group_id]['images'] = [img for img in groups[group_id]['images'] if img['filename'] != filename]
        groups[group_id]['image_count'] = len(groups[group_id]['images'])
        save_local_json(GROUPS_JSON, groups)
    return True

def regenerate_link_and_qr(item_type, item_id):
    try:
        if item_type == 'image':
            images = get_images_from_db()
            if item_id not in images:
                return None
            image_data = images[item_id]
            old_link_id = image_data.get('link_id')
            new_link_id = generate_unique_id()
            new_url = BASE_URL + '/view/image/' + item_id + '?link=' + new_link_id
            new_qr = generate_qr_code_base64(new_url)
            if old_link_id:
                delete_link_from_db(old_link_id)
            save_link_to_db(new_link_id, new_url, new_qr, image_id=item_id, link_type='image')
            if supabase:
                supabase.table('images').update({'link_id': new_link_id}).eq('filename', item_id).execute()
            images[item_id]['link_id'] = new_link_id
            save_local_json(IMAGES_JSON, images)
            return {'link_id': new_link_id, 'url': new_url, 'qr': new_qr}
        elif item_type == 'group':
            groups = get_groups_from_db()
            if item_id not in groups:
                return None
            group_data = groups[item_id]
            old_link_id = group_data.get('link_id')
            new_link_id = generate_unique_id()
            new_url = BASE_URL + '/view/group/' + item_id + '?link=' + new_link_id
            new_qr = generate_qr_code_base64(new_url)
            if old_link_id:
                delete_link_from_db(old_link_id)
            save_link_to_db(new_link_id, new_url, new_qr, group_id=item_id, link_type='group')
            if supabase:
                supabase.table('groups').update({'link_id': new_link_id, 'url': new_url}).eq('id', item_id).execute()
            groups[item_id]['link_id'] = new_link_id
            groups[item_id]['url'] = new_url
            save_local_json(GROUPS_JSON, groups)
            return {'link_id': new_link_id, 'url': new_url, 'qr': new_qr}
        elif item_type == 'link':
            links = get_links_from_db()
            if item_id not in links:
                return None
            link_data = links[item_id]
            new_link_id = generate_unique_id()
            new_url = link_data['url']
            new_qr = generate_qr_code_base64(new_url)
            delete_link_from_db(item_id)
            save_link_to_db(
                new_link_id, 
                new_url, 
                new_qr,
                group_id=link_data.get('group_id'),
                image_id=link_data.get('image_id'),
                link_type=link_data.get('link_type', 'image')
            )
            return {'link_id': new_link_id, 'url': new_url, 'qr': new_qr}
        return None
    except Exception as e:
        print(f"Regenerate error: {e}")
        return None

# ============ TEMPLATES (app1.py style design) ============

LOGIN_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Login - TORIKUL SYSTEM</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            background: linear-gradient(135deg, #0f0c29, #302b63, #24243e);
        }
        .login-container {
            width: 100%;
            max-width: 420px;
            padding: 20px;
        }
        .login-box {
            background: rgba(255,255,255,0.05);
            backdrop-filter: blur(20px);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 24px;
            padding: 40px 35px;
            box-shadow: 0 25px 80px rgba(0,0,0,0.5);
        }
        .login-header { text-align: center; margin-bottom: 35px; }
        .login-icon { font-size: 3.5em; display: block; margin-bottom: 10px; }
        .login-title { color: #fff; font-size: 1.8em; font-weight: 700; }
        .login-subtitle { color: rgba(255,255,255,0.6); font-size: 0.95em; margin-top: 5px; }
        .form-group { margin-bottom: 20px; }
        .form-group label { display: block; color: rgba(255,255,255,0.7); font-size: 0.9em; margin-bottom: 8px; font-weight: 500; }
        .form-group input {
            width: 100%;
            padding: 14px 20px;
            background: rgba(255,255,255,0.06);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 12px;
            color: #fff;
            font-size: 1em;
            transition: all 0.3s;
            outline: none;
        }
        .form-group input:focus {
            border-color: #667eea;
            background: rgba(255,255,255,0.08);
            box-shadow: 0 0 20px rgba(102,126,234,0.15);
        }
        .form-group input::placeholder { color: rgba(255,255,255,0.3); }
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
        .btn-login:hover { transform: scale(1.02); box-shadow: 0 10px 30px rgba(102,126,234,0.3); }
        .error-msg {
            background: rgba(255,0,0,0.15);
            border: 1px solid rgba(255,0,0,0.2);
            color: #ff6b6b;
            padding: 12px 16px;
            border-radius: 10px;
            margin-bottom: 20px;
            font-size: 0.9em;
            display: {{ 'block' if error else 'none' }};
        }
        .footer { text-align: center; margin-top: 25px; color: rgba(255,255,255,0.3); font-size: 0.8em; }
    </style>
</head>
<body>
    <div class="login-container">
        <div class="login-box">
            <div class="login-header">
                <span class="login-icon">🖼️</span>
                <h1 class="login-title">TORIKUL SYSTEM</h1>
                <p class="login-subtitle">Welcome Back</p>
            </div>
            <div class="error-msg" id="errorMsg">{{ error }}</div>
            <form method="POST" action="{{ url_for('login') }}">
                <div class="form-group">
                    <label>Username</label>
                    <input type="text" name="username" placeholder="Enter your username" value="{{ username or '' }}" required>
                </div>
                <div class="form-group">
                    <label>Password</label>
                    <input type="password" name="password" placeholder="Enter your password" required>
                </div>
                <button type="submit" class="btn-login">Login</button>
            </form>
            <div class="footer">Created by TORIKUL</div>
        </div>
    </div>
    <script>
        {% if error %}document.getElementById('errorMsg').style.display = 'block';{% endif %}
    </script>
</body>
</html>
'''

DASHBOARD_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dashboard - TORIKUL SYSTEM</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: #0a0a1a;
            min-height: 100vh;
            color: #fff;
        }
        .app-container { display: flex; min-height: 100vh; }
        .sidebar {
            width: 240px;
            background: rgba(20,20,40,0.95);
            backdrop-filter: blur(10px);
            border-right: 1px solid rgba(255,255,255,0.05);
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
            border-bottom: 1px solid rgba(255,255,255,0.05);
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
            color: rgba(255,255,255,0.4);
        }
        .nav-item {
            display: flex;
            align-items: center;
            padding: 12px 25px;
            color: rgba(255,255,255,0.6);
            text-decoration: none;
            transition: all 0.3s;
            border-left: 3px solid transparent;
            gap: 12px;
        }
        .nav-item:hover, .nav-item.active {
            background: rgba(102,126,234,0.1);
            color: #fff;
            border-left-color: #667eea;
        }
        .nav-item .nav-icon { font-size: 1.2em; width: 28px; }
        .nav-item .nav-text { font-size: 0.95em; }
        .nav-item.logout {
            margin-top: 20px;
            border-top: 1px solid rgba(255,255,255,0.05);
            padding-top: 20px;
            color: #ff6b6b;
        }
        .nav-item.logout:hover { border-left-color: #ff6b6b; background: rgba(255,0,0,0.1); }
        .main-content {
            margin-left: 240px;
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
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .stat-card {
            background: rgba(255,255,255,0.04);
            border: 1px solid rgba(255,255,255,0.06);
            border-radius: 16px;
            padding: 20px 25px;
            transition: all 0.3s;
            text-decoration: none;
            color: #fff;
            display: block;
            cursor: pointer;
        }
        .stat-card:hover { transform: translateY(-3px); background: rgba(255,255,255,0.06); }
        .stat-card .stat-icon { font-size: 2em; margin-bottom: 8px; }
        .stat-card .stat-number { font-size: 2em; font-weight: 700; }
        .stat-card .stat-label { color: rgba(255,255,255,0.5); font-size: 0.85em; }
        .btn {
            padding: 10px 20px;
            border: none;
            border-radius: 10px;
            font-size: 0.95em;
            cursor: pointer;
            transition: all 0.3s;
            color: #fff;
            font-weight: 500;
            text-decoration: none;
            display: inline-block;
        }
        .btn-primary { background: linear-gradient(135deg, #667eea, #764ba2); }
        .btn-primary:hover { transform: scale(1.05); box-shadow: 0 10px 30px rgba(102,126,234,0.3); }
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
            background: rgba(20,20,40,0.95);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255,255,255,0.1);
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
            <a href="/dashboard" class="nav-item active">
                <span class="nav-icon">🏠</span><span class="nav-text">Dashboard</span>
            </a>
            <a href="/upload" class="nav-item">
                <span class="nav-icon">📸</span><span class="nav-text">Upload Image</span>
            </a>
            <a href="/multiple-upload" class="nav-item">
                <span class="nav-icon">📸📸</span><span class="nav-text">Multiple Upload</span>
            </a>
            <a href="/link-to-qr" class="nav-item">
                <span class="nav-icon">🔗</span><span class="nav-text">Link to QR</span>
            </a>
            <a href="/multiple-links-to-qr" class="nav-item">
                <span class="nav-icon">🔗🔗</span><span class="nav-text">Multiple Links</span>
            </a>
            <a href="/gallery" class="nav-item">
                <span class="nav-icon">🖼️</span><span class="nav-text">My Images</span>
            </a>
            <a href="/groups" class="nav-item">
                <span class="nav-icon">📁</span><span class="nav-text">Image Groups</span>
            </a>
            <a href="/link-groups" class="nav-item">
                <span class="nav-icon">📁🔗</span><span class="nav-text">Link Groups</span>
            </a>
            <a href="/logout" class="nav-item logout">
                <span class="nav-icon">🚪</span><span class="nav-text">Logout</span>
            </a>
        </nav>
        <div class="main-content">
            <div class="top-bar">
                <div style="display:flex;align-items:center;gap:15px;">
                    <button class="menu-toggle" onclick="toggleSidebar()">☰</button>
                    <h1>Welcome, <span>TORIKUL</span></h1>
                </div>
                <div style="color:rgba(255,255,255,0.4);">📅 {{ now.strftime('%B %d, %Y') }}</div>
            </div>
            <div class="stats-grid">
                <a href="/gallery" class="stat-card">
                    <div class="stat-icon">📸</div>
                    <div class="stat-number">{{ total_images }}</div>
                    <div class="stat-label">Total Images</div>
                </a>
                <a href="/link-groups" class="stat-card">
                    <div class="stat-icon">🔗</div>
                    <div class="stat-number">{{ total_links }}</div>
                    <div class="stat-label">Total Links</div>
                </a>
                <a href="/groups" class="stat-card">
                    <div class="stat-icon">📁</div>
                    <div class="stat-number">{{ total_groups }}</div>
                    <div class="stat-label">Image Groups</div>
                </a>
                <a href="/link-groups" class="stat-card">
                    <div class="stat-icon">📁🔗</div>
                    <div class="stat-number">{{ total_link_groups }}</div>
                    <div class="stat-label">Link Groups</div>
                </a>
            </div>
            <div style="margin-top:40px;text-align:center;color:rgba(255,255,255,0.2);font-size:0.8em;padding:20px;">
                Created by TORIKUL
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
    </script>
</body>
</html>
'''

# ============ UPLOAD TEMPLATE (app1.py style) ============
UPLOAD_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Upload - TORIKUL SYSTEM</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
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
            border: 3px dashed rgba(102,126,234,0.3);
            border-radius: 20px;
            padding: 60px 20px;
            text-align: center;
            background: rgba(255,255,255,0.02);
            cursor: pointer;
            transition: all 0.3s;
        }
        .upload-area:hover { border-color: #667eea; background: rgba(102,126,234,0.05); }
        .upload-area .icon { font-size: 4em; margin-bottom: 15px; }
        .upload-area .text { font-size: 1.2em; color: rgba(255,255,255,0.6); }
        .upload-area .sub { color: rgba(255,255,255,0.3); font-size: 0.9em; margin-top: 5px; }
        #fileInput { display: none; }
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
        .btn-primary:hover { transform: scale(1.05); box-shadow: 0 10px 30px rgba(102,126,234,0.3); }
        .btn-success { background: linear-gradient(135deg, #51cf66, #40c057); }
        .btn-success:hover { transform: scale(1.05); }
        .btn-danger { background: linear-gradient(135deg, #ff6b6b, #e03131); }
        .btn-danger:hover { transform: scale(1.05); }
        .btn-secondary { background: rgba(255,255,255,0.1); }
        .btn-secondary:hover { background: rgba(255,255,255,0.2); }
        .group-input {
            margin-top: 20px;
            padding: 20px;
            background: rgba(255,255,255,0.04);
            border-radius: 12px;
            border: 1px solid rgba(255,255,255,0.06);
        }
        .group-input label { display: block; color: rgba(255,255,255,0.7); margin-bottom: 8px; font-weight: 500; }
        .group-input input {
            width: 100%; padding: 12px 16px;
            background: rgba(255,255,255,0.06);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 10px;
            color: #fff; font-size: 1em;
            transition: all 0.3s; outline: none;
        }
        .group-input input:focus { border-color: #667eea; background: rgba(255,255,255,0.08); }
        .group-input input::placeholder { color: rgba(255,255,255,0.3); }
        .result-box {
            display: none;
            margin-top: 30px;
            background: rgba(255,255,255,0.04);
            border: 1px solid rgba(255,255,255,0.06);
            border-radius: 20px;
            padding: 30px;
        }
        .result-box .preview { text-align: center; margin-bottom: 20px; }
        .result-box .preview img { max-width: 100%; max-height: 400px; border-radius: 12px; }
        .info-row {
            display: flex; flex-wrap: wrap; gap: 15px;
            margin: 10px 0; padding: 12px 16px;
            background: rgba(255,255,255,0.03);
            border-radius: 10px; align-items: center;
        }
        .info-row .label { color: rgba(255,255,255,0.5); min-width: 100px; }
        .info-row .value { word-break: break-all; flex: 1; color: #667eea; }
        .btn-group { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 15px; }
        .qr-container { text-align: center; padding: 15px; background: #fff; border-radius: 12px; display: inline-block; }
        .qr-container img { max-width: 200px; }
        .loading {
            display: none;
            text-align: center;
            padding: 30px;
        }
        .spinner {
            border: 4px solid rgba(255,255,255,0.1);
            border-top: 4px solid #667eea;
            border-radius: 50%;
            width: 40px; height: 40px;
            animation: spin 1s linear infinite;
            margin: 0 auto;
        }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        .toast-container {
            position: fixed; bottom: 30px; right: 30px;
            z-index: 999; display: flex; flex-direction: column; gap: 10px;
        }
        .toast {
            padding: 14px 24px; border-radius: 12px;
            background: rgba(20,20,40,0.95); backdrop-filter: blur(10px);
            border: 1px solid rgba(255,255,255,0.1);
            color: #fff; font-size: 0.95em;
            animation: slideIn 0.3s ease-out;
        }
        .toast.success { border-left: 4px solid #51cf66; }
        .toast.error { border-left: 4px solid #ff6b6b; }
        @keyframes slideIn { from { transform: translateX(100px); opacity: 0; } to { transform: translateX(0); opacity: 1; } }
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
            <h1>📸 Single Upload</h1>
            <a href="/dashboard" class="btn-back">🏠 Dashboard</a>
        </div>
        <div class="upload-area" onclick="document.getElementById('fileInput').click()">
            <div class="icon">📷</div>
            <div class="text">Click to select an image</div>
            <div class="sub">or drag & drop here</div>
            <input type="file" id="fileInput" accept="image/*" onchange="handleFile(this.files[0])">
        </div>
        <div class="group-input">
            <label>Group Name (optional)</label>
            <input type="text" id="groupName" placeholder="Leave empty for no group">
        </div>
        <div style="margin-top:15px;">
            <button class="btn btn-primary" onclick="uploadWithGroup()" id="uploadBtn" style="display:none;">Upload & Create Group</button>
        </div>
        <div class="loading" id="loading">
            <div class="spinner"></div>
            <p style="margin-top:15px;">Uploading...</p>
        </div>
        <div class="result-box" id="resultBox">
            <div class="preview"><img id="previewImg" alt="Preview"></div>
            <div class="info-row"><span class="label">Filename</span><span class="value" id="fileName">-</span></div>
            <div class="info-row"><span class="label">Size</span><span class="value" id="fileSize">-</span></div>
            <div class="info-row"><span class="label">Group</span><span class="value" id="groupNameDisplay">-</span></div>
            <div class="info-row"><span class="label">Image URL</span><span class="value" id="imageUrl">-</span></div>
            <div class="info-row"><span class="label">Group URL</span><span class="value" id="groupUrl">-</span></div>
            <div class="btn-group">
                <button class="btn btn-primary" onclick="copyLink('imageUrl')">📋 Copy Image Link</button>
                <button class="btn btn-success" onclick="copyLink('groupUrl')">📋 Copy Group Link</button>
                <button class="btn btn-success" onclick="downloadQR()">⬇️ Download QR</button>
                <button class="btn btn-danger" onclick="deleteImage()">🗑️ Delete</button>
            </div>
            <div style="margin-top:20px;text-align:center;">
                <div class="qr-container"><img id="qrImg" alt="QR Code"></div>
            </div>
        </div>
        <div style="margin-top:30px;text-align:center;color:rgba(255,255,255,0.2);font-size:0.8em;">
            Created by TORIKUL
        </div>
    </div>
    <div class="toast-container" id="toastContainer"></div>
    <script>
        let currentFile = null;
        let currentFilename = null;
        let currentGroupId = null;

        function handleFile(file) {
            if (!file) return;
            currentFile = file;
            document.getElementById('uploadBtn').style.display = 'inline-block';
        }

        function uploadWithGroup() {
            if (!currentFile) {
                showToast('Please select an image first!', 'error');
                return;
            }
            const groupName = document.getElementById('groupName').value.trim();
            document.getElementById('loading').style.display = 'block';
            document.getElementById('resultBox').style.display = 'none';
            const formData = new FormData();
            formData.append('photos', currentFile);
            if (groupName) formData.append('group_name', groupName);

            fetch('/api/upload-with-group', {
                method: 'POST',
                body: formData
            })
            .then(res => res.json())
            .then(data => {
                if (data.success && data.files.length > 0) {
                    const img = data.files[0];
                    currentFilename = img.filename;
                    currentGroupId = data.group_id;
                    document.getElementById('previewImg').src = img.url;
                    document.getElementById('fileName').textContent = img.original_name;
                    document.getElementById('fileSize').textContent = img.size;
                    document.getElementById('imageUrl').textContent = img.link_url;
                    document.getElementById('groupNameDisplay').textContent = data.group_name || 'None';
                    document.getElementById('groupUrl').textContent = data.group_url || 'N/A';
                    document.getElementById('qrImg').src = 'data:image/png;base64,' + img.qr;
                    document.getElementById('resultBox').style.display = 'block';
                    document.getElementById('loading').style.display = 'none';
                    showToast('Uploaded successfully!', 'success');
                }
            })
            .catch(err => {
                document.getElementById('loading').style.display = 'none';
                showToast('Upload failed!', 'error');
            });
        }

        function copyLink(elementId) {
            const el = document.getElementById(elementId);
            const url = el.textContent;
            if (url && url !== '-') {
                navigator.clipboard.writeText(url).then(() => {
                    showToast('Link copied!', 'success');
                }).catch(() => { prompt('Copy this link:', url); });
            } else {
                showToast('No link available!', 'error');
            }
        }

        function downloadQR() {
            const img = document.getElementById('qrImg');
            if (img.src) {
                const link = document.createElement('a');
                link.download = 'qr_' + currentFilename + '.png';
                link.href = img.src;
                link.click();
                showToast('QR Code downloaded!', 'success');
            }
        }

        function deleteImage() {
            if (!currentFilename) return;
            if (!confirm('Are you sure?')) return;
            fetch('/api/delete/' + currentFilename, { method: 'DELETE' })
                .then(res => res.json())
                .then(data => {
                    if (data.success) {
                        showToast('Image deleted!', 'success');
                        document.getElementById('resultBox').style.display = 'none';
                        document.getElementById('fileInput').value = '';
                        currentFile = null;
                        document.getElementById('uploadBtn').style.display = 'none';
                    } else {
                        showToast('Delete failed!', 'error');
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

        const dropArea = document.querySelector('.upload-area');
        dropArea.addEventListener('dragover', (e) => { e.preventDefault(); dropArea.style.borderColor = '#764ba2'; });
        dropArea.addEventListener('dragleave', () => { dropArea.style.borderColor = 'rgba(102,126,234,0.3)'; });
        dropArea.addEventListener('drop', (e) => {
            e.preventDefault();
            dropArea.style.borderColor = 'rgba(102,126,234,0.3)';
            if (e.dataTransfer.files.length > 0) handleFile(e.dataTransfer.files[0]);
        });
    </script>
</body>
</html>
'''

# ============ MULTIPLE UPLOAD TEMPLATE (app1.py style) ============
MULTIPLE_UPLOAD_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Multiple Upload - TORIKUL SYSTEM</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
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
            border: 3px dashed rgba(102,126,234,0.3);
            border-radius: 20px;
            padding: 50px 20px;
            text-align: center;
            background: rgba(255,255,255,0.02);
            cursor: pointer;
            transition: all 0.3s;
        }
        .upload-area:hover { border-color: #667eea; background: rgba(102,126,234,0.05); }
        .upload-area .icon { font-size: 3.5em; margin-bottom: 15px; }
        .upload-area .text { font-size: 1.1em; color: rgba(255,255,255,0.6); }
        .upload-area .sub { color: rgba(255,255,255,0.3); font-size: 0.9em; margin-top: 5px; }
        #fileInput { display: none; }
        .selected-files { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 15px; }
        .file-tag {
            background: rgba(102,126,234,0.2);
            padding: 5px 15px; border-radius: 20px;
            font-size: 0.85em; display: flex; align-items: center; gap: 8px;
        }
        .file-tag .remove { cursor: pointer; color: #ff6b6b; font-weight: bold; }
        .group-input {
            margin-top: 20px;
            padding: 20px;
            background: rgba(255,255,255,0.04);
            border-radius: 12px;
            border: 1px solid rgba(255,255,255,0.06);
        }
        .group-input label { display: block; color: rgba(255,255,255,0.7); margin-bottom: 8px; font-weight: 500; }
        .group-input input {
            width: 100%; padding: 12px 16px;
            background: rgba(255,255,255,0.06);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 10px;
            color: #fff; font-size: 1em;
            transition: all 0.3s; outline: none;
        }
        .group-input input:focus { border-color: #667eea; background: rgba(255,255,255,0.08); }
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
        .btn-primary:hover { transform: scale(1.05); box-shadow: 0 10px 30px rgba(102,126,234,0.3); }
        .btn-success { background: linear-gradient(135deg, #51cf66, #40c057); }
        .btn-success:hover { transform: scale(1.05); }
        .btn-danger { background: linear-gradient(135deg, #ff6b6b, #e03131); }
        .btn-danger:hover { transform: scale(1.05); }
        .btn-secondary { background: rgba(255,255,255,0.1); }
        .btn-secondary:hover { background: rgba(255,255,255,0.2); }
        .result-box {
            display: none; margin-top: 30px;
            background: rgba(255,255,255,0.04);
            border: 1px solid rgba(255,255,255,0.06);
            border-radius: 20px; padding: 30px;
        }
        .result-box .group-info { margin-bottom: 20px; }
        .result-box .group-info .label { color: rgba(255,255,255,0.5); }
        .result-box .group-info .value { color: #667eea; word-break: break-all; }
        .gallery-preview {
            display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
            gap: 15px; margin: 20px 0;
        }
        .gallery-preview .thumb {
            background: rgba(255,255,255,0.03);
            border-radius: 10px; overflow: hidden;
        }
        .gallery-preview .thumb img { width: 100%; height: 150px; object-fit: cover; }
        .gallery-preview .thumb .name { padding: 8px; font-size: 0.75em; color: rgba(255,255,255,0.6); text-align: center; }
        .btn-group { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 15px; }
        .qr-container { text-align: center; padding: 15px; background: #fff; border-radius: 12px; display: inline-block; margin-top: 15px; }
        .qr-container img { max-width: 200px; }
        .loading {
            display: none; text-align: center; padding: 30px;
        }
        .spinner {
            border: 4px solid rgba(255,255,255,0.1);
            border-top: 4px solid #667eea;
            border-radius: 50%;
            width: 40px; height: 40px;
            animation: spin 1s linear infinite;
            margin: 0 auto;
        }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        .toast-container {
            position: fixed; bottom: 30px; right: 30px;
            z-index: 999; display: flex; flex-direction: column; gap: 10px;
        }
        .toast {
            padding: 14px 24px; border-radius: 12px;
            background: rgba(20,20,40,0.95); backdrop-filter: blur(10px);
            border: 1px solid rgba(255,255,255,0.1);
            color: #fff; font-size: 0.95em;
            animation: slideIn 0.3s ease-out;
        }
        .toast.success { border-left: 4px solid #51cf66; }
        .toast.error { border-left: 4px solid #ff6b6b; }
        @keyframes slideIn { from { transform: translateX(100px); opacity: 0; } to { transform: translateX(0); opacity: 1; } }
        @media (max-width: 600px) {
            .container { padding: 15px; }
            .header h1 { font-size: 1.3em; }
            .upload-area { padding: 30px 15px; }
            .result-box { padding: 20px; }
            .gallery-preview { grid-template-columns: repeat(auto-fill, minmax(120px, 1fr)); }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📸📸 Multiple Upload</h1>
            <a href="/dashboard" class="btn-back">🏠 Dashboard</a>
        </div>
        <div class="upload-area" onclick="document.getElementById('fileInput').click()">
            <div class="icon">📸</div>
            <div class="text">Click to select multiple images</div>
            <div class="sub">or drag & drop here</div>
            <input type="file" id="fileInput" accept="image/*" multiple onchange="handleFiles(this.files)">
        </div>
        <div class="selected-files" id="selectedFiles"></div>
        <div class="group-input">
            <label>Group Name</label>
            <input type="text" id="groupName" placeholder="Enter group name" value="Image_Group_{{ now.strftime('%Y%m%d_%H%M%S') }}">
        </div>
        <div style="margin-top:15px;display:flex;gap:10px;flex-wrap:wrap;">
            <button class="btn btn-primary" onclick="uploadFiles()" id="uploadBtn">Create Group</button>
            <button class="btn btn-secondary" onclick="clearFiles()">Clear All</button>
        </div>
        <div class="loading" id="loading"><div class="spinner"></div><p style="margin-top:15px;">Uploading...</p></div>
        <div class="result-box" id="resultBox">
            <div class="group-info">
                <div><span class="label">Group Name:</span> <span class="value" id="groupNameDisplay">-</span></div>
                <div><span class="label">Images:</span> <span class="value" id="imageCount">-</span></div>
                <div><span class="label">Group URL:</span> <span class="value" id="groupUrl">-</span></div>
            </div>
            <div class="gallery-preview" id="galleryPreview"></div>
            <div class="btn-group">
                <button class="btn btn-primary" onclick="copyGroupLink()">📋 Copy Group Link</button>
                <button class="btn btn-success" onclick="downloadGroupQR()">⬇️ Download QR</button>
                <button class="btn btn-danger" onclick="deleteGroup()">🗑️ Delete Group</button>
                <button class="btn btn-secondary" onclick="location.reload()">➕ Add More</button>
            </div>
            <div style="text-align:center;">
                <div class="qr-container"><img id="groupQrImg" alt="Group QR Code"></div>
            </div>
        </div>
        <div style="margin-top:30px;text-align:center;color:rgba(255,255,255,0.2);font-size:0.8em;">
            Created by TORIKUL
        </div>
    </div>
    <div class="toast-container" id="toastContainer"></div>
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
            btn.textContent = selectedFiles.length > 0 ? `Create Group (${selectedFiles.length} images)` : 'Create Group';
            btn.disabled = selectedFiles.length === 0;
        }

        function uploadFiles() {
            if (selectedFiles.length === 0) return;
            const groupName = document.getElementById('groupName').value.trim();
            if (!groupName) {
                showToast('Please enter a group name!', 'error');
                return;
            }
            document.getElementById('loading').style.display = 'block';
            document.getElementById('resultBox').style.display = 'none';
            const formData = new FormData();
            for (let file of selectedFiles) formData.append('photos', file);
            formData.append('group_name', groupName);

            fetch('/api/multiple-upload', {
                method: 'POST',
                body: formData
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    currentGroupId = data.group_id;
                    currentGroupUrl = data.group_url;
                    document.getElementById('groupNameDisplay').textContent = data.group_name;
                    document.getElementById('imageCount').textContent = data.count + ' images';
                    document.getElementById('groupUrl').textContent = data.group_url;
                    const preview = document.getElementById('galleryPreview');
                    preview.innerHTML = '';
                    data.files.forEach(img => {
                        const div = document.createElement('div');
                        div.className = 'thumb';
                        div.innerHTML = `<img src="${img.url}" alt="${img.original_name}"><div class="name">${img.original_name.substring(0, 20)}</div>`;
                        preview.appendChild(div);
                    });
                    document.getElementById('groupQrImg').src = 'data:image/png;base64,' + data.group_qr;
                    document.getElementById('resultBox').style.display = 'block';
                    document.getElementById('loading').style.display = 'none';
                    selectedFiles = [];
                    document.getElementById('selectedFiles').innerHTML = '';
                    updateUploadBtn();
                    showToast('Group created with ' + data.count + ' images!', 'success');
                }
            })
            .catch(err => {
                document.getElementById('loading').style.display = 'none';
                showToast('Upload failed!', 'error');
            });
        }

        function copyGroupLink() {
            const url = document.getElementById('groupUrl').textContent;
            navigator.clipboard.writeText(url).then(() => {
                showToast('Group link copied!', 'success');
            }).catch(() => { prompt('Copy this link:', url); });
        }

        function downloadGroupQR() {
            const img = document.getElementById('groupQrImg');
            if (img.src) {
                const link = document.createElement('a');
                link.download = 'group_qr_' + currentGroupId + '.png';
                link.href = img.src;
                link.click();
                showToast('QR Code downloaded!', 'success');
            }
        }

        function deleteGroup() {
            if (!currentGroupId) return;
            if (!confirm('Are you sure?')) return;
            fetch('/api/delete-group/' + currentGroupId, { method: 'DELETE' })
                .then(res => res.json())
                .then(data => {
                    if (data.success) {
                        showToast('Group deleted!', 'success');
                        document.getElementById('resultBox').style.display = 'none';
                    } else {
                        showToast('Delete failed!', 'error');
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

        const dropArea = document.querySelector('.upload-area');
        dropArea.addEventListener('dragover', (e) => { e.preventDefault(); dropArea.style.borderColor = '#764ba2'; });
        dropArea.addEventListener('dragleave', () => { dropArea.style.borderColor = 'rgba(102,126,234,0.3)'; });
        dropArea.addEventListener('drop', (e) => {
            e.preventDefault();
            dropArea.style.borderColor = 'rgba(102,126,234,0.3)';
            handleFiles(e.dataTransfer.files);
        });
    </script>
</body>
</html>
'''

# ============ GALLERY TEMPLATE (app1.py style) ============
GALLERY_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Gallery - TORIKUL SYSTEM</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
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
            display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
            gap: 25px;
        }
        .image-card {
            background: rgba(255,255,255,0.04);
            border: 1px solid rgba(255,255,255,0.06);
            border-radius: 16px;
            overflow: hidden;
            transition: all 0.3s;
        }
        .image-card:hover { transform: translateY(-5px); background: rgba(255,255,255,0.06); }
        .image-card .img-wrap { height: 220px; overflow: hidden; cursor: pointer; }
        .image-card .img-wrap img { width: 100%; height: 100%; object-fit: cover; transition: transform 0.3s; }
        .image-card:hover .img-wrap img { transform: scale(1.05); }
        .image-card .info { padding: 15px; }
        .image-card .info .name { font-weight: 500; word-break: break-all; font-size: 0.9em; }
        .image-card .info .meta { color: rgba(255,255,255,0.4); font-size: 0.8em; margin: 5px 0; }
        .image-card .info .url { color: #667eea; font-size: 0.75em; word-break: break-all; cursor: pointer; }
        .btn {
            padding: 6px 14px; border: none; border-radius: 8px;
            font-size: 0.8em; cursor: pointer; transition: all 0.3s;
            color: #fff;
        }
        .btn-primary { background: linear-gradient(135deg, #667eea, #764ba2); }
        .btn-primary:hover { transform: scale(1.05); }
        .btn-success { background: linear-gradient(135deg, #51cf66, #40c057); }
        .btn-success:hover { transform: scale(1.05); }
        .btn-danger { background: linear-gradient(135deg, #ff6b6b, #e03131); }
        .btn-danger:hover { transform: scale(1.05); }
        .btn-group { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; }
        .empty-state { text-align: center; padding: 80px 20px; }
        .empty-state .icon { font-size: 4em; margin-bottom: 15px; }
        .empty-state h2 { margin-bottom: 10px; }
        .empty-state p { color: rgba(255,255,255,0.4); }
        .toast-container {
            position: fixed; bottom: 30px; right: 30px;
            z-index: 999; display: flex; flex-direction: column; gap: 10px;
        }
        .toast {
            padding: 14px 24px; border-radius: 12px;
            background: rgba(20,20,40,0.95); backdrop-filter: blur(10px);
            border: 1px solid rgba(255,255,255,0.1);
            color: #fff; font-size: 0.95em;
            animation: slideIn 0.3s ease-out;
        }
        .toast.success { border-left: 4px solid #51cf66; }
        .toast.error { border-left: 4px solid #ff6b6b; }
        @keyframes slideIn { from { transform: translateX(100px); opacity: 0; } to { transform: translateX(0); opacity: 1; } }
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
            <h1>🖼️ My Images</h1>
            <div>
                <a href="/upload" class="btn-back" style="margin-right:10px;">📸 Upload</a>
                <a href="/dashboard" class="btn-back">🏠 Dashboard</a>
            </div>
        </div>
        {% if images %}
        <div class="gallery-grid">
            {% for img in images %}
            <div class="image-card" data-filename="{{ img.filename }}">
                <div class="img-wrap" onclick="location.href='/image/{{ img.filename }}'">
                    <img src="{{ img.url }}" alt="{{ img.filename }}" loading="lazy">
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
            <a href="/upload" class="btn btn-primary" style="display:inline-block;margin-top:20px;padding:12px 30px;font-size:1em;text-decoration:none;background:linear-gradient(135deg,#667eea,#764ba2);border-radius:10px;color:#fff;">📸 Upload Image</a>
        </div>
        {% endif %}
        <div style="margin-top:30px;text-align:center;color:rgba(255,255,255,0.2);font-size:0.8em;">
            Created by TORIKUL | Total: {{ images|length }} images
        </div>
    </div>
    <div class="toast-container" id="toastContainer"></div>
    <script>
        function copyToClipboard(text) {
            navigator.clipboard.writeText(text).then(() => {
                showToast('Link copied!', 'success');
            }).catch(() => { prompt('Copy this link:', text); });
        }

        function downloadQR(filename) {
            fetch('/api/qr/' + filename)
                .then(res => res.json())
                .then(data => {
                    const link = document.createElement('a');
                    link.download = 'qr_' + filename + '.png';
                    link.href = 'data:image/png;base64,' + data.qr;
                    link.click();
                    showToast('QR Code downloaded!', 'success');
                });
        }

        function deleteImage(filename) {
            if (!confirm('Are you sure?')) return;
            fetch('/api/delete/' + filename, { method: 'DELETE' })
                .then(res => res.json())
                .then(data => {
                    if (data.success) {
                        showToast('Image deleted!', 'success');
                        const card = document.querySelector(`.image-card[data-filename="${filename}"]`);
                        if (card) card.remove();
                    } else {
                        showToast('Delete failed!', 'error');
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
    </script>
</body>
</html>
'''

# ============ GROUPS TEMPLATE (app1.py style) ============
GROUPS_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Groups - TORIKUL SYSTEM</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
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
            display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
            gap: 25px;
        }
        .group-card {
            background: rgba(255,255,255,0.04);
            border: 1px solid rgba(255,255,255,0.06);
            border-radius: 16px;
            overflow: hidden;
            transition: all 0.3s;
        }
        .group-card:hover { transform: translateY(-5px); background: rgba(255,255,255,0.06); }
        .group-card .thumb-grid {
            display: grid; grid-template-columns: repeat(3, 1fr);
            gap: 2px; height: 150px; cursor: pointer;
        }
        .group-card .thumb-grid img { width: 100%; height: 100%; object-fit: cover; }
        .group-card .thumb-grid .more { display: flex; justify-content: center; align-items: center; background: rgba(102,126,234,0.2); font-size: 1.2em; }
        .group-card .info { padding: 15px; }
        .group-card .info .name { font-weight: 600; font-size: 1.1em; }
        .group-card .info .meta { color: rgba(255,255,255,0.4); font-size: 0.85em; margin: 5px 0; }
        .group-card .info .url { color: #667eea; font-size: 0.75em; word-break: break-all; cursor: pointer; }
        .btn {
            padding: 6px 14px; border: none; border-radius: 8px;
            font-size: 0.8em; cursor: pointer; transition: all 0.3s;
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
        .btn-group { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; }
        .empty-state { text-align: center; padding: 80px 20px; }
        .empty-state .icon { font-size: 4em; margin-bottom: 15px; }
        .empty-state h2 { margin-bottom: 10px; }
        .empty-state p { color: rgba(255,255,255,0.4); }
        .toast-container {
            position: fixed; bottom: 30px; right: 30px;
            z-index: 999; display: flex; flex-direction: column; gap: 10px;
        }
        .toast {
            padding: 14px 24px; border-radius: 12px;
            background: rgba(20,20,40,0.95); backdrop-filter: blur(10px);
            border: 1px solid rgba(255,255,255,0.1);
            color: #fff; font-size: 0.95em;
            animation: slideIn 0.3s ease-out;
        }
        .toast.success { border-left: 4px solid #51cf66; }
        .toast.error { border-left: 4px solid #ff6b6b; }
        @keyframes slideIn { from { transform: translateX(100px); opacity: 0; } to { transform: translateX(0); opacity: 1; } }
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
            <h1>📁 Image Groups</h1>
            <div>
                <a href="/multiple-upload" class="btn-back" style="margin-right:10px;">📸 New Group</a>
                <a href="/dashboard" class="btn-back">🏠 Dashboard</a>
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
                    <div class="url" onclick="copyToClipboard('{{ group.url }}')">🔗 {{ group.url }}</div>
                    <div class="btn-group">
                        <button class="btn btn-primary" onclick="copyToClipboard('{{ group.url }}')">📋 Copy</button>
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
            <a href="/multiple-upload" class="btn btn-primary" style="display:inline-block;margin-top:20px;padding:12px 30px;font-size:1em;text-decoration:none;background:linear-gradient(135deg,#667eea,#764ba2);border-radius:10px;color:#fff;">📸 Create Group</a>
        </div>
        {% endif %}
        <div style="margin-top:30px;text-align:center;color:rgba(255,255,255,0.2);font-size:0.8em;">
            Created by TORIKUL | Total: {{ groups|length }} groups
        </div>
    </div>
    <div class="toast-container" id="toastContainer"></div>
    <script>
        function copyToClipboard(text) {
            navigator.clipboard.writeText(text).then(() => {
                showToast('Link copied!', 'success');
            }).catch(() => { prompt('Copy this link:', text); });
        }

        function downloadGroupQR(groupId) {
            fetch('/api/qr-group/' + groupId)
                .then(res => res.json())
                .then(data => {
                    const link = document.createElement('a');
                    link.download = 'group_qr_' + groupId + '.png';
                    link.href = 'data:image/png;base64,' + data.qr;
                    link.click();
                    showToast('QR Code downloaded!', 'success');
                });
        }

        function deleteGroup(groupId) {
            if (!confirm('Are you sure?')) return;
            fetch('/api/delete-group/' + groupId, { method: 'DELETE' })
                .then(res => res.json())
                .then(data => {
                    if (data.success) {
                        showToast('Group deleted!', 'success');
                        const card = document.querySelector(`.group-card[data-groupid="${groupId}"]`);
                        if (card) card.remove();
                    } else {
                        showToast('Delete failed!', 'error');
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
    </script>
</body>
</html>
'''

# ============ LINK_GROUPS_TEMPLATE (app1.py style) ============
LINK_GROUPS_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Link Groups - TORIKUL SYSTEM</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
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
            display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
            gap: 25px;
        }
        .group-card {
            background: rgba(255,255,255,0.04);
            border: 1px solid rgba(255,255,255,0.06);
            border-radius: 16px;
            overflow: hidden;
            transition: all 0.3s;
            padding: 20px;
            cursor: pointer;
        }
        .group-card:hover { transform: translateY(-5px); background: rgba(255,255,255,0.06); }
        .group-card .name { font-weight: 600; font-size: 1.1em; }
        .group-card .meta { color: rgba(255,255,255,0.4); font-size: 0.85em; margin: 5px 0; }
        .group-card .url { color: #667eea; font-size: 0.75em; word-break: break-all; cursor: pointer; }
        .group-card .links-preview {
            margin: 10px 0; padding: 10px;
            background: rgba(255,255,255,0.03);
            border-radius: 8px;
            max-height: 120px; overflow-y: auto;
        }
        .group-card .links-preview .link-item {
            font-size: 0.8em; color: rgba(255,255,255,0.6);
            padding: 3px 0;
            border-bottom: 1px solid rgba(255,255,255,0.03);
            word-break: break-all;
        }
        .btn {
            padding: 6px 14px; border: none; border-radius: 8px;
            font-size: 0.8em; cursor: pointer; transition: all 0.3s;
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
        .btn-group { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; }
        .empty-state { text-align: center; padding: 80px 20px; }
        .empty-state .icon { font-size: 4em; margin-bottom: 15px; }
        .empty-state h2 { margin-bottom: 10px; }
        .empty-state p { color: rgba(255,255,255,0.4); }
        .toast-container {
            position: fixed; bottom: 30px; right: 30px;
            z-index: 999; display: flex; flex-direction: column; gap: 10px;
        }
        .toast {
            padding: 14px 24px; border-radius: 12px;
            background: rgba(20,20,40,0.95); backdrop-filter: blur(10px);
            border: 1px solid rgba(255,255,255,0.1);
            color: #fff; font-size: 0.95em;
            animation: slideIn 0.3s ease-out;
        }
        .toast.success { border-left: 4px solid #51cf66; }
        .toast.error { border-left: 4px solid #ff6b6b; }
        @keyframes slideIn { from { transform: translateX(100px); opacity: 0; } to { transform: translateX(0); opacity: 1; } }
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
            <h1>📁🔗 Link Groups</h1>
            <div>
                <a href="/multiple-links-to-qr" class="btn-back" style="margin-right:10px;">🔗 New Group</a>
                <a href="/dashboard" class="btn-back">🏠 Dashboard</a>
            </div>
        </div>
        {% if groups %}
        <div class="groups-grid">
            {% for gid, group in groups.items() %}
            <div class="group-card" data-groupid="{{ gid }}" onclick="window.open('{{ group.url }}', '_blank')">
                <div class="name">📁🔗 {{ group.name }}</div>
                <div class="meta">🔗 {{ group.link_count }} links | 🕒 {{ group.created_at }}</div>
                <div class="url" onclick="event.stopPropagation();copyToClipboard('{{ group.url }}')">🔗 {{ group.url }}</div>
                <div class="links-preview">
                    {% for link in group.links[:5] %}
                    <div class="link-item">🔗 {{ link.url }}</div>
                    {% endfor %}
                    {% if group.links|length > 5 %}
                    <div class="link-item" style="color:rgba(255,255,255,0.3);">... and {{ group.links|length - 5 }} more</div>
                    {% endif %}
                </div>
                <div class="btn-group" onclick="event.stopPropagation();">
                    <button class="btn btn-primary" onclick="copyToClipboard('{{ group.url }}')">📋 Copy</button>
                    <button class="btn btn-success" onclick="downloadGroupQR('{{ gid }}')">🧾 QR</button>
                    <button class="btn btn-secondary" onclick="window.open('{{ group.url }}', '_blank')">👁️ View</button>
                    <button class="btn btn-danger" onclick="deleteLinkGroup('{{ gid }}')">🗑️ Delete</button>
                </div>
            </div>
            {% endfor %}
        </div>
        {% else %}
        <div class="empty-state">
            <div class="icon">📭</div>
            <h2>No Link Groups Yet</h2>
            <p>Create your first link group by adding multiple URLs!</p>
            <a href="/multiple-links-to-qr" class="btn btn-primary" style="display:inline-block;margin-top:20px;padding:12px 30px;font-size:1em;text-decoration:none;background:linear-gradient(135deg,#667eea,#764ba2);border-radius:10px;color:#fff;">🔗 Create Group</a>
        </div>
        {% endif %}
        <div style="margin-top:30px;text-align:center;color:rgba(255,255,255,0.2);font-size:0.8em;">
            Created by TORIKUL | Total: {{ groups|length }} groups
        </div>
    </div>
    <div class="toast-container" id="toastContainer"></div>
    <script>
        function copyToClipboard(text) {
            navigator.clipboard.writeText(text).then(() => {
                showToast('Link copied!', 'success');
            }).catch(() => { prompt('Copy this link:', text); });
        }

        function downloadGroupQR(groupId) {
            fetch('/api/qr-link-group/' + groupId)
                .then(res => res.json())
                .then(data => {
                    const link = document.createElement('a');
                    link.download = 'group_qr_' + groupId + '.png';
                    link.href = 'data:image/png;base64,' + data.qr;
                    link.click();
                    showToast('QR Code downloaded!', 'success');
                });
        }

        function deleteLinkGroup(groupId) {
            if (!confirm('Are you sure?')) return;
            fetch('/api/delete-link-group/' + groupId, { method: 'DELETE' })
                .then(res => res.json())
                .then(data => {
                    if (data.success) {
                        showToast('Group deleted!', 'success');
                        const card = document.querySelector(`.group-card[data-groupid="${groupId}"]`);
                        if (card) card.remove();
                    } else {
                        showToast('Delete failed!', 'error');
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
    images = get_images_from_db()
    groups = get_groups_from_db()
    links = get_links_from_db()
    link_groups = get_link_groups_from_db()
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
    return render_template_string(MULTIPLE_UPLOAD_TEMPLATE, now=datetime.now())

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
                'upload_date': data.get('upload_date', 'Unknown')[:10] if data.get('upload_date') else 'Unknown',
                'link_id': data.get('link_id')
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

@app.route('/group/<group_id>')
@login_required
def view_group(group_id):
    groups_data = get_groups_from_db()
    if group_id not in groups_data:
        return "Group not found", 404
    group = groups_data[group_id]
    return render_template_string(GROUP_VIEW_TEMPLATE, group=group)

@app.route('/link-group/<group_id>')
@login_required
def view_link_group(group_id):
    link_groups_data = get_link_groups_from_db()
    if group_id not in link_groups_data:
        return "Link Group not found", 404
    group = link_groups_data[group_id]
    return render_template_string(LINK_GROUP_VIEW_TEMPLATE, group=group)

# ============ PUBLIC VIEWS (No Login) ============
@app.route('/view-group/<group_id>')
def view_group_public(group_id):
    groups_data = get_groups_from_db()
    if group_id not in groups_data:
        return "Group not found", 404
    group = groups_data[group_id]
    return render_template_string(PUBLIC_GROUP_VIEW_TEMPLATE, group=group)

# ============ API ROUTES ============
@app.route('/api/upload-with-group', methods=['POST'])
@login_required
def api_upload_with_group():
    if 'photos' not in request.files:
        return jsonify({'error': 'No files uploaded'}), 400
    files = request.files.getlist('photos')
    group_name = request.form.get('group_name', '').strip()
    uploaded_files = []
    group_id = None
    group_url = None
    for file in files:
        if file and file.filename != '' and allowed_file(file.filename):
            ext = file.filename.rsplit('.', 1)[1].lower()
            unique_id = generate_unique_id()
            unique_name = f"{unique_id}.{ext}"
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_name)
            file.save(file_path)
            cloudinary_url = upload_to_cloudinary(file_path, unique_name)
            if cloudinary_url:
                file_size = get_file_size(file_path)
                link_id = generate_unique_id()
                full_url = BASE_URL + '/view/image/' + unique_name + '?link=' + link_id
                qr_base64 = generate_qr_code_base64(full_url)
                if group_name:
                    groups_data = get_groups_from_db()
                    existing_group = None
                    for gid, g in groups_data.items():
                        if g['name'].lower() == group_name.lower():
                            existing_group = gid
                            break
                    if existing_group:
                        group_id = existing_group
                        group_url = groups_data[existing_group]['url']
                    else:
                        group_id = generate_unique_id()
                        group_url = BASE_URL + '/view/group/' + group_id
                        save_group_to_db(group_id, group_name, group_url, 0, [])
                save_image_to_db(
                    filename=unique_name,
                    original_name=file.filename,
                    url=cloudinary_url,
                    size=file_size,
                    file_type=ext.upper(),
                    group_id=group_id,
                    link_id=link_id
                )
                save_link_to_db(link_id, full_url, qr_base64, image_id=unique_name, link_type='image')
                if group_id:
                    image_data = {
                        'original_name': file.filename,
                        'url': cloudinary_url,
                        'size': file_size,
                        'type': ext.upper(),
                        'filename': unique_name,
                        'link_id': link_id,
                        'link_url': full_url,
                        'qr': qr_base64
                    }
                    add_image_to_group_db(group_id, image_data)
                uploaded_files.append({
                    'original_name': file.filename,
                    'url': cloudinary_url,
                    'size': file_size,
                    'type': ext.upper(),
                    'filename': unique_name,
                    'link_id': link_id,
                    'link_url': full_url,
                    'qr': qr_base64
                })
                if os.path.exists(file_path):
                    os.remove(file_path)
    return jsonify({
        'success': True,
        'files': uploaded_files,
        'group_id': group_id,
        'group_name': group_name,
        'group_url': group_url
    })

@app.route('/api/multiple-upload', methods=['POST'])
@login_required
def api_multiple_upload():
    if 'photos' not in request.files:
        return jsonify({'error': 'No files uploaded'}), 400
    files = request.files.getlist('photos')
    if not files or files[0].filename == '':
        return jsonify({'error': 'No files selected'}), 400
    group_name = request.form.get('group_name', '').strip()
    if not group_name:
        group_name = f"Image_Group_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    group_id = generate_unique_id()
    uploaded_files = []
    for file in files:
        if file and file.filename != '' and allowed_file(file.filename):
            ext = file.filename.rsplit('.', 1)[1].lower()
            unique_id = generate_unique_id()
            unique_name = f"{unique_id}.{ext}"
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_name)
            file.save(file_path)
            cloudinary_url = upload_to_cloudinary(file_path, unique_name)
            if cloudinary_url:
                file_size = get_file_size(file_path)
                link_id = generate_unique_id()
                full_url = BASE_URL + '/view/image/' + unique_name + '?link=' + link_id
                qr_base64 = generate_qr_code_base64(full_url)
                save_image_to_db(
                    filename=unique_name,
                    original_name=file.filename,
                    url=cloudinary_url,
                    size=file_size,
                    file_type=ext.upper(),
                    group_id=group_id,
                    link_id=link_id
                )
                save_link_to_db(link_id, full_url, qr_base64, image_id=unique_name, link_type='image')
                uploaded_files.append({
                    'original_name': file.filename,
                    'url': cloudinary_url,
                    'size': file_size,
                    'type': ext.upper(),
                    'filename': unique_name,
                    'link_id': link_id,
                    'link_url': full_url,
                    'qr': qr_base64
                })
                if os.path.exists(file_path):
                    os.remove(file_path)
    if uploaded_files:
        group_url = BASE_URL + '/view/group/' + group_id
        group_qr = generate_qr_code_base64(group_url)
        save_group_to_db(
            group_id=group_id,
            name=group_name,
            url=group_url,
            image_count=len(uploaded_files),
            images=uploaded_files
        )
        save_link_to_db(group_id, group_url, group_qr, group_id=group_id, link_type='group')
        return jsonify({
            'success': True,
            'group_id': group_id,
            'group_url': group_url,
            'group_qr': group_qr,
            'group_name': group_name,
            'files': uploaded_files,
            'count': len(uploaded_files)
        })
    return jsonify({'success': False, 'error': 'No files uploaded successfully'}), 400

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
    save_link_to_db(link_id=link_id, url=url, qr=qr_base64, link_type='custom')
    return jsonify({'success': True, 'link_id': link_id, 'url': url, 'qr': qr_base64})

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
        save_link_to_db(
            link_id=link_id,
            url=url,
            qr=qr_base64,
            group_id=group_id,
            link_type='link_group'
        )
        processed_links.append({
            'link_id': link_id,
            'url': url,
            'qr': qr_base64
        })
    if processed_links:
        group_url = BASE_URL + '/view/link-group/' + group_id
        group_qr = generate_qr_code_base64(group_url)
        save_link_group_to_db(
            group_id=group_id,
            name=group_name,
            url=group_url,
            link_count=len(processed_links),
            links=processed_links
        )
        save_link_to_db(group_id, group_url, group_qr, group_id=group_id, link_type='link_group')
        return jsonify({
            'success': True,
            'group_id': group_id,
            'group_url': group_url,
            'group_qr': group_qr,
            'group_name': group_name,
            'links': processed_links,
            'count': len(processed_links)
        })
    return jsonify({'success': False, 'error': 'No links processed successfully'}), 400

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
@login_required
def generate_qr(filename):
    images_data = get_images_from_db()
    if filename not in images_data:
        return jsonify({'error': 'Image not found'}), 404
    url = images_data[filename]['url']
    qr_base64 = generate_qr_code_base64(url)
    return jsonify({'qr': qr_base64})

@app.route('/api/qr-group/<group_id>')
@login_required
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
@login_required
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
        try:
            public_id = filename.replace('.', '_')
            cloudinary.uploader.destroy(f"torikul_images/{public_id}")
        except Exception as e:
            print(f"Cloudinary delete error: {e}")
        delete_image_from_db(filename)
        if group_id:
            groups_data = get_groups_from_db()
            if group_id in groups_data:
                groups_data[group_id]['images'] = [img for img in groups_data[group_id]['images'] if img['filename'] != filename]
                groups_data[group_id]['image_count'] = len(groups_data[group_id]['images'])
                save_local_json(GROUPS_JSON, groups_data)
        return jsonify({'success': True})
    return jsonify({'success': False}), 404

@app.route('/api/delete-link/<link_id>', methods=['DELETE'])
@login_required
def delete_link(link_id):
    if delete_link_from_db(link_id):
        return jsonify({'success': True})
    return jsonify({'success': False}), 404

@app.route('/api/delete-group/<group_id>', methods=['DELETE'])
@login_required
def delete_group(group_id):
    groups_data = get_groups_from_db()
    if group_id not in groups_data:
        return jsonify({'success': False}), 404
    for img in groups_data[group_id].get('images', []):
        filename = img.get('filename')
        if filename:
            try:
                public_id = filename.replace('.', '_')
                cloudinary.uploader.destroy(f"torikul_images/{public_id}")
            except Exception as e:
                print(f"Cloudinary delete error: {e}")
    delete_group_from_db(group_id)
    return jsonify({'success': True})

@app.route('/api/delete-link-group/<group_id>', methods=['DELETE'])
@login_required
def delete_link_group(group_id):
    if delete_link_group_from_db(group_id):
        return jsonify({'success': True})
    return jsonify({'success': False}), 404

@app.route('/api/regenerate-link/<item_type>/<item_id>', methods=['POST'])
@login_required
def api_regenerate_link(item_type, item_id):
    result = regenerate_link_and_qr(item_type, item_id)
    if result:
        return jsonify({'success': True, 'link_id': result['link_id'], 'url': result['url'], 'qr': result['qr']})
    return jsonify({'success': False}), 400

# ============ MAIN ============
if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("🖼️ TORIKUL IMAGE • LINK • QR SYSTEM v7.1 (Design Updated)")
    print("=" * 60)
    print(f"🌐 Server: http://127.0.0.1:5000")
    print(f"🔑 Login: {ADMIN_USERNAME} / {ADMIN_PASSWORD}")
    print("=" * 60)
    print("✅ Cloudinary + Supabase + Local JSON Fallback")
    print("✅ Design: app1.py style (clean, minimal, English)")
    print("=" * 60)
    print("Press CTRL+C to stop\n")
    app.run(debug=True, host='0.0.0.0', port=5000)