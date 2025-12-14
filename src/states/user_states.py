from aiogram.fsm.state import State, StatesGroup


class OrderStates(StatesGroup):
    """Стани для процесу замовлення"""
    waiting_for_quantity = State()

class AdminStates(StatesGroup):
    """Стани для адмін-панелі"""
    # --- Розсилка ---
    waiting_for_broadcast_text = State()
    confirm_broadcast = State()

    # --- Імпорт ---
    waiting_for_import_file = State()
    waiting_for_import_link = State()
    
    # --- Експорт (НОВЕ) ---
    waiting_for_export_filter = State() # Чекаємо вибору: Фільтрувати чи ні?