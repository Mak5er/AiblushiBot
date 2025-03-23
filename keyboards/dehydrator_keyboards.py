from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

# Клавіатура для вибору дегідратора
dehydrators_with_menu_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🔹 Дегідратор №1"), KeyboardButton(text="🔹 Дегідратор №2")],
        [KeyboardButton(text="🔹 Дегідратор №3")],
        [KeyboardButton(text="🏠 На головну")]
    ],
    resize_keyboard=True
)

# Клавіатура для вводу часу
time_input_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="⏱ 1 година"), KeyboardButton(text="⏱ 2 години"), KeyboardButton(text="⏱ 3 години")],
        [KeyboardButton(text="⏱ 4 години"), KeyboardButton(text="⏱ 5 годин"), KeyboardButton(text="⏱ 6 годин")],
        [KeyboardButton(text="⏱ 7 годин"), KeyboardButton(text="⏱ 8 годин"), KeyboardButton(text="⏱ 9 годин")],
        [KeyboardButton(text="⏱ 10 годин"), KeyboardButton(text="⏱ 12 годин"), KeyboardButton(text="⏱ 15 годин")],
        [KeyboardButton(text="🔙 Повернутися назад"), KeyboardButton(text="🏠 На головну")]
    ],
    resize_keyboard=True
)
