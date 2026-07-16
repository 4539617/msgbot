from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

# ── Убрать клавиатуру ────────────────────────────────────────────────────────
remove_kb = ReplyKeyboardRemove()


# ── Главное меню пользователя ────────────────────────────────────────────────
def main_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📋 Подать заявку")],
            [KeyboardButton(text="📂 Мои заявки")],
        ],
        resize_keyboard=True,
    )


# ── Выбор типа транспорта ────────────────────────────────────────────────────
TRANSPORT_OPTIONS = [
    "🛴 Электросамокат",
    "🚲 Электровелосипед",
    "🛵 Электромопед / скутер",
]


def transport_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for opt in TRANSPORT_OPTIONS:
        builder.button(text=opt, callback_data=f"transport:{opt}")
    builder.adjust(1)
    return builder.as_markup()


# ── Причина поломки ──────────────────────────────────────────────────────────
REASON_OPTIONS = [
    "💧 Попала вода",
    "❌ Не включается",
    "⚡ Переразряд",
    "🔌 Не заряжается",
    "🔧 Замена BMS",
]


def reason_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for opt in REASON_OPTIONS:
        builder.button(text=opt, callback_data=f"reason:{opt}")
    builder.adjust(1)
    return builder.as_markup()


# ── Пропустить медиа ─────────────────────────────────────────────────────────
def skip_media_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⏭ Пропустить", callback_data="skip_media")]
        ]
    )


# ── Подтверждение заявки ─────────────────────────────────────────────────────
def confirm_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Отправить", callback_data="confirm_yes"),
                InlineKeyboardButton(text="🗑 Отменить", callback_data="confirm_no"),
            ]
        ]
    )


# ── Панель администратора для заявки ────────────────────────────────────────
def admin_request_kb(request_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💬 Ответить", callback_data=f"admin_reply:{request_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="✅ Принять в работу", callback_data=f"admin_status:in_work:{request_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🏁 Закрыть заявку", callback_data=f"admin_status:closed:{request_id}"
                )
            ],
        ]
    )


# ── Список заявок пользователя ───────────────────────────────────────────────
STATUS_ICONS = {"new": "🆕", "in_work": "🔧", "answered": "💬", "closed": "✅"}
STATUS_LABELS = {"new": "Новая", "in_work": "В работе", "answered": "Отвечено", "closed": "Закрыта"}

def user_requests_kb(requests: list[dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for r in requests:
        icon = STATUS_ICONS.get(r["status"], "❓")
        label = f"{icon} #{r['id']} — {r['transport'][:15]} | {r['created_at']}"
        builder.button(text=label, callback_data=f"my_request:{r['id']}")
    builder.adjust(1)
    return builder.as_markup()


# ── Список заявок для admin /list ────────────────────────────────────────────
def admin_list_kb(requests: list[dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    status_icons = {"new": "🆕", "in_work": "🔧", "answered": "💬", "closed": "✅"}
    for r in requests:
        icon = status_icons.get(r["status"], "❓")
        label = f"{icon} #{r['id']} — {r['transport']} | {r['created_at']}"
        builder.button(text=label, callback_data=f"admin_open:{r['id']}")
    builder.adjust(1)
    return builder.as_markup()
