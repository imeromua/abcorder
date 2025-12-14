import os
import re
from datetime import datetime

import pandas as pd


class ExporterService:
    def clean_filename(self, name):
        """Очищує назву від спецсимволів для використання в імені файлу"""
        clean = re.sub(r'[^\w\s-]', '', str(name))
        clean = clean.strip().replace(' ', '_')
        return clean

    async def generate_order_files(self, items, grouping_mode, user_id):
        """
        Генерує файли замовлень з кошика.
        grouping_mode: 'department' (по відділах) або 'supplier' (по постачальниках)
        """
        df = pd.DataFrame(items)
        
        # Базовий словник колонок
        export_cols = {
            'department': 'Відділ',
            'article': 'Артикул',
            'name': 'Найменування',
            'quantity': 'Кількість',
            'supplier': 'Постачальник'
        }

        # Якщо режим "по відділах" (для магазину), постачальник не потрібен у файлі
        if grouping_mode == 'department':
            if 'supplier' in export_cols:
                del export_cols['supplier']
        
        # Фільтруємо і перейменовуємо колонки
        available_cols = [c for c in export_cols.keys() if c in df.columns]
        df_export = df[available_cols].rename(columns=export_cols)

        timestamp = datetime.now().strftime("%d-%m_%H-%M")
        output_files = []
        
        temp_dir = "data/temp"
        os.makedirs(temp_dir, exist_ok=True)

        # Логіка групування
        if grouping_mode == 'department':
            # Якщо раптом відділу немає, ставимо заглушку
            if 'Відділ' not in df_export.columns:
                df_export['Відділ'] = 'General'
            grouped = df_export.groupby('Відділ')
            prefix = "ЗПТ_" # Заявка на переміщення товару
        
        elif grouping_mode == 'supplier':
            if 'Постачальник' in df_export.columns:
                df_export['Постачальник'] = df_export['Постачальник'].fillna('Other')
            grouped = df_export.groupby('Постачальник')
            prefix = "Order_"
            
        else:
            # Дефолт
            grouped = df_export.groupby('Відділ')
            prefix = "Export_"

        # Створення файлів
        for group_name, group_data in grouped:
            safe_name = self.clean_filename(group_name)
            filename = f"{prefix}{safe_name}_{timestamp}.xlsx"
            filepath = os.path.join(temp_dir, filename)
            
            group_data.to_excel(filepath, index=False)
            output_files.append(filepath)

        return output_files


    async def export_full_base(self, items, department_filter=None):
        """
        Експортує базу товарів (або її частину) у форматі, ідентичному до імпорту.
        """
        df = pd.DataFrame(items)
        
        # 1. Розбиваємо category_path назад на колонки (Департамент, Група...)
        if 'category_path' in df.columns:
            split_path = df['category_path'].str.split('/', expand=True)
            cols = ['Департамент', 'Піддеп-т', 'Група', 'Підгрупа']
            for i, col_name in enumerate(cols):
                if i < split_path.shape[1]:
                    df[col_name] = split_path[i]
                else:
                    df[col_name] = ""
        
        # 2. Перейменовуємо технічні колонки на людські
        rename_map = {
            "department": "Відділ",
            "article": "Артикул",
            "name": "Найменування",
            "supplier": "Постачальник",
            "resident": "Резидент",
            "cluster": "DP",
            "sales_qty": "Розхід, кіл.",
            "sales_sum": "Розхід ц.р., грн.",
            "stock_qty": "Залишок, кіл.",
            "stock_sum": "Залишок, грн."
        }
        df = df.rename(columns=rename_map)

        # 3. Фільтрація по відділу (якщо треба)
        if department_filter:
            # department у нас вже став "Відділ"
            df = df[df['Відділ'].astype(str) == str(department_filter)]

        # 4. Визначаємо правильний порядок колонок
        final_order = [
            "Відділ", "Департамент", "Піддеп-т", "Група", "Підгрупа",
            "Артикул", "Найменування", "Постачальник", "Резидент", "DP",
            "Розхід, кіл.", "Розхід ц.р., грн.", "Залишок, кіл.", "Залишок, грн."
        ]
        
        # Залишаємо тільки ті, що реально є в даних
        final_cols = [c for c in final_order if c in df.columns]
        df_final = df[final_cols]

        # 5. Зберігаємо файл
        timestamp = datetime.now().strftime("%d-%m_%H-%M")
        
        if department_filter:
            safe_dept = self.clean_filename(department_filter)
            filename = f"Export_Dept_{safe_dept}_{timestamp}.xlsx"
        else:
            filename = f"Export_FULL_Base_{timestamp}.xlsx"
            
        temp_dir = "data/temp"
        os.makedirs(temp_dir, exist_ok=True)
        filepath = os.path.join(temp_dir, filename)
        
        df_final.to_excel(filepath, index=False)
        return filepath

exporter = ExporterService()