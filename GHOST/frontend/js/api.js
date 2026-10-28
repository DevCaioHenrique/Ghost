// Camada única de acesso à API do GHOST.
export class ApiError extends Error {
  constructor(msg, status = 0, data = {}) { super(msg); this.status = status; this.data = data; }
}

async function req(method, url, body) {
  let r;
  try {
    r = await fetch(url, { method, headers: body ? { 'Content-Type': 'application/json' } : {}, body: body ? JSON.stringify(body) : undefined });
  } catch {
    throw new ApiError('Sem conexão com o servidor GHOST. Verifique se ele está em execução.');
  }
  if (r.status === 204) return null;
  const d = await r.json().catch(() => ({}));
  if (!r.ok) throw new ApiError(d.error || 'Falha na requisição.', r.status, d);
  return d;
}

const q = c => (c ? '?confirm=true' : '');
export const api = {
  collections: () => req('GET', '/api/collections'),
  createCollection: d => req('POST', '/api/collections', d),
  updateCollection: (id, d) => req('PATCH', `/api/collections/${id}`, d),
  deleteCollection: (id, c) => req('DELETE', `/api/collections/${id}${q(c)}`),
  addField: (cid, d) => req('POST', `/api/collections/${cid}/fields`, d),
  updateField: (id, d) => req('PATCH', `/api/fields/${id}`, d),
  deleteField: (id, c) => req('DELETE', `/api/fields/${id}${q(c)}`),
  records: (cid, p) => req('GET', `/api/collections/${cid}/records?${p}`),
  record: id => req('GET', `/api/records/${id}`),
  createRecord: (cid, d) => req('POST', `/api/collections/${cid}/records`, d),
  updateRecord: (id, d) => req('PATCH', `/api/records/${id}`, d),
  deleteRecord: id => req('DELETE', `/api/records/${id}`),
  search: s => req('GET', `/api/search?q=${encodeURIComponent(s)}`),
};
