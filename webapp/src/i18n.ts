import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import en from "./locales/en";
import ru from "./locales/ru";

const savedLang = localStorage.getItem("lang");
const initialLang = savedLang === "ru" || savedLang === "en" ? savedLang : "en";

i18n.use(initReactI18next).init({
  resources: {
    en: { translation: en },
    ru: { translation: ru },
  },
  lng: initialLang,
  fallbackLng: "en",
  interpolation: { escapeValue: false },
});

export function setAppLanguage(lang: string) {
  i18n.changeLanguage(lang);
  localStorage.setItem("lang", lang);
}

export default i18n;
