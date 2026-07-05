import { useState } from 'react'
import UploadForm from './components/UploadForm'
import ChatView from './components/ChatView'
import './index.css'

function App() {
  const [paper, setPaper] = useState(null)
  const [file, setFile] = useState(null)

  function handleUploaded(data, uploadedFile) {
    setPaper(data)
    setFile(uploadedFile)
  }

  function handleReset() {
    setPaper(null)
    setFile(null)
  }

  if (paper && file) {
    return <ChatView paper={paper} file={file} onReset={handleReset} />
  }

  return <UploadForm onUploaded={handleUploaded} />
}

export default App
