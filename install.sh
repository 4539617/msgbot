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
CONTAINER_NAME="msgbot"
COMPOSE_FILE="docker-compose.yml"

# ─── Логирование ──────────────────────────────────────────────────────────────
log()  { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG_FILE"; }
step() { echo -e "${BLUE}▶ $*${NC}";  log "STEP: $*"; }
ok()   { echo -e "${GREEN}✅ $*${NC}"; log "OK:   $*"; }
warn() { echo -e "${YELLOW}⚠️  $*${NC}"; log "WARN: $*"; }
fail() { echo -e "${RED}❌ $*${NC}";  log "FAIL: $*"; exit 1; }

# ─── Инициализация ────────────────────────────────────────────────────────────
mkdir -p "$(dirname "$LOG_FILE")"
touch "$LOG_FILE"

# ─── Проверка root ────────────────────────────────────────────────────────────
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}❌ Запустите с правами root: sudo bash install.sh${NC}"
    exit 1
fi

# ─── Шапка ───────────────────────────────────────────────────────────────────
print_header() {
    clear
    echo -e "${BLUE}${BOLD}"
    echo "╔══════════════════════════════════════════╗"
    echo "║         msgbot — Manager v1.0            ║"
    echo "║  Бот приёма заявок на ремонт батарей     ║"
    echo "╚══════════════════════════════════════════╝"
    echo -e "${NC}"
}

# ─── Установка Docker ─────────────────────────────────────────────────────────
install_docker() {
    if ! command -v docker &>/dev/null; then
        step "Установка Docker..."
        curl -fsSL https://get.docker.com -o /tmp/get-docker.sh >> "$LOG_FILE" 2>&1
        sh /tmp/get-docker.sh >> "$LOG_FILE" 2>&1
        rm /tmp/get-docker.sh
        systemctl enable docker >> "$LOG_FILE" 2>&1
        systemctl start docker  >> "$LOG_FILE" 2>&1
        ok "Docker установлен"
    else
        ok "Docker уже установлен ($(docker --version | cut -d' ' -f3 | tr -d ','))"
    fi

    if ! systemctl is-active --quiet docker; then
        step "Запуск Docker..."
        systemctl start docker >> "$LOG_FILE" 2>&1
        ok "Docker запущен"
    fi

    # Определяем команду docker compose
    if docker compose version &>/dev/null 2>&1; then
        DOCKER_COMPOSE_CMD="docker compose"
    elif command -v docker-compose &>/dev/null; then
        DOCKER_COMPOSE_CMD="docker-compose"
    else
        step "Установка Docker Compose plugin..."
        apt-get install -y -qq docker-compose-plugin >> "$LOG_FILE" 2>&1
        DOCKER_COMPOSE_CMD="docker compose"
        ok "Docker Compose установлен"
    fi
    export DOCKER_COMPOSE_CMD
}

# ─── Установка Git и curl ─────────────────────────────────────────────────────
install_deps() {
    for pkg in git curl; do
        if ! command -v "$pkg" &>/dev/null; then
            step "Установка $pkg..."
            apt-get update -qq >> "$LOG_FILE" 2>&1
            apt-get install -y -qq "$pkg" >> "$LOG_FILE" 2>&1
            ok "$pkg установлен"
        fi
    done
}

# ─── Синхронизация репозитория ────────────────────────────────────────────────
sync_repo() {
    if [ -d "$WORK_DIR/.git" ]; then
        step "Обновление репозитория..."
        cd "$WORK_DIR"
        BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "main")
        git fetch origin >> "$LOG_FILE" 2>&1
        git reset --hard "origin/${BRANCH}" >> "$LOG_FILE" 2>&1
        ok "Репозиторий обновлён (ветка: ${BRANCH})"
    else
        step "Клонирование репозитория в ${WORK_DIR}..."
        git clone "$REPO_URL" "$WORK_DIR" >> "$LOG_FILE" 2>&1
        ok "Репозиторий клонирован"
    fi
    cd "$WORK_DIR"
}

# ─── Настройка .env ───────────────────────────────────────────────────────────
setup_env() {
    ENV_FILE="$WORK_DIR/.env"

    if [ -f "$ENV_FILE" ]; then
        warn ".env уже существует"
        read -p "  Перенастроить параметры заново? [y/N]: " RECONFIGURE
        if [[ "$RECONFIGURE" != "y" && "$RECONFIGURE" != "Y" ]]; then
            echo -e "${YELLOW}  Пропускаем настройку .env${NC}"
            return 0
        fi
    fi

    echo -e "\n${GREEN}📱 Введите параметры бота:${NC}\n"

    while true; do
        read -p "  BOT_TOKEN (от @BotFather): " BOT_TOKEN
        if [[ "$BOT_TOKEN" =~ ^[0-9]+:[A-Za-z0-9_-]{35}$ ]]; then
            ok "Токен корректный"
            break
        else
            warn "Неверный формат токена, попробуйте снова"
        fi
    done

    echo -e "\n  ${YELLOW}Узнать свой Telegram ID → @userinfobot${NC}"
    read -p "  ADMIN_IDS (через запятую для нескольких): " ADMIN_IDS
    [ -z "$ADMIN_IDS" ] && fail "ADMIN_IDS не может быть пустым"

    cat > "$ENV_FILE" <<EOF
BOT_TOKEN=${BOT_TOKEN}
ADMIN_IDS=${ADMIN_IDS}
DATA_DIR=/app/data
EOF
    chmod 600 "$ENV_FILE"
    ok ".env создан (chmod 600)"
}

# ─── 1. Установка ─────────────────────────────────────────────────────────────
install_bot() {
    echo -e "\n${BLUE}════════════════════════════════════════${NC}"
    echo -e "${BLUE}   Установка msgbot                     ${NC}"
    echo -e "${BLUE}════════════════════════════════════════${NC}\n"

    install_deps
    sync_repo
    setup_env

    cd "$WORK_DIR"

    step "Остановка старых контейнеров (если есть)..."
    $DOCKER_COMPOSE_CMD -f "$COMPOSE_FILE" down >> "$LOG_FILE" 2>&1 || true

    step "Сборка и запуск контейнера..."
    echo -e "${YELLOW}  Это может занять несколько минут...${NC}"

    if ! $DOCKER_COMPOSE_CMD -f "$COMPOSE_FILE" up -d --build >> "$LOG_FILE" 2>&1; then
        echo -e "${RED}❌ Ошибка при запуске. Логи:${NC}"
        $DOCKER_COMPOSE_CMD -f "$COMPOSE_FILE" logs --tail=30
        exit 1
    fi

    sleep 3

    STATUS=$(docker ps --filter "name=${CONTAINER_NAME}" --format "{{.Status}}" 2>/dev/null || echo "")

    echo -e "\n${GREEN}✅ msgbot установлен!${NC}"
    echo -e "${BLUE}════════════════════════════════════════${NC}"
    if [[ "$STATUS" == *"Up"* ]]; then
        echo -e "  Контейнер: ${GREEN}✓ Работает${NC} ($STATUS)"
    else
        echo -e "  Контейнер: ${RED}✗ Не запущен${NC} ($STATUS)"
    fi
    echo -e "${BLUE}════════════════════════════════════════${NC}"

    echo -e "\n${YELLOW}📋 Последние логи:${NC}"
    docker logs --tail=20 "$CONTAINER_NAME" 2>&1 || true

    echo -e "\n${GREEN}💡 Полезные команды:${NC}"
    echo -e "  Логи:       ${YELLOW}docker logs -f ${CONTAINER_NAME}${NC}"
    echo -e "  Статус:     ${YELLOW}docker ps${NC}"
    echo -e "  Перезапуск: ${YELLOW}$DOCKER_COMPOSE_CMD -f ${WORK_DIR}/${COMPOSE_FILE} restart${NC}"

    read -p $'\nНажмите Enter для возврата в меню...'
}

# ─── 2. Логи ──────────────────────────────────────────────────────────────────
show_logs() {
    echo -e "\n${BLUE}════════════════════════════════════════${NC}"
    echo -e "${BLUE}   Логи msgbot (последние 50 строк)     ${NC}"
    echo -e "${BLUE}════════════════════════════════════════${NC}\n"

    docker logs --tail=50 "$CONTAINER_NAME" 2>/dev/null \
        || echo -e "${RED}Контейнер ${CONTAINER_NAME} не запущен${NC}"

    echo -e "\n${YELLOW}Для слежения в реальном времени:${NC}"
    echo -e "  ${BLUE}docker logs -f ${CONTAINER_NAME}${NC}"

    read -p $'\nНажмите Enter для возврата в меню...'
}

# ─── 3. Пересборка ────────────────────────────────────────────────────────────
rebuild_bot() {
    echo -e "\n${BLUE}════════════════════════════════════════${NC}"
    echo -e "${BLUE}   Пересборка msgbot                    ${NC}"
    echo -e "${BLUE}════════════════════════════════════════${NC}\n"

    cd "$WORK_DIR" 2>/dev/null || fail "Директория ${WORK_DIR} не найдена. Сначала установите бота."

    step "Обновление кода из репозитория..."
    BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "main")
    git fetch origin >> "$LOG_FILE" 2>&1
    git reset --hard "origin/${BRANCH}" >> "$LOG_FILE" 2>&1
    ok "Код обновлён (ветка: ${BRANCH})"

    step "Остановка контейнера..."
    $DOCKER_COMPOSE_CMD -f "$COMPOSE_FILE" down >> "$LOG_FILE" 2>&1

    step "Пересборка образа..."
    echo -e "${YELLOW}  Это может занять несколько минут...${NC}"

    if ! $DOCKER_COMPOSE_CMD -f "$COMPOSE_FILE" up -d --build >> "$LOG_FILE" 2>&1; then
        echo -e "${RED}❌ Ошибка при пересборке. Логи:${NC}"
        $DOCKER_COMPOSE_CMD -f "$COMPOSE_FILE" logs --tail=30
        read -p $'\nНажмите Enter для возврата в меню...'
        return 1
    fi

    sleep 3

    STATUS=$(docker ps --filter "name=${CONTAINER_NAME}" --format "{{.Status}}" 2>/dev/null || echo "")
    if [[ "$STATUS" == *"Up"* ]]; then
        ok "Пересборка завершена. Контейнер работает ($STATUS)"
    else
        warn "Контейнер не запустился после пересборки ($STATUS)"
    fi

    echo -e "\n${YELLOW}📋 Последние логи:${NC}"
    docker logs --tail=20 "$CONTAINER_NAME" 2>&1 || true

    read -p $'\nНажмите Enter для возврата в меню...'
}

# ─── 4. Статус ────────────────────────────────────────────────────────────────
show_status() {
    echo -e "\n${BLUE}════════════════════════════════════════${NC}"
    echo -e "${BLUE}   Статус системы                       ${NC}"
    echo -e "${BLUE}════════════════════════════════════════${NC}\n"

    # Контейнер
    STATUS=$(docker ps -a --filter "name=${CONTAINER_NAME}" --format "{{.Status}}" 2>/dev/null || echo "")
    if [[ "$STATUS" == *"Up"* ]]; then
        echo -e "  🤖 Контейнер ${CONTAINER_NAME}: ${GREEN}✓ Работает${NC} ($STATUS)"
    elif [ -n "$STATUS" ]; then
        echo -e "  🤖 Контейнер ${CONTAINER_NAME}: ${RED}✗ Остановлен${NC} ($STATUS)"
    else
        echo -e "  🤖 Контейнер ${CONTAINER_NAME}: ${YELLOW}не найден${NC}"
    fi

    # Директория
    if [ -d "$WORK_DIR" ]; then
        echo -e "  📁 Директория: ${GREEN}✓ ${WORK_DIR}${NC}"
    else
        echo -e "  📁 Директория: ${RED}✗ не найдена${NC}"
    fi

    # .env
    if [ -f "$WORK_DIR/.env" ]; then
        echo -e "  📄 .env файл:  ${GREEN}✓ существует${NC}"
    else
        echo -e "  📄 .env файл:  ${RED}✗ не найден${NC}"
    fi

    # Docker
    echo -e "  🐳 Docker:     ${GREEN}$(docker --version 2>/dev/null | cut -d' ' -f1-3)${NC}"

    # Диск
    echo -e "\n  💾 Использование диска:"
    df -h / | awk 'NR==2 {printf "     Всего: %s  Занято: %s  Свободно: %s (%s)\n", $2, $3, $4, $5}'

    # Память
    echo -e "  🧠 Память:"
    free -h | awk 'NR==2 {printf "     Всего: %s  Занято: %s  Свободно: %s\n", $2, $3, $4}'

    read -p $'\nНажмите Enter для возврата в меню...'
}

# ─── 5. Удаление ──────────────────────────────────────────────────────────────
remove_bot() {
    echo -e "\n${BLUE}════════════════════════════════════════${NC}"
    echo -e "${BLUE}   Удаление msgbot                      ${NC}"
    echo -e "${BLUE}════════════════════════════════════════${NC}\n"

    warn "Это действие остановит и удалит контейнер и образ."
    warn "Данные (база заявок) сохранятся в Docker volume."
    echo ""
    read -p "  Вы уверены? (нажмите Enter для подтверждения или 0 для отмены): " confirm
    [[ "$confirm" == "0" ]] && { echo -e "${YELLOW}Отменено${NC}"; read -p $'\nНажмите Enter...'; return; }

    if [ -d "$WORK_DIR" ]; then
        cd "$WORK_DIR"
        step "Остановка и удаление контейнера..."
        $DOCKER_COMPOSE_CMD -f "$COMPOSE_FILE" down >> "$LOG_FILE" 2>&1 || true
        ok "Контейнер удалён"

        step "Удаление Docker-образа..."
        docker rmi msgbot-msgbot 2>/dev/null || docker rmi msgbot_msgbot 2>/dev/null || true
        ok "Образ удалён"
    else
        warn "Директория ${WORK_DIR} не найдена — нечего удалять"
    fi

    echo ""
    read -p "  Удалить также файлы бота в ${WORK_DIR}? [y/N]: " del_files
    if [[ "$del_files" == "y" || "$del_files" == "Y" ]]; then
        rm -rf "$WORK_DIR"
        ok "Файлы удалены"
    else
        ok "Файлы оставлены в ${WORK_DIR}"
    fi

    ok "msgbot удалён"
    read -p $'\nНажмите Enter для возврата в меню...'
}

# ─── Меню ─────────────────────────────────────────────────────────────────────
show_menu() {
    echo -e "${BLUE}════════════════════════════════════════${NC}"
    echo -e "${BLUE}   Выберите действие:                   ${NC}"
    echo -e "${BLUE}════════════════════════════════════════${NC}"
    echo -e "${YELLOW}🤖 MSGBOT:${NC}"
    echo -e "  ${GREEN}1)${NC} 📥 Установка"
    echo -e "  ${GREEN}2)${NC} 📜 Логи"
    echo -e "  ${GREEN}3)${NC} 🔄 Пересборка"
    echo -e "  ${GREEN}4)${NC} 🗑️  Удаление"
    echo -e "${BLUE}────────────────────────────────────────${NC}"
    echo -e "  ${GREEN}5)${NC} 📊 Статус системы"
    echo -e "${BLUE}────────────────────────────────────────${NC}"
    echo -e "  ${GREEN}0)${NC} 🚪 Выход"
    echo -e "${BLUE}════════════════════════════════════════${NC}"
}

# ─── Инициализация ────────────────────────────────────────────────────────────
print_header
echo -e "${YELLOW}Лог установки: ${LOG_FILE}${NC}\n"
install_deps
install_docker

# ─── Основной цикл ───────────────────────────────────────────────────────────
while true; do
    print_header
    show_menu
    read -p "Введите номер: " choice

    case $choice in
        1) install_bot  ;;
        2) show_logs    ;;
        3) rebuild_bot  ;;
        4) remove_bot   ;;
        5) show_status  ;;
        0)
            echo -e "\n${GREEN}👋 До свидания!${NC}\n"
            exit 0
            ;;
        *)
            warn "Неверный выбор: $choice"
            sleep 1
            ;;
    esac
done
