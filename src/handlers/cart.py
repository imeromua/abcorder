from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from src.database.db import db
from src.states.user_states import OrderStates
from src.keyboards.inline import get_cart_keyboard

cart_router = Router()

# 1. Натиснули "Додати в замовлення"
@cart_router.callback_query(F.data.startswith("add_"))
async def start_add_to_cart(callback: types.CallbackQuery, state: FSMContext):
    # Витягуємо артикул з кнопки (add_12345 -> 12345)
    article = callback.data.split("_")[1]
    
    # Отримуємо інфо про товар (щоб показати ліміти)
    product = await db.fetch_one("SELECT * FROM products WHERE article = $1", article)
    user = await db.fetch_one("SELECT role FROM users WHERE user_id = $1", callback.from_user.id)
    
    role = user['role']
    limit_text = ""
    
    # --- ЛОГІКА ОБМЕЖЕНЬ (SHOP vs PATRON) ---
    max_qty = 999999
    if role == 'shop':
        # Правило: Залишок - 3
        available = int(product['stock_qty']) - 3
        if available < 0: available = 0
        max_qty = available
        limit_text = f"\n⚠️ <b>Доступно для переміщення:</b> {available} шт. (НЗ: 3)"
        
        if available == 0:
            await callback.answer("⛔️ Товар недоступний (Залишок < 3)", show_alert=True)
            return

    # Запам'ятовуємо в пам'яті бота, що саме ми замовляємо
    await state.update_data(article=article, max_qty=max_qty, role=role)
    await state.set_state(OrderStates.waiting_for_quantity)

    await callback.message.answer(
        f"🔢 Введіть кількість для <b>{product['name']}</b>:{limit_text}",
        reply_markup=get_cart_keyboard(article),
        parse_mode="HTML"
    )
    await callback.answer()

# 2. Ввели число
@cart_router.message(OrderStates.waiting_for_quantity)
async def process_quantity(message: types.Message, state: FSMContext):
    # Перевірка, чи це число
    if not message.text.isdigit():
        await message.answer("❌ Будь ласка, введіть ціле число.")
        return

    qty = int(message.text)
    data = await state.get_data()
    article = data['article']
    max_qty = data['max_qty']
    role = data['role']

    # Перевірка лімітів
    if role == 'shop' and qty > max_qty:
        await message.answer(f"⛔️ Помилка! Максимум для замовлення: {max_qty} шт.")
        return

    if qty <= 0:
        await message.answer("❌ Кількість має бути більше 0.")
        return
    
    # "Жирний палець" (попередження)
    if qty > 1000:
         await message.answer(f"🧐 Ви ввели <b>{qty}</b> шт. Це не помилка? Якщо так — введіть ще раз, якщо ні — зменшіть кількість.", parse_mode="HTML")
         # Тут можна додати кнопку підтвердження, але поки просто попередимо
         return

    # --- ЗАПИС В БД ---
    # Upsert: Якщо товар вже є в кошику -> додаємо кількість
    await db.execute("""
        INSERT INTO cart (user_id, article, quantity)
        VALUES ($1, $2, $3)
        ON CONFLICT (user_id, article) 
        DO UPDATE SET quantity = cart.quantity + $3
    """, message.from_user.id, article, qty)

    # Очищаємо стан
    await state.clear()
    
    await message.answer(
        f"✅ <b>Додано в кошик:</b> {qty} шт.\n"
        f"<i>Натисніть /cart, щоб переглянути замовлення.</i>", # Поки команди немає, але скоро буде
        parse_mode="HTML"
    )

# 3. Скасування
@cart_router.callback_query(F.data == "cancel_order")
async def cancel_handler(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.delete()
    await callback.answer("Скасовано")