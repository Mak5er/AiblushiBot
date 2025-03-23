import datetime

from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

import keyboards as kb
from config import CHAT_ID
from handlers.work import WorkStates
from services.db import (
    get_all_approved_users,
    start_work_session,
    get_active_work_session,
    update_work_session_message_id
)
from utils.helpers import (
    init_partner_selection,
    handle_nobody_selection,
    handle_partner_selection,
    get_partners_text,
    check_private_chat
)

# Створюємо роутер для виробництва
production_router = Router()


class ProductionStates(StatesGroup):
    """Стани для роботи з виробництвом"""
    partner_selection = State()  # Вибір партнерів для виробництва


@production_router.message(WorkStates.select_work_type,
                           F.text.in_(["🏭 Виробництво", "🏭 Виробництво сушених продуктів"]))
async def start_production_process(message: types.Message, state: FSMContext):
    """Обробник початку процесу виробництва"""
    await message.bot.send_chat_action(message.chat.id, "typing")

    # Не реагуємо на повідомлення з груп
    if not check_private_chat(message):
        return

    # Ініціалізуємо стан для вибору партнерів
    await init_partner_selection(state, "production")

    # Отримання всіх користувачів для вибору партнера
    users = await get_all_approved_users()

    # Створюємо інлайн-клавіатуру з користувачами
    await message.answer(
        "👥 <b>Виберіть партнерів для виробництва:</b>",
        reply_markup=kb.get_multiselect_partners_kb(users, message.from_user.id),
        parse_mode="HTML"
    )
    await state.set_state(ProductionStates.partner_selection)


@production_router.callback_query(ProductionStates.partner_selection, F.data == "select_nobody")
async def toggle_nobody_selection(callback: types.CallbackQuery, state: FSMContext):
    """Обробник вибору 'Нікого'"""
    await handle_nobody_selection(callback, state)


@production_router.callback_query(ProductionStates.partner_selection, F.data.startswith("select_partner_"))
async def toggle_partner_selection(callback: types.CallbackQuery, state: FSMContext):
    """Обробник вибору партнера"""
    await handle_partner_selection(callback, state)


@production_router.callback_query(ProductionStates.partner_selection, F.data == "confirm_partners")
async def confirm_partners(callback: types.CallbackQuery, state: FSMContext):
    """Обробник підтвердження вибору партнерів"""
    # Отримуємо дані партнерів
    data = await state.get_data()
    selected_partners = data.get("selected_partners", [])
    nobody_selected = data.get("nobody_selected", False)

    # Перевіряємо, чи вибрано хоча б одного партнера або опцію "Нікого"
    if not selected_partners and not nobody_selected:
        await callback.answer("❌ Будь ласка, виберіть принаймні одного партнера або вкажіть 'Нікого'", show_alert=True)
        return

    # Зберігаємо тип роботи
    work_type = data.get("work_type")

    # Зберігаємо сесію виробництва
    main_partner_id = selected_partners[0] if selected_partners else None
    session_id = await start_work_session(
        user_id=callback.from_user.id,
        partner_id=main_partner_id,
        work_type=work_type,
        all_partners=selected_partners
    )

    # Зберігаємо ID сесії та вибраних партнерів
    await state.update_data(session_id=session_id, all_partners=selected_partners, nobody_selected=nobody_selected)

    # Формуємо згадку користувача
    user_mention = f"@{callback.from_user.username}" if callback.from_user.username else f"{callback.from_user.id}"

    # Визначаємо текст партнерів
    users = await get_all_approved_users()
    partners_text = get_partners_text(selected_partners, nobody_selected, users)

    # Відправляємо повідомлення в загальний чат з роботою
    message = await callback.bot.send_message(
        CHAT_ID,
        f"🏭 <b>ПОЧАЛОСЯ ВИРОБНИЦТВО</b> 🏭\n\n"
        f"👤 Працівник: {user_mention}\n"
        f"👥 Партнери: {partners_text}\n"
        f"🕒 Час початку: <b>{datetime.datetime.now().strftime('%H:%M %d.%m.%Y')}</b>",
        parse_mode="HTML"
    )

    # Закріплюємо повідомлення з кнопкою для завершення зміни
    pinned_message = await callback.message.answer(
        f"🟢 <b>ЗМІНА ВИРОБНИЦТВА ПОЧАЛАСЬ</b>\n"
        f"⏱ Початок: <b>{datetime.datetime.now().strftime('%H:%M %d.%m.%Y')}</b>",
        reply_markup=kb.end_shift_production_kb,
        parse_mode="HTML"
    )

    # Закріплюємо повідомлення тільки в особистому чаті користувача з ботом
    try:
        if callback.message.chat.type == "private":
            await pinned_message.pin(disable_notification=True)
    except Exception as e:
        print(f"Помилка при закріпленні повідомлення: {e}")

    # Зберігаємо ID повідомлення в базі даних для подальшого використання
    await update_work_session_message_id(session_id, pinned_message.message_id)

    # Видаляємо повідомлення з інлайн-клавіатурою вибору партнерів
    await callback.message.delete()

    # Відправляємо повідомлення про початок роботи
    await callback.bot.send_chat_action(callback.message.chat.id, "typing")
    await callback.message.answer(
        "✅ <b>Ви почали виробляти продукт!</b>\n"
        "По завершенню натисніть кнопку '🔴 Завершити зміну' на закріпленому повідомленні.",
        reply_markup=kb.main_menu_kb,
        parse_mode="HTML"
    )

    # Оновлюємо стан
    await state.set_state(WorkStates.work_in_progress)

    await callback.answer()


@production_router.callback_query(ProductionStates.partner_selection, F.data == "cancel_partners")
async def cancel_partners_selection(callback: types.CallbackQuery, state: FSMContext):
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


@production_router.callback_query(F.data == "end_shift_production")
async def end_shift_callback(callback: types.CallbackQuery, state: FSMContext):
    """Обробник кнопки завершення зміни виробництва"""
    # Отримуємо активну зміну
    active_session = await get_active_work_session(callback.from_user.id)

    if not active_session:
        await callback.answer("У вас немає активної зміни.", show_alert=True)
        return

    # Перевіряємо, чи це зміна виробництва
    if active_session.work_type != "production":
        await callback.answer("Цей обробник тільки для виробництва.", show_alert=True)
        return

    try:
        if callback.message.chat.type == "private":
            await callback.message.unpin()
    except Exception as e:
        print(f"Помилка при відкріпленні повідомлення: {e}")

    # Питаємо, що було зроблено за зміну
    await callback.message.answer(
        "📝 <b>Опишіть, що було зроблено під час зміни:</b>",
        reply_markup=kb.menu_kb,
        parse_mode="HTML"
    )

    # Зберігаємо ID сесії
    await state.update_data(session_id=active_session.id)

    # Змінюємо текст кнопки
    await callback.message.edit_text(
        "🔴 <b>ЗМІНА ЗАВЕРШЕНА</b>",
        reply_markup=None,
        parse_mode="HTML"
    )

    await callback.answer("Будь ласка, опишіть результати вашої роботи")

    # Оновлюємо стан для очікування результатів роботи
    await state.set_state(WorkStates.work_in_progress)
