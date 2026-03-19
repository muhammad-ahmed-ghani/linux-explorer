import http.server
import socketserver
import urllib.parse
import os
import zipfile
import tempfile
import shutil
import json
import socket
import sys
import base64
import webbrowser
from threading import Timer
try:
    import psutil
except ImportError:
    psutil = None

try:
    from pynvml import *
    nvmlInit()
    HAS_GPU = True
except (ImportError, Exception):
    HAS_GPU = False

# Port range
PORT_START = 7701
PORT_END = 7799

# Get the directory of this script to find viewer.html
PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
VIEWER_HTML_PATH = os.path.join(PACKAGE_DIR, 'viewer.html')
FAVICON_PATH = os.path.join(PACKAGE_DIR, 'favicon.jpg')

def get_dir_size(path):
    total = 0
    try:
        with os.scandir(path) as it:
            for entry in it:
                if entry.is_file():
                    total += entry.stat().st_size
                elif entry.is_dir():
                    total += get_dir_size(entry.path)
    except Exception:
        pass
    return total

class CustomHandler(http.server.SimpleHTTPRequestHandler):
    def do_DELETE(self):
        parsed_path = urllib.parse.urlparse(self.path)

        if parsed_path.path == '/api/delete':
            try:
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data)

                paths = data.get('paths', [])
                if not paths:
                    self.send_error(400, "No paths provided")
                    return

                deleted = []
                errors = []

                for path in paths:
                    unquoted_path = urllib.parse.unquote(path).lstrip('/')
                    target = os.path.normpath(unquoted_path)

                    if '..' in target:
                        errors.append({"path": path, "error": "Forbidden"})
                        continue

                    try:
                        if os.path.isfile(target):
                            os.remove(target)
                            deleted.append(path)
                        elif os.path.isdir(target):
                            shutil.rmtree(target)
                            deleted.append(path)
                        else:
                            errors.append({"path": path, "error": "Not found"})
                    except Exception as e:
                        errors.append({"path": path, "error": str(e)})

                resp = json.dumps({"status": "success", "deleted": deleted, "errors": errors}).encode('utf-8')
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(resp)))
                self.end_headers()
                self.wfile.write(resp)
            except Exception as e:
                self.send_error(500, str(e))
        else:
            self.send_error(404, "Not Found")

    def do_POST(self):
        parsed_path = urllib.parse.urlparse(self.path)

        if parsed_path.path == '/api/save':
            try:
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data)
                
                file_path = data.get('path')
                image_data = data.get('data') # base64

                if not file_path or not image_data:
                    self.send_error(400, "Missing path or data")
                    return

                # Decode base64
                if ';base64,' in image_data:
                    header, image_data = image_data.split(';base64,')
                
                binary_data = base64.b64decode(image_data)
                
                # Resolve path relative to CWD
                unquoted_path = urllib.parse.unquote(file_path).lstrip('/')
                target_file = os.path.normpath(unquoted_path)
                
                # Security: prevent directory traversal
                if '..' in target_file:
                    self.send_error(403, "Forbidden")
                    return

                with open(target_file, 'wb') as f:
                    f.write(binary_data)

                resp = json.dumps({"status": "success"}).encode('utf-8')
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(resp)))
                self.end_headers()
                self.wfile.write(resp)
            except Exception as e:
                self.send_error(500, str(e))
        
        elif parsed_path.path == '/api/upload':
            try:
                content_type = self.headers.get('Content-Type')
                if not content_type or 'multipart/form-data' not in content_type:
                    self.send_error(400, "Content-Type must be multipart/form-data")
                    return

                boundary = content_type.split('boundary=')[1].encode()
                content_length = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(content_length)

                parts = body.split(b'--' + boundary)
                target_path = "."
                files_to_save = []

                import re
                for part in parts:
                    if not part or part == b'--\r\n' or part == b'--' or part == b'\r\n': continue

                    if b'\r\n\r\n' not in part: continue
                    header_part, content = part.split(b'\r\n\r\n', 1)
                    content = content.rsplit(b'\r\n', 1)[0]

                    header_str = header_part.decode('utf-8', errors='ignore')

                    if 'name="path"' in header_str:
                        target_path = content.decode('utf-8').strip()
                    elif 'filename="' in header_str:
                        match = re.search(r'filename="([^"]+)"', header_str)
                        if match:
                            filename = match.group(1)
                            files_to_save.append((filename, content))

                target_dir = os.path.normpath(target_path).lstrip('/')
                if '..' in target_dir:
                    self.send_error(403, "Forbidden")
                    return

                # If target_dir is '.', it's the current directory
                if target_dir == '.' or not target_dir:
                    target_dir = os.getcwd()
                else:
                    if not os.path.exists(target_dir):
                        os.makedirs(target_dir, exist_ok=True)

                for filename, content in files_to_save:
                    save_path = os.path.join(target_dir, filename)
                    with open(save_path, 'wb') as f:
                        f.write(content)

                resp = json.dumps({"status": "success", "count": len(files_to_save)}).encode('utf-8')
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(resp)))
                self.end_headers()
                self.wfile.write(resp)
            except Exception as e:
                self.send_error(500, str(e))

        elif parsed_path.path == '/api/rename':
            try:
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data)

                old_path = data.get('oldPath')
                new_name = data.get('newName')

                if not old_path or not new_name:
                    self.send_error(400, "Missing oldPath or newName")
                    return

                old_unquoted = urllib.parse.unquote(old_path).lstrip('/')
                old_target = os.path.normpath(old_unquoted)

                if '..' in old_target or '..' in new_name:
                    self.send_error(403, "Forbidden")
                    return

                # Build new path in same directory
                old_dir = os.path.dirname(old_target) if os.path.dirname(old_target) else '.'
                new_target = os.path.join(old_dir, new_name)

                if not os.path.exists(old_target):
                    self.send_error(404, "Source not found")
                    return

                if os.path.exists(new_target):
                    self.send_error(409, "Target already exists")
                    return

                os.rename(old_target, new_target)

                resp = json.dumps({"status": "success"}).encode('utf-8')
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(resp)))
                self.end_headers()
                self.wfile.write(resp)
            except Exception as e:
                self.send_error(500, str(e))

        elif parsed_path.path == '/api/mkdir':
            try:
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data)

                path = data.get('path')
                folder_name = data.get('name')

                if not folder_name:
                    self.send_error(400, "Missing folder name")
                    return

                unquoted_path = urllib.parse.unquote(path).lstrip('/') if path else '.'
                target_dir = os.path.normpath(unquoted_path)

                if '..' in target_dir or '..' in folder_name:
                    self.send_error(403, "Forbidden")
                    return

                new_folder = os.path.join(target_dir, folder_name)

                if os.path.exists(new_folder):
                    self.send_error(409, "Folder already exists")
                    return

                os.makedirs(new_folder, exist_ok=False)

                resp = json.dumps({"status": "success"}).encode('utf-8')
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(resp)))
                self.end_headers()
                self.wfile.write(resp)
            except Exception as e:
                self.send_error(500, str(e))

        elif parsed_path.path == '/api/copy':
            try:
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data)

                sources = data.get('sources', [])
                destination = data.get('destination')

                if not sources or not destination:
                    self.send_error(400, "Missing sources or destination")
                    return

                dest_unquoted = urllib.parse.unquote(destination).lstrip('/')
                dest_target = os.path.normpath(dest_unquoted)

                if '..' in dest_target:
                    self.send_error(403, "Forbidden")
                    return

                if not os.path.exists(dest_target) or not os.path.isdir(dest_target):
                    self.send_error(404, "Destination directory not found")
                    return

                copied = []
                errors = []

                for src in sources:
                    src_unquoted = urllib.parse.unquote(src).lstrip('/')
                    src_target = os.path.normpath(src_unquoted)

                    if '..' in src_target:
                        errors.append({"path": src, "error": "Forbidden"})
                        continue

                    try:
                        basename = os.path.basename(src_target)
                        dest_path = os.path.join(dest_target, basename)

                        if os.path.isfile(src_target):
                            shutil.copy2(src_target, dest_path)
                            copied.append(src)
                        elif os.path.isdir(src_target):
                            shutil.copytree(src_target, dest_path)
                            copied.append(src)
                        else:
                            errors.append({"path": src, "error": "Not found"})
                    except Exception as e:
                        errors.append({"path": src, "error": str(e)})

                resp = json.dumps({"status": "success", "copied": copied, "errors": errors}).encode('utf-8')
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(resp)))
                self.end_headers()
                self.wfile.write(resp)
            except Exception as e:
                self.send_error(500, str(e))

        elif parsed_path.path == '/api/move':
            try:
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data)

                sources = data.get('sources', [])
                destination = data.get('destination')

                if not sources or not destination:
                    self.send_error(400, "Missing sources or destination")
                    return

                dest_unquoted = urllib.parse.unquote(destination).lstrip('/')
                dest_target = os.path.normpath(dest_unquoted)

                if '..' in dest_target:
                    self.send_error(403, "Forbidden")
                    return

                if not os.path.exists(dest_target) or not os.path.isdir(dest_target):
                    self.send_error(404, "Destination directory not found")
                    return

                moved = []
                errors = []

                for src in sources:
                    src_unquoted = urllib.parse.unquote(src).lstrip('/')
                    src_target = os.path.normpath(src_unquoted)

                    if '..' in src_target:
                        errors.append({"path": src, "error": "Forbidden"})
                        continue

                    try:
                        basename = os.path.basename(src_target)
                        dest_path = os.path.join(dest_target, basename)

                        if os.path.exists(src_target):
                            shutil.move(src_target, dest_path)
                            moved.append(src)
                        else:
                            errors.append({"path": src, "error": "Not found"})
                    except Exception as e:
                        errors.append({"path": src, "error": str(e)})

                resp = json.dumps({"status": "success", "moved": moved, "errors": errors}).encode('utf-8')
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(resp)))
                self.end_headers()
                self.wfile.write(resp)
            except Exception as e:
                self.send_error(500, str(e))

        else:
            self.send_error(404, "Not Found")

    def do_GET(self):
        parsed_path = urllib.parse.urlparse(self.path)
        
        # API: Download
        if parsed_path.path == '/api/download':
            query = urllib.parse.parse_qs(parsed_path.query)
            dir_name = query.get('dir', [''])[0]
            dir_name = os.path.normpath(urllib.parse.unquote(dir_name)).lstrip('/')
            
            if not dir_name or dir_name == '.' or dir_name == '':
                target_dir = '.'
                download_name = 'root_directory.zip'
            else:
                target_dir = urllib.parse.unquote(dir_name)
                download_name = f"{os.path.basename(target_dir.rstrip('/'))}.zip"

            if not os.path.exists(target_dir) or not os.path.isdir(target_dir):
                self.send_error(404, "Directory not found")
                return

            fd, temp_path = tempfile.mkstemp(suffix='.zip')
            os.close(fd)
            
            try:
                with zipfile.ZipFile(temp_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                    for root, dirs, files in os.walk(target_dir):
                        dirs[:] = [d for d in dirs if not d.startswith('.')]
                        for file in files:
                            if file.startswith('.'): continue
                            file_path = os.path.join(root, file)
                            arcname = os.path.relpath(file_path, '.' if target_dir == '.' else target_dir)
                            zf.write(file_path, arcname)
                
                file_size = os.path.getsize(temp_path)
                self.send_response(200)
                self.send_header('Content-Type', 'application/zip')
                self.send_header('Content-Disposition', f'attachment; filename="{download_name}"')
                self.send_header('Content-Length', str(file_size))
                self.end_headers()
                
                with open(temp_path, 'rb') as f:
                    shutil.copyfileobj(f, self.wfile)
            except BrokenPipeError:
                pass
            finally:
                if os.path.exists(temp_path):
                    os.remove(temp_path)

        # API: Download Single File
        elif parsed_path.path == '/api/download_single':
            query = urllib.parse.parse_qs(parsed_path.query)
            file_path = query.get('path', [''])[0]
            target_file = urllib.parse.unquote(file_path).lstrip('/')

            if not os.path.exists(target_file) or not os.path.isfile(target_file):
                self.send_error(404, "File not found")
                return

            try:
                file_size = os.path.getsize(target_file)
                self.send_response(200)
                self.send_header('Content-Type', 'application/octet-stream')
                self.send_header('Content-Disposition', f'attachment; filename="{os.path.basename(target_file)}"')
                self.send_header('Content-Length', str(file_size))
                self.end_headers()
                
                with open(target_file, 'rb') as f:
                    shutil.copyfileobj(f, self.wfile)
            except BrokenPipeError:
                pass
            except Exception as e:
                self.send_error(500, str(e))

        # API: System Stats
        elif parsed_path.path == '/api/stats':
            stats = {
                'cpu': 0,
                'ram': {'consumed': 0, 'total': 0, 'percent': 0},
                'gpus': []
            }

            try:
                if psutil:
                    stats['cpu'] = psutil.cpu_percent(interval=None)
                    mem = psutil.virtual_memory()
                    stats['ram'] = {
                        'consumed': round(mem.used / (1024**3), 2),
                        'total': round(mem.total / (1024**3), 2),
                        'percent': mem.percent
                    }

                if HAS_GPU:
                    try:
                        device_count = nvmlDeviceGetCount()
                        for i in range(device_count):
                            handle = nvmlDeviceGetHandleByIndex(i)
                            name = nvmlDeviceGetName(handle)
                            if isinstance(name, bytes): name = name.decode('utf-8')
                            util = nvmlDeviceGetUtilizationRates(handle)
                            mem_info = nvmlDeviceGetMemoryInfo(handle)
                            stats['gpus'].append({
                                'name': name,
                                'usage': util.gpu,
                                'consumed': round(mem_info.used / (1024**3), 2),
                                'total': round(mem_info.total / (1024**3), 2)
                            })
                    except Exception:
                        pass
            except Exception:
                pass

            resp = json.dumps(stats).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(resp)))
            self.end_headers()
            self.wfile.write(resp)

        # API: List
        elif parsed_path.path == '/api/list':
            query = urllib.parse.parse_qs(parsed_path.query)
            path = query.get('path', [''])[0]
            unquoted_path = urllib.parse.unquote(path)
            
            if unquoted_path == '~' or unquoted_path.startswith('~/'):
                target_dir = os.path.expanduser(unquoted_path)
            elif os.path.isabs(unquoted_path):
                target_dir = unquoted_path
            else:
                safe_path = os.path.normpath(unquoted_path).lstrip('/')
                target_dir = '.' if (safe_path == '.' or safe_path == '') else safe_path

            if not os.path.exists(target_dir) or not os.path.isdir(target_dir):
                self.send_error(404, "Directory not found")
                return

            try:
                items = []
                for entry in os.scandir(target_dir):
                    if entry.name.startswith('.'): continue
                    stats = entry.stat()
                    is_dir = entry.is_dir()
                    item_size = stats.st_size if not is_dir else get_dir_size(entry.path)
                    
                    items.append({
                        'name': entry.name,
                        'is_dir': is_dir,
                        'size': item_size,
                        'mtime': stats.st_mtime,
                        'ext': os.path.splitext(entry.name)[1].lower() if not is_dir else ''
                    })
                items.sort(key=lambda x: (not x['is_dir'], x['name'].lower()))
                response_data = json.dumps(items).encode('utf-8')
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(response_data)))
                self.end_headers()
                self.wfile.write(response_data)
            except Exception as e:
                self.send_error(500, str(e))

        # Default Serving
        else:
            if parsed_path.path == '/favicon.ico' or parsed_path.path == '/favicon.jpg':
                try:
                    with open(FAVICON_PATH, 'rb') as f:
                        content = f.read()
                        self.send_response(200)
                        self.send_header('Content-Type', 'image/jpeg')
                        self.send_header('Content-Length', str(len(content)))
                        self.end_headers()
                        self.wfile.write(content)
                        return
                except Exception:
                    pass

            if parsed_path.path == '/' or parsed_path.path == '/viewer.html':
                # Serve viewer.html from the package directory
                try:
                    with open(VIEWER_HTML_PATH, 'rb') as f:
                        content = f.read()
                        self.send_response(200)
                        self.send_header('Content-Type', 'text/html')
                        self.send_header('Content-Length', str(len(content)))
                        self.end_headers()
                        self.wfile.write(content)
                        return
                except Exception as e:
                    self.send_error(404, f"viewer.html not found: {e}")
                    return
            
            # Fall back to standard file serving from CWD
            try:
                super().do_GET()
            except BrokenPipeError:
                pass

def print_banner(port):
    """Print immersive startup banner"""
    url = f"http://localhost:{port}"
    cwd = os.getcwd()

    # Properly format the dynamic content
    server_line = f"║  🌐  Server Address:  {url:<53}║"
    dir_line = f"║  📂  Working Directory:  {cwd[:50]:<50}║"

    banner = f"""
╔══════════════════════════════════════════════════════════════════════════╗
║                                                                          ║
║               ██╗     ██╗███╗   ██╗██╗   ██╗██╗  ██╗                    ║
║               ██║     ██║████╗  ██║██║   ██║╚██╗██╔╝                    ║
║               ██║     ██║██╔██╗ ██║██║   ██║ ╚███╔╝                     ║
║               ██║     ██║██║╚██╗██║██║   ██║ ██╔██╗                     ║
║               ███████╗██║██║ ╚████║╚██████╔╝██╔╝ ██╗                    ║
║               ╚══════╝╚═╝╚═╝  ╚═══╝ ╚═════╝ ╚═╝  ╚═╝                    ║
║                                                                          ║
║               ███████╗██╗  ██╗██████╗ ██╗      ██████╗ ██████╗          ║
║               ██╔════╝╚██╗██╔╝██╔══██╗██║     ██╔═══██╗██╔══██╗         ║
║               █████╗   ╚███╔╝ ██████╔╝██║     ██║   ██║██████╔╝         ║
║               ██╔══╝   ██╔██╗ ██╔═══╝ ██║     ██║   ██║██╔══██╗         ║
║               ███████╗██╔╝ ██╗██║     ███████╗╚██████╔╝██║  ██║         ║
║               ╚══════╝╚═╝  ╚═╝╚═╝     ╚══════╝ ╚═════╝ ╚═╝  ╚═╝         ║
║                                                                          ║
╠══════════════════════════════════════════════════════════════════════════╣
║                                                                          ║
║  Version: 0.0.2                    Created by: Muhammad Ahmed           ║
║  Enterprise File Management for Linux Systems                           ║
║                                                                          ║
╠══════════════════════════════════════════════════════════════════════════╣
║                                                                          ║
{server_line}
{dir_line}
║                                                                          ║
╠══════════════════════════════════════════════════════════════════════════╣
║                                                                          ║
║  STATUS: Running in background                                          ║
║                                                                          ║
║  The explorer is now accessible from your browser.                      ║
║  You can safely close this terminal window - the server will continue   ║
║  running in the background.                                             ║
║                                                                          ║
║  To stop the server later, use:  pkill -f linux-explorer                ║
║                                                                          ║
╚══════════════════════════════════════════════════════════════════════════╝
"""
    print(banner)

def daemonize():
    """Fork the process to run in background"""
    try:
        pid = os.fork()
        if pid > 0:
            # Parent process - exit and let child run
            return False
    except OSError as e:
        print(f"Fork failed: {e}")
        sys.exit(1)

    # Decouple from parent environment
    os.chdir('/')
    os.setsid()
    os.umask(0)

    # Second fork to prevent zombie
    try:
        pid = os.fork()
        if pid > 0:
            sys.exit(0)
    except OSError as e:
        print(f"Second fork failed: {e}")
        sys.exit(1)

    # Redirect standard file descriptors to /dev/null
    sys.stdout.flush()
    sys.stderr.flush()

    with open('/dev/null', 'r') as devnull:
        os.dup2(devnull.fileno(), sys.stdin.fileno())

    with open('/dev/null', 'a+') as devnull:
        os.dup2(devnull.fileno(), sys.stdout.fileno())
        os.dup2(devnull.fileno(), sys.stderr.fileno())

    return True

def main():
    socketserver.TCPServer.allow_reuse_address = True

    server = None
    applied_port = None

    # Find available port
    for port in range(PORT_START, PORT_END + 1):
        try:
            server = socketserver.TCPServer(("", port), CustomHandler)
            applied_port = port
            break
        except socket.error:
            continue

    if not server:
        print(f"\n❌ Error: All ports in range {PORT_START}-{PORT_END} are occupied.")
        sys.exit(1)

    # Change back to original working directory before starting server
    original_cwd = os.getcwd()

    # Print banner before forking
    print_banner(applied_port)

    url = f"http://localhost:{applied_port}"

    # Open browser immediately
    webbrowser.open(url)

    # Fork to background on Linux/Unix systems
    if os.name != 'nt':  # Not Windows
        should_run = daemonize()
        if not should_run:
            # Parent process - just exit
            print(f"\n✓ Server started successfully in background (PID will be assigned)")
            print(f"✓ Browser opened to {url}")
            return

        # Child process continues
        os.chdir(original_cwd)
    else:
        # On Windows, run in foreground
        print(f"\n✓ Server running (Windows mode - keep this window open)")
        print(f"✓ Browser opened to {url}")
        print("\nPress Ctrl+C to stop the server...")

    # Run server
    with server:
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass

if __name__ == "__main__":
    main()
