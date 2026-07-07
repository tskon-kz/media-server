import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import { Provider } from "react-redux"
import { MantineProvider } from "@mantine/core"
import { Notifications } from "@mantine/notifications"
import "@mantine/core/styles.css"
import "@mantine/notifications/styles.css"
import "./i18n"
import { initTelegram } from "./telegram"
import { ThemeSync, useTheme } from "./theme"
import { mantineTheme, cssVariablesResolver } from "./mantineTheme"
import { store } from "./store"
import App from "./App"
import "./styles/globals.scss"

initTelegram()

function Root() {
  const { appearance } = useTheme()
  return (
    <MantineProvider
      theme={mantineTheme}
      cssVariablesResolver={cssVariablesResolver}
      forceColorScheme={appearance}
    >
      <Notifications position="bottom-center" containerWidth={480} zIndex={1000} />
      <ThemeSync />
      <App />
    </MantineProvider>
  )
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <Provider store={store}>
      <Root />
    </Provider>
  </StrictMode>,
)
