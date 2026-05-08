import { useEffect, useState } from 'react'
import { apiGet } from '../services/api'

export default function HistoryPage() {
  const [rows, setRows] = useState([])
  const [onlyReview, setOnlyReview] = useState(false)
  const [selectedRow, setSelectedRow] = useState(null)
  const [error, setError] = useState('')

  const loadHistory = async (flag) => {
    setError('')
    try {
      const suffix = flag ? '?needs_review=true' : ''
      const data = await apiGet(`/kb/history${suffix}`)
      setRows(data)
      setSelectedRow(null)
    } catch (e) {
      setError(e.message)
    }
  }

  useEffect(() => {
    void loadHistory(onlyReview)
  }, [onlyReview])

  return (
    <section>
      <h2>История запросов</h2>
      <label className="checkbox">
        <input
          type="checkbox"
          checked={onlyReview}
          onChange={(event) => setOnlyReview(event.target.checked)}
        />
        Требует проверки
      </label>
      {error && <p className="error">{error}</p>}
      <div className="card">
        <table>
          <thead>
            <tr>
              <th>Создано</th>
              <th>Вопрос</th>
              <th>Требует проверки</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr
                key={row.id}
                className={selectedRow?.id === row.id ? 'clickable-row active' : 'clickable-row'}
                onClick={() => setSelectedRow(row)}
              >
                <td>{row.created_at}</td>
                <td>{row.question}</td>
                <td>{row.needs_review ? 'Да' : 'Нет'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {selectedRow && (
        <div className="card">
          <h3>Детали записи #{selectedRow.id}</h3>
          <p>
            <strong>Вопрос:</strong> {selectedRow.question}
          </p>
          <p>
            <strong>Требует проверки:</strong> {selectedRow.needs_review ? 'Да' : 'Нет'}
          </p>
          <p>
            <strong>Причина проверки:</strong> {selectedRow.review_reason ?? '—'}
          </p>
          <p>
            <strong>Ответ:</strong> {selectedRow.answer}
          </p>
          <p>
            <strong>Источники:</strong>
          </p>
          <ul className="list">
            {selectedRow.sources?.map((source, idx) => (
              <li key={idx}>
                {`Документ: ${source.document_id || source.filename || 'Не указан'} · Цитата: ${
                  source.quote
                }`}
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  )
}

