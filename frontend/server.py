#!/usr/bin/env python3
"""
Продвинутый HTTP сервер для фронтенда GPTInfernse
"""

import os
import sys
from http.server import HTTPServer, SimpleHTTPRequestHandler
import socketserver
from urllib.parse import urlparse, parse_qs
import json
import requests
from pathlib import Path
import mimetypes

class GPTInfernseHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(Path(__file__).parent), **kwargs)
    
    def do_GET(self):
        """Обработка GET запросов"""
        parsed_path = urlparse(self.path)
        
        # Главная страница
        if parsed_path.path == '/' or parsed_path.path == '':
            self.path = '/index.html'
            return super().do_GET()
        
        # API проксирование для GET запросов
        if parsed_path.path.startswith('/api/'):
            self.proxy_to_api('GET')
            return
        
        # Статические файлы
        return super().do_GET()
    
    def do_POST(self):
        """Обработка POST запросов"""
        if self.path.startswith('/api/'):
            self.proxy_to_api('POST')
        else:
            self.send_error(404, "Not Found")
    
    def do_OPTIONS(self):
        """Обработка OPTIONS запросов для CORS"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.send_header('Access-Control-Max-Age', '86400')
        self.end_headers()
    
    def proxy_to_api(self, method='GET'):
        """Проксирование запросов к API"""
        try:
            # Формируем URL для API
            api_url = f"http://localhost:8000{self.path}"
            
            headers = {
                'Content-Type': 'application/json',
                'User-Agent': 'GPTInfernse-Frontend/1.0'
            }
            
            # Подготавливаем данные для POST запросов
            data = None
            if method == 'POST':
                content_length = int(self.headers.get('Content-Length', 0))
                if content_length > 0:
                    data = self.rfile.read(content_length)
            
            # Отправляем запрос к API
            if method == 'GET':
                response = requests.get(api_url, headers=headers, timeout=30)
            else:
                response = requests.post(api_url, data=data, headers=headers, timeout=30)
            
            # Возвращаем ответ клиенту
            self.send_response(response.status_code)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Cache-Control', 'no-cache')
            self.end_headers()
            
            self.wfile.write(response.content)
            
            # Логирование
            status_emoji = "✅" if response.status_code < 400 else "❌"
            print(f"{status_emoji} {method} {self.path} -> {response.status_code}")
            
        except requests.exceptions.ConnectionError:
            print(f"❌ Нет связи с API сервером: {api_url}")
            self.send_error(503, "API server unavailable")
        except requests.exceptions.Timeout:
            print(f"⏰ Таймаут запроса к API: {api_url}")
            self.send_error(504, "API server timeout")
        except Exception as e:
            print(f"❌ Ошибка проксирования {method} {self.path}: {e}")
            self.send_error(500, f"Proxy error: {str(e)}")
    
    def end_headers(self):
        """Добавляем CORS заголовки ко всем ответам"""
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        super().end_headers()
    
    def guess_type(self, path):
        """Определяем MIME тип файла"""
        mimetype, _ = mimetypes.guess_type(path)
        if mimetype is None:
            if path.endswith('.js'):
                return 'application/javascript'
            elif path.endswith('.css'):
                return 'text/css'
            elif path.endswith('.html'):
                return 'text/html; charset=utf-8'
            elif path.endswith('.json'):
                return 'application/json'
            else:
                return 'application/octet-stream'
        return mimetype
    
    def log_message(self, format, *args):
        """Кастомное логирование"""
        if not self.path.startswith('/api/'):
            # Логируем только не-API запросы для статических файлов
            timestamp = self.log_date_time_string()
            print(f"📁 {timestamp} - {format % args}")

class ThreadedHTTPServer(socketserver.ThreadingMixIn, HTTPServer):
    """HTTP сервер с поддержкой многопоточности"""
    daemon_threads = True
    allow_reuse_address = True

def run_server(port=3000, host='localhost'):
    """Запуск продвинутого сервера фронтенда"""
    try:
        # Проверяем доступность API
        try:
            response = requests.get(f"http://localhost:8000/health", timeout=5)
            if response.status_code == 200:
                print("✅ API сервер доступен")
            else:
                print(f"⚠️ API сервер отвечает с кодом {response.status_code}")
        except:
            print("❌ API сервер недоступен на localhost:8000")
            print("   Убедитесь, что API запущен перед использованием фронтенда")
        
        # Запускаем сервер
        server_address = (host, port)
        httpd = ThreadedHTTPServer(server_address, GPTInfernseHandler)
        
        print(f"\n🚀 GPTInfernse Frontend Server")
        print(f"🌐 Адрес: http://{host}:{port}")
        print(f"📁 Директория: {Path(__file__).parent}")
        print(f"🔗 API Proxy: http://localhost:8000")
        print(f"🛑 Остановка: Ctrl+C")
        print("-" * 50)
        
        httpd.serve_forever()
        
    except KeyboardInterrupt:
        print("\n🛑 Сервер остановлен пользователем")
    except OSError as e:
        if e.errno == 48:  # Address already in use
            print(f"❌ Порт {port} уже используется")
            print(f"   Попробуйте другой порт: python server.py {port + 1}")
        else:
            print(f"❌ Ошибка сети: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Неожиданная ошибка: {e}")
        sys.exit(1)

if __name__ == "__main__":
    # Парсинг аргументов командной строки
    port = 3000
    host = '0.0.0.0'
    
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print("❌ Неверный формат порта")
            sys.exit(1)
    
    if len(sys.argv) > 2:
        host = sys.argv[2]
    
    run_server(port, host)