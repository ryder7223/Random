"""
Folder structure:
├───save
│   ├───Artist
│   │   ├───Comic
"""

import os
from io import BytesIO
from flask import Flask, request, send_file, send_from_directory, render_template_string, abort, redirect, url_for, make_response
from datetime import datetime, UTC
from werkzeug.serving import WSGIRequestHandler
from PIL import Image
import json

class QuietHandler(WSGIRequestHandler):
    def log_request(self, code='-', size='-'):
        try:
            line = self.raw_requestline or b''
            if b'/pingPage' in line or b'/file/' in line or b'/status' in line:
                return
        except Exception:
            return
        if isinstance(code, int) and code == 400:
            return
        super().log_request(code, size)

    def log_error(self, format, *args):
        if len(args) >= 2:
            msg = str(args[1])
            if (
                'Bad request version' in msg
                or 'Bad HTTP/0.9 request type' in msg
                or 'Bad request syntax' in msg
            ):
                return
        super().log_error(format, *args)

app = Flask(__name__)
BASE_DIR = os.path.abspath("save")
IMAGE_EXTS = {'.png', '.jpg', '.jpeg', '.gif', '.webp'}

def resolveSafePath(subpath=""):
    basePath = BASE_DIR
    candidate = os.path.abspath(os.path.join(basePath, subpath))

    if candidate != basePath and not candidate.startswith(basePath + os.sep):
        abort(403)

    return candidate

def get_file_entries(folder):
    entries = []
    for entry in os.listdir(folder):
        fullPath = os.path.join(folder, entry)
        if os.path.isfile(fullPath):
            ext = os.path.splitext(entry)[1].lower()
            if ext in IMAGE_EXTS:
                stat = os.stat(fullPath)
                entries.append({
                    'name': entry,
                    'size': stat.st_size,
                    'modified': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                    'ext': ext
                })
    return sorted(entries, key=lambda x: x['name'].lower())

def get_subfolders(folder):
    return sorted([
        d for d in os.listdir(folder)
        if os.path.isdir(os.path.join(folder, d))
    ])

def isCompressionEnabled():
    return request.cookies.get('compressImages', 'true') == 'true'

def isLandscapeMode():
    return request.cookies.get('landscapeMode', 'false') == 'true'

def getQuality():
    try:
        q = int(request.cookies.get('jpegQuality', '50'))
        return max(1, min(q, 100))
    except Exception:
        return 50

currentReaders = {}

@app.route('/pingPage', methods=['POST'])
def pingPage():
    data = request.get_json(silent=True) or {}

    artist = data.get('artist') or "Unknown"
    comic = data.get('comic') or "Unknown"
    page = data.get('page') or 0
    pageCount = data.get('pageCount') or 0

    payload = {
        'ip': request.remote_addr,
        'artist': artist,
        'comic': comic,
        'page': page,
        'pageCount': pageCount,
        'timestamp': datetime.now(UTC).isoformat()
    }

    currentReaders[request.remote_addr] = payload

    logLine = f"[READING] Artist: {artist} | Comic: {comic} | Page: {page}/{pageCount}"
    print(logLine, flush=True)

    with open('pagePings.log', 'a', encoding='utf-8') as f:
        f.write(json.dumps(payload) + '\n')

    return '', 204

@app.route('/status')
def status():
    abort(403)

@app.route('/favicon.ico')
def favicon():
    return '', 204

@app.route('/toggleCompression')
def toggleCompression():
    resp = make_response(redirect(request.referrer or url_for('list_files', subpath='')))
    resp.set_cookie(
        'compressImages',
        'false' if isCompressionEnabled() else 'true',
        max_age=60 * 60 * 24 * 30,
        httponly=True,
        samesite='Lax'
    )
    return resp

@app.route('/toggleLandscape', methods=['POST'])
def toggleLandscape():
    resp = make_response('', 204)
    resp.set_cookie(
        'landscapeMode',
        'false' if isLandscapeMode() else 'true',
        max_age=60 * 60 * 24 * 30,
        httponly=True,
        samesite='Lax'
    )
    return resp

@app.route('/setQuality')
def setQuality():
    try:
        val = int(request.args.get('q', ''))
        if 1 <= val <= 100:
            resp = make_response(redirect(request.referrer or url_for('list_files', subpath='')))
            resp.set_cookie(
                'jpegQuality',
                str(val),
                max_age=60 * 60 * 24 * 30,
                httponly=True,
                samesite='Lax'
            )
            return resp
    except Exception:
        pass
    return redirect(request.referrer or url_for('list_files', subpath=''))

@app.route('/', defaults={'subpath': ''})
@app.route('/<path:subpath>')
def list_files(subpath):
    absPath = resolveSafePath(subpath)
    if not os.path.isdir(absPath):
        abort(404)

    files = get_file_entries(absPath)
    subfolders = get_subfolders(absPath)

    pathParts = subpath.split('/') if subpath else []
    artist = pathParts[0] if len(pathParts) >= 1 else None
    comic = pathParts[1] if len(pathParts) >= 2 else None

    return render_template_string(
        HTML_TEMPLATE,
        files=files,
        subfolders=subfolders,
        current_path=subpath.strip('/'),
        compressionEnabled=isCompressionEnabled(),
        landscapeMode=isLandscapeMode(),
        jpegQuality=getQuality(),
        artist=artist,
        comic=comic
    )

@app.route('/file/<path:filepath>')
def serve_file(filepath):
    absPath = resolveSafePath(filepath)
    if not os.path.isfile(absPath):
        abort(404)

    directory = os.path.dirname(absPath)
    filename = os.path.basename(absPath)
    ext = os.path.splitext(filename)[1].lower()

    if isCompressionEnabled() and ext in {'.png', '.jpg', '.jpeg', '.webp'}:
        try:
            Image.MAX_IMAGE_PIXELS = 25_000_000
            with Image.open(absPath) as img:
                buf = BytesIO()
                img = img.convert('RGB')
                img.save(buf, format='JPEG', quality=getQuality(), optimize=True)
                buf.seek(0)
                return send_file(buf, mimetype='image/jpeg', download_name=filename)
        except Exception:
            pass

    return send_from_directory(directory, filename)

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Comic Viewer</title>
    <style>
        body { font-family: sans-serif; margin: 0; background: #111; color: #eee; text-align: center; }
        .settingsBtn {
            display: inline-block;
            background: #222; color: #fff; border: 2px solid #555; border-radius: 6px;
            padding: 8px 12px; cursor: pointer; font-size: 0.9em; text-decoration: none;
            margin-bottom: 15px; transition: background 0.2s, transform 0.2s;
        }
        .settingsBtn:hover { background: #333; transform: scale(1.05); }

        .settingsContainer {
            margin-top: 10px;
            display: flex;
            justify-content: center;
            gap: 10px;
            align-items: center;
        }

        .gallery { display: flex; flex-wrap: wrap; justify-content: center; gap: 10px; padding: 10px; }
        .gallery img { width: 150px; height: auto; cursor: pointer; border: 2px solid #444; border-radius: 4px; transition: transform 0.2s ease; }
        .gallery {
            align-items: flex-start;
        }

        .thumb {
            position: relative;
            display: inline-block;
            transform-origin: center center;
            transition: transform 0.2s ease;
        }
        
        .thumb:hover {
            transform: scale(1.05);
        }


        .folders {
            margin: 20px auto;
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 10px;
            max-width: 400px;
        }

        .thumb {
            position: relative;
            display: inline-block;
        }
        
        .pageNumber {
            position: absolute;
            bottom: 4px;
            right: 4px;
            background: rgba(0, 0, 0, 0.75);
            color: #fff;
            font-size: 0.85em;
            padding: 2px 6px;
            border-radius: 4px;
            pointer-events: none;
            user-select: none;
            font-weight: bold;
        
            opacity: 0;
            transition: opacity 0.3s ease;
        }
        .pageNumber.visible {
            opacity: 1;
        }


        .folder-link {
            display: block;
            background: #222;
            color: #fff;
            padding: 12px 20px;
            border: 2px solid #555;
            border-radius: 6px;
            width: 100%;
            text-align: center;
            font-size: 1.1em;
            text-decoration: none;
            transition: background 0.2s, transform 0.2s;
        }

        .folder-link:hover {
            background: #333;
            transform: scale(1.02);
        }

        #viewerOverlay {
            display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%;
            background: rgba(0, 0, 0, 0.95); z-index: 9999; justify-content: center; align-items: center;
            overflow: hidden; flex-direction: column;
            -webkit-user-select: none;
            user-select: none;
        }

        #imageScrollContainer {
            width: 100vw;
            height: 100vh;
            overflow-y: auto;
            overflow-x: hidden;
            display: flex;
            justify-content: center;
            align-items: flex-start;
            -webkit-overflow-scrolling: touch;
            touch-action: pan-y;
        }

        #imageScrollContainer.landscape-mode {
            overflow-x: auto;
            touch-action: pan-x pan-y;
        }

        #viewerImage {
            width: auto;
            height: auto;
            max-width: 100%;
            max-height: none;
            object-fit: contain;
            user-select: none;
            -webkit-user-drag: none;
        }

        #viewerImage.landscape-mode {
            max-width: none;
            max-height: 100vh;
        }

        #viewerProgress {
            position: absolute; bottom: 0; left: 0; width: 100%;
            background: rgba(0, 0, 0, 0.6); color: white; font-size: 1.2em;
            padding: 10px 0; text-align: center; opacity: 0;
            transform: translateY(100%);
            transition: transform 0.3s ease, opacity 0.3s ease;
            -webkit-user-select: none;
            user-select: none;
        }

        #viewerProgress.visible {
            opacity: 1;
            transform: translateY(0%);
        }
    </style>
</head>
<body>
    <h1>{{ current_path or "Root" }}</h1>

    <div class="settingsContainer">
        <a href="{{ url_for('toggleCompression') }}" class="settingsBtn">
            Compression: {{ 'ON' if compressionEnabled else 'OFF' }}
        </a>
    
        <button id="landscapeBtn" class="settingsBtn" onclick="toggleLandscapeMode()">
            Landscape
        </button>

    
        <button class="settingsBtn" onclick="setQualityPrompt()">{{ jpegQuality }}</button>
    </div>

    <div class="folders">
        {% if current_path %}
            {% if '/' in current_path %}
                {% set parent_path = current_path.rsplit('/', 1)[0] %}
            {% else %}
                {% set parent_path = '' %}
            {% endif %}
            <a href="{{ url_for('list_files', subpath=parent_path) }}" class="folder-link">⬅ Back</a>
        {% endif %}
        {% for folder in subfolders %}
            <a href="{{ url_for('list_files', subpath=(current_path + '/' if current_path else '') + folder) }}" class="folder-link">{{ folder }}</a>
        {% endfor %}
    </div>

    <div class="gallery" id="gallery">
        {% for file in files %}
            <div class="thumb">
                <img src="{{ url_for('serve_file', filepath=(current_path + '/' if current_path else '') + file.name) }}"
                     data-index="{{ loop.index0 }}"
                     onclick="openViewer({{ loop.index0 }})">
                <div class="pageNumber">{{ loop.index }}</div>
            </div>
        {% endfor %}
    </div>


    <div id="viewerOverlay">
        <div id="imageScrollContainer">
            <img id="viewerImage" src="" draggable="false">
        </div>
        <div id="viewerProgress"></div>
    </div>

    <script>
        (function () {
            const scrollKey = "scrollPos:" + window.location.pathname;
    
            // Restore scroll position on load
            document.addEventListener("DOMContentLoaded", function () {
                const saved = sessionStorage.getItem(scrollKey);
                if (saved !== null) {
                    window.scrollTo(0, parseInt(saved, 10));
                }
            });

            // Save scroll position before navigating away
            window.addEventListener("beforeunload", function () {
                sessionStorage.setItem(scrollKey, window.scrollY.toString());
            });
        })();
        function setQualityPrompt() {
            const val = prompt("Enter JPEG Quality (1-100):", "{{ jpegQuality }}");
            if (val && !isNaN(val) && val >= 1 && val <= 100) {
                window.location.href = "/setQuality?q=" + encodeURIComponent(val);
            } else if (val !== null) {
                alert("Invalid value. Must be between 1 and 100.");
            }
        }
        function toggleLandscapeMode() {
            const img = document.getElementById('viewerImage');
            const scroll = document.getElementById('imageScrollContainer');
        
            landscapeEnabled = !landscapeEnabled;
        
            img.classList.toggle('landscape-mode', landscapeEnabled);
            scroll.classList.toggle('landscape-mode', landscapeEnabled);
        
            updateLandscapeButton();
        
            fetch('/toggleLandscape', {
                method: 'POST',
                credentials: 'same-origin'
            }).catch(() => {});
        }
        const images = Array.from(document.querySelectorAll('.gallery img'));
        const overlay = document.getElementById('viewerOverlay');
        const viewerImg = document.getElementById('viewerImage');
        const scrollContainer = document.getElementById('imageScrollContainer');
        const progressBar = document.getElementById('viewerProgress');
        let currentIndex = 0;
        
        // Set landscape mode based on cookie
        {% if landscapeMode %}
        viewerImg.classList.add('landscape-mode');
        scrollContainer.classList.add('landscape-mode');
        {% else %}
        viewerImg.classList.remove('landscape-mode');
        scrollContainer.classList.remove('landscape-mode');
        {% endif %}
        let landscapeEnabled = {{ 'true' if landscapeMode else 'false' }};
        let touchStartX = 0, touchEndX = 0;
        let touchStartY = 0, touchEndY = 0;
        let longPressTimer = null;
        let isLongPress = false;
        let touchStartRatioY = 0;
        const LONG_PRESS_DURATION = 600;

        function updateProgress() { progressBar.textContent = (currentIndex + 1) + "/" + images.length; }
        function updateLandscapeButton() {
            const btn = document.getElementById('landscapeBtn');
            btn.textContent = "Landscape: " + (landscapeEnabled ? "ON" : "OFF");
        }

        images.forEach(img => {
            const number = img.parentElement.querySelector('.pageNumber');
        
            if (img.complete && img.naturalWidth !== 0) {
                number.classList.add('visible');
            } else {
                img.addEventListener('load', () => {
                    number.classList.add('visible');
                }, { once: true });
            }
        });

        updateLandscapeButton();

        let pingTimeout = null;
        
        function pingServer() {
            if (pingTimeout) clearTimeout(pingTimeout);
        
            // Wait 100ms after last navigation before sending ping
            pingTimeout = setTimeout(() => {
                fetch('/pingPage', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    keepalive: true,
                    body: JSON.stringify({
                        artist: "{{ artist }}",
                        comic: "{{ comic }}",
                        page: currentIndex + 1,
                        pageCount: images.length
                    })
                }).catch(() => {});
            }, 150); // adjust delay as needed
        }

        function openViewer(index) {
            currentIndex = index;
            viewerImg.src = images[index].src;
            overlay.style.display = 'flex';
            document.body.style.overflow = 'hidden';
            scrollContainer.scrollTop = 0;
            updateProgress();
        
            // Ping only after the image successfully loaded
            if (viewerImg.complete && viewerImg.naturalWidth !== 0) {
                pingServer();
            } else {
                viewerImg.addEventListener('load', pingServer, { once: true });
            }
        }

        function closeViewer() {
            overlay.style.display = 'none';
            document.body.style.overflow = '';
            progressBar.classList.remove('visible');
        }

        function navigate(direction) {
            currentIndex = (currentIndex + direction + images.length) % images.length;
            viewerImg.src = images[currentIndex].src;
            scrollContainer.scrollTop = 0;
            updateProgress();
            pingServer();
        }


        function toggleProgressBar() { progressBar.classList.toggle('visible'); }

        function cancelLongPress() { clearTimeout(longPressTimer); longPressTimer = null; }

        overlay.addEventListener('touchstart', function(e) {
            isLongPress = false;
            const touch = e.changedTouches[0];
            touchStartX = touch.screenX;
            touchStartY = touch.screenY;
            touchStartRatioY = touch.clientY / window.innerHeight;
            if (touchStartRatioY > 0.5) {
                e.preventDefault();
                longPressTimer = setTimeout(() => {
                    isLongPress = true;
                    toggleProgressBar();
                }, LONG_PRESS_DURATION);
            } else cancelLongPress();
        }, {passive: false});

        overlay.addEventListener('touchmove', function(e) {
            if (touchStartRatioY > 0.5) { e.preventDefault(); cancelLongPress(); }
        }, {passive: false});

        overlay.addEventListener('touchcancel', cancelLongPress);

        overlay.addEventListener('touchend', function(e) {
            cancelLongPress();
            const touch = e.changedTouches[0];
            touchEndX = touch.screenX;
            touchEndY = touch.screenY;
            const deltaX = touchEndX - touchStartX;
            const deltaY = touchEndY - touchStartY;
            if (isLongPress) return;
            if (touchStartRatioY <= 0.5) return;
            if (Math.abs(deltaX) > 30 && Math.abs(deltaX) > Math.abs(deltaY)) navigate(deltaX > 0 ? -1 : 1);
            else if (deltaY > 50 && Math.abs(deltaY) > Math.abs(deltaX)) closeViewer();
            else if (Math.abs(deltaX) < 10 && Math.abs(deltaY) < 10) navigate(1);
        });

        viewerImg.addEventListener('mousedown', function(e) {
            e.preventDefault();
            isLongPress = false;
            longPressTimer = setTimeout(() => { isLongPress = true; toggleProgressBar(); }, LONG_PRESS_DURATION);
        });
        viewerImg.addEventListener('mousemove', cancelLongPress);
        viewerImg.addEventListener('mouseup', cancelLongPress);

        document.addEventListener('keydown', function(e) {
            if (!overlay.style.display.includes('flex')) return;
            if (e.key === 'ArrowLeft') navigate(-1);
            if (e.key === 'ArrowRight') navigate(1);
            if (e.key === 'Escape') closeViewer();
        });
    </script>
</body>
</html>
'''

if __name__ == '__main__':
    os.makedirs(BASE_DIR, exist_ok=True)
    app.run(host='0.0.0.0', port=5008, request_handler=QuietHandler, debug=True, use_reloader=True)