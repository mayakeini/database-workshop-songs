#!/usr/bin/env bash

set -e

CONTAINER_NAME="oracle-free"
ORACLE_IMAGE="gvenzl/oracle-free:23-slim"
ORACLE_VOLUME="oracle-free-data"

ORACLE_PASSWORD="your_password"
ORACLE_SERVICE="FREEPDB1"

APP_USER="concordance"
APP_PASSWORD="your_password"

echo "========================================"
echo " Songs Concordance Project Setup"
echo "========================================"
echo


check_command() {
    local command_name="$1"

    if ! command -v "$command_name" >/dev/null 2>&1; then
        echo "ERROR: Required command '$command_name' was not found."
        echo "Please install it and run the script again."
        exit 1
    fi
}


wait_for_oracle() {
    echo "Waiting for Oracle Database to become ready..."

    until docker logs "$CONTAINER_NAME" 2>&1 \
        | grep -q "DATABASE IS READY TO USE"; do
        sleep 5
    done

    echo "Oracle Database is ready."
}


oracle_user_exists() {
    local result

    result=$(
        printf "%s\n" \
            "ALTER SESSION SET CONTAINER=${ORACLE_SERVICE};" \
            "SET HEADING OFF FEEDBACK OFF PAGESIZE 0 VERIFY OFF ECHO OFF;" \
            "SELECT COUNT(*) FROM dba_users WHERE username = UPPER('${APP_USER}');" \
            "EXIT;" \
        | docker exec -i "$CONTAINER_NAME" \
            /bin/bash -lc \
            'sqlplus -s / as sysdba'
    )

    result=$(echo "$result" | tr -d '[:space:]')

    if [ "$result" = "1" ]; then
        return 0
    fi

    return 1
}


create_app_user() {
    echo "Creating Oracle user '${APP_USER}'..."

    printf "%s\n" \
        "WHENEVER SQLERROR EXIT SQL.SQLCODE;" \
        "ALTER SESSION SET CONTAINER=${ORACLE_SERVICE};" \
        "CREATE USER ${APP_USER} IDENTIFIED BY ${APP_PASSWORD};" \
        "GRANT CONNECT, RESOURCE TO ${APP_USER};" \
        "ALTER USER ${APP_USER} QUOTA UNLIMITED ON USERS;" \
        "EXIT;" \
    | docker exec -i "$CONTAINER_NAME" \
        /bin/bash -lc \
        'sqlplus -s / as sysdba'

    echo "Oracle user '${APP_USER}' created successfully."
}


drop_app_user() {
    echo "Removing existing Oracle user '${APP_USER}'..."

    printf "%s\n" \
        "WHENEVER SQLERROR EXIT SQL.SQLCODE;" \
        "ALTER SESSION SET CONTAINER=${ORACLE_SERVICE};" \
        "DROP USER ${APP_USER} CASCADE;" \
        "EXIT;" \
    | docker exec -i "$CONTAINER_NAME" \
        /bin/bash -lc \
        'sqlplus -s / as sysdba'

    echo "Existing Oracle schema removed."
}


run_schema() {
    echo "Creating database schema..."

    (
        cat schema.sql
        printf "\nEXIT;\n"
    ) \
    | docker exec -i "$CONTAINER_NAME" \
        /bin/bash -lc \
        "sqlplus -s ${APP_USER}/${APP_PASSWORD}@localhost:1521/${ORACLE_SERVICE}"

    echo "Database schema created successfully."
}


create_env_file() {
    echo "Creating .env file..."

    cat > .env <<EOF
ORACLE_HOST=localhost
ORACLE_PORT=1521
ORACLE_SERVICE=${ORACLE_SERVICE}
ORACLE_USER=${APP_USER}
ORACLE_PASSWORD=${APP_PASSWORD}
EOF

    echo ".env file created."
}


echo "1. Checking required software"
check_command docker
check_command python3
echo "Required software found."
echo


echo "2. Downloading Oracle image"
docker pull "$ORACLE_IMAGE"
echo


echo "3. Creating Python virtual environment"
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
    echo "Virtual environment created."
else
    echo "Existing virtual environment found."
fi

.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
echo "Python dependencies installed."
echo


echo "4. Starting Oracle Database"
if docker container inspect "$CONTAINER_NAME" >/dev/null 2>&1; then
    echo "Existing Oracle container found."

    if [ "$(docker inspect -f '{{.State.Running}}' "$CONTAINER_NAME")" != "true" ]; then
        echo "Starting existing Oracle container..."
        docker start "$CONTAINER_NAME" >/dev/null
    else
        echo "Oracle container is already running."
    fi
else
    echo "No existing Oracle container found."
    echo "Creating Oracle container..."

    docker run -d \
        --name "$CONTAINER_NAME" \
        -p 1521:1521 \
        -e ORACLE_PASSWORD="$ORACLE_PASSWORD" \
        -v "${ORACLE_VOLUME}:/opt/oracle/oradata" \
        "$ORACLE_IMAGE"

    echo "Oracle container created."
fi

wait_for_oracle
echo


echo "5. Configuring project database"
if oracle_user_exists; then
    echo
    echo "An existing Concordance database was found."
    echo
    echo "Recreating it will permanently delete all existing"
    echo "project data stored under the '${APP_USER}' Oracle user."
    echo
    read -r -p "Do you want to recreate the database? [y/N]: " response
    case "$response" in
        [yY]|[yY][eE][sS])
            echo
            drop_app_user
            create_app_user
            run_schema
            ;;
        *)
            echo
            echo "Existing database will NOT be modified."
            echo
            echo "WARNING:"
            echo "The current application expects the database schema"
            echo "to match the current schema.sql file."
            echo
            echo "If the existing database uses an older schema,"
            echo "some application features may not work correctly."
            echo
            ;;
    esac
else
    echo "No existing Concordance database was found."
    create_app_user
    run_schema
fi
echo


echo "6. Creating application environment"
create_env_file
echo


echo "7. Starting Streamlit application"
echo
echo "Setup completed."
echo
echo "Starting Songs Concordance System..."
echo

.venv/bin/python -m streamlit run app.py