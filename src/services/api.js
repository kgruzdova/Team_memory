const API_BASE = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000'

async function assertOk(response, method, path) {
  if (!response.ok) {
    throw new Error(`${method} ${path} failed: ${response.status}`)
  }
}

export async function apiGet(path) {
  const response = await fetch(`${API_BASE}${path}`)
  await assertOk(response, 'GET', path)
  return response.json()
}

export async function apiPost(path, payload) {
  const response = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  await assertOk(response, 'POST', path)
  return response.json()
}

export async function apiDelete(path) {
  const response = await fetch(`${API_BASE}${path}`, {
    method: 'DELETE',
  })
  await assertOk(response, 'DELETE', path)
  return response.json()
}

export async function apiUploadFile(file) {
  const formData = new FormData()
  formData.append('file', file)
  const response = await fetch(`${API_BASE}/kb/files`, {
    method: 'POST',
    body: formData,
  })
  await assertOk(response, 'FILE', '/kb/files')
  return response.json()
}

export async function apiUploadUrl(url, title) {
  const response = await fetch(`${API_BASE}/kb/urls`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url, title: title || null }),
  })
  await assertOk(response, 'POST', '/kb/urls')
  return response.json()
}

