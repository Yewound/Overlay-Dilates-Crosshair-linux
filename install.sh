#!/bin/bash

# Получаем абсолютный путь к текущей папке проекта
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

echo "Настройка Dilates Crosshair..."

# Делаем AppImage исполняемым
chmod +x "$DIR/Dilates_Crosshair-x86_64.AppImage"

# Копируем иконку в системную папку, чтобы Linux её увидел
sudo cp "$DIR/icon.png" /usr/share/icons/hicolor/256x256/apps/crosshair.png

# Создаем ярлык в меню приложений текущего пользователя
mkdir -p ~/.local/share/applications
cat <<EOF > ~/.local/share/applications/crosshair.desktop
[Desktop Entry]
Type=Application
Name=Dilates Crosshair
Comment=Overlay Crosshair for Linux
Exec="$DIR/Dilates_Crosshair-x86_64.AppImage"
Icon=crosshair
Terminal=false
Categories=Game;Utility;
EOF

# Обновляем кэш иконок и меню
sudo gtk-update-icon-cache /usr/share/icons/hicolor/ 2>/dev/null
update-desktop-database ~/.local/share/applications

echo "Установка завершена! Ищите 'Dilates Crosshair' в меню приложений."
