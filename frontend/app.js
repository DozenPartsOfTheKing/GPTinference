/**
 * GPTInfernse - Дополнительная функциональность
 * Профессиональные фишки для UI
 */

class GPTInfernseApp {
    constructor() {
        this.notifications = [];
        this.contextMenu = null;
        this.currentTheme = 'dark';
        this.shortcuts = new Map();
        
        this.init();
    }
    
    init() {
        console.log('🚀 Инициализация GPTInfernse App...');
        
        this.setupKeyboardShortcuts();
        this.setupContextMenu();
        this.setupNotifications();
        this.setupProgressBar();
        this.setupThemeToggle();
        this.setupMessageActions();
        
        console.log('✅ GPTInfernse App готов!');
    }
    
    // Клавиатурные сочетания
    setupKeyboardShortcuts() {
        this.shortcuts.set('Escape', () => this.closeAllModals());
        this.shortcuts.set('ctrl+/', () => this.showShortcutsModal());
        this.shortcuts.set('ctrl+k', () => this.focusInput());
        this.shortcuts.set('ctrl+l', () => this.clearChat());
        this.shortcuts.set('ctrl+n', () => startNewChat());
        
        document.addEventListener('keydown', (e) => {
            const key = e.ctrlKey || e.metaKey ? 
                `ctrl+${e.key.toLowerCase()}` : 
                e.key;
            
            const handler = this.shortcuts.get(key);
            if (handler) {
                e.preventDefault();
                handler();
            }
        });
    }
    
    // Контекстное меню
    setupContextMenu() {
        document.addEventListener('contextmenu', (e) => {
            if (e.target.closest('.message-content')) {
                e.preventDefault();
                this.showContextMenu(e, 'message');
            }
        });
        
        document.addEventListener('click', () => {
            this.hideContextMenu();
        });
    }
    
    showContextMenu(event, type) {
        this.hideContextMenu();
        
        const menu = document.createElement('div');
        menu.className = 'context-menu active';
        menu.style.left = event.pageX + 'px';
        menu.style.top = event.pageY + 'px';
        
        if (type === 'message') {
            menu.innerHTML = `
                <div class="context-menu-item" onclick="app.copyMessage(event)">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
                        <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
                    </svg>
                    Копировать
                </div>
                <div class="context-menu-item" onclick="app.selectMessage(event)">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M9 11H5a2 2 0 0 0-2 2v3a2 2 0 0 0 2 2h4m6-6h4a2 2 0 0 1 2 2v3a2 2 0 0 1-2 2h-4m-6 0a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v3a2 2 0 0 1-2 2h-4z"/>
                    </svg>
                    Выделить всё
                </div>
                <div class="context-menu-separator"></div>
                <div class="context-menu-item" onclick="app.regenerateResponse(event)">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <polyline points="23 4 23 10 17 10"/>
                        <polyline points="1 20 1 14 7 14"/>
                        <path d="M20.49 9A9 9 0 0 0 5.64 5.64L1 10m22 4l-4.64 4.36A9 9 0 0 1 3.51 15"/>
                    </svg>
                    Повторить ответ
                </div>
            `;
        }
        
        document.body.appendChild(menu);
        this.contextMenu = menu;
        
        // Корректируем позицию если меню выходит за границы
        const rect = menu.getBoundingClientRect();
        if (rect.right > window.innerWidth) {
            menu.style.left = (event.pageX - rect.width) + 'px';
        }
        if (rect.bottom > window.innerHeight) {
            menu.style.top = (event.pageY - rect.height) + 'px';
        }
    }
    
    hideContextMenu() {
        if (this.contextMenu) {
            this.contextMenu.remove();
            this.contextMenu = null;
        }
    }
    
    // Уведомления
    setupNotifications() {
        this.notificationContainer = document.createElement('div');
        this.notificationContainer.id = 'notifications';
        this.notificationContainer.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 10001;
            pointer-events: none;
        `;
        document.body.appendChild(this.notificationContainer);
    }
    
    showNotification(message, type = 'info', duration = 5000) {
        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        notification.style.pointerEvents = 'auto';
        
        const icons = {
            success: '✅',
            error: '❌',
            warning: '⚠️',
            info: 'ℹ️'
        };
        
        notification.innerHTML = `
            <div class="notification-header">
                <span class="notification-title">${icons[type]} ${this.getNotificationTitle(type)}</span>
                <button class="notification-close" onclick="this.parentElement.parentElement.remove()">×</button>
            </div>
            <div class="notification-message">${message}</div>
        `;
        
        this.notificationContainer.appendChild(notification);
        
        // Анимация появления
        setTimeout(() => notification.classList.add('show'), 100);
        
        // Автоматическое скрытие
        if (duration > 0) {
            setTimeout(() => {
                notification.classList.remove('show');
                setTimeout(() => notification.remove(), 300);
            }, duration);
        }
        
        this.notifications.push(notification);
        return notification;
    }
    
    getNotificationTitle(type) {
        const titles = {
            success: 'Успешно',
            error: 'Ошибка',
            warning: 'Внимание',
            info: 'Информация'
        };
        return titles[type] || 'Уведомление';
    }
    
    // Прогресс бар
    setupProgressBar() {
        this.progressBar = document.createElement('div');
        this.progressBar.className = 'progress-bar';
        this.progressBar.innerHTML = '<div class="progress-fill"></div>';
        document.body.appendChild(this.progressBar);
    }
    
    showProgress() {
        this.progressBar.classList.add('active');
        const fill = this.progressBar.querySelector('.progress-fill');
        fill.style.width = '0%';
        
        // Симуляция прогресса
        let progress = 0;
        const interval = setInterval(() => {
            progress += Math.random() * 30;
            if (progress > 90) progress = 90;
            fill.style.width = progress + '%';
        }, 200);
        
        return () => {
            clearInterval(interval);
            fill.style.width = '100%';
            setTimeout(() => {
                this.progressBar.classList.remove('active');
            }, 300);
        };
    }
    
    // Переключатель темы
    setupThemeToggle() {
        const toggle = document.createElement('button');
        toggle.className = 'theme-toggle tooltip';
        toggle.setAttribute('data-tooltip', 'Переключить тему');
        toggle.innerHTML = '🌙';
        toggle.onclick = () => this.toggleTheme();
        
        // Временно скрываем, так как у нас только темная тема
        toggle.style.display = 'none';
        document.body.appendChild(toggle);
    }
    
    toggleTheme() {
        this.currentTheme = this.currentTheme === 'dark' ? 'light' : 'dark';
        document.documentElement.setAttribute('data-theme', this.currentTheme);
        
        const toggle = document.querySelector('.theme-toggle');
        toggle.innerHTML = this.currentTheme === 'dark' ? '🌙' : '☀️';
        
        this.showNotification(
            `Переключено на ${this.currentTheme === 'dark' ? 'темную' : 'светлую'} тему`,
            'success',
            2000
        );
    }
    
    // Действия с сообщениями
    setupMessageActions() {
        // Добавляем кнопки действий к сообщениям при наведении
        document.addEventListener('mouseover', (e) => {
            const message = e.target.closest('.message');
            if (message && !message.querySelector('.message-actions')) {
                this.addMessageActions(message);
            }
        });
    }
    
    addMessageActions(message) {
        const actions = document.createElement('div');
        actions.className = 'message-actions';
        
        if (message.classList.contains('ai-message')) {
            actions.innerHTML = `
                <button class="action-btn tooltip" data-tooltip="Копировать" onclick="app.copyMessage(event)">
                    📋
                </button>
                <button class="action-btn tooltip" data-tooltip="Повторить" onclick="app.regenerateResponse(event)">
                    🔄
                </button>
                <button class="action-btn tooltip" data-tooltip="Лайк" onclick="app.likeMessage(event)">
                    👍
                </button>
            `;
        } else {
            actions.innerHTML = `
                <button class="action-btn tooltip" data-tooltip="Копировать" onclick="app.copyMessage(event)">
                    📋
                </button>
                <button class="action-btn tooltip" data-tooltip="Редактировать" onclick="app.editMessage(event)">
                    ✏️
                </button>
            `;
        }
        
        message.appendChild(actions);
    }
    
    // Утилиты
    focusInput() {
        const input = document.getElementById('messageInput');
        if (input) {
            input.focus();
            this.showNotification('Фокус на поле ввода', 'info', 1000);
        }
    }
    
    clearChat() {
        if (confirm('Очистить историю чата?')) {
            startNewChat();
            this.showNotification('Чат очищен', 'success', 2000);
        }
    }
    
    closeAllModals() {
        document.querySelectorAll('.modal-overlay.active').forEach(modal => {
            modal.classList.remove('active');
        });
        this.hideContextMenu();
    }
    
    // Действия с сообщениями
    copyMessage(event) {
        const message = event.target.closest('.message');
        const content = message.querySelector('.message-content').textContent;
        
        navigator.clipboard.writeText(content).then(() => {
            this.showNotification('Сообщение скопировано', 'success', 2000);
        }).catch(() => {
            this.showNotification('Не удалось скопировать', 'error', 2000);
        });
        
        this.hideContextMenu();
    }
    
    selectMessage(event) {
        const message = event.target.closest('.message');
        const content = message.querySelector('.message-content');
        
        const range = document.createRange();
        range.selectNodeContents(content);
        const selection = window.getSelection();
        selection.removeAllRanges();
        selection.addRange(range);
        
        this.hideContextMenu();
    }
    
    regenerateResponse(event) {
        this.showNotification('Функция в разработке', 'info', 2000);
        this.hideContextMenu();
    }
    
    likeMessage(event) {
        const button = event.target;
        button.innerHTML = button.innerHTML === '👍' ? '❤️' : '👍';
        this.showNotification('Спасибо за обратную связь!', 'success', 2000);
    }
    
    editMessage(event) {
        this.showNotification('Функция в разработке', 'info', 2000);
    }
    
    // Модальные окна
    showModal(title, content) {
        const overlay = document.createElement('div');
        overlay.className = 'modal-overlay';
        
        overlay.innerHTML = `
            <div class="modal">
                <div class="modal-header">
                    <div class="modal-title">${title}</div>
                    <button class="modal-close" onclick="this.closest('.modal-overlay').remove()">×</button>
                </div>
                <div class="modal-content">${content}</div>
            </div>
        `;
        
        document.body.appendChild(overlay);
        setTimeout(() => overlay.classList.add('active'), 100);
        
        return overlay;
    }
    
    showShortcutsModal() {
        const shortcuts = `
            <div class="shortcuts-list">
                <div class="shortcut-item">
                    <kbd>Ctrl + K</kbd>
                    <span>Фокус на поле ввода</span>
                </div>
                <div class="shortcut-item">
                    <kbd>Ctrl + L</kbd>
                    <span>Очистить чат</span>
                </div>
                <div class="shortcut-item">
                    <kbd>Ctrl + N</kbd>
                    <span>Новый чат</span>
                </div>
                <div class="shortcut-item">
                    <kbd>Ctrl + /</kbd>
                    <span>Показать горячие клавиши</span>
                </div>
                <div class="shortcut-item">
                    <kbd>Escape</kbd>
                    <span>Закрыть модальные окна</span>
                </div>
                <div class="shortcut-item">
                    <kbd>Enter</kbd>
                    <span>Отправить сообщение</span>
                </div>
                <div class="shortcut-item">
                    <kbd>Shift + Enter</kbd>
                    <span>Новая строка</span>
                </div>
            </div>
            <style>
                .shortcuts-list {
                    display: flex;
                    flex-direction: column;
                    gap: 12px;
                }
                .shortcut-item {
                    display: flex;
                    align-items: center;
                    justify-content: space-between;
                    padding: 8px 0;
                }
                kbd {
                    background: var(--bg-tertiary);
                    border: 1px solid var(--border);
                    border-radius: 4px;
                    padding: 4px 8px;
                    font-size: 12px;
                    font-family: monospace;
                }
            </style>
        `;
        
        this.showModal('Горячие клавиши', shortcuts);
    }
    
    // Анимации
    animateElement(element, animation, duration = 300) {
        element.style.animation = `${animation} ${duration}ms ease-out`;
        setTimeout(() => {
            element.style.animation = '';
        }, duration);
    }
    
    // Утилиты для работы с API
    async makeRequest(url, options = {}) {
        const hideProgress = this.showProgress();
        
        try {
            const response = await fetch(url, {
                headers: {
                    'Content-Type': 'application/json',
                    ...options.headers
                },
                ...options
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const data = await response.json();
            hideProgress();
            return data;
            
        } catch (error) {
            hideProgress();
            this.showNotification(
                `Ошибка запроса: ${error.message}`,
                'error',
                5000
            );
            throw error;
        }
    }
    
    // Дебаунс для оптимизации
    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }
    
    // Сохранение состояния
    saveState() {
        const state = {
            theme: this.currentTheme,
            chatHistory: chatHistory || [],
            currentModel: currentModel || 'llama3'
        };
        
        localStorage.setItem('gptinfernse_state', JSON.stringify(state));
    }
    
    loadState() {
        try {
            const saved = localStorage.getItem('gptinfernse_state');
            if (saved) {
                const state = JSON.parse(saved);
                this.currentTheme = state.theme || 'dark';
                // Восстанавливаем другие параметры...
            }
        } catch (error) {
            console.warn('Не удалось загрузить сохраненное состояние:', error);
        }
    }
}

// Инициализация приложения
let app;
document.addEventListener('DOMContentLoaded', () => {
    app = new GPTInfernseApp();
    
    // Сохраняем состояние при закрытии
    window.addEventListener('beforeunload', () => {
        app.saveState();
    });
});

// Экспорт для использования в других скриптах
window.GPTInfernseApp = GPTInfernseApp;
