#!/usr/bin/env python3
"""
Remote Access Script for Windows
Provides screen sharing and remote control via web interface
"""

import os
import sys
import time
import json
import base64
import threading
import signal
from io import BytesIO
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room
import mss
import mss.tools
from PIL import Image
import pyautogui
import cv2
import numpy as np
from datetime import datetime

# Configure pyautogui for safety
pyautogui.FAILSAFE = False  # Disable failsafe for remote access
pyautogui.PAUSE = 0.01

class RemoteAccessServer:
    def __init__(self, host='0.0.0.0', port=7003, quality=70, fps=15):
        self.host = host
        self.port = port
        self.quality = quality  # JPEG quality (1-100)
        self.fps = fps
        self.screen_width, self.screen_height = pyautogui.size()
        
        # Initialize Flask app
        self.app = Flask(__name__)
        self.app.config['SECRET_KEY'] = 'remote_access_secret_key'
        self.app.config['SOCKETIO_ASYNC_MODE'] = 'threading'
        
        self.socketio = SocketIO(
            self.app, 
            cors_allowed_origins="*", 
            async_mode='threading',
            logger=False,
            engineio_logger=False,
            ping_timeout=60,
            ping_interval=25,
            max_http_buffer_size=1e8
        )
        
        # Setup routes and socket events
        self.setup_routes()
        self.setup_socket_events()
        
        # Control variables
        self.is_streaming = False
        self.stream_thread = None
        self.connected_clients = set()
        self.stream_lock = threading.Lock()
        self.server_running = False
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
    
    def signal_handler(self, signum, frame):
        """Handle graceful shutdown signals"""
        print(f"Received signal {signum}. Shutting down server...")
        self.server_running = False
        self.stop_streaming()
        sys.exit(0)
    
    def setup_routes(self):
        @self.app.route('/')
        def index():
            return render_template('remote_control.html')
            
        @self.app.route('/api/screen_info')
        def screen_info():
            return jsonify({
                'width': self.screen_width,
                'height': self.screen_height,
                'quality': self.quality,
                'fps': self.fps
            })
            
        @self.app.route('/api/update_settings', methods=['POST'])
        def update_settings():
            data = request.json
            if 'quality' in data:
                self.quality = max(1, min(100, int(data['quality'])))
            if 'fps' in data:
                self.fps = max(1, min(30, int(data['fps'])))
            return jsonify({'status': 'success'})

        @self.app.route('/api/test_capture')
        def test_capture():
            """Test endpoint to verify screen capture is working"""
            try:
                img_data = self.capture_screen()
                if img_data:
                    return jsonify({
                        'status': 'success',
                        'image_length': len(img_data),
                        'message': 'Screen capture working'
                    })
                else:
                    return jsonify({
                        'status': 'error',
                        'message': 'Failed to capture screen'
                    }), 500
            except Exception as e:
                return jsonify({
                    'status': 'error',
                    'message': f'Capture error: {str(e)}'
                }), 500
    
    def validate_coordinates(self, x, y):
        """Validate coordinates are within screen bounds"""
        try:
            x = int(x)
            y = int(y)
            return (0 <= x <= self.screen_width and 0 <= y <= self.screen_height)
        except (ValueError, TypeError):
            return False
    
    def setup_socket_events(self):
        @self.socketio.on('connect')
        def handle_connect():
            client_id = request.sid
            print(f"Client connected: {client_id}")
            
            with self.stream_lock:
                self.connected_clients.add(client_id)
            
            join_room('stream_room')
            
            emit('screen_info', {
                'width': self.screen_width,
                'height': self.screen_height,
                'quality': self.quality,
                'fps': self.fps
            })
            
            # Start streaming if not already started
            if not self.is_streaming:
                self.start_streaming()
        
        @self.socketio.on('disconnect')
        def handle_disconnect():
            client_id = request.sid
            print(f"Client disconnected: {client_id}")
            
            with self.stream_lock:
                self.connected_clients.discard(client_id)
            
            leave_room('stream_room')
            
            # Stop streaming if no clients connected
            if not self.connected_clients:
                self.stop_streaming()
        
        @self.socketio.on('error')
        def handle_error(error):
            print(f"WebSocket error: {error}")
        
        @self.socketio.on('connect_error')
        def handle_connect_error(error):
            print(f"WebSocket connection error: {error}")
        
        @self.socketio.on('start_stream')
        def handle_start_stream():
            self.start_streaming()
        
        @self.socketio.on('stop_stream')
        def handle_stop_stream():
            self.stop_streaming()
        
        @self.socketio.on('mouse_move')
        def handle_mouse_move(data):
            try:
                x = data.get('x')
                y = data.get('y')
                
                if x is None or y is None:
                    print(f"Invalid mouse coordinates: x={x}, y={y}")
                    return
                
                if not self.validate_coordinates(x, y):
                    print(f"Mouse coordinates out of bounds: x={x}, y={y}, screen={self.screen_width}x{self.screen_height}")
                    return
                
                pyautogui.moveTo(int(x), int(y))
            except Exception as e:
                print(f"Mouse move error: {e}")
        
        @self.socketio.on('mouse_click')
        def handle_mouse_click(data):
            try:
                x = data.get('x')
                y = data.get('y')
                button = data.get('button', 'left')
                
                if x is None or y is None:
                    print(f"Invalid click coordinates: x={x}, y={y}")
                    return
                
                if not self.validate_coordinates(x, y):
                    print(f"Click coordinates out of bounds: x={x}, y={y}, screen={self.screen_width}x{self.screen_height}")
                    return
                
                # Validate button
                if button not in ['left', 'right', 'middle']:
                    button = 'left'
                
                pyautogui.click(int(x), int(y), button=button)
            except Exception as e:
                print(f"Mouse click error: {e}")
        
        @self.socketio.on('key_press')
        def handle_key_press(data):
            try:
                key = data.get('key')
                if not key:
                    print("No key provided")
                    return
                
                # List of safe keys that can be pressed
                safe_keys = [
                    'backspace', 'enter', 'tab', 'escape', 'space', 'delete',
                    'up', 'down', 'left', 'right', 'home', 'end', 'pageup', 'pagedown',
                    'f1', 'f2', 'f3', 'f4', 'f5', 'f6', 'f7', 'f8', 'f9', 'f10', 'f11', 'f12',
                    'ctrl', 'alt', 'shift', 'win', 'capslock', 'numlock', 'scrolllock'
                ]
                
                # Allow single characters (letters, numbers, symbols)
                if len(key) == 1 and key.isprintable():
                    pyautogui.press(key)
                elif key in safe_keys:
                    pyautogui.press(key)
                else:
                    print(f"Unsafe key attempted: {key}")
            except Exception as e:
                print(f"Key press error: {e}")
        
        @self.socketio.on('text_input')
        def handle_text_input(data):
            try:
                text = data.get('text', '')
                if not text:
                    print("No text provided")
                    return
                
                # Limit text length to prevent abuse
                if len(text) > 1000:
                    print(f"Text too long: {len(text)} characters")
                    return
                
                # Only allow printable characters
                if all(c.isprintable() for c in text):
                    pyautogui.write(text)
                else:
                    print("Text contains non-printable characters")
            except Exception as e:
                print(f"Text input error: {e}")
    
    def capture_screen(self):
        """Capture screen and return as base64 encoded JPEG"""
        try:
            # Create mss instance in the current thread
            with mss.mss() as sct:
                monitor = sct.monitors[1]  # Primary monitor
                # Capture screen
                screenshot = sct.grab(monitor)
                # Convert to PIL Image
                img = Image.frombytes('RGB', screenshot.size, screenshot.rgb)
                
                # Resize for better performance (optional)
                # img = img.resize((img.width // 2, img.height // 2), Image.Resampling.LANCZOS)
                
                # Convert to JPEG with specified quality
                buffer = BytesIO()
                img.save(buffer, format='JPEG', quality=self.quality, optimize=True)
                
                # Encode to base64
                img_str = base64.b64encode(buffer.getvalue()).decode('utf-8')
                return img_str
        except Exception as e:
            print(f"Screen capture error: {e}")
            return None
    
    def stream_screen(self):
        """Stream screen captures to connected clients"""
        frame_time = 1.0 / self.fps
        frame_count = 0
        error_count = 0
        max_errors = 5
        
        print("Stream thread started")
        
        while self.is_streaming and self.server_running:
            start_time = time.time()
            
            # Check if we have connected clients
            with self.stream_lock:
                client_count = len(self.connected_clients)
                if client_count == 0:
                    time.sleep(0.1)
                    continue
            
            # Capture and send screen
            img_data = self.capture_screen()
            if img_data:
                frame_count += 1
                try:
                    # Only emit if server is running and we have clients
                    if self.server_running and client_count > 0:
                        self.socketio.emit('screen_update', {
                            'image': img_data,
                            'timestamp': datetime.now().isoformat(),
                            'frame': frame_count
                        }, room='stream_room')
                        error_count = 0  # Reset error count on success
                except Exception as e:
                    error_count += 1
                    print(f"Error sending frame {frame_count}: {e}")
                    
                    # If too many consecutive errors, stop streaming
                    if error_count >= max_errors:
                        print(f"Too many consecutive errors ({error_count}), stopping stream")
                        self.stop_streaming()
                        break
                    
                    # If it's a WebSocket error, wait a bit longer
                    if "write() before start_response" in str(e) or "WebSocket" in str(e):
                        time.sleep(0.5)
                        continue
            else:
                print("Failed to capture screen")
            
            # Maintain FPS
            elapsed = time.time() - start_time
            if elapsed < frame_time:
                time.sleep(frame_time - elapsed)
        
        print("Stream thread stopped")
    
    def start_streaming(self):
        """Start screen streaming"""
        with self.stream_lock:
            if not self.is_streaming:
                self.is_streaming = True
                self.stream_thread = threading.Thread(target=self.stream_screen, daemon=True)
                self.stream_thread.start()
                print("Screen streaming started")
    
    def stop_streaming(self):
        """Stop screen streaming"""
        with self.stream_lock:
            self.is_streaming = False
        
        if self.stream_thread:
            self.stream_thread.join(timeout=1)
        print("Screen streaming stopped")
    
    def run(self):
        """Start the remote access server"""
        print(f"Starting Remote Access Server on {self.host}:{self.port}")
        print(f"Screen resolution: {self.screen_width}x{self.screen_height}")
        print(f"Quality: {self.quality}%, FPS: {self.fps}")
        print(f"Access the remote control interface at: http://localhost:{self.port}")
        
        self.server_running = True
        
        try:
            self.socketio.run(
                self.app, 
                host=self.host, 
                port=self.port, 
                debug=False, 
                allow_unsafe_werkzeug=True,
                use_reloader=False
            )
        except KeyboardInterrupt:
            print("\nShutting down server...")
            self.server_running = False
            self.stop_streaming()
        except Exception as e:
            print(f"Server error: {e}")
            self.server_running = False
            self.stop_streaming()
        finally:
            self.server_running = False

def create_templates_directory():
    """Create templates directory and HTML file"""
    os.makedirs('templates', exist_ok=True)
    
    html_content = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Remote Access Control</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #1a1a1a;
            color: #ffffff;
            overflow: hidden;
        }
        
        .header {
            background: #2d2d2d;
            padding: 10px 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 2px solid #4a4a4a;
        }
        
        .controls {
            display: flex;
            gap: 10px;
            align-items: center;
        }
        
        .control-group {
            display: flex;
            align-items: center;
            gap: 5px;
        }
        
        .control-group label {
            font-size: 12px;
            color: #cccccc;
        }
        
        .control-group input, .control-group select {
            padding: 5px;
            border: 1px solid #4a4a4a;
            background: #3a3a3a;
            color: #ffffff;
            border-radius: 3px;
        }
        
        button {
            padding: 8px 16px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-weight: bold;
            transition: all 0.2s;
        }
        
        .btn-primary {
            background: #007acc;
            color: white;
        }
        
        .btn-primary:hover {
            background: #005a9e;
        }
        
        .btn-danger {
            background: #dc3545;
            color: white;
        }
        
        .btn-danger:hover {
            background: #c82333;
        }
        
        .btn-success {
            background: #28a745;
            color: white;
        }
        
        .btn-success:hover {
            background: #218838;
        }
        
        .screen-container {
            position: relative;
            width: 100vw;
            height: calc(100vh - 60px);
            background: #000000;
            overflow: hidden;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        
        #screenCanvas {
            display: block;
            max-width: 100%;
            max-height: 100%;
            object-fit: contain;
            cursor: crosshair;
        }
        
        .loading {
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            font-size: 18px;
            color: #cccccc;
        }
    </style>
</head>
<body>
    <div class="header">
        <h2>Remote Access Control</h2>
        <div class="controls">
            <div class="control-group">
                <label>Quality:</label>
                <input type="range" id="qualitySlider" min="1" max="100" value="70">
                <span id="qualityValue">70%</span>
            </div>
            <div class="control-group">
                <label>FPS:</label>
                <select id="fpsSelect">
                    <option value="5">5 FPS</option>
                    <option value="10">10 FPS</option>
                    <option value="15" selected>15 FPS</option>
                    <option value="20">20 FPS</option>
                    <option value="30">30 FPS</option>
                </select>
            </div>
            <button id="startBtn" class="btn-success">Start Stream</button>
            <button id="stopBtn" class="btn-danger" style="display: none;">Stop Stream</button>
        </div>
    </div>
    
    <div class="screen-container">
        <div class="loading" id="loadingText">Connecting...</div>
        <img id="screenCanvas" style="display: none;">
    </div>

    <script>
        let socket;
        let canvas = document.getElementById('screenCanvas');
        let loadingText = document.getElementById('loadingText');
        let isStreaming = false;
        let frameCount = 0;
        let lastFpsTime = Date.now();
        let fpsCounter = 0;
        
        // Initialize connection
        function initConnection() {
            console.log('Initializing connection...');
            socket = io({
                transports: ['websocket', 'polling'],
                upgrade: true,
                rememberUpgrade: true,
                timeout: 20000,
                reconnection: true,
                reconnectionAttempts: 5,
                reconnectionDelay: 1000
            });
            
            socket.on('connect', function() {
                console.log('Connected to server');
                loadingText.textContent = 'Waiting for stream...';
            });
            
            socket.on('disconnect', function() {
                console.log('Disconnected from server');
                loadingText.textContent = 'Disconnected';
                loadingText.style.display = 'block';
                canvas.style.display = 'none';
                stopStream();
            });
            
            socket.on('connect_error', function(error) {
                console.error('Connection error:', error);
            });
            
            socket.on('reconnect', function(attemptNumber) {
                console.log('Reconnected after', attemptNumber, 'attempts');
            });
            
            socket.on('reconnect_error', function(error) {
                console.error('Reconnection error:', error);
            });
            
            socket.on('screen_info', function(data) {
                console.log('Received screen info:', data);
            });
            
            socket.on('screen_update', function(data) {
                console.log('Received frame:', data.frame);
                displayScreen(data.image, data.frame);
                updateFps();
            });
        }
        
        function displayScreen(imageData, frame) {
            console.log('Displaying frame:', frame, 'Image data length:', imageData ? imageData.length : 0);
            
            if (!imageData) {
                console.error('No image data received');
                return;
            }
            
            if (loadingText.style.display !== 'none') {
                loadingText.style.display = 'none';
                canvas.style.display = 'block';
            }
            
            canvas.onload = function() {
                console.log('Image loaded successfully, frame:', frame);
            };
            
            canvas.onerror = function() {
                console.error('Failed to load image');
                loadingText.textContent = 'Failed to load image';
                loadingText.style.display = 'block';
                canvas.style.display = 'none';
            };
            
            try {
                canvas.src = 'data:image/jpeg;base64,' + imageData;
            } catch (error) {
                console.error('Error setting image source:', error);
            }
        }
        
        function updateFps() {
            fpsCounter++;
            const now = Date.now();
            if (now - lastFpsTime >= 1000) {
                fpsCounter = 0;
                lastFpsTime = now;
            }
        }
        
        function startStream() {
            if (socket && socket.connected) {
                socket.emit('start_stream');
                isStreaming = true;
                document.getElementById('startBtn').style.display = 'none';
                document.getElementById('stopBtn').style.display = 'inline-block';
            }
        }
        
        function stopStream() {
            if (socket && socket.connected) {
                socket.emit('stop_stream');
            }
            isStreaming = false;
            document.getElementById('startBtn').style.display = 'inline-block';
            document.getElementById('stopBtn').style.display = 'none';
        }
        
        // Mouse and keyboard control
        function setupControls() {
            function validateAndSendMouseEvent(event, eventType) {
                if (!isStreaming || !socket || !socket.connected) return;
                
                const rect = canvas.getBoundingClientRect();
                const scaleX = canvas.naturalWidth / rect.width;
                const scaleY = canvas.naturalHeight / rect.height;
                
                let clientX, clientY;
                
                if (event.touches && event.touches[0]) {
                    // Touch event
                    clientX = event.touches[0].clientX;
                    clientY = event.touches[0].clientY;
                } else {
                    // Mouse event
                    clientX = event.clientX;
                    clientY = event.clientY;
                }
                
                const x = Math.round((clientX - rect.left) * scaleX);
                const y = Math.round((clientY - rect.top) * scaleY);
                
                // Validate coordinates are within bounds
                if (x < 0 || y < 0 || x > canvas.naturalWidth || y > canvas.naturalHeight) {
                    console.warn('Coordinates out of bounds:', x, y);
                    return;
                }
                
                if (eventType === 'move') {
                    socket.emit('mouse_move', {x: x, y: y});
                } else if (eventType === 'click') {
                    const button = event.button === 2 ? 'right' : 'left';
                    socket.emit('mouse_click', {x: x, y: y, button: button});
                }
            }
            
            canvas.addEventListener('mousemove', function(e) {
                validateAndSendMouseEvent(e, 'move');
            });
            
            canvas.addEventListener('click', function(e) {
                validateAndSendMouseEvent(e, 'click');
            });
            
            canvas.addEventListener('contextmenu', function(e) {
                e.preventDefault();
            });
            
            // Touch events for mobile
            canvas.addEventListener('touchstart', function(e) {
                e.preventDefault();
                validateAndSendMouseEvent(e, 'click');
            });
            
            // Keyboard control
            document.addEventListener('keydown', function(e) {
                if (isStreaming && socket && socket.connected) {
                    e.preventDefault();
                    
                    let key = e.key;
                    if (e.key === 'Backspace') key = 'backspace';
                    else if (e.key === 'Enter') key = 'enter';
                    else if (e.key === 'Tab') key = 'tab';
                    else if (e.key === 'Escape') key = 'escape';
                    else if (e.key === ' ') key = 'space';
                    else if (e.key === 'Delete') key = 'delete';
                    else if (e.key === 'ArrowUp') key = 'up';
                    else if (e.key === 'ArrowDown') key = 'down';
                    else if (e.key === 'ArrowLeft') key = 'left';
                    else if (e.key === 'ArrowRight') key = 'right';
                    else if (e.key === 'Home') key = 'home';
                    else if (e.key === 'End') key = 'end';
                    else if (e.key === 'PageUp') key = 'pageup';
                    else if (e.key === 'PageDown') key = 'pagedown';
                    
                    socket.emit('key_press', {key: key});
                }
            });
            
            // Text input
            document.addEventListener('paste', function(e) {
                if (isStreaming && socket && socket.connected) {
                    e.preventDefault();
                    const text = e.clipboardData.getData('text');
                    if (text && text.length <= 1000) {
                        socket.emit('text_input', {text: text});
                    }
                }
            });
        }
        
        // Settings controls
        function setupSettings() {
            const qualitySlider = document.getElementById('qualitySlider');
            const qualityValue = document.getElementById('qualityValue');
            const fpsSelect = document.getElementById('fpsSelect');
            
            qualitySlider.addEventListener('input', function() {
                const quality = this.value;
                qualityValue.textContent = quality + '%';
                document.getElementById('currentQuality').textContent = quality + '%';
                
                if (socket && socket.connected) {
                    fetch('/api/update_settings', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({quality: parseInt(quality)})
                    });
                }
            });
            
            fpsSelect.addEventListener('change', function() {
                const fps = this.value;
                document.getElementById('currentFps').textContent = fps + ' FPS';
                
                if (socket && socket.connected) {
                    fetch('/api/update_settings', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({fps: parseInt(fps)})
                    });
                }
            });
            
            document.getElementById('startBtn').addEventListener('click', startStream);
            document.getElementById('stopBtn').addEventListener('click', stopStream);
        }
        
        // Initialize everything
        document.addEventListener('DOMContentLoaded', function() {
            initConnection();
            setupControls();
            setupSettings();
        });
    </script>
</body>
</html>'''
    
    with open('templates/remote_control.html', 'w', encoding='utf-8') as f:
        f.write(html_content)

def main():
    """Main function"""
    print("Remote Access Script for Windows")
    print("=" * 40)
    
    # Create templates directory and HTML file
    create_templates_directory()
    
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description='Remote Access Server')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to (default: 0.0.0.0)')
    parser.add_argument('--port', type=int, default=7003, help='Port to bind to (default: 7003)')
    parser.add_argument('--quality', type=int, default=70, help='JPEG quality 1-100 (default: 70)')
    parser.add_argument('--fps', type=int, default=15, help='Frames per second (default: 15)')
    
    args = parser.parse_args()
    
    # Create and run server
    server = RemoteAccessServer(
        host=args.host,
        port=args.port,
        quality=args.quality,
        fps=args.fps
    )
    
    try:
        server.run()
    except KeyboardInterrupt:
        print("\nServer stopped by user")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main() 