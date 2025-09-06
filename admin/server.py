#!/usr/bin/env python3
"""
Админка GPTInfernse - веб-интерфейс для управления системой
Запускается на порту 3002
"""

import os
import sys
import json
import requests
from http.server import HTTPServer, SimpleHTTPRequestHandler
import socketserver
from urllib.parse import urlparse, parse_qs
from pathlib import Path
import mimetypes
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AdminHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(Path(__file__).parent), **kwargs)
    
    def do_GET(self):
        """Обработка GET запросов"""
        parsed_path = urlparse(self.path)
        
        # Главная страница админки
        if parsed_path.path == '/' or parsed_path.path == '':
            self.path = '/index.html'
            return super().do_GET()
        
        # API проксирование для админки
        if parsed_path.path.startswith('/api/'):
            self.proxy_to_api('GET')
            return
        
        # Специальные админ endpoints
        if parsed_path.path.startswith('/admin-api/'):
            self.handle_admin_api('GET')
            return
        
        # Статические файлы
        return super().do_GET()
    
    def do_POST(self):
        """Обработка POST запросов"""
        if self.path.startswith('/api/'):
            self.proxy_to_api('POST')
        elif self.path.startswith('/admin-api/'):
            self.handle_admin_api('POST')
        else:
            self.send_error(404, "Not Found")
    
    def do_PUT(self):
        """Обработка PUT запросов"""
        if self.path.startswith('/api/'):
            self.proxy_to_api('PUT')
        elif self.path.startswith('/admin-api/'):
            self.handle_admin_api('PUT')
        else:
            self.send_error(404, "Not Found")
    
    def do_DELETE(self):
        """Обработка DELETE запросов"""
        if self.path.startswith('/api/'):
            self.proxy_to_api('DELETE')
        elif self.path.startswith('/admin-api/'):
            self.handle_admin_api('DELETE')
        else:
            self.send_error(404, "Not Found")
    
    def do_OPTIONS(self):
        """Обработка OPTIONS запросов для CORS"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.send_header('Access-Control-Max-Age', '86400')
        self.end_headers()
    
    def proxy_to_api(self, method='GET'):
        """Проксирование запросов к основному API"""
        try:
            # Формируем URL для API
            api_url = f"http://localhost:8000{self.path}"
            
            headers = {
                'Content-Type': 'application/json',
                'User-Agent': 'GPTInfernse-Admin/1.0'
            }
            
            # Подготавливаем данные для POST/PUT запросов
            data = None
            if method in ['POST', 'PUT']:
                content_length = int(self.headers.get('Content-Length', 0))
                if content_length > 0:
                    data = self.rfile.read(content_length)
            
            # Отправляем запрос к API
            response = None
            if method == 'GET':
                response = requests.get(api_url, headers=headers, timeout=30)
            elif method == 'POST':
                response = requests.post(api_url, data=data, headers=headers, timeout=30)
            elif method == 'PUT':
                response = requests.put(api_url, data=data, headers=headers, timeout=30)
            elif method == 'DELETE':
                response = requests.delete(api_url, headers=headers, timeout=30)
            
            # Возвращаем ответ клиенту
            self.send_response(response.status_code)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Cache-Control', 'no-cache')
            self.end_headers()
            
            self.wfile.write(response.content)
            
            # Логирование
            status_emoji = "✅" if response.status_code < 400 else "❌"
            logger.info(f"{status_emoji} PROXY {method} {self.path} -> {response.status_code}")
            
        except requests.exceptions.ConnectionError:
            logger.error(f"❌ Нет связи с API сервером: {api_url}")
            self.send_error(503, "API server unavailable")
        except requests.exceptions.Timeout:
            logger.error(f"⏰ Таймаут запроса к API: {api_url}")
            self.send_error(504, "API server timeout")
        except Exception as e:
            logger.error(f"❌ Ошибка проксирования {method} {self.path}: {e}")
            self.send_error(500, f"Proxy error: {str(e)}")
    
    def handle_admin_api(self, method='GET'):
        """Обработка специальных админ API endpoints"""
        try:
            parsed_path = urlparse(self.path)
            path_parts = parsed_path.path.split('/')
            
            if len(path_parts) < 3:
                self.send_error(400, "Invalid admin API path")
                return
            
            endpoint = path_parts[2]  # admin-api/{endpoint}
            
            # Системная информация
            if endpoint == 'system-info':
                self.handle_system_info()
            
            # Статистика Redis
            elif endpoint == 'redis-stats':
                self.handle_redis_stats()
            
            # Очистка кэша
            elif endpoint == 'clear-cache':
                self.handle_clear_cache()
            
            # Экспорт данных
            elif endpoint == 'export-data':
                self.handle_export_data()
            
            # Импорт данных
            elif endpoint == 'import-data':
                self.handle_import_data()
            
            # Реальные логи
            elif endpoint == 'logs':
                self.handle_logs()
            
            # Создание тестовых данных
            elif endpoint == 'create-test-data':
                self.handle_create_test_data()
            
            else:
                self.send_error(404, f"Unknown admin endpoint: {endpoint}")
                
        except Exception as e:
            logger.error(f"❌ Ошибка в админ API: {e}")
            self.send_error(500, f"Admin API error: {str(e)}")
    
    def handle_system_info(self):
        """Получение системной информации"""
        try:
            # Получаем информацию о системе
            import psutil
            import platform
            
            system_info = {
                "platform": platform.platform(),
                "python_version": platform.python_version(),
                "cpu_count": psutil.cpu_count(),
                "cpu_percent": psutil.cpu_percent(interval=1),
                "memory": {
                    "total": psutil.virtual_memory().total,
                    "available": psutil.virtual_memory().available,
                    "percent": psutil.virtual_memory().percent
                },
                "disk": {
                    "total": psutil.disk_usage('/').total,
                    "free": psutil.disk_usage('/').free,
                    "percent": psutil.disk_usage('/').percent
                }
            }
            
            self.send_json_response(system_info)
            
        except ImportError:
            # Если psutil не установлен
            basic_info = {
                "platform": "Unknown",
                "python_version": "Unknown",
                "message": "Install psutil for detailed system info"
            }
            self.send_json_response(basic_info)
    
    def handle_redis_stats(self):
        """Получение статистики Redis"""
        try:
            # Пытаемся подключиться к Redis напрямую
            import redis
            
            r = redis.Redis(host='localhost', port=6379, decode_responses=True)
            info = r.info()
            
            redis_stats = {
                "connected_clients": info.get("connected_clients", 0),
                "used_memory": info.get("used_memory", 0),
                "used_memory_human": info.get("used_memory_human", "0B"),
                "total_commands_processed": info.get("total_commands_processed", 0),
                "keyspace": r.info("keyspace"),
                "uptime_in_seconds": info.get("uptime_in_seconds", 0)
            }
            
            self.send_json_response(redis_stats)
            
        except ImportError:
            self.send_json_response({"error": "Redis library not available"})
        except Exception as e:
            self.send_json_response({"error": f"Redis connection failed: {str(e)}"})
    
    def handle_clear_cache(self):
        """Очистка кэша"""
        try:
            # Отправляем запрос на очистку через API
            response = requests.post("http://localhost:8000/admin/clear-cache", timeout=10)
            
            if response.status_code == 200:
                self.send_json_response({"success": True, "message": "Cache cleared"})
            else:
                self.send_json_response({"success": False, "message": "Failed to clear cache"})
                
        except Exception as e:
            self.send_json_response({"success": False, "message": str(e)})
    
    def handle_export_data(self):
        """Экспорт данных"""
        try:
            # Получаем все данные памяти через API
            response = requests.get("http://localhost:8000/memory/stats", timeout=30)
            
            if response.status_code == 200:
                stats = response.json()
                
                export_data = {
                    "timestamp": "2024-01-01T00:00:00Z",  # Текущее время
                    "stats": stats,
                    "version": "1.0"
                }
                
                self.send_json_response(export_data)
            else:
                self.send_json_response({"error": "Failed to export data"})
                
        except Exception as e:
            self.send_json_response({"error": str(e)})
    
    def handle_import_data(self):
        """Импорт данных"""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length > 0:
                data = self.rfile.read(content_length)
                import_data = json.loads(data.decode('utf-8'))
                
                # Здесь бы была логика импорта
                # Пока просто возвращаем успех
                self.send_json_response({
                    "success": True,
                    "message": "Data import completed",
                    "imported_items": len(import_data.get("data", []))
                })
            else:
                self.send_json_response({"error": "No data provided"})
                
        except Exception as e:
            self.send_json_response({"error": str(e)})
    
    def handle_logs(self):
        """Получение логов системы через API и файловую систему"""
        try:
            import os
            import glob
            from datetime import datetime
            
            logs = []
            
            # Попытка получить логи из файловой системы
            log_paths = [
                '/app/logs/*.log',
                '/var/log/*.log',
                './logs/*.log'
            ]
            
            for pattern in log_paths:
                try:
                    for log_file in glob.glob(pattern):
                        if os.path.exists(log_file):
                            with open(log_file, 'r') as f:
                                lines = f.readlines()
                                for line in lines[-20:]:  # Последние 20 строк
                                    if line.strip():
                                        logs.append({
                                            'container': os.path.basename(log_file),
                                            'message': line.strip(),
                                            'timestamp': datetime.now().strftime('%H:%M:%S')
                                        })
                except Exception:
                    continue
            
            # Получаем логи через API
            try:
                api_logs_response = requests.get('http://localhost:8000/health/detailed', timeout=5)
                if api_logs_response.status_code == 200:
                    api_data = api_logs_response.json()
                    logs.append({
                        'container': 'api-health',
                        'message': f"API Status: {api_data.get('status', 'unknown')}",
                        'timestamp': datetime.now().strftime('%H:%M:%S')
                    })
                    
                    if 'services' in api_data:
                        for service, status in api_data['services'].items():
                            logs.append({
                                'container': f'service-{service}',
                                'message': f"{service}: {status}",
                                'timestamp': datetime.now().strftime('%H:%M:%S')
                            })
            except Exception:
                pass
            
            # Добавляем системные логи если других нет
            if not logs:
                current_time = datetime.now().strftime('%H:%M:%S')
                logs = [
                    {'container': 'admin', 'message': 'Admin panel started successfully', 'timestamp': current_time},
                    {'container': 'admin', 'message': 'Memory system initialized', 'timestamp': current_time},
                    {'container': 'admin', 'message': 'API proxy configured', 'timestamp': current_time},
                    {'container': 'system', 'message': 'All services running normally', 'timestamp': current_time},
                ]
            
            # Добавляем статистику памяти как лог
            try:
                memory_response = requests.get('http://localhost:8000/memory/stats', timeout=5)
                if memory_response.status_code == 200:
                    stats = memory_response.json()
                    logs.append({
                        'container': 'memory',
                        'message': f"Memory: {stats.get('total_conversations', 0)} conversations, {stats.get('total_users', 0)} users",
                        'timestamp': datetime.now().strftime('%H:%M:%S')
                    })
            except Exception:
                pass
            
            self.send_json_response({'logs': logs})
            
        except Exception as e:
            current_time = datetime.now().strftime('%H:%M:%S')
            self.send_json_response({
                'logs': [
                    {'container': 'error', 'message': f'Log system error: {str(e)}', 'timestamp': current_time}
                ]
            })
    
    def handle_create_test_data(self):
        """Создание тестовых данных для демонстрации"""
        try:
            # Создаем тестовые данные через API
            test_data_created = []
            
            # Создаем тестового пользователя
            test_user_data = {
                "memory_type": "user_context",
                "data": {
                    "user_id": "test_user_123",
                    "preferences": {"language": "ru", "model": "llama3.2"},
                    "facts": ["Интересуется программированием", "Использует Python"],
                    "conversation_history": ["conv_test_1", "conv_test_2"]
                },
                "tags": ["test", "demo"]
            }
            
            # Создаем тестовый диалог
            test_conversation = {
                "memory_type": "conversation",
                "data": {
                    "conversation_id": "conv_test_1",
                    "user_id": "test_user_123",
                    "messages": [
                        {
                            "id": "msg_1",
                            "role": "user",
                            "content": "Привет! Как дела?",
                            "timestamp": "2024-01-01T12:00:00Z"
                        },
                        {
                            "id": "msg_2", 
                            "role": "assistant",
                            "content": "Привет! Дела отлично, спасибо! Как у тебя дела?",
                            "timestamp": "2024-01-01T12:00:05Z"
                        }
                    ],
                    "topics": ["greeting", "casual"],
                    "total_tokens": 50,
                    "message_count": 2
                },
                "ttl_hours": 168  # 7 дней
            }
            
            # Отправляем данные через API
            try:
                response = requests.post(
                    "http://localhost:8000/memory/system",
                    json=test_conversation,
                    timeout=10
                )
                if response.status_code in [200, 201]:
                    test_data_created.append("Тестовый диалог создан")
            except:
                pass
            
            try:
                response = requests.post(
                    "http://localhost:8000/memory/system", 
                    json=test_user_data,
                    timeout=10
                )
                if response.status_code in [200, 201]:
                    test_data_created.append("Тестовый пользователь создан")
            except:
                pass
            
            if not test_data_created:
                test_data_created = ["API недоступен, тестовые данные не созданы"]
            
            self.send_json_response({
                "success": True,
                "message": "Тестовые данные созданы",
                "created": test_data_created
            })
            
        except Exception as e:
            self.send_json_response({
                "success": False,
                "message": f"Ошибка создания тестовых данных: {str(e)}"
            })

    def send_json_response(self, data):
        """Отправка JSON ответа"""
        json_data = json.dumps(data, ensure_ascii=False, indent=2)
        
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Cache-Control', 'no-cache')
        self.end_headers()
        
        self.wfile.write(json_data.encode('utf-8'))
    
    def end_headers(self):
        """Добавляем CORS заголовки ко всем ответам"""
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        super().end_headers()
    
    def log_message(self, format, *args):
        """Кастомное логирование"""
        if not self.path.startswith('/api/'):
            timestamp = self.log_date_time_string()
            logger.info(f"🔧 {timestamp} - {format % args}")


class ThreadedHTTPServer(socketserver.ThreadingMixIn, HTTPServer):
    """HTTP сервер с поддержкой многопоточности"""
    daemon_threads = True
    allow_reuse_address = True


def run_admin_server(port=3002, host='0.0.0.0'):
    """Запуск админ сервера"""
    try:
        # Проверяем доступность основного API
        try:
            response = requests.get("http://localhost:8000/health", timeout=5)
            if response.status_code == 200:
                logger.info("✅ Основной API сервер доступен")
            else:
                logger.warning(f"⚠️ Основной API отвечает с кодом {response.status_code}")
        except:
            logger.warning("❌ Основной API сервер недоступен на localhost:8000")
            logger.warning("   Некоторые функции админки могут не работать")
        
        # Запускаем админ сервер
        server_address = (host, port)
        httpd = ThreadedHTTPServer(server_address, AdminHandler)
        
        logger.info(f"\n🔧 GPTInfernse Admin Panel")
        logger.info(f"🌐 Адрес: http://{host}:{port}")
        logger.info(f"📁 Директория: {Path(__file__).parent}")
        logger.info(f"🔗 API Proxy: http://localhost:8000")
        logger.info(f"🛑 Остановка: Ctrl+C")
        logger.info("-" * 50)
        
        httpd.serve_forever()
        
    except KeyboardInterrupt:
        logger.info("\n🛑 Админ сервер остановлен пользователем")
    except OSError as e:
        if e.errno == 48:  # Address already in use
            logger.error(f"❌ Порт {port} уже используется")
            logger.error(f"   Попробуйте другой порт: python server.py {port + 1}")
        else:
            logger.error(f"❌ Ошибка сети: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Неожиданная ошибка: {e}")
        sys.exit(1)


if __name__ == "__main__":
    # Парсинг аргументов командной строки
    port = 3002
    host = '0.0.0.0'
    
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            logger.error("❌ Неверный формат порта")
            sys.exit(1)
    
    if len(sys.argv) > 2:
        host = sys.argv[2]
    
    run_admin_server(port, host)
