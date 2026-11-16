// Typed path builders for the existing FastAPI routes (src/career_graph/web/app.py, llm_routes.py).
// Paths only: no fetching here. Each comment names the HTTP method(s) the route accepts.
const e = encodeURIComponent
type Id = string | number

export const endpoints = {
  sources: {
    list: () => '/api/sources', // GET
    remove: (source: string) => `/api/sources/${e(source)}`, // DELETE (204)
  },
  imports: {
    linkedin: () => '/api/import/linkedin', // POST
    text: () => '/api/import/text', // POST
    file: () => '/api/import/file', // POST (multipart)
  },
  job: {
    fetch: () => '/api/job/fetch', // POST
  },
  graph: {
    get: () => '/api/graph', // GET
  },
  facts: {
    list: () => '/api/facts', // GET
    create: () => '/api/facts', // POST (201)
    update: (factId: Id) => `/api/facts/${e(String(factId))}`, // PATCH
    reorder: (factId: Id) => `/api/facts/${e(String(factId))}/order`, // PATCH
  },
  duplicates: {
    list: () => '/api/duplicates', // GET
    dismiss: () => '/api/duplicates/dismiss', // POST
    merge: () => '/api/merges', // POST
  },
  templates: {
    list: () => '/api/templates', // GET
  },
  profile: {
    get: () => '/api/profile', // GET
  },
  documents: {
    render: () => '/api/documents/render', // POST
    check: () => '/api/documents/check', // POST
    preview: () => '/api/documents/preview', // POST
    suggest: () => '/api/documents/suggest', // POST
    resume: (fmt: string) => `/api/resume/${e(fmt)}`, // GET (file download)
    coverLetter: () => '/api/cover-letter', // POST (file response)
    fit: () => '/api/fit', // POST
  },
  savedDocuments: {
    list: () => '/api/saved-documents', // GET
    create: () => '/api/saved-documents', // POST (201)
    remove: (docId: Id) => `/api/saved-documents/${e(String(docId))}`, // DELETE (204)
    file: (docId: Id) => `/api/saved-documents/${e(String(docId))}/file`, // GET (attachment)
  },
  llm: {
    providers: () => '/api/llm/providers', // GET
    connections: () => '/api/llm/connections', // GET, POST (201)
    connection: (connId: Id) => `/api/llm/connections/${e(String(connId))}`, // PATCH, DELETE (204)
    active: () => '/api/llm/active', // PUT
    test: () => '/api/llm/test', // POST
  },
} as const
