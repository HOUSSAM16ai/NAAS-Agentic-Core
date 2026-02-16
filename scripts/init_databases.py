import os
import sys
import time

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

# Default to postgres service
DB_HOST = os.getenv("POSTGRES_HOST", "postgres")
DB_USER = os.getenv("POSTGRES_USER", "postgres")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")
DB_PORT = os.getenv("POSTGRES_PORT", "5432")

# List of databases and their schemas
DATABASES = {
    "planning_db": "planning",
    "memory_db": "memory",
    "user_db": "user_service",
    "research_db": "research",
    "reasoning_db": "reasoning",
    "observability_db": "observability",
    "core_db": "public",  # Core kernel likely uses public schema or multiple
}


def get_conn(dbname="postgres"):
    return psycopg2.connect(
        host=DB_HOST, user=DB_USER, password=DB_PASSWORD, port=DB_PORT, dbname=dbname
    )


def wait_for_db():
    retries = 30
    while retries > 0:
        try:
            conn = get_conn()
            conn.close()
            print("Connected to PostgreSQL.")
            return
        except psycopg2.OperationalError:
            print("Waiting for PostgreSQL...")
            time.sleep(2)
            retries -= 1
    print("Could not connect to PostgreSQL.")
    sys.exit(1)


def create_databases():
    try:
        conn = get_conn()
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()

        for db_name in DATABASES:
            cursor.execute(f"SELECT 1 FROM pg_database WHERE datname = '{db_name}'")
            if not cursor.fetchone():
                print(f"Creating database {db_name}...")
                cursor.execute(f"CREATE DATABASE {db_name}")
            else:
                print(f"Database {db_name} already exists.")

        conn.close()
    except Exception as e:
        print(f"Error checking/creating databases: {e}")
        sys.exit(1)


def create_schemas():
    for db_name, schema_name in DATABASES.items():
        if schema_name == "public":
            continue

        print(f"Initializing schema {schema_name} in {db_name}...")
        try:
            conn = get_conn(dbname=db_name)
            conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            cursor = conn.cursor()

            cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {schema_name}")
            print(f"Schema {schema_name} created/verified.")

            conn.close()
        except Exception as e:
            print(f"Error initializing schema in {db_name}: {e}")
            sys.exit(1)


if __name__ == "__main__":
    wait_for_db()
    create_databases()
    create_schemas()
    print("Database initialization complete.")
