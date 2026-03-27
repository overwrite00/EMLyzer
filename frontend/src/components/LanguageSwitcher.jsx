// src/components/LanguageSwitcher.jsx
import { useLang } from '../i18n/LangContext'

export default function LanguageSwitcher() {
  const { lang, setLang } = useLang()

  return (
    <div style={{ display: 'flex', gap: 2, alignItems: 'center' }}>
      {['it', 'en'].map(l => (
        <button
          key={l}
          onClick={() => setLang(l)}
          style={{
            padding: '3px 10px',
            borderRadius: 4,
            border: `1px solid ${lang === l ? 'var(--accent-blue)' : 'var(--border)'}`,
            background: lang === l ? 'var(--accent-blue)' : 'transparent',
            color: lang === l ? '#fff' : 'var(--text-muted)',
            fontSize: 11,
            fontWeight: 600,
            cursor: 'pointer',
            textTransform: 'uppercase',
            letterSpacing: '0.05em',
            transition: 'all 0.15s',
          }}
        >
          {l}
        </button>
      ))}
    </div>
  )
}
