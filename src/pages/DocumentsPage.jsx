import { useEffect, useState } from 'react'
import { apiDelete, apiGet, apiPost, apiUploadFile, apiUploadUrl } from '../services/api'

export default function DocumentsPage({ documents, setDocuments }) {
  const [title, setTitle] = useState('')
  const [text, setText] = useState('')
  const [selectedFile, setSelectedFile] = useState(null)
  const [url, setUrl] = useState('')
  const [urlTitle, setUrlTitle] = useState('')
  const [loading, setLoading] = useState(false)
  const [loadingFile, setLoadingFile] = useState(false)
  const [loadingUrl, setLoadingUrl] = useState(false)
  const [selectedFileName, setSelectedFileName] = useState('')
  const [fileStatus, setFileStatus] = useState(null)
  const [loadingDocuments, setLoadingDocuments] = useState(false)
  const [clearingDocuments, setClearingDocuments] = useState(false)
  const [error, setError] = useState('')

  const loadDocuments = async () => {
    setLoadingDocuments(true)
    setError('')
    try {
      const data = await apiGet('/kb/documents')
      setDocuments(data)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoadingDocuments(false)
    }
  }

  useEffect(() => {
    void loadDocuments()
  }, [])

  const onSubmit = async (event) => {
    event.preventDefault()
    setLoading(true)
    setError('')
    try {
      await apiPost('/kb/documents', { title, text })
      setTitle('')
      setText('')
      await loadDocuments()
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const onFileSelect = async (event) => {
    const file = event.target.files?.[0]
    if (!file) {
      return
    }
    setSelectedFile(file)
    setSelectedFileName(file.name)
    setError('')
    setFileStatus(null)
  }

  const onFileSubmit = async (event) => {
    event.preventDefault()
    if (!selectedFile) {
      setError('Сначала выберите файл')
      return
    }
    setError('')
    setFileStatus(null)
    setLoadingFile(true)
    try {
      const result = await apiUploadFile(selectedFile)
      setFileStatus(result)
      setSelectedFile(null)
      setSelectedFileName('')
      await loadDocuments()
    } catch (e) {
      setError(`Не удалось загрузить файл: ${e.message}`)
    } finally {
      setLoadingFile(false)
    }
  }

  const onUrlSubmit = async (event) => {
    event.preventDefault()
    setError('')
    setFileStatus(null)
    setLoadingUrl(true)
    try {
      const result = await apiUploadUrl(url, urlTitle)
      setFileStatus(result)
      setUrl('')
      setUrlTitle('')
      await loadDocuments()
    } catch (e) {
      setError(`Не удалось загрузить URL: ${e.message}`)
    } finally {
      setLoadingUrl(false)
    }
  }

  const onClearDocuments = async () => {
    const shouldClear = window.confirm(
      'Очистить список документов? Это удалит документы из SQLite и индексы поиска.'
    )
    if (!shouldClear) {
      return
    }
    setError('')
    setClearingDocuments(true)
    try {
      await apiDelete('/kb/documents')
      setDocuments([])
      setFileStatus(null)
      await loadDocuments()
    } catch (e) {
      setError(`Не удалось очистить список документов: ${e.message}`)
    } finally {
      setClearingDocuments(false)
    }
  }

  return (
    <section>
      <div className="card">
        <div className="row">
          <h3>Список документов</h3>
          <button type="button" onClick={onClearDocuments} disabled={clearingDocuments}>
            {clearingDocuments ? 'Очищаю...' : 'Очистить список'}
          </button>
        </div>
        {loadingDocuments && <p className="hint">Обновляю список документов...</p>}
        <table>
          <thead>
            <tr>
              <th>Название</th>
              <th>Дата</th>
              <th>Document ID</th>
            </tr>
          </thead>
          <tbody>
            {documents.map((doc) => (
              <tr key={doc.id}>
                <td>{doc.title}</td>
                <td>{doc.created_at}</td>
                <td>{doc.id}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {fileStatus && (
        <div className="card">
          <p>{fileStatus.message}</p>
          <p>{fileStatus.summary}</p>
        </div>
      )}
      <form className="card form-grid" onSubmit={onFileSubmit}>
        <label className="form-grid">
          Прикрепить документ
          <input type="file" onChange={onFileSelect} disabled={loadingFile} />
        </label>
        <p className="hint">
          {selectedFileName
            ? `Выбран файл "${selectedFileName}".`
            : 'Выберите файл и нажмите "Добавить файл".'}
        </p>
        <button type="submit" disabled={loadingFile || !selectedFile}>
          {loadingFile ? 'Загружаю файл...' : 'Добавить файл'}
        </button>
      </form>

      <form className="card form-grid" onSubmit={onSubmit}>
        <input
          placeholder="Название документа"
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          required
        />
        <textarea
          placeholder="Текст"
          rows={6}
          value={text}
          onChange={(event) => setText(event.target.value)}
          required
        />
        <button type="submit" disabled={loading}>
          {loading ? 'Сохраняю...' : 'Добавить текст'}
        </button>
      </form>
      <form className="card form-grid" onSubmit={onUrlSubmit}>
        <h3>Загрузка URL-страницы</h3>
        <input
          type="url"
          placeholder="https://example.com/page"
          value={url}
          onChange={(event) => setUrl(event.target.value)}
          disabled={loadingUrl}
          required
        />
        <input
          placeholder="Название (опционально)"
          value={urlTitle}
          onChange={(event) => setUrlTitle(event.target.value)}
          disabled={loadingUrl}
        />
        <button type="submit" disabled={loadingUrl}>
          {loadingUrl ? 'Загружаю URL...' : 'Добавить URL-страницу'}
        </button>
      </form>
      {error && <p className="error">{error}</p>}
    </section>
  )
}

