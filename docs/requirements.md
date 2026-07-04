# Requirements — Research Paper Assistant

## Project Statement

Research Paper Assistant is an AI-powered application that allows users to
upload scientific papers and interact with them through natural language for
summarization, question answering, comparison, and literature analysis.

## MVP Scope

### In scope
- Upload research paper PDF
- Extract text/structure
- Ask questions (RAG-based Q&A)
- Generate summaries
- Show citations (section/page grounding)

### Out of scope (post-MVP)
- Multi-agent system
- LangGraph orchestration
- Authentication / user accounts
- Deployment (cloud hosting, CI/CD)
- Multi-user collaboration

## Functional Requirements

| ID  | Requirement |
|-----|-------------|
| FR1 | User can upload PDF papers |
| FR2 | System extracts structured content (sections, pages) |
| FR3 | User can ask questions about an uploaded paper |
| FR4 | System provides grounded answers with citations |
| FR5 | System can generate a summary of an uploaded paper |

## Non-Functional Requirements

| ID   | Requirement |
|------|-------------|
| NFR1 | Answer latency < 5s |
| NFR2 | Answers must cite sources (section/page) |
| NFR3 | System should support PDFs up to 50MB |
| NFR4 | System should degrade gracefully on malformed/unparsable PDFs |

## Open Questions (to resolve before/while building)
- [ ] What counts as a "grounded" answer for evaluation purposes?
- [ ] Single paper per session for MVP, or multiple papers loaded at once?
- [ ] What happens if Docling fails to parse a PDF (scanned/image-only PDFs)?
