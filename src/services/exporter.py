import os
import re
from datetime import datetime

import pandas as pd


class ExporterService:
    def clean_filename(self, name):
        """Очищує назву від спецсимволів"""
        clean = re.sub(r'[^\w\s-]', '', name)
        clean = clean.strip().replace(' ', '_')
        return clean

    async def generate_order_files(self, items, role, user_id):
        """
        Генерація файлів Excel
        items = [{article, name, quantity, department, supplier, ...}]
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

        # --- ЛОГІКА ДЛЯ МАГАЗИНУ (SHOP) ---
        if role == 'shop':
            # Прибираємо Постачальника зі списку колонок
            if 'supplier' in export_cols:
                del export_cols['supplier']
        
        # Фільтруємо і перейменовуємо
        available_cols = [c for c in export_cols.keys() if c in df.columns]
        df_export = df[available_cols].rename(columns=export_cols)

        timestamp = datetime.now().strftime("%d-%m_%H-%M")
        output_files = []
        
        temp_dir = "data/temp"
        os.makedirs(temp_dir, exist_ok=True)

        # --- РОЗПОДІЛ І НАЗВИ ФАЙЛІВ ---
        
        if role == 'shop':
            # Ділимо по ВІДДІЛАХ
            grouped = df_export.groupby('Відділ')
            # Формат: "10_10-12_10-40.xlsx" (Без префікса Move)
            prefix = "" 
        
        elif role == 'patron':
            # Для Патрона залишаємо як є (або теж змінимо, якщо треба)
            if 'Постачальник' in df_export.columns:
                df_export['Постачальник'] = df_export['Постачальник'].fillna('Other')
                grouped = df_export.groupby('Постачальник')
            else:
                grouped = df_export.groupby('Відділ')
            
            prefix = "Order_" 

        for group_name, group_data in grouped:
            safe_name = self.clean_filename(str(group_name))
            
            # Якщо префікс порожній, не додаємо підкреслення на початку
            if prefix:
                filename = f"{prefix}{safe_name}_{timestamp}.xlsx"
            else:
                filename = f"{safe_name}_{timestamp}.xlsx"
                
            filepath = os.path.join(temp_dir, filename)
            group_data.to_excel(filepath, index=False)
            output_files.append(filepath)

        return output_files

exporter = ExporterService()