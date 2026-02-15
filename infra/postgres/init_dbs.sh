#!/bin/bash
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE DATABASE gateway_db;
    CREATE DATABASE planning_db;
    CREATE DATABASE memory_db;
    CREATE DATABASE user_db;
EOSQL
