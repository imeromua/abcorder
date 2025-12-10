import pandas as pd
import os
import re
from datetime import datetime

class ExporterService:
    def clean_filename(self, name):
        """Очищує назву від спецсимволів"""
        clean = re.sub(r'[^\w\s-]', '', str(name))
        clean = clean.strip().replace(' ', '_')
        return clean

    async def generate_order_files(self, items, grouping_mode, user_id):
        """
        grouping_mode: 'department' (по відділах) або 'supplier' (по постачальниках)
        """
        df = pd.DataFrame(items)
        
        # Базові колонки
        export_cols = {
            'department': 'Відділ',
            'article': 'Артикул',
            'name': 'Найменування',
            'quantity': 'Кількість',
            'supplier': 'Постачальник'
        }

        # --- ЛОГІКА ДЛЯ МАГАЗИНУ / ВІДДІЛІВ ---
        if grouping_mode == 'department':
            # Прибираємо Постачальника зі списку колонок для файлу
            if 'supplier' in export_cols:
                del export_cols['supplier']
        
        # Фільтруємо і перейменовуємо
        available_cols = [c for c in export_cols.keys() if c in df.columns]
        df_export = df[available_cols].rename(columns=export_cols)

        timestamp = datetime.now().strftime("%d-%m_%H-%M")
        output_files = []
        
        temp_dir = "data/temp"
        os.makedirs(temp_dir, exist_ok=True)

        # --- РОЗПОДІЛ І ПРЕФІКСИ ---
        
        if grouping_mode == 'department':
            # Группуємо по ВІДДІЛАХ
            if 'Відділ' not in df_export.columns:
                df_export['Відділ'] = 'General'
            grouped = df_export.groupby('Відділ')
            
            prefix = "ЗПТ_" # <--- БУЛО "Move_", СТАЛО "ЗПТ_"
        
        elif grouping_mode == 'supplier':
            # Группуємо по ПОСТАЧАЛЬНИКАХ
            if 'Постачальник' in df_export.columns:
                df_export['Постачальник'] = df_export['Постачальник'].fillna('Other')
                grouped = df_export.groupby('Постачальник')
            else:
                grouped = df_export.groupby('Відділ')
            
            prefix = "Order_" # Закупівля

        # Генерація файлів
        for group_name, group_data in grouped:
            safe_name = self.clean_filename(group_name)
            filename = f"{prefix}{safe_name}_{timestamp}.xlsx"
            filepath = os.path.join(temp_dir, filename)
            
            # index=False прибирає нумерацію рядків (0,1,2) зліва
            group_data.to_excel(filepath, index=False)
            output_files.append(filepath)

        return output_files

exporter = ExporterService()