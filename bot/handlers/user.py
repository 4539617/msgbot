from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from bot.keyboards import (
    main_menu_kb,
    transport_kb,
    reason_kb,
    skip_media_kb,
    confirm_kb,
    remove_kb,
)
from bot import database as db
from bot.config import ADMIN_IDS

router = Router()

MAX_MEDIA = 5  # максимум файлов в одной заявке


# ── FSM состояния ─────────────────────────────────────────────────────────────
class RequestFSM(StatesGroup):
    transport = State()
    reason = State()
    description = State()
    media = State()
    confirm = State()


# ── /start ────────────────────────────────────────────────────────────────────
@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "👋 Привет! Я бот для приёма заявок на <b>ремонт батареи / замену BMS</b> "
        "электротранспорта.\n\nНажми кнопку ниже, чтобы подать заявку.",
        reply_markup=main_menu_kb(),
        parse_mode="HTML",
    )


# ── Начало заявки ─────────────────────────────────────────────────────────────
@router.message(F.text == "📋 Подать заявку")
async def start_request(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(RequestFSM.transport)
    await message.answer(
        "🚗 <b>Шаг 1 из 4.</b> Выберите тип транспорта:",
        reply_markup=transport_kb(),
        parse_mode="HTML",
    )


# ── Шаг 1: транспорт ─────────────────────────────────────────────────────────
@router.callback_query(RequestFSM.transport, F.data.startswith("transport:"))
async def step_transport(callback: CallbackQuery, state: FSMContext) -> None:
    transport = callback.data.split(":", 1)[1]  # type: ignore[union-attr]
    await state.update_data(transport=transport)
    await callback.message.edit_text(  # type: ignore[union-attr]
        f"✅ Тип транспорта: <b>{transport}</b>\n\n"
        "🔧 <b>Шаг 2 из 4.</b> Выберите причину обращения:",
        reply_markup=reason_kb(),
        parse_mode="HTML",
    )
    await state.set_state(RequestFSM.reason)
    await callback.answer()


# ── Шаг 2: причина ───────────────────────────────────────────────────────────
@router.callback_query(RequestFSM.reason, F.data.startswith("reason:"))
async def step_reason(callback: CallbackQuery, state: FSMContext) -> None:
    reason = callback.data.split(":", 1)[1]  # type: ignore[union-attr]
    await state.update_data(reason=reason)
    await callback.message.edit_text(  # type: ignore[union-attr]
        f"✅ Причина: <b>{reason}</b>\n\n"
        "📝 <b>Шаг 3 из 4.</b> Опишите проблему подробнее (текстом):",
        parse_mode="HTML",
        reply_markup=None,
    )
    await state.set_state(RequestFSM.description)
    await callback.answer()


# ── Шаг 3: описание ──────────────────────────────────────────────────────────
@router.message(RequestFSM.description, F.text)
async def step_description(message: Message, state: FSMContext) -> None:
    await state.update_data(description=message.text, media_ids=[])
    await state.set_state(RequestFSM.media)
    await message.answer(
        "📷 <b>Шаг 4 из 4.</b> Прикрепите фото или видео (до 5 файлов).\n"
        "Отправляйте по одному. Когда закончите — нажмите <b>«Пропустить»</b> "
        "или просто нажмите «Пропустить», если медиа не нужно.",
        reply_markup=skip_media_kb(),
        parse_mode="HTML",
    )


# ── Шаг 4: медиа (фото) ──────────────────────────────────────────────────────
@router.message(RequestFSM.media, F.photo)
async def step_photo(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    media_ids: list = data.get("media_ids", [])
    if len(media_ids) >= MAX_MEDIA:
        await message.answer(f"⚠️ Максимум {MAX_MEDIA} файлов. Нажмите «Пропустить» для продолжения.")
        return
    file_id = message.photo[-1].file_id  # type: ignore[index]
    media_ids.append(f"photo:{file_id}")
    await state.update_data(media_ids=media_ids)
    remaining = MAX_MEDIA - len(media_ids)
    await message.answer(
        f"✅ Фото добавлено ({len(media_ids)}/{MAX_MEDIA}). "
        + (f"Можете добавить ещё {remaining}." if remaining else "Лимит достигнут."),
        reply_markup=skip_media_kb(),
    )


# ── Шаг 4: медиа (видео) ─────────────────────────────────────────────────────
@router.message(RequestFSM.media, F.video)
async def step_video(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    media_ids: list = data.get("media_ids", [])
    if len(media_ids) >= MAX_MEDIA:
        await message.answer(f"⚠️ Максимум {MAX_MEDIA} файлов. Нажмите «Пропустить» для продолжения.")
        return
    file_id = message.video.file_id  # type: ignore[union-attr]
    media_ids.append(f"video:{file_id}")
    await state.update_data(media_ids=media_ids)
    remaining = MAX_MEDIA - len(media_ids)
    await message.answer(
        f"✅ Видео добавлено ({len(media_ids)}/{MAX_MEDIA}). "
        + (f"Можете добавить ещё {remaining}." if remaining else "Лимит достигнут."),
        reply_markup=skip_media_kb(),
    )


# ── Шаг 4: пропустить медиа ──────────────────────────────────────────────────
@router.callback_query(RequestFSM.media, F.data == "skip_media")
async def step_skip_media(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    media_count = len(data.get("media_ids", []))
    media_note = f"📎 Медиафайлов: <b>{media_count}</b>" if media_count else "📎 Медиа: <i>не прикреплено</i>"

    text = (
        "📋 <b>Ваша заявка:</b>\n\n"
        f"🚗 Транспорт: <b>{data['transport']}</b>\n"
        f"🔧 Причина: <b>{data['reason']}</b>\n"
        f"📝 Описание: {data['description']}\n"
        f"{media_note}\n\n"
        "Всё верно? Отправить заявку?"
    )
    await callback.message.edit_text(  # type: ignore[union-attr]
        text, reply_markup=confirm_kb(), parse_mode="HTML"
    )
    await state.set_state(RequestFSM.confirm)
    await callback.answer()


# ── Подтверждение ─────────────────────────────────────────────────────────────
@router.callback_query(RequestFSM.confirm, F.data == "confirm_yes")
async def confirm_yes(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    user = callback.from_user  # type: ignore[union-attr]

    media_ids_str = ",".join(data.get("media_ids", []))
    request_id = await db.create_request(
        user_id=user.id,
        username=user.username,
        full_name=user.full_name,
        transport=data["transport"],
        reason=data["reason"],
        description=data["description"],
        media_ids=media_ids_str,
    )

    await callback.message.edit_text(  # type: ignore[union-attr]
        f"✅ <b>Заявка #{request_id} принята!</b>\n\n"
        "Мы свяжемся с вами в ближайшее время. Спасибо! 🙏",
        parse_mode="HTML",
        reply_markup=None,
    )
    await state.clear()
    await callback.answer("Заявка отправлена!")

    # Уведомить всех администраторов
    from bot.keyboards import admin_request_kb
    bot = callback.bot  # type: ignore[union-attr]
    media_ids_list: list[str] = [m for m in media_ids_str.split(",") if m]

    media_note = f"📎 Медиафайлов: <b>{len(media_ids_list)}</b>" if media_ids_list else "📎 Медиа: <i>не прикреплено</i>"
    username_str = f"@{user.username}" if user.username else "—"

    admin_text = (
        f"🆕 <b>Новая заявка #{request_id}</b>\n\n"
        f"👤 Клиент: <b>{user.full_name}</b> ({username_str})\n"
        f"🆔 ID: <code>{user.id}</code>\n"
        f"🚗 Транспорт: <b>{data['transport']}</b>\n"
        f"🔧 Причина: <b>{data['reason']}</b>\n"
        f"📝 Описание: {data['description']}\n"
        f"{media_note}"
    )

    for admin_id in ADMIN_IDS:
        try:
            # Отправить текст заявки
            await bot.send_message(
                admin_id, admin_text,
                parse_mode="HTML",
                reply_markup=admin_request_kb(request_id),
            )
            # Отправить медиа если есть
            for item in media_ids_list:
                kind, fid = item.split(":", 1)
                if kind == "photo":
                    await bot.send_photo(admin_id, fid, caption=f"📷 Фото к заявке #{request_id}")
                elif kind == "video":
                    await bot.send_video(admin_id, fid, caption=f"🎥 Видео к заявке #{request_id}")
        except Exception:
            pass


@router.callback_query(RequestFSM.confirm, F.data == "confirm_no")
async def confirm_no(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text(  # type: ignore[union-attr]
        "🗑 Заявка отменена. Вы можете подать новую в любой момент.",
        reply_markup=None,
    )
    await callback.answer("Отменено")
