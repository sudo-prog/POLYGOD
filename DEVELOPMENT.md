# POLYGOD Development Guide

## 🚀 Quick Start

### Prerequisites
- Python 3.12+
- Node.js 18+
- `uv` package manager
- Docker & Docker Compose (optional)

### Setup
```bash
# Install all dependencies
make install

# Or manually:
uv sync                              # Install Python dependencies
cd src/frontend && npm install       # Install frontend dependencies
uv run pre-commit install            # Install pre-commit hooks
```

### Development
```bash
# Start both backend and frontend
make dev

# Or separately:
make backend   # Start FastAPI server on port 8000
make frontend  # Start Vite dev server
```

## 📦 Installed Tools

### Python Backend Tools

| Tool | Purpose |
|------|---------|
| **Black** | Code formatter |
| **Ruff** | Linter and formatter |
| **Mypy** | Static type checker |
| **Pytest** | Testing framework |
| **Pytest-cov** | Test coverage |
| **Pre-commit** | Git hooks |
| **IPython** | Enhanced REPL |
| **Alembic** | Database migrations |

### Frontend Tools

| Tool | Purpose |
|------|---------|
| **Prettier** | Code formatter |
| **ESLint** | Linter |
| **Vitest** | Testing framework |
| **Testing Library** | React component testing |
| **Tailwind CSS** | Utility-first CSS |
| **TypeScript** | Type-safe JavaScript |

### VS Code Extensions (Recommended)

The following extensions are recommended (`.vscode/extensions.json`):

- Python & Pylance
- Black Formatter
- Ruff
- ESLint
- Prettier
- Tailwind CSS IntelliSense
- Docker
- GitLens
- Error Lens

## 🧪 Testing

### Backend Tests
```bash
# Run all tests
make test-backend

# Run with coverage
uv run pytest --cov=src/backend --cov-report=html

# Run specific test file
uv run pytest tests/test_markets.py

# Run with verbose output
uv run pytest -v
```

### Frontend Tests
```bash
# Run all tests
make test-frontend

# Run in watch mode
npm run test:watch

# Run with coverage
npm run test:coverage

# Open test UI
npm run test:ui
```

## 🔍 Linting & Formatting

### Backend
```bash
# Format code
make format-backend

# Check for issues
uv run ruff check src/backend/
uv run mypy src/backend/

# Fix auto-fixable issues
uv run ruff check --fix src/backend/
```

### Frontend
```bash
# Format code
make format-frontend

# Lint code
cd src/frontend && npm run lint

# Fix auto-fixable issues
cd src/frontend && npm run lint -- --fix
```

### All Code
```bash
# Format everything
make format

# Lint everything
make lint
```

## 🐳 Docker

```bash
# Start containers
make docker-up

# Stop containers
make docker-down

# Build containers
make docker-build

# View logs
make logs

# Connect to PostgreSQL
make psql

# Connect to Redis
make redis-cli
```

## 📊 Database

### Migrations
```bash
# Run migrations
make migrate

# Create new migration
make migrate-create

# Seed database
make seed
```

## 🛠️ Development Scripts

### Make Commands

| Command | Description |
|---------|-------------|
| `make help` | Show all available commands |
| `make install` | Install all dependencies |
| `make dev` | Start development servers |
| `make test` | Run all tests |
| `make lint` | Run all linters |
| `make format` | Format all code |
| `make clean` | Clean build artifacts |
| `make docker-up` | Start Docker containers |
| `make docker-down` | Stop Docker containers |
| `make migrate` | Run database migrations |
| `make check` | Run linters and tests |
| `make pre-commit` | Run pre-commit hooks |
| `make update-deps` | Update dependencies |
| `make health` | Check backend health |
| `make setup` | Full project setup |
| `make ci` | CI pipeline (lint + test) |

## 🔧 Configuration Files

### Python Configuration (`pyproject.toml`)
- Project dependencies
- Ruff linter settings
- Pytest configuration
- Black formatter settings

### Frontend Configuration
- `package.json`: Dependencies and scripts
- `vite.config.ts`: Vite build configuration
- `tailwind.config.js`: Tailwind CSS settings
- `tsconfig.json`: TypeScript configuration

### Editor Configuration
- `.editorconfig`: Editor-agnostic settings
- `.vscode/settings.json`: VS Code workspace settings
- `.prettierrc`: Prettier formatting rules
- `.pre-commit-config.yaml`: Git hooks

## 📝 Code Quality

### Pre-commit Hooks
Pre-commit hooks run automatically before each commit:
- Trailing whitespace removal
- End-of-file fixer
- YAML validation
- Large file check
- Merge conflict detection
- Black formatting (Python)
- Ruff linting (Python)
- Mypy type checking (Python)
- Prettier formatting (Frontend)

### CI/CD
Run the full CI pipeline locally:
```bash
make ci
```

This runs:
1. All linters
2. All tests

## 🐛 Debugging

### Backend
```bash
# Start with reload
uvicorn src.backend.main:app --reload --port 8000

# Use IPython for debugging
uv run ipython

# Run with verbose logging
LOG_LEVEL=DEBUG uvicorn src.backend.main:app --reload
```

### Frontend
```bash
# Start dev server
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview
```

## 📚 Additional Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [React Documentation](https://react.dev/)
- [Vite Documentation](https://vitejs.dev/)
- [Tailwind CSS Documentation](https://tailwindcss.com/)
- [TypeScript Documentation](https://www.typescriptlang.org/)
