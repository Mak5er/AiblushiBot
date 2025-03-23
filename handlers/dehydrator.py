import datetime
import re

from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import keyboards as kb
from services.db import is_user_approved, start_drying, is_dehydrator_busy, get_dehydrator_session
from utils.helpers import check_private_chat

dehydrator_router = Router()


class DryingSetup(StatesGroup):
    selecting_dehydrator = State()
    setting_time = State()


@dehydrator_router.message(F.text.in_(["🍇 Дегідратори", "🍇 Керування дегідраторами"]))
async def show_dehydrators(message: types.Message, state: FSMContext):
    if not check_private_chat(message):
        return

    user_id = message.from_user.id
    if not await is_user_approved(user_id):
        await message.bot.send_chat_action(message.chat.id, "typing")
        await message.answer("❌ <b>У вас немає доступу до цієї функції.</b>", parse_mode="HTML")
        return
    await state.set_state(DryingSetup.selecting_dehydrator)
    await message.bot.send_chat_action(message.chat.id, "typing")
    await message.answer("🔍 <b>Оберіть номер дегідратора:</b>", reply_markup=kb.dehydrators_with_menu_kb,
                         parse_mode="HTML")


@dehydrator_router.message(DryingSetup.selecting_dehydrator)
async def select_dehydrator(message: types.Message, state: FSMContext):
    await message.bot.send_chat_action(message.chat.id, "typing")


    if message.chat.type != "private":
        return

    user_id = message.from_user.id
    if not await is_user_approved(user_id):
        await message.bot.send_chat_action(message.chat.id, "typing")
        await message.answer("❌ <b>У вас немає доступу до цієї функції.</b>", parse_mode="HTML")
        return

    if message.text == "🏠 Меню" or message.text == "🏠 На головну":
        await message.bot.send_chat_action(message.chat.id, "typing")
        await message.answer("👋 <b>Головне меню</b>", reply_markup=kb.main_menu_kb, parse_mode="HTML")
        await state.clear()
        return

    try:
        # Використовуємо регулярний вираз для пошуку номера дегідратора
        dehydrator_pattern = re.compile(r'№?(\d+)')
        match = dehydrator_pattern.search(message.text)

        if match:
            dehydrator_id = int(match.group(1))
        else:
            # Якщо не знайдено явний номер, шукаємо в останньому слові
            words = message.text.split()
            if words:
                try:
                    dehydrator_id = int(words[-1])
                except ValueError:
                    raise ValueError("Номер дегідратора не знайдено")
            else:
                raise ValueError("Порожнє повідомлення")

        if dehydrator_id not in [1, 2, 3]:  # Перевірка на допустимі номери дегідраторів
            await message.bot.send_chat_action(message.chat.id, "typing")
            await message.answer("⚠️ <b>Будь ласка, оберіть дегідратор зі списку!</b>", parse_mode="HTML")
            return

        if await is_dehydrator_busy(dehydrator_id):
            session_data = await get_dehydrator_session(dehydrator_id)
            if session_data:
                duration_hours = int((session_data.finish_time - session_data.start_time).total_seconds() / 3600)

                await message.bot.send_chat_action(message.chat.id, "typing")
                await message.answer(
                    f"⚠️ <b>Дегідратор {dehydrator_id} зараз зайнятий!</b>\n\n"
                    f"🕒 Включений о: <b>{session_data.start_time.strftime('%H:%M')}</b>\n"
                    f"⏱ Тривалість: <b>{duration_hours} год.</b>\n"
                    f"🏁 Буде працювати до: <b>{session_data.finish_time.strftime('%H:%M')}</b>",
                    parse_mode="HTML",
                    reply_markup=kb.dehydrators_with_menu_kb
                )
                return

        await state.update_data(dehydrator_id=dehydrator_id)
        await state.set_state(DryingSetup.setting_time)
        await message.bot.send_chat_action(message.chat.id, "typing")
        await message.answer(
            f"✅ <b>Ви обрали дегідратор {dehydrator_id}</b>\n\n"
            f"⏱ <b>Введіть тривалість сушки:</b>",
            reply_markup=kb.time_input_kb,
            parse_mode="HTML"
        )
    except (ValueError, IndexError):
        await message.bot.send_chat_action(message.chat.id, "typing")
        await message.answer("⚠️ <b>Будь ласка, оберіть дегідратор зі списку!</b>", parse_mode="HTML")


@dehydrator_router.message(DryingSetup.setting_time, lambda message: message.text.startswith("⏱ "))
async def handle_time_button(message: types.Message, state: FSMContext):
    await message.bot.send_chat_action(message.chat.id, "typing")

    user_id = message.from_user.id
    if not await is_user_approved(user_id):
        await message.bot.send_chat_action(message.chat.id, "typing")
        await message.answer("❌ <b>У вас немає доступу до цієї функції.</b>", parse_mode="HTML")
        return

    if message.chat.type != "private":
        return

    try:
        # Використовуємо регулярний вираз для пошуку числа годин
        time_pattern = re.compile(r'⏱\s+(\d+)')
        match = time_pattern.search(message.text)

        if match:
            hours = int(match.group(1))
        else:
            # Альтернативний спосіб отримання числа, якщо регулярний вираз не спрацював
            time_text = message.text.replace("⏱ ", "").strip()
            hours = int(time_text.split()[0])  # Беремо перше слово (число)

        if hours <= 0:
            await message.bot.send_chat_action(message.chat.id, "typing")
            await message.answer("⚠️ <b>Будь ласка, введіть додатнє число годин.</b>", parse_mode="HTML")
            return

        data = await state.get_data()
        dehydrator_id = data.get('dehydrator_id')

        try:
            # Передаємо години напряму, а не хвилини
            finish_time = await start_drying(dehydrator_id, hours, message.bot, user_id)
            await message.bot.send_chat_action(message.chat.id, "typing")
            await message.answer(
                f"✅ <b>СУШКА РОЗПОЧАТА!</b>\n\n"
                f"🔹 Дегідратор: <b>№{dehydrator_id}</b>\n"
                f"🕒 Час початку: <b>{datetime.datetime.now().strftime('%H:%M')}</b>\n"
                f"⏱ Тривалість: <b>{hours} год.</b>\n"
                f"🏁 Закінчиться о: <b>{finish_time.strftime('%H:%M')}</b>",
                parse_mode="HTML",
                reply_markup=kb.main_menu_kb
            )
            await state.clear()

        except ValueError as e:
            await message.bot.send_chat_action(message.chat.id, "typing")
            await message.answer(f"⚠️ <b>{str(e)}</b>", parse_mode="HTML")
            await message.bot.send_chat_action(message.chat.id, "typing")
            await message.answer("🔍 <b>Оберіть номер дегідратора:</b>", reply_markup=kb.dehydrators_with_menu_kb,
                                 parse_mode="HTML")
            await state.set_state(DryingSetup.selecting_dehydrator)

    except ValueError:
        await message.bot.send_chat_action(message.chat.id, "typing")
        await message.answer("⚠️ <b>Будь ласка, введіть коректне число годин.</b>", parse_mode="HTML")


@dehydrator_router.message(DryingSetup.setting_time, F.text.in_(["🔙 Назад", "🔙 Повернутися назад"]))
async def back_to_dehydrator_selection(message: types.Message, state: FSMContext):
    # Не реагуємо на повідомлення з груп
    if message.chat.type != "private":
        return

    await state.set_state(DryingSetup.selecting_dehydrator)
    await message.bot.send_chat_action(message.chat.id, "typing")
    await message.answer("🔍 <b>Оберіть номер дегідратора:</b>", reply_markup=kb.dehydrators_with_menu_kb,
                         parse_mode="HTML")


@dehydrator_router.message(DryingSetup.setting_time, F.text.in_(["🏠 Меню", "🏠 На головну"]))
async def back_to_main_menu(message: types.Message, state: FSMContext):
    await message.bot.send_chat_action(message.chat.id, "typing")

    if message.chat.type != "private":
        return

    await message.answer("👋 <b>Головне меню</b>", reply_markup=kb.main_menu_kb, parse_mode="HTML")
    await state.clear()


@dehydrator_router.message(DryingSetup.setting_time)
async def process_time_input(message: types.Message, state: FSMContext):
    await message.bot.send_chat_action(message.chat.id, "typing")

    # Не реагуємо на повідомлення з груп
    if message.chat.type != "private":
        return

    # Передаємо керування до обробника кнопок, якщо текст починається з символу ⏱
    if message.text.startswith("⏱ "):
        return await handle_time_button(message, state)

    try:
        # Використовуємо регулярні вирази для розпізнавання різних форматів часу
        # Шукаємо формат "X годин(и)"
        hours_pattern = re.compile(r'(\d+)\s*(?:год(?:ин)?|h)')
        hours_match = hours_pattern.search(message.text)

        # Шукаємо формат "X хвилин"
        minutes_pattern = re.compile(r'(\d+)\s*(?:хв(?:илин)?|m)')
        minutes_match = minutes_pattern.search(message.text)

        # Визначаємо кількість годин
        drying_hours = 0

        if hours_match:
            drying_hours += int(hours_match.group(1))

        if minutes_match:
            # Переводимо хвилини в години (як дробове число)
            drying_hours += int(minutes_match.group(1)) / 60

        # Якщо не розпізнали ні годин ні хвилин, пробуємо інтерпретувати як просто число (годин)
        if not hours_match and not minutes_match:
            try:
                # Спроба розпізнати як ціле число
                drying_hours = int(message.text.strip())  # Вважаємо що це години
            except ValueError:
                await message.bot.send_chat_action(message.chat.id, "typing")
                await message.answer(
                    "⚠️ <b>Не вдалося розпізнати формат часу.</b>\n\n"
                    "Введіть час у форматі:\n"
                    "• <code>5</code> (годин)\n"
                    "• <code>5 годин</code>\n"
                    "• <code>30 хвилин</code> (буде переведено в години)\n"
                    "Або оберіть зі списку.",
                    parse_mode="HTML"
                )
                return

        # Перевіряємо, що час більше нуля
        if drying_hours <= 0:
            await message.bot.send_chat_action(message.chat.id, "typing")
            await message.answer("⚠️ <b>Будь ласка, введіть додатній час сушіння.</b>", parse_mode="HTML")
            return

        # Продовжуємо обробку введеного часу
        data = await state.get_data()
        dehydrator_id = data.get('dehydrator_id')

        try:
            # Передаємо години напряму
            finish_time = await start_drying(dehydrator_id, drying_hours, message.bot, user_id=message.from_user.id)

            # Форматуємо відображення часу (години та хвилини)
            hours = int(drying_hours)
            minutes = int((drying_hours - hours) * 60)

            duration_text = f"{hours} год."
            if minutes > 0:
                duration_text += f" {minutes} хв."

            await message.bot.send_chat_action(message.chat.id, "typing")
            await message.answer(
                f"✅ <b>СУШКА РОЗПОЧАТА!</b>\n\n"
                f"🔹 Дегідратор: <b>№{dehydrator_id}</b>\n"
                f"🕒 Час початку: <b>{datetime.datetime.now().strftime('%H:%M')}</b>\n"
                f"⏱ Тривалість: <b>{duration_text}</b>\n"
                f"🏁 Закінчиться о: <b>{finish_time.strftime('%H:%M')}</b>",
                parse_mode="HTML",
                reply_markup=kb.main_menu_kb
            )
            await state.clear()

        except ValueError as e:
            await message.bot.send_chat_action(message.chat.id, "typing")
            await message.answer(f"⚠️ <b>{str(e)}</b>", parse_mode="HTML")
            await message.bot.send_chat_action(message.chat.id, "typing")
            await message.answer("🔍 <b>Оберіть номер дегідратора:</b>", reply_markup=kb.dehydrators_with_menu_kb,
                                 parse_mode="HTML")
            await state.set_state(DryingSetup.selecting_dehydrator)

    except Exception as e:
        await message.bot.send_chat_action(message.chat.id, "typing")
        await message.answer(
            f"⚠️ <b>Помилка обробки введеного часу:</b> {str(e)}\n\n"
            f"Будь ласка, оберіть час зі списку або введіть коректне значення.",
            parse_mode="HTML"
        )
