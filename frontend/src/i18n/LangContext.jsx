// src/i18n/LangContext.jsx
import { createContext, useContext, useState, useCallback } from 'react'
import { createT } from './translations'
import { setLanguage as apiSetLanguage } from '../api/client'

const LangContext = createContext(null)

export function LangProvider({ children }) {
  const [lang, setLangState] = useState(() => {
    return localStorage.getItem('emlyzer_lang') || 'it'
  })

  const t = createT(lang)

  const setLang = useCallback(async (newLang) => {
    setLangState(newLang)
    localStorage.setItem('emlyzer_lang', newLang)
    try {
      await apiSetLanguage(newLang)
    } catch {
      // Intentional: silence API error, language already set locally
    }
  }, [])

  return (
    <LangContext.Provider value={{ lang, setLang, t }}>
      {children}
    </LangContext.Provider>
  )
}

// eslint-disable-next-line react-refresh/only-export-components
export function useLang() {
  return useContext(LangContext)
}
