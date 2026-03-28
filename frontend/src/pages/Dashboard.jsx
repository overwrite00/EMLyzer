// src/pages/Dashboard.jsx
import { useState, useEffect, useCallback, useRef } from 'react'
import { listAnalyses, getAnalysis } from '../api/client'
import UploadZone from '../components/UploadZone'
import AnalysisDetail from '../components/AnalysisDetail'
import LanguageSwitcher from '../components/LanguageSwitcher'
import { RiskBadge, Spinner } from '../components/ui'
import { useLang } from '../i18n/LangContext'
import CampaignsPanel from '../components/CampaignsPanel'

const RISK_LABELS = ['low', 'medium', 'high', 'critical']

// Debounce hook
function useDebounce(value, delay) {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), delay)
    return () => clearTimeout(t)
  }, [value, delay])
  return debounced
}

export default function Dashboard() {
  const { t } = useLang()
  const [analyses, setAnalyses]   = useState([])
  const [total, setTotal]         = useState(0)
  const [pages, setPages]         = useState(1)
  const [loading, setLoading]     = useState(true)
  const [selected, setSelected]   = useState(null)
  const [detailLoading, setDetailLoading] = useState(false)

  // Filtri
  const [searchQ, setSearchQ]     = useState('')
  const [riskFilter, setRiskFilter] = useState([])  // array di label selezionate
  const [page, setPage]           = useState(1)
  const PAGE_SIZE = 25

  const debouncedQ = useDebounce(searchQ, 350)

  const fetchList = useCallback(async () => {
    setLoading(true)
    try {
      const data = await listAnalyses({
        q: debouncedQ,
        risk: riskFilter.join(','),
        page,
        pageSize: PAGE_SIZE,
      })
      setAnalyses(data.items || [])
      setTotal(data.total || 0)
      setPages(data.pages || 1)
    } catch (_) {}
    finally { setLoading(false) }
  }, [debouncedQ, riskFilter, page])

  useEffect(() => { fetchList() }, [fetchList])

  // Reset pagina quando cambiano filtri
  useEffect(() => { setPage(1) }, [debouncedQ, riskFilter])

  async function openDetail(jobId) {
    setDetailLoading(true)
    try { setSelected(await getAnalysis(jobId)) }
    catch (_) {}
    finally { setDetailLoading(false) }
  }

  function onNewAnalysis(result) {
    setSelected(result)
    fetchList()
  }

  function toggleRisk(label) {
    setRiskFilter(prev =>
      prev.includes(label) ? prev.filter(l => l !== label) : [...prev, label]
    )
  }

  function exportCSV() {
    if (!analyses.length) return
    const headers = ['job_id','subject','from','date','risk_score','risk_label','filename']
    const rows = analyses.map(a => [
      a.job_id, `"${(a.subject||'').replace(/"/g,'""')}"`,
      `"${(a.from||'').replace(/"/g,'""')}"`, a.date||'',
      a.risk_score||'', a.risk_label||'', a.filename||''
    ])
    const csv = [headers.join(','), ...rows.map(r => r.join(','))].join('\n')
    const blob = new Blob([csv], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a'); a.href = url
    a.download = `emlyzer_analyses_${new Date().toISOString().slice(0,10)}.csv`
    a.click(); URL.revokeObjectURL(url)
  }

  const RISK_COLORS = {
    low: 'var(--risk-low)', medium: 'var(--risk-medium)',
    high: 'var(--risk-high)', critical: 'var(--risk-critical)',
  }

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg-primary)', display: 'flex', flexDirection: 'column' }}>
      {/* Navbar */}
      <header style={{
        display: 'flex', alignItems: 'center', gap: 12,
        padding: '12px 24px', borderBottom: '1px solid var(--border)',
        background: 'var(--bg-secondary)', position: 'sticky', top: 0, zIndex: 50,
      }}>
        <span style={{ fontSize: 20 }}>🔍</span>
        <span style={{ fontWeight: 700, fontSize: 16, letterSpacing: '0.02em' }}>EMLyzer</span>
        <span style={{
          marginLeft: 4, padding: '1px 8px', borderRadius: 4,
          background: 'var(--bg-card)', border: '1px solid var(--border)',
          fontSize: 10, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)',
        }}>v0.3.3</span>
        <div style={{ flex: 1 }} />
        <LanguageSwitcher />
      </header>

      <main style={{ flex: 1, padding: '24px', maxWidth: 1100, margin: '0 auto', width: '100%' }}>
        {/* Upload */}
        <section style={{ marginBottom: 32 }}>
          <h2 style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 12, letterSpacing: '0.06em', textTransform: 'uppercase' }}>
            {t('dash.analyze_title')}
          </h2>
          <UploadZone onAnalysisComplete={onNewAnalysis} />
        </section>

        {/* Campagne */}
        <CampaignsPanel />

        {/* Analisi recenti */}
        <section>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14, flexWrap: 'wrap', gap: 10 }}>
            <h2 style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-secondary)', letterSpacing: '0.06em', textTransform: 'uppercase' }}>
              {t('dash.recent_title')}
            </h2>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              {detailLoading && <Spinner size={16} />}
              {total > 0 && (
                <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>
                  {t('filter.total_results', { n: total })}
                </span>
              )}
            </div>
          </div>

          {/* Barra ricerca + filtri */}
          <div style={{
            display: 'flex', gap: 10, marginBottom: 12,
            flexWrap: 'wrap', alignItems: 'center',
          }}>
            {/* Ricerca */}
            <div style={{ position: 'relative', flex: 1, minWidth: 200 }}>
              <span style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)', fontSize: 13 }}>🔍</span>
              <input
                type="text"
                value={searchQ}
                onChange={e => setSearchQ(e.target.value)}
                placeholder={t('filter.search_placeholder')}
                style={{
                  width: '100%', padding: '7px 10px 7px 32px',
                  background: 'var(--bg-secondary)', border: '1px solid var(--border)',
                  borderRadius: 'var(--radius)', color: 'var(--text-primary)',
                  fontSize: 13, outline: 'none', boxSizing: 'border-box',
                }}
              />
              {searchQ && (
                <button onClick={() => setSearchQ('')} style={{
                  position: 'absolute', right: 8, top: '50%', transform: 'translateY(-50%)',
                  background: 'none', border: 'none', color: 'var(--text-muted)',
                  cursor: 'pointer', fontSize: 14, lineHeight: 1,
                }}>×</button>
              )}
            </div>

            {/* Filtri risk */}
            <div style={{ display: 'flex', gap: 5 }}>
              {RISK_LABELS.map(label => {
                const active = riskFilter.includes(label)
                return (
                  <button key={label} onClick={() => toggleRisk(label)} style={{
                    padding: '5px 12px', borderRadius: 20, fontSize: 11, fontWeight: 600,
                    cursor: 'pointer', letterSpacing: '0.04em', textTransform: 'uppercase',
                    border: `1px solid ${active ? RISK_COLORS[label] : 'var(--border)'}`,
                    background: active ? RISK_COLORS[label] + '22' : 'transparent',
                    color: active ? RISK_COLORS[label] : 'var(--text-muted)',
                    transition: 'all 0.15s',
                  }}>
                    {t(`filter.${label}`)}
                  </button>
                )
              })}
              {riskFilter.length > 0 && (
                <button onClick={() => setRiskFilter([])} style={{
                  padding: '5px 10px', borderRadius: 20, fontSize: 11,
                  background: 'none', border: '1px solid var(--border)',
                  color: 'var(--text-muted)', cursor: 'pointer',
                }}>✕</button>
              )}
            </div>

            {/* Export CSV */}
            <button onClick={exportCSV} disabled={!analyses.length} style={{
              padding: '6px 12px', borderRadius: 'var(--radius)', fontSize: 12,
              background: 'var(--bg-card)', border: '1px solid var(--border)',
              color: analyses.length ? 'var(--text-secondary)' : 'var(--text-muted)',
              cursor: analyses.length ? 'pointer' : 'not-allowed',
            }}>
              📥 {t('filter.export_csv')}
            </button>
          </div>

          {/* Tabella */}
          {loading ? (
            <div style={{ display: 'flex', justifyContent: 'center', padding: '40px 0' }}>
              <Spinner size={28} />
            </div>
          ) : analyses.length === 0 ? (
            <div style={{
              padding: '40px 24px', textAlign: 'center',
              color: 'var(--text-muted)', fontSize: 13,
              background: 'var(--bg-secondary)', borderRadius: 'var(--radius-lg)',
              border: '1px solid var(--border)',
            }}>
              {searchQ || riskFilter.length
                ? (t('filter.total_results', { n: 0 }))
                : t('dash.no_analyses')}
            </div>
          ) : (
            <>
              <div style={{
                background: 'var(--bg-secondary)', border: '1px solid var(--border)',
                borderRadius: 'var(--radius-lg)', overflow: 'hidden',
              }}>
                {/* Header */}
                <div style={{
                  display: 'grid', gridTemplateColumns: '1fr 170px 70px 80px 110px',
                  padding: '8px 16px', borderBottom: '1px solid var(--border)',
                  fontSize: 11, color: 'var(--text-muted)', fontWeight: 600,
                  letterSpacing: '0.05em', textTransform: 'uppercase',
                }}>
                  <span>{t('col.subject')}</span>
                  <span>{t('col.date')}</span>
                  <span>{t('col.file')}</span>
                  <span>{t('col.score')}</span>
                  <span>{t('col.risk')}</span>
                </div>

                {analyses.map((a, i) => (
                  <div key={a.job_id} onClick={() => openDetail(a.job_id)}
                    style={{
                      display: 'grid', gridTemplateColumns: '1fr 170px 70px 80px 110px',
                      padding: '11px 16px',
                      borderBottom: i < analyses.length - 1 ? '1px solid var(--border)' : 'none',
                      cursor: 'pointer', transition: 'background 0.12s',
                      alignItems: 'center', gap: 8,
                    }}
                    onMouseEnter={e => e.currentTarget.style.background = 'var(--bg-card)'}
                    onMouseLeave={e => e.currentTarget.style.background = ''}
                  >
                    <div style={{ minWidth: 0 }}>
                      <div style={{
                        fontWeight: 500, fontSize: 13,
                        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                        color: 'var(--text-primary)',
                      }}>
                        {/* Highlight search term */}
                        {searchQ
                          ? <HighlightedText text={a.subject || t('detail.no_subject')} query={searchQ} />
                          : (a.subject || t('detail.no_subject'))
                        }
                      </div>
                      <div style={{
                        fontSize: 11, color: 'var(--text-muted)',
                        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                      }}>
                        {searchQ
                          ? <HighlightedText text={a.from || '—'} query={searchQ} />
                          : (a.from || '—')
                        }
                      </div>
                    </div>
                    <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                      {a.analyzed_at ? new Date(a.analyzed_at).toLocaleString() : '—'}
                    </div>
                    <div style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                      {a.filename?.includes('manual') ? 'RAW' : a.filename?.split('.').pop()?.toUpperCase() || '—'}
                    </div>
                    <div style={{
                      fontSize: 13, fontWeight: 700, fontFamily: 'var(--font-mono)',
                      color: RISK_COLORS[a.risk_label] || 'var(--text-muted)',
                    }}>
                      {a.risk_score != null ? a.risk_score.toFixed(1) : '—'}
                    </div>
                    <RiskBadge label={a.risk_label || 'low'} />
                  </div>
                ))}
              </div>

              {/* Paginazione */}
              {pages > 1 && (
                <div style={{
                  display: 'flex', justifyContent: 'center', alignItems: 'center',
                  gap: 12, marginTop: 16,
                }}>
                  <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page <= 1}
                    style={paginBtn(page <= 1)}>
                    {t('filter.prev')}
                  </button>
                  <span style={{ color: 'var(--text-secondary)', fontSize: 13 }}>
                    {t('filter.page_of', { page, pages })}
                  </span>
                  <button onClick={() => setPage(p => Math.min(pages, p + 1))} disabled={page >= pages}
                    style={paginBtn(page >= pages)}>
                    {t('filter.next')}
                  </button>
                </div>
              )}
            </>
          )}
        </section>
      </main>

      {selected && <AnalysisDetail data={selected} onClose={() => setSelected(null)} />}
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  )
}

function paginBtn(disabled) {
  return {
    padding: '6px 16px', borderRadius: 'var(--radius)',
    background: 'var(--bg-card)', border: '1px solid var(--border)',
    color: disabled ? 'var(--text-muted)' : 'var(--text-primary)',
    cursor: disabled ? 'not-allowed' : 'pointer', fontSize: 12,
    opacity: disabled ? 0.5 : 1,
  }
}

// Evidenzia il termine di ricerca nel testo
function HighlightedText({ text, query }) {
  if (!query || !text) return text
  const idx = text.toLowerCase().indexOf(query.toLowerCase())
  if (idx < 0) return text
  return (
    <>
      {text.slice(0, idx)}
      <mark style={{ background: '#f59e0b33', color: 'var(--risk-medium)', borderRadius: 2 }}>
        {text.slice(idx, idx + query.length)}
      </mark>
      {text.slice(idx + query.length)}
    </>
  )
}