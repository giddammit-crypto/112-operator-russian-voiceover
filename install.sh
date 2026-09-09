#!/bin/bash
set -e

echo "=========================================================="
echo " 112 Operator - Русская кинематографическая озвучка (Установщик) "
echo "=========================================================="

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Поиск пути к игре
CANDIDATE_DIRS=(
    "/home/astra/vint2/gamez/steamapps/common/112 Operator"
    "$HOME/.steam/steam/steamapps/common/112 Operator"
    "$HOME/.local/share/Steam/steamapps/common/112 Operator"
    "$1"
)

GAME_DIR=""
for d in "${CANDIDATE_DIRS[@]}"; do
    if [ -n "$d" ] && [ -d "$d/Operator 112_Data" ]; then
        GAME_DIR="$d"
        break
    fi
done

if [ -z "$GAME_DIR" ]; then
    echo "Ошибка: Не удалось найти директорию игры '112 Operator'!"
    echo "Использование: ./install.sh \"/путь/к/112 Operator\""
    exit 1
fi

echo "[+] Найдена игра: $GAME_DIR"
GAME_DATA="$GAME_DIR/Operator 112_Data"
MANAGED="$GAME_DATA/Managed"
STREAMING="$GAME_DATA/StreamingAssets"

# 1. Сборка DLL если необходимо
if [ ! -f "$SCRIPT_DIR/RussianRadioMod/bin/Release/netstandard2.1/RussianRadioMod.dll" ]; then
    echo "[*] Сборка RussianRadioMod.dll..."
    DOTNET_BIN="$HOME/.dotnet/dotnet"
    if ! command -v dotnet &> /dev/null && [ -f "$DOTNET_BIN" ]; then
        DOTNET_CMD="$DOTNET_BIN"
    else
        DOTNET_CMD="dotnet"
    fi
    $DOTNET_CMD build "$SCRIPT_DIR/RussianRadioMod/RussianRadioMod.csproj" -c Release
fi

# 2. Копирование RussianRadioMod.dll в Managed/
echo "[*] Установка RussianRadioMod.dll..."
cp "$SCRIPT_DIR/RussianRadioMod/bin/Release/netstandard2.1/RussianRadioMod.dll" "$MANAGED/RussianRadioMod.dll"

# 3. Регистрация сборки в конфигурациях Unity
python3 "$SCRIPT_DIR/deploy_mod.py"

# 4. Пропатчивание Main.dll через Cecil
echo "[*] Пропатчивание Main.dll для перехвата рации и вызовов..."
DOTNET_BIN="$HOME/.dotnet/dotnet"
if ! command -v dotnet &> /dev/null && [ -f "$DOTNET_BIN" ]; then
    DOTNET_CMD="$DOTNET_BIN"
else
    DOTNET_CMD="dotnet"
fi
$DOTNET_CMD run --project "$SCRIPT_DIR/Patcher/Patcher.csproj"

# 5. Установка файлов профиля мода
PROTON_MODS_DIR="$GAME_DIR/../../compatdata/793460/pfx/drive_c/users/steamuser/AppData/LocalLow/JutsuGames/112 Operator/MyMods/RussianRadioVoiceover"
LOCAL_MODS_DIR="$GAME_DIR/MyMods/RussianRadioVoiceover"

for target_m in "$PROTON_MODS_DIR" "$LOCAL_MODS_DIR"; do
    mkdir -p "$target_m"
    if [ -d "$SCRIPT_DIR/MyMods/RussianRadioVoiceover" ]; then
        cp -r "$SCRIPT_DIR/MyMods/RussianRadioVoiceover/"* "$target_m/"
        echo "[+] Профиль мода скопирован в: $target_m"
    fi
done

echo ""
echo "=========================================================="
echo " Установка успешно завершена! "
echo " Запустите 112 Operator в Steam и убедитесь, что мод "
echo " 'Russian Radio Voiceover' включен в меню 'Моды'."
echo " Приятной игры!"
echo "=========================================================="
