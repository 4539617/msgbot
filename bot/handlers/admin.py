from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from bot.config import ADMIN_IDS
from bot import database as db
from bot.keyboards import admin_request_kb, admin_list_kb

router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# ── FSM: ожидание текста ответа ───────────────────────────────────────────────
class AdminReplyFSM(StatesGroup):
    waiting_reply = State()


# ── /admin — справка ──────────────────────────────────────────────────────────
@router.message(Command("admin"))
async def cmd_admin(message: Message) -> None:
    if not is_admin(message.from_user.id):  # type: ignore[union-attr]
        return
    await message.answer(
        "🛠 <b>Панель администратора</b>\n\n"
        "/list — все заявки\n"
        "/new — новые заявки\n"
        "/inwork — заявки в работе\n"
        "/stats — статистика",
        parse_mode="HTML",
    )


# ── /list — все заявки ────────────────────────────────────────────────────────
@router.message(Command("list"))
async def cmd_list(message: Message) -> None:
    if not is_admin(message.from_user.id):  # type: ignore[union-attr]
        return
    requests = await db.get_all_requests()
    if not requests:
        await message.answer("📭 Заявок пока нет.")
        return
    await message.answer(
        f"📋 <b>Все заявки ({len(requests)}):</b>",
        reply_markup=admin_list_kb(requests),
        parse_mode="HTML",
    )


# ── /new — только новые ───────────────────────────────────────────────────────
@router.message(Command("new"))
async def cmd_new(message: Message) -> None:
    if not is_admin(message.from_user.id):  # type: ignore[union-attr]
        return
    requests = await db.get_all_requests(status="new")
    if not requests:
        await message.answer("✅ Новых заявок нет.")
        return
    await message.answer(
        f"🆕 <b>Новые заявки ({len(requests)}):</b>",
        reply_markup=admin_list_kb(requests),
        parse_mode="HTML",
    )


# ── /inwork — в работе ────────────────────────────────────────────────────────
@router.message(Command("inwork"))
async def cmd_inwork(message: Message) -> None:
    if not is_admin(message.from_user.id):  # type: ignore[union-attr]
        return
    requests = await db.get_all_requests(status="in_work")
    if not requests:
        await message.answer("📭 Заявок в работе нет.")
        return
    await message.answer(
        f"🔧 <b>В работе ({len(requests)}):</b>",
        reply_markup=admin_list_kb(requests),
        parse_mode="HTML",
    )


# ── /stats — статистика ───────────────────────────────────────────────────────
@router.message(Command("stats"))
async def cmd_stats(message: Message) -> None:
    if not is_admin(message.from_user.id):  # type: ignore[union-attr]
        return
    all_req = await db.get_all_requests()
    counts = {"new": 0, "in_work": 0, "answered": 0, "closed": 0}
    for r in all_req:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    await message.answer(
        f"📊 <b>Статистика заявок:</b>\n\n"
        f"🆕 Новых: <b>{counts['new']}</b>\n"
        f"🔧 В работе: <b>{counts['in_work']}</b>\n"
        f"💬 Отвечено: <b>{counts['answered']}</b>\n"
        f"✅ Закрыто: <b>{counts['closed']}</b>\n"
        f"📋 Всего: <b>{len(all_req)}</b>",
        parse_mode="HTML",
    )


# ── Открыть заявку ────────────────────────────────────────────────────────────
@router.callback_query(F.data.startswith("admin_open:"))
async def admin_open(callback: CallbackQuery) -> None:
    if not is_admin(callback.from_user.id):  # type: ignore[union-attr]
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    request_id = int(callback.data.split(":")[1])  # type: ignore[union-attr]
    req = await db.get_request(request_id)
    if not req:
        await callback.answer("❌ Заявка не найдена", show_alert=True)
        return

    status_map = {"new": "🆕 Новая", "in_work": "🔧 В работе", "answered": "💬 Отвечено", "closed": "✅ Закрыта"}
    status_str = status_map.get(req["status"], req["status"])
    username_str = f"@{req['username']}" if req["username"] else "—"
    reply_str = f"\n\n💬 <b>Ответ администратора:</b>\n{req['admin_reply']}" if req.get("admin_reply") else ""

    media_ids_list = [m for m in (req["media_ids"] or "").split(",") if m]
    media_note = f"📎 Медиафайлов: <b>{len(media_ids_list)}</b>" if media_ids_list else "📎 Медиа: <i>не прикреплено</i>"

    text = (
        f"📋 <b>Заявка #{req['id']}</b>  {status_str}\n\n"
        f"👤 Клиент: <b>{req['full_name']}</b> ({username_str})\n"
        f"🆔 ID: <code>{req['user_id']}</code>\n"
        f"📅 Дата: {req['created_at']}\n"
        f"🚗 Транспорт: <b>{req['transport']}</b>\n"
        f"🔧 Причина: <b>{req['reason']}</b>\n"
        f"📝 Описание: {req['description']}\n"
        f"{media_note}"
        f"{reply_str}"
    )
    await callback.message.answer(  # type: ignore[union-attr]
        text,
        reply_markup=admin_request_kb(request_id),
        parse_mode="HTML",
    )
    await callback.answer()


# ── Изменить статус ───────────────────────────────────────────────────────────
@router.callback_query(F.data.startswith("admin_status:"))
async def admin_status(callback: CallbackQuery) -> None:
    if not is_admin(callback.from_user.id):  # type: ignore[union-attr]
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    _, new_status, request_id_str = callback.data.split(":")  # type: ignore[union-attr]
    request_id = int(request_id_str)
    await db.set_status(request_id, new_status)

    status_labels = {"in_work": "🔧 Принято в работу", "closed": "✅ Закрыто"}
    label = status_labels.get(new_status, new_status)
    await callback.answer(f"{label}", show_alert=True)

    # Уведомить клиента
    req = await db.get_request(request_id)
    if req:
        try:
            msg_map = {
                "in_work": f"🔧 Ваша заявка <b>#{request_id}</b> принята в работу! Скоро свяжемся.",
                "closed": f"✅ Ваша заявка <b>#{request_id}</b> закрыта. Спасибо!",
            }
            if new_status in msg_map:
                await callback.bot.send_message(  # type: ignore[union-attr]
                    req["user_id"], msg_map[new_status], parse_mode="HTML"
                )
        except Exception:
            pass


# ── Начать ответ администратора ───────────────────────────────────────────────
@router.callback_query(F.data.startswith("admin_reply:"))
async def admin_reply_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(callback.from_user.id):  # type: ignore[union-attr]
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    request_id = int(callback.data.split(":")[1])  # type: ignore[union-attr]
    await state.set_state(AdminReplyFSM.waiting_reply)
    await state.update_data(reply_request_id=request_id)
    await callback.message.answer(  # type: ignore[union-attr]
        f"✏️ Введите ответ для заявки <b>#{request_id}</b>:\n"
        "(отправьте сообщение — оно будет переслано клиенту)",
        parse_mode="HTML",
    )
    await callback.answer()


# ── Получить и отправить ответ ────────────────────────────────────────────────
@router.message(AdminReplyFSM.waiting_reply, F.text)
async def admin_reply_send(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):  # type: ignore[union-attr]
        return
    data = await state.get_data()
    request_id: int = data["reply_request_id"]
    reply_text = message.text  # type: ignore[assignment]

    await db.set_reply(request_id, reply_text)  # type: ignore[arg-type]

    req = await db.get_request(request_id)
    if req:
        try:
            await message.bot.send_message(  # type: ignore[union-attr]
                req["user_id"],
                f"💬 <b>Ответ по вашей заявке #{request_id}:</b>\n\n{reply_text}",
                parse_mode="HTML",
            )
            await message.answer(f"✅ Ответ отправлен клиенту (заявка #{request_id}).")
        except Exception:
            await message.answer(
                f"⚠️ Ответ сохранён, но не удалось доставить клиенту "
                f"(возможно, заблокировал бота)."
            )
    else:
        await message.answer("❌ Заявка не найдена.")

    await state.clear()
