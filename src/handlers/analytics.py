import asyncio  # <--- ДОДАНО ІМПОРТ
import os

from aiogram import F, Router, types
from aiogram.types import FSInputFile

from src.database.db import db
from src.keyboards import get_analytics_order_type_keyboard
from src.services.exporter import exporter

analytics_router = Router()

# Вхід в меню
@analytics_router.message(F.text == "📊 Аналітика / Автозамовлення")
async def show_analytics_menu(message: types.Message):
    user = await db.fetch_one("SELECT role FROM users WHERE user_id = $1", message.from_user.id)
    if user['role'] == 'shop':
        await message.answer("🔒 Цей розділ доступний тільки для керівників.")
        return

    text = (
        "📊 <b>Аналітичний Центр</b>\n\n"
        "Що бажаєте зробити?"
    )
    
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔮 Сформувати Автозамовлення", callback_data="analytics_auto_menu")],
        [InlineKeyboardButton(text="📉 Звіт: Закінчуються товари", callback_data="analytics_low_stock")],
        [InlineKeyboardButton(text="🏆 ТОП-50 товарів (Файл)", callback_data="analytics_top_sales")]
    ])
    
    await message.answer(text, parse_mode="HTML", reply_markup=kb)


# --- 1. АВТОЗАМОВЛЕННЯ: КРОК 1 (ВИБІР ТИПУ) ---
@analytics_router.callback_query(F.data == "analytics_auto_menu")
async def ask_auto_order_type(callback: types.CallbackQuery):
    await callback.message.answer(
        "🔮 <b>Як згрупувати автозамовлення?</b>", 
        parse_mode="HTML", 
        reply_markup=get_analytics_order_type_keyboard()
    )
    await callback.answer()

# --- АВТОЗАМОВЛЕННЯ: КРОК 2 (ГЕНЕРАЦІЯ) ---
@analytics_router.callback_query(F.data.in_({"auto_order_dept", "auto_order_supp"}))
async def generate_auto_order_action(callback: types.CallbackQuery):
    # Визначаємо режим
    mode = 'department' if callback.data == 'auto_order_dept' else 'supplier'
    
    await callback.message.edit_text("⏳ <b>Аналізую продажі та залишки...</b>", parse_mode="HTML")
    
    # Формула: Залишок < Продажів АБО Залишок < 3 (критичний)
    sql = """
        SELECT 
            article, name, supplier, department,
            stock_qty as "Залишок", 
            sales_qty as "Продажі",
            (sales_qty - stock_qty) as "Рекомендовано"
        FROM products 
        WHERE 
            (stock_qty < sales_qty OR stock_qty < 3) 
            AND sales_qty > 0
        ORDER BY supplier, name
    """
    
    rows = await db.fetch_all(sql)
    
    if not rows:
        await callback.message.edit_text("🤷‍♂️ Все добре! Критичних позицій не знайдено.")
        return

    items = []
    for r in rows:
        rec_qty = r['Рекомендовано']
        if rec_qty <= 0: rec_qty = 2 
        
        items.append({
            'article': r['article'],
            'name': r['name'],
            'quantity': int(rec_qty),
            'department': r['department'],
            'supplier': r['supplier']
        })

    try:
        # Генеруємо файли відповідно до вибраного режиму
        files = await exporter.generate_order_files(items, grouping_mode=mode, user_id=callback.from_user.id)
        
        mode_text = "по відділах (ЗПТ)" if mode == 'department' else "по постачальниках"
        await callback.message.edit_text(f"✅ <b>Автозамовлення готове!</b>\nПозицій: {len(items)}\nРозбивка: {mode_text}.", parse_mode="HTML")
        
        for f in files:
            await callback.message.answer_document(FSInputFile(f))
            # 🔥 ПАУЗА, ЩОБ НЕ ЗЛОВИТИ FLOOD WAIT
            await asyncio.sleep(0.5)
            
            try: os.remove(f)
            except: pass
            
    except Exception as e:
        await callback.message.edit_text(f"❌ Помилка: {e}")


# --- 2. ЗВІТ: МАЛИЙ ЗАЛИШОК ---
@analytics_router.callback_query(F.data == "analytics_low_stock")
async def generate_low_stock_report(callback: types.CallbackQuery):
    await callback.message.answer("⏳ <b>Шукаю товари, яких менше 3 шт...</b>", parse_mode="HTML")
    
    sql = """
        SELECT article, name, supplier, department, stock_qty 
        FROM products 
        WHERE stock_qty < 3 
        ORDER BY department, name
    """
    rows = await db.fetch_all(sql)
    
    if not rows:
        await callback.message.answer("🤷‍♂️ Товарів з малим залишком не знайдено.")
        return

    items = []
    for r in rows:
        items.append({
            'article': r['article'],
            'name': r['name'],
            'quantity': int(r['stock_qty']),
            'department': r['department'],
            'supplier': r['supplier']
        })

    try:
        files = await exporter.generate_order_files(items, grouping_mode='department', user_id=callback.from_user.id)
        
        await callback.message.answer(f"📉 <b>Звіт по залишках сформовано!</b>\n(У колонці 'Кількість' вказано поточний залишок).", parse_mode="HTML")
        
        for f in files:
            await callback.message.answer_document(FSInputFile(f))
            # 🔥 ПАУЗА ТУТ ТАКОЖ
            await asyncio.sleep(0.5)
            
            try: os.remove(f)
            except: pass

    except Exception as e:
        await callback.message.answer(f"❌ Помилка: {e}")


# --- 3. ТОП-50 ПРОДАЖІВ ---
@analytics_router.callback_query(F.data == "analytics_top_sales")
async def generate_top_sales(callback: types.CallbackQuery):
    await callback.message.answer("⏳ <b>Визначаю ТОП-50 лідерів продажів...</b>", parse_mode="HTML")
    
    # Сортуємо глобально по всіх відділах
    sql = """
        SELECT article, name, supplier, sales_qty, sales_sum
        FROM products 
        ORDER BY sales_sum DESC
        LIMIT 50
    """
    rows = await db.fetch_all(sql)
    
    items = []
    for r in rows:
        items.append({
            'article': r['article'],
            'name': f"{r['name']} ({r['sales_sum']:.0f} грн)",
            'quantity': int(r['sales_qty']),
            'department': 'TOP-50_GLOBAL', # Складаємо все в один файл
            'supplier': r['supplier']
        })

    try:
        # grouping_mode='department' -> Створить один файл з префіксом ЗПТ_
        files = await exporter.generate_order_files(items, grouping_mode='department', user_id=callback.from_user.id)
        
        await callback.message.answer(f"🏆 <b>ТОП-50 товарів готовий!</b>", parse_mode="HTML")
        
        for f in files:
            await callback.message.answer_document(FSInputFile(f))
            # 🔥 І ТУТ ПАУЗА (про всяк випадок)
            await asyncio.sleep(0.5)
            
            try: os.remove(f)
            except: pass

    except Exception as e:
        await callback.message.answer(f"❌ Помилка: {e}")