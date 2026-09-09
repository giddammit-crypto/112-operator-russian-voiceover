#!/bin/bash
# Установщик кинематографической русской озвучки для 112 Operator.
#
# Использование:
#   ./install.sh                          # автопоиск игры, сборка и установка
#   ./install.sh "/путь/к/112 Operator"   # явный путь к игре
#
# Переменные окружения:
#   BACKEND=edge|piper|silero|espeak|stub   движок синтеза речи (по умолчанию auto)
#   JOBS=4                                  число параллельных процессов
#   SKIP_AUDIO=1                            не пересобирать аудио
#   SKIP_BUILD=1                            не собирать C#-сборку мода

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND="${BACKEND:-auto}"
JOBS="${JOBS:-}"

echo "=========================================================="
echo " 112 Operator — Русская кинематографическая озвучка"
echo "=========================================================="

# --- 1. Поиск игры -------------------------------------------------------
CANDIDATE_DIRS=(
    "${1:-}"
    "$HOME/.steam/steam/steamapps/common/112 Operator"
    "$HOME/.local/share/Steam/steamapps/common/112 Operator"
    "$HOME/.var/app/com.valvesoftware.Steam/data/Steam/steamapps/common/112 Operator"
    "/mnt/steam/steamapps/common/112 Operator"
)

GAME_DIR=""
for d in "${CANDIDATE_DIRS[@]}"; do
    if [ -n "$d" ] && [ -d "$d/Operator 112_Data" ]; then
        GAME_DIR="$d"
        break
    fi
done

if [ -z "$GAME_DIR" ]; then
    echo "Ошибка: каталог игры '112 Operator' не найден."
    echo "Использование: ./install.sh \"/путь/к/112 Operator\""
    exit 1
fi

echo "[+] Игра найдена: $GAME_DIR"
GAME_DATA="$GAME_DIR/Operator 112_Data"

# --- 2. Проверка Python --------------------------------------------------
if ! command -v python3 >/dev/null 2>&1; then
    echo "Ошибка: требуется Python 3.8 или новее."
    exit 1
fi
echo "[+] Python: $(python3 --version)"

# --- 3. Сборка аудио -----------------------------------------------------
BUILD_DIR="$SCRIPT_DIR/build"
if [ "${SKIP_AUDIO:-0}" != "1" ]; then
    echo ""
    echo "[*] Генерация озвучки (движок: $BACKEND)..."
    JOBS_ARG=()
    [ -n "$JOBS" ] && JOBS_ARG=(--jobs "$JOBS")

    ( cd "$SCRIPT_DIR" && python3 -m voicepack all \
        --out "$BUILD_DIR" \
        --game "$GAME_DIR" \
        --backend "$BACKEND" \
        "${JOBS_ARG[@]}" )
else
    echo "[~] Пропуск генерации аудио (SKIP_AUDIO=1)"
fi

# --- 4. Сборка C#-модуля -------------------------------------------------
DLL="$SCRIPT_DIR/RussianRadioMod/bin/Release/netstandard2.1/RussianRadioMod.dll"
if [ "${SKIP_BUILD:-0}" != "1" ] && [ ! -f "$DLL" ]; then
    echo ""
    echo "[*] Сборка RussianRadioMod.dll..."
    DOTNET_CMD="dotnet"
    if ! command -v dotnet >/dev/null 2>&1; then
        if [ -x "$HOME/.dotnet/dotnet" ]; then
            DOTNET_CMD="$HOME/.dotnet/dotnet"
        else
            echo "[~] .NET SDK не найден — сборка мода пропущена."
            echo "    Аудио установится, но потребуется собрать DLL вручную."
            DOTNET_CMD=""
        fi
    fi
    if [ -n "$DOTNET_CMD" ]; then
        "$DOTNET_CMD" build "$SCRIPT_DIR/RussianRadioMod/RussianRadioMod.csproj" -c Release
        if [ -d "$GAME_DATA/Managed" ]; then
            "$DOTNET_CMD" run --project "$SCRIPT_DIR/Patcher/Patcher.csproj" -- "$GAME_DIR" || \
                echo "[~] Патчер завершился с ошибкой — проверьте вывод выше."
        fi
    fi
fi

# --- 5. Установка --------------------------------------------------------
echo ""
echo "[*] Установка пака в игру..."
( cd "$SCRIPT_DIR" && python3 -m voicepack install --out "$BUILD_DIR" --game "$GAME_DIR" )

# --- 6. Проверка ---------------------------------------------------------
echo ""
( cd "$SCRIPT_DIR" && python3 -m voicepack verify --out "$BUILD_DIR" --game "$GAME_DIR" )

echo ""
echo "=========================================================="
echo " Готово! Запустите 112 Operator и включите мод"
echo " «Russian Radio Voiceover» в меню «Моды»."
echo "=========================================================="
