from aiogram import Router
from aiogram.types import CallbackQuery

from services.db import approve_user, reject_user

admin_router = Router()


@admin_router.callback_query(lambda c: c.data.startswith("approve_"))
async def approve_user_handler(callback: CallbackQuery):
    user_id = int(callback.data.split("_")[1])
    await approve_user(user_id)
    await callback.bot.send_chat_action(user_id, "typing")
    await callback.bot.send_message(user_id, "Ваш запит схвалено! Тепер ви можете користуватися ботом.")
    await callback.bot.send_chat_action(callback.message.chat.id, "typing")
    await callback.answer("Користувача схвалено!")
    await callback.message.edit_text(f"✅ Користувача {user_id} схвалено!")


@admin_router.callback_query(lambda c: c.data.startswith("reject_"))
async def reject_user_handler(callback: CallbackQuery):
    user_id = int(callback.data.split("_")[1])
    await reject_user(user_id)
    await callback.bot.send_chat_action(user_id, "typing")
    await callback.bot.send_message(user_id, "Ваш запит відхилено.")
    await callback.bot.send_chat_action(callback.message.chat.id, "typing")
    await callback.answer("Користувача відхилено!")
    await callback.message.edit_text(f"❌ Користувача {user_id} відхилено!")
