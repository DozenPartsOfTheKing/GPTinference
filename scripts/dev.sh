#!/bin/bash

# GPTInfernse Development Helper Script

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() {
    echo -e "${BLUE}[DEV]${NC} $1"
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

# Development environment setup
setup_dev() {
    log_info "Setting up development environment..."
    
    # Create virtual environment
    if [ ! -d "venv" ]; then
        python3 -m venv venv
        log_success "Created virtual environment"
    fi
    
    # Activate virtual environment
    source venv/bin/activate
    
    # Install dependencies
    pip install -r requirements.txt
    
    # Install development dependencies
    pip install pytest pytest-asyncio pytest-cov black isort flake8 mypy
    
    log_success "Development environment ready"
}

# Run tests
run_tests() {
    log_info "Running tests..."
    
    source venv/bin/activate
    
    # Run pytest with coverage
    pytest tests/ -v --cov=app --cov-report=html --cov-report=term
    
    log_success "Tests completed"
}

# Code formatting
format_code() {
    log_info "Formatting code..."
    
    source venv/bin/activate
    
    # Sort imports
    isort app/ tests/ --profile black
    
    # Format with black
    black app/ tests/
    
    log_success "Code formatted"
}

# Lint code
lint_code() {
    log_info "Linting code..."
    
    source venv/bin/activate
    
    # Flake8
    flake8 app/ tests/ --max-line-length=88 --extend-ignore=E203,W503
    
    # MyPy
    mypy app/ --ignore-missing-imports
    
    log_success "Linting completed"
}

# Run development server
run_dev() {
    log_info "Starting development server..."
    
    source venv/bin/activate
    
    # Set development environment
    export DEBUG=true
    export LOG_LEVEL=DEBUG
    
    # Run with reload
    python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
}

# Run Celery worker for development
run_worker() {
    log_info "Starting Celery worker..."
    
    source venv/bin/activate
    
    # Set development environment
    export DEBUG=true
    export LOG_LEVEL=DEBUG
    
    # Run worker with reload
    celery -A app.utils.celery_app.celery_app worker --loglevel=debug --reload
}

# Generate API documentation
generate_docs() {
    log_info "Generating API documentation..."
    
    source venv/bin/activate
    
    # Start server in background
    python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 &
    SERVER_PID=$!
    
    # Wait for server to start
    sleep 5
    
    # Generate OpenAPI spec
    curl -s http://localhost:8000/openapi.json > docs/openapi.json
    
    # Kill server
    kill $SERVER_PID
    
    log_success "API documentation generated"
}

# Database migrations (placeholder for future)
migrate() {
    log_info "Running database migrations..."
    
    source venv/bin/activate
    
    # TODO: Add Alembic migrations when database is implemented
    log_warning "Database migrations not implemented yet"
}

# Clean up development environment
clean_dev() {
    log_info "Cleaning development environment..."
    
    # Remove virtual environment
    rm -rf venv/
    
    # Remove cache files
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find . -type f -name "*.pyc" -delete 2>/dev/null || true
    
    # Remove test artifacts
    rm -rf .pytest_cache/ htmlcov/ .coverage
    
    log_success "Development environment cleaned"
}

# Show help
show_help() {
    echo "GPTInfernse Development Helper"
    echo ""
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  setup       - Setup development environment"
    echo "  test        - Run tests with coverage"
    echo "  format      - Format code with black and isort"
    echo "  lint        - Lint code with flake8 and mypy"
    echo "  dev         - Run development server"
    echo "  worker      - Run Celery worker"
    echo "  docs        - Generate API documentation"
    echo "  migrate     - Run database migrations"
    echo "  clean       - Clean development environment"
    echo "  help        - Show this help"
    echo ""
    echo "Examples:"
    echo "  $0 setup           # Setup dev environment"
    echo "  $0 dev             # Start dev server"
    echo "  $0 test            # Run tests"
    echo "  $0 format && $0 lint  # Format and lint code"
}

# Main script
case "${1:-help}" in
    setup)
        setup_dev
        ;;
    test)
        run_tests
        ;;
    format)
        format_code
        ;;
    lint)
        lint_code
        ;;
    dev)
        run_dev
        ;;
    worker)
        run_worker
        ;;
    docs)
        generate_docs
        ;;
    migrate)
        migrate
        ;;
    clean)
        clean_dev
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
