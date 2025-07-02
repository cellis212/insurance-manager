# PostgreSQL Initialization Scripts

This directory contains SQL scripts that are automatically executed when the PostgreSQL container is first initialized.

Files in this directory are executed in alphabetical order during the first startup of the PostgreSQL container (when the data directory is empty).

## Usage

- Place `.sql` or `.sh` scripts here for database initialization
- Scripts are executed once when the container is first created
- Use this for initial data seeding or database setup that should happen before Alembic migrations

## Note

The main database schema is managed by Alembic migrations in the `/migrations/versions/` directory. This directory is primarily for any custom initialization scripts that need to run before the application starts.