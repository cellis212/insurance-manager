# Insurance Manager MVP - Quick Start Guide

## 🎯 MVP Overview

The Insurance Manager MVP is a fully functional backend for an educational insurance business simulation game. This MVP demonstrates all core game mechanics and provides a complete REST API for frontend development.

## ⚡ Quick Start

### Option 1: Use the Startup Script (Recommended)
```bash
./start_mvp.sh
```

This script will:
- Check and start PostgreSQL and Redis
- Run database migrations
- Start the FastAPI server
- Show you where to access the API

### Option 2: Manual Startup
```bash
# Activate virtual environment
source venv/bin/activate

# Start services (if not running)
sudo -u postgres pg_ctlcluster 17 main start
sudo redis-server --daemonize yes

# Run migrations
alembic upgrade head

# Start API server
uvicorn api.main:app --host 127.0.0.1 --port 8001 --reload
```

## 🌐 Access the MVP

Once started, you can access:

- **API Base**: http://127.0.0.1:8001
- **API Documentation**: http://127.0.0.1:8001/api/docs
- **Health Check**: http://127.0.0.1:8001/api/v1/health

## 🎮 Using the API

### Authentication
```bash
# Register a new user
curl -X POST "http://127.0.0.1:8001/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "securepassword123",
    "first_name": "John",
    "last_name": "Doe"
  }'

# Login
curl -X POST "http://127.0.0.1:8001/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "securepassword123"
  }'
```

### CEO Creation
```bash
# Create a CEO character (requires auth token)
curl -X POST "http://127.0.0.1:8001/api/v1/ceo/create" \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -H "Content-Type: application/json" \
  -d '{
    "first_name": "Jane",
    "last_name": "Smith",
    "age": 35,
    "university": "University of Pennsylvania",
    "academic_background": ["Risk Management", "Finance"]
  }'
```

### Company Creation
```bash
# Create an insurance company
curl -X POST "http://127.0.0.1:8001/api/v1/game/companies" \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Acme Insurance",
    "home_state": "Delaware",
    "initial_line_of_business": "auto"
  }'
```

## 🔧 MVP Features

### ✅ What's Working
- User registration and JWT authentication
- CEO character creation with 8 attributes
- Company creation and management
- Turn-based game mechanics
- State expansion system
- Product configuration (Basic/Standard/Premium tiers)
- Employee hiring (C-suite positions)
- Investment portfolio management
- Market events and economic cycles
- Regulatory compliance tracking
- Complete audit logging

### 📊 Game Mechanics
- **8 CEO Attributes**: Leadership, Risk Intelligence, Market Acumen, Regulatory Mastery, Innovation Capacity, Deal Making, Financial Expertise, Crisis Command
- **50 States**: Full US market with state-specific regulations
- **3 Lines of Business**: Auto, Home, Commercial insurance
- **Turn Processing**: Weekly turn cycles with decision deadlines
- **Investment System**: Bonds, Stocks, Real Estate with CFO skill effects
- **Market Events**: Boom/bust cycles, catastrophes, regulatory changes

### 🗄️ Database
- PostgreSQL with complete schema
- All relationships properly configured
- Audit trails for all actions
- JSONB fields for flexible configuration

## 📖 API Documentation

The MVP includes comprehensive API documentation accessible at `/api/docs`. This includes:

- Interactive endpoint testing
- Request/response schemas
- Authentication examples
- Error handling documentation

## 🛠️ Development

### Adding Features
The MVP uses a plugin architecture for easy extension:

```python
# Example plugin structure
class MyGamePlugin(GameSystemPlugin):
    def __init__(self):
        super().__init__()
        self.name = "MyGamePlugin"
        
    async def initialize(self, config: Dict[str, Any]) -> None:
        # Plugin initialization
        pass
```

### Configuration
Game parameters are managed through:
- Environment variables (`.env`)
- YAML semester configurations (`config/semester_configs/`)
- Database feature flags

### Database Migrations
```bash
# Create a new migration
alembic revision --autogenerate -m "Description"

# Apply migrations
alembic upgrade head

# Check current version
alembic current
```

## 🧪 Testing the MVP

### Health Check
```bash
curl http://127.0.0.1:8001/api/v1/health
# Expected: {"status":"healthy","timestamp":"...","service":"insurance-manager-api","version":"1.0.0-mvp"}
```

### Database Connection
```bash
psql -U postgres -d insurance_manager_mvp -c "SELECT COUNT(*) FROM users;"
```

### Redis Connection
```bash
redis-cli ping
# Expected: PONG
```

## 📁 MVP Structure

```
/workspace/
├── api/                     # FastAPI application
│   ├── main.py             # Main application entry
│   └── v1/                 # API version 1 endpoints
├── core/                   # Core game engine
│   ├── models/             # Database models
│   ├── database.py         # Database configuration
│   └── config.py           # Application settings
├── features/               # Game system plugins
├── migrations/             # Database migrations
├── config/                 # Game configuration files
├── .env                   # Environment variables
├── start_mvp.sh           # Quick start script
└── MVP_SUMMARY.md         # Detailed MVP documentation
```

## 🚨 Troubleshooting

### Server Won't Start
1. Check if PostgreSQL is running: `sudo systemctl status postgresql`
2. Check if Redis is running: `redis-cli ping`
3. Verify database exists: `psql -U postgres -l | grep insurance_manager_mvp`
4. Check port availability: `lsof -i :8001`

### Database Issues
```bash
# Reset database
sudo -u postgres dropdb insurance_manager_mvp
sudo -u postgres createdb insurance_manager_mvp
alembic upgrade head
```

### Permission Issues
```bash
# Fix PostgreSQL permissions
sudo -u postgres psql -c "ALTER USER postgres PASSWORD 'postgres';"
```

## 🎓 Educational Use

This MVP is ready for:
- **Classroom Demonstrations**: Show students how insurance businesses operate
- **Case Studies**: Create scenarios for business decision making
- **Research**: Collect data on student decision patterns
- **Assessment**: Evaluate understanding of insurance concepts

## 📈 Next Steps

The MVP backend is complete. Recommended next development:

1. **Frontend Development**: React/Next.js interface
2. **User Experience**: Intuitive game interface design
3. **Analytics Dashboard**: Student performance tracking
4. **Advanced Features**: AI advisors, complex market scenarios
5. **Deployment**: Production environment setup

## 🏆 Success!

Your Insurance Manager MVP is ready to use! The backend provides a complete insurance business simulation engine that's perfect for educational use and frontend development.

For detailed technical information, see `MVP_SUMMARY.md`.