@echo off
setlocal

echo 1. Download Oracle image
docker pull gvenzl/oracle-free:23-slim
if errorlevel 1 exit /b 1

echo 2. Build Python venv
python -m venv .venv
if errorlevel 1 exit /b 1
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 exit /b 1

echo 3. Run Oracle container and create schema
docker rm -f oracle-free 2>nul
docker run -d ^
  --name oracle-free ^
  -p 1521:1521 ^
  -e ORACLE_PASSWORD=your_password ^
  -v oracle-free-data:/opt/oracle/oradata ^
  gvenzl/oracle-free:23-slim
if errorlevel 1 exit /b 1

:wait_for_oracle
docker logs oracle-free 2>&1 | findstr /C:"DATABASE IS READY TO USE" >nul
if errorlevel 1 (
  timeout /t 5 /nobreak >nul
  goto wait_for_oracle
)

(
echo ORACLE_HOST=localhost
echo ORACLE_PORT=1521
echo ORACLE_SERVICE=FREEPDB1
echo ORACLE_USER=concordance
echo ORACLE_PASSWORD=your_password
) > .env

(
echo ALTER SESSION SET CONTAINER=FREEPDB1;
echo DROP USER concordance CASCADE;
echo CREATE USER concordance IDENTIFIED BY your_password;
echo GRANT CONNECT, RESOURCE TO concordance;
echo ALTER USER concordance QUOTA UNLIMITED ON USERS;
echo EXIT
) | docker exec -i oracle-free /bin/bash -lc "sqlplus -s / as sysdba"
if errorlevel 1 exit /b 1

type schema.sql > "%TEMP%\concordance_schema.sql"
echo EXIT>> "%TEMP%\concordance_schema.sql"
type "%TEMP%\concordance_schema.sql" | docker exec -i oracle-free /bin/bash -lc "sqlplus -s concordance/your_password@localhost:1521/FREEPDB1"
if errorlevel 1 exit /b 1

echo 4. Run Streamlit app
.venv\Scripts\python.exe -m streamlit run app.py
