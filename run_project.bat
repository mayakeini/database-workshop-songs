@echo off
setlocal EnableExtensions

cd /d "%~dp0"

rem ============================================================
rem Configuration
rem ============================================================

set "CONTAINER_NAME=oracle-free"
set "ORACLE_IMAGE=gvenzl/oracle-free:23-slim"
set "ORACLE_VOLUME=oracle-free-data"

set "ORACLE_PASSWORD=songsproject"
set "ORACLE_SERVICE=FREEPDB1"

set "APP_USER=concordance"
set "APP_PASSWORD=songsproject"


echo ========================================
echo  Songs Concordance Project Setup
echo ========================================
echo.


rem ============================================================
rem 1. Check required software
rem ============================================================

echo 1. Checking required software

docker --version >nul 2>&1

if errorlevel 1 (
    echo.
    echo ERROR: Docker was not found.
    echo Please install and start Docker Desktop, then run this script again.
    exit /b 1
)

call :find_python

if errorlevel 1 (
    echo.
    echo ERROR: Python was not found.
    echo Please install Python and run this script again.
    exit /b 1
)

echo Required software found.
echo.


rem ============================================================
rem 2. Prepare Oracle Docker image
rem ============================================================

echo 2. Preparing Oracle image

docker image inspect %ORACLE_IMAGE% >nul 2>&1

if errorlevel 1 (
    echo Oracle image was not found locally.
    echo Downloading Oracle image...

    docker pull %ORACLE_IMAGE%

    if errorlevel 1 (
        echo.
        echo ERROR: Failed to download the Oracle image.
        echo Make sure Docker Desktop is running and you have internet access.
        exit /b 1
    )
) else (
    echo Oracle image already exists locally.
)

echo.


rem ============================================================
rem 3. Prepare Python environment
rem ============================================================

echo 3. Preparing Python environment

if not exist ".venv\Scripts\python.exe" (
    echo Creating Python virtual environment...

    call :create_virtual_environment

    if errorlevel 1 (
        echo.
        echo ERROR: Failed to create Python virtual environment.
        exit /b 1
    )

    echo Virtual environment created.
) else (
    echo Existing virtual environment found.
)

echo Installing Python dependencies...

.venv\Scripts\python.exe -m pip install --upgrade pip

if errorlevel 1 (
    echo.
    echo ERROR: Failed to upgrade pip.
    exit /b 1
)

.venv\Scripts\python.exe -m pip install -r requirements.txt

if errorlevel 1 (
    echo.
    echo ERROR: Failed to install Python dependencies.
    exit /b 1
)

echo Python dependencies installed.
echo.


rem ============================================================
rem 4. Start Oracle Database
rem ============================================================

echo 4. Starting Oracle Database

call :ensure_oracle_container

if errorlevel 1 (
    exit /b 1
)

call :wait_for_oracle

if errorlevel 1 (
    exit /b 1
)

echo Oracle Database is ready.
echo.


rem ============================================================
rem 5. Check project database
rem ============================================================

echo 5. Checking project database
echo.

call :check_app_user

if errorlevel 2 (
    echo.
    echo ERROR: Failed to check the existing Oracle database.
    exit /b 1
)

if errorlevel 1 (
    set "USER_EXISTS=0"
) else (
    set "USER_EXISTS=1"
)


if "%USER_EXISTS%"=="1" (
    call :ask_recreate

    if errorlevel 2 (
        set "RECREATE_DATABASE=yes"
    ) else (
        set "RECREATE_DATABASE=no"
    )
) else (
    echo No existing Concordance database was found.
    echo A new project database will be created.
    echo.

    set "RECREATE_DATABASE=yes"
)


if /I "%RECREATE_DATABASE%"=="yes" (
    call :recreate_database

    if errorlevel 1 (
        exit /b 1
    )
) else (
    call :preserve_database

    if errorlevel 1 (
        exit /b 1
    )
)


rem ============================================================
rem 6. Start Streamlit
rem ============================================================

echo.
echo 6. Starting Streamlit application
echo.
echo Setup completed successfully.
echo Using built-in local Oracle connection settings.
echo.
echo Starting Songs Concordance System...
echo.

.venv\Scripts\python.exe -m streamlit run app.py

exit /b %ERRORLEVEL%


rem ============================================================
rem Subroutine: Find Python
rem ============================================================

:find_python

python --version >nul 2>&1

if not errorlevel 1 (
    set "PYTHON_COMMAND=python"
    exit /b 0
)

py -3 --version >nul 2>&1

if not errorlevel 1 (
    set "PYTHON_COMMAND=py -3"
    exit /b 0
)

exit /b 1


rem ============================================================
rem Subroutine: Create virtual environment
rem ============================================================

:create_virtual_environment

if "%PYTHON_COMMAND%"=="python" (
    python -m venv .venv
    exit /b %ERRORLEVEL%
)

py -3 -m venv .venv
exit /b %ERRORLEVEL%


rem ============================================================
rem Subroutine: Ensure Oracle container exists and is running
rem ============================================================

:ensure_oracle_container

docker container inspect %CONTAINER_NAME% >nul 2>&1

if errorlevel 1 (
    echo No existing Oracle container found.
    echo Creating Oracle container...

    docker run -d ^
        --name %CONTAINER_NAME% ^
        -p 1521:1521 ^
        -e ORACLE_PASSWORD=%ORACLE_PASSWORD% ^
        -v %ORACLE_VOLUME%:/opt/oracle/oradata ^
        %ORACLE_IMAGE%

    if errorlevel 1 (
        echo.
        echo ERROR: Failed to create Oracle container.
        exit /b 1
    )

    echo Oracle container created.
    exit /b 0
)

echo Existing Oracle container found.

docker inspect -f "{{.State.Running}}" %CONTAINER_NAME% | findstr /I /X "true" >nul

if errorlevel 1 (
    echo Starting existing Oracle container...

    docker start %CONTAINER_NAME% >nul

    if errorlevel 1 (
        echo.
        echo ERROR: Failed to start Oracle container.
        exit /b 1
    )

    echo Oracle container started.
) else (
    echo Oracle container is already running.
)

exit /b 0


rem ============================================================
rem Subroutine: Wait until Oracle REALLY accepts SQL commands
rem ============================================================

:wait_for_oracle

echo Waiting for Oracle Database to become ready...

set /a WAIT_ATTEMPTS=0

:wait_for_oracle_loop

set /a WAIT_ATTEMPTS+=1

call :test_oracle_connection

if not errorlevel 1 (
    exit /b 0
)

if %WAIT_ATTEMPTS% GEQ 60 (
    echo.
    echo ERROR: Oracle Database did not become ready in time.
    echo Check the Docker container status and logs.
    exit /b 1
)

timeout /t 5 /nobreak >nul
goto wait_for_oracle_loop


rem ============================================================
rem Subroutine: Test a real Oracle connection
rem ============================================================

:test_oracle_connection

set "READY_FILE=%TEMP%\concordance_ready.sql"

> "%READY_FILE%" echo WHENEVER SQLERROR EXIT FAILURE
>> "%READY_FILE%" echo ALTER SESSION SET CONTAINER=%ORACLE_SERVICE%;
>> "%READY_FILE%" echo SELECT 1 FROM dual;
>> "%READY_FILE%" echo EXIT

type "%READY_FILE%" | docker exec -i %CONTAINER_NAME% /bin/bash -lc "sqlplus -s / as sysdba" >nul 2>&1

set "READY_RESULT=%ERRORLEVEL%"

del "%READY_FILE%" >nul 2>&1

exit /b %READY_RESULT%


rem ============================================================
rem Subroutine: Check whether application user exists
rem
rem Return codes:
rem   0 = user exists
rem   1 = user does not exist
rem   2 = query failed
rem ============================================================

:check_app_user

set "CHECK_FILE=%TEMP%\concordance_check_user.sql"
set "CHECK_OUTPUT=%TEMP%\concordance_check_user_output.txt"

> "%CHECK_FILE%" echo WHENEVER SQLERROR EXIT FAILURE
>> "%CHECK_FILE%" echo SET HEADING OFF
>> "%CHECK_FILE%" echo SET FEEDBACK OFF
>> "%CHECK_FILE%" echo SET PAGESIZE 0
>> "%CHECK_FILE%" echo SET VERIFY OFF
>> "%CHECK_FILE%" echo SET ECHO OFF
>> "%CHECK_FILE%" echo ALTER SESSION SET CONTAINER=%ORACLE_SERVICE%;
>> "%CHECK_FILE%" echo SELECT 'CONCORDANCE_USER_EXISTS' FROM dba_users WHERE username = 'CONCORDANCE';
>> "%CHECK_FILE%" echo EXIT

type "%CHECK_FILE%" | docker exec -i %CONTAINER_NAME% /bin/bash -lc "sqlplus -s / as sysdba" > "%CHECK_OUTPUT%" 2>&1

if errorlevel 1 (
    del "%CHECK_FILE%" >nul 2>&1
    del "%CHECK_OUTPUT%" >nul 2>&1
    exit /b 2
)

findstr /C:"CONCORDANCE_USER_EXISTS" "%CHECK_OUTPUT%" >nul

if errorlevel 1 (
    del "%CHECK_FILE%" >nul 2>&1
    del "%CHECK_OUTPUT%" >nul 2>&1
    exit /b 1
)

del "%CHECK_FILE%" >nul 2>&1
del "%CHECK_OUTPUT%" >nul 2>&1

exit /b 0


rem ============================================================
rem Subroutine: Ask whether to recreate existing database
rem
rem Return codes:
rem   2 = yes
rem   0 = no
rem ============================================================

:ask_recreate

echo An existing Concordance database was found.
echo.
echo Recreating it will permanently delete all existing
echo project data stored under the '%APP_USER%' Oracle user.
echo.

:ask_recreate_loop

set "RESPONSE="
set /p "RESPONSE=Do you want to recreate the database? [y/N]: "

if "%RESPONSE%"=="" (
    exit /b 0
)

if /I "%RESPONSE%"=="y" (
    exit /b 2
)

if /I "%RESPONSE%"=="yes" (
    exit /b 2
)

if /I "%RESPONSE%"=="n" (
    exit /b 0
)

if /I "%RESPONSE%"=="no" (
    exit /b 0
)

echo.
echo Invalid response: "%RESPONSE%"
echo Please enter Y or N.
echo.

goto ask_recreate_loop


rem ============================================================
rem Subroutine: Recreate application database
rem ============================================================

:recreate_database

if "%USER_EXISTS%"=="1" (
    echo.
    echo Closing existing database connections...

    docker restart %CONTAINER_NAME% >nul

    if errorlevel 1 (
        echo.
        echo ERROR: Failed to restart Oracle container.
        exit /b 1
    )

    echo Oracle container restarted.

    call :wait_for_oracle

    if errorlevel 1 (
        exit /b 1
    )

    echo Oracle Database is ready.
    echo.

    call :drop_app_user

    if errorlevel 1 (
        exit /b 1
    )
)

call :create_app_user

if errorlevel 1 (
    exit /b 1
)

call :create_schema

if errorlevel 1 (
    exit /b 1
)

exit /b 0


rem ============================================================
rem Subroutine: Drop application user
rem ============================================================

:drop_app_user

echo Removing existing Oracle user '%APP_USER%'...

set "DROP_FILE=%TEMP%\concordance_drop_user.sql"

> "%DROP_FILE%" echo WHENEVER SQLERROR EXIT FAILURE
>> "%DROP_FILE%" echo ALTER SESSION SET CONTAINER=%ORACLE_SERVICE%;
>> "%DROP_FILE%" echo DROP USER %APP_USER% CASCADE;
>> "%DROP_FILE%" echo EXIT

type "%DROP_FILE%" | docker exec -i %CONTAINER_NAME% /bin/bash -lc "sqlplus -s / as sysdba"

set "DROP_RESULT=%ERRORLEVEL%"

del "%DROP_FILE%" >nul 2>&1

if not "%DROP_RESULT%"=="0" (
    echo.
    echo ERROR: Failed to remove existing Oracle user.
    exit /b 1
)

echo Existing Oracle schema removed successfully.
echo.

exit /b 0


rem ============================================================
rem Subroutine: Create application user
rem ============================================================

:create_app_user

echo Creating Oracle user '%APP_USER%'...

set "CREATE_FILE=%TEMP%\concordance_create_user.sql"

> "%CREATE_FILE%" echo WHENEVER SQLERROR EXIT FAILURE
>> "%CREATE_FILE%" echo ALTER SESSION SET CONTAINER=%ORACLE_SERVICE%;
>> "%CREATE_FILE%" echo CREATE USER %APP_USER% IDENTIFIED BY %APP_PASSWORD%;
>> "%CREATE_FILE%" echo GRANT CONNECT, RESOURCE TO %APP_USER%;
>> "%CREATE_FILE%" echo GRANT UNLIMITED TABLESPACE TO %APP_USER%;
>> "%CREATE_FILE%" echo EXIT

type "%CREATE_FILE%" | docker exec -i %CONTAINER_NAME% /bin/bash -lc "sqlplus -s / as sysdba"

set "CREATE_RESULT=%ERRORLEVEL%"

del "%CREATE_FILE%" >nul 2>&1

if not "%CREATE_RESULT%"=="0" (
    echo.
    echo ERROR: Failed to create Oracle user.
    exit /b 1
)

echo Oracle user created successfully.
echo.

exit /b 0


rem ============================================================
rem Subroutine: Create project schema
rem ============================================================

:create_schema

echo Creating database schema...

if not exist "schema.sql" (
    echo.
    echo ERROR: schema.sql was not found.
    exit /b 1
)

set "SCHEMA_FILE=%TEMP%\concordance_schema.sql"

> "%SCHEMA_FILE%" echo WHENEVER SQLERROR EXIT FAILURE
type "schema.sql" >> "%SCHEMA_FILE%"
>> "%SCHEMA_FILE%" echo.
>> "%SCHEMA_FILE%" echo EXIT

type "%SCHEMA_FILE%" | docker exec -i %CONTAINER_NAME% /bin/bash -lc "sqlplus -s %APP_USER%/%APP_PASSWORD%@localhost:1521/%ORACLE_SERVICE%"

set "SCHEMA_RESULT=%ERRORLEVEL%"

del "%SCHEMA_FILE%" >nul 2>&1

if not "%SCHEMA_RESULT%"=="0" (
    echo.
    echo ERROR: Failed to create database schema.
    exit /b 1
)

echo Database schema created successfully.
echo.

exit /b 0


rem ============================================================
rem Subroutine: Preserve existing database
rem ============================================================

:preserve_database

echo.
echo Existing database will NOT be modified.
echo.
echo WARNING:
echo The existing database schema was not recreated.
echo If it does not match the current schema.sql,
echo some application features may not work correctly.
echo.

exit /b 0
