import calendar
import datetime
from typing import Dict, List, Tuple, Optional, Union

from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup
from sqlalchemy import select

import keyboards as kb
from services.db import get_available_months, get_all_work_sessions, \
    get_all_other_works, get_available_months_all_users, get_user_by_id, WorkPartner, OtherWorkPartner, async_session
from utils.helpers import format_time

# Створюємо роутер для звітності
reports_router = Router()


class ReportStates(StatesGroup):
    """Стани для роботи зі звітністю"""
    select_month = State()  # Вибір місяця для звіту
    choosing_report_type = State()
    waiting_for_month = State()


@reports_router.message(F.text.in_(["📊 Звітність", "📊 Перегляд звітності"]))
async def start_report_process(message: types.Message, state: FSMContext):
    """Обробник для початку процесу звітності"""
    await message.bot.send_chat_action(message.chat.id, "typing")


    # Не реагуємо на повідомлення з груп
    if message.chat.type != "private":
        return

    try:
        # Отримуємо доступні місяці для всіх користувачів
        available_months = await get_available_months_all_users()

        if not available_months:
            # Якщо немає доступних даних
            await message.answer(
                "❌ <b>У системі поки немає завершених робочих сесій.</b>\n"
                "Дані для звіту відсутні.",
                reply_markup=kb.main_menu_kb,
                parse_mode="HTML"
            )
            return

        # Створюємо клавіатуру з доступними місяцями
        months_kb = get_months_keyboard(available_months)

        await message.answer(
            "📅 <b>Виберіть місяць для отримання звіту по всіх користувачах:</b>",
            reply_markup=months_kb,
            parse_mode="HTML"
        )
        await state.set_state(ReportStates.select_month)
    except Exception as e:
        print(f"Помилка при запуску звітів: {str(e)}")
        print(f"Тип помилки: {type(e)}")
        import traceback
        traceback.print_exc()

        await message.answer(
            f"❌ <b>Сталася помилка при отриманні доступних місяців:</b>\n"
            f"<code>{str(e)}</code>\n\n"
            f"Спробуйте пізніше або зверніться до адміністратора.",
            parse_mode="HTML",
            reply_markup=kb.main_menu_kb
        )


@reports_router.message(ReportStates.select_month)
async def process_month_selection(message: types.Message, state: FSMContext):
    """Обробник вибору місяця для звіту"""

    await message.bot.send_chat_action(message.chat.id, "typing")

    month_text = message.text

    # Перевіряємо формат повідомлення (має бути "Місяць YYYY")
    if not month_text or " " not in month_text:
        # Отримуємо доступні місяці
        user_id = message.from_user.id
        available_months = await get_available_months(user_id)

        await message.answer(
            "❌ <b>Невірний формат вибору місяця.</b>\n"
            "Будь ласка, виберіть місяць з клавіатури.",
            reply_markup=get_months_keyboard(available_months),
            parse_mode="HTML"
        )
        return

    month_name, year_str = month_text.split(" ", 1)
    try:
        year = int(year_str)
        month = get_month_number(month_name)

        if month == 0:
            raise ValueError("Невірна назва місяця")

        # Отримуємо дані про роботу користувача за вказаний місяць
        await generate_monthly_report(message, month, year)

        # Повертаємось до головного меню
        await message.answer(
            "🏠 <b>Головне меню</b>",
            reply_markup=kb.main_menu_kb,
            parse_mode="HTML"
        )
        await state.clear()

    except ValueError:
        # Отримуємо доступні місяці
        user_id = message.from_user.id
        available_months = await get_available_months(user_id)

        await message.answer(
            "❌ <b>Невірний формат дати.</b>\n"
            "Будь ласка, виберіть місяць з клавіатури.",
            reply_markup=get_months_keyboard(available_months),
            parse_mode="HTML"
        )


@reports_router.message(ReportStates.select_month, F.text.in_(["🔙 Назад", "🔙 Повернутися назад"]))
async def back_to_main_menu(message: types.Message, state: FSMContext):
    """Обробник для повернення до головного меню з вибору місяця"""
    await message.bot.send_chat_action(message.chat.id, "typing")


    if message.chat.type != "private":
        return

    await message.answer(
        "👋 <b>Головне меню</b>",
        reply_markup=kb.main_menu_kb,
        parse_mode="HTML"
    )
    await state.clear()


async def generate_monthly_report(message: types.Message, month: int, year: int):
    """Генерує та відправляє звіт за вказаний місяць для всіх користувачів"""
    start_date, end_date = get_month_range(month, year)
    await message.bot.send_chat_action(message.chat.id, "typing")



    try:
        # Отримуємо дані про всіх користувачів
        await message.answer("🔍 <b>Пошук даних...</b>", parse_mode="HTML")
        await message.bot.send_chat_action(message.chat.id, "typing") 
        all_work_sessions = await get_all_work_sessions(start_date, end_date)
        all_other_works = await get_all_other_works(start_date, end_date)


        # Аналізуємо дані та формуємо звіт для всіх користувачів
        await message.answer("⚙️ <b>Аналізую дані...</b>", parse_mode="HTML")
        await message.bot.send_chat_action(message.chat.id, "typing")
        report_data = await analyze_all_work_data(all_work_sessions, all_other_works)


        # Спочатку надсилаємо загальні підсумки
        month_name = get_month_name(month)
        totals = report_data["totals"]

        await message.answer("📝 <b>Формую загальний звіт...</b>", parse_mode="HTML")
        report = f"📊 <b>Звіт за {month_name} {year} - Загальні підсумки</b>\n\n"
        report += f"📋 <b>Загальні підсумки:</b>\n"
        report += f"🏭 <b>Виробництво:</b> {format_time(totals['production']['time'])}\n"
        report += f"📦 <b>Пакування:</b> {format_time(totals['packaging']['time'])}, {totals['packaging']['packages']} пакетів\n"
        report += f"💰 <b>Продаж:</b> {format_time(totals['sales']['time'])}, {totals['sales']['packages']} пакетів, {totals['sales']['amount']} грн\n"
        report += f"📝 <b>Інша робота:</b> {format_time(totals['other_work']['time'])}\n\n"

        # Відправляємо загальний звіт
        await message.answer(report, parse_mode="HTML")

        # Готуємо детальний звіт по користувачах
        await message.answer("📊 <b>Формую детальний звіт по користувачах...</b>", parse_mode="HTML")
        users_report = f"📊 <b>Детальний звіт за {month_name} {year} по користувачах</b>\n\n"

        for user_id, user_data in report_data["users"].items():
            user = await get_user_by_id(user_id)
            if not user:
                continue  # Пропускаємо користувача, якщо не знайдено

            user_name = f"@{user.username}" if user.username else f"Користувач {user_id}"
            users_report += f"👤 <b>{user_name}</b>\n"

            # Додаємо інформацію про виробництво
            production = user_data["production"]
            production_time = production['host_time'] + production['partner_time']
            if production_time > 0:
                users_report += f"🏭 Виробництво: {format_time(production_time)}\n"

            # Додаємо інформацію про пакування
            packaging = user_data["packaging"]
            packaging_time = packaging['host_time'] + packaging['partner_time']
            if packaging_time > 0:
                users_report += f"📦 Пакування: {format_time(packaging_time)}"
                if packaging['packages'] > 0:
                    users_report += f", {packaging['packages']} пакетів"
                users_report += "\n"

            # Додаємо інформацію про продаж
            sales = user_data["sales"]
            sales_time = sales['host_time'] + sales['partner_time']
            if sales_time > 0:
                users_report += f"💰 Продаж: {format_time(sales_time)}"
                if sales['packages'] > 0:
                    users_report += f", {sales['packages']} пакетів"
                if sales['amount'] > 0:
                    users_report += f", {sales['amount']} грн"
                users_report += "\n"

            # Додаємо інформацію про іншу роботу
            other_work = user_data["other_work"]
            if other_work['time'] > 0:
                users_report += f"📝 Інша робота: {format_time(other_work['time'])}\n"

            # Додаємо загальний час
            total_time = production_time + packaging_time + sales_time + other_work['time']
            users_report += f"⏱ <b>Загальний час:</b> {format_time(total_time)}\n\n"

        # Відправляємо детальний звіт по користувачах
        if len(users_report) > 4096:
            # Розбиваємо звіт на частини, якщо він занадто довгий
            for i in range(0, len(users_report), 4000):
                part = users_report[i:i+4000]
                await message.answer(part, parse_mode="HTML")
        else:
            await message.answer(users_report, parse_mode="HTML")

    except Exception as e:
        print(f"Error generating monthly report: {str(e)}")
        await message.answer(f"❌ <b>Помилка при формуванні звіту:</b> {str(e)}", parse_mode="HTML")


def analyze_work_data(work_sessions: List, other_works: List) -> Dict:
    """Аналізує дані про роботи та повертає структуровану інформацію для звіту"""
    report = {
        "production": {"host_time": 0, "partner_time": 0, "sessions": []},
        "packaging": {"host_time": 0, "partner_time": 0, "sessions": [], "packages": 0},
        "sales": {"host_time": 0, "partner_time": 0, "sessions": [], "packages": 0, "amount": 0},
        "other_work": {"time": 0, "works": []}
    }

    # Обробляємо сесії роботи
    for session in work_sessions:
        if not session.end_time:
            continue  # Пропускаємо незавершені сесії

        # Розраховуємо тривалість у хвилинах
        duration_minutes = (session.end_time - session.start_time).total_seconds() / 60

        # Визначаємо, чи користувач був головним або партнером
        try:
            is_host = session.user_id == session.requested_by
        except (AttributeError, TypeError):
            # Якщо поле requested_by відсутнє, використовуємо user_id
            is_host = True  # За замовчуванням вважаємо головним

        work_type = session.work_type

        # Додаємо дані в залежності від типу роботи
        if work_type == "production":
            if is_host:
                report["production"]["host_time"] += duration_minutes
            else:
                report["production"]["partner_time"] += duration_minutes

            # Додаємо сесію до списку для детального відображення
            work_date = session.start_time.date()
            report["production"]["sessions"].append({
                "date": work_date.strftime("%d.%m.%Y"),
                "duration": duration_minutes,
                "results": session.results if session.results else ""
            })

        elif work_type == "packaging":
            if is_host:
                report["packaging"]["host_time"] += duration_minutes
            else:
                report["packaging"]["partner_time"] += duration_minutes

            # Додаємо кількість пакетів
            report["packaging"]["packages"] += session.packages_count if session.packages_count else 0

            # Додаємо сесію до списку
            work_date = session.start_time.date()
            report["packaging"]["sessions"].append({
                "date": work_date.strftime("%d.%m.%Y"),
                "duration": duration_minutes,
                "packages": session.packages_count if session.packages_count else 0
            })

        elif work_type == "sales":
            if is_host:
                report["sales"]["host_time"] += duration_minutes
            else:
                report["sales"]["partner_time"] += duration_minutes

            # Додаємо кількість пакетів та суму продажу
            report["sales"]["packages"] += session.packages_count if session.packages_count else 0
            report["sales"]["amount"] += session.sales_amount if session.sales_amount else 0

            # Додаємо сесію до списку
            work_date = session.start_time.date()
            report["sales"]["sessions"].append({
                "date": work_date.strftime("%d.%m.%Y"),
                "duration": duration_minutes,
                "packages": session.packages_count if session.packages_count else 0,
                "amount": session.sales_amount if session.sales_amount else 0
            })

    # Обробляємо інші роботи
    for work in other_works:
        work_date = work.created_at.date()
        
        # Додаємо тривалість іншої роботи
        work_duration = work.duration if work.duration else 0
        report["other_work"]["time"] += work_duration

        # Додаємо опис роботи
        report["other_work"]["works"].append({
            "date": work_date.strftime("%d.%m.%Y"),
            "description": work.description,
            "duration": work.duration if work.duration else 0
        })

    return report


def format_report(report_data: Dict, month: int, year: int) -> str:
    """Форматує дані звіту у текстове повідомлення"""
    month_name = get_month_name(month)

    report = f"📊 <b>Звіт за {month_name} {year}</b>\n\n"

    # Додаємо інформацію про виробництво
    production = report_data["production"]
    report += f"🏭 <b>Виробництво:</b>\n"
    report += f"   - Всього: {format_time(production['host_time'] + production['partner_time'])}\n\n"

    # Додаємо інформацію про пакування
    packaging = report_data["packaging"]
    report += f"📦 <b>Пакування:</b>\n"
    report += f"   - Всього: {format_time(packaging['host_time'] + packaging['partner_time'])}\n"
    if packaging["packages"] > 0:
        report += f"   - Пакетів: {packaging['packages']}\n\n"
    else:
        report += "\n"

    # Додаємо інформацію про продаж
    sales = report_data["sales"]
    report += f"💰 <b>Продаж:</b>\n"
    report += f"   - Всього: {format_time(sales['host_time'] + sales['partner_time'])}\n"
    if sales["packages"] > 0:
        report += f"   - Продано пакетів: {sales['packages']}\n"
    if sales["amount"] > 0:
        report += f"   - Сума продажу: {sales['amount']} грн.\n\n"
    else:
        report += "\n"

    # Додаємо інформацію про іншу роботу
    other_work = report_data["other_work"]
    report += f"📝 <b>Інша робота:</b>\n"
    report += f"   - Всього: {format_time(other_work['time'])}\n"

    if other_work["works"]:
        report += "   - Виконані завдання:\n"
        for work in other_work["works"]:
            report += f"     • {work['description']}\n"

    return report


def get_months_keyboard(available_months: List[Tuple[int, int]]) -> types.ReplyKeyboardMarkup:
    """Створює клавіатуру з доступними місяцями
    
    Args:
        available_months: Список кортежів (місяць, рік)
    """
    # Сортуємо місяці в зворотньому хронологічному порядку
    sorted_months = sorted(available_months, key=lambda x: (x[1], x[0]), reverse=True)

    buttons = []
    for month, year in sorted_months:
        month_name = get_month_name(month)
        buttons.append([KeyboardButton(text=f"{month_name} {year}")])

    # Додаємо кнопку "Назад"
    buttons.append([KeyboardButton(text="🔙 Назад")])

    return types.ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def get_month_number(month_name: str) -> int:
    """Повертає номер місяця за його назвою українською"""
    months = {
        "Січень": 1, "Лютий": 2, "Березень": 3, "Квітень": 4,
        "Травень": 5, "Червень": 6, "Липень": 7, "Серпень": 8,
        "Вересень": 9, "Жовтень": 10, "Листопад": 11, "Грудень": 12
    }
    return months.get(month_name, 0)


def get_month_name(month_number: int) -> str:
    """Повертає назву місяця українською за його номером"""
    months = {
        1: "Січень", 2: "Лютий", 3: "Березень", 4: "Квітень",
        5: "Травень", 6: "Червень", 7: "Липень", 8: "Серпень",
        9: "Вересень", 10: "Жовтень", 11: "Листопад", 12: "Грудень"
    }
    return months.get(month_number, "")


def get_month_range(month: int, year: int) -> Tuple[datetime.datetime, datetime.datetime]:
    """Повертає початок і кінець місяця"""
    first_day = datetime.datetime(year, month, 1)
    
    # Визначаємо останній день місяця
    last_day = datetime.datetime(year, month, calendar.monthrange(year, month)[1])
    
    # Встановлюємо час на кінець дня
    last_day = last_day.replace(hour=23, minute=59, second=59)
    
    return first_day, last_day


async def analyze_all_work_data(all_work_sessions: List, all_other_works: List) -> Dict:
    """Аналізує дані всіх користувачів та повертає структуровану інформацію для звіту"""
    report = {
        "totals": {
            "production": {"time": 0, "sessions": 0},
            "packaging": {"time": 0, "sessions": 0, "packages": 0},
            "sales": {"time": 0, "sessions": 0, "packages": 0, "amount": 0},
            "other_work": {"time": 0, "works": 0}
        },
        "users": {}
    }

    # Ініціалізуємо словник для зберігання даних користувачів
    unique_users = set()
    for session in all_work_sessions:
        unique_users.add(session.user_id)
    
    for work in all_other_works:
        unique_users.add(work.user_id)

    for user_id in unique_users:
        report["users"][user_id] = {
            "production": {"host_time": 0, "partner_time": 0},
            "packaging": {"host_time": 0, "partner_time": 0, "packages": 0},
            "sales": {"host_time": 0, "partner_time": 0, "packages": 0, "amount": 0},
            "other_work": {"time": 0}
        }

    # Обробляємо сесії роботи
    for session in all_work_sessions:
        if not session.end_time:
            continue  # Пропускаємо незавершені сесії

        # Розраховуємо тривалість у хвилинах
        duration_minutes = (session.end_time - session.start_time).total_seconds() / 60
        
        # Визначаємо тип роботи
        work_type = session.work_type
        
        # Визначаємо користувача
        user_id = session.user_id
        
        # Визначаємо, чи користувач був головним або партнером
        try:
            is_host = session.user_id == session.requested_by
        except (AttributeError, TypeError):
            is_host = True  # За замовчуванням вважаємо головним

        # Додаємо дані в залежності від типу роботи
        if work_type == "production":
            # Додаємо до загальних підсумків
            report["totals"]["production"]["time"] += duration_minutes
            report["totals"]["production"]["sessions"] += 1
            
            # Додаємо до користувача
            if is_host:
                report["users"][user_id]["production"]["host_time"] += duration_minutes
            else:
                report["users"][user_id]["production"]["partner_time"] += duration_minutes
        
        elif work_type == "packaging":
            # Додаємо до загальних підсумків
            report["totals"]["packaging"]["time"] += duration_minutes
            report["totals"]["packaging"]["sessions"] += 1
            packages_count = session.packages_count if session.packages_count else 0
            report["totals"]["packaging"]["packages"] += packages_count
            
            # Додаємо до користувача
            if is_host:
                report["users"][user_id]["packaging"]["host_time"] += duration_minutes
            else:
                report["users"][user_id]["packaging"]["partner_time"] += duration_minutes
            
            # Додаємо кількість пакетів (тільки для головного)
            if is_host:
                report["users"][user_id]["packaging"]["packages"] += packages_count
        
        elif work_type == "sales":
            # Додаємо до загальних підсумків
            report["totals"]["sales"]["time"] += duration_minutes
            report["totals"]["sales"]["sessions"] += 1
            packages_count = session.packages_count if session.packages_count else 0
            sales_amount = session.sales_amount if session.sales_amount else 0
            report["totals"]["sales"]["packages"] += packages_count
            report["totals"]["sales"]["amount"] += sales_amount
            
            # Додаємо до користувача
            if is_host:
                report["users"][user_id]["sales"]["host_time"] += duration_minutes
            else:
                report["users"][user_id]["sales"]["partner_time"] += duration_minutes
            
            # Додаємо кількість пакетів та суму (тільки для головного)
            if is_host:
                report["users"][user_id]["sales"]["packages"] += packages_count
                report["users"][user_id]["sales"]["amount"] += sales_amount

    # Обробляємо інші роботи
    for work in all_other_works:
        user_id = work.user_id
        
        # Додаємо тривалість іншої роботи
        work_duration = work.duration if work.duration else 0
        
        # Додаємо до загальних підсумків
        report["totals"]["other_work"]["time"] += work_duration
        report["totals"]["other_work"]["works"] += 1
        
        # Додаємо до користувача
        if user_id in report["users"]:
            report["users"][user_id]["other_work"]["time"] += work_duration

    return report


def format_all_users_report(report_data: Dict, month: int, year: int) -> str:
    """Форматує дані звіту по всіх користувачах у текстове повідомлення
    
    Args:
        report_data: Дані звіту
        month: Місяць
        year: Рік
        
    Returns:
        str: Відформатоване повідомлення
    """
    users_data = report_data["users_data"]
    totals = report_data["totals"]

    month_name = get_month_name(month)

    # Функція для форматування часу
    def format_time(minutes: float) -> str:
        hours = int(minutes // 60)
        mins = int(minutes % 60)
        if hours > 0:
            return f"{hours} год. {mins} хв."
        else:
            return f"{mins} хв."

    report = f"📊 <b>Звіт за {month_name} {year} - Всі користувачі</b>\n\n"

    # Додаємо загальні підсумки
    report += f"📋 <b>Загальні підсумки:</b>\n"
    report += f"🏭 <b>Виробництво:</b> {format_time(totals['production']['time'])}\n"

    report += f"📦 <b>Пакування:</b> {format_time(totals['packaging']['time'])}\n"
    if totals["packaging"]["packages"] > 0:
        report += f"   - Всього пакетів: {totals['packaging']['packages']}\n"

    report += f"💰 <b>Продаж:</b> {format_time(totals['sales']['time'])}\n"
    if totals["sales"]["packages"] > 0:
        report += f"   - Всього пакетів продано: {totals['sales']['packages']}\n"
    if totals["sales"]["amount"] > 0:
        report += f"   - Всього продано: {totals['sales']['amount']} грн.\n"

    report += f"📝 <b>Інша робота:</b> {format_time(totals['other_work']['time'])}\n"
    report += f"⏱ <b>Загальний час:</b> {format_time(totals['total_time'])}\n\n"

    # Сортуємо користувачів за іменами
    sorted_users = sorted(users_data.items(), key=lambda x: x[1]['username'])

    # Детальна інформація по кожному користувачу
    for user_id, user_data in sorted_users:
        username = user_data["username"]
        report += f"👤 <b>{username}</b>\n"

        # Виробництво
        production = user_data["production"]
        prod_total = production['host_time'] + production['partner_time']
        if prod_total > 0:
            report += f"🏭 <b>Виробництво:</b> {format_time(prod_total)}\n"

        # Пакування
        packaging = user_data["packaging"]
        pack_total = packaging['host_time'] + packaging['partner_time']
        if pack_total > 0:
            report += f"📦 <b>Пакування:</b> {format_time(pack_total)}\n"

        # Продаж
        sales = user_data["sales"]
        sales_total = sales['host_time'] + sales['partner_time']
        if sales_total > 0:
            report += f"💰 <b>Продаж:</b> {format_time(sales_total)}\n"

        # Інша робота
        other_work = user_data["other_work"]
        if other_work["time"] > 0:
            report += f"📝 <b>Інша робота:</b> {format_time(other_work['time'])}\n"
            if other_work["works"]:
                report += "   - Виконані завдання:\n"
                for work in other_work["works"]:
                    # Показуємо дату, тривалість та опис
                    work_time = work["duration"]
                    if work_time:
                        report += f"     • {work['date']} ({work_time} год.) - {work['description']}\n"
                    else:
                        report += f"     • {work['date']} - {work['description']}\n"

        report += f"⏱ <b>Загальний час:</b> {format_time(user_data['total_time'])}\n\n"

    return report
