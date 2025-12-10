from aiogram.fsm.state import State, StatesGroup

class OrderStates(StatesGroup):
    waiting_for_quantity = State()

class AdminStates(StatesGroup):
    waiting_for_broadcast_text = State()
    confirm_broadcast = State()