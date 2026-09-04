#!/bin/bash

# Останавливаем скрипт при любой ошибке
set -e

APP_NAME="DilatesCrosshair"
PYTHON_SCRIPT="app.py"

echo "=== 1. Создание виртуального окружения (venv) ==="
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

# Активируем виртуальное окружение
source venv/bin/activate

echo "=== 2. Установка PyInstaller и PyQt5 в изолированное окружение ==="
pip install --upgrade pip
pip install pyinstaller PyQt5

echo "=== 3. Очистка старых сборок ==="
rm -rf build dist AppDir *.AppImage

echo "=== 4. Сборка через PyInstaller (режим папки для стабильности PyQt) ==="
pyinstaller --noconsole --onedir --collect-all PyQt5 "$PYTHON_SCRIPT"

echo "=== 5. Создание структуры AppDir ==="
mkdir -p AppDir/usr/bin
mkdir -p AppDir/usr/share/applications
mkdir -p AppDir/usr/share/icons/hicolor/256x256/apps

# Копируем скомпилированную папку в AppDir/usr/bin/
cp -r "dist/app" "AppDir/usr/bin/$APP_NAME"
chmod +x "AppDir/usr/bin/$APP_NAME/app"

# Создаем правильный AppRun в корне AppDir (критично для запуска AppImage)
cat << 'EOF' > "AppDir/AppRun"
#!/bin/bash
HERE="$(dirname "$(readlink -f "$0")")"
exec "$HERE/usr/bin/DilatesCrosshair/app" "$@"
EOF
chmod +x "AppDir/AppRun"

# Создаем .desktop файл
cat << EOF > "AppDir/usr/share/applications/$APP_NAME.desktop"
[Desktop Entry]
Type=Application
Name=Dilates Crosshair
Exec=AppRun
Icon=crosshair
Categories=Utility;Game;
Comment=Custom Crosshair Overlay
Terminal=false
EOF

# Копируем .desktop в корень AppDir
cp "AppDir/usr/share/applications/$APP_NAME.desktop" "AppDir/"

# Создаем или копируем иконку
if [ -f "icon.png" ]; then
    cp icon.png AppDir/usr/share/icons/hicolor/256x256/apps/crosshair.png
    cp icon.png AppDir/crosshair.png
else
    echo "Иконка icon.png не найдена, скачиваем базовую заглушку..."
    curl -s -L -o AppDir/crosshair.png "https://raw.githubusercontent.com/xi/xi-mac/master/assets/icon.png" || touch AppDir/crosshair.png
    cp AppDir/crosshair.png AppDir/usr/share/icons/hicolor/256x256/apps/crosshair.png
fi

echo "=== 6. Загрузка appimagetool (если отсутствует) ==="
if [ ! -f "appimagetool-x86_64.AppImage" ]; then
    wget -q https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage
    chmod +x appimagetool-x86_64.AppImage
fi

echo "=== 7. Упаковка в .AppImage ==="
export ARCH=x86_64
./appimagetool-x86_64.AppImage --appimage-extract-and-run AppDir

echo "=== СБОРКА УСПЕШНО ЗАВЕРШЕНА! ==="
ls -lh *.AppImage