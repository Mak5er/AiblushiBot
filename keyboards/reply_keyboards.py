from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

main_menu_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🍇 Дегідратори"), KeyboardButton(text="🤖 Робота")],
        [KeyboardButton(text="📊 Звітність")],
    ],
    resize_keyboard=True
)

menu_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🏠 На головну")]
    ],
    resize_keyboard=True
)
# Клавіатура з кнопкою "Назад" для повернення до вибору дегідратора
back_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🔙 Повернутися назад")]
    ],
    resize_keyboard=True
)

# Клавіатура для вибору типу роботи
work_type_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🏭 Виробництво"), KeyboardButton(text="📦 Пакування")],
        [KeyboardButton(text="💰 Продаж"), KeyboardButton(text="📝 Інша діяльність")],
        [KeyboardButton(text="🔙 Повернутися назад")]
    ],
    resize_keyboard=True
)
