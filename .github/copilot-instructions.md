# GitHub Copilot Instructions for CogniForge

## Project Overview

CogniForge is an advanced, AI-powered educational platform built with Flask that combines cutting-edge technology with intuitive design. The platform features:

- **Superior Database Management System v2.0**: Advanced health monitoring, live analytics, and auto-optimization
- **Overmind AI Orchestrator**: Intelligent mission planning and task execution with adaptive cycles
- **World-Class API Gateway**: RESTful CRUD API with intelligent routing, security, and observability
- **Multi-Platform Support**: Compatible with Gitpod, GitHub Codespaces, Dev Containers, and local development

## Architecture & Technology Stack

### Backend
- **Framework**: Flask (Python web framework)
- **Database ORM**: SQLAlchemy with Alembic for migrations
- **Primary Database**: PostgreSQL via Supabase (cloud-native)
- **AI/ML**: OpenRouter API gateway for LLM access (GPT-4, Claude)
- **Authentication**: Flask-Login with JWT support
- **API Validation**: Marshmallow schemas

### Frontend
- **UI Framework**: Bootstrap 5
- **JavaScript**: Vanilla JS with AJAX for async operations
- **Templates**: Jinja2 (Flask templating)

### Project Structure
```
app/
├── __init__.py           # Application factory pattern
├── models.py             # SQLAlchemy database models
├── routes.py             # Main application routes
├── admin/                # Admin panel routes and templates
├── api/                  # RESTful API endpoints
├── cli/                  # Flask CLI commands (users, database, overmind)
├── services/             # Business logic layer
│   ├── database_service.py
│   ├── admin_ai_service.py
│   ├── master_agent_service.py
│   └── agent_tools.py
├── overmind/             # AI orchestration and planning
├── middleware/           # Request/response middleware
└── templates/            # Jinja2 templates
```

## Coding Standards & Conventions

### Python Code Style
- Follow PEP 8 style guide
- Use descriptive variable names (English preferred, Arabic comments allowed)
- Maximum line length: 100 characters
- Use type hints where appropriate
- Docstrings for all public functions and classes

### Database Models
- All models inherit from `db.Model` (SQLAlchemy)
- Use snake_case for table and column names
- Always include `id`, `created_at`, and `updated_at` fields
- Add proper indexes for foreign keys and frequently queried fields
- Use relationship() for defining relationships between models

Example:
```python
class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

### API Endpoints
- Follow RESTful conventions
- Use versioning: `/api/v1/`, `/api/v2/`
- Consistent response format:
  ```json
  {
    "ok": true/false,
    "data": {...},
    "error": "error message if any",
    "meta": {"pagination": {...}}
  }
  ```
- Use proper HTTP status codes (200, 201, 400, 401, 404, 500)
- Implement pagination for list endpoints (default: 20 items per page)

### Service Layer Pattern
- Business logic goes in `app/services/`
- Keep routes thin, move logic to services
- Services should be stateless and reusable
- Use dependency injection where appropriate

### Error Handling
- Use try-except blocks with specific exceptions
- Log errors with appropriate severity levels
- Return user-friendly error messages
- Never expose internal errors or stack traces to users

## Environment & Configuration

### Environment Variables
All configuration is managed through `.env` file. Never commit `.env` to version control.

**Critical Variables:**
```bash
# Database (Supabase)
DATABASE_URL=postgresql://postgres:password@project.pooler.supabase.com:6543/postgres?sslmode=require

# AI Engine
OPENROUTER_API_KEY=sk-or-v1-xxxxx
DEFAULT_AI_MODEL=anthropic/claude-3.7-sonnet:thinking
LOW_COST_MODEL=openai/gpt-4o-mini

# Admin Seeding
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=strong-password
ADMIN_NAME=Admin User

# Flask
FLASK_DEBUG=1
SECRET_KEY=random-secret-key
```

### Database Connection
- **Always use Supabase** for production and development
- Use pooled connection (port 6543) for Codespaces/Gitpod
- Use direct connection (port 5432) for write-heavy operations
- Include `?sslmode=require` in connection string
- Percent-encode special characters in passwords (@ → %40, # → %23)

### Platform Detection
The application automatically detects the runtime environment:
- `GITPOD_WORKSPACE_ID` → Gitpod
- `CODESPACES=true` → GitHub Codespaces
- `REMOTE_CONTAINERS=true` → Dev Container

## Database Operations

### Migrations
```bash
# Create new migration
flask db migrate -m "description"

# Apply migrations
flask db upgrade

# Rollback
flask db downgrade
```

### CLI Commands
```bash
# Database health and stats
flask db health
flask db stats
flask db tables
flask db schema <table_name>
flask db optimize

# User management
flask users create-admin
flask users list
flask users create --email user@example.com --name "User Name"

# Overmind (AI orchestration)
flask overmind list
flask overmind create --objective "Task description"
flask overmind status <mission_id>
```

## AI/LLM Integration

### Agent Tools
The `app/services/agent_tools.py` module provides tools for AI agents:
- **read_file**: Read file contents with size limits
- **write_file**: Write content to files
- **generic_think**: AI reasoning and planning
- **code_index_project**: Index project files
- **code_search_lexical**: Search codebase

**Configuration:**
```bash
CODE_INDEX_MAX_FILES=2200
CODE_INDEX_INCLUDE_EXTS=.py,.md,.txt,.js,.ts,.json,.yml,.yaml
CODE_INDEX_EXCLUDE_DIRS=.git,__pycache__,venv,node_modules,dist,build
```

### Overmind Planning
- Missions are broken into tasks
- Tasks can be parallelized or sequential
- Supports streaming for large content generation
- Automatic retry on failures with exponential backoff

## API Gateway Architecture

### Security Features
- JWT token-based authentication
- Rate limiting (configurable per endpoint)
- Request signing for sensitive operations
- CORS support with whitelist
- Audit logging for all operations

### Observability
- Real-time metrics collection
- Distributed tracing with correlation IDs
- Latency tracking (P50, P95, P99)
- Health checks for all services
- Performance snapshots

### Endpoints Structure
```
/api/v1/health              # Health check
/api/v1/users               # User CRUD
/api/v1/missions            # Mission CRUD
/api/v1/tasks               # Task CRUD
/api/security/*             # Auth and security
/api/observability/*        # Metrics and monitoring
/api/gateway/*              # Gateway management
```

## Testing

### Test Structure
```
tests/
├── test_models.py          # Model tests
├── test_routes.py          # Route tests
├── test_api_gateway_complete.py
├── test_database_service.py
└── fixtures/               # Test fixtures
```

### Running Tests
```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_api_gateway_complete.py

# Run with coverage
pytest --cov=app --cov-report=html
```

### Test Conventions
- Use pytest fixtures for setup/teardown
- Mock external API calls (OpenRouter, etc.)
- Test both success and failure cases
- Use descriptive test names: `test_<feature>_<scenario>_<expected_result>`

## Security Best Practices

### Input Validation
- Always validate and sanitize user input
- Use Marshmallow schemas for API validation
- Escape HTML/SQL when rendering user content
- Validate file uploads (type, size, content)

### Authentication & Authorization
- Require authentication for all admin routes
- Use `@login_required` decorator
- Check user permissions before operations
- Implement CSRF protection for forms

### Secrets Management
- Never hardcode secrets in code
- Use environment variables for all credentials
- Rotate API keys regularly
- Use different keys for dev/staging/prod

### Database Security
- Use parameterized queries (SQLAlchemy protects by default)
- Limit query execution permissions
- Enable SSL/TLS for database connections
- Regular backups (use `flask db backup`)

## Performance Optimization

### Caching Strategy
- Query result caching with 5-minute TTL
- Use Redis for session storage (when available)
- Cache static assets with appropriate headers
- Implement ETags for conditional requests

### Database Optimization
- Add indexes on foreign keys and frequently queried columns
- Use `db.session.query().options(joinedload())` for eager loading
- Limit query results with pagination
- Run `flask db optimize` periodically

### API Performance
- Use connection pooling (Supabase Pooler)
- Implement request batching for multiple operations
- Use async operations where appropriate
- Monitor P99 latency and optimize slow endpoints

## Documentation Standards

### Code Comments
- Use inline comments sparingly (code should be self-documenting)
- Add docstrings to all public functions/classes
- Arabic comments are acceptable for complex business logic
- Keep comments up-to-date with code changes

### API Documentation
- Use Swagger/OpenAPI for API docs
- Document all endpoints with examples
- Include request/response schemas
- Specify error codes and meanings

### Markdown Documentation
- Use clear headings and structure
- Include code examples
- Add emojis for visual clarity (✅, ⚠️, 🔧, etc.)
- Support both English and Arabic when relevant

## Multi-Platform Development

### Gitpod
- Configuration in `.gitpod.yml`
- Automatic port forwarding (5000, 5432, 6543)
- Pre-installed dependencies via Dockerfile
- Skip local database wait with `SKIP_DB_WAIT=true`

### GitHub Codespaces
- Configuration in `.devcontainer/devcontainer.json`
- Uses same Dockerfile as Gitpod
- Automatic environment variable injection from secrets
- Built-in port forwarding

### Local Development
- Use Docker Compose for consistent environment
- Mount volumes for hot-reload during development
- Separate `.env` for local configuration
- Connect to Supabase or local PostgreSQL

## Common Patterns & Examples

### Creating a New Model
```python
from app import db
from datetime import datetime

class NewModel(db.Model):
    __tablename__ = 'new_models'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

### Creating a New API Endpoint
```python
from flask import Blueprint, jsonify, request
from app.models import User
from app import db

api_bp = Blueprint('api', __name__, url_prefix='/api/v1')

@api_bp.route('/users', methods=['GET'])
def list_users():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    users = User.query.paginate(page=page, per_page=per_page)
    
    return jsonify({
        'ok': True,
        'data': [user.to_dict() for user in users.items],
        'meta': {
            'page': page,
            'per_page': per_page,
            'total': users.total
        }
    })
```

### Using AI Service
```python
from app.services.admin_ai_service import AdminAIService

ai_service = AdminAIService()
response = ai_service.chat(
    message="Analyze this project",
    context={"project_files": files}
)
```

## Troubleshooting Common Issues

### Database Connection Issues
1. Verify `DATABASE_URL` in `.env`
2. Check Supabase project is active
3. Ensure SSL mode is enabled (`?sslmode=require`)
4. Verify password encoding for special characters
5. Use `flask db health` to test connection

### Migration Errors
1. Check current migration status: `flask db current`
2. Verify all models are imported in `models.py`
3. Review migration file for syntax errors
4. Try downgrade then upgrade: `flask db downgrade` → `flask db upgrade`

### AI/LLM Errors (500 errors)
1. Verify `OPENROUTER_API_KEY` is set correctly
2. Check API key has sufficient credits
3. Verify the model chain and readiness: `python scripts/fitness/check_model_registry.py`
   and `python scripts/fitness/check_model_chain_parity.py`
   (D-266: this line used to point at a `check_api_config` script that does not exist in
   this repository. An instruction pointing at nothing wastes the time of the one person
   careful enough to follow it.)
4. Review logs: `docker-compose logs web`

### Platform-Specific Issues
- **Gitpod**: Ensure `.gitpod.yml` has correct port configuration
- **Codespaces**: Set secrets at repository or org level
- **Dev Container**: Rebuild container after `.devcontainer/` changes
- **Local**: Check Docker is running and ports are available

## Important Notes

### File Naming
- Use snake_case for Python files: `database_service.py`
- Use kebab-case for documentation: `setup-guide.md`
- Use PascalCase for class names: `DatabaseService`

### Git Workflow
- Never commit `.env` files
- Use descriptive commit messages
- Create feature branches for new work
- Keep commits focused and atomic

### Documentation Updates
When making changes, update relevant documentation:
- README.md for major features
- Specific guides (SETUP_GUIDE.md, DATABASE_GUIDE_AR.md, etc.)
- API documentation (Swagger/OpenAPI)
- Code comments and docstrings

## Quick Reference Commands

```bash
# Start development server
flask run

# Start with Docker
docker-compose up -d

# Database operations
flask db upgrade
flask db health
flask users create-admin

# Testing
pytest
pytest --cov=app

# Logs
docker-compose logs -f web

# Shell access
flask shell
docker-compose exec web bash
```

## Additional Resources

- **Setup Guide**: See `SETUP_GUIDE.md` for detailed setup instructions
- **Database Guide**: See `DATABASE_SYSTEM_SUPREME_AR.md` for database documentation
- **API Guide**: See `API_GATEWAY_COMPLETE_GUIDE.md` for API documentation
- **Platform Guide**: See `MULTI_PLATFORM_SETUP.md` for multi-platform setup
- **Vector DB**: See `VECTOR_DATABASE_GUIDE_AR.md` for vector database features

---

**Built with ❤️ by Houssam Benmerah**

*These instructions help GitHub Copilot provide better suggestions tailored to the CogniForge project structure, conventions, and best practices.*
