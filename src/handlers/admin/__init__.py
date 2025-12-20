from aiogram import Router

# Імпортуємо "дочірні" роутери з наших модулів
from .menu import router as menu_router
from .users import router as users_router
from .import_process import router as import_router
from .export_process import router as export_router

# Створюємо головний роутер для всієї адмінки
admin_router = Router()

# Підключаємо їх до головного
# Важливо: порядок іноді має значення, але тут у нас чіткі фільтри
admin_router.include_routers(
    menu_router,
    users_router,
    import_router,
    export_router
)

# Тепер у main.py достатньо написати:
# from src.handlers.admin import admin_router