import pandas as pd
import logging
from src.database.db import db

# Маппинг колонок (Згідно з твоїм скріншотом)
COLUMN_MAPPING = {
    "Відділ": "department",          # Це числовий ID (Корінь меню)
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
    async def import_file(self, file_path: str):
        try:
            # Читаємо файл
            if file_path.endswith('.csv'):
                df = pd.read_csv(file_path)
            else:
                df = pd.read_excel(file_path)

            # Чистимо
            df = df.dropna(subset=['Артикул'])
            df = df.fillna('')

            # --- ФОРМУВАННЯ ШЛЯХУ (НОВА ЛОГІКА) ---
            # Структура: Департамент -> Піддеп-т -> Група -> Підгрупа
            # (Відділ йде окремо в колонку department)
            
            def build_path(row):
                # Список колонок строго в порядку ієрархії
                hierarchy_cols = ['Департамент', 'Піддеп-т', 'Група', 'Підгрупа']
                parts = []
                for col in hierarchy_cols:
                    # Якщо колонка є і вона не порожня
                    val = str(row.get(col, '')).strip()
                    if val and val != '0' and val.lower() != 'nan':
                        parts.append(val)
                return "/".join(parts)

            df['category_path'] = df.apply(build_path, axis=1)

            # Перейменовуємо
            df = df.rename(columns=COLUMN_MAPPING)

            # Фільтруємо колонки (залишаємо тільки ті, що є в маппінгу + category_path)
            valid_cols = list(COLUMN_MAPPING.values()) + ['category_path']
            available_cols = [c for c in valid_cols if c in df.columns]
            df = df[available_cols]

            # Конвертація типів
            df['article'] = df['article'].astype(str)
            
            # Числа
            numeric_cols = ['sales_qty', 'sales_sum', 'stock_qty', 'stock_sum', 'department']
            for col in numeric_cols:
                if col in df.columns:
                    # Замінюємо коми на крапки, прибираємо пробіли
                    df[col] = pd.to_numeric(
                        df[col].astype(str).str.replace(',', '.').replace('\xa0', '').replace(' ', ''), 
                        errors='coerce'
                    ).fillna(0)

            records = df.to_dict('records')
            total = len(records)
            logging.info(f"📊 Зчитано {total} рядків. Імпорт...")

            # Batch Insert
            batch_size = 1000
            for i in range(0, total, batch_size):
                batch = records[i:i + batch_size]
                await self._insert_batch(batch)

            return total

        except Exception as e:
            logging.error(f"Import Error: {e}")
            raise e

    async def _insert_batch(self, batch):
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