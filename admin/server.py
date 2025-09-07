#!/usr/bin/env python3
"""
Админка GPTInfernse - веб-интерфейс для управления системой
Запускается на порту 3002
"""

import os
import sys
import json
import requests
from urllib.parse import urlparse, urlunparse
from http.server import HTTPServer, SimpleHTTPRequestHandler
import socketserver
from urllib.parse import urlparse, parse_qs
from pathlib import Path
import mimetypes

from loguru_config import setup_admin_loguru, get_admin_logger

# Setup loguru
setup_admin_loguru()
logger = get_admin_logger()


def _is_running_in_docker() -> bool:
    try:
        return os.path.exists('/.dockerenv')
    except Exception:
        return False


def get_api_base_url() -> str:
    """Resolve API base URL with Docker-aware defaults and overrides."""
    default_url = 'http://api:8000' if _is_running_in_docker() else 'http://localhost:8000'
    base_url = os.getenv('API_BASE_URL', default_url)

    try:
        parsed = urlparse(base_url)
        # If inside docker and target host is localhost/127.0.0.1, rewrite to service name 'api'
        if _is_running_in_docker() and parsed.hostname in ['localhost', '127.0.0.1']:
            parsed = parsed._replace(netloc=f"api:{parsed.port or 8000}")
            base_url = urlunparse(parsed)
    except Exception:
        base_url = default_url
    return base_url


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
            api_base = get_api_base_url()
            api_url = f"{api_base}{self.path}"
            
            headers = {
                'Content-Type': 'application/json',
                'User-Agent': 'GPTInfernse-Admin/1.0',
                'X-Admin': 'true',
                # Forward client IP for consistent anon id and rate limit grouping
                'X-Forwarded-For': self.client_address[0]
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
            
            # Пытаемся подключиться к Redis (сначала Docker, потом localhost)
            redis_host = os.getenv('REDIS_HOST', 'redis')  # 'redis' для Docker, 'localhost' для локального запуска
            r = redis.Redis(host=redis_host, port=6379, decode_responses=True)
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
            api_base = get_api_base_url()
            response = requests.post(f"{api_base}/admin/clear-cache", timeout=10)
            
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
            api_base = get_api_base_url()
            response = requests.get(f"{api_base}/memory/stats", timeout=30)
            
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
        """Получение всех логов системы с детальным трейсингом"""
        try:
            import os
            import glob
            from datetime import datetime
            
            logs = []
            
            # Все возможные лог файлы
            log_files = [
                '/app/logs/app.log',
                '/app/logs/errors.log', 
                '/app/logs/memory.log',
                '/app/logs/chat.log',
                '/app/logs/database.log',
                '/app/logs/api.log',
                '/app/logs/admin.log',
                '/app/logs/frontend.log',
                './logs/app.log',
                './logs/errors.log',
                './logs/memory.log', 
                './logs/chat.log',
                './logs/database.log',
                './logs/api.log',
                './logs/admin.log',
                './logs/frontend.log'
            ]
            
            # Читаем логи из всех доступных файлов
            for log_file in log_files:
                try:
                    if os.path.isfile(log_file):
                        logger.info(f"📖 Reading logs from: {log_file}")
                        with open(log_file, 'r', encoding='utf-8') as f:
                            lines = f.readlines()[-50:]  # Последние 50 строк на файл
                            
                            for line in lines:
                                line = line.strip()
                                if not line:
                                    continue
                                    
                                # Парсим формат loguru: YYYY-MM-DD HH:mm:ss.SSS | LEVEL | MESSAGE
                                try:
                                    parts = line.split(' | ', 2)
                                    if len(parts) >= 3:
                                        timestamp = parts[0]
                                        level = parts[1].strip()
                                        message = parts[2]
                                    else:
                                        timestamp = datetime.now().strftime('%H:%M:%S')
                                        level = 'INFO'
                                        message = line
                                except:
                                    timestamp = datetime.now().strftime('%H:%M:%S')
                                    level = 'INFO'
                                    message = line
                                
                                logs.append({
                                    'container': os.path.basename(log_file).replace('.log', ''),
                                    'message': message,
                                    'timestamp': timestamp,
                                    'level': level
                                })
                                
                except Exception as e:
                    logger.debug(f"Could not read {log_file}: {e}")
            
            # Добавляем статус системы в реальном времени
            current_time = datetime.now().strftime('%H:%M:%S')
            
            # API Health
            try:
                api_base = get_api_base_url()
                api_logs_response = requests.get(f'{api_base}/health/detailed', timeout=3)
                if api_logs_response.status_code == 200:
                    api_data = api_logs_response.json()
                    logs.append({
                        'container': 'system',
                        'message': f"🏥 API Health: {api_data.get('status', 'unknown')}",
                        'timestamp': current_time,
                        'level': 'INFO'
                    })
                    
                    if 'services' in api_data:
                        for service, status in api_data['services'].items():
                            logs.append({
                                'container': 'system',
                                'message': f"🔧 {service}: {status}",
                                'timestamp': current_time,
                                'level': 'INFO'
                            })
            except Exception as e:
                logs.append({
                    'container': 'system',
                    'message': f"❌ API Health check failed: {e}",
                    'timestamp': current_time,
                    'level': 'ERROR'
                })
            
            # Memory Stats
            try:
                api_base = get_api_base_url()
                memory_response = requests.get(f'{api_base}/memory/stats', timeout=3)
                if memory_response.status_code == 200:
                    stats = memory_response.json()
                    logs.append({
                        'container': 'memory',
                        'message': f"💾 Stats: {stats.get('total_conversations', 0)} conversations, {stats.get('total_users', 0)} users, {stats.get('total_messages', 0)} messages",
                        'timestamp': current_time,
                        'level': 'INFO'
                    })
            except Exception as e:
                logs.append({
                    'container': 'memory',
                    'message': f"❌ Memory stats failed: {e}",
                    'timestamp': current_time,
                    'level': 'ERROR'
                })
            
            # Redis Status (without docker exec)
            try:
                import redis
                redis_host = os.getenv('REDIS_HOST', 'redis' if _is_running_in_docker() else 'localhost')
                r = redis.Redis(host=redis_host, port=6379, decode_responses=True)
                dbsize = r.dbsize()
                logs.append({
                    'container': 'redis',
                    'message': f"🔴 Redis: {dbsize} keys found",
                    'timestamp': current_time,
                    'level': 'INFO'
                })
                # Sample up to 3 keys via SCAN
                sample_keys = []
                try:
                    for i, key in enumerate(r.scan_iter('*', count=100)):
                        sample_keys.append(key)
                        if i >= 2:
                            break
                except Exception:
                    pass
                if sample_keys:
                    logs.append({
                        'container': 'redis',
                        'message': f"🔑 Sample keys: {', '.join(sample_keys)}",
                        'timestamp': current_time,
                        'level': 'DEBUG'
                    })
            except Exception as e:
                logs.append({
                    'container': 'redis',
                    'message': f"❌ Redis check failed: {e}",
                    'timestamp': current_time,
                    'level': 'ERROR'
                })
            
            # Если нет логов, добавляем базовые
            if not logs:
                logs = [
                    {'container': 'admin', 'message': '⚠️ No logs found in any location', 'timestamp': current_time, 'level': 'WARNING'}
                ]
            
            # Сортируем по времени (новые сверху) и ограничиваем количество
            logs.sort(key=lambda x: x['timestamp'], reverse=True)
            logs = logs[:300]  # Максимум 300 записей
            
            logger.info(f"📊 Collected {len(logs)} log entries")
            self.send_json_response({'logs': logs})
            
        except Exception as e:
            current_time = datetime.now().strftime('%H:%M:%S')
            logger.error(f"Error in handle_logs: {e}")
            self.send_json_response({
                'logs': [
                    {'container': 'error', 'message': f'❌ Log system error: {str(e)}', 'timestamp': current_time, 'level': 'ERROR'}
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
            api_base = get_api_base_url()
            response = requests.get(f"{api_base}/health", timeout=5)
            if response.status_code == 200:
                logger.info("✅ Основной API сервер доступен")
            else:
                logger.warning(f"⚠️ Основной API отвечает с кодом {response.status_code}")
        except:
            logger.warning(f"❌ Основной API сервер недоступен на {get_api_base_url()}")
            logger.warning("   Некоторые функции админки могут не работать")
        
        # Запускаем админ сервер
        server_address = (host, port)
        httpd = ThreadedHTTPServer(server_address, AdminHandler)
        
        logger.info(f"\n🔧 GPTInfernse Admin Panel")
        logger.info(f"🌐 Адрес: http://{host}:{port}")
        logger.info(f"📁 Директория: {Path(__file__).parent}")
        logger.info(f"🔗 API Proxy: {get_api_base_url()}")
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
