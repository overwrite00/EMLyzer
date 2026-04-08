// src/api/client.js
import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 60000,
})

// Upload email file - returns { job_id, sha256, size_bytes, ... }
export async function uploadEmail(file) {
  const form = new FormData()
  form.append('file', file)
  const res = await api.post('/upload/', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return res.data
}

// Run full analysis on uploaded file
export async function runAnalysis(jobId, doWhois = true) {
  const res = await api.post(`/analysis/${jobId}?do_whois=${doWhois}`)
  return res.data
}

// Get existing analysis result
export async function getAnalysis(jobId) {
  const res = await api.get(`/analysis/${jobId}`)
  return res.data
}

// List all analyses
export async function listAnalyses({ q = "", risk = "", page = 1, pageSize = 25 } = {}) {
  const params = new URLSearchParams()
  if (q)        params.set("q", q)
  if (risk)     params.set("risk", risk)
  if (page > 1) params.set("page", page)
  if (pageSize !== 25) params.set("page_size", pageSize)
  const res = await api.get(`/analysis/?${params}`)
  return res.data
}

// Run reputation checks
export async function runReputation(jobId) {
  const res = await api.post(`/reputation/${jobId}`)
  return res.data
}

// Download report (returns blob URL)
export function getReportUrl(jobId) {
  return `/api/report/${jobId}`
}

// Health check
export async function healthCheck() {
  const res = await api.get('/health')
  return res.data
}

// Set backend language
export async function setLanguage(lang) {
  const res = await api.post('/settings/language', { language: lang })
  return res.data
}

// Analyze manually pasted email source
export async function analyzeManual(source, filename = 'manual_input.eml', doWhois = true) {
  const res = await api.post('/manual/', { source, filename, do_whois: doWhois })
  return res.data
}

// Delete an analysis (DB record + email file + report .docx)
export async function deleteAnalysis(jobId) {
  const res = await api.delete(`/analysis/${jobId}`)
  return res.data
}

// Update analyst notes
export async function updateNotes(jobId, notes) {
  const res = await api.patch(`/analysis/${jobId}/notes`, { notes })
  return res.data
}

// Get campaign clusters
export async function getCampaigns({ threshold = 0.6, minSize = 2 } = {}) {
  const res = await api.get(`/campaigns/?threshold=${threshold}&min_size=${minSize}`)
  return res.data
}

// Get app settings (includes which API keys are configured)
export async function getSettings() {
  const res = await api.get('/settings/')
  return res.data
}