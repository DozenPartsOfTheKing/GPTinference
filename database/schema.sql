-- GPTInfernse Database Schema
-- Гибридная архитектура: PostgreSQL для персистентности + Redis для кэша

-- Пользователи
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_identifier VARCHAR(255) UNIQUE NOT NULL, -- anon_xxx, user_xxx, session_xxx
    display_name VARCHAR(255),
    email VARCHAR(255),
    preferences JSONB DEFAULT '{}',
    facts TEXT[],
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_active TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    is_active BOOLEAN DEFAULT TRUE
);

-- Диалоги
CREATE TABLE conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id VARCHAR(255) UNIQUE NOT NULL, -- conv_xxx
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(500),
    summary TEXT,
    topics TEXT[],
    total_tokens INTEGER DEFAULT 0,
    message_count INTEGER DEFAULT 0,
    model_used VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE, -- TTL для автоочистки
    is_active BOOLEAN DEFAULT TRUE
);

-- Сообщения в диалогах
CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id VARCHAR(255) UNIQUE NOT NULL, -- msg_xxx
    conversation_id UUID REFERENCES conversations(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    tokens INTEGER,
    model VARCHAR(100),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Индекс для быстрого поиска по диалогу
    INDEX idx_messages_conversation (conversation_id, created_at),
    INDEX idx_messages_role (role),
    INDEX idx_messages_created (created_at)
);

-- Системная память (факты, настройки, статистика)
CREATE TABLE system_memory (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    key VARCHAR(255) UNIQUE NOT NULL,
    value JSONB NOT NULL,
    memory_type VARCHAR(50) NOT NULL,
    priority VARCHAR(20) DEFAULT 'medium',
    tags TEXT[],
    access_count INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE,
    last_accessed TIMESTAMP WITH TIME ZONE
);

-- Сессии пользователей (для быстрого доступа)
CREATE TABLE user_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_token VARCHAR(255) UNIQUE NOT NULL,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    conversation_id UUID REFERENCES conversations(id) ON DELETE SET NULL,
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() + INTERVAL '7 days',
    is_active BOOLEAN DEFAULT TRUE
);

-- Статистика использования
CREATE TABLE usage_stats (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    conversation_id UUID REFERENCES conversations(id) ON DELETE CASCADE,
    model VARCHAR(100),
    tokens_used INTEGER,
    processing_time_ms INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Партиционирование по дате для производительности
    INDEX idx_usage_stats_date (created_at),
    INDEX idx_usage_stats_user (user_id, created_at),
    INDEX idx_usage_stats_model (model, created_at)
);

-- Индексы для производительности
CREATE INDEX idx_users_identifier ON users(user_identifier);
CREATE INDEX idx_users_active ON users(last_active) WHERE is_active = TRUE;

CREATE INDEX idx_conversations_user ON conversations(user_id, created_at);
CREATE INDEX idx_conversations_active ON conversations(updated_at) WHERE is_active = TRUE;
CREATE INDEX idx_conversations_expires ON conversations(expires_at) WHERE expires_at IS NOT NULL;

CREATE INDEX idx_system_memory_type ON system_memory(memory_type);
CREATE INDEX idx_system_memory_expires ON system_memory(expires_at) WHERE expires_at IS NOT NULL;

CREATE INDEX idx_sessions_token ON user_sessions(session_token) WHERE is_active = TRUE;
CREATE INDEX idx_sessions_expires ON user_sessions(expires_at) WHERE is_active = TRUE;

-- Триггеры для автообновления timestamps
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_conversations_updated_at BEFORE UPDATE ON conversations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_system_memory_updated_at BEFORE UPDATE ON system_memory
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Функция для очистки истекших данных
CREATE OR REPLACE FUNCTION cleanup_expired_data()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER := 0;
BEGIN
    -- Удаляем истекшие диалоги
    DELETE FROM conversations 
    WHERE expires_at IS NOT NULL AND expires_at < NOW();
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    
    -- Удаляем истекшие сессии
    DELETE FROM user_sessions 
    WHERE expires_at < NOW();
    
    -- Удаляем истекшую системную память
    DELETE FROM system_memory 
    WHERE expires_at IS NOT NULL AND expires_at < NOW();
    
    -- Удаляем старую статистику (старше 90 дней)
    DELETE FROM usage_stats 
    WHERE created_at < NOW() - INTERVAL '90 days';
    
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- Представления для удобного доступа
CREATE VIEW active_conversations AS
SELECT 
    c.*,
    u.user_identifier,
    u.display_name,
    COUNT(m.id) as actual_message_count,
    MAX(m.created_at) as last_message_at
FROM conversations c
LEFT JOIN users u ON c.user_id = u.id
LEFT JOIN messages m ON c.id = m.conversation_id
WHERE c.is_active = TRUE
GROUP BY c.id, u.user_identifier, u.display_name;

CREATE VIEW conversation_summaries AS
SELECT 
    c.conversation_id,
    c.title,
    c.summary,
    c.topics,
    c.total_tokens,
    c.message_count,
    c.created_at,
    c.updated_at,
    u.user_identifier,
    ARRAY_AGG(
        json_build_object(
            'role', m.role,
            'content', LEFT(m.content, 200),
            'created_at', m.created_at
        ) ORDER BY m.created_at DESC
    ) FILTER (WHERE m.id IS NOT NULL) as recent_messages
FROM conversations c
LEFT JOIN users u ON c.user_id = u.id
LEFT JOIN messages m ON c.id = m.conversation_id
WHERE c.is_active = TRUE
GROUP BY c.id, u.user_identifier
ORDER BY c.updated_at DESC;

-- Комментарии для документации
COMMENT ON TABLE users IS 'Пользователи системы с их предпочтениями и фактами';
COMMENT ON TABLE conversations IS 'Диалоги пользователей с метаданными';
COMMENT ON TABLE messages IS 'Отдельные сообщения в диалогах';
COMMENT ON TABLE system_memory IS 'Системная память для настроек и фактов';
COMMENT ON TABLE user_sessions IS 'Активные сессии пользователей';
COMMENT ON TABLE usage_stats IS 'Статистика использования для аналитики';

-- Начальные данные
INSERT INTO system_memory (key, value, memory_type, priority) VALUES
('system_version', '"1.0.0"', 'system_facts', 'high'),
('default_model', '"llama3.2"', 'preferences', 'medium'),
('max_conversation_length', '50', 'preferences', 'medium'),
('cleanup_interval_hours', '24', 'preferences', 'low');
