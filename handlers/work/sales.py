import datetime

from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

import keyboards as kb
from config import CHAT_ID
from handlers.work import WorkStates
from handlers.work.common import calculate_duration
from services.db import (
    get_all_approved_users,
    start_work_session,
    get_active_work_session,
    end_work_session,
    update_work_session_message_id
)
from utils.helpers import (
    init_partner_selection,
    handle_nobody_selection,
    handle_partner_selection,
    get_partners_text,
    check_private_chat,
    calculate_duration
)

# Створюємо роутер для продажу
sales_router = Router()


class SalesStates(StatesGroup):
    """Стани для роботи з продажами"""
    partner_selection = State()  # Вибір партнерів для продажу
    count_packages = State()  # Введення кількості проданих пакетів
    sales_amount = State()  # Введення суми продажу


@sales_router.message(WorkStates.select_work_type, F.text.in_(["💰 Продаж", "💰 Продаж та реалізація"]))
async def start_sales_process(message: types.Message, state: FSMContext):
    """Обробник початку процесу продажу"""

    await message.bot.send_chat_action(message.chat.id, "typing")

    # Не реагуємо на повідомлення з груп
    if not check_private_chat(message):
        return

    # Ініціалізуємо стан для вибору партнерів
    await init_partner_selection(state, "sales")

    # Отримання всіх користувачів для вибору партнера
    users = await get_all_approved_users()

    # Створюємо інлайн-клавіатуру з користувачами
    await message.answer(
        "👥 <b>Виберіть партнерів для продажу:</b>",
        reply_markup=kb.get_multiselect_partners_kb(users, message.from_user.id),
        parse_mode="HTML"
    )
    await state.set_state(SalesStates.partner_selection)


@sales_router.callback_query(SalesStates.partner_selection, F.data == "select_nobody")
async def toggle_nobody_selection(callback: types.CallbackQuery, state: FSMContext):
    """Обробник вибору 'Нікого'"""
    await handle_nobody_selection(callback, state)


@sales_router.callback_query(SalesStates.partner_selection, F.data.startswith("select_partner_"))
async def toggle_partner_selection(callback: types.CallbackQuery, state: FSMContext):
    """Обробник вибору партнера"""
    await callback.bot.send_chat_action(callback.message.chat.id, "typing")
    await handle_partner_selection(callback, state)


@sales_router.callback_query(SalesStates.partner_selection, F.data == "confirm_partners")
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

    # Зберігаємо сесію продажу
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
        f"💰 <b>РОЗПОЧАТО ЗМІНУ ПРОДАЖУ</b> 💰\n\n"
        f"👤 Працівник: {user_mention}\n"
        f"👥 Партнери: {partners_text}\n"
        f"🕒 Час початку: <b>{datetime.datetime.now().strftime('%H:%M %d.%m.%Y')}</b>",
        parse_mode="HTML"
    )

    # Створюємо та закріплюємо інлайн клавіатуру для завершення зміни
    shift_message = await callback.message.answer(
        "🟢 <b>АКТИВНА ЗМІНА ПРОДАЖУ</b>",
        reply_markup=kb.end_shift_sales_kb,
        parse_mode="HTML"
    )

    # Закріплюємо повідомлення тільки в особистому чаті користувача з ботом
    try:
        if callback.message.chat.type == "private":
            await shift_message.pin(disable_notification=True)
    except Exception as e:
        print(f"Помилка при закріпленні повідомлення: {e}")

    # Зберігаємо ID повідомлення в базі даних для подальшого використання
    await update_work_session_message_id(session_id, shift_message.message_id)

    # Видаляємо повідомлення з інлайн-клавіатурою вибору партнерів
    await callback.message.delete()

    # Відправляємо повідомлення про початок роботи
    await callback.message.answer(
        "✅ <b>Ви почали зміну продажу!</b>\n"
        "По завершенню натисніть кнопку '🔴 Завершити зміну' на закріпленому повідомленні.",
        reply_markup=kb.main_menu_kb,
        parse_mode="HTML"
    )

    # Оновлюємо стан
    await state.set_state(WorkStates.work_in_progress)

    await callback.answer()


@sales_router.callback_query(SalesStates.partner_selection, F.data == "cancel_partners")
async def cancel_partners_selection(callback: types.CallbackQuery, state: FSMContext):
    """Обробник скасування вибору партнерів"""
    await callback.message.delete()
    await callback.message.answer(
        "🤖 <b>Виберіть тип роботи:</b>",
        reply_markup=kb.work_type_kb,
        parse_mode="HTML"
    )
    await state.set_state(WorkStates.select_work_type)
    await callback.answer()


@sales_router.callback_query(F.data == "end_shift_sales")
async def end_shift_callback(callback: types.CallbackQuery, state: FSMContext):
    """Обробник кнопки завершення зміни продажу"""
    # Отримуємо активну зміну
    active_session = await get_active_work_session(callback.from_user.id)

    if not active_session:
        await callback.answer("У вас немає активної зміни.", show_alert=True)
        return

    # Перевіряємо, чи це зміна продажу
    if active_session.work_type != "sales":
        await callback.answer("Цей обробник тільки для продажу.", show_alert=True)
        return

    # Відкріплюємо повідомлення тільки в особистому чаті
    try:
        if callback.message.chat.type == "private":
            await callback.message.unpin()
    except Exception as e:
        print(f"Помилка при відкріпленні повідомлення: {e}")

    # Питаємо кількість проданих пакетів
    await callback.message.answer(
        "📦 <b>Скільки пакетів ви продали?</b>\n"
        "Введіть число:",
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

    await callback.answer("Будь ласка, вкажіть кількість проданих пакетів")

    # Оновлюємо стан для очікування кількості пакетів
    await state.set_state(SalesStates.count_packages)


@sales_router.message(SalesStates.count_packages)
async def process_package_count(message: types.Message, state: FSMContext):
    """Обробник кількості проданих пакетів"""
    try:
        # Намагаємося конвертувати введене значення в число
        packages_count = int(message.text)

        if packages_count < 0:
            raise ValueError("Кількість пакетів не може бути від'ємною")

        # Зберігаємо кількість пакетів та переходимо до вказання суми продажу
        await state.update_data(packages_count=packages_count)

        # Питаємо суму продажу
        await message.answer(
            "💰 <b>Яка загальна сума продажу?</b>\n"
            "Введіть число (у гривнях):",
            reply_markup=kb.menu_kb,
            parse_mode="HTML"
        )

        # Оновлюємо стан для очікування суми продажу
        await state.set_state(SalesStates.sales_amount)

    except ValueError:
        # Якщо введено не число
        await message.answer(
            "❌ <b>Будь ласка, введіть коректне число пакетів.</b>",
            parse_mode="HTML"
        )
        return


@sales_router.message(SalesStates.sales_amount)
async def process_sales_amount(message: types.Message, state: FSMContext):
    """Обробник суми продажу"""
    # Отримуємо дані сесії
    data = await state.get_data()
    session_id = data.get("session_id")
    packages_count = data.get("packages_count")

    try:
        # Намагаємося конвертувати введене значення в число
        sales_amount = float(message.text)

        if sales_amount < 0:
            raise ValueError("Сума продажу не може бути від'ємною")

        # Завершуємо сесію і зберігаємо результати
        session = await end_work_session(
            session_id=session_id,
            results=f"Продано {packages_count} пакетів на суму {sales_amount} грн",
            packages_count=packages_count,
            sales_amount=sales_amount
        )

        # Розраховуємо тривалість зміни
        duration = calculate_duration(session.start_time)

        # Формуємо згадку користувача
        user_mention = f"@{message.from_user.username}" if message.from_user.username else f"{message.from_user.id}"

        # Отримуємо всіх партнерів
        all_partners = data.get("all_partners", [])
        nobody_selected = data.get("nobody_selected", False)

        # Визначаємо текст партнерів
        users = await get_all_approved_users()
        partners_text = get_partners_text(all_partners, nobody_selected, users)

        # Відправляємо повідомлення в загальний чат
        await message.bot.send_message(
            CHAT_ID,
            f"💰 <b>ЗМІНА ПРОДАЖУ ЗАВЕРШЕНА</b> 💰\n\n"
            f"👤 Працівник: {user_mention}\n"
            f"👥 Партнери: {partners_text}\n"
            f"🕒 Тривалість: <b>{duration}</b>\n"
            f"📦 Продано пакетів: <b>{packages_count}</b>\n"
            f"💵 Загальна сума: <b>{sales_amount} грн</b>",
            parse_mode="HTML"
        )

        # Відправляємо повідомлення користувачу
        await message.answer(
            f"✅ <b>Зміну продажу завершено!</b>\n"
            f"📦 Продано пакетів: <b>{packages_count}</b>\n"
            f"💵 Загальна сума: <b>{sales_amount} грн</b>\n"
            f"⏱ Тривалість зміни: <b>{duration}</b>",
            reply_markup=kb.main_menu_kb,
            parse_mode="HTML"
        )

        # Очищуємо стан
        await state.clear()

    except ValueError:
        # Якщо введено не число
        await message.answer(
            "❌ <b>Будь ласка, введіть коректну суму продажу (тільки число).</b>",
            parse_mode="HTML"
        )
        return
