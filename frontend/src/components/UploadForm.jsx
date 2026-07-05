import { useState } from 'react'

const API_URL = 'http://127.0.0.1:8000'

function UploadForm({ onUploaded }) {
  const [file, setFile] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  async function handleSubmit(event) {
    event.preventDefault()
    if (!file) return

    setLoading(true)
    setError(null)

    const formData = new FormData()
    formData.append('file', file)

    try {
      const response = await fetch(`${API_URL}/papers/upload`, {
        method: 'POST',
        body: formData,
      })

      if (!response.ok) {
        const body = await response.json()
        throw new Error(body.detail || 'Upload failed')
      }

      const data = await response.json()
      onUploaded(data, file)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col items-center gap-4 p-8">
      <h1 className="text-2xl font-semibold">Upload a research paper</h1>

      <input
        type="file"
        accept="application/pdf"
        onChange={(event) => setFile(event.target.files[0])}
        className="border rounded p-2"
      />

      <button
        type="submit"
        disabled={!file || loading}
        className="bg-blue-600 text-white px-4 py-2 rounded disabled:opacity-50"
      >
        {loading ? 'Processing...' : 'Upload'}
      </button>

      {error && <p className="text-red-600">{error}</p>}
    </form>
  )
}

export default UploadForm
