import pandas as pd
import logging
from src.database.db import db
from src.config import config

# Маппинг колонок (Excel -> DB)
COLUMN_MAPPING = {
    "Відділ": "department",
    "Артикул": "article",
    "Найменування": "name",
    "Постачальник": "supplier",
    "Резидент": "resident",
    "DP": "cluster",
    "Розхід, кіл.": "sales_qty",
    "Розхід ц.р., грн.": "sales_sum",
    "Залишок, кіл.": "stock_qty",
    "Залишок, грн.": "stock_sum"
}

class ImporterService:
    async def import_file(self, file_path: str) -> int:
        """
        Читає файл, фільтрує дані та оновлює базу.
        Повертає кількість імпортованих товарів.
        """
        try:
            # 1. Читання файлу
            if file_path.endswith('.csv'):
                df = pd.read_csv(file_path)
            else:
                df = pd.read_excel(file_path)

            # 2. Базове очищення
            df = df.dropna(subset=['Артикул'])  # Артикул обов'язковий
            df = df.fillna('')

            # 3. Формування шляху категорії (Breadcrumbs)
            def build_path(row):
                hierarchy_cols = ['Департамент', 'Піддеп-т', 'Група', 'Підгрупа']
                parts = []
                for col in hierarchy_cols:
                    val = str(row.get(col, '')).strip()
                    # Ігноруємо '0', 'nan', пусті рядки
                    if val and val != '0' and val.lower() != 'nan':
                        parts.append(val)
                return "/".join(parts)

            df['category_path'] = df.apply(build_path, axis=1)

            # 4. Перейменування колонок згідно маппінгу
            df = df.rename(columns=COLUMN_MAPPING)

            # Залишаємо тільки потрібні колонки
            valid_cols = list(COLUMN_MAPPING.values()) + ['category_path']
            available_cols = [c for c in valid_cols if c in df.columns]
            df = df[available_cols]

            # 5. Конвертація типів даних
            df['article'] = df['article'].astype(str)
            
            numeric_cols = ['sales_qty', 'sales_sum', 'stock_qty', 'stock_sum', 'department']
            for col in numeric_cols:
                if col in df.columns:
                    # Чистимо числа: "1 234,56" -> 1234.56
                    df[col] = pd.to_numeric(
                        df[col].astype(str).str.replace(',', '.').replace('\xa0', '').replace(' ', ''), 
                        errors='coerce'
                    ).fillna(0)

            # 6. 🔥 РОЗУМНА ФІЛЬТРАЦІЯ
            # Відсіюємо "мертві" товари згідно налаштувань .env
            initial_count = len(df)
            
            # Логіка: Залишаємо товар, ЯКЩО (Продажі >= MIN) АБО (Залишок >= MIN)
            # Тобто, видаляємо тільки якщо І продажі малі, І залишку немає.
            df = df[ 
                (df['sales_qty'] >= config.MIN_SALES) | 
                (df['stock_qty'] >= config.MIN_STOCK) 
            ]
            
            filtered_count = len(df)
            dead_items = initial_count - filtered_count
            
            if dead_items > 0:
                logging.info(f"🧹 Importer: Відфільтровано {dead_items} мертвих позицій (Sales<{config.MIN_SALES}, Stock<{config.MIN_STOCK})")

            # 7. Підготовка до вставки
            records = df.to_dict('records')
            total = len(records)
            logging.info(f"📊 До імпорту готово {total} рядків.")

            # 8. Пакетна вставка (Batch Insert)
            batch_size = 1000
            for i in range(0, total, batch_size):
                batch = records[i:i + batch_size]
                await self._insert_batch(batch)

            return total

        except Exception as e:
            logging.error(f"Import Error: {e}")
            raise e

    async def _insert_batch(self, batch):
        """Вставка пакета даних в БД"""
        values = []
        for row in batch:
            values.append((
                row.get('article'), 
                row.get('name'), 
                int(row.get('department', 0)),
                row.get('category_path'), 
                row.get('supplier'), 
                row.get('resident'),
                row.get('cluster'), 
                float(row.get('sales_qty', 0)), 
                float(row.get('sales_sum', 0)),
                float(row.get('stock_qty', 0)), 
                float(row.get('stock_sum', 0))
            ))

        query = """
            INSERT INTO products (
                article, name, department, category_path, supplier, resident, cluster,
                sales_qty, sales_sum, stock_qty, stock_sum, updated_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, CURRENT_TIMESTAMP)
            ON CONFLICT (article) DO UPDATE SET
                name = EXCLUDED.name,
                department = EXCLUDED.department,
                category_path = EXCLUDED.category_path,
                supplier = EXCLUDED.supplier,
                resident = EXCLUDED.resident,
                cluster = EXCLUDED.cluster,
                sales_qty = EXCLUDED.sales_qty,
                sales_sum = EXCLUDED.sales_sum,
                stock_qty = EXCLUDED.stock_qty,
                stock_sum = EXCLUDED.stock_sum,
                updated_at = CURRENT_TIMESTAMP;
        """
        await db.pool.executemany(query, values)

importer = ImporterService()