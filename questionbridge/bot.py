import html as html_module
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from .config import settings
from . import store

bot = Bot(token=settings.BOT_TOKEN)
dp = Dispatcher()

_SEP = "━" * 22


def _keyboard(question_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Yes", callback_data=f"a:{question_id}:yes"),
            InlineKeyboardButton(text="❌ No",  callback_data=f"a:{question_id}:no"),
        ],
        [
            InlineKeyboardButton(text="🚫 Cancel request", callback_data=f"a:{question_id}:cancel"),
        ],
    ])


# ── Commands ──────────────────────────────────────────────────────────────────

@dp.message(Command("start", "help"))
async def cmd_start(message: types.Message):
    if message.from_user.id != settings.OWNER_CHAT_ID:
        return
    await message.answer(
        "🤖 <b>QuestionBridge</b>\n\n"
        "I forward questions from Claude to you.\n\n"
        "• <b>Reply</b> to a question message with your answer\n"
        "• Or tap <b>Yes / No</b> for quick confirmations\n\n"
        "<b>Commands:</b>\n"
        "/away — tell Claude to use the bridge\n"
        "/back — tell Claude to use the chat\n"
        "/pending — list pending questions",
        parse_mode="HTML",
    )


@dp.message(Command("away"))
async def cmd_away(message: types.Message):
    if message.from_user.id != settings.OWNER_CHAT_ID:
        return
    store.away = True
    await message.answer("🌙 <b>Away mode ON</b> — Claude will use the bridge.", parse_mode="HTML")


@dp.message(Command("back"))
async def cmd_back(message: types.Message):
    if message.from_user.id != settings.OWNER_CHAT_ID:
        return
    store.away = False
    await message.answer("👋 <b>Away mode OFF</b> — Claude will use the chat.", parse_mode="HTML")


@dp.message(Command("pending"))
async def cmd_pending(message: types.Message):
    if message.from_user.id != settings.OWNER_CHAT_ID:
        return
    pending = [q for q in store.questions.values() if q.status == "pending"]
    if not pending:
        await message.answer("✅ No pending questions.")
        return
    lines = [f"📋 <b>Pending ({len(pending)})</b>\n"]
    for q in pending:
        preview = html_module.escape(q.question[:60])
        ellipsis = "…" if len(q.question) > 60 else ""
        lines.append(f"• <code>{q.id}</code>: {preview}{ellipsis}")
    await message.answer("\n".join(lines), parse_mode="HTML")


# ── Send a question ───────────────────────────────────────────────────────────

async def send_question(question: store.Question) -> None:
    text = (
        f"🤔 <b>Question</b> <code>[{question.id}]</code>\n"
        f"{_SEP}\n\n"
        f"{html_module.escape(question.question)}"
    )
    if question.context:
        text += (
            f"\n\n📎 <b>Context:</b>\n"
            f"<i>{html_module.escape(question.context)}</i>"
        )
    text += f"\n\n{_SEP}\n💬 <i>Reply to this message with your answer</i>"

    msg = await bot.send_message(
        settings.OWNER_CHAT_ID,
        text,
        parse_mode="HTML",
        reply_markup=_keyboard(question.id),
    )
    question.telegram_message_id = msg.message_id
    store.message_to_question[msg.message_id] = question.id


# ── Receive answers ───────────────────────────────────────────────────────────

@dp.message(F.reply_to_message)
async def handle_reply(message: types.Message):
    if message.from_user.id != settings.OWNER_CHAT_ID:
        return
    replied_id = message.reply_to_message.message_id
    q_id = store.message_to_question.get(replied_id)
    if not q_id:
        return

    answer_text = (message.text or message.caption or "").strip()
    if not answer_text:
        await message.reply("⚠️ Empty reply — not recorded.")
        return

    q = store.answer_question(q_id, answer_text)
    if q:
        await message.reply(
            f"✅ <b>Recorded</b> for <code>{q.id}</code>:\n"
            f"<i>{html_module.escape(answer_text)}</i>",
            parse_mode="HTML",
        )
    else:
        await message.reply("⚠️ Already answered or cancelled.")


@dp.callback_query(F.data.startswith("a:"))
async def handle_callback(callback: types.CallbackQuery):
    if callback.from_user.id != settings.OWNER_CHAT_ID:
        await callback.answer("Unauthorized", show_alert=True)
        return

    parts = callback.data.split(":", 2)
    if len(parts) != 3:
        await callback.answer("Bad data")
        return

    _, q_id, answer = parts

    if answer == "cancel":
        q = store.cancel_question(q_id)
        label = f"🚫 Cancelled — <code>{q_id}</code>"
    else:
        q = store.answer_question(q_id, answer)
        label = f"✅ Answered <b>{html_module.escape(answer)}</b> — <code>{q_id}</code>"

    if q:
        await callback.answer(f"Recorded: {answer}")
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.reply(label, parse_mode="HTML")
    else:
        await callback.answer("Already answered or not found", show_alert=True)


# ── Entry point ───────────────────────────────────────────────────────────────

async def start_polling() -> None:
    await dp.start_polling(bot, allowed_updates=["message", "callback_query"])
