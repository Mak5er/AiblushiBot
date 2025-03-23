from aiogram.types import InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def approve_reject_kb(user_id: int):
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Схвалити користувача", callback_data=f"approve_{user_id}"),
        InlineKeyboardButton(text="❌ Відхилити запит", callback_data=f"reject_{user_id}")
    )
    return builder.as_markup()


# Клавіатура для підтвердження вибору партнерів
confirm_partners_kb = InlineKeyboardBuilder()
confirm_partners_kb.add(InlineKeyboardButton(text="✅ Підтвердити вибраних партнерів", callback_data="confirm_partners"))
confirm_partners_kb.add(InlineKeyboardButton(text="❌ Скасувати вибір", callback_data="cancel_selection"))
confirm_partners_kb = confirm_partners_kb.as_markup()

# Клавіатури для завершення різних типів робіт
# Виробництво
end_shift_production_kb = InlineKeyboardBuilder()
end_shift_production_kb.add(
    InlineKeyboardButton(text="🔴 Завершити зміну з виробництва", callback_data="end_shift_production"))
end_shift_production_kb = end_shift_production_kb.as_markup()

# Пакування
end_shift_packaging_kb = InlineKeyboardBuilder()
end_shift_packaging_kb.add(
    InlineKeyboardButton(text="🔴 Завершити зміну з пакування", callback_data="end_shift_packaging"))
end_shift_packaging_kb = end_shift_packaging_kb.as_markup()

# Продаж
end_shift_sales_kb = InlineKeyboardBuilder()
end_shift_sales_kb.add(InlineKeyboardButton(text="🔴 Завершити зміну з продажу", callback_data="end_shift_sales"))
end_shift_sales_kb = end_shift_sales_kb.as_markup()

# Deprecated - буде видалено в майбутніх версіях
# Використовується для сумісності з існуючим кодом
end_shift_kb = InlineKeyboardBuilder()
end_shift_kb.add(InlineKeyboardButton(text="🔴 Завершити поточну зміну", callback_data="end_shift"))
end_shift_kb = end_shift_kb.as_markup()


async def get_users_keyboard(users, current_user_id, include_nobody=False):
    """Створити клавіатуру з користувачами для вибору партнера"""
    keyboard = []
    row = []

    # Додаємо користувачів у клавіатуру
    for i, user in enumerate(users):
        # Пропускаємо поточного користувача
        if user.id == current_user_id:
            continue

        # Формуємо текст кнопки
        button_text = f"{user.username if user.username else f'user'} ({user.id})"

        # Додаємо кнопку в рядок
        row.append(KeyboardButton(text=button_text))

        # Якщо в рядку вже 2 кнопки або це останній користувач, додаємо рядок в клавіатуру
        if len(row) == 2 or i == len(users) - 1:
            keyboard.append(row.copy())
            row = []

    # Додаємо кнопку "Ніхто", якщо потрібно
    if include_nobody:
        keyboard.append([KeyboardButton(text="🙅‍♂️ Ніхто")])

    # Додаємо кнопки навігації
    keyboard.append([KeyboardButton(text="🔙 Назад"), KeyboardButton(text="🏠 Меню")])

    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def get_multiselect_partners_kb(users: list, user_id: int, selected_partners: list = None,
                                nobody_selected: bool = False) -> InlineKeyboardMarkup:
    """
    Створює інлайн-клавіатуру для вибору кількох партнерів з можливістю позначити/зняти позначку
    
    Args:
        users: список користувачів
        user_id: ID поточного користувача
        selected_partners: список ID вибраних партнерів
        nobody_selected: чи вибрано "Нікого"
    
    Returns:
        InlineKeyboardMarkup: інлайн-клавіатура з користувачами
    """
    if selected_partners is None:
        selected_partners = []

    kb = InlineKeyboardBuilder()

    # Додаємо користувачів
    for user in users:
        if user.id != user_id:  # Не показуємо поточного користувача
            # Визначаємо, чи вибраний цей партнер
            is_selected = user.id in selected_partners

            # Додаємо відповідний символ (✅ або ⬜️)
            mark = "✅" if is_selected and not nobody_selected else "⬜️"

            # Формуємо текст кнопки з username або ID користувача
            display_name = f"@{user.username}" if user.username else f"Користувач {user.id}"

            kb.button(
                text=f"{mark} {display_name}",
                callback_data=f"select_partner_{user.id}"
            )

    # Додаємо кнопки в ряди по 2
    kb.adjust(2)

    # Додаємо кнопку "Нікого"
    nobody_mark = "✅" if nobody_selected else "⬜️"
    kb.row(
        InlineKeyboardButton(
            text=f"{nobody_mark} Працювати самостійно",
            callback_data="select_nobody"
        )
    )

    # Додаємо кнопку підтвердження
    kb.row(
        InlineKeyboardButton(
            text="✅ Підтвердити обраних партнерів",
            callback_data="confirm_partners"
        )
    )

    # Додаємо кнопку скасування
    kb.row(
        InlineKeyboardButton(
            text="🔙 Скасувати вибір",
            callback_data="cancel_partners"
        )
    )

    return kb.as_markup()
