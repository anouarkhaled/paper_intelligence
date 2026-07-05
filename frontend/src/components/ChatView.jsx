import { useMemo, useState } from 'react'

const API_URL = 'http://127.0.0.1:8000'

function ChatView({ paper, file, onReset }) {
  const [messages, setMessages] = useState([])
  const [question, setQuestion] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  // Recomputed only when `file` changes, not on every render — creating
  // an object URL repeatedly would leak memory (each one stays alive
  // until explicitly revoked).
  const fileUrl = useMemo(() => URL.createObjectURL(file), [file])

  async function handleSend(event) {
    event.preventDefault()
    if (!question.trim()) return

    setLoading(true)
    setError(null)

    try {
      const response = await fetch(`${API_URL}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ paper_id: paper.paper_id, question }),
      })

      if (!response.ok) {
        const body = await response.json()
        throw new Error(body.detail || 'Chat request failed')
      }

      const data = await response.json()
      setMessages((prev) => [...prev, { question, answer: data.answer, citations: data.citations }])
      setQuestion('')
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex h-screen">
      <div className="w-1/2 border-r">
        <iframe src={fileUrl} title="Paper preview" className="w-full h-full" />
      </div>

      <div className="w-1/2 flex flex-col p-4">
        <div className="flex justify-between items-center mb-4">
          <div>
            <h2 className="font-semibold">{paper.filename}</h2>
            <p className="text-sm text-gray-500">
              {paper.num_pages} pages · {paper.num_chunks} chunks
            </p>
          </div>
          <button onClick={onReset} className="text-sm text-blue-600">
            Upload another
          </button>
        </div>

        <div className="flex-1 overflow-y-auto space-y-4 mb-4">
          {messages.map((message, i) => (
            <div key={i} className="space-y-1">
              <p className="font-medium">{message.question}</p>
              <p>{message.answer}</p>
              {message.citations.length > 0 && (
                <ul className="text-sm text-gray-500">
                  {message.citations.map((citation, j) => (
                    <li key={j}>
                      {citation.section} — page {citation.page}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ))}
        </div>

        {error && <p className="text-red-600 mb-2">{error}</p>}

        <form onSubmit={handleSend} className="flex gap-2">
          <input
            type="text"
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder="Ask a question about this paper..."
            className="flex-1 border rounded p-2"
          />
          <button
            type="submit"
            disabled={loading || !question.trim()}
            className="bg-blue-600 text-white px-4 py-2 rounded disabled:opacity-50"
          >
            {loading ? '...' : 'Send'}
          </button>
        </form>
      </div>
    </div>
  )
}

export default ChatView
