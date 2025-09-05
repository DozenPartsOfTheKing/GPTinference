#!/bin/bash

# GPTInfernse Deployment Script
# This script handles deployment and management of the GPTInfernse service

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_NAME="gptinfernse"
COMPOSE_FILE="docker-compose.yml"
ENV_FILE=".env"

# Functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_requirements() {
    log_info "Checking requirements..."
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed"
        exit 1
    fi
    
    # Check Docker Compose
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        log_error "Docker Compose is not installed"
        exit 1
    fi
    
    # Check if Ollama is running
    if ! curl -s http://localhost:11434/api/tags > /dev/null; then
        log_warning "Ollama is not running on localhost:11434"
        log_info "Please start Ollama first or update OLLAMA_BASE_URL in .env"
    fi
    
    log_success "Requirements check passed"
}

setup_environment() {
    log_info "Setting up environment..."
    
    # Create .env file if it doesn't exist
    if [ ! -f "$ENV_FILE" ]; then
        log_info "Creating .env file from template..."
        cp config.env.example "$ENV_FILE"
        
        # Generate secret key
        SECRET_KEY=$(openssl rand -hex 32)
        sed -i.bak "s/your-secret-key-here/$SECRET_KEY/" "$ENV_FILE"
        rm "$ENV_FILE.bak"
        
        log_success "Created $ENV_FILE with generated secret key"
        log_warning "Please review and update $ENV_FILE with your configuration"
    fi
    
    # Create logs directory
    mkdir -p logs
    
    # Create data directories
    mkdir -p data/{redis,prometheus,grafana}
    
    log_success "Environment setup completed"
}

build_images() {
    log_info "Building Docker images..."
    
    if command -v docker-compose &> /dev/null; then
        docker-compose build --no-cache
    else
        docker compose build --no-cache
    fi
    
    log_success "Docker images built successfully"
}

start_services() {
    log_info "Starting services..."
    
    if command -v docker-compose &> /dev/null; then
        docker-compose up -d
    else
        docker compose up -d
    fi
    
    log_success "Services started"
    
    # Wait for services to be ready
    log_info "Waiting for services to be ready..."
    sleep 10
    
    # Check API health
    for i in {1..30}; do
        if curl -s http://localhost:8000/health > /dev/null; then
            log_success "API is ready!"
            break
        fi
        
        if [ $i -eq 30 ]; then
            log_error "API failed to start within 5 minutes"
            show_logs
            exit 1
        fi
        
        sleep 10
        log_info "Waiting for API... ($i/30)"
    done
}

stop_services() {
    log_info "Stopping services..."
    
    if command -v docker-compose &> /dev/null; then
        docker-compose down
    else
        docker compose down
    fi
    
    log_success "Services stopped"
}

restart_services() {
    log_info "Restarting services..."
    stop_services
    start_services
}

show_status() {
    log_info "Service status:"
    
    if command -v docker-compose &> /dev/null; then
        docker-compose ps
    else
        docker compose ps
    fi
    
    echo ""
    log_info "API Health:"
    if curl -s http://localhost:8000/health/detailed | jq . 2>/dev/null; then
        log_success "API is healthy"
    else
        log_error "API is not responding"
    fi
}

show_logs() {
    log_info "Recent logs:"
    
    if command -v docker-compose &> /dev/null; then
        docker-compose logs --tail=50
    else
        docker compose logs --tail=50
    fi
}

follow_logs() {
    log_info "Following logs (Ctrl+C to exit):"
    
    if command -v docker-compose &> /dev/null; then
        docker-compose logs -f
    else
        docker compose logs -f
    fi
}

cleanup() {
    log_info "Cleaning up..."
    
    # Stop and remove containers
    if command -v docker-compose &> /dev/null; then
        docker-compose down -v --remove-orphans
    else
        docker compose down -v --remove-orphans
    fi
    
    # Remove images
    docker rmi $(docker images "${PROJECT_NAME}*" -q) 2>/dev/null || true
    
    # Clean up unused resources
    docker system prune -f
    
    log_success "Cleanup completed"
}

backup_data() {
    log_info "Creating backup..."
    
    BACKUP_DIR="backups/$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$BACKUP_DIR"
    
    # Backup Redis data
    if docker ps | grep -q "${PROJECT_NAME}_redis"; then
        docker exec "${PROJECT_NAME}_redis_1" redis-cli BGSAVE
        sleep 5
        docker cp "${PROJECT_NAME}_redis_1:/data/dump.rdb" "$BACKUP_DIR/redis_dump.rdb"
    fi
    
    # Backup configuration
    cp -r config/ "$BACKUP_DIR/" 2>/dev/null || true
    cp "$ENV_FILE" "$BACKUP_DIR/" 2>/dev/null || true
    
    log_success "Backup created at $BACKUP_DIR"
}

update_service() {
    log_info "Updating service..."
    
    # Create backup first
    backup_data
    
    # Pull latest changes (if using git)
    if [ -d ".git" ]; then
        git pull
    fi
    
    # Rebuild and restart
    build_images
    restart_services
    
    log_success "Service updated successfully"
}

install_ollama_models() {
    log_info "Installing recommended Ollama models..."
    
    MODELS=("llama3" "mistral" "codellama")
    
    for model in "${MODELS[@]}"; do
        log_info "Pulling $model..."
        if curl -X POST http://localhost:11434/api/pull -d "{\"name\":\"$model\"}" > /dev/null 2>&1; then
            log_success "$model installed"
        else
            log_warning "Failed to install $model"
        fi
    done
}

show_help() {
    echo "GPTInfernse Deployment Script"
    echo ""
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  install     - Full installation (setup + build + start)"
    echo "  start       - Start all services"
    echo "  stop        - Stop all services"
    echo "  restart     - Restart all services"
    echo "  status      - Show service status"
    echo "  logs        - Show recent logs"
    echo "  logs-f      - Follow logs"
    echo "  build       - Build Docker images"
    echo "  update      - Update service (backup + rebuild + restart)"
    echo "  backup      - Create data backup"
    echo "  cleanup     - Clean up containers and images"
    echo "  models      - Install recommended Ollama models"
    echo "  help        - Show this help"
    echo ""
    echo "Examples:"
    echo "  $0 install          # Full installation"
    echo "  $0 start            # Start services"
    echo "  $0 logs-f           # Follow logs"
    echo "  $0 status           # Check status"
}

# Main script
case "${1:-help}" in
    install)
        check_requirements
        setup_environment
        build_images
        start_services
        log_success "Installation completed!"
        log_info "API available at: http://localhost:8000"
        log_info "Flower monitoring: http://localhost:5555"
        log_info "Grafana dashboard: http://localhost:3000 (admin/admin123)"
        ;;
    start)
        start_services
        ;;
    stop)
        stop_services
        ;;
    restart)
        restart_services
        ;;
    status)
        show_status
        ;;
    logs)
        show_logs
        ;;
    logs-f)
        follow_logs
        ;;
    build)
        build_images
        ;;
    update)
        update_service
        ;;
    backup)
        backup_data
        ;;
    cleanup)
        cleanup
        ;;
    models)
        install_ollama_models
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        log_error "Unknown command: $1"
        show_help
        exit 1
        ;;
esac
