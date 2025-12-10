#!/bin/bash

PROJECT_NAME="abc_bot"
echo "🚧 Створюю проект $PROJECT_NAME..."

# 1. Папки
mkdir -p $PROJECT_NAME/src/{handlers,keyboards,database,services,middlewares,states}
mkdir -p $PROJECT_NAME/data/{imports,orders_archive,temp}
mkdir -p $PROJECT_NAME/logs

# 2. Файли-пакети (__init__)
find $PROJECT_NAME/src -type d -exec touch {}/__init__.py \;

# 3. Основні файли
touch $PROJECT_NAME/main.py
touch $PROJECT_NAME/src/config.py
touch $PROJECT_NAME/.env
touch $PROJECT_NAME/run.sh

# 4. Модулі (порожні файли)
# Handlers
touch $PROJECT_NAME/src/handlers/{admin.py,catalog.py,cart.py,analytics.py,common.py}
# Database
touch $PROJECT_NAME/src/database/{db.py,models.py,redis_cache.py}
# Services
touch $PROJECT_NAME/src/services/{importer.py,exporter.py,calculator.py,cleaner.py}
# Keyboards
touch $PROJECT_NAME/src/keyboards/{main_menu.py,inline.py,builders.py}
# Middlewares
touch $PROJECT_NAME/src/middlewares/{auth.py,maintenance.py}
# States
touch $PROJECT_NAME/src/states/user_states.py

# 5. Requirements (Бібліотеки)
cat <<EOL > $PROJECT_NAME/requirements.txt
aiogram>=3.10.0
asyncpg
redis
pandas
openpyxl
pyxlsb
python-dotenv
loguru
EOL

# 6. Скрипт запуску
cat <<EOL > $PROJECT_NAME/run.sh
#!/bin/bash
if [ ! -d "venv" ]; then
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
else
    source venv/bin/activate
fi
python main.py
EOL
chmod +x $PROJECT_NAME/run.sh

echo "✅ Готово! Структура створена в папці $PROJECT_NAME"