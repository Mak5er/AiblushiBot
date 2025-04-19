import asyncio

from aiogram import Bot, Dispatcher

from config import BOT_TOKEN
from handlers.admin import admin_router
from handlers.dehydrator import dehydrator_router
from handlers.reports import reports_router
from handlers.user import user_router
from handlers.work import work_router
from services.db import init_db, check_and_notify_finished_drying


async def check_drying_sessions(bot: Bot):
    while True:
        await check_and_notify_finished_drying(bot)
        await asyncio.sleep(60)


async def main():
    import middleware

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()

    await init_db()

    for middleware in middleware.__all__:
        dp.message.outer_middleware(middleware())
        dp.callback_query.outer_middleware(middleware())
        dp.inline_query.outer_middleware(middleware())

    dp.include_router(admin_router)
    dp.include_router(work_router)
    dp.include_router(reports_router)
    dp.include_router(dehydrator_router)
    dp.include_router(user_router)

    polling_task = asyncio.create_task(dp.start_polling(bot))
    checking_task = asyncio.create_task(check_drying_sessions(bot))

    try:
        await asyncio.gather(polling_task, checking_task)
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
