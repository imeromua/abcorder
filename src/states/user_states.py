from aiogram.fsm.state import State, StatesGroup

class OrderStates(StatesGroup):
    waiting_for_quantity = State()  # Чекаємо введення числа