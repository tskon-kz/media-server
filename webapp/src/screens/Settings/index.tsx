import {useEffect, useState} from "react"
import {Box, Button, Drawer, Loader, SegmentedControl, Stack, Text} from "@mantine/core"
import {Trash2, UserPlus,} from "lucide-react"
import {useTranslation} from "react-i18next"
import {api} from "@/api"
import {toast} from "@/components/Toast"
import {type ThemeMode, useTheme} from "@/theme"
import {setAppLanguage} from "@/i18n"
import {Collapse} from "@/components/Collapse"
import {PromptSheet} from "@/components/PromptSheet"
import Section from "@/components/Section"
import {ListItem, ListSection} from "@/components/ui"
import type {AppConfig, JellyfinUser, Settings as SettingsData, UpdateInfo} from "@/types"
import PageHeader from "@/components/PageHeader"
import {QbContent} from "./components/QbContent"
import {JackettContent} from "./components/JackettContent"
import {JellyfinContent} from "./components/JellyfinContent"
import {UpdateContent} from "./components/UpdateContent"

const DEL_COLOR = "var(--tg-theme-destructive-text-color)"

export function Settings() {
  const {t} = useTranslation()
  const {mode: themeMode, setMode: setThemeMode} = useTheme()
  const [cfg, setCfg] = useState<AppConfig | null>(null)
  const [settingsData, setSettingsData] = useState<SettingsData | null>(null)
  const [users, setUsers] = useState<JellyfinUser[] | null>(null)
  const [updateInfo, setUpdateInfo] = useState<UpdateInfo | null>(null)
  const [dialog, setDialog] = useState<string | null>(null)
  const [newUserName, setNewUserName] = useState("")
  const [scanning, setScanning] = useState(false)

  const reload = async () => {
    const [c, settings] = await Promise.all([api.config(), api.settings()])
    setCfg(c)
    setSettingsData(settings)
    setAppLanguage(settings.lang)
    // Update info involves a GitHub call — load without blocking the main render
    api.update().then(setUpdateInfo).catch(() => {})
  }

  useEffect(() => {
    reload().catch((e) => toast((e as Error).message, "err"))
  }, []) // eslint-disable-line

  const guard = async (fn: () => Promise<void>) => {
    try {
      await fn()
    } catch (e) {
      toast((e as Error).message, "err")
    }
  }

  if (!cfg || !settingsData) {
    return (
      <Box style={{textAlign: "center", paddingTop: 60}}>
        <Loader size="md"/>
      </Box>
    )
  }

  const setLang = (lang: string) => guard(async () => {
    await api.setLanguage(lang)
    setAppLanguage(lang)
    reload()
  })

  const openUsers = () => guard(async () => {
    const u = await api.jellyfinUsers()
    setUsers(u.users)
    setDialog("users")
  })

  const addUser = (password: string) => guard(async () => {
    await api.createJellyfinUser(newUserName, password)
    setDialog("users")
    setNewUserName("")
    toast(t("settings.userCreated"))
    const u = await api.jellyfinUsers()
    setUsers(u.users)
  })

  const delUser = (u: JellyfinUser) => guard(async () => {
    await api.deleteJellyfinUser(u.id)
    const list = await api.jellyfinUsers()
    setUsers(list.users)
  })

  const qbPass = (p: string) => guard(async () => {
    await api.setQbPassword(p)
    setDialog(null)
    toast(t("settings.qbPassChanged"))
    reload()
  })
  const qbTemp = () => guard(async () => {
    const r = await api.fetchQbTemp()
    toast(r.found ? t("settings.tempPass", {password: r.password}) : t("settings.noTemp"), r.found ? "ok" : "err")
    reload()
  })
  const qbRestart = () => guard(async () => {
    const r = await api.restartQb()
    toast(r.ok ? t("settings.qbRestarting") : t("settings.restartFailed"), r.ok ? "ok" : "err")
  })
  const jackettPass = (p: string) => guard(async () => {
    await api.setJackettPassword(p)
    setDialog(null)
    toast(t("settings.jackettPassUpdated"))
    reload()
  })
  const jackettRemovePass = () => guard(async () => {
    await api.setJackettPassword("")
    toast(t("settings.jackettPassRemoved"))
    reload()
  })

  const scan = async () => {
    setScanning(true)
    try {
      const r = await api.scan()
      toast(r.ok ? t("settings.scanOk") : t("settings.scanFail"), r.ok ? "ok" : "err")
    } catch (e) {
      toast((e as Error).message, "err")
    } finally {
      setScanning(false)
    }
  }

  return (
    <Box>
      <PageHeader title={t("settings.title")}/>

      <Box p={16}>
        <Stack gap={8}>
          <Section title={t("settings.autoStructure")} className="mb-16">
            <SegmentedControl
              fullWidth
              value={settingsData.rename_mode}
              onChange={(v) => guard(async () => {
                await api.setRenameMode(v as "flat" | "pretty")
                toast(v === "pretty" ? t("settings.smartOn") : t("settings.originalOn"))
                reload()
              })}
              data={[
                {value: "flat", label: t("settings.originalSub")},
                {value: "pretty", label: t("settings.smartSub")},
              ]}
            />
          </Section>

          <Section className="mb-16" title={t("settings.language")}>
            <SegmentedControl
              fullWidth
              value={settingsData.lang}
              onChange={setLang}
              data={[
                {value: "ru", label: "RU"},
                {value: "en", label: "EN"},
              ]}
            />
          </Section>

          <Section className="mb-16" title={t("settings.appearance")}>
            <SegmentedControl
              fullWidth
              value={themeMode}
              onChange={(v) => setThemeMode(v as ThemeMode)}
              data={[
                {value: "auto", label: t("settings.auto")},
                {value: "light", label: t("settings.light")},
                {value: "dark", label: t("settings.dark")},
              ]}
            />
          </Section>

          <Collapse className="mb-16" title={t("settings.qb")}>
            <QbContent
              data={settingsData}
              cfg={cfg}
              onChangePass={() => setDialog("qbPass")}
              onGetTemp={qbTemp}
              onRestart={qbRestart}
            />
          </Collapse>

          <Collapse className="mb-16" title={t("settings.jackett")}>
            <JackettContent
              data={settingsData}
              cfg={cfg}
              onChangePass={() => setDialog("jackettPass")}
              onRemovePass={jackettRemovePass}
            />
          </Collapse>

          {settingsData.jellyfin.has_key && (
            <Collapse className="mb-16" title={t("settings.jellyfin")}>
              <JellyfinContent cfg={cfg} scanning={scanning} onScan={scan} onManageUsers={openUsers}/>
            </Collapse>
          )}

          <Collapse className="mb-16" title={t("settings.update")}>
            {updateInfo
              ? <UpdateContent info={updateInfo} onDone={reload}/>
              : <div style={{padding: "16px", textAlign: "center"}}><Loader size="sm"/></div>
            }
          </Collapse>

          <Text size="xs" c="dimmed" ta="center">
            {t("settings.version", {version: cfg.version})}
          </Text>
        </Stack>
      </Box>

      <Drawer
        opened={dialog === "users"}
        onClose={() => setDialog(null)}
        title={t("settings.jfUsers")}
        position="bottom"
        radius="lg"
        overlayProps={{blur: 2}}
      >
        <Stack gap={8} pb={16} px={4}>
          <ListSection>
            {users?.map((u) => (
              <ListItem
                key={u.id}
                after={
                  <Button
                    variant="subtle"
                    size="compact-sm"
                    px={4}
                    style={{color: DEL_COLOR}}
                    onClick={() => delUser(u)}
                  >
                    <Trash2 size={18}/>
                  </Button>
                }
              >
                {u.name}
              </ListItem>
            ))}
            {users?.length === 0 && (
              <ListItem>{t("settings.noUsers")}</ListItem>
            )}
          </ListSection>
          <Button fullWidth variant="dark" leftSection={<UserPlus size={18}/>}
                  onClick={() => setDialog("newUserName")}>
            {t("settings.addUser")}
          </Button>
        </Stack>
      </Drawer>

      <PromptSheet
        title={t("settings.qbPassTitle")}
        label={t("settings.newPass")}
        password
        open={dialog === "qbPass"}
        onSubmit={qbPass}
        onClose={() => setDialog(null)}
      />

      <PromptSheet
        title={t("settings.jackettPassTitle")}
        label={t("settings.newPassEmpty")}
        password
        submitText={t("common.save")}
        open={dialog === "jackettPass"}
        onSubmit={jackettPass}
        onClose={() => setDialog(null)}
      />

      <PromptSheet
        title={t("settings.newUser")}
        label={t("settings.username")}
        submitText={t("settings.next")}
        open={dialog === "newUserName"}
        onSubmit={(n) => {
          setNewUserName(n)
          setDialog("newUserPass")
        }}
        onClose={() => setDialog("users")}
      />

      <PromptSheet
        title={t("settings.passwordFor", {name: newUserName})}
        label={t("settings.password")}
        password
        open={dialog === "newUserPass"}
        onSubmit={addUser}
        onClose={() => setDialog("users")}
      />
    </Box>
  )
}
