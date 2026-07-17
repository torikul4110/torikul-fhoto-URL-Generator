import os
import uuid
import tempfile
from datetime import datetime
from flask import Flask, render_template_string, request, send_from_directory, jsonify

app = Flask(__name__)

# Vercel-এ ফাইল সংরক্ষণের জন্য tmp ফোল্ডার ব্যবহার করুন
UPLOAD_FOLDER = os.path.join(tempfile.gettempdir(), 'uploads')
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB

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
    <title>Photo to URL Generator - ইমেজ থেকে লিংক জেনারেটর</title>
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
        }

        .header h1 {
            font-size: 3em;
            margin-bottom: 10px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.2);
        }

        .header p {
            font-size: 1.2em;
            opacity: 0.95;
        }

        .upload-card {
            background: white;
            border-radius: 20px;
            padding: 40px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            margin-bottom: 30px;
            transition: transform 0.3s;
        }

        .upload-card:hover {
            transform: translateY(-5px);
        }

        .upload-area {
            border: 3px dashed #667eea;
            border-radius: 15px;
            padding: 60px 20px;
            text-align: center;
            background: #f8f9ff;
            cursor: pointer;
            transition: all 0.3s;
        }

        .upload-area:hover {
            border-color: #764ba2;
            background: #f0f2ff;
        }

        .upload-icon {
            font-size: 4em;
            margin-bottom: 20px;
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
            transition: transform 0.2s;
            margin: 10px 5px;
        }

        .btn:hover {
            transform: scale(1.05);
        }

        .btn-secondary {
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
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
            transition: transform 0.3s;
        }

        .preview-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 10px 25px rgba(0,0,0,0.2);
        }

        .preview-image {
            width: 100%;
            height: 200px;
            object-fit: cover;
        }

        .preview-info {
            padding: 15px;
        }

        .preview-name {
            font-weight: bold;
            margin-bottom: 5px;
            color: #333;
            word-break: break-all;
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
        }

        .copy-btn {
            background: #667eea;
            color: white;
            border: none;
            padding: 5px 10px;
            border-radius: 5px;
            cursor: pointer;
            font-size: 0.85em;
        }

        .copy-btn:hover {
            background: #764ba2;
        }

        .result-card {
            background: white;
            border-radius: 20px;
            padding: 30px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            margin-top: 30px;
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
            background: #f8f9ff;
            padding: 15px;
            margin-bottom: 10px;
            border-radius: 10px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
        }

        .link-url {
            font-family: monospace;
            color: #667eea;
            word-break: break-all;
            flex: 1;
            margin-right: 10px;
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

        .nav-buttons {
            display: flex;
            justify-content: center;
            gap: 15px;
            margin-top: 20px;
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
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📸 Photo to URL Generator</h1>
            <p>আপলোড করুন আপনার ছবি, সাথে সাথে পেয়ে যান ডাউনলোড লিংক</p>
        </div>

        <div class="upload-card">
            <div class="upload-area" onclick="document.getElementById('fileInput').click()">
                <div class="upload-icon">📷</div>
                <div class="upload-text">ক্লিক করুন ছবি নির্বাচন করতে</div>
                <div class="upload-subtext">অথবা এখানে ড্র্যাগ করুন</div>
                <input type="file" id="fileInput" multiple accept="image/*" onchange="handleFiles(this.files)">
            </div>

            <div id="loading" class="loading">
                <div class="spinner"></div>
                <p style="margin-top: 10px;">আপলোড হচ্ছে...</p>
            </div>

            <div id="preview" class="preview-area"></div>
        </div>

        <div id="result" class="result-card" style="display: none;">
            <h3 class="result-title">✅ জেনারেটেড লিংকসমূহ</h3>
            <div id="linkList"></div>
            <div class="nav-buttons">
                <button class="btn" onclick="window.location.href='/gallery'">🎨 গ্যালারি দেখুন</button>
                <button class="btn btn-secondary" onclick="resetForm()">🔄 নতুন করে আপলোড করুন</button>
            </div>
        </div>
    </div>

    <script>
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
                    displayPreview(data.files);
                    displayLinks(data.files);
                    document.getElementById('result').style.display = 'block';
                }
            } catch (error) {
                console.error('Error:', error);
                alert('আপলোড করতে সমস্যা হয়েছে!');
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
                        <div class="preview-name">${file.original_name.substring(0, 30)}</div>
                        <div class="preview-size">📦 ${file.size}</div>
                        <div class="url-link" onclick="copyToClipboard('${file.url}')">
                            🔗 ক্লিক করে কপি করুন
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
                prompt('ম্যানুয়ালি কপি করুন:', text);
            }
        }
        
        function resetForm() {
            document.getElementById('fileInput').value = '';
            document.getElementById('preview').innerHTML = '';
            document.getElementById('result').style.display = 'none';
            location.reload();
        }
        
        // Drag and drop functionality
        const dropZone = document.querySelector('.upload-area');
        
        dropZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            dropZone.style.borderColor = '#764ba2';
            dropZone.style.background = '#f0f2ff';
        });
        
        dropZone.addEventListener('dragleave', (e) => {
            e.preventDefault();
            dropZone.style.borderColor = '#667eea';
            dropZone.style.background = '#f8f9ff';
        });
        
        dropZone.addEventListener('drop', (e) => {
            e.preventDefault();
            dropZone.style.borderColor = '#667eea';
            dropZone.style.background = '#f8f9ff';
            const files = e.dataTransfer.files;
            handleFiles(files);
        });
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
    <title>ইমেজ গ্যালারি - Photo to URL Generator</title>
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
            transition: transform 0.2s;
        }

        .btn:hover {
            transform: scale(1.05);
        }

        .gallery-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
            gap: 25px;
        }

        .gallery-card {
            background: white;
            border-radius: 15px;
            overflow: hidden;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            transition: transform 0.3s;
            animation: fadeIn 0.5s ease-in;
        }

        @keyframes fadeIn {
            from {
                opacity: 0;
                transform: translateY(20px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }

        .gallery-card:hover {
            transform: translateY(-5px);
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
            transition: transform 0.3s;
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

        .btn-danger {
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        }

        .empty-state {
            text-align: center;
            padding: 80px 20px;
            background: white;
            border-radius: 20px;
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
        }

        @media (max-width: 768px) {
            .gallery-grid {
                grid-template-columns: 1fr;
            }
            
            .header {
                flex-direction: column;
                text-align: center;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎨 ইমেজ গ্যালারি</h1>
            <div class="stats">
                📸 মোট ছবি: {{ images|length }} টি
            </div>
            <a href="/" class="btn">➕ নতুন ছবি আপলোড করুন</a>
        </div>

        {% if images %}
        <div class="gallery-grid">
            {% for image in images %}
            <div class="gallery-card">
                <div class="image-container" onclick="openModal('{{ image.url }}')">
                    <img src="{{ image.url }}" class="gallery-image" alt="{{ image.filename }}">
                    <div class="overlay">
                        <div class="url-box" onclick="event.stopPropagation(); copyToClipboard('{{ image.url }}')">
                            🔗 ক্লিক করে URL কপি করুন
                        </div>
                    </div>
                </div>
                <div class="card-info">
                    <div class="filename">📄 {{ image.filename[:30] }}{% if image.filename|length > 30 %}...{% endif %}</div>
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
            <p style="margin: 20px 0; color: #666;">প্রথমে কিছু ছবি আপলোড করুন</p>
            <a href="/" class="btn">📸 ছবি আপলোড করুন</a>
        </div>
        {% endif %}
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
                alert('✅ URL কপি হয়েছে!');
            }).catch(() => {
                prompt('ম্যানুয়ালি কপি করুন:', text);
            });
        }
        
        function openModal(url) {
            document.getElementById('modalImage').src = url;
            document.getElementById('imageModal').style.display = 'block';
        }
        
        function closeModal() {
            document.getElementById('imageModal').style.display = 'none';
        }
        
        async function deleteImage(filename) {
            if (confirm('আপনি কি এই ছবিটি ডিলিট করতে চান?')) {
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
        
        // Close modal with ESC key
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') {
                closeModal();
            }
        });
    </script>
</body>
</html>
'''

# Home page with upload form
@app.route('/', methods=['GET', 'POST'])
def index():
    generated_links = []
    uploaded_files_info = []
    
    if request.method == 'POST':
        # Get multiple files
        files = request.files.getlist('photos')
        
        for file in files:
            if file and file.filename != '' and allowed_file(file.filename):
                # Create unique filename
                ext = file.filename.rsplit('.', 1)[1].lower()
                unique_name = f"{uuid.uuid4().hex}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{ext}"
                
                # Save file to uploads folder
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_name)
                file.save(file_path)
                
                # Get file size
                file_size = get_file_size(file_path)
                
                # Create photo URL
                full_url = request.host_url + 'image/' + unique_name
                generated_links.append(full_url)
                
                # Store file info for display
                uploaded_files_info.append({
                    'original_name': file.filename,
                    'url': full_url,
                    'size': file_size,
                    'type': ext.upper()
                })
    
    return render_template_string(INDEX_TEMPLATE, links=generated_links, files_info=uploaded_files_info)

# Serve images from uploads folder
@app.route('/image/<filename>')
def serve_image(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# API endpoint for AJAX uploads
@app.route('/api/upload', methods=['POST'])
def api_upload():
    """JSON API for uploading files"""
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

# Delete uploaded file
@app.route('/delete/<filename>', methods=['DELETE'])
def delete_file(filename):
    """Delete an uploaded file"""
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if os.path.exists(file_path):
        os.remove(file_path)
        return jsonify({'success': True, 'message': 'File deleted successfully'})
    return jsonify({'success': False, 'message': 'File not found'}), 404

# View all uploaded images
@app.route('/gallery')
def gallery():
    """Display all uploaded images in a gallery"""
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
    return render_template_string(GALLERY_TEMPLATE, images=images)

# Clean up old uploads (optional - run manually)
@app.route('/cleanup', methods=['POST'])
def cleanup():
    """Delete files older than 7 days"""
    import time
    deleted = 0
    current_time = time.time()
    for filename in os.listdir(UPLOAD_FOLDER):
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        if os.path.isfile(file_path):
            # Delete files older than 7 days (604800 seconds)
            if current_time - os.path.getctime(file_path) > 604800:
                os.remove(file_path)
                deleted += 1
    return jsonify({'success': True, 'deleted': deleted})

# Vercel-এর জন্য WSGI handler (গুরুত্বপূর্ণ)
app = app

if __name__ == '__main__':
    print("\n" + "="*50)
    print("🚀 Photo to URL Generator Started!")
    print("="*50)
    print(f"📁 Upload folder: {os.path.abspath(UPLOAD_FOLDER)}")
    print(f"🌐 Server running at: http://127.0.0.1:5000")
    print(f"📸 Gallery available at: http://127.0.0.1:5000/gallery")
    print("="*50)
    print("Press CTRL+C to stop the server\n")
    app.run(debug=True, host='0.0.0.0', port=5002)