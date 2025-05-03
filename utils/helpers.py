"""
Модуль з допоміжними функціями, які використовуються в різних обробниках
"""
import datetime
from typing import List, Optional, Union, Dict

from aiogram import types
from aiogram.fsm.context import FSMContext

from services.db import get_all_approved_users


async def init_partner_selection(
    state: FSMContext, 
    work_type: str
) -> None:
    """
    Ініціалізує початковий стан для вибору партнерів
    
    Args:
        state: FSM контекст
        work_type: Тип роботи
    """
    # Зберігаємо тип роботи
    await state.update_data(work_type=work_type)
    
    # Ініціалізуємо пустий список вибраних партнерів та стан вибору "Нікого"
    await state.update_data(selected_partners=[], nobody_selected=False)


async def handle_nobody_selection(
    callback: types.CallbackQuery, 
    state: FSMContext
) -> None:
    """
    Обробник вибору опції 'Нікого'
    
    Args:
        callback: Об'єкт колбеку
        state: FSM контекст
    """
    # Отримуємо поточний стан вибору
    data = await state.get_data()
    nobody_selected = data.get("nobody_selected", False)

    # Інвертуємо стан вибору "Нікого"
    nobody_selected = not nobody_selected

    # Якщо вибрано "Нікого", очищаємо список вибраних партнерів
    if nobody_selected:
        await state.update_data(selected_partners=[], nobody_selected=True)
    else:
        await state.update_data(nobody_selected=False)

    # Оновлюємо клавіатуру
    users = await get_all_approved_users()
    from keyboards import get_multiselect_partners_kb
    await callback.message.edit_reply_markup(
        reply_markup=get_multiselect_partners_kb(
            users,
            callback.from_user.id,
            selected_partners=[] if nobody_selected else data.get("selected_partners", []),
            nobody_selected=nobody_selected
        )
    )

    await callback.answer()


async def handle_partner_selection(
    callback: types.CallbackQuery, 
    state: FSMContext
) -> None:
    """
    Обробник вибору партнера
    
    Args:
        callback: Об'єкт колбеку
        state: FSM контекст
    """
    # Отримуємо ID партнера
    partner_id = int(callback.data.split("_")[2])

    # Отримуємо поточні вибрані партнери і стан "Нікого"
    data = await state.get_data()
    selected_partners = data.get("selected_partners", [])
    nobody_selected = data.get("nobody_selected", False)

    # Якщо було вибрано "Нікого", знімаємо цей вибір при виборі партнера
    if nobody_selected:
        nobody_selected = False
        await state.update_data(nobody_selected=False)

    # Додаємо або видаляємо партнера з списку
    if partner_id in selected_partners:
        selected_partners.remove(partner_id)
    else:
        selected_partners.append(partner_id)

    # Оновлюємо список вибраних партнерів
    await state.update_data(selected_partners=selected_partners)

    # Оновлюємо клавіатуру
    users = await get_all_approved_users()
    from keyboards import get_multiselect_partners_kb
    await callback.message.edit_reply_markup(
        reply_markup=get_multiselect_partners_kb(
            users,
            callback.from_user.id,
            selected_partners=selected_partners,
            nobody_selected=nobody_selected
        )
    )

    await callback.answer()


def get_partners_text(
    selected_partners: List[int], 
    nobody_selected: bool, 
    users: List
) -> str:
    """
    Формує текст зі списком партнерів
    
    Args:
        selected_partners: Список ID вибраних партнерів
        nobody_selected: Чи вибрано "Нікого"
        users: Список користувачів
        
    Returns:
        Текстове представлення партнерів
    """
    if nobody_selected or not selected_partners:
        return "Нікого"
    
    # Створюємо список згадок партнерів
    partner_mentions = []
    for partner_id in selected_partners:
        partner_username = None
        for user in users:
            if user.id == partner_id:
                partner_username = user.username
                break
        partner_mention = f"@{partner_username}" if partner_username else f"користувач ({partner_id})"
        partner_mentions.append(partner_mention)

    return ", ".join(partner_mentions)


def format_time(minutes: float) -> str:
    """Форматує час у хвилинах у зручний для читання формат (години та хвилини)
    
    Args:
        minutes: Час у хвилинах
        
    Returns:
        str: Відформатований час (наприклад, "2 год. 30 хв.")
    """
    if minutes is None or minutes == 0:
        return "0 хв."
        
    hours = int(minutes // 60)
    mins = int(minutes % 60)
    
    if hours > 0 and mins > 0:
        return f"{hours} год. {mins} хв."
    elif hours > 0:
        return f"{hours} год."
    else:
        return f"{mins} хв."


def calculate_duration(start_time: datetime.datetime) -> str:
    """
    Розраховує тривалість від вказаного часу до поточного моменту
    
    Args:
        start_time: Час початку
        
    Returns:
        Відформатована тривалість
    """
    now = datetime.datetime.now()
    duration = now - start_time
    return format_time(duration.total_seconds() / 60)


def check_private_chat(message: types.Message) -> bool:
    """
    Перевіряє, чи повідомлення надійшло з приватного чату
    
    Args:
        message: Об'єкт повідомлення
        
    Returns:
        True якщо чат приватний, інакше False
    """
    return message.chat.type == "private" 