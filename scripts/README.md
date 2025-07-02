# Insurance Manager Scripts

This directory contains utility scripts for managing the Insurance Manager application.

## test_db_connection.py

Tests database connectivity before running the full data load. Use this to diagnose connection issues.

### What it does:

1. **Checks environment variables** - Verifies DATABASE_URL, REDIS_URL, SECRET_KEY are set
2. **Tests database connection** - Attempts to connect to PostgreSQL
3. **Runs basic query** - Executes SELECT 1 to verify connectivity
4. **Lists existing tables** - Shows what tables exist (if any)
5. **Runs health check** - Tests the database health check endpoint

### Usage:

```bash
# Test database connection
python scripts/test_db_connection.py
```

### Expected Output:

```
1. Checking environment variables:
  ✓ DATABASE_URL: postgresql+asyncpg://***@localhost:5432/insurance_manager
  ✓ REDIS_URL: redis://localhost:6379/0
  ✓ SECRET_KEY: ***

2. Testing database connection:
  ✓ Database initialization successful

3. Testing basic database query:
  ✓ Basic query successful

4. Checking for existing tables:
  ⚠ No tables found - migrations may need to be run

5. Running health check:
  ✓ Database is healthy: {'status': 'healthy', ...}

✅ All database connection tests passed!
```

## load_initial_data.py

Sets up a fresh database with all necessary data for running the Insurance Manager.

### What it does:

1. **Runs database migrations** - Uses Alembic to create/update all database tables
2. **Loads base game data** - All 51 US states, 5 lines of business, default game configuration
3. **Loads university data** - 70+ real US universities and 4 academic background options
4. **Creates feature flags** - Enables all 6 game plugins
5. **Creates initial semester** - Sets up a playable semester with configuration
6. **Verifies everything** - Checks that all data loaded correctly

### Prerequisites:

- PostgreSQL database running (via `docker-compose up postgres` or locally)
- Database connection configured in `.env` file
- Python environment with dependencies installed (`pip install -r requirements.txt`)

### Basic Usage:

```bash
# Load data with defaults (Spring 2024 semester starting today)
python scripts/load_initial_data.py

# Custom semester
python scripts/load_initial_data.py \
    --semester-code F24 \
    --semester-name "Fall 2024" \
    --start-date 2024-08-15

# Use specific configuration file
python scripts/load_initial_data.py \
    --config-file config/semester_configs/example_semester.yaml
```

### Command Line Options:

- `--semester-code`: Short code for the semester (default: S24)
- `--semester-name`: Full name of the semester (default: Spring 2024)
- `--start-date`: Start date in YYYY-MM-DD format (default: today)
- `--config-file`: Path to semester configuration YAML (default: example_semester.yaml)

### Verification Output:

The script verifies that all data loaded correctly:

```
✓ states: {'expected': 51, 'actual': 51, 'passed': True}
✓ lines_of_business: {'expected': 5, 'actual': 5, 'passed': True}
✓ game_configuration: {'expected': 1, 'actual': 1, 'passed': True}
✓ universities: {'expected_min': 70, 'actual': 71, 'passed': True}
✓ academic_backgrounds: {'expected': 4, 'actual': 4, 'passed': True}
✓ active_semester: {'expected': 1, 'actual': 1, 'passed': True}
✓ feature_flags: {'expected_min': 6, 'actual': 6, 'passed': True}
```

### Next Steps After Loading:

1. Start the backend services:
   ```bash
   docker-compose up
   ```

2. Access the API documentation:
   - http://localhost:8000/docs

3. Start developing the frontend or use the API directly

### Troubleshooting:

- **Migration errors**: Ensure PostgreSQL is running and connection details in `.env` are correct
- **Import errors**: Run from project root or ensure PYTHONPATH includes the project root
- **Data already exists**: The script skips existing data, so it's safe to run multiple times

### Development Notes:

- The script is idempotent - safe to run multiple times
- Existing data is preserved (not overwritten)
- All data loading follows the "no mock data" rule - everything is real data
- Feature flags enable all 6 game plugins by default

## Recommended Workflow

1. **First time setup**:
   ```bash
   # 1. Copy environment file
   cp example.env .env
   # Edit .env with your database credentials
   
   # 2. Start PostgreSQL (if using Docker)
   docker-compose up -d postgres
   
   # 3. Test connection
   python scripts/test_db_connection.py
   
   # 4. Load initial data
   python scripts/load_initial_data.py
   
   # 5. Start all services
   docker-compose up
   ```

2. **Reset database** (for development):
   ```bash
   # Stop services
   docker-compose down
   
   # Reset database volume (WARNING: deletes all data)
   docker-compose down -v
   
   # Start fresh
   docker-compose up -d postgres
   python scripts/load_initial_data.py
   ``` 