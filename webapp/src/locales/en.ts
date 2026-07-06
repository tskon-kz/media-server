export default {
  // Bottom navigation tabs
  tabs: {
    torrents: "Torrents",
    add: "Add",
    search: "Search",
    status: "Status",
    settings: "Settings",
  },

  // Shared across multiple screens
  common: {
    save: "Save",
    cancel: "Cancel",
    delete: "Delete",
    added: "Added",
    done: "Done",
    chooseCategory: "Choose category",
  },

  // Torrent list screen
  torrents: {
    title: "Torrents",
    pull: "↓ pull to refresh",
    empty: "No torrents",
    emptyHint: "Add a magnet link or .torrent file",
    deleted: "Deleted",
    moved: "Moved to {{name}}",
    xdev: "Hardlink error: different partitions",
    linked: "Linked {{n}}, {{pending}} need input",
    // Action buttons
    move: "Move to category",
    structure: "Structure",
    pretty: "Pretty names",
    original: "Original structure",
    delLinks: "Delete hardlinks",
    // Delete confirmation modal
    deleteTitle: "Delete torrent?",
    deleteBody: '"{{name}}" and all its files will be removed.',
  },

  // Add torrent screen
  add: {
    title: "Add torrent",
    magnetSection: "Magnet link",
    addMagnet: "Add magnet",
    fileSection: ".torrent file",
    uploadLabel: "Upload .torrent file",
    invalidMagnet: "Enter a valid magnet link",
  },

  // Search screen
  search: {
    title: "Search",
    inputHeader: "Search Jackett",
    placeholder: "Search Jackett…",
    empty: "No results",
    emptyHint: "Try a different query",
    seeders: "{{n}} seeders",
  },

  // Status screen
  status: {
    title: "Status",
    services: "Services",
    transfer: "Transfer",
    download: "↓ Download",
    upload: "↑ Upload",
    scan: "Scan Jellyfin library",
    scanOk: "Jellyfin scan started",
    scanFail: "Scan failed",
  },

  // Settings screen
  settings: {
    title: "Settings",

    // Auto-structure toggle
    autoStructure: "Torrents auto-structure",
    smartSub: "Smart (parse filenames)",
    originalSub: "Original structure",

    // Language & appearance
    language: "Language",
    appearance: "Appearance",
    auto: "Auto",
    light: "Light",
    dark: "Dark",

    // Categories section
    categories: "Categories",
    addCategory: "Add category",
    newCategory: "New category",
    nameLabel: "Name",
    libraryType: "Library type",
    catAdded: "Category added",
    catDeleted: "Category deleted",
    renameCategory: "Rename category",
    newName: "New name",
    // Jellyfin library type labels
    movies: "Movies",
    tvShows: "TV Shows",
    music: "Music",
    other: "Other",

    // qBittorrent section
    qb: "qBittorrent",
    credentials: "Credentials",
    userSub: "User: {{user}}",
    changePass: "Change pass",
    getTemp: "Get temp",
    restart: "Restart",
    qbPassTitle: "qBittorrent password",
    newPass: "New password",
    qbPassChanged: "qB password changed",
    noTemp: "No temporary password",
    tempPass: "Temp: {{password}}",
    qbRestarting: "qB restarting…",
    restartFailed: "Restart failed",

    // Jackett section
    jackett: "Jackett",
    apiKey: "API key: {{status}}",
    keyAvailable: "available",
    keyMissing: "missing",
    removePass: "Remove pass",
    jackettPassTitle: "Jackett admin password",
    newPassEmpty: "New password (empty to remove)",
    jackettPassUpdated: "Jackett password updated",
    jackettPassRemoved: "Jackett password removed",

    // Jellyfin section
    jellyfin: "Jellyfin",
    manageUsers: "Manage users",
    jfUsers: "Jellyfin users",
    noUsers: "No users yet",
    addUser: "Add user",
    newUser: "New user",
    username: "Username",
    next: "Next",
    passwordFor: "Password for {{name}}",
    password: "Password",
    userCreated: "User created",

    // Web UIs section
    webUIs: "Web UIs",

    // Footer
    version: "version {{version}}",
    smartOn: "Smart structure on",
    originalOn: "Original structure",
  },
} as const;
