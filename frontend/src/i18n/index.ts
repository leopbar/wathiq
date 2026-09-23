import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import { LANG_KEY } from "@/lib/constants";
import en from "./locales/en.json";
import ar from "./locales/ar.json";

export type AppLang = "en" | "ar";

export function readStoredLang(): AppLang {
  try {
    return localStorage.getItem(LANG_KEY) === "ar" ? "ar" : "en";
  } catch {
    return "en";
  }
}

export function applyLang(lang: AppLang): void {
  document.documentElement.lang = lang;
  document.documentElement.dir = lang === "ar" ? "rtl" : "ltr";
  try {
    localStorage.setItem(LANG_KEY, lang);
  } catch {
    /* storage blocked */
  }
}

const initialLanguage = readStoredLang();
applyLang(initialLanguage);

void i18n.use(initReactI18next).init({
  resources: {
    en: { translation: en },
    ar: { translation: ar },
  },
  lng: initialLanguage,
  fallbackLng: "en",
  interpolation: { escapeValue: false },
  returnNull: false,
});

i18n.on("languageChanged", (language) => {
  applyLang(language.startsWith("ar") ? "ar" : "en");
});

export default i18n;
