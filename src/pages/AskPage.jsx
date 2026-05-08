import { useState } from 'react'
import { apiPost } from '../services/api'

export default function AskPage({ askHistory, setAskHistory }) {
  const [question, setQuestion] = useState('')
  const [testQuestion, setTestQuestion] = useState('')
  const [testContext, setTestContext] = useState('')
  const [testResult, setTestResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [loadingTest, setLoadingTest] = useState(false)
  const [error, setError] = useState('')
  const [testError, setTestError] = useState('')

  const onSubmit = async (event) => {
    event.preventDefault()
    setLoading(true)
    setError('')
    try {
      const data = await apiPost('/kb/ask', { question })
      setAskHistory((prev) =>
        [
          {
            id: crypto.randomUUID(),
            question,
            answer: data.answer,
            sources: data.sources || [],
            needs_review: data.needs_review,
          },
          ...prev,
        ].slice(0, 7)
      )
      setQuestion('')
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const onTestSubmit = async (event) => {
    event.preventDefault()
    setLoadingTest(true)
    setTestError('')
    setTestResult(null)
    try {
      const data = await apiPost('/ai/answer_with_sources', {
        question: testQuestion,
        context: testContext,
      })
      setTestResult(data)
    } catch (e) {
      setTestError(e.message)
    } finally {
      setLoadingTest(false)
    }
  }

  return (
    <section>
      <h2>Задай вопрос системе знаний</h2>
      <form className="card form-grid" onSubmit={onSubmit}>
        <input
          placeholder="Ваш вопрос"
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          required
        />
        <button type="submit" disabled={loading}>
          {loading ? 'Спрашиваю...' : 'Спросить'}
        </button>
      </form>
      {error && <p className="error">{error}</p>}
      <div className="card">
        <h3>Ответы (последние 7 вопросов)</h3>
        {askHistory.length === 0 && <p className="hint">Пока нет ответов. Задайте первый вопрос.</p>}
        {askHistory.map((item) => (
          <div key={item.id} className="card">
            <p>
              <strong>Вопрос:</strong> {item.question}
            </p>
            <p>
              <strong>Ответ:</strong> {item.answer}
            </p>
            <h4>Цитаты-источники</h4>
            <ul className="list">
              {item.sources.map((source, idx) => (
                <li key={`${item.id}-${idx}`}>
                  {`Документ: ${source.document_id || source.filename || 'Не указан'} · Цитата: ${
                    source.quote
                  }`}
                </li>
              ))}
            </ul>
            {item.needs_review && <p className="badge warn">Требует проверки</p>}
          </div>
        ))}
      </div>

      <form className="card form-grid" onSubmit={onTestSubmit}>
        <h3>Качество ИИ (тестовый режим)</h3>
        <input
          placeholder="Вопрос для теста"
          value={testQuestion}
          onChange={(event) => setTestQuestion(event.target.value)}
          required
        />
        <textarea
          placeholder="Тестовый контекст"
          rows={6}
          value={testContext}
          onChange={(event) => setTestContext(event.target.value)}
          required
        />
        <button type="submit" disabled={loadingTest}>
          {loadingTest ? 'Проверяю...' : 'Проверить качество ИИ'}
        </button>
      </form>
      {testError && <p className="error">{testError}</p>}
      {testResult && (
        <div className="card">
          <div className="row">
            <h3>Тестовый ответ</h3>
            <span className={testResult.needs_review ? 'badge warn' : 'badge ok'}>
              confidence: {testResult.confidence}
            </span>
          </div>
          <p>{testResult.answer}</p>
          <h4>Цитаты</h4>
          <ul className="list">
            {testResult.sources.map((source, idx) => (
              <li key={idx}>{source.quote}</li>
            ))}
          </ul>
        </div>
      )}
    </section>
  )
}

