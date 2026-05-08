import { useEffect, useState } from 'react'
import { NavLink, Route, Routes } from 'react-router-dom'
import './App.css'
import AskPage from './pages/AskPage'
import DocumentsPage from './pages/DocumentsPage'
import HistoryPage from './pages/HistoryPage'

const ASK_HISTORY_STORAGE_KEY = 'team-memory:ask-history'

function loadAskHistoryFromStorage() {
  if (typeof window === 'undefined') {
    return []
  }
  try {
    const raw = window.localStorage.getItem(ASK_HISTORY_STORAGE_KEY)
    if (!raw) {
      return []
    }
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) {
      return []
    }
    return parsed.slice(0, 7)
  } catch {
    return []
  }
}

function App() {
  const [documentsCache, setDocumentsCache] = useState([])
  const [askHistoryCache, setAskHistoryCache] = useState(loadAskHistoryFromStorage)

  useEffect(() => {
    if (typeof window === 'undefined') {
      return
    }
    window.localStorage.setItem(ASK_HISTORY_STORAGE_KEY, JSON.stringify(askHistoryCache))
  }, [askHistoryCache])

  return (
    <div className="app-shell">
      <header>
        <div className="brand-block">
          <p className="company-name">Nexora Systems</p>
          <h1>Система знаний команды</h1>
        </div>
        <nav>
          <NavLink to="/">Документы</NavLink>
          <NavLink to="/ask">Спросить</NavLink>
          <NavLink to="/history">История</NavLink>
        </nav>
      </header>
      <main>
        <Routes>
          <Route
            path="/"
            element={
              <DocumentsPage
                documents={documentsCache}
                setDocuments={setDocumentsCache}
              />
            }
          />
          <Route
            path="/ask"
            element={<AskPage askHistory={askHistoryCache} setAskHistory={setAskHistoryCache} />}
          />
          <Route path="/history" element={<HistoryPage />} />
        </Routes>
      </main>
    </div>
  )
}

export default App
