import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { initTelegram } from "./telegram";
import App from "./App";
import "./styles/globals.scss";

initTelegram();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
