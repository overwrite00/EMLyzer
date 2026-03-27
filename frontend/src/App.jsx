import './index.css'
import { LangProvider } from './i18n/LangContext'
import Dashboard from './pages/Dashboard'

export default function App() {
  return (
    <LangProvider>
      <Dashboard />
    </LangProvider>
  )
}
