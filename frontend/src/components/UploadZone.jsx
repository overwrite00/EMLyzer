// src/components/UploadZone.jsx
import { useState, useCallback } from 'react'
import { uploadEmail, runAnalysis, analyzeManual } from '../api/client'
import { Button, Spinner } from './ui'
import { useLang } from '../i18n/LangContext'

export default function UploadZone({ onAnalysisComplete }) {
  const { t } = useLang()
  const [tab, setTab]           = useState('file')
  const [dragging, setDragging] = useState(false)
  const [status, setStatus]     = useState('idle')
  const [message, setMessage]   = useState('')
  const [manualText, setManualText] = useState('')
  const [doWhois, setDoWhois]       = useState(false)

  const handleFile = useCallback(async (file) => {
    if (!file) return
    const ext = '.' + file.name.split('.').pop().toLowerCase()
    if (!['.eml', '.msg'].includes(ext)) {
      setStatus('error'); setMessage(t('upload.unsupported', { ext })); return
    }
    try {
      setStatus('uploading'); setMessage(t('upload.uploading'))
      const upload = await uploadEmail(file)
      setStatus('analyzing'); setMessage(t('upload.analyzing'))
      const result = await runAnalysis(upload.job_id, doWhois)
      setStatus('idle'); setMessage(''); onAnalysisComplete?.(result)
    } catch (err) {
      setStatus('error'); setMessage(err.response?.data?.detail || err.message || 'Error')
    }
  }, [onAnalysisComplete, t])

  const onDrop = useCallback((e) => {
    e.preventDefault(); setDragging(false); handleFile(e.dataTransfer.files[0])
  }, [handleFile])

  const handleManual = useCallback(async () => {
    if (!manualText.trim()) { setStatus('error'); setMessage(t('manual.empty_error')); return }
    try {
      setStatus('analyzing'); setMessage(t('manual.analyzing'))
      const result = await analyzeManual(manualText, "manual_input.eml", doWhois)
      setStatus('idle'); setMessage(''); setManualText(''); onAnalysisComplete?.(result)
    } catch (err) {
      setStatus('error'); setMessage(err.response?.data?.detail || err.message || 'Error')
    }
  }, [manualText, onAnalysisComplete, t])

  const busy = status === 'uploading' || status === 'analyzing'

  return (
    <div>
      <div style={{ display: 'flex', marginBottom: 12 }}>
        {[['file', t('manual.file_tab')], ['manual', t('manual.tab')]].map(([key, label]) => (
          <button key={key} onClick={() => { setTab(key); setStatus('idle') }} style={{
            padding: '7px 18px', background: 'none', border: 'none',
            borderBottom: `2px solid ${tab === key ? 'var(--accent-blue)' : 'transparent'}`,
            color: tab === key ? 'var(--text-primary)' : 'var(--text-muted)',
            cursor: 'pointer', fontSize: 13, fontWeight: tab === key ? 600 : 400,
          }}>{label}</button>
        ))}
      </div>

      {/* WHOIS toggle */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10, padding: '6px 10px', background: 'var(--bg-card)', borderRadius: 6, border: '1px solid var(--border)' }}>
        <input
          type="checkbox" id="whois-toggle"
          checked={doWhois} onChange={e => setDoWhois(e.target.checked)}
          style={{ cursor: 'pointer', accentColor: 'var(--accent-blue)' }}
        />
        <label htmlFor="whois-toggle" style={{ cursor: 'pointer', fontSize: 12, color: 'var(--text-secondary)', userSelect: 'none' }}>
          🌐 {t('upload.whois_toggle')}
        </label>
        <span style={{ fontSize: 11, color: 'var(--text-muted)', marginLeft: 4 }}>
          ({t('upload.whois_note')})
        </span>
      </div>

      {tab === 'file' && (
        <label onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
          onDragLeave={() => setDragging(false)} onDrop={onDrop}
          style={{
            display: 'flex', flexDirection: 'column', alignItems: 'center',
            justifyContent: 'center', gap: 12, padding: '36px 24px',
            borderRadius: 'var(--radius-lg)',
            border: `2px dashed ${dragging ? 'var(--accent-blue)' : busy ? 'var(--border-light)' : 'var(--border)'}`,
            background: dragging ? '#0f1f3d' : 'var(--bg-secondary)',
            cursor: busy ? 'not-allowed' : 'pointer', transition: 'all 0.15s', textAlign: 'center',
          }}>
          <input type="file" accept=".eml,.msg"
            onChange={e => { handleFile(e.target.files[0]); e.target.value = '' }}
            disabled={busy} style={{ display: 'none' }} />
          {busy
            ? <><Spinner size={32} /><div style={{ color: 'var(--text-secondary)', fontSize: 13 }}>{message}</div></>
            : <>
                <div style={{ fontSize: 36 }}>📧</div>
                <div style={{ color: 'var(--text-primary)', fontSize: 15, fontWeight: 500 }}>{t('upload.drag_title')}</div>
                <div style={{ color: 'var(--text-muted)', fontSize: 12 }}>{t('upload.drag_sub')} — {t('upload.max_size', { mb: 25 })}</div>
              </>
          }
        </label>
      )}

      {tab === 'manual' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <textarea value={manualText} onChange={e => setManualText(e.target.value)}
            placeholder={t('manual.placeholder')} disabled={busy} rows={12}
            style={{
              width: '100%', padding: '12px 14px',
              background: 'var(--bg-secondary)', border: '1px solid var(--border)',
              borderRadius: 'var(--radius)', color: 'var(--text-primary)',
              fontFamily: 'var(--font-mono)', fontSize: 12, lineHeight: 1.6,
              resize: 'vertical', outline: 'none', opacity: busy ? 0.6 : 1,
              boxSizing: 'border-box',
            }} />
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, alignItems: 'center' }}>
            {busy && <><Spinner size={16} /><span style={{ color: 'var(--text-muted)', fontSize: 12 }}>{message}</span></>}
            <Button onClick={handleManual} disabled={busy || !manualText.trim()} loading={busy}>
              🔍 {t('manual.analyze_btn')}
            </Button>
          </div>
        </div>
      )}

      {status === 'error' && (
        <div style={{
          marginTop: 10, padding: '10px 14px', borderRadius: 'var(--radius)',
          background: 'var(--risk-high-bg)', border: '1px solid var(--risk-high)',
          color: 'var(--risk-high)', fontSize: 13,
          display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12,
        }}>
          <span>{message}</span>
          <button onClick={() => setStatus('idle')} style={{ background:'none', border:'none', color:'inherit', cursor:'pointer', fontSize:16 }}>×</button>
        </div>
      )}
    </div>
  )
}
