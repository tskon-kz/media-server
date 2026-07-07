import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { MantineProvider } from "@mantine/core";
import { Notifications } from "@mantine/notifications";
import "@mantine/core/styles.css";
import "@mantine/notifications/styles.css";
import "./i18n";
import { initTelegram } from "./telegram";
import { ThemeProvider, useTheme } from "./theme";
import { mantineTheme, cssVariablesResolver } from "./mantineTheme";
import App from "./App";
import "./styles/globals.scss";

initTelegram();

function Root() {
  const { appearance } = useTheme();
  return (
    <MantineProvider
      theme={mantineTheme}
      cssVariablesResolver={cssVariablesResolver}
      forceColorScheme={appearance}
    >
      <Notifications position="bottom-center" containerWidth={480} zIndex={1000} />
      <App />
    </MantineProvider>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ThemeProvider>
      <Root />
    </ThemeProvider>
  </StrictMode>,
);
