// src/api/client.js
import axios from 'axios'

/**
 * Axios instance for API calls.
 * Base URL: /api (resolved relative to current host)
 * Timeout: 60s (overridden for long-running operations like analysis)
 */
const api = axios.create({
  baseURL: '/api',
  timeout: 60000,
})

/**
 * Upload email file for analysis.
 * @param {File} file - Email file (.eml or .msg)
 * @returns {Promise<{job_id: string, sha256: string, size_bytes: number}>} Analysis job ID and metadata
 */
export async function uploadEmail(file) {
  const form = new FormData()
  form.append('file', file)
  const res = await api.post('/upload/', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return res.data
}

/**
 * Run full analysis pipeline on uploaded email.
 * Timeout 300s: emails with 40+ URLs can take ~55s for URL analysis with WHOIS deduplication.
 * @param {string} jobId - UUID of uploaded email
 * @param {boolean} [doWhois=true] - Whether to perform WHOIS lookups for domains
 * @returns {Promise<Object>} Complete analysis result with risk score, headers, body, URLs, attachments, reputation
 */
export async function runAnalysis(jobId, doWhois = true) {
  const res = await api.post(`/analysis/${jobId}?do_whois=${doWhois}`, null, {
    timeout: 300000,
  })
  return res.data
}

/**
 * Retrieve previously completed analysis result.
 * @param {string} jobId - UUID of analysis
 * @returns {Promise<Object>} Complete analysis result
 */
export async function getAnalysis(jobId) {
  const res = await api.get(`/analysis/${jobId}`)
  return res.data
}

/**
 * List all analyses with optional filtering.
 * @param {Object} [options={}] - Filter options
 * @param {string} [options.q=""] - Full-text search (subject, from, filename)
 * @param {string} [options.risk=""] - Filter by risk: low, medium, high, critical
 * @param {number} [options.page=1] - Page number (1-indexed)
 * @param {number} [options.pageSize=25] - Results per page
 * @returns {Promise<Object>} Paginated list of analyses
 */
export async function listAnalyses({ q = "", risk = "", page = 1, pageSize = 25 } = {}) {
  const params = new URLSearchParams()
  if (q)        params.set("q", q)
  if (risk)     params.set("risk", risk)
  if (page > 1) params.set("page", page)
  if (pageSize !== 25) params.set("page_size", pageSize)
  const res = await api.get(`/analysis/?${params}`)
  return res.data
}

/**
 * Run reputation checks (FAST services).
 * SLOW services (VirusTotal, AbuseIPDB) execute in background.
 * Poll getAnalysis() to see when reputation_phase="complete".
 * @param {string} jobId - UUID of analysis
 * @returns {Promise<Object>} Reputation results from FAST services
 */
export async function runReputation(jobId) {
  const res = await api.post(`/reputation/${jobId}`)
  return res.data
}

/**
 * Get URL to download report PDF.
 * @param {string} jobId - UUID of analysis
 * @returns {string} Report download URL (/api/report/{jobId})
 */
export function getReportUrl(jobId) {
  return `/api/report/${jobId}`
}

/**
 * Health check and version info.
 * @returns {Promise<Object>} {status, version, app}
 */
export async function healthCheck() {
  const res = await api.get('/health')
  return res.data
}

/**
 * Change UI language.
 * @param {string} lang - Language code: 'it' (Italian) or 'en' (English)
 * @returns {Promise<Object>} Updated settings
 */
export async function setLanguage(lang) {
  const res = await api.post('/settings/language', { language: lang })
  return res.data
}

/**
 * Analyze manually pasted email source (RFC 2822).
 * Timeout 300s (same as runAnalysis).
 * @param {string} source - Raw RFC 2822 email source
 * @param {string} [filename='manual_input.eml'] - Display name for this email
 * @param {boolean} [doWhois=true] - Whether to perform WHOIS lookups
 * @returns {Promise<Object>} Complete analysis result (same as runAnalysis)
 */
export async function analyzeManual(source, filename = 'manual_input.eml', doWhois = true) {
  const res = await api.post('/manual/', { source, filename, do_whois: doWhois }, {
    timeout: 300000,
  })
  return res.data
}

/**
 * Delete analysis (DB record + email file + report .docx).
 * @param {string} jobId - UUID of analysis to delete
 */
export async function deleteAnalysis(jobId) {
  const res = await api.delete(`/analysis/${jobId}`)
  return res.data
}

// Bulk delete analyses (DB records + files)
export async function deleteBulkAnalyses(jobIds) {
  const res = await api.post('/analysis/bulk-delete', { job_ids: jobIds })
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

// Get email body content (text + sanitized HTML for preview)
export async function getEmailBody(jobId) {
  const res = await api.get(`/analysis/${jobId}/body`)
  return res.data
}