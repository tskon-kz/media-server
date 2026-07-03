# Media Server

> [English version](README.md)

Самохостинг медиасервера: Jellyfin + qBittorrent, управление полностью через Telegram-бот. Один скрипт — и всё готово.

## Возможности

- Отправь magnet-ссылку или `.torrent`-файл в Telegram — бот сделает остальное
- **Поиск раздач** через `/search` — ищет по всем индексаторам Jackett, выбери результат и добавь
- Уведомления о завершении загрузки с автоматическим сканированием Jellyfin
- Автоматическое переименование файлов по стандарту Jellyfin через хардлинки (без дублирования)
- Управление категориями-библиотеками (Фильмы, Сериалы + добавление своих)
- Встроенная система обновлений через бота

## Установка

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/tskon-kz/media-server/main/install.sh)
```

## Документация

- [Установка (подробно)](docs/installation.md)
- [Настройка для разработки](docs/dev-setup.md)
- [Команды бота](docs/commands.md)
- [Конфигурация](docs/configuration.md)
- [Решение проблем и обслуживание](docs/troubleshooting.md)
