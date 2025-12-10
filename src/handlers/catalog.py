from aiogram import F, Router, types

from src.database.db import db
from src.keyboards.inline import get_product_keyboard

catalog_router = Router()

@catalog_router.message(F.text)
async def search_handler(message: types.Message):
    """
    Обробляє будь-який текст як пошуковий запит
    """
    query = message.text.strip()
    
    # Ігноруємо команди типу /start
    if query.startswith('/'):
        return

    # 1. Шукаємо в базі (по Артикулу АБО по Назві)
    # ILIKE означає "нечутливий до регістру" (Лопата = лопата)
    sql = """
        SELECT * FROM products 
        WHERE article = $1 OR name ILIKE $2
        LIMIT 10
    """
    # Додаємо % для пошуку по частині слова
    search_pattern = f"%{query}%"
    
    products = await db.fetch_all(sql, query, search_pattern)

    # 2. Результат
    if not products:
        await message.answer("🤷‍♂️ Нічого не знайдено. Спробуйте інший запит.")
        return

    # Якщо знайшли багато товарів (список)
    if len(products) > 1:
        text = f"🔍 <b>Знайдено {len(products)} товарів:</b>\n\n"
        for p in products:
            # Розрахунок ціни (Залишок грн / Залишок шт)
            price = 0
            if p['stock_qty'] > 0:
                price = p['stock_sum'] / p['stock_qty']
            elif p['sales_qty'] > 0: # Якщо залишку 0, пробуємо взяти ціну з продажів
                price = p['sales_sum'] / p['sales_qty']
            
            icon = "📦"
            if p['stock_qty'] <= 0: icon = "⚪️" # Немає в наявності
            
            text += f"{icon} <b>{p['name']}</b>\n"
            text += f"🆔 <code>{p['article']}</code> | 💰 {price:.2f} грн\n"
            text += f"----------------\n"
            
        await message.answer(text, parse_mode="HTML")

    # Якщо знайшли ОДИН конкретний товар -> Показуємо детальну картку
    elif len(products) == 1:
        p = products[0]
        await show_product_card(message, p)

async def show_product_card(message: types.Message, p: dict):
    """Генерація красивої картки товару"""
    
    # --- Калькулятор ціни ---
    price = 0.0
    if p['stock_qty'] > 0:
        price = p['stock_sum'] / p['stock_qty']
    elif p['sales_qty'] > 0:
        price = p['sales_sum'] / p['sales_qty']

    # --- Емодзі для Класу ---
    cluster_emoji = "⚪️"
    if p['cluster'] == 'A': cluster_emoji = "💎 A"
    elif p['cluster'] == 'B': cluster_emoji = "⚖️ B"
    elif p['cluster'] == 'C': cluster_emoji = "🐢 C"

    # --- Текст картки ---
    text = (
        f"📦 <b>{p['name']}</b>\n\n"
        f"💰 <b>Ціна:</b> {price:.2f} грн\n"
        f"📊 <b>Клас:</b> {cluster_emoji}\n"
        f"🆔 <b>Артикул:</b> <code>{p['article']}</code>\n"
        f"🏭 <b>Постачальник:</b> {p['supplier']}\n\n"
        f"📂 <b>Шлях:</b> {p['category_path']}\n\n"
        f"📈 <b>Статистика:</b>\n"
        f"• Продажі: {p['sales_qty']} шт ({p['sales_sum']:.0f} грн)\n"
        f"• Залишок: {p['stock_qty']} шт ({p['stock_sum']:.0f} грн)"
    )

    # Тут скоро додамо кнопку "Замовити"
    await message.answer(
    text, 
    parse_mode="HTML",
    reply_markup=get_product_keyboard(p['article']) # <--- Додали кнопку
)