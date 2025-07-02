# Insurance Manager

An educational simulation game for insurance and risk management, designed for academic use in RMI (Risk Management and Insurance) courses.

## Project Structure

- `core/` - Core game engine and interfaces
- `features/` - Pluggable game features (CEO system, employees, products, etc.)
- `api/` - FastAPI backend endpoints
- `simulations/` - Economic simulation modules
- `frontend/` - Next.js 14 frontend application
- `config/` - Game configuration and feature flags
- `tests/` - Test suites
- `docs/` - Documentation

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Python 3.12+
- Node.js 18+
- PostgreSQL 16+ (or use Docker)
- Redis 7+ (or use Docker)

### Local Development Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd insurance-manager
   ```

2. **Set up environment variables**
   ```bash
   cp example.env .env
   # Edit .env with your configuration
   # Note: A working .env file is already provided for development
   ```

3. **Install Python dependencies**
   ```bash
   pip install -r requirements.txt
   # Or create a virtual environment first:
   # python -m venv venv && source venv/bin/activate
   ```

4. **Start services with Docker Compose (optional)**
   ```bash
   docker-compose up -d postgres redis
   # Only start database services if you prefer local Python development
   ```

5. **Run database migrations**
   ```bash
   alembic upgrade head
   ```

6. **Load seed data**
   ```bash
   python scripts/load_initial_data.py
   ```

7. **Start the backend development server**
   ```bash
   uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
   ```

8. **Start the frontend development server**
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

The application will be available at:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Documentation: http://localhost:8000/docs
- Health Check: http://localhost:8000/health

## Authentication

The Insurance Manager uses JWT-based authentication with the following endpoints:

- `POST /api/v1/auth/register` - Create a new user account
- `POST /api/v1/auth/login` - Login with email and password
- `POST /api/v1/auth/logout` - Logout and revoke sessions
- `POST /api/v1/auth/refresh` - Refresh access token
- `GET /api/v1/auth/me` - Get current user info
- `GET /api/v1/auth/sessions` - List active sessions
- `DELETE /api/v1/auth/sessions/{id}` - Revoke specific session

### Example Usage

```bash
# Register a new user
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password": "SecurePass123"}'

# Login
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password": "SecurePass123"}'

# Use the access token for authenticated requests
curl -X GET http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer <access_token>"
```

## Development

### Running Tests

```bash
# Backend tests
pytest

# Frontend tests
cd frontend
npm test
```

### Code Quality

```bash
# Format Python code
black .
ruff check .

# Format TypeScript/React code
cd frontend
npm run lint
npm run format
```

See the documentation in the `docs/` directory for detailed development guidelines.

## License

This project is for educational use in academic institutions. 