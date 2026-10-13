// Vite embeds VITE_* variables into the browser bundle. Never put secrets here.
export const API_URL = (import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000').replace(/\/+$/, '')
