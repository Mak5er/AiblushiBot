import datetime

from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext

import keyboards as kb
from config import CHAT_ID
from handlers.work import WorkStates
from services.db import (
    get_active_work_session,
    end_work_session,
    get_all_approved_users
)
from utils.helpers import (
    check_private_chat,
    calculate_duration,
    get_partners_text
)


# Функція для форматування часу
def calculate_duration(start_time: datetime.datetime) -> str:
    """Розрахувати тривалість зміни"""
    now = datetime.datetime.now()
    duration = now - start_time
    hours, remainder = divmod(duration.seconds, 3600)
    minutes, _ = divmod(remainder, 60)

    if hours > 0:
        return f"{hours}г {minutes}хв"
    else:
        return f"{minutes}хв"


def register_common_handlers(router: Router) -> None:
    """Реєструє спільні хендлери для різних типів робіт"""

    @router.message(F.text.in_(["🤖 Робота", "🤖 Облік робочого часу"]))
    async def start_work_process(message: types.Message, state: FSMContext):
        """Обробник для початку процесу роботи"""

        await message.bot.send_chat_action(message.chat.id, "typing")
        # Не реагуємо на повідомлення з груп
        if not check_private_chat(message):
            return

        # Перевіряємо, чи є у користувача вже активна зміна
        active_session = await get_active_work_session(message.from_user.id)
        if active_session:
            await message.answer(
                "❗ У вас вже є активна зміна. Будь ласка, спочатку завершіть її.",
                reply_markup=kb.main_menu_kb
            )
            return

        await message.answer(
            "🤖 <b>Виберіть тип роботи:</b>",
            reply_markup=kb.work_type_kb,
            parse_mode="HTML"
        )
        await state.set_state(WorkStates.select_work_type)

    @router.message(WorkStates.select_work_type, F.text.in_(["🔙 Назад", "🔙 Повернутися назад"]))
    async def back_to_main_menu(message: types.Message, state: FSMContext):
        """Обробник для повернення до головного меню"""

        await message.bot.send_chat_action(message.chat.id, "typing")
        # Не реагуємо на повідомлення з груп
        if not check_private_chat(message):
            return

        await message.answer(
            "👋 <b>Головне меню</b>",
            reply_markup=kb.main_menu_kb,
            parse_mode="HTML"
        )
        await state.clear()

    @router.message(
        WorkStates.select_work_type,
        ~F.text.in_([
            "🏭 Виробництво", "🏭 Виробництво сушених продуктів",
            "📦 Пакування", "📦 Пакування продукції",
            "💰 Продаж", "💰 Продаж та реалізація",
            "📝 Інша робота", "📝 Інша діяльність",
            "🔙 Назад", "🔙 Повернутися назад"
        ])
    )
    async def unhandled_work_type(message: types.Message, state: FSMContext):
        """Обробник невизначеного типу роботи (найнижчий пріоритет)"""

        await message.bot.send_chat_action(message.chat.id, "typing")
        # Не реагуємо на повідомлення з груп
        if not check_private_chat(message):
            return

        await message.answer(
            "❌ Невідомий тип роботи. Будь ласка, виберіть з клавіатури:",
            reply_markup=kb.work_type_kb
        )

    @router.message(WorkStates.work_in_progress)
    async def process_work_results(message: types.Message, state: FSMContext):
        """Обробник результатів роботи після завершення зміни"""
        # Отримуємо дані сесії
        await message.bot.send_chat_action(message.chat.id, "typing")

        data = await state.get_data()
        session_id = data.get("session_id")

        if not session_id:
            await message.answer(
                "❌ <b>Не знайдено активної сесії.</b>\n"
                "Будь ласка, почніть новий робочий процес.",
                reply_markup=kb.main_menu_kb,
                parse_mode="HTML"
            )
            await state.clear()
            return

        # Отримуємо активну сесію для визначення типу роботи
        active_session = await get_active_work_session(message.from_user.id)

        if not active_session:
            await message.answer(
                "❌ <b>Робочу сесію було завершено іншим способом.</b>",
                reply_markup=kb.main_menu_kb,
                parse_mode="HTML"
            )
            await state.clear()
            return

        # Направляємо в потрібний обробник залежно від типу роботи
        work_type = active_session.work_type

        if work_type == "production":
            await handle_production_results(message, state, session_id, data, active_session)
        elif work_type == "packaging":
            await message.answer(
                "⚠️ Для пакування потрібно вказати кількість пакетів.\n"
                "Будь ласка, використовуйте правильний обробник завершення зміни.",
                reply_markup=kb.main_menu_kb
            )
            return
        elif work_type == "sales":
            await message.answer(
                "⚠️ Для продажу потрібно вказати кількість пакетів та суму продажу.\n"
                "Будь ласка, використовуйте правильний обробник завершення зміни.",
                reply_markup=kb.main_menu_kb
            )
            return
        else:
            # Якщо тип роботи не "production", це помилка маршрутизації
            await message.answer(
                f"❓ <b>Незнайомий тип роботи: {work_type}.</b>\n"
                "Будь ласка, оберіть правильний процес, щоб завершити зміну.",
                reply_markup=kb.main_menu_kb,
                parse_mode="HTML"
            )
            return


async def handle_production_results(message: types.Message, state: FSMContext, session_id: int, data: dict,
                                    active_session):
    """Обробник для завершення виробництва"""
    results = message.text

    await message.bot.send_chat_action(message.chat.id, "typing")

    # Завершуємо сесію
    session = await end_work_session(
        session_id=session_id,
        results=results
    )

    # Перевіряємо, чи сесія не є None
    if not session:
        await message.answer(
            "❌ <b>Помилка при завершенні сесії.</b>\n"
            "Сесія не знайдена або вже була завершена.",
            reply_markup=kb.main_menu_kb,
            parse_mode="HTML"
        )
        await state.clear()
        return

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
        f"🏭 <b>ВИРОБНИЦТВО ЗАВЕРШЕНО</b> 🏭\n\n"
        f"👤 Працівник: {user_mention}\n"
        f"👥 Партнери: {partners_text}\n"
        f"🕒 Тривалість: <b>{duration}</b>\n\n"
        f"📋 <b>Результати:</b> {results}",
        parse_mode="HTML"
    )

    # Відправляємо повідомлення користувачу
    await message.answer(
        f"✅ <b>Виробництво завершено!</b>\n"
        f"⏱ Тривалість зміни: <b>{duration}</b>",
        reply_markup=kb.main_menu_kb,
        parse_mode="HTML"
    )

    # Очищуємо стан
    await state.clear()

    return


# Експортуємо функції
__all__ = ["register_common_handlers"]
