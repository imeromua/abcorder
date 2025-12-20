# Використовуємо Python 3.11 (стабільний і швидкий)
FROM python:3.11-slim

# Встановлюємо робочу директорію
WORKDIR /app

# Оновлюємо систему та ставимо git (іноді потрібен для бібліотек)
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Копіюємо requirements і ставимо бібліотеки
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копіюємо весь код проекту
COPY . .

# Запускаємо бота
CMD ["python", "main.py"]