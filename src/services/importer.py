import logging
import pandas as pd
from src.config import config
from src.database.db import db

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
    async def import_file(self, file_path: str, status_callback=None) -> int:
        """
        Читає файл, фільтрує дані та оновлює базу.
        status_callback: асинхронна функція (current, total, stage), яку ми викликаємо для оновлення прогресу.
        """
        df = None

        try:
            # --- ЕТАП 1: ЧИТАННЯ ---
            if status_callback:
                await status_callback(0, 0, "reading")

            # Визначаємо формат
            if file_path.lower().endswith('.csv'):
                df = pd.read_csv(file_path)
            else:
                df = pd.read_excel(file_path, engine='openpyxl')

            if df is None:
                raise ValueError("Не вдалося прочитати файл (DataFrame is None)")

            # --- ЕТАП 2: ОБРОБКА ---
            
            # Базове очищення
            if 'Артикул' in df.columns:
                df = df.dropna(subset=['Артикул'])
            elif 'article' in df.columns:
                 df = df.dropna(subset=['article'])
            else:
                raise ValueError("У файлі відсутня колонка 'Артикул'")

            df = df.fillna('')

            # Формування шляху категорії
            def build_path(row):
                hierarchy_cols = ['Департамент', 'Піддеп-т', 'Група', 'Підгрупа']
                parts = []
                for col in hierarchy_cols:
                    val = str(row.get(col, '')).strip()
                    if val and val != '0' and val.lower() != 'nan':
                        parts.append(val)
                return "/".join(parts)

            if 'Департамент' in df.columns:
                df['category_path'] = df.apply(build_path, axis=1)
            else:
                df['category_path'] = ''

            # Перейменування та вибір колонок
            df = df.rename(columns=COLUMN_MAPPING)
            valid_cols = list(COLUMN_MAPPING.values()) + ['category_path']
            available_cols = [c for c in valid_cols if c in df.columns]
            df = df[available_cols]

            # Конвертація типів
            if 'article' in df.columns:
                df['article'] = df['article'].astype(str)
            
            numeric_cols = ['sales_qty', 'sales_sum', 'stock_qty', 'stock_sum', 'department']
            for col in numeric_cols:
                if col in df.columns:
                    # Чистимо від пробілів та ком
                    df[col] = pd.to_numeric(
                        df[col].astype(str).str.replace(',', '.').replace('\xa0', '').replace(' ', ''), 
                        errors='coerce'
                    ).fillna(0)

            # Фільтрація
            initial_count = len(df)
            has_sales = 'sales_qty' in df.columns
            has_stock = 'stock_qty' in df.columns

            if has_sales and has_stock:
                df = df[ 
                    (df['sales_qty'] >= config.MIN_SALES) | 
                    (df['stock_qty'] >= config.MIN_STOCK) 
                ]
            
            filtered_count = len(df)
            if initial_count - filtered_count > 0:
                logging.info(f"🧹 Importer: Відфільтровано {initial_count - filtered_count} мертвих позицій")

            # Підготовка до вставки
            records = df.to_dict('records')
            total = len(records)
            logging.info(f"📊 До імпорту готово {total} рядків.")

            if total == 0:
                return 0

            # --- ЕТАП 3: ВСТАВКА (З ПРОГРЕСОМ) ---
            batch_size = 1000
            processed = 0

            for i in range(0, total, batch_size):
                batch = records[i:i + batch_size]
                await self._insert_batch(batch)
                
                processed += len(batch)
                
                # Оновлюємо прогрес-бар
                if status_callback:
                    await status_callback(processed, total, "inserting")

            return total

        except Exception as e:
            logging.error(f"Import Error: {e}")
            raise e

    async def _insert_batch(self, batch):
        values = []
        for row in batch:
            values.append((
                row.get('article'), 
                row.get('name', ''), 
                int(row.get('department', 0)),
                row.get('category_path', ''), 
                row.get('supplier', ''), 
                row.get('resident', ''),
                row.get('cluster', ''), 
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
        async with db.pool.acquire() as connection:
            await connection.executemany(query, values)

importer = ImporterService()