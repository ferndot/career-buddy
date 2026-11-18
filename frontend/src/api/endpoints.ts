// Typed path builders for the existing FastAPI routes (src/career_buddy/web/app.py, llm_routes.py).
// Paths only: no fetching here. Each comment names the HTTP method(s) the route accepts.
const e = encodeURIComponent
type Id = string | number

export const endpoints = {
  sources: {
    list: () => '/api/sources', // GET
    remove: (source: string) => `/api/sources/${e(source)}`, // DELETE (204)
    log: (source: string) => `/api/sources/${e(source)}/log`, // GET ?since=<cursor>
  },
  imports: {
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
    remove: (factId: Id) => `/api/facts/${e(String(factId))}`, // DELETE (204)
    reorder: (factId: Id) => `/api/facts/${e(String(factId))}/order`, // PATCH
  },
  links: {
    add: () => '/api/links', // POST {source_id, target_id, kind} (201)
    remove: (sourceId: Id, targetId: Id, kind: string) =>
      `/api/links?source_id=${e(String(sourceId))}&target_id=${e(String(targetId))}&kind=${e(kind)}`, // DELETE (204)
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
    generate: () => '/api/documents/generate', // POST
    resume: (fmt: string) => `/api/resume/${e(fmt)}`, // GET (file download)
    fit: () => '/api/fit', // POST
  },
  savedDocuments: {
    list: () => '/api/saved-documents', // GET
    create: () => '/api/saved-documents', // POST (201)
    content: (docId: Id) => `/api/saved-documents/${e(String(docId))}/content`, // GET: {html, css, slots, source}
    remove: (docId: Id) => `/api/saved-documents/${e(String(docId))}`, // DELETE (204)
    file: (docId: Id, format: string) => `/api/saved-documents/${e(String(docId))}/file?format=${e(format)}`, // GET (attachment); format docx|pdf|txt
  },
  llm: {
    providers: () => '/api/llm/providers', // GET
    connections: () => '/api/llm/connections', // GET, POST (201)
    connection: (connId: Id) => `/api/llm/connections/${e(String(connId))}`, // PATCH, DELETE (204)
    active: () => '/api/llm/active', // PUT
    test: () => '/api/llm/test', // POST
  },
  writing: {
    rules: () => '/api/writing/rules', // GET
    kind: (kind: 'resume' | 'letter') => `/api/writing/rules/${kind}`, // PUT, DELETE (204)
    strictness: () => '/api/writing/strictness', // GET, PUT
  },
} as const
