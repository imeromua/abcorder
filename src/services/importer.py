import pandas as pd
import logging
from src.database.db import db

# Словник: Як колонка називається в Файлі -> Як називається в Базі
COLUMN_MAPPING = {
    "Артикул": "article",
    "Найменування": "name",
    "Відділ": "department",
    # Збираємо шлях з кількох колонок, але основна для навігації це Група
    # Тут ми зробимо хитрість у коді нижче
    "Постачальник": "supplier",
    "Резидент": "resident",
    "DP": "cluster",             # Ми перейменували DP в cluster
    "Розхід, кіл.": "sales_qty",
    "Розхід ц.р., грн.": "sales_sum",
    "Залишок, кіл.": "stock_qty",
    "Залишок, грн.": "stock_sum"
}

class ImporterService:
    async def import_file(self, file_path: str):
        """Головна функція імпорту"""
        try:
            # 1. Читаємо файл (визначаємо формат)
            if file_path.endswith('.csv'):
                df = pd.read_csv(file_path)
            else:
                df = pd.read_excel(file_path)

            # 2. Чистимо і перейменовуємо
            # Видаляємо рядки, де немає Артикула
            df = df.dropna(subset=['Артикул'])
            
            # Формуємо повний шлях категорії: Відділ / Група / Підгрупа
            # (Заповнюємо порожні значення пустими рядками)
            df = df.fillna('')
            df['category_path'] = df['Департамент'].astype(str) + "/" + \
                                  df['Група'].astype(str) + "/" + \
                                  df['Підгрупа'].astype(str)

            # Перейменовуємо колонки
            df = df.rename(columns=COLUMN_MAPPING)

            # Залишаємо тільки ті колонки, які є в нашій базі
            valid_cols = list(COLUMN_MAPPING.values()) + ['category_path']
            # Перевіряємо, чи всі колонки знайшлись (щоб не впасти)
            available_cols = [c for c in valid_cols if c in df.columns]
            df = df[available_cols]

            # 3. Перетворюємо дані для SQL
            # Артикул має бути рядком
            df['article'] = df['article'].astype(str)
            # Числа мають бути числами (замінюємо коми на крапки, якщо треба, і нулі)
            numeric_cols = ['sales_qty', 'sales_sum', 'stock_qty', 'stock_sum', 'department']
            for col in numeric_cols:
                if col in df.columns:
                    # Видаляємо пробіли, замінюємо коми
                    df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', '.').replace('', '0'), errors='coerce').fillna(0)

            records = df.to_dict('records')
            total = len(records)
            logging.info(f"📊 Зчитано {total} рядків. Починаю завантаження в БД...")

            # 4. Виконуємо Upsert (Вставка або Оновлення)
            # Робимо це пачками (batch), щоб не вбити пам'ять
            batch_size = 1000
            for i in range(0, total, batch_size):
                batch = records[i:i + batch_size]
                await self._insert_batch(batch)
                logging.info(f"   Processed {min(i + batch_size, total)}/{total}")

            return total

        except Exception as e:
            logging.error(f"Import Error: {e}")
            raise e

    async def _insert_batch(self, batch):
        """SQL магія для масової вставки"""
        # Формуємо список значень
        values = []
        for row in batch:
            values.append((
                row.get('article'), row.get('name'), int(row.get('department', 0)),
                row.get('category_path'), row.get('supplier'), row.get('resident'),
                row.get('cluster'), 
                float(row.get('sales_qty', 0)), float(row.get('sales_sum', 0)),
                float(row.get('stock_qty', 0)), float(row.get('stock_sum', 0))
            ))

        query = """
            INSERT INTO products (
                article, name, department, category_path, supplier, resident, cluster,
                sales_qty, sales_sum, stock_qty, stock_sum, updated_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, CURRENT_TIMESTAMP)
            ON CONFLICT (article) DO UPDATE SET
                name = EXCLUDED.name,
                sales_qty = EXCLUDED.sales_qty,
                sales_sum = EXCLUDED.sales_sum,
                stock_qty = EXCLUDED.stock_qty,
                stock_sum = EXCLUDED.stock_sum,
                cluster = EXCLUDED.cluster,
                updated_at = CURRENT_TIMESTAMP;
        """
        # executemany працює швидко
        await db.pool.executemany(query, values)

importer = ImporterService()