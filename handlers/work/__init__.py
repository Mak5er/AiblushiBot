from aiogram import Router
from aiogram.fsm.state import StatesGroup, State


# Визначаємо загальні стани для роботи
class WorkStates(StatesGroup):
    """Стани для роботи"""
    select_work_type = State()  # Вибір типу роботи
    work_in_progress = State()  # Робота в процесі (загальний стан)


# Імпортуємо роутери та необхідні функції з модулів
from . import production, other_work, packaging, sales, common

# Створюємо основний роутер
work_router = Router(name=__name__)

# Створюємо роутер для спільних обробників
common_router = Router(name=f"{__name__}.common")
common.register_common_handlers(common_router)

# Включаємо всі роутери в основний. ВАЖЛИВО: у aiogram остання реєстрація
# має найвищий пріоритет (порядок включення впливає на пріоритет обробки)
work_router.include_routers(
    # Специфічні роутери за типами робіт (мають вищий пріоритет)
    sales.sales_router,
    packaging.packaging_router,
    production.production_router,
    other_work.other_work_router,
    # Загальний роутер має найнижчий пріоритет, щоб не перехоплювати спеціалізовані обробники
    common_router,
)

# Визначаємо, що експортуватиметься з цього модуля
__all__ = ["work_router"]
