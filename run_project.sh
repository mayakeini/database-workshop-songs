#!/usr/bin/env bash
set -e

echo "1. Download Oracle image"
docker pull gvenzl/oracle-free:23-slim

echo "2. Build Python venv"
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt

echo "3. Run Oracle container and create schema"
docker rm -f oracle-free 2>/dev/null || true
docker run -d \
  --name oracle-free \
  -p 1521:1521 \
  -e ORACLE_PASSWORD=your_password \
  -v oracle-free-data:/opt/oracle/oradata \
  gvenzl/oracle-free:23-slim

until docker logs oracle-free 2>&1 | grep -q "DATABASE IS READY TO USE"; do
  sleep 5
done

cat > .env <<'EOF'
ORACLE_HOST=localhost
ORACLE_PORT=1521
ORACLE_SERVICE=FREEPDB1
ORACLE_USER=concordance
ORACLE_PASSWORD=your_password
EOF

printf "%s\n" \
"ALTER SESSION SET CONTAINER=FREEPDB1;" \
"DROP USER concordance CASCADE;" \
"CREATE USER concordance IDENTIFIED BY your_password;" \
"GRANT CONNECT, RESOURCE TO concordance;" \
"ALTER USER concordance QUOTA UNLIMITED ON USERS;" \
"EXIT" | docker exec -i oracle-free /bin/bash -lc 'sqlplus -s / as sysdba'

(cat schema.sql; printf "\nEXIT\n") | docker exec -i oracle-free /bin/bash -lc \
  'sqlplus -s concordance/your_password@localhost:1521/FREEPDB1'

echo "4. Run Streamlit app"
.venv/bin/python -m streamlit run app.py
