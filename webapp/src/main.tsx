import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { AppRoot } from "@telegram-apps/telegram-ui";
import "@telegram-apps/telegram-ui/dist/styles.css";
import { initTelegram } from "./telegram";
import { ThemeProvider, useTheme } from "./theme";
import App from "./App";
import "./styles/globals.scss";

initTelegram();

function Root() {
  const { appearance } = useTheme();
  return (
    <AppRoot appearance={appearance} style={{ height: "100%" }}>
      <App />
    </AppRoot>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ThemeProvider>
      <Root />
    </ThemeProvider>
  </StrictMode>,
);
