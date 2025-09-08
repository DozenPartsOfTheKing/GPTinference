/**
 * GPTInfernse Admin Panel JavaScript
 */

class AdminPanel {
    constructor() {
        // Prefer proxy through admin server to preserve headers and avoid CORS
        this.apiBaseUrl = '/api';
        this.adminApiUrl = '/admin-api';
        this.currentSection = 'dashboard';
        this.refreshInterval = null;
        this.init();
    }

    async loadRouter() {
        try {
            // Active schema
            const activeResp = await fetch(`${this.apiBaseUrl}/router/schemas/active`);
            const activeData = activeResp.ok ? await activeResp.json() : { active: null };
            const activeEl = document.getElementById('router-active');
            const active = activeData.active;
            if (active) {
                const classes = (active.schema?.classes || []).map(c => `${c.name}`).join(', ');
                activeEl.innerHTML = `
                    <div class="info-item"><span class="info-label">Ключ:</span> <span class="info-value">${active.key}</span></div>
                    <div class="info-item"><span class="info-label">Название:</span> <span class="info-value">${active.title || active.key}</span></div>
                    <div class="info-item"><span class="info-label">Классы:</span> <span class="info-value">${this.escapeHtml(classes)}</span></div>
                `;
            } else {
                activeEl.innerHTML = '<div class="no-data">Активная схема не выбрана</div>';
            }

            // List schemas
            const listResp = await fetch(`${this.apiBaseUrl}/router/schemas`);
            const schemas = listResp.ok ? await listResp.json() : [];
            const listEl = document.getElementById('router-schemas-list');
            if (!schemas || schemas.length === 0) {
                listEl.innerHTML = '<div class="no-data">Схемы не найдены</div>';
            } else {
                listEl.innerHTML = schemas.map(item => {
                    const isActive = active && active.key === item.key;
                    const title = (item.value && item.value.title) || item.title || item.key;
                    const descr = (item.value && item.value.description) || item.description || '';
                    const classes = (item.value?.schema?.classes || item.schema?.classes || []).map(c => c.name).join(', ');
                    return `
                        <div class="memory-item">
                            <div class="memory-item-info">
                                <div class="memory-item-title">${title} ${isActive ? '<span class="badge">Активная</span>' : ''}</div>
                                <div class="memory-item-meta">Ключ: ${item.key} ${descr ? '• ' + this.escapeHtml(descr) : ''}</div>
                                <div class="memory-item-content" style="color: var(--text-secondary); margin-top: 6px;">Классы: ${this.escapeHtml(classes)}</div>
                            </div>
                            <div class="memory-item-actions">
                                <button class="btn btn-secondary btn-sm" onclick="adminPanel.activateRouterSchema('${item.key}')"><i class="fas fa-check"></i></button>
                                <button class="btn btn-danger btn-sm" onclick="adminPanel.deleteRouterSchema('${item.key}')"><i class="fas fa-trash"></i></button>
                            </div>
                        </div>
                    `;
                }).join('');
            }
        } catch (e) {
            console.error('Error loading router:', e);
            const activeEl = document.getElementById('router-active');
            const listEl = document.getElementById('router-schemas-list');
            if (activeEl) activeEl.innerHTML = '<div class="error">Ошибка загрузки</div>';
            if (listEl) listEl.innerHTML = '<div class="error">Ошибка загрузки</div>';
        }
    }

    async saveRouterSchema() {
        try {
            const key = document.getElementById('router-key').value.trim();
            const title = document.getElementById('router-title').value.trim();
            const description = document.getElementById('router-description').value.trim();
            if (!key) { this.showNotification('Ключ обязателен', 'error'); return; }
            const classes = this.collectRouterClasses();
            const examples = this.collectRouterExamples();
            const resp = await fetch(`${this.apiBaseUrl}/router/schemas`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ key, title, description, classes, examples })
            });
            if (resp.ok) {
                this.showNotification('Схема сохранена', 'success');
                await this.loadRouter();
            } else {
                const data = await resp.json().catch(() => ({}));
                this.showNotification(data.detail || 'Ошибка сохранения схемы', 'error');
            }
        } catch (e) {
            this.showNotification('Ошибка сохранения схемы', 'error');
        }
    }

    async activateRouterSchema(key) {
        try {
            const resp = await fetch(`${this.apiBaseUrl}/router/schemas/${encodeURIComponent(key)}/activate`, { method: 'PUT' });
            if (resp.ok) {
                this.showNotification('Схема активирована', 'success');
                await this.loadRouter();
            } else {
                this.showNotification('Не удалось активировать схему', 'error');
            }
        } catch (e) {
            this.showNotification('Ошибка активации схемы', 'error');
        }
    }

    async deleteRouterSchema(key) {
        this.showConfirmModal('Удалить схему', `Удалить схему роутера ${key}?`, async () => {
            try {
                const resp = await fetch(`${this.apiBaseUrl}/router/schemas/${encodeURIComponent(key)}`, { method: 'DELETE' });
                if (resp.ok) {
                    this.showNotification('Схема удалена', 'success');
                    await this.loadRouter();
                } else {
                    this.showNotification('Не удалось удалить схему', 'error');
                }
            } catch (e) {
                this.showNotification('Ошибка удаления схемы', 'error');
            }
        });
    }

    async testRouter() {
        try {
            const query = document.getElementById('router-test-input').value.trim();
            const schemaKey = document.getElementById('router-test-schema').value.trim();
            if (!query) { this.showNotification('Введите запрос', 'error'); return; }
            const resp = await fetch(`${this.apiBaseUrl}/router/route`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query, schema_key: schemaKey || undefined })
            });
            const data = await resp.json();
            const pre = document.querySelector('#router-test-result code');
            pre.textContent = JSON.stringify(data, null, 2);
            if (resp.ok) this.showNotification('Маршрутизация выполнена', 'success');
            else this.showNotification(data.detail || 'Ошибка маршрутизации', 'error');
        } catch (e) {
            this.showNotification('Ошибка маршрутизации', 'error');
        }
    }

    init() {
        this.setupEventListeners();
        this.setupNavigation();
        this.checkApiStatus();
        this.loadDashboard();
        this.startAutoRefresh();
    }

    setupEventListeners() {
        // Navigation
        document.querySelectorAll('.nav-link').forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                const section = e.currentTarget.dataset.section;
                this.navigateToSection(section);
            });
        });

        // Refresh buttons
        document.getElementById('refresh-btn').addEventListener('click', () => {
            this.refreshCurrentSection();
        });

        document.getElementById('refresh-models-btn').addEventListener('click', () => {
            this.loadModels();
        });

        document.getElementById('refresh-system-btn').addEventListener('click', () => {
            this.loadSystemInfo();
        });

        // System prompts
        const spCreateBtn = document.getElementById('sp-create-btn');
        if (spCreateBtn) {
            spCreateBtn.addEventListener('click', () => this.createSystemPrompt());
        }

        // Memory management
        document.getElementById('clear-memory-btn').addEventListener('click', () => {
            this.showConfirmModal(
                'Очистка памяти',
                'Вы уверены, что хотите очистить всю память? Это действие нельзя отменить.',
                () => this.clearMemory()
            );
        });

        document.getElementById('export-memory-btn').addEventListener('click', () => {
            this.exportMemory();
        });

        document.getElementById('create-test-data-btn').addEventListener('click', () => {
            this.createTestData();
        });

        // Memory tabs
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const tab = e.currentTarget.dataset.tab;
                this.switchMemoryTab(tab);
            });
        });

        // Modal
        document.getElementById('modal-cancel').addEventListener('click', () => {
            this.hideModal();
        });

        document.getElementById('modal-confirm').addEventListener('click', () => {
            if (this.modalCallback) {
                this.modalCallback();
            }
            this.hideModal();
        });

        // Notification
        document.getElementById('notification-close').addEventListener('click', () => {
            this.hideNotification();
        });

        const refreshRouterBtn = document.getElementById('refresh-router-btn');
        if (refreshRouterBtn) {
            refreshRouterBtn.addEventListener('click', () => this.loadRouter());
        }

        const addClassBtn = document.getElementById('router-add-class-btn');
        if (addClassBtn) {
            addClassBtn.addEventListener('click', () => this.addRouterClassRow());
        }

        const addExampleBtn = document.getElementById('router-add-example-btn');
        if (addExampleBtn) {
            addExampleBtn.addEventListener('click', () => this.addRouterExampleRow());
        }

        const routerSaveBtn = document.getElementById('router-save-btn');
        if (routerSaveBtn) {
            routerSaveBtn.addEventListener('click', () => this.saveRouterSchema());
        }

        const routerTestBtn = document.getElementById('router-test-btn');
        if (routerTestBtn) {
            routerTestBtn.addEventListener('click', () => this.testRouter());
        }

        // Search
        document.getElementById('conversation-search').addEventListener('input', (e) => {
            this.searchConversations(e.target.value);
        });

        document.getElementById('users-search').addEventListener('input', (e) => {
            this.searchUsers(e.target.value);
        });
    }

    setupNavigation() {
        // Set initial active states
        this.navigateToSection('dashboard');
    }

    navigateToSection(section) {
        // Update navigation
        document.querySelectorAll('.nav-link').forEach(link => {
            link.classList.remove('active');
        });
        document.querySelector(`[data-section="${section}"]`).classList.add('active');

        // Update content
        document.querySelectorAll('.content-section').forEach(section => {
            section.classList.remove('active');
        });
        document.getElementById(`${section}-section`).classList.add('active');

        // Update page title
        const titles = {
            dashboard: 'Dashboard',
            models: 'Модели',
            memory: 'Память',
            conversations: 'Диалоги',
            users: 'Пользователи',
            system: 'Система',
            logs: 'Логи',
            router: 'Роутер'
        };
        document.getElementById('page-title').textContent = titles[section] || section;

        this.currentSection = section;
        this.loadSectionData(section);
    }

    loadSectionData(section) {
        switch (section) {
            case 'dashboard':
                this.loadDashboard();
                break;
            case 'models':
                this.loadModels();
                break;
            case 'memory':
                this.loadMemoryData();
                break;
            case 'conversations':
                this.loadConversations();
                break;
            case 'users':
                this.loadUsers();
                break;
            case 'system':
                this.loadSystemInfo();
                break;
            case 'logs':
                this.loadLogs();
                break;
            case 'router':
                this.loadRouter();
                break;
        }
    }

    refreshCurrentSection() {
        this.loadSectionData(this.currentSection);
        this.showNotification('Данные обновлены', 'success');
    }

    async checkApiStatus() {
        try {
            const response = await fetch(`${this.apiBaseUrl}/health`);
            const statusDot = document.getElementById('api-status');
            
            if (response.ok) {
                statusDot.classList.remove('offline');
                statusDot.classList.add('online');
            } else {
                statusDot.classList.remove('online');
                statusDot.classList.add('offline');
            }
        } catch (error) {
            const statusDot = document.getElementById('api-status');
            statusDot.classList.remove('online');
            statusDot.classList.add('offline');
        }
    }

    async loadDashboard() {
        try {
            // Load memory stats
            const memoryResponse = await fetch(`${this.apiBaseUrl}/memory/stats`);
            if (memoryResponse.ok) {
                const memoryStats = await memoryResponse.json();
                this.updateDashboardStats(memoryStats);
                this.updateDashboardCharts(memoryStats);
            }

            // Load models count
            const modelsResponse = await fetch(`${this.apiBaseUrl}/models`);
            if (modelsResponse.ok) {
                const modelsData = await modelsResponse.json();
                document.getElementById('active-models').textContent = modelsData.models?.length || 0;
            }

        } catch (error) {
            console.error('Error loading dashboard:', error);
            this.showNotification('Ошибка загрузки dashboard', 'error');
        }
    }

    updateDashboardStats(stats) {
        document.getElementById('total-conversations').textContent = stats.total_conversations || 0;
        document.getElementById('total-users').textContent = stats.total_users || 0;
        document.getElementById('memory-usage').textContent = (stats.memory_usage_mb || 0).toFixed(1);
    }

    updateDashboardCharts(stats) {
        // Update topics chart
        const topicsChart = document.getElementById('topics-chart');
        if (stats.popular_topics && stats.popular_topics.length > 0) {
            topicsChart.innerHTML = stats.popular_topics.map(topic => `
                <div class="chart-item">
                    <span class="chart-label">${topic.topic}</span>
                    <div class="chart-bar">
                        <div class="chart-fill" style="width: ${(topic.count / stats.popular_topics[0].count) * 100}%"></div>
                    </div>
                    <span class="chart-value">${topic.count}</span>
                </div>
            `).join('');
        } else {
            topicsChart.innerHTML = '<div class="no-data">Нет данных</div>';
        }

        // Update models chart
        const modelsChart = document.getElementById('models-chart');
        if (stats.model_usage_stats && Object.keys(stats.model_usage_stats).length > 0) {
            const modelEntries = Object.entries(stats.model_usage_stats);
            const maxUsage = Math.max(...modelEntries.map(([_, data]) => data.usage_count));
            
            modelsChart.innerHTML = modelEntries.map(([model, data]) => `
                <div class="chart-item">
                    <span class="chart-label">${model}</span>
                    <div class="chart-bar">
                        <div class="chart-fill" style="width: ${(data.usage_count / maxUsage) * 100}%"></div>
                    </div>
                    <span class="chart-value">${data.usage_count}</span>
                </div>
            `).join('');
        } else {
            modelsChart.innerHTML = '<div class="no-data">Нет данных</div>';
        }
    }

    async loadModels() {
        try {
            const response = await fetch(`${this.apiBaseUrl}/models`);
            const data = await response.json();
            
            const modelsGrid = document.getElementById('models-grid');
            
            if (data.models && data.models.length > 0) {
                modelsGrid.innerHTML = data.models.map(model => `
                    <div class="model-card">
                        <div class="model-header">
                            <div class="model-name">${model.name}</div>
                            <div class="model-status active">Активна</div>
                        </div>
                        <div class="model-info">
                            <div class="model-info-item">
                                <span class="model-info-label">Размер:</span>
                                <span>${model.size || 'Неизвестно'}</span>
                            </div>
                            <div class="model-info-item">
                                <span class="model-info-label">Изменена:</span>
                                <span>${new Date(model.modified_at).toLocaleString('ru-RU')}</span>
                            </div>
                        </div>
                        <div class="model-actions">
                            <button class="btn btn-primary btn-sm" onclick="adminPanel.testModel('${model.name}')">
                                <i class="fas fa-play"></i> Тест
                            </button>
                            <button class="btn btn-secondary btn-sm" onclick="adminPanel.showModelDetails('${model.name}')">
                                <i class="fas fa-info"></i> Детали
                            </button>
                        </div>
                    </div>
                `).join('');
            } else {
                modelsGrid.innerHTML = '<div class="no-data">Модели не найдены</div>';
            }
        } catch (error) {
            console.error('Error loading models:', error);
            document.getElementById('models-grid').innerHTML = '<div class="error">Ошибка загрузки моделей</div>';
        }
    }

    async loadMemoryData() {
        this.switchMemoryTab('conversations');
    }

    async switchMemoryTab(tab) {
        // Update tab buttons
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.classList.remove('active');
        });
        document.querySelector(`[data-tab="${tab}"]`).classList.add('active');

        // Update tab content
        document.querySelectorAll('.tab-content').forEach(content => {
            content.classList.remove('active');
        });
        document.getElementById(`memory-${tab}`).classList.add('active');

        // Load tab data
        switch (tab) {
            case 'conversations':
                await this.loadMemoryConversations();
                break;
            case 'users':
                await this.loadMemoryUsers();
                break;
            case 'system':
                await this.loadMemorySystem();
                break;
        }
    }

    async loadMemoryConversations() {
        try {
            const response = await fetch(`${this.apiBaseUrl}/memory/query`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    memory_type: 'conversation',
                    limit: 50
                })
            });

            const data = await response.json();
            const conversationsList = document.getElementById('conversations-list');

            if (data.success && data.data.conversations.length > 0) {
                conversationsList.innerHTML = data.data.conversations.map(conv => `
                    <div class="memory-item">
                        <div class="memory-item-info">
                            <div class="memory-item-title">Диалог ${conv.conversation_id.substring(0, 8)}...</div>
                            <div class="memory-item-meta">
                                ${conv.message_count} сообщений • ${conv.total_tokens} токенов • 
                                ${new Date(conv.updated_at).toLocaleString('ru-RU')}
                            </div>
                        </div>
                        <div class="memory-item-actions">
                            <button class="btn btn-secondary btn-sm" onclick="adminPanel.viewConversation('${conv.conversation_id}')">
                                <i class="fas fa-eye"></i>
                            </button>
                            <button class="btn btn-danger btn-sm" onclick="adminPanel.deleteConversation('${conv.conversation_id}')">
                                <i class="fas fa-trash"></i>
                            </button>
                        </div>
                    </div>
                `).join('');
            } else {
                conversationsList.innerHTML = '<div class="no-data">Диалоги не найдены</div>';
            }
        } catch (error) {
            console.error('Error loading memory conversations:', error);
            document.getElementById('conversations-list').innerHTML = '<div class="error">Ошибка загрузки</div>';
        }
    }

    async loadMemoryUsers() {
        try {
            const response = await fetch(`${this.apiBaseUrl}/memory/query`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    memory_type: 'user_context',
                    limit: 50
                })
            });

            const data = await response.json();
            const usersList = document.getElementById('users-list');

            if (data.success && data.data.users.length > 0) {
                usersList.innerHTML = data.data.users.map(user => `
                    <div class="memory-item">
                        <div class="memory-item-info">
                            <div class="memory-item-title">Пользователь ${user.user_id}</div>
                            <div class="memory-item-meta">
                                ${user.conversation_history.length} диалогов • ${user.facts.length} фактов • 
                                ${new Date(user.last_active).toLocaleString('ru-RU')}
                            </div>
                        </div>
                        <div class="memory-item-actions">
                            <button class="btn btn-secondary btn-sm" onclick="adminPanel.viewUser('${user.user_id}')">
                                <i class="fas fa-eye"></i>
                            </button>
                            <button class="btn btn-danger btn-sm" onclick="adminPanel.deleteUser('${user.user_id}')">
                                <i class="fas fa-trash"></i>
                            </button>
                        </div>
                    </div>
                `).join('');
            } else {
                usersList.innerHTML = '<div class="no-data">Пользователи не найдены</div>';
            }
        } catch (error) {
            console.error('Error loading memory users:', error);
            document.getElementById('users-list').innerHTML = '<div class="error">Ошибка загрузки</div>';
        }
    }

    async loadMemorySystem() {
        try {
            const response = await fetch(`${this.apiBaseUrl}/memory/query`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    memory_type: 'system_facts',
                    limit: 50
                })
            });

            const data = await response.json();
            const systemList = document.getElementById('system-list');

            if (data.success && data.data.system_memories.length > 0) {
                systemList.innerHTML = data.data.system_memories.map(mem => `
                    <div class="memory-item">
                        <div class="memory-item-info">
                            <div class="memory-item-title">${mem.key}</div>
                            <div class="memory-item-meta">
                                Приоритет: ${mem.priority} • Обращений: ${mem.access_count} • 
                                ${new Date(mem.updated_at).toLocaleString('ru-RU')}
                            </div>
                        </div>
                        <div class="memory-item-actions">
                            <button class="btn btn-secondary btn-sm" onclick="adminPanel.viewSystemMemory('${mem.key}')">
                                <i class="fas fa-eye"></i>
                            </button>
                            <button class="btn btn-danger btn-sm" onclick="adminPanel.deleteSystemMemory('${mem.key}')">
                                <i class="fas fa-trash"></i>
                            </button>
                        </div>
                    </div>
                `).join('');
            } else {
                systemList.innerHTML = '<div class="no-data">Системная память не найдена</div>';
            }
        } catch (error) {
            console.error('Error loading system memory:', error);
            document.getElementById('system-list').innerHTML = '<div class="error">Ошибка загрузки</div>';
        }
    }

    async loadConversations() {
        // This would load detailed conversation view
        await this.loadMemoryConversations();
    }

    async loadUsers() {
        // This would load detailed users view
        await this.loadMemoryUsers();
    }

    async loadSystemInfo() {
        try {
            // Load system info
            const systemResponse = await fetch(`${this.adminApiUrl}/system-info`);
            if (systemResponse.ok) {
                const systemData = await systemResponse.json();
                this.updateSystemInfo(systemData);
            }

            // Load Redis stats
            const redisResponse = await fetch(`${this.adminApiUrl}/redis-stats`);
            if (redisResponse.ok) {
                const redisData = await redisResponse.json();
                this.updateRedisInfo(redisData);
            }

            // Load API info
            const apiResponse = await fetch(`${this.apiBaseUrl}/info`);
            if (apiResponse.ok) {
                const apiData = await apiResponse.json();
                this.updateApiInfo(apiData);
            }

            // Load system prompts
            await this.loadSystemPrompts();

        } catch (error) {
            console.error('Error loading system info:', error);
        }
    }

    updateSystemInfo(data) {
        const systemInfo = document.getElementById('system-info');
        systemInfo.innerHTML = `
            <div class="info-item">
                <span class="info-label">Платформа:</span>
                <span class="info-value">${data.platform || 'Неизвестно'}</span>
            </div>
            <div class="info-item">
                <span class="info-label">Python:</span>
                <span class="info-value">${data.python_version || 'Неизвестно'}</span>
            </div>
            <div class="info-item">
                <span class="info-label">CPU:</span>
                <span class="info-value">${data.cpu_count || 'Неизвестно'} ядер (${data.cpu_percent || 0}%)</span>
            </div>
            <div class="info-item">
                <span class="info-label">Память:</span>
                <span class="info-value">${data.memory ? Math.round(data.memory.percent) : 0}% использовано</span>
            </div>
            <div class="info-item">
                <span class="info-label">Диск:</span>
                <span class="info-value">${data.disk ? Math.round(data.disk.percent) : 0}% использовано</span>
            </div>
        `;
    }

    updateRedisInfo(data) {
        const redisInfo = document.getElementById('redis-info');
        if (data.error) {
            redisInfo.innerHTML = `<div class="error">${data.error}</div>`;
        } else {
            redisInfo.innerHTML = `
                <div class="info-item">
                    <span class="info-label">Клиенты:</span>
                    <span class="info-value">${data.connected_clients || 0}</span>
                </div>
                <div class="info-item">
                    <span class="info-label">Память:</span>
                    <span class="info-value">${data.used_memory_human || '0B'}</span>
                </div>
                <div class="info-item">
                    <span class="info-label">Команды:</span>
                    <span class="info-value">${data.total_commands_processed || 0}</span>
                </div>
                <div class="info-item">
                    <span class="info-label">Uptime:</span>
                    <span class="info-value">${Math.round((data.uptime_in_seconds || 0) / 3600)} часов</span>
                </div>
            `;
        }
    }

    updateApiInfo(data) {
        const apiInfo = document.getElementById('api-info');
        apiInfo.innerHTML = `
            <div class="info-item">
                <span class="info-label">Версия:</span>
                <span class="info-value">${data.version || 'Неизвестно'}</span>
            </div>
            <div class="info-item">
                <span class="info-label">Режим:</span>
                <span class="info-value">${data.environment || 'Неизвестно'}</span>
            </div>
            <div class="info-item">
                <span class="info-label">Ollama:</span>
                <span class="info-value">${data.ollama_url || 'Не настроено'}</span>
            </div>
            <div class="info-item">
                <span class="info-label">Функции:</span>
                <span class="info-value">
                    ${data.features ? Object.entries(data.features).filter(([k, v]) => v).map(([k]) => k).join(', ') : 'Нет'}
                </span>
            </div>
        `;
    }

    async loadSystemPrompts() {
        try {
            const listEl = document.getElementById('system-prompts-list');
            if (!listEl) return;
            listEl.innerHTML = '<div class="loading">Загрузка...</div>';
            const response = await fetch(`${this.apiBaseUrl}/system-prompts/`);
            const activeResp = await fetch(`${this.apiBaseUrl}/system-prompts/active`);
            const data = response.ok ? await response.json() : [];
            const active = activeResp.ok ? (await activeResp.json()).active : null;

            if (!data || data.length === 0) {
                listEl.innerHTML = '<div class="no-data">Промпты не найдены</div>';
                return;
            }

            listEl.innerHTML = data.map(item => {
                const isActive = active && active.key === item.key;
                const title = (item.value && item.value.title) || item.title || item.key;
                const content = (item.value && item.value.content) || item.content || '';
                const descr = (item.value && item.value.description) || item.description || '';
                return `
                    <div class="memory-item">
                        <div class="memory-item-info">
                            <div class="memory-item-title">${title} ${isActive ? '<span class="badge">Активный</span>' : ''}</div>
                            <div class="memory-item-meta">
                                Ключ: ${item.key} ${descr ? '• ' + this.escapeHtml(descr) : ''}
                            </div>
                            <div class="memory-item-content" style="white-space: pre-wrap; color: var(--text-secondary); margin-top: 6px;">${this.escapeHtml(content).slice(0, 500)}</div>
                        </div>
                        <div class="memory-item-actions">
                            <button class="btn btn-secondary btn-sm" onclick="adminPanel.activateSystemPrompt('${item.key}')">
                                <i class="fas fa-check"></i>
                            </button>
                            <button class="btn btn-danger btn-sm" onclick="adminPanel.deleteSystemPrompt('${item.key}')">
                                <i class="fas fa-trash"></i>
                            </button>
                        </div>
                    </div>
                `;
            }).join('');
        } catch (error) {
            console.error('Error loading system prompts:', error);
            const el = document.getElementById('system-prompts-list');
            if (el) el.innerHTML = '<div class="error">Ошибка загрузки</div>';
        }
    }

    async createSystemPrompt() {
        try {
            const key = document.getElementById('sp-key').value.trim();
            const title = document.getElementById('sp-title').value.trim();
            const description = document.getElementById('sp-description').value.trim();
            const content = document.getElementById('sp-content').value.trim();

            if (!key || !content) {
                this.showNotification('Ключ и контент обязательны', 'error');
                return;
            }

            const resp = await fetch(`${this.apiBaseUrl}/system-prompts/`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ key, title, description, content })
            });

            if (resp.ok) {
                this.showNotification('Промпт сохранён', 'success');
                await this.loadSystemPrompts();
            } else {
                const data = await resp.json().catch(() => ({}));
                this.showNotification(data.detail || 'Ошибка сохранения промпта', 'error');
            }
        } catch (e) {
            this.showNotification('Ошибка сохранения промпта', 'error');
        }
    }

    async activateSystemPrompt(key) {
        try {
            const resp = await fetch(`${this.apiBaseUrl}/system-prompts/${encodeURIComponent(key)}/activate`, { method: 'PUT' });
            if (resp.ok) {
                this.showNotification('Промпт активирован', 'success');
                await this.loadSystemPrompts();
            } else {
                this.showNotification('Не удалось активировать промпт', 'error');
            }
        } catch (e) {
            this.showNotification('Ошибка активации промпта', 'error');
        }
    }

    async deleteSystemPrompt(key) {
        this.showConfirmModal('Удалить промпт', `Удалить системный промпт ${key}?`, async () => {
            try {
                const resp = await fetch(`${this.apiBaseUrl}/system-prompts/${encodeURIComponent(key)}`, { method: 'DELETE' });
                if (resp.ok) {
                    this.showNotification('Промпт удалён', 'success');
                    await this.loadSystemPrompts();
                } else {
                    this.showNotification('Не удалось удалить промпт', 'error');
                }
            } catch (e) {
                this.showNotification('Ошибка удаления промпта', 'error');
            }
        });
    }

    escapeHtml(str) {
        const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' };
        return String(str).replace(/[&<>"']/g, m => map[m]);
    }

    async loadLogs() {
        try {
            const response = await fetch('/admin-api/logs');
            const data = await response.json();
            
            const logsContent = document.getElementById('logs-content');
            
            if (data.logs && data.logs.length > 0) {
                logsContent.innerHTML = data.logs.map(log => `
                    <div class="log-entry">
                        <span class="log-timestamp">[${log.timestamp}]</span>
                        <span class="log-container">[${log.container}]</span>
                        <span class="log-message">${log.message}</span>
                    </div>
                `).join('');
            } else {
                logsContent.innerHTML = '<div class="no-data">Логи не найдены</div>';
            }
        } catch (error) {
            console.error('Error loading logs:', error);
            document.getElementById('logs-content').innerHTML = '<div class="error">Ошибка загрузки логов</div>';
        }
    }

    // Action methods
    async testModel(modelName) {
        try {
            const response = await fetch(`${this.apiBaseUrl}/chat`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    prompt: 'Тестовое сообщение',
                    model: modelName,
                    max_tokens: 50
                })
            });

            if (response.ok) {
                this.showNotification(`Модель ${modelName} работает корректно`, 'success');
            } else {
                this.showNotification(`Ошибка тестирования модели ${modelName}`, 'error');
            }
        } catch (error) {
            this.showNotification(`Ошибка тестирования модели ${modelName}`, 'error');
        }
    }

    showModelDetails(modelName) {
        this.showNotification(`Детали модели ${modelName} (функция в разработке)`, 'info');
    }

    async clearMemory() {
        try {
            const response = await fetch(`${this.adminApiUrl}/clear-cache`, {
                method: 'POST'
            });

            if (response.ok) {
                this.showNotification('Память очищена успешно', 'success');
                this.loadMemoryData();
            } else {
                this.showNotification('Ошибка очистки памяти', 'error');
            }
        } catch (error) {
            this.showNotification('Ошибка очистки памяти', 'error');
        }
    }

    async exportMemory() {
        try {
            const response = await fetch(`${this.adminApiUrl}/export-data`);
            const data = await response.json();

            if (response.ok) {
                const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `gptinfernse-memory-${new Date().toISOString().split('T')[0]}.json`;
                a.click();
                URL.revokeObjectURL(url);
                
                this.showNotification('Данные экспортированы успешно', 'success');
            } else {
                this.showNotification('Ошибка экспорта данных', 'error');
            }
        } catch (error) {
            this.showNotification('Ошибка экспорта данных', 'error');
        }
    }

    async createTestData() {
        try {
            const response = await fetch(`${this.adminApiUrl}/create-test-data`, {
                method: 'POST'
            });
            const data = await response.json();

            if (response.ok && data.success) {
                this.showNotification('Тестовые данные созданы успешно', 'success');
                // Обновляем данные в памяти
                this.loadMemoryData();
                this.loadDashboard();
            } else {
                this.showNotification(data.message || 'Ошибка создания тестовых данных', 'error');
            }
        } catch (error) {
            this.showNotification('Ошибка создания тестовых данных', 'error');
        }
    }

    viewConversation(conversationId) {
        this.showNotification(`Просмотр диалога ${conversationId} (функция в разработке)`, 'info');
    }

    deleteConversation(conversationId) {
        this.showConfirmModal(
            'Удаление диалога',
            `Вы уверены, что хотите удалить диалог ${conversationId}?`,
            async () => {
                try {
                    const response = await fetch(`${this.apiBaseUrl}/memory/conversation/${conversationId}`, {
                        method: 'DELETE'
                    });

                    if (response.ok) {
                        this.showNotification('Диалог удален', 'success');
                        this.loadMemoryConversations();
                    } else {
                        this.showNotification('Ошибка удаления диалога', 'error');
                    }
                } catch (error) {
                    this.showNotification('Ошибка удаления диалога', 'error');
                }
            }
        );
    }

    viewUser(userId) {
        this.showNotification(`Просмотр пользователя ${userId} (функция в разработке)`, 'info');
    }

    deleteUser(userId) {
        this.showNotification(`Удаление пользователя ${userId} (функция в разработке)`, 'info');
    }

    viewSystemMemory(key) {
        this.showNotification(`Просмотр системной памяти ${key} (функция в разработке)`, 'info');
    }

    deleteSystemMemory(key) {
        this.showNotification(`Удаление системной памяти ${key} (функция в разработке)`, 'info');
    }

    searchConversations(query) {
        // Placeholder for search functionality
        console.log('Searching conversations:', query);
    }

    searchUsers(query) {
        // Placeholder for search functionality
        console.log('Searching users:', query);
    }

    // UI Helper methods
    showConfirmModal(title, message, callback) {
        document.getElementById('modal-title').textContent = title;
        document.getElementById('modal-message').textContent = message;
        document.getElementById('confirm-modal').classList.add('active');
        this.modalCallback = callback;
    }

    hideModal() {
        document.getElementById('confirm-modal').classList.remove('active');
        this.modalCallback = null;
    }

    showNotification(message, type = 'info') {
        const notification = document.getElementById('notification');
        const messageEl = document.getElementById('notification-message');
        
        messageEl.textContent = message;
        notification.className = `notification show ${type}`;
        
        setTimeout(() => {
            this.hideNotification();
        }, 5000);
    }

    hideNotification() {
        document.getElementById('notification').classList.remove('show');
    }

    startAutoRefresh() {
        // Auto-refresh every 30 seconds
        this.refreshInterval = setInterval(() => {
            this.checkApiStatus();
            if (this.currentSection === 'dashboard') {
                this.loadDashboard();
            }
        }, 30000);
    }

    stopAutoRefresh() {
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
            this.refreshInterval = null;
        }
    }

    collectRouterClasses() {
        const list = document.getElementById('router-classes-builder');
        if (!list) return [];
        const rows = Array.from(list.querySelectorAll('.router-class-row'));
        const classes = [];
        for (const r of rows) {
            const name = r.querySelector('.rc-name').value.trim();
            const description = r.querySelector('.rc-desc').value.trim();
            if (!name) continue;
            classes.push({ name, description });
        }
        return classes;
    }

    collectRouterExamples() {
        const list = document.getElementById('router-examples-builder');
        if (!list) return [];
        const rows = Array.from(list.querySelectorAll('.router-example-row'));
        const examples = [];
        for (const r of rows) {
            const query = r.querySelector('.re-query').value.trim();
            const key = r.querySelector('.re-key').value.trim();
            const val = r.querySelector('.re-value').value.trim();
            if (!query) continue;
            let expected = {};
            if (key && val) expected[key] = val;
            examples.push({ query, expected });
        }
        return examples;
    }

    addRouterClassRow(initial = { name: '', description: '' }) {
        const list = document.getElementById('router-classes-builder');
        if (!list) return;
        if (list.children.length >= 10) { this.showNotification('Максимум 10 классов', 'warning'); return; }
        const row = document.createElement('div');
        row.className = 'router-class-row';
        row.style.display = 'grid';
        row.style.gridTemplateColumns = '1fr 2fr auto';
        row.style.gap = '8px';
        row.innerHTML = `
            <input type="text" class="rc-name" placeholder="name (ключ)" value="${this.escapeHtml(initial.name)}">
            <input type="text" class="rc-desc" placeholder="description" value="${this.escapeHtml(initial.description)}">
            <button class="btn btn-danger btn-sm rc-remove">✕</button>
        `;
        row.querySelector('.rc-remove').addEventListener('click', () => row.remove());
        list.appendChild(row);
    }

    addRouterExampleRow(initial = { query: '', expected_key: '', expected_value: '' }) {
        const list = document.getElementById('router-examples-builder');
        if (!list) return;
        if (list.children.length >= 10) { this.showNotification('Максимум 10 примеров', 'warning'); return; }
        const row = document.createElement('div');
        row.className = 'router-example-row';
        row.style.display = 'grid';
        row.style.gridTemplateColumns = '2fr 1fr 1fr auto';
        row.style.gap = '8px';
        row.innerHTML = `
            <input type="text" class="re-query" placeholder="query" value="${this.escapeHtml(initial.query)}">
            <input type="text" class="re-key" placeholder="expected.class (например internet_search)" value="${this.escapeHtml(initial.expected_key)}">
            <input type="text" class="re-value" placeholder="expected.value (например билеты москва рязань)" value="${this.escapeHtml(initial.expected_value)}">
            <button class="btn btn-danger btn-sm re-remove">✕</button>
        `;
        row.querySelector('.re-remove').addEventListener('click', () => row.remove());
        list.appendChild(row);
    }
}

// Initialize admin panel when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.adminPanel = new AdminPanel();
});

// Add chart styles to CSS
const chartStyles = `
    .chart-item {
        display: flex;
        align-items: center;
        margin-bottom: 0.75rem;
        gap: 0.75rem;
    }
    
    .chart-label {
        min-width: 80px;
        font-size: 0.875rem;
        color: var(--text-secondary);
    }
    
    .chart-bar {
        flex: 1;
        height: 8px;
        background-color: var(--border-color);
        border-radius: 4px;
        overflow: hidden;
    }
    
    .chart-fill {
        height: 100%;
        background: linear-gradient(90deg, var(--primary-color), var(--primary-dark));
        transition: width 0.3s ease;
    }
    
    .chart-value {
        min-width: 40px;
        text-align: right;
        font-size: 0.875rem;
        font-weight: 600;
        color: var(--text-primary);
    }
    
    .no-data {
        text-align: center;
        color: var(--text-secondary);
        font-style: italic;
        padding: 2rem;
    }
    
    .error {
        text-align: center;
        color: var(--danger-color);
        padding: 2rem;
    }
    
    .btn-sm {
        padding: 0.375rem 0.75rem;
        font-size: 0.75rem;
    }
`;

// Inject chart styles
const styleSheet = document.createElement('style');
styleSheet.textContent = chartStyles;
document.head.appendChild(styleSheet);
