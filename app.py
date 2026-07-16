import os
import uuid
import json
from datetime import datetime
from flask import Flask, render_template_string, request, send_from_directory, jsonify

app = Flask(__name__)

# Configure upload folder
UPLOAD_FOLDER = 'uploads'
JSON_FOLDER = 'json_data'

# Create folders if they don't exist
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
if not os.path.exists(JSON_FOLDER):
    os.makedirs(JSON_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['JSON_FOLDER'] = JSON_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max total file size

# Allowed image extensions
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp', 'svg', 'ico'}

def allowed_file(filename):
    """Check if file has an allowed extension"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_file_size(filepath):
    """Get file size in human readable format"""
    size_bytes = os.path.getsize(filepath)
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} GB"

# HTML Template
INDEX_TEMPLATE = '''
<!DOCTYPE html>
<html lang="bn">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>📸 Photo & JSON to URL Generator</title>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }

        .container {
            max-width: 1200px;
            margin: 0 auto;
        }

        .header {
            text-align: center;
            color: white;
            margin-bottom: 40px;
            padding: 20px;
            animation: slideDown 0.8s ease-out;
        }

        @keyframes slideDown {
            from {
                opacity: 0;
                transform: translateY(-50px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }

        .header h1 {
            font-size: 3.2em;
            margin-bottom: 10px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.2);
            background: linear-gradient(to right, #fff, #f0f0ff);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .header p {
            font-size: 1.2em;
            opacity: 0.95;
            color: #fff;
        }

        .top-nav {
            display: flex;
            justify-content: center;
            gap: 15px;
            margin-top: 20px;
            flex-wrap: wrap;
        }

        .top-nav .btn-nav {
            background: rgba(255, 255, 255, 0.2);
            backdrop-filter: blur(10px);
            color: white;
            border: 2px solid rgba(255, 255, 255, 0.3);
            padding: 12px 25px;
            border-radius: 50px;
            text-decoration: none;
            font-weight: 600;
            transition: all 0.3s;
            display: inline-flex;
            align-items: center;
            gap: 8px;
        }

        .top-nav .btn-nav:hover {
            background: rgba(255, 255, 255, 0.3);
            transform: translateY(-3px);
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        }

        .top-nav .btn-nav i {
            font-size: 1.2em;
        }

        .upload-card {
            background: white;
            border-radius: 20px;
            padding: 40px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            margin-bottom: 30px;
            transition: transform 0.3s, box-shadow 0.3s;
            animation: fadeInUp 0.6s ease-out;
        }

        @keyframes fadeInUp {
            from {
                opacity: 0;
                transform: translateY(30px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }

        .upload-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 25px 70px rgba(0,0,0,0.4);
        }

        .upload-area {
            border: 3px dashed #667eea;
            border-radius: 15px;
            padding: 60px 20px;
            text-align: center;
            background: #f8f9ff;
            cursor: pointer;
            transition: all 0.3s;
            position: relative;
        }

        .upload-area:hover {
            border-color: #764ba2;
            background: #f0f2ff;
            transform: scale(1.02);
        }

        .upload-area.dragover {
            border-color: #764ba2;
            background: #e8ebff;
            transform: scale(1.02);
        }

        .upload-icon {
            font-size: 4em;
            margin-bottom: 20px;
            color: #667eea;
            animation: bounce 2s infinite;
        }

        @keyframes bounce {
            0%, 20%, 50%, 80%, 100% {
                transform: translateY(0);
            }
            40% {
                transform: translateY(-20px);
            }
            60% {
                transform: translateY(-10px);
            }
        }

        .upload-text {
            font-size: 1.2em;
            color: #666;
            margin-bottom: 10px;
        }

        .upload-subtext {
            color: #999;
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
            text-decoration: none;
            display: inline-block;
            font-weight: 600;
            box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
        }

        .btn:hover {
            transform: translateY(-3px) scale(1.02);
            box-shadow: 0 8px 25px rgba(102, 126, 234, 0.6);
        }

        .btn-secondary {
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
            box-shadow: 0 4px 15px rgba(245, 87, 108, 0.4);
        }

        .btn-secondary:hover {
            box-shadow: 0 8px 25px rgba(245, 87, 108, 0.6);
        }

        .btn-success {
            background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
            box-shadow: 0 4px 15px rgba(79, 172, 254, 0.4);
        }

        .btn-success:hover {
            box-shadow: 0 8px 25px rgba(79, 172, 254, 0.6);
        }

        .btn-warning {
            background: linear-gradient(135deg, #f6d365 0%, #fda085 100%);
            box-shadow: 0 4px 15px rgba(253, 160, 133, 0.4);
        }

        .btn-warning:hover {
            box-shadow: 0 8px 25px rgba(253, 160, 133, 0.6);
        }

        .btn-danger {
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
            box-shadow: 0 4px 15px rgba(245, 87, 108, 0.4);
        }

        .btn-danger:hover {
            box-shadow: 0 8px 25px rgba(245, 87, 108, 0.6);
        }

        .btn-gallery {
            background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%);
            box-shadow: 0 4px 15px rgba(67, 233, 123, 0.4);
            color: #1a1a2e;
        }

        .btn-gallery:hover {
            box-shadow: 0 8px 25px rgba(67, 233, 123, 0.6);
        }

        .btn-json {
            background: linear-gradient(135deg, #a18cd1 0%, #fbc2eb 100%);
            box-shadow: 0 4px 15px rgba(161, 140, 209, 0.4);
            color: #1a1a2e;
        }

        .btn-json:hover {
            box-shadow: 0 8px 25px rgba(161, 140, 209, 0.6);
        }

        .preview-area {
            margin-top: 30px;
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
            gap: 20px;
        }

        .preview-card {
            background: white;
            border-radius: 15px;
            overflow: hidden;
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
            transition: all 0.3s;
            border: 1px solid #eee;
        }

        .preview-card:hover {
            transform: translateY(-8px);
            box-shadow: 0 15px 35px rgba(0,0,0,0.15);
        }

        .preview-image {
            width: 100%;
            height: 200px;
            object-fit: cover;
            transition: transform 0.3s;
        }

        .preview-card:hover .preview-image {
            transform: scale(1.05);
        }

        .preview-info {
            padding: 15px;
        }

        .preview-name {
            font-weight: bold;
            margin-bottom: 5px;
            color: #333;
            word-break: break-all;
            font-size: 0.95em;
        }

        .preview-size {
            color: #999;
            font-size: 0.9em;
            margin-bottom: 10px;
        }

        .url-link {
            background: #f0f0f0;
            padding: 8px;
            border-radius: 8px;
            font-size: 0.85em;
            word-break: break-all;
            margin: 10px 0;
            cursor: pointer;
            transition: background 0.3s;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        .url-link:hover {
            background: #e0e0e0;
        }

        .copy-btn {
            background: #667eea;
            color: white;
            border: none;
            padding: 5px 12px;
            border-radius: 5px;
            cursor: pointer;
            font-size: 0.85em;
            transition: all 0.3s;
        }

        .copy-btn:hover {
            background: #764ba2;
            transform: scale(1.05);
        }

        .result-card {
            background: white;
            border-radius: 20px;
            padding: 30px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            margin-top: 30px;
            animation: fadeInUp 0.8s ease-out;
        }

        .result-title {
            font-size: 1.5em;
            margin-bottom: 20px;
            color: #667eea;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .link-list {
            list-style: none;
        }

        .link-item {
            background: #f8f9ff;
            padding: 15px;
            margin-bottom: 10px;
            border-radius: 10px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 10px;
            transition: all 0.3s;
        }

        .link-item:hover {
            background: #f0f2ff;
            transform: translateX(5px);
        }

        .link-url {
            font-family: monospace;
            color: #667eea;
            word-break: break-all;
            flex: 1;
            margin-right: 10px;
            font-size: 0.9em;
        }

        .loading {
            text-align: center;
            padding: 20px;
            display: none;
        }

        .spinner {
            border: 4px solid #f3f3f3;
            border-top: 4px solid #667eea;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 0 auto;
        }

        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }

        .alert {
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 20px;
            display: flex;
            align-items: center;
            gap: 10px;
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 9999;
            max-width: 400px;
            box-shadow: 0 5px 20px rgba(0,0,0,0.2);
            animation: slideDown 0.5s ease-out;
        }

        .alert-success {
            background: #d4edda;
            color: #155724;
            border: 1px solid #c3e6cb;
        }

        .alert-error {
            background: #f8d7da;
            color: #721c24;
            border: 1px solid #f5c6cb;
        }

        .alert-info {
            background: #d1ecf1;
            color: #0c5460;
            border: 1px solid #bee5eb;
        }

        .nav-buttons {
            display: flex;
            justify-content: center;
            gap: 15px;
            margin-top: 20px;
            flex-wrap: wrap;
        }

        .text-area-container {
            margin-top: 20px;
            padding: 20px;
            background: #f8f9ff;
            border-radius: 10px;
            border: 2px solid #e0e0e0;
        }

        .text-area-container label {
            font-weight: 600;
            color: #333;
            display: block;
            margin-bottom: 8px;
        }

        .text-area-container textarea {
            width: 100%;
            padding: 12px;
            border: 2px solid #ddd;
            border-radius: 10px;
            font-size: 1em;
            resize: vertical;
            min-height: 80px;
            transition: border-color 0.3s;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }

        .text-area-container textarea:focus {
            outline: none;
            border-color: #667eea;
            box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
        }

        .text-area-container input[type="number"] {
            width: 100%;
            padding: 12px;
            border: 2px solid #ddd;
            border-radius: 10px;
            font-size: 1em;
            transition: border-color 0.3s;
            margin-top: 8px;
        }

        .text-area-container input[type="number"]:focus {
            outline: none;
            border-color: #667eea;
            box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
        }

        .json-output {
            margin-top: 15px;
            padding: 15px;
            background: #1e1e1e;
            border-radius: 10px;
            color: #d4d4d4;
            font-family: 'Courier New', monospace;
            font-size: 0.9em;
            overflow-x: auto;
            white-space: pre-wrap;
            word-break: break-all;
            max-height: 300px;
            overflow-y: auto;
        }

        .json-output .key {
            color: #9cdcfe;
        }
        .json-output .string {
            color: #ce9178;
        }
        .json-output .number {
            color: #b5cea8;
        }
        .json-output .bracket {
            color: #d4d4d4;
        }

        .copy-json-btn {
            margin-top: 10px;
        }

        .json-list {
            margin-top: 20px;
        }

        .json-item {
            background: #f8f9ff;
            padding: 15px;
            margin-bottom: 10px;
            border-radius: 10px;
            border-left: 4px solid #667eea;
        }

        .json-item .json-url {
            font-family: monospace;
            color: #667eea;
            word-break: break-all;
            margin: 5px 0;
        }

        .stats-bar {
            display: flex;
            justify-content: center;
            gap: 30px;
            flex-wrap: wrap;
            margin-top: 20px;
        }

        .stat-item {
            background: rgba(255, 255, 255, 0.15);
            padding: 10px 25px;
            border-radius: 50px;
            color: white;
            font-weight: 600;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.2);
        }

        .stat-item i {
            margin-right: 8px;
        }

        .vercel-badge {
            display: inline-block;
            background: #000;
            color: #fff;
            padding: 5px 15px;
            border-radius: 20px;
            font-size: 0.8em;
            margin-top: 10px;
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

            .link-item {
                flex-direction: column;
                align-items: stretch;
            }

            .link-url {
                margin-right: 0;
                margin-bottom: 8px;
            }

            .top-nav {
                flex-direction: column;
                align-items: center;
            }

            .top-nav .btn-nav {
                width: 100%;
                justify-content: center;
            }

            .stats-bar {
                flex-direction: column;
                align-items: center;
                gap: 10px;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📸 Photo & JSON to URL Generator</h1>
            <p>আপলোড করুন ছবি অথবা তৈরি করুন JSON, সাথে সাথে পেয়ে যান ইউনিক URL</p>
            
            <div class="vercel-badge">
                <i class="fas fa-cloud"></i> Vercel Ready
            </div>
            
            <div class="stats-bar">
                <div class="stat-item">
                    <i class="fas fa-images"></i> মোট ছবি: <span id="totalImages">0</span>
                </div>
                <div class="stat-item">
                    <i class="fas fa-code"></i> মোট JSON: <span id="totalJson">0</span>
                </div>
            </div>

            <div class="top-nav">
                <a href="/" class="btn-nav">
                    <i class="fas fa-home"></i> হোম
                </a>
                <a href="/gallery" class="btn-nav">
                    <i class="fas fa-images"></i> গ্যালারি দেখুন
                </a>
                <a href="/gallery#json-section" class="btn-nav">
                    <i class="fas fa-code"></i> JSON সমূহ
                </a>
                <a href="#" class="btn-nav" onclick="cleanupFiles(event)">
                    <i class="fas fa-broom"></i> ক্লিনআপ
                </a>
            </div>
        </div>

        <div class="upload-card">
            <div class="upload-area" id="dropZone" onclick="document.getElementById('fileInput').click()">
                <div class="upload-icon">📷</div>
                <div class="upload-text">ক্লিক করুন ছবি নির্বাচন করতে</div>
                <div class="upload-subtext">অথবা এখানে ড্র্যাগ করুন</div>
                <input type="file" id="fileInput" multiple accept="image/*" onchange="handleFiles(this.files)">
            </div>

            <!-- Text and Number Input Section -->
            <div class="text-area-container">
                <label for="customText">📝 আপনার টেক্সট লিখুন:</label>
                <textarea id="customText" placeholder="এখানে আপনার টেক্সট লিখুন..."></textarea>
                
                <label for="customNumber" style="margin-top: 12px;">🔢 সংখ্যা দিন:</label>
                <input type="number" id="customNumber" placeholder="যেমন: 100" step="any">
                
                <div style="margin-top: 15px; display: flex; gap: 10px; flex-wrap: wrap;">
                    <button class="btn btn-success" onclick="saveJson()">
                        <i class="fas fa-save"></i> JSON সংরক্ষণ করুন & URL তৈরি করুন
                    </button>
                    <button class="btn btn-warning" onclick="clearJson()">
                        <i class="fas fa-eraser"></i> ক্লিয়ার করুন
                    </button>
                    <button class="btn btn-json" onclick="window.location.href='/gallery#json-section'">
                        <i class="fas fa-list"></i> সব JSON দেখুন
                    </button>
                </div>

                <div id="jsonOutput" class="json-output" style="display: none;">
                    <span class="bracket">{</span><br>
                    <span class="key">  "message"</span><span class="bracket">:</span> <span class="string">"আপনাদের এই বট টি কেমন লাগল"</span><span class="bracket">,</span><br>
                    <span class="key">  "NUMBER"</span><span class="bracket">:</span> <span class="number">100</span><br>
                    <span class="bracket">}</span>
                </div>
                <button class="btn copy-json-btn" id="copyJsonBtn" onclick="copyJson()" style="display: none;">
                    <i class="fas fa-copy"></i> JSON কপি করুন
                </button>
            </div>

            <div id="loading" class="loading">
                <div class="spinner"></div>
                <p style="margin-top: 10px; color: #666;">আপলোড হচ্ছে...</p>
            </div>

            <div id="preview" class="preview-area"></div>
        </div>

        <div id="result" class="result-card" style="display: none;">
            <h3 class="result-title">✅ জেনারেটেড লিংকসমূহ</h3>
            <div id="linkList"></div>
            <div class="nav-buttons">
                <button class="btn btn-gallery" onclick="window.location.href='/gallery'">
                    <i class="fas fa-images"></i> 🎨 গ্যালারি দেখুন
                </button>
                <button class="btn btn-secondary" onclick="resetForm()">
                    <i class="fas fa-redo"></i> 🔄 নতুন করে শুরু করুন
                </button>
                <button class="btn btn-json" onclick="window.location.href='/gallery#json-section'">
                    <i class="fas fa-code"></i> 📄 JSON সমূহ দেখুন
                </button>
            </div>
        </div>

        <div id="jsonResult" class="result-card" style="display: none;">
            <h3 class="result-title">📄 সংরক্ষিত JSON সমূহ</h3>
            <div id="jsonList" class="json-list"></div>
            <div class="nav-buttons">
                <button class="btn btn-gallery" onclick="window.location.href='/gallery'">
                    <i class="fas fa-images"></i> সম্পূর্ণ গ্যালারি দেখুন
                </button>
                <button class="btn btn-secondary" onclick="resetForm()">
                    <i class="fas fa-redo"></i> নতুন JSON তৈরি করুন
                </button>
            </div>
        </div>
    </div>

    <script>
        let uploadedFiles = [];
        let savedJsonItems = [];

        async function handleFiles(files) {
            if (files.length === 0) return;
            
            const formData = new FormData();
            for (let file of files) {
                if (file.type.startsWith('image/')) {
                    formData.append('photos', file);
                }
            }
            
            document.getElementById('loading').style.display = 'block';
            
            try {
                const response = await fetch('/api/upload', {
                    method: 'POST',
                    body: formData
                });
                
                const data = await response.json();
                
                if (data.success) {
                    uploadedFiles = data.files;
                    displayPreview(data.files);
                    displayLinks(data.files);
                    document.getElementById('result').style.display = 'block';
                    
                    showAlert('success', '✅ ' + data.files.length + ' টি ছবি সফলভাবে আপলোড হয়েছে!');
                    updateStats();
                }
            } catch (error) {
                console.error('Error:', error);
                showAlert('error', '❌ আপলোড করতে সমস্যা হয়েছে!');
            } finally {
                document.getElementById('loading').style.display = 'none';
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
                        <div class="preview-name">📄 ${file.original_name.substring(0, 30)}${file.original_name.length > 30 ? '...' : ''}</div>
                        <div class="preview-size">📦 ${file.size}</div>
                        <div class="url-link" onclick="copyToClipboard('${file.url}')">
                            <span>🔗 ${file.url.substring(0, 40)}...</span>
                            <button class="copy-btn">📋 কপি</button>
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
                showAlert('success', '✅ কপি হয়েছে!');
            } catch (err) {
                prompt('ম্যানুয়ালি কপি করুন:', text);
            }
        }
        
        function showAlert(type, message) {
            const alertDiv = document.createElement('div');
            alertDiv.className = `alert alert-${type}`;
            alertDiv.innerHTML = message;
            document.body.appendChild(alertDiv);
            
            setTimeout(() => {
                alertDiv.style.opacity = '0';
                alertDiv.style.transition = 'opacity 0.5s';
                setTimeout(() => alertDiv.remove(), 500);
            }, 4000);
        }
        
        function resetForm() {
            document.getElementById('fileInput').value = '';
            document.getElementById('preview').innerHTML = '';
            document.getElementById('result').style.display = 'none';
            document.getElementById('jsonResult').style.display = 'none';
            document.getElementById('customText').value = '';
            document.getElementById('customNumber').value = '';
            document.getElementById('jsonOutput').style.display = 'none';
            document.getElementById('copyJsonBtn').style.display = 'none';
            uploadedFiles = [];
            savedJsonItems = [];
            window.scrollTo({ top: 0, behavior: 'smooth' });
            updateStats();
        }

        async function saveJson() {
            const text = document.getElementById('customText').value.trim();
            const number = document.getElementById('customNumber').value.trim();
            
            if (!text && !number) {
                showAlert('error', '❌ দয়া করে টেক্সট অথবা সংখ্যা দিন!');
                return;
            }
            
            let jsonObj = {};
            if (text) jsonObj.message = text;
            if (number) jsonObj.NUMBER = number;
            
            try {
                const response = await fetch('/api/save_json', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(jsonObj)
                });
                
                const data = await response.json();
                
                if (data.success) {
                    showAlert('success', '✅ JSON সফলভাবে সংরক্ষিত হয়েছে!');
                    
                    displayJsonItem(data.data);
                    document.getElementById('jsonResult').style.display = 'block';
                    
                    document.getElementById('customText').value = '';
                    document.getElementById('customNumber').value = '';
                    document.getElementById('jsonOutput').style.display = 'none';
                    document.getElementById('copyJsonBtn').style.display = 'none';
                    
                    updateStats();
                }
            } catch (error) {
                console.error('Error:', error);
                showAlert('error', '❌ JSON সংরক্ষণ করতে সমস্যা হয়েছে!');
            }
        }

        function displayJsonItem(data) {
            const jsonList = document.getElementById('jsonList');
            const item = document.createElement('div');
            item.className = 'json-item';
            item.innerHTML = `
                <div><strong>📝 টেক্সট:</strong> ${data.message || 'N/A'}</div>
                <div><strong>🔢 সংখ্যা:</strong> ${data.NUMBER || 'N/A'}</div>
                <div class="json-url"><strong>🔗 URL:</strong> ${data.url}</div>
                <button class="copy-btn" onclick="copyToClipboard('${data.url}')">📋 URL কপি করুন</button>
                <button class="copy-btn" style="margin-left: 10px;" onclick="copyJsonContent('${data.filename}')">📋 JSON কপি করুন</button>
                <button class="copy-btn" style="margin-left: 10px; background: #f5576c;" onclick="deleteJsonItem('${data.filename}')">🗑️ ডিলিট</button>
            `;
            jsonList.appendChild(item);
        }

        async function copyJsonContent(filename) {
            try {
                const response = await fetch('/get_json/' + filename);
                const data = await response.json();
                const jsonString = JSON.stringify(data, null, 2);
                await navigator.clipboard.writeText(jsonString);
                showAlert('success', '✅ JSON কপি হয়েছে!');
            } catch (error) {
                showAlert('error', '❌ JSON কপি করতে সমস্যা হয়েছে!');
            }
        }

        async function deleteJsonItem(filename) {
            if (confirm('আপনি কি এই JSON ডেটা ডিলিট করতে চান?')) {
                try {
                    const response = await fetch('/delete_json/' + filename, {
                        method: 'DELETE'
                    });
                    const data = await response.json();
                    if (data.success) {
                        showAlert('success', '✅ JSON ডিলিট হয়েছে!');
                        // Remove the item from the list
                        const items = document.querySelectorAll('.json-item');
                        for (let item of items) {
                            if (item.innerHTML.includes(filename)) {
                                item.remove();
                                break;
                            }
                        }
                        updateStats();
                    } else {
                        showAlert('error', '❌ ডিলিট করতে সমস্যা হয়েছে!');
                    }
                } catch (error) {
                    showAlert('error', '❌ ডিলিট করতে সমস্যা হয়েছে!');
                }
            }
        }

        function generateJsonPreview() {
            const text = document.getElementById('customText').value.trim();
            const number = document.getElementById('customNumber').value.trim();
            
            if (!text && !number) {
                document.getElementById('jsonOutput').style.display = 'none';
                document.getElementById('copyJsonBtn').style.display = 'none';
                return;
            }
            
            let jsonObj = {};
            if (text) jsonObj.message = text;
            if (number) jsonObj.NUMBER = number;
            
            const jsonString = JSON.stringify(jsonObj, null, 2);
            
            const jsonOutput = document.getElementById('jsonOutput');
            jsonOutput.style.display = 'block';
            
            // Escape HTML special characters
            const escaped = jsonString
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;');
            
            // Simple syntax highlighting
            let highlighted = escaped
                .replace(/"([^"]+)":/g, '<span class="key">"$1"</span>:')
                .replace(/: "([^"]+)"/g, ': <span class="string">"$1"</span>')
                .replace(/: (\\d+)/g, ': <span class="number">$1</span>');
            
            jsonOutput.innerHTML = highlighted;
            
            // Store the JSON string for copying
            jsonOutput.dataset.jsonString = jsonString;
            document.getElementById('copyJsonBtn').style.display = 'inline-block';
        }

        function clearJson() {
            document.getElementById('customText').value = '';
            document.getElementById('customNumber').value = '';
            document.getElementById('jsonOutput').style.display = 'none';
            document.getElementById('copyJsonBtn').style.display = 'none';
        }

        function copyJson() {
            const jsonOutput = document.getElementById('jsonOutput');
            const jsonString = jsonOutput.dataset.jsonString || jsonOutput.textContent;
            
            navigator.clipboard.writeText(jsonString).then(() => {
                showAlert('success', '✅ JSON কপি হয়েছে!');
            }).catch(() => {
                prompt('ম্যানুয়ালি কপি করুন:', jsonString);
            });
        }

        async function updateStats() {
            try {
                // Get image count
                const imgResponse = await fetch('/count_images');
                const imgData = await imgResponse.json();
                if (imgData.success) {
                    document.getElementById('totalImages').textContent = imgData.count;
                }

                // Get JSON count
                const jsonResponse = await fetch('/count_json');
                const jsonData = await jsonResponse.json();
                if (jsonData.success) {
                    document.getElementById('totalJson').textContent = jsonData.count;
                }
            } catch (error) {
                console.error('Error updating stats:', error);
            }
        }

        async function cleanupFiles(event) {
            event.preventDefault();
            if (confirm('আপনি কি ৭ দিনের বেশি পুরানো সব ফাইল ডিলিট করতে চান?')) {
                try {
                    const response = await fetch('/cleanup', {
                        method: 'POST'
                    });
                    const data = await response.json();
                    if (data.success) {
                        showAlert('success', '✅ ' + data.deleted + ' টি ফাইল ডিলিট হয়েছে!');
                        updateStats();
                    }
                } catch (error) {
                    showAlert('error', '❌ ক্লিনআপ করতে সমস্যা হয়েছে!');
                }
            }
        }
        
        // Drag and drop functionality
        const dropZone = document.getElementById('dropZone');
        
        dropZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            dropZone.classList.add('dragover');
        });
        
        dropZone.addEventListener('dragleave', (e) => {
            e.preventDefault();
            dropZone.classList.remove('dragover');
        });
        
        dropZone.addEventListener('drop', (e) => {
            e.preventDefault();
            dropZone.classList.remove('dragover');
            const files = e.dataTransfer.files;
            handleFiles(files);
        });

        // Auto-generate JSON preview when text or number changes
        document.getElementById('customText').addEventListener('input', generateJsonPreview);
        document.getElementById('customNumber').addEventListener('input', generateJsonPreview);

        // Load existing JSON items on page load
        async function loadJsonItems() {
            try {
                const response = await fetch('/list_json');
                const data = await response.json();
                if (data.success && data.files.length > 0) {
                    document.getElementById('jsonResult').style.display = 'block';
                    data.files.forEach(file => {
                        // Parse the content to get the data
                        try {
                            const parsed = JSON.parse(file.content);
                            displayJsonItem({
                                filename: file.filename,
                                url: file.url,
                                message: parsed.message,
                                NUMBER: parsed.NUMBER
                            });
                        } catch (e) {
                            // If parsing fails, just show the raw content
                            displayJsonItem({
                                filename: file.filename,
                                url: file.url,
                                message: 'Raw JSON',
                                NUMBER: 'See content'
                            });
                        }
                    });
                }
                updateStats();
            } catch (error) {
                console.error('Error loading JSON items:', error);
            }
        }

        // Load on page load
        window.onload = function() {
            loadJsonItems();
        };
    </script>
</body>
</html>
'''

# Gallery Template
GALLERY_TEMPLATE = '''
<!DOCTYPE html>
<html lang="bn">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🎨 গ্যালারি - Photo & JSON to URL Generator</title>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }

        .container {
            max-width: 1400px;
            margin: 0 auto;
        }

        .header {
            background: white;
            border-radius: 20px;
            padding: 20px 30px;
            margin-bottom: 30px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 15px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            animation: slideDown 0.6s ease-out;
        }

        @keyframes slideDown {
            from {
                opacity: 0;
                transform: translateY(-30px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }

        .header h1 {
            color: #667eea;
            font-size: 2em;
        }

        .stats {
            color: #666;
            font-size: 1.1em;
        }

        .btn {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 10px 20px;
            font-size: 1em;
            border-radius: 50px;
            cursor: pointer;
            text-decoration: none;
            display: inline-block;
            transition: all 0.3s;
            font-weight: 600;
            box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
        }

        .btn:hover {
            transform: translateY(-3px) scale(1.02);
            box-shadow: 0 8px 25px rgba(102, 126, 234, 0.6);
        }

        .btn-danger {
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
            box-shadow: 0 4px 15px rgba(245, 87, 108, 0.4);
        }

        .btn-danger:hover {
            box-shadow: 0 8px 25px rgba(245, 87, 108, 0.6);
        }

        .btn-gallery {
            background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%);
            box-shadow: 0 4px 15px rgba(67, 233, 123, 0.4);
            color: #1a1a2e;
        }

        .btn-gallery:hover {
            box-shadow: 0 8px 25px rgba(67, 233, 123, 0.6);
        }

        .btn-home {
            background: linear-gradient(135deg, #a18cd1 0%, #fbc2eb 100%);
            box-shadow: 0 4px 15px rgba(161, 140, 209, 0.4);
            color: #1a1a2e;
        }

        .btn-home:hover {
            box-shadow: 0 8px 25px rgba(161, 140, 209, 0.6);
        }

        .section-title {
            color: white;
            margin: 30px 0 20px 0;
            font-size: 1.8em;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }

        .section-title i {
            margin-right: 10px;
        }

        .gallery-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
            gap: 25px;
            animation: fadeIn 0.8s ease-out;
        }

        @keyframes fadeIn {
            from {
                opacity: 0;
            }
            to {
                opacity: 1;
            }
        }

        .gallery-card {
            background: white;
            border-radius: 15px;
            overflow: hidden;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            transition: all 0.3s;
            animation: cardFadeIn 0.5s ease-out;
            animation-fill-mode: both;
        }

        @keyframes cardFadeIn {
            from {
                opacity: 0;
                transform: translateY(20px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }

        .gallery-card:nth-child(1) { animation-delay: 0.05s; }
        .gallery-card:nth-child(2) { animation-delay: 0.1s; }
        .gallery-card:nth-child(3) { animation-delay: 0.15s; }
        .gallery-card:nth-child(4) { animation-delay: 0.2s; }
        .gallery-card:nth-child(5) { animation-delay: 0.25s; }
        .gallery-card:nth-child(6) { animation-delay: 0.3s; }

        .gallery-card:hover {
            transform: translateY(-8px);
            box-shadow: 0 20px 50px rgba(0,0,0,0.3);
        }

        .image-container {
            position: relative;
            cursor: pointer;
            overflow: hidden;
            height: 250px;
        }

        .gallery-image {
            width: 100%;
            height: 100%;
            object-fit: cover;
            transition: transform 0.5s;
        }

        .gallery-card:hover .gallery-image {
            transform: scale(1.1);
        }

        .overlay {
            position: absolute;
            bottom: -100%;
            left: 0;
            right: 0;
            background: linear-gradient(to top, rgba(0,0,0,0.8), transparent);
            padding: 20px;
            transition: bottom 0.3s;
        }

        .gallery-card:hover .overlay {
            bottom: 0;
        }

        .card-info {
            padding: 15px;
        }

        .filename {
            font-weight: bold;
            color: #333;
            margin-bottom: 8px;
            word-break: break-all;
            font-size: 0.9em;
        }

        .meta {
            color: #999;
            font-size: 0.85em;
            margin-bottom: 10px;
        }

        .url-box {
            background: #f0f0f0;
            padding: 10px;
            border-radius: 8px;
            font-size: 0.8em;
            word-break: break-all;
            margin-bottom: 10px;
            cursor: pointer;
            transition: background 0.3s;
        }

        .url-box:hover {
            background: #e0e0e0;
        }

        .button-group {
            display: flex;
            gap: 10px;
            margin-top: 10px;
        }

        .btn-small {
            flex: 1;
            padding: 8px;
            font-size: 0.85em;
        }

        .json-list {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }

        .json-card {
            background: white;
            border-radius: 15px;
            padding: 20px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            transition: all 0.3s;
            animation: cardFadeIn 0.5s ease-out;
            animation-fill-mode: both;
        }

        .json-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 15px 40px rgba(0,0,0,0.3);
        }

        .json-card .json-content {
            background: #1e1e1e;
            padding: 15px;
            border-radius: 10px;
            color: #d4d4d4;
            font-family: 'Courier New', monospace;
            font-size: 0.85em;
            overflow-x: auto;
            white-space: pre-wrap;
            word-break: break-all;
            max-height: 150px;
            overflow-y: auto;
            margin: 10px 0;
        }

        .json-card .json-url {
            font-family: monospace;
            color: #667eea;
            word-break: break-all;
            margin: 10px 0;
            padding: 10px;
            background: #f8f9ff;
            border-radius: 8px;
        }

        .empty-state {
            text-align: center;
            padding: 80px 20px;
            background: white;
            border-radius: 20px;
            animation: fadeIn 0.6s ease-out;
        }

        .empty-icon {
            font-size: 5em;
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
            background: rgba(0,0,0,0.9);
            animation: fadeIn 0.3s;
        }

        .modal-content {
            position: relative;
            margin: auto;
            padding: 20px;
            width: 90%;
            max-width: 90%;
            top: 50%;
            transform: translateY(-50%);
        }

        .modal-image {
            width: 100%;
            max-height: 80vh;
            object-fit: contain;
            border-radius: 10px;
        }

        .close {
            position: absolute;
            top: 20px;
            right: 40px;
            color: white;
            font-size: 40px;
            cursor: pointer;
            transition: transform 0.3s;
        }

        .close:hover {
            transform: rotate(90deg);
        }

        .alert {
            padding: 15px;
            border-radius: 10px;
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 9999;
            max-width: 400px;
            box-shadow: 0 5px 20px rgba(0,0,0,0.2);
            animation: slideDown 0.5s ease-out;
        }

        .alert-success {
            background: #d4edda;
            color: #155724;
            border: 1px solid #c3e6cb;
        }

        .nav-buttons {
            display: flex;
            justify-content: center;
            gap: 15px;
            margin-top: 30px;
            flex-wrap: wrap;
        }

        .vercel-badge {
            display: inline-block;
            background: #000;
            color: #fff;
            padding: 5px 15px;
            border-radius: 20px;
            font-size: 0.8em;
        }

        @media (max-width: 768px) {
            .gallery-grid {
                grid-template-columns: 1fr;
            }
            
            .json-list {
                grid-template-columns: 1fr;
            }

            .header {
                flex-direction: column;
                text-align: center;
            }

            .modal-content {
                width: 95%;
            }

            .close {
                right: 20px;
                top: 10px;
                font-size: 30px;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1><i class="fas fa-images"></i> গ্যালারি</h1>
            <div class="stats">
                <i class="fas fa-camera"></i> ছবি: {{ images|length }} টি | 
                <i class="fas fa-code"></i> JSON: {{ json_files|length }} টি
            </div>
            <div style="display: flex; gap: 10px; flex-wrap: wrap;">
                <a href="/" class="btn btn-home"><i class="fas fa-home"></i> হোম</a>
                <a href="/" class="btn"><i class="fas fa-plus"></i> নতুন তৈরি করুন</a>
            </div>
            <div class="vercel-badge" style="margin-top: 10px;">
                <i class="fas fa-cloud"></i> Vercel Ready
            </div>
        </div>

        <div id="image-section">
            {% if images %}
            <h2 class="section-title"><i class="fas fa-image"></i> ছবি সমূহ</h2>
            <div class="gallery-grid">
                {% for image in images %}
                <div class="gallery-card">
                    <div class="image-container" onclick="openModal('{{ image.url }}')">
                        <img src="{{ image.url }}" class="gallery-image" alt="{{ image.filename }}" loading="lazy">
                        <div class="overlay">
                            <div class="url-box" onclick="event.stopPropagation(); copyToClipboard('{{ image.url }}')">
                                <i class="fas fa-link"></i> ক্লিক করে URL কপি করুন
                            </div>
                        </div>
                    </div>
                    <div class="card-info">
                        <div class="filename"><i class="fas fa-file-image"></i> {{ image.filename[:30] }}{% if image.filename|length > 30 %}...{% endif %}</div>
                        <div class="meta"><i class="fas fa-weight-hanging"></i> {{ image.size }} | <i class="far fa-clock"></i> {{ image.upload_date }}</div>
                        <div class="button-group">
                            <button class="btn btn-small" onclick="copyToClipboard('{{ image.url }}')"><i class="fas fa-copy"></i> কপি URL</button>
                            <button class="btn btn-small btn-danger" onclick="deleteImage('{{ image.filename }}')"><i class="fas fa-trash"></i> ডিলিট</button>
                        </div>
                    </div>
                </div>
                {% endfor %}
            </div>
            {% else %}
            <div class="empty-state">
                <div class="empty-icon">📭</div>
                <h2>কোনো ছবি নেই!</h2>
                <p style="margin: 20px 0; color: #666;">প্রথমে কিছু ছবি আপলোড করুন</p>
                <a href="/" class="btn"><i class="fas fa-upload"></i> ছবি আপলোড করুন</a>
            </div>
            {% endif %}
        </div>

        <div id="json-section">
            {% if json_files %}
            <h2 class="section-title" style="margin-top: 40px;"><i class="fas fa-code"></i> JSON ডেটা সমূহ</h2>
            <div class="json-list">
                {% for json_item in json_files %}
                <div class="json-card">
                    <div><strong><i class="fas fa-tag"></i> আইডি:</strong> {{ json_item.filename[:20] }}...</div>
                    <div class="json-content">{{ json_item.content }}</div>
                    <div class="json-url"><strong>🔗 URL:</strong> {{ json_item.url }}</div>
                    <div class="button-group">
                        <button class="btn btn-small" onclick="copyToClipboard('{{ json_item.url }}')"><i class="fas fa-copy"></i> কপি URL</button>
                        <button class="btn btn-small" onclick="copyJsonContent('{{ json_item.filename }}')"><i class="fas fa-copy"></i> কপি JSON</button>
                        <button class="btn btn-small btn-danger" onclick="deleteJson('{{ json_item.filename }}')"><i class="fas fa-trash"></i> ডিলিট</button>
                    </div>
                </div>
                {% endfor %}
            </div>
            {% else %}
            <div class="empty-state" style="margin-top: 30px;">
                <div class="empty-icon">📄</div>
                <h2>কোনো JSON ডেটা নেই!</h2>
                <p style="margin: 20px 0; color: #666;">প্রথমে কিছু JSON তৈরি করুন</p>
                <a href="/" class="btn"><i class="fas fa-code"></i> JSON তৈরি করুন</a>
            </div>
            {% endif %}
        </div>

        <div class="nav-buttons">
            <a href="/" class="btn btn-home"><i class="fas fa-home"></i> হোম পেজে ফিরে যান</a>
            <a href="/#json-section" class="btn"><i class="fas fa-plus"></i> নতুন JSON তৈরি করুন</a>
        </div>
    </div>

    <div id="imageModal" class="modal">
        <span class="close" onclick="closeModal()">&times;</span>
        <div class="modal-content">
            <img id="modalImage" class="modal-image">
        </div>
    </div>

    <script>
        function copyToClipboard(text) {
            navigator.clipboard.writeText(text).then(() => {
                showAlert('✅ কপি হয়েছে!');
            }).catch(() => {
                prompt('ম্যানুয়ালি কপি করুন:', text);
            });
        }
        
        function showAlert(message) {
            const alertDiv = document.createElement('div');
            alertDiv.className = 'alert alert-success';
            alertDiv.innerHTML = message;
            document.body.appendChild(alertDiv);
            
            setTimeout(() => {
                alertDiv.style.opacity = '0';
                alertDiv.style.transition = 'opacity 0.5s';
                setTimeout(() => alertDiv.remove(), 500);
            }, 3000);
        }
        
        function openModal(url) {
            document.getElementById('modalImage').src = url;
            document.getElementById('imageModal').style.display = 'block';
            document.body.style.overflow = 'hidden';
        }
        
        function closeModal() {
            document.getElementById('imageModal').style.display = 'none';
            document.body.style.overflow = 'auto';
        }
        
        async function deleteImage(filename) {
            if (confirm('আপনি কি এই ছবিটি ডিলিট করতে চান?')) {
                try {
                    const response = await fetch('/delete/' + filename, {
                        method: 'DELETE'
                    });
                    const data = await response.json();
                    if (data.success) {
                        showAlert('✅ ছবি ডিলিট হয়েছে!');
                        setTimeout(() => location.reload(), 1000);
                    } else {
                        showAlert('❌ ডিলিট করতে সমস্যা হয়েছে!');
                    }
                } catch (error) {
                    showAlert('❌ ডিলিট করতে সমস্যা হয়েছে!');
                }
            }
        }

        async function deleteJson(filename) {
            if (confirm('আপনি কি এই JSON ডেটা ডিলিট করতে চান?')) {
                try {
                    const response = await fetch('/delete_json/' + filename, {
                        method: 'DELETE'
                    });
                    const data = await response.json();
                    if (data.success) {
                        showAlert('✅ JSON ডিলিট হয়েছে!');
                        setTimeout(() => location.reload(), 1000);
                    } else {
                        showAlert('❌ ডিলিট করতে সমস্যা হয়েছে!');
                    }
                } catch (error) {
                    showAlert('❌ ডিলিট করতে সমস্যা হয়েছে!');
                }
            }
        }

        async function copyJsonContent(filename) {
            try {
                const response = await fetch('/get_json/' + filename);
                const data = await response.json();
                const jsonString = JSON.stringify(data, null, 2);
                await navigator.clipboard.writeText(jsonString);
                showAlert('✅ JSON কপি হয়েছে!');
            } catch (error) {
                showAlert('❌ JSON কপি করতে সমস্যা হয়েছে!');
            }
        }
        
        // Close modal with ESC key
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') {
                closeModal();
            }
        });
        
        // Close modal on outside click
        document.getElementById('imageModal').addEventListener('click', function(e) {
            if (e.target === this) {
                closeModal();
            }
        });
    </script>
</body>
</html>
'''

@app.route('/', methods=['GET', 'POST'])
def index():
    generated_links = []
    uploaded_files_info = []
    
    if request.method == 'POST':
        files = request.files.getlist('photos')
        
        for file in files:
            if file and file.filename != '' and allowed_file(file.filename):
                ext = file.filename.rsplit('.', 1)[1].lower()
                unique_name = f"{uuid.uuid4().hex}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{ext}"
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_name)
                file.save(file_path)
                
                file_size = get_file_size(file_path)
                full_url = request.host_url + 'image/' + unique_name
                generated_links.append(full_url)
                
                uploaded_files_info.append({
                    'original_name': file.filename,
                    'url': full_url,
                    'size': file_size,
                    'type': ext.upper()
                })
    
    return render_template_string(INDEX_TEMPLATE, links=generated_links, files_info=uploaded_files_info)

@app.route('/image/<filename>')
def serve_image(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/api/upload', methods=['POST'])
def api_upload():
    if 'photos' not in request.files:
        return jsonify({'error': 'No files uploaded'}), 400
    
    files = request.files.getlist('photos')
    uploaded_files = []
    
    for file in files:
        if file and file.filename != '' and allowed_file(file.filename):
            ext = file.filename.rsplit('.', 1)[1].lower()
            unique_name = f"{uuid.uuid4().hex}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{ext}"
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_name)
            file.save(file_path)
            
            file_size = get_file_size(file_path)
            full_url = request.host_url + 'image/' + unique_name
            
            uploaded_files.append({
                'original_name': file.filename,
                'url': full_url,
                'size': file_size,
                'type': ext.upper(),
                'filename': unique_name
            })
    
    return jsonify({'success': True, 'files': uploaded_files})

@app.route('/api/save_json', methods=['POST'])
def save_json():
    """Save JSON data and return a unique URL"""
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    # Generate unique filename
    unique_id = uuid.uuid4().hex
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"{unique_id}_{timestamp}.json"
    file_path = os.path.join(app.config['JSON_FOLDER'], filename)
    
    # Save JSON data
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    # Generate URL
    full_url = request.host_url + 'json/' + filename
    
    return jsonify({
        'success': True,
        'data': {
            'filename': filename,
            'url': full_url,
            **data
        }
    })

@app.route('/json/<filename>')
def serve_json(filename):
    """Serve JSON file"""
    return send_from_directory(app.config['JSON_FOLDER'], filename)

@app.route('/get_json/<filename>')
def get_json(filename):
    """Get JSON content"""
    file_path = os.path.join(app.config['JSON_FOLDER'], filename)
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return jsonify(data)
    return jsonify({'error': 'File not found'}), 404

@app.route('/delete_json/<filename>', methods=['DELETE'])
def delete_json(filename):
    """Delete a JSON file"""
    file_path = os.path.join(app.config['JSON_FOLDER'], filename)
    if os.path.exists(file_path):
        os.remove(file_path)
        return jsonify({'success': True, 'message': 'JSON file deleted successfully'})
    return jsonify({'success': False, 'message': 'File not found'}), 404

@app.route('/list_json')
def list_json():
    """List all JSON files"""
    json_files = []
    for filename in os.listdir(app.config['JSON_FOLDER']):
        if filename.endswith('.json'):
            file_path = os.path.join(app.config['JSON_FOLDER'], filename)
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            json_files.append({
                'filename': filename,
                'url': request.host_url + 'json/' + filename,
                'content': json.dumps(data, ensure_ascii=False, indent=2)
            })
    return jsonify({'success': True, 'files': json_files})

@app.route('/count_images')
def count_images():
    """Count total images"""
    count = 0
    for filename in os.listdir(UPLOAD_FOLDER):
        if any(filename.lower().endswith(ext) for ext in ALLOWED_EXTENSIONS):
            count += 1
    return jsonify({'success': True, 'count': count})

@app.route('/count_json')
def count_json():
    """Count total JSON files"""
    count = 0
    for filename in os.listdir(app.config['JSON_FOLDER']):
        if filename.endswith('.json'):
            count += 1
    return jsonify({'success': True, 'count': count})

@app.route('/delete/<filename>', methods=['DELETE'])
def delete_file(filename):
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if os.path.exists(file_path):
        os.remove(file_path)
        return jsonify({'success': True, 'message': 'File deleted successfully'})
    return jsonify({'success': False, 'message': 'File not found'}), 404

@app.route('/gallery')
def gallery():
    # Get all images
    images = []
    for filename in os.listdir(UPLOAD_FOLDER):
        if any(filename.lower().endswith(ext) for ext in ALLOWED_EXTENSIONS):
            file_path = os.path.join(UPLOAD_FOLDER, filename)
            file_size = get_file_size(file_path)
            images.append({
                'filename': filename,
                'url': request.host_url + 'image/' + filename,
                'size': file_size,
                'upload_date': datetime.fromtimestamp(os.path.getctime(file_path)).strftime('%Y-%m-%d %H:%M:%S')
            })
    
    # Get all JSON files
    json_files = []
    for filename in os.listdir(app.config['JSON_FOLDER']):
        if filename.endswith('.json'):
            file_path = os.path.join(app.config['JSON_FOLDER'], filename)
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            json_files.append({
                'filename': filename,
                'url': request.host_url + 'json/' + filename,
                'content': json.dumps(data, ensure_ascii=False, indent=2)
            })
    
    return render_template_string(GALLERY_TEMPLATE, images=images, json_files=json_files)

@app.route('/cleanup', methods=['POST'])
def cleanup():
    import time
    deleted = 0
    current_time = time.time()
    
    # Cleanup images
    for filename in os.listdir(UPLOAD_FOLDER):
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        if os.path.isfile(file_path):
            if current_time - os.path.getctime(file_path) > 604800:  # 7 days
                os.remove(file_path)
                deleted += 1
    
    # Cleanup JSON files
    for filename in os.listdir(app.config['JSON_FOLDER']):
        file_path = os.path.join(app.config['JSON_FOLDER'], filename)
        if os.path.isfile(file_path):
            if current_time - os.path.getctime(file_path) > 604800:  # 7 days
                os.remove(file_path)
                deleted += 1
    
    return jsonify({'success': True, 'deleted': deleted})

# For Vercel deployment
def create_app():
    return app

if __name__ == '__main__':
    print("\n" + "="*50)
    print("🚀 Photo & JSON to URL Generator Started!")
    print("="*50)
    print(f"📁 Upload folder: {os.path.abspath(UPLOAD_FOLDER)}")
    print(f"📁 JSON folder: {os.path.abspath(JSON_FOLDER)}")
    print(f"🌐 Server running at: http://127.0.0.1:5002")
    print(f"📸 Gallery available at: http://127.0.0.1:5002/gallery")
    print("="*50)
    print("Press CTRL+C to stop the server\n")
    app.run(debug=True, host='0.0.0.0', port=5002)