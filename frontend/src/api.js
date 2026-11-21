import axios from 'axios'

export const api = axios.create({
  baseURL: '/api',
  withCredentials: true,
  headers: { 'Content-Type': 'application/json' },
})

/** The server's message for a failed request, for showing to the cook. */
export function errorMessage(err, fallback = 'Something went wrong.') {
  const detail = err?.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) return detail.map((d) => d.msg).join('; ')
  return fallback
}

export const methods = {
  instapot: 'Instant Pot',
  crockpot: 'Crockpot',
  'stovetop-oven': 'Stovetop & Oven',
  other: 'Other',
}
