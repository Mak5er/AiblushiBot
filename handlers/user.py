from aiogram import Router, types, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext

import keyboards as kb
from config import ADMIN_ID, CHAT_ID
from services.db import add_user, get_user_by_id, is_user_approved
from utils.helpers import check_private_chat

# Ініціалізуємо роутер для користувача
user_router = Router()


@user_router.message(CommandStart())
async def start_cmd(message: types.Message, state: FSMContext):
    """Обробник команди /start"""
    # Не реагуємо на команди не в приватних чатах
    if not check_private_chat(message):
        return

    await message.bot.send_chat_action(message.chat.id, "typing")

    user_id = message.from_user.id
    username = message.from_user.username

    # Перевіряємо, чи вже є користувач в базі
    user = await get_user_by_id(user_id)

    if not user:
        # Створюємо нового користувача
        await add_user(user_id, username)

        # Повідомляємо адміністраторів про нового користувача
        await message.bot.send_chat_action(ADMIN_ID, "typing")
        approve_kb = types.InlineKeyboardMarkup(inline_keyboard=[
            [
                types.InlineKeyboardButton(text="✅ Підтвердити", callback_data=f"approve_{user_id}"),
                types.InlineKeyboardButton(text="❌ Відхилити", callback_data=f"reject_{user_id}")
            ]
        ])

        await message.bot.send_message(
            admin_id,
            f"👤 <b>Новий користувач запитує доступ:</b>\n\n"
            f"ID: <code>{user_id}</code>\n"
            f"Username: @{username if username else 'Не вказано'}\n"
            f"Ім'я: {message.from_user.full_name}",
            parse_mode="HTML",
            reply_markup=approve_kb
        )

        # Повідомляємо користувача про очікування підтвердження
        await message.answer(
            f"👋 <b>Вітаємо вас, {message.from_user.first_name}!</b>\n\n"
            f"Ваш запит на доступ відправлено адміністраторам. Будь ласка, зачекайте на підтвердження.",
            parse_mode="HTML"
        )
    else:
        # Перевіряємо, чи користувач має доступ
        if await is_user_approved(user_id):
            await message.answer(
                f"👋 <b>Вітаємо знову, {message.from_user.first_name}!</b>\n\n"
                f"Виберіть опцію з меню нижче:",
                reply_markup=kb.main_menu_kb,
                parse_mode="HTML"
            )
        else:
            await message.answer(
                f"👋 <b>Вітаємо, {message.from_user.first_name}!</b>\n\n"
                f"Ваш запит на доступ ще розглядається. Будь ласка, зачекайте на підтвердження.",
                parse_mode="HTML"
            )

    # Очищаємо стан FSM
    await state.clear()


@user_router.message()
async def handle_menu(message: types.Message, state: FSMContext):
    await message.bot.send_chat_action(message.chat.id, "typing")
    # Не реагуємо на повідомлення з груп
    if message.chat.type != "private":
        return

    if message.text in ["🏠 Меню", "🏠 На головну", "🔙 Повернутися назад"]:
        await message.answer("👋 <b>Головне меню</b>", reply_markup=kb.main_menu_kb, parse_mode="HTML")
        await state.clear()
        return
