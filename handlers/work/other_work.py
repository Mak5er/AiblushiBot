import datetime

from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

import keyboards as kb
from config import CHAT_ID
from handlers.work import WorkStates
from services.db import (
    get_all_approved_users,
    add_other_work
)
from utils.helpers import (
    init_partner_selection,
    handle_nobody_selection,
    handle_partner_selection,
    get_partners_text,
    check_private_chat
)

# Створюємо роутер для іншої роботи
other_work_router = Router()


class OtherWorkStates(StatesGroup):
    """Стани для роботи з іншою роботою"""
    partner_selection = State()  # Вибір партнерів
    work_description = State()  # Опис іншої роботи


@other_work_router.message(WorkStates.select_work_type, F.text == "📝 Інша діяльність")
async def start_other_work_process(message: types.Message, state: FSMContext):
    """Обробник початку процесу іншої роботи"""
    await message.bot.send_chat_action(message.chat.id, "typing")

    # Ініціалізуємо стан для вибору партнерів
    await init_partner_selection(state, "other_work")

    # Отримання всіх користувачів для вибору партнера
    users = await get_all_approved_users()

    # Створюємо інлайн-клавіатуру з користувачами
    await message.answer(
        "👥 <b>Виберіть партнерів для іншої роботи:</b>",
        reply_markup=kb.get_multiselect_partners_kb(users, message.from_user.id),
        parse_mode="HTML"
    )
    await state.set_state(OtherWorkStates.partner_selection)


@other_work_router.callback_query(OtherWorkStates.partner_selection, F.data == "select_nobody")
async def toggle_nobody_selection(callback: types.CallbackQuery, state: FSMContext):
    """Обробник вибору 'Нікого'"""
    await handle_nobody_selection(callback, state)


@other_work_router.callback_query(OtherWorkStates.partner_selection, F.data.startswith("select_partner_"))
async def toggle_partner_selection(callback: types.CallbackQuery, state: FSMContext):
    """Обробник вибору партнера"""
    await handle_partner_selection(callback, state)


@other_work_router.callback_query(OtherWorkStates.partner_selection, F.data == "confirm_partners")
async def confirm_other_work_partners(callback: types.CallbackQuery, state: FSMContext):
    """Обробник підтвердження вибору партнерів"""
    # Отримуємо дані партнерів
    data = await state.get_data()
    selected_partners = data.get("selected_partners", [])
    nobody_selected = data.get("nobody_selected", False)

    # Видаляємо повідомлення з інлайн-клавіатурою вибору партнерів
    await callback.message.delete()

    # Зберігаємо вибраних партнерів
    await state.update_data(all_partners=selected_partners, nobody_selected=nobody_selected)

    # Питаємо опис іншої роботи
    await callback.bot.send_chat_action(callback.message.chat.id, "typing")
    await callback.message.answer(
        "📝 <b>Опишіть, яку роботу ви виконали:</b>",
        reply_markup=kb.menu_kb,
        parse_mode="HTML"
    )

    # Оновлюємо стан
    await state.set_state(OtherWorkStates.work_description)

    await callback.answer()


@other_work_router.callback_query(OtherWorkStates.partner_selection, F.data == "cancel_partners")
async def cancel_other_work_partners_selection(callback: types.CallbackQuery, state: FSMContext):
    """Обробник скасування вибору партнерів"""
    await callback.message.delete()
    await callback.bot.send_chat_action(callback.message.chat.id, "typing")
    await callback.message.answer(
        "🤖 <b>Виберіть тип роботи:</b>",
        reply_markup=kb.work_type_kb,
        parse_mode="HTML"
    )
    await state.set_state(WorkStates.select_work_type)
    await callback.answer()


@other_work_router.message(OtherWorkStates.work_description)
async def process_other_work_description(message: types.Message, state: FSMContext):
    """Обробник опису іншої роботи"""
    # Отримуємо дані
    data = await state.get_data()
    description = message.text
    selected_partners = data.get("all_partners", [])
    nobody_selected = data.get("nobody_selected", False)

    if description == "🏠 На головну":
        await state.clear()
        await message.answer("👋 <b>Головне меню</b>", reply_markup=kb.main_menu_kb, parse_mode="HTML")

    # Перевіряємо наявність опису
    if not description:
        await message.bot.send_chat_action(message.chat.id, "typing")
        await message.answer(
            "❌ <b>Будь ласка, введіть опис виконаної роботи.</b>",
            parse_mode="HTML"
        )
        return

    # Зберігаємо іншу роботу в базу даних
    main_partner_id = selected_partners[0] if selected_partners else None
    await add_other_work(
        user_id=message.from_user.id,
        partner_id=main_partner_id,
        description=description,
        all_partners=selected_partners
    )

    # Формуємо згадку користувача
    user_mention = f"@{message.from_user.username}" if message.from_user.username else f"{message.from_user.id}"

    # Визначаємо текст партнерів
    users = await get_all_approved_users()
    partners_text = get_partners_text(selected_partners, nobody_selected, users)

    # Відправляємо повідомлення в загальний чат
    await message.bot.send_message(
        CHAT_ID,
        f"📝 <b>ІНША РОБОТА ВИКОНАНА</b> 📝\n\n"
        f"👤 Працівник: {user_mention}\n"
        f"👥 Партнери: {partners_text}\n"
        f"🕒 Час запису: <b>{datetime.datetime.now().strftime('%H:%M %d.%m.%Y')}</b>\n\n"
        f"📋 <b>Опис роботи:</b> {description}",
        parse_mode="HTML"
    )

    # Відправляємо повідомлення користувачу
    await message.bot.send_chat_action(message.chat.id, "typing")
    await message.answer(
        "✅ <b>Ваша робота була записана!</b>",
        reply_markup=kb.main_menu_kb,
        parse_mode="HTML"
    )

    # Очищуємо стан
    await state.clear()
