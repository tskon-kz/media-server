export default {
  // Bottom navigation tabs
  tabs: {
    torrents: "Торренты",
    add: "Добавить",
    search: "Поиск",
    status: "Статус",
    settings: "Настройки",
  },

  // Shared across multiple screens
  common: {
    save: "Сохранить",
    cancel: "Отмена",
    delete: "Удалить",
    added: "Добавлено",
    done: "Готово",
    chooseCategory: "Выберите категорию",
  },

  // Torrent list screen
  torrents: {
    title: "Торренты",
    pull: "↓ потяните для обновления",
    empty: "Нет торрентов",
    emptyHint: "Добавьте magnet-ссылку или .torrent файл",
    deleted: "Удалено",
    moved: "Перемещено в {{name}}",
    xdev: "Ошибка хардлинка: разные разделы",
    linked: "Связано {{n}}, {{pending}} требуют ввода",
    // Action buttons
    move: "Переместить в категорию",
    structure: "Структура",
    pretty: "Красивые имена",
    original: "Оригинальная структура",
    delLinks: "Удалить хардлинки",
    // Delete confirmation modal
    deleteTitle: "Удалить торрент?",
    deleteBody: '"{{name}}" и все его файлы будут удалены.',
  },

  // Add torrent screen
  add: {
    title: "Добавить торрент",
    magnetSection: "Magnet-ссылка",
    addMagnet: "Добавить magnet",
    uploadLabel: "Загрузить .torrent файл",
    invalidMagnet: "Введите корректную magnet-ссылку",
    manual: "Добавить вручную",
  },

  // Search screen
  search: {
    title: "Поиск",
    addViaSearch: "Добавить через поиск",
    inputHeader: "Поиск Jackett",
    placeholder: "Поиск Jackett…",
    empty: "Нет результатов",
    emptyHint: "Попробуйте другой запрос",
    seeders: "{{n}} сидеров",
  },

  // Status screen
  status: {
    title: "Статус",
    services: "Сервисы",
    transfer: "Передача",
    download: "↓ Загрузка",
    upload: "↑ Отдача",
    session: "За сессию",
    sessionDl: "Скачано",
    sessionUl: "Отдано",
    diskFree: "Свободно на диске",
    torrentsSection: "Торренты",
    downloading: "Скачивается",
    seeding: "Раздаётся",
    total: "Всего",
  },

  // Settings screen
  settings: {
    title: "Настройки",

    // Auto-structure toggle
    autoStructure: "Авто-структура закачек",
    smartSub: "Умный парсинг",
    originalSub: "Ориг. структура",

    // Language & appearance
    language: "Язык",
    appearance: "Оформление",
    auto: "Авто",
    light: "Светлая",
    dark: "Тёмная",

    // Categories section
    categories: "Категории",
    addCategory: "Добавить категорию",
    newCategory: "Новая категория",
    nameLabel: "Название",
    libraryType: "Тип библиотеки",
    catAdded: "Категория добавлена",
    catDeleted: "Категория удалена",
    deleteCatTitle: "Удалить категорию?",
    deleteCatBody: "Категория «{{name}}» будет удалена.",
    renameCategory: "Переименовать категорию",
    newName: "Новое название",
    // Jellyfin library type labels
    movies: "Фильмы",
    tvShows: "Сериалы",
    music: "Музыка",
    other: "Прочее",

    // qBittorrent section
    qb: "qBittorrent",
    credentials: "Учётные данные",
    userSub: "Пользователь: {{user}}",
    changePass: "Изменить пароль",
    getTemp: "Временный пароль",
    restart: "Перезапустить",
    qbPassTitle: "Пароль qBittorrent",
    newPass: "Новый пароль",
    qbPassChanged: "Пароль qBittorrent изменён",
    noTemp: "Нет временного пароля",
    tempPass: "Временный: {{password}}",
    qbRestarting: "qBittorrent перезапускается…",
    restartFailed: "Ошибка перезапуска",

    // Jackett section
    jackett: "Jackett",
    apiKey: "API ключ: {{status}}",
    keyAvailable: "есть",
    keyMissing: "нет",
    removePass: "Убрать пароль",
    jackettPassTitle: "Пароль администратора Jackett",
    newPassEmpty: "Новый пароль (пусто — убрать)",
    jackettPassUpdated: "Пароль Jackett обновлён",
    jackettPassRemoved: "Пароль Jackett удалён",

    // Jellyfin section
    jellyfin: "Jellyfin",
    scanLibrary: "Сканировать библиотеку",
    scanOk: "Сканирование Jellyfin запущено",
    scanFail: "Ошибка сканирования",
    manageUsers: "Управление пользователями",
    jfUsers: "Пользователи Jellyfin",
    noUsers: "Нет пользователей",
    addUser: "Добавить пользователя",
    newUser: "Новый пользователь",
    username: "Имя пользователя",
    next: "Далее",
    passwordFor: "Пароль для {{name}}",
    password: "Пароль",
    userCreated: "Пользователь создан",

    openWebUI: "Открыть веб-интерфейс",

    // Update section
    update: "Обновление",
    updateVersion: "Версия",
    updateChannel: "Канал",
    updateStable: "Stable",
    updateEdge: "Edge (бета)",
    updateAvailable: "Доступна",
    updateBtn: "Обновить до {{version}}",
    updateRefreshEdge: "🔄 Обновить Edge",
    updateSwitchToEdge: "Перейти на Edge (бета)",
    updateSwitchToStable: "Перейти на Stable",
    updateStarted: "Обновление запущено, бот перезапустится через ~1 мин.",
    updateEdgeWarning: "Edge — это неопубликованный код из ветки main. Может быть нестабильным.",
    updateConfirmEdge: "Да, переключить на Edge",

    // Footer
    version: "версия {{version}}",
    smartOn: "Умная структура включена",
    originalOn: "Оригинальная структура",
  },
} as const;
