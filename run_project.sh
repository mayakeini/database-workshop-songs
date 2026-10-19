#!/usr/bin/env bash
set -Eeuo pipefail

# Local demonstration database only. Do not reuse these credentials elsewhere.
readonly CONTAINER_NAME="oracle-free"
readonly ORACLE_IMAGE="gvenzl/oracle-free:23-slim"
readonly ORACLE_VOLUME="oracle-free-data"
readonly ORACLE_PASSWORD="songsproject"
readonly ORACLE_SERVICE="FREEPDB1"
readonly APP_USER="concordance"
readonly APP_PASSWORD="songsproject"

cd "$(dirname "${BASH_SOURCE[0]}")"

fail() {
    printf 'ERROR: %s\n' "$*" >&2
    exit 1
}

check_requirements() {
    echo "1. Checking required software"
    command -v docker >/dev/null 2>&1 || fail "Docker was not found. Install and start Docker Desktop/Engine."
    command -v python3 >/dev/null 2>&1 || fail "Python 3 was not found."
    docker info >/dev/null 2>&1 || fail "Docker daemon is unavailable. Start Docker Desktop/Engine."
    [[ -f requirements.txt ]] || fail "requirements.txt was not found."
    [[ -f schema.sql ]] || fail "schema.sql was not found."
    echo "Required software found."
    echo
}

prepare_image() {
    echo "2. Preparing Oracle image"
    if docker image inspect "$ORACLE_IMAGE" >/dev/null 2>&1; then
        echo "Oracle image already exists locally."
    else
        echo "Downloading Oracle image..."
        docker pull "$ORACLE_IMAGE" || fail "Could not download Oracle image."
    fi
    echo
}

prepare_python() {
    echo "3. Preparing Python environment"
    if [[ ! -x .venv/bin/python ]]; then
        echo "Creating Python virtual environment..."
        python3 -m venv .venv || fail "Could not create virtual environment."
    else
        echo "Existing virtual environment found."
    fi
    .venv/bin/python -m pip install --upgrade pip || fail "pip upgrade failed."
    .venv/bin/python -m pip install -r requirements.txt || fail "Installing dependencies failed."
    echo "Python dependencies installed."
    echo
}

sql_as_admin() {
    docker exec -i "$CONTAINER_NAME" /bin/bash -lc 'sqlplus -L -s / as sysdba'
}

sql_as_app() {
    docker exec -i "$CONTAINER_NAME" /bin/bash -lc \
        "sqlplus -L -s ${APP_USER}/${APP_PASSWORD}@localhost:1521/${ORACLE_SERVICE}"
}

oracle_ready() {
    printf '%s\n' \
        'WHENEVER OSERROR EXIT FAILURE' \
        'WHENEVER SQLERROR EXIT FAILURE' \
        "ALTER SESSION SET CONTAINER=${ORACLE_SERVICE};" \
        'SELECT 1 FROM dual;' \
        'EXIT' | sql_as_admin >/dev/null 2>&1
}

wait_for_oracle() {
    echo "Waiting for Oracle Database to accept SQL commands..."
    local attempt
    for ((attempt = 1; attempt <= 60; attempt++)); do
        if oracle_ready; then
            echo "Oracle Database is ready."
            return 0
        fi
        sleep 5
    done
    fail "Oracle did not become ready within 5 minutes; check docker logs $CONTAINER_NAME."
}

ensure_container() {
    echo "4. Starting Oracle Database"
    if docker container inspect "$CONTAINER_NAME" >/dev/null 2>&1; then
        echo "Existing Oracle container found."
        if [[ $(docker inspect -f '{{.State.Running}}' "$CONTAINER_NAME") != true ]]; then
            docker start "$CONTAINER_NAME" >/dev/null || fail "Could not start existing Oracle container."
        else
            echo "Oracle container is already running."
        fi
    else
        echo "Creating Oracle container..."
        docker run -d \
            --name "$CONTAINER_NAME" \
            -p 1521:1521 \
            -e "ORACLE_PASSWORD=$ORACLE_PASSWORD" \
            -v "${ORACLE_VOLUME}:/opt/oracle/oradata" \
            "$ORACLE_IMAGE" || fail "Could not create Oracle container."
    fi
    wait_for_oracle
    echo
}

user_exists() {
    local output
    output=$(
        printf '%s\n' \
            'WHENEVER OSERROR EXIT FAILURE' \
            'WHENEVER SQLERROR EXIT FAILURE' \
            'SET HEADING OFF FEEDBACK OFF PAGESIZE 0 VERIFY OFF ECHO OFF' \
            "ALTER SESSION SET CONTAINER=${ORACLE_SERVICE};" \
            "SELECT 'CONCORDANCE_USER_EXISTS' FROM dba_users WHERE username = UPPER('${APP_USER}');" \
            'EXIT' | sql_as_admin
    ) || fail "Could not determine whether the project user exists. Database will not be modified."
    [[ "$output" == *CONCORDANCE_USER_EXISTS* ]]
}

ask_recreate() {
    local reply
    echo "An existing Concordance database was found."
    echo "Recreating it permanently deletes all project data in Oracle user '$APP_USER'."
    while true; do
        read -r -p 'Do you want to recreate the database? [y/N]: ' reply || reply=''
        case "$reply" in
            y|Y|yes|YES|Yes) return 0 ;;
            ''|n|N|no|NO|No) return 1 ;;
            *) printf 'Invalid response: "%s". Please enter Y or N.\n' "$reply" ;;
        esac
    done
}

check_no_conflicting_role() {
    local result
    result=$(
        printf '%s\n' \
            'WHENEVER SQLERROR EXIT FAILURE' \
            'SET HEADING OFF FEEDBACK OFF PAGESIZE 0 VERIFY OFF ECHO OFF' \
            "ALTER SESSION SET CONTAINER=${ORACLE_SERVICE};" \
            "SELECT 'CONCORDANCE_ROLE_EXISTS' FROM dba_roles WHERE role = UPPER('${APP_USER}');" \
            'EXIT' | sql_as_admin
    ) || fail "Could not check Oracle roles."
    [[ "$result" != *CONCORDANCE_ROLE_EXISTS* ]] || fail "An Oracle role named $APP_USER already exists; resolve this conflict manually."
}

drop_app_user() {
    echo "Removing existing Oracle user '$APP_USER'..."
    printf '%s\n' \
        'WHENEVER OSERROR EXIT FAILURE' \
        'WHENEVER SQLERROR EXIT FAILURE' \
        "ALTER SESSION SET CONTAINER=${ORACLE_SERVICE};" \
        "DROP USER ${APP_USER} CASCADE;" \
        'EXIT' | sql_as_admin || fail "Could not drop existing Oracle user."
}

create_app_user() {
    echo "Creating Oracle user '$APP_USER'..."
    printf '%s\n' \
        'WHENEVER OSERROR EXIT FAILURE' \
        'WHENEVER SQLERROR EXIT FAILURE' \
        "ALTER SESSION SET CONTAINER=${ORACLE_SERVICE};" \
        "CREATE USER ${APP_USER} IDENTIFIED BY ${APP_PASSWORD};" \
        "GRANT CONNECT, RESOURCE TO ${APP_USER};" \
        "GRANT UNLIMITED TABLESPACE TO ${APP_USER};" \
        'EXIT' | sql_as_admin || fail "Could not create Oracle user."
}

create_schema() {
    echo "Creating database schema..."
    {
        printf '%s\n' 'WHENEVER OSERROR EXIT FAILURE' 'WHENEVER SQLERROR EXIT FAILURE'
        cat schema.sql
        printf '\nEXIT\n'
    } | sql_as_app || fail "Could not create database schema."
    echo "Database schema created successfully."
}

configure_database() {
    echo "5. Checking project database"
    if user_exists; then
        if ask_recreate; then
            echo "Restarting Oracle to close existing application connections..."
            docker restart "$CONTAINER_NAME" >/dev/null || fail "Oracle restart failed."
            wait_for_oracle
            drop_app_user
            check_no_conflicting_role
            create_app_user
            create_schema
        else
            echo "Existing database will NOT be modified."
            echo "WARNING: Its schema must be compatible with the current schema.sql."
        fi
    else
        echo "No existing Concordance database was found. Creating it..."
        check_no_conflicting_role
        create_app_user
        create_schema
    fi
    echo "Using built-in local Oracle connection settings; existing .env is untouched."
    echo
}

main() {
    echo "========================================"
    echo " Songs Concordance Project Setup"
    echo "========================================"
    echo
    check_requirements
    prepare_image
    prepare_python
    ensure_container
    configure_database
    echo "6. Starting Streamlit application"
    echo "Setup completed. Starting Songs Concordance System..."
    exec .venv/bin/python -m streamlit run app.py
}

main "$@"
