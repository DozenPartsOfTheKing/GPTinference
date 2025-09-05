#!/usr/bin/env python3
"""
Простой HTTP сервер для фронтенда GPTInfernse
"""

import http.server
import socketserver
import os
import sys
from pathlib import Path

# Порт для фронтенда
PORT = 3000

class CORSHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    """HTTP handler с поддержкой CORS"""
    
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

def main():
    # Переходим в директорию фронтенда
    frontend_dir = Path(__file__).parent
    os.chdir(frontend_dir)
    
    # Создаем сервер
    with socketserver.TCPServer(("", PORT), CORSHTTPRequestHandler) as httpd:
        print(f"🚀 Фронтенд запущен на http://localhost:{PORT}")
        print(f"📁 Директория: {frontend_dir}")
        print("🔗 Откройте http://localhost:3000 в браузере")
        print("⏹️  Для остановки нажмите Ctrl+C")
        
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n👋 Сервер остановлен")
            sys.exit(0)

if __name__ == "__main__":
    main()
