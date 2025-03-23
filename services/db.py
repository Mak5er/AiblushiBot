import datetime
from typing import List, Tuple

from sqlalchemy import BigInteger, Integer, Boolean, String, select, update, DateTime, delete, and_, Text, ForeignKey, \
    or_
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from config import DATABASE_URL, CHAT_ID

# Використання asyncpg
engine = create_async_engine(DATABASE_URL, echo=True, pool_size=5, max_overflow=10, future=True)

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[str] = mapped_column(String, nullable=True)
    is_approved: Mapped[bool] = mapped_column(Boolean, default=False)


class DryingSession(Base):
    __tablename__ = "drying_sessions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dehydrator_id: Mapped[int] = mapped_column(Integer, nullable=False)
    start_time: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    finish_time: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)


class WorkSession(Base):
    __tablename__ = "work_sessions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    partner_id: Mapped[int] = mapped_column(BigInteger, nullable=True)
    requested_by: Mapped[int] = mapped_column(BigInteger, nullable=False)  # ID користувача, який створив сесію
    work_type: Mapped[str] = mapped_column(String, nullable=False)  # "production", "packaging", "sales" або інші типи
    start_time: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    end_time: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=True)
    results: Mapped[str] = mapped_column(Text, nullable=True)
    message_id: Mapped[int] = mapped_column(Integer, nullable=True)  # ID закріпленого повідомлення
    packages_count: Mapped[int] = mapped_column(Integer, nullable=True)  # Кількість пакетів (для пакування)
    sales_amount: Mapped[float] = mapped_column(Integer, nullable=True)  # Сума продажів (для продажів)


class WorkPartner(Base):
    """Модель для зберігання всіх партнерів для робочої сесії"""
    __tablename__ = "work_partners"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(Integer, ForeignKey("work_sessions.id", ondelete="CASCADE"))
    partner_id: Mapped[int] = mapped_column(BigInteger, nullable=False)


class OtherWork(Base):
    __tablename__ = "other_work"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    partner_id: Mapped[int] = mapped_column(BigInteger, nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    work_date: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    duration: Mapped[int] = mapped_column(Integer, nullable=True)  # Тривалість у хвилинах


class OtherWorkPartner(Base):
    """Модель для зберігання всіх партнерів для іншої роботи"""
    __tablename__ = "other_work_partners"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    other_work_id: Mapped[int] = mapped_column(Integer, ForeignKey("other_work.id", ondelete="CASCADE"))
    partner_id: Mapped[int] = mapped_column(BigInteger, nullable=False)


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def add_user(user_id: int, username: str):
    async with async_session() as session:
        user = User(id=user_id, username=username)
        session.add(user)
        await session.commit()


async def is_user_approved(user_id: int) -> bool:
    async with async_session() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        return user.is_approved if user else False


async def approve_user(user_id: int):
    async with async_session() as session:
        await session.execute(update(User).where(User.id == user_id).values(is_approved=True))
        await session.commit()


async def reject_user(user_id: int):
    async with async_session() as session:
        await session.execute(update(User).where(User.id == user_id).values(is_approved=False))
        await session.commit()


async def is_dehydrator_busy(dehydrator_id: int) -> bool:
    async with async_session() as session:
        now = datetime.datetime.now()
        result = await session.execute(
            select(DryingSession).where(
                and_(
                    DryingSession.dehydrator_id == dehydrator_id,
                    DryingSession.finish_time > now
                )
            )
        )
        return result.scalar_one_or_none() is not None


async def start_drying(dehydrator_id: int, drying_hours: int, bot, user_id: int) -> datetime.datetime:
    if await is_dehydrator_busy(dehydrator_id):
        raise ValueError("❌ Цей дегідратор вже використовується!")

    now = datetime.datetime.now()
    finish_time = now + datetime.timedelta(hours=drying_hours)

    async with async_session() as session:
        new_session = DryingSession(
            dehydrator_id=dehydrator_id,
            start_time=now,
            finish_time=finish_time,
            user_id=user_id
        )
        session.add(new_session)
        await session.commit()

        # Відправляємо сповіщення про початок сушки
        await bot.send_message(
            CHAT_ID,
            f"🟢 <b>СУШКА РОЗПОЧАТА</b> 🟢\n\n"
            f"🔹 Дегідратор: <b>№{dehydrator_id}</b>\n"
            f"🕒 Час початку: <b>{now.strftime('%H:%M')}</b>\n"
            f"⏱ Тривалість: <b>{drying_hours} год.</b>\n"
            f"🏁 Закінчиться о: <b>{finish_time.strftime('%H:%M')}</b>",
            parse_mode="HTML"
        )

    return finish_time


async def check_and_notify_finished_drying(bot):
    async with async_session() as session:
        now = datetime.datetime.now()
        # Знаходимо всі сесії, які закінчились
        result = await session.execute(
            select(DryingSession).where(
                DryingSession.finish_time <= now
            )
        )
        finished_sessions = result.scalars().all()

        for finished_session in finished_sessions:
            # Обчислюємо тривалість у годинах
            duration_seconds = (finished_session.finish_time - finished_session.start_time).total_seconds()
            duration_hours = duration_seconds / 3600
            hours = int(duration_hours)
            minutes = int((duration_hours - hours) * 60)

            duration_text = f"{hours} год."
            if minutes > 0:
                duration_text += f" {minutes} хв."

            # Відправляємо сповіщення в загальний чат
            await bot.send_message(
                CHAT_ID,
                f"🔴 <b>СУШКА ЗАВЕРШЕНА</b> 🔴\n\n"
                f"🔹 Дегідратор: <b>№{finished_session.dehydrator_id}</b>\n"
                f"🕒 Час початку: <b>{finished_session.start_time.strftime('%H:%M')}</b>\n"
                f"🏁 Час завершення: <b>{finished_session.finish_time.strftime('%H:%M')}</b>\n"
                f"⏱ Тривалість: <b>{duration_text}</b>",
                parse_mode="HTML"
            )

            # Відправляємо сповіщення користувачу, який запускав сушку
            try:
                await bot.send_message(
                    finished_session.user_id,
                    f"🔴 <b>ВАША СУШКА ЗАВЕРШЕНА</b> 🔴\n\n"
                    f"🔹 Дегідратор: <b>№{finished_session.dehydrator_id}</b>\n"
                    f"🕒 Час початку: <b>{finished_session.start_time.strftime('%H:%M')}</b>\n"
                    f"🏁 Час завершення: <b>{finished_session.finish_time.strftime('%H:%M')}</b>\n"
                    f"⏱ Тривалість: <b>{duration_text}</b>",
                    parse_mode="HTML"
                )
            except Exception as e:
                # Якщо не вдалось відправити повідомлення користувачу, логуємо помилку
                print(f"Не вдалось відправити повідомлення користувачу {finished_session.user_id}: {str(e)}")

            # Видаляємо завершену сесію
            await session.execute(delete(DryingSession).where(DryingSession.id == finished_session.id))

        await session.commit()


async def get_dehydrator_session(dehydrator_id: int):
    """Отримання інформації про активну сесію дегідратора"""
    async with async_session() as session:
        now = datetime.datetime.now()
        result = await session.execute(
            select(DryingSession).where(
                and_(
                    DryingSession.dehydrator_id == dehydrator_id,
                    DryingSession.finish_time > now
                )
            )
        )
        session_data = result.scalar_one_or_none()
        return session_data


async def get_all_approved_users():
    """Отримати всіх затверджених користувачів"""
    async with async_session() as session:
        result = await session.execute(select(User).where(User.is_approved == True))
        return result.scalars().all()


async def start_work_session(user_id: int, partner_id: int, work_type: str, all_partners=None) -> int:
    """Почати робочу зміну"""
    now = datetime.datetime.now()

    async with async_session() as session:
        # Перевіряємо, чи є вже активна зміна для цього користувача
        result = await session.execute(
            select(WorkSession).where(
                and_(
                    WorkSession.user_id == user_id,
                    WorkSession.end_time == None
                )
            )
        )
        active_session = result.scalar_one_or_none()

        if active_session:
            raise ValueError("У вас вже є активна зміна!")

        new_session = WorkSession(
            user_id=user_id,
            partner_id=partner_id,
            requested_by=user_id,  # Додаємо хто створив сесію
            work_type=work_type,
            start_time=now
        )
        session.add(new_session)
        await session.commit()
        await session.refresh(new_session)

        # Додаємо всіх партнерів у таблицю WorkPartner
        if all_partners:
            for partner in all_partners:
                work_partner = WorkPartner(
                    session_id=new_session.id,
                    partner_id=partner
                )
                session.add(work_partner)

            await session.commit()

        return new_session.id


async def end_work_session(session_id: int, results: str, packages_count: int = None, sales_amount: float = None):
    """Завершити робочу зміну"""
    now = datetime.datetime.now()

    async with async_session() as session:
        # Формуємо дані для оновлення
        update_data = {"end_time": now, "results": results}

        # Якщо вказано кількість пакетів, додаємо їх
        if packages_count is not None:
            update_data["packages_count"] = packages_count

        # Якщо вказано суму продажів, додаємо її
        if sales_amount is not None:
            update_data["sales_amount"] = sales_amount

        await session.execute(
            update(WorkSession)
            .where(WorkSession.id == session_id)
            .values(**update_data)
        )
        await session.commit()

        # Отримуємо оновлену сесію
        result = await session.execute(
            select(WorkSession).where(WorkSession.id == session_id)
        )
        updated_session = result.scalar_one_or_none()
        return updated_session


async def get_active_work_session(user_id: int):
    """Отримати активну робочу зміну користувача"""
    async with async_session() as session:
        result = await session.execute(
            select(WorkSession).where(
                and_(
                    WorkSession.user_id == user_id,
                    WorkSession.end_time == None
                )
            )
        )
        return result.scalar_one_or_none()


async def update_work_session_message_id(session_id: int, message_id: int):
    """Оновити ID закріпленого повідомлення для зміни"""
    async with async_session() as session:
        await session.execute(
            update(WorkSession)
            .where(WorkSession.id == session_id)
            .values(message_id=message_id)
        )
        await session.commit()


async def add_other_work(user_id: int, partner_id: int, description: str, duration: int = None, all_partners=None):
    """Додати запис про іншу роботу"""
    now = datetime.datetime.now()

    async with async_session() as session:
        new_work = OtherWork(
            user_id=user_id,
            partner_id=partner_id,
            description=description,
            work_date=now,
            duration=duration
        )
        session.add(new_work)
        await session.commit()
        await session.refresh(new_work)

        # Додаємо всіх партнерів у таблицю OtherWorkPartner
        if all_partners:
            for partner in all_partners:
                other_work_partner = OtherWorkPartner(
                    other_work_id=new_work.id,
                    partner_id=partner
                )
                session.add(other_work_partner)

            await session.commit()

        return new_work.id


async def get_user_by_id(user_id: int):
    """Отримати інформацію про користувача за його ID"""
    async with async_session() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()


async def get_user_work_sessions(user_id: int, start_date: datetime.datetime, end_date: datetime.datetime):
    """Отримати всі сесії роботи користувача за вказаний період"""
    async with async_session() as session:
        # Знаходимо сесії, де користувач є головним або партнером
        query = select(WorkSession).where(
            and_(
                # Користувач є головним або одним з партнерів
                or_(
                    WorkSession.user_id == user_id,
                    WorkSession.requested_by == user_id,
                    WorkSession.id.in_(
                        select(WorkPartner.session_id).where(WorkPartner.partner_id == user_id)
                    )
                ),
                # Фільтруємо за датою
                WorkSession.start_time >= start_date,
                WorkSession.start_time <= end_date,
                # Тільки завершені сесії
                WorkSession.end_time != None
            )
        ).order_by(WorkSession.start_time.desc())

        result = await session.execute(query)
        return result.scalars().all()


async def get_user_other_works(user_id: int, start_date: datetime.datetime, end_date: datetime.datetime):
    """Отримати всі записи іншої роботи користувача за вказаний період"""
    async with async_session() as session:
        query = select(OtherWork).where(
            and_(
                or_(
                    OtherWork.user_id == user_id,
                    OtherWork.id.in_(
                        select(OtherWorkPartner.other_work_id).where(OtherWorkPartner.partner_id == user_id)
                    )
                ),
                OtherWork.work_date >= start_date,
                OtherWork.work_date <= end_date
            )
        ).order_by(OtherWork.work_date.desc())

        result = await session.execute(query)
        return result.scalars().all()


async def get_available_months(user_id: int) -> List[Tuple[int, int]]:
    """Отримати список місяців, за які є дані у користувача
    
    Returns:
        List[Tuple[int, int]]: Список кортежів (місяць, рік)
    """
    async with async_session() as session:
        from sqlalchemy import extract, distinct

        # Використовуємо SQLAlchemy Core для отримання унікальних місяців і років
        # Запит для робочих сесій
        work_query = select(
            distinct(extract('month', WorkSession.start_time).cast(Integer).label('month')),
            extract('year', WorkSession.start_time).cast(Integer).label('year')
        ).where(
            (WorkSession.user_id == user_id) | (WorkSession.partner_id == user_id)
        ).where(
            WorkSession.end_time != None
        )

        result_work = await session.execute(work_query)
        work_months = [(int(row[0]), int(row[1])) for row in result_work]

        # Запит для іншої роботи
        other_query = select(
            distinct(extract('month', OtherWork.work_date).cast(Integer).label('month')),
            extract('year', OtherWork.work_date).cast(Integer).label('year')
        ).where(
            (OtherWork.user_id == user_id) | (OtherWork.partner_id == user_id)
        )

        result_other = await session.execute(other_query)
        other_months = [(int(row[0]), int(row[1])) for row in result_other]

        # Об'єднуємо результати
        all_months = set(work_months + other_months)

        # Сортуємо за роком та місяцем у зворотньому порядку
        return sorted(all_months, key=lambda x: (x[1], x[0]), reverse=True)


async def get_all_work_sessions(start_date: datetime.datetime, end_date: datetime.datetime):
    """Отримати всі сесії роботи за вказаний період без фільтрації за користувачем"""
    async with async_session() as session:
        # Використовуємо SQLAlchemy для отримання всіх завершених сесій за період
        query = select(WorkSession).where(
            and_(
                WorkSession.start_time >= start_date,
                WorkSession.start_time <= end_date,
                WorkSession.end_time != None  # Тільки завершені сесії
            )
        ).order_by(WorkSession.start_time.desc())

        result = await session.execute(query)
        return result.scalars().all()


async def get_all_other_works(start_date: datetime.datetime, end_date: datetime.datetime):
    """Отримати всі записи іншої роботи за вказаний період без фільтрації за користувачем"""
    async with async_session() as session:
        # Використовуємо SQLAlchemy для отримання всіх записів іншої роботи за період
        query = select(OtherWork).where(
            and_(
                OtherWork.work_date >= start_date,
                OtherWork.work_date <= end_date
            )
        ).order_by(OtherWork.work_date.desc())

        result = await session.execute(query)
        return result.scalars().all()


async def get_available_months_all_users() -> List[Tuple[int, int]]:
    """Отримати список місяців, за які є дані для всіх користувачів
    
    Returns:
        List[Tuple[int, int]]: Список кортежів (місяць, рік)
    """
    async with async_session() as session:
        from sqlalchemy import extract, distinct

        # Використовуємо SQLAlchemy Core для отримання унікальних місяців і років
        # Запит для робочих сесій (всі користувачі)
        work_query = select(
            distinct(extract('month', WorkSession.start_time).cast(Integer).label('month')),
            extract('year', WorkSession.start_time).cast(Integer).label('year')
        ).where(
            WorkSession.end_time != None
        )

        result_work = await session.execute(work_query)
        work_months = [(int(row[0]), int(row[1])) for row in result_work]

        # Запит для іншої роботи (всі користувачі)
        other_query = select(
            distinct(extract('month', OtherWork.work_date).cast(Integer).label('month')),
            extract('year', OtherWork.work_date).cast(Integer).label('year')
        )

        result_other = await session.execute(other_query)
        other_months = [(int(row[0]), int(row[1])) for row in result_other]

        # Об'єднуємо результати
        all_months = set(work_months + other_months)

        # Сортуємо за роком та місяцем у зворотньому порядку
        return sorted(all_months, key=lambda x: (x[1], x[0]), reverse=True)
