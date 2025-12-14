from aiogram.fsm.state import State, StatesGroup

class OrderStates(StatesGroup):
    """Стани для процесу замовлення"""
    waiting_for_quantity = State()  # Коли юзер вводить кількість товару

class AdminStates(StatesGroup):
    """Стани для адмін-панелі"""
    # --- Розсилка ---
    waiting_for_broadcast_text = State()  # Чекаємо текст повідомлення
    confirm_broadcast = State()           # Чекаємо підтвердження (Так/Ні)

    # --- Імпорт ---
    waiting_for_import_file = State()     # Чекаємо файл (.xlsx/.zip)
    waiting_for_import_link = State()     # Чекаємо посилання (Google Drive)