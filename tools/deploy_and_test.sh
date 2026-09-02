#!/usr/bin/env bash
# deploy_and_test.sh — синхронизирует исходники на RV1126B SOC,
#                      собирает unit-тесты на устройстве и запускает их.
#
# Требования на хосте: bash, rsync, ssh, scp
# Требования на SOC  : Ubuntu 22.04, g++, cmake ≥ 3.20
#                      (cmake устанавливается автоматически при первом запуске)
#
# Использование:
#   ./tools/deploy_and_test.sh <SOC_IP> [USER=root] [PORT=22]
#
# Дополнительные переменные окружения:
#   MODELS_DIR  — путь к директории с .rknn моделями на SOC
#                 (если задан — запускаются интеграционные тесты LPR)
#   CLEAN_BUILD — если задан (любое значение) — пересобрать с нуля
#   NO_RSYNC    — пропустить синхронизацию исходников (только сборка/запуск)
#
# Примеры:
#   ./tools/deploy_and_test.sh 10.0.0.5
#   ./tools/deploy_and_test.sh 10.0.0.5 root 22
#   MODELS_DIR=/opt/traffic_ai/models ./tools/deploy_and_test.sh 10.0.0.5
#   CLEAN_BUILD=1 ./tools/deploy_and_test.sh 10.0.0.5
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

# ── Аргументы ────────────────────────────────────────────────────────────────

SOC_IP="${1:-}"
SOC_USER="${2:-root}"
SOC_PORT="${3:-22}"

if [[ -z "$SOC_IP" ]]; then
    echo "Использование: $0 <SOC_IP> [USER=root] [PORT=22]"
    echo ""
    echo "Переменные окружения:"
    echo "  MODELS_DIR  — путь к .rknn моделям на SOC (интеграционные тесты LPR)"
    echo "  CLEAN_BUILD — 1: пересобрать с нуля"
    echo "  NO_RSYNC    — 1: пропустить синхронизацию"
    exit 1
fi

REMOTE_SRC="/opt/rv1126b_src"
REMOTE_BUILD="$REMOTE_SRC/firmware/build_tests"

# ── Цвета ────────────────────────────────────────────────────────────────────

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

step()  { echo -e "\n${CYAN}${BOLD}▶ $*${NC}"; }
ok()    { echo -e "${GREEN}✓${NC} $*"; }
warn()  { echo -e "${YELLOW}⚠${NC}  $*"; }
die()   { echo -e "\n${RED}${BOLD}✗ ОШИБКА: $*${NC}" >&2; exit 1; }

SSH_OPTS="-p $SOC_PORT -o StrictHostKeyChecking=no -o ConnectTimeout=10"
SSH="ssh $SSH_OPTS $SOC_USER@$SOC_IP"
RSYNC_SSH="ssh $SSH_OPTS"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# ── 1. Проверка соединения ────────────────────────────────────────────────────

step "Проверка SSH-соединения с $SOC_USER@$SOC_IP:$SOC_PORT"

$SSH "echo OK" >/dev/null 2>&1 \
    || die "Нет доступа к $SOC_IP. Проверьте IP, пользователя и SSH-ключи."
ok "Соединение установлено"

SOC_ARCH=$($SSH "uname -m")
SOC_OS=$($SSH "lsb_release -ds 2>/dev/null || cat /etc/os-release | grep PRETTY | cut -d= -f2 | tr -d '\"'")
echo "   Архитектура: $SOC_ARCH   ОС: $SOC_OS"

# ── 2. Проверка и установка зависимостей на SOC ───────────────────────────────

step "Проверка зависимостей на SOC"

install_if_missing() {
    local pkg="$1"
    local cmd="${2:-$1}"
    if ! $SSH "command -v $cmd >/dev/null 2>&1"; then
        warn "$cmd не найден — устанавливаем пакет $pkg ..."
        $SSH "apt-get install -y $pkg" \
            || die "Не удалось установить $pkg. Запустите: ssh $SOC_USER@$SOC_IP apt-get install -y $pkg"
        ok "$pkg установлен"
    else
        ok "$cmd — $(${SSH} "$cmd --version 2>&1 | head -1")"
    fi
}

install_if_missing "g++"         "g++"
install_if_missing "cmake"       "cmake"
install_if_missing "rsync"       "rsync"
install_if_missing "git"         "git"    # нужен FetchContent для GoogleTest

# ── 3. Синхронизация исходников ───────────────────────────────────────────────

if [[ -z "${NO_RSYNC:-}" ]]; then
    step "Синхронизация исходников → $SOC_USER@$SOC_IP:$REMOTE_SRC"

    $SSH "mkdir -p $REMOTE_SRC/firmware"

    rsync -az --delete \
        --exclude 'build*/' \
        --exclude '*.o' \
        --exclude '*.a' \
        -e "$RSYNC_SSH" \
        "$REPO_ROOT/firmware/src/"   "$SOC_USER@$SOC_IP:$REMOTE_SRC/firmware/src/"

    rsync -az --delete \
        --exclude 'build*/' \
        -e "$RSYNC_SSH" \
        "$REPO_ROOT/firmware/tests/" "$SOC_USER@$SOC_IP:$REMOTE_SRC/firmware/tests/"

    ok "Исходники синхронизированы"
else
    warn "NO_RSYNC задан — синхронизация пропущена"
fi

# ── 4. Сборка тестов на SOC ───────────────────────────────────────────────────

step "Сборка тестов на SOC (cmake + make)"

if [[ -n "${CLEAN_BUILD:-}" ]]; then
    warn "CLEAN_BUILD задан — удаляем $REMOTE_BUILD"
    $SSH "rm -rf $REMOTE_BUILD"
fi

# cmake configure (только если CacheEntries нет или CLEAN_BUILD)
$SSH "bash -c '
    set -e
    mkdir -p $REMOTE_BUILD
    cd $REMOTE_BUILD

    if [[ ! -f CMakeCache.txt ]]; then
        echo \"[cmake] Конфигурируем ...\"
        cmake $REMOTE_SRC/firmware/tests \
            -DCMAKE_BUILD_TYPE=Debug \
            2>&1
    else
        echo \"[cmake] Кэш найден — пропускаем конфигурацию\"
    fi

    echo \"[make] Собираем ...\"
    make -j\$(nproc) 2>&1
'"

ok "Сборка завершена"

# ── 5. Запуск тестов ──────────────────────────────────────────────────────────

step "Запуск unit-тестов на SOC"

CTEST_OUTPUT=$($SSH "bash -c '
    cd $REMOTE_BUILD
    ctest --output-on-failure -V 2>&1
'" || true)   # не прерываемся на провале — покажем результаты сами

echo "$CTEST_OUTPUT"

# ── 6. Интеграционные тесты LPR (опционально) ────────────────────────────────

if [[ -n "${MODELS_DIR:-}" ]]; then
    step "Интеграционные тесты LPR (MODELS_DIR=$MODELS_DIR)"

    if $SSH "test -f $REMOTE_BUILD/test_lpr"; then
        LPR_OUTPUT=$($SSH "cd $REMOTE_BUILD && MODELS_DIR=$MODELS_DIR ./test_lpr --gtest_color=yes 2>&1" || true)
        echo "$LPR_OUTPUT"
    else
        warn "test_lpr не собран (RKNN runtime не найден при cmake). " \
             "Передайте -DRKNN_RT_LIB=... в cmake или установите librknnrt.so."
    fi
fi

# ── 7. Итог ───────────────────────────────────────────────────────────────────

step "Итог"

PASSED=$(echo "$CTEST_OUTPUT" | grep -oP '\d+(?= tests passed)'  || echo "0")
FAILED=$(echo "$CTEST_OUTPUT" | grep -oP '\d+(?= tests failed)'  || echo "0")
TOTAL=$(echo  "$CTEST_OUTPUT" | grep -oP '\d+(?= tests)'         | tail -1 || echo "0")

if [[ "$FAILED" == "0" ]]; then
    echo -e "\n${GREEN}${BOLD}  ✓  $PASSED/$TOTAL тестов прошли${NC}"
    exit 0
else
    echo -e "\n${RED}${BOLD}  ✗  $FAILED тестов провалились ($PASSED/$TOTAL прошли)${NC}"
    echo -e "   Запустите отдельный бинарник для деталей:"
    echo -e "   ${CYAN}ssh $SOC_USER@$SOC_IP \"cd $REMOTE_BUILD && ./test_violation --gtest_color=yes\"${NC}"
    exit 1
fi
