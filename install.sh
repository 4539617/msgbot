#!/bin/bash
set -e

# ─── Цвета ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

# ─── Константы ────────────────────────────────────────────────────────────────
WORK_DIR="/opt/msgbot"
LOG_FILE="/var/log/msgbot_install.log"
REPO_URL="https://github.com/4539617/msgbot.git"
PYTHON_MIN="3.10"
SERVICE_NAME="msgbot"

# ─── Логирование ──────────────────────────────────────────────────────────────
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG_FILE"
}

step() {
    echo -e "${BLUE}▶ $*${NC}"
    log "STEP: $*"
}

ok() {
    echo -e "${GREEN}✅ $*${NC}"
    log "OK: $*"
}

warn() {
    echo -e "${YELLOW}⚠️  $*${NC}"
    log "WARN: $*"
}

fail() {
    echo -e "${RED}❌ $*${NC}"
    log "FAIL: $*"
    exit 1
}

# ─── Шапка ───────────────────────────────────────────────────────────────────
clear
echo -e "${BLUE}${BOLD}"
echo "╔══════════════════════════════════════════╗"
echo "║         msgbot — Installer v1.0          ║"
echo "║  Бот приёма заявок на ремонт батарей     ║"
echo "╚══════════════════════════════════════════╝"
echo -e "${NC}"
echo -e "${YELLOW}Лог установки: ${LOG_FILE}${NC}\n"

# ─── Проверка root ────────────────────────────────────────────────────────────
if [ "$EUID" -ne 0 ]; then
    fail "Запустите с правами root: sudo bash install.sh"
fi

# ─── Инициализация лог-файла ──────────────────────────────────────────────────
mkdir -p "$(dirname "$LOG_FILE")"
echo "=== msgbot install log $(date) ===" > "$LOG_FILE"

# ─── 1. Системные пакеты ─────────────────────────────────────────────────────
echo -e "\n${BLUE}════════════════════════════════════════${NC}"
echo -e "${BLUE}   Шаг 1 / 5 — Системные пакеты        ${NC}"
echo -e "${BLUE}════════════════════════════════════════${NC}\n"

step "Обновление списка пакетов..."
apt-get update -qq >> "$LOG_FILE" 2>&1
ok "Список пакетов обновлён"

for pkg in python3 python3-pip python3-venv git curl; do
    if dpkg -s "$pkg" &>/dev/null; then
        ok "$pkg уже установлен"
    else
        step "Установка $pkg..."
        apt-get install -y "$pkg" >> "$LOG_FILE" 2>&1
        ok "$pkg установлен"
    fi
done

# ─── 2. Проверка версии Python ────────────────────────────────────────────────
echo -e "\n${BLUE}════════════════════════════════════════${NC}"
echo -e "${BLUE}   Шаг 2 / 5 — Проверка Python         ${NC}"
echo -e "${BLUE}════════════════════════════════════════${NC}\n"

PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)

step "Обнаружен Python ${PYTHON_VERSION}"

if [ "$PYTHON_MAJOR" -lt 3 ] || { [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 10 ]; }; then
    fail "Требуется Python ${PYTHON_MIN}+. Установлен: ${PYTHON_VERSION}"
fi

ok "Python ${PYTHON_VERSION} — подходит"

# ─── 3. Скачивание / обновление кода ─────────────────────────────────────────
echo -e "\n${BLUE}════════════════════════════════════════${NC}"
echo -e "${BLUE}   Шаг 3 / 5 — Код бота                ${NC}"
echo -e "${BLUE}════════════════════════════════════════${NC}\n"

if [ -d "$WORK_DIR/.git" ]; then
    step "Репозиторий уже существует, обновляем..."
    cd "$WORK_DIR"
    git pull origin main >> "$LOG_FILE" 2>&1
    ok "Код обновлён"
else
    step "Клонирование репозитория в ${WORK_DIR}..."
    git clone "$REPO_URL" "$WORK_DIR" >> "$LOG_FILE" 2>&1
    ok "Репозиторий клонирован"
fi

cd "$WORK_DIR"

# ─── 4. Виртуальное окружение и зависимости ──────────────────────────────────
echo -e "\n${BLUE}════════════════════════════════════════${NC}"
echo -e "${BLUE}   Шаг 4 / 5 — Python-окружение        ${NC}"
echo -e "${BLUE}════════════════════════════════════════${NC}\n"

if [ ! -d "$WORK_DIR/venv" ]; then
    step "Создание виртуального окружения..."
    python3 -m venv venv >> "$LOG_FILE" 2>&1
    ok "Виртуальное окружение создано"
else
    ok "Виртуальное окружение уже существует"
fi

step "Установка зависимостей из requirements.txt..."
venv/bin/pip install --upgrade pip -q >> "$LOG_FILE" 2>&1
venv/bin/pip install -r requirements.txt -q >> "$LOG_FILE" 2>&1
ok "Зависимости установлены"

# ─── 5. Настройка .env ───────────────────────────────────────────────────────
echo -e "\n${BLUE}════════════════════════════════════════${NC}"
echo -e "${BLUE}   Шаг 5 / 5 — Настройка бота          ${NC}"
echo -e "${BLUE}════════════════════════════════════════${NC}\n"

ENV_FILE="$WORK_DIR/.env"

if [ -f "$ENV_FILE" ]; then
    warn ".env уже существует"
    read -p "Перенастроить параметры заново? [y/N]: " RECONFIGURE
    if [[ "$RECONFIGURE" != "y" && "$RECONFIGURE" != "Y" ]]; then
        echo -e "${YELLOW}Пропускаем настройку .env${NC}"
        SKIP_ENV=1
    fi
fi

if [ -z "$SKIP_ENV" ]; then
    echo -e "${GREEN}📱 Введите параметры бота:${NC}\n"

    # BOT_TOKEN
    while true; do
        read -p "  BOT_TOKEN (от @BotFather): " BOT_TOKEN
        if [[ "$BOT_TOKEN" =~ ^[0-9]+:[A-Za-z0-9_-]{35}$ ]]; then
            ok "Токен выглядит корректно"
            break
        else
            warn "Токен не похож на Telegram Bot Token, попробуйте снова"
        fi
    done

    # ADMIN_IDS
    echo -e "\n  ${YELLOW}Узнать свой Telegram ID → @userinfobot${NC}"
    read -p "  ADMIN_IDS (один или несколько через запятую): " ADMIN_IDS
    if [ -z "$ADMIN_IDS" ]; then
        fail "ADMIN_IDS не может быть пустым"
    fi

    # Сохранить .env
    cat > "$ENV_FILE" <<EOF
BOT_TOKEN=${BOT_TOKEN}
ADMIN_IDS=${ADMIN_IDS}
EOF
    chmod 600 "$ENV_FILE"
    ok ".env создан и защищён (chmod 600)"
fi

# ─── Systemd сервис ───────────────────────────────────────────────────────────
echo -e "\n${BLUE}⚙️  Настройка автозапуска (systemd)...${NC}"

cat > "/etc/systemd/system/${SERVICE_NAME}.service" <<EOF
[Unit]
Description=msgbot — бот приёма заявок на ремонт батарей
After=network.target

[Service]
Type=simple
WorkingDirectory=${WORK_DIR}
ExecStart=${WORK_DIR}/venv/bin/python main.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload >> "$LOG_FILE" 2>&1
systemctl enable "$SERVICE_NAME" >> "$LOG_FILE" 2>&1
ok "Сервис ${SERVICE_NAME} добавлен в автозапуск"

# ─── Запуск ───────────────────────────────────────────────────────────────────
step "Запуск бота..."
systemctl restart "$SERVICE_NAME" >> "$LOG_FILE" 2>&1
sleep 2

if systemctl is-active --quiet "$SERVICE_NAME"; then
    ok "Бот запущен и работает"
else
    warn "Бот не запустился, проверьте логи:"
    echo -e "${YELLOW}  journalctl -u ${SERVICE_NAME} -n 30${NC}"
fi

# ─── Итог ─────────────────────────────────────────────────────────────────────
echo -e "\n${GREEN}${BOLD}"
echo "╔══════════════════════════════════════════╗"
echo "║          Установка завершена! 🎉         ║"
echo "╚══════════════════════════════════════════╝"
echo -e "${NC}"
echo -e "  📁 Директория:  ${BLUE}${WORK_DIR}${NC}"
echo -e "  📋 Лог установки: ${BLUE}${LOG_FILE}${NC}"
echo -e "  📋 Лог бота:    ${BLUE}journalctl -u ${SERVICE_NAME} -f${NC}"
echo -e "  🔁 Перезапуск:  ${BLUE}systemctl restart ${SERVICE_NAME}${NC}"
echo -e "  ⏹  Остановка:   ${BLUE}systemctl stop ${SERVICE_NAME}${NC}"
echo -e "  📊 Статус:      ${BLUE}systemctl status ${SERVICE_NAME}${NC}"
echo ""
