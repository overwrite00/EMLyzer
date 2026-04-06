// src/components/AnalysisDetail.jsx
import { useState, useRef, useEffect, useCallback } from 'react'
import { runReputation, getReportUrl, updateNotes, getAnalysis } from '../api/client'
import { Section, KeyValue, FindingRow, EmptyState, Button, SeverityBadge } from './ui'
import RiskMeter from './RiskMeter'
import { useLang } from '../i18n/LangContext'
import TabReputation from './TabReputation'

export default function AnalysisDetail({ data, onClose }) {
  const { t, lang } = useLang()
  const TABS = [
    t('detail.tab_summary'), t('detail.tab_header'), t('detail.tab_body'),
    t('detail.tab_url'), t('detail.tab_attachments'), t('detail.tab_reputation'),
  ]
  const [tab, setTab]             = useState(0)
  const [repLoading, setRepLoading] = useState(false)
  const [repData, setRepData]     = useState(null)
  const [repError, setRepError]   = useState('')
  const pollRef = useRef(null)
  const [notes, setNotes]         = useState(data?.analyst_notes || '')
  const [notesSaving, setNotesSaving] = useState(false)
  const [notesSaved, setNotesSaved]   = useState(false)

  if (!data) return null
  const { email, risk, header_analysis, body_analysis, url_analysis, attachment_analysis } = data

  async function handleReputation() {
    setRepLoading(true); setRepError('')
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null }
    try {
      // Fase 1: chiama POST /api/reputation/{id} → risultati fast (<15s)
      const result = await runReputation(data.job_id)
      setRepData(result)

      // Fase 2: se ci sono servizi slow (VT/AbuseIPDB/crt.sh) avvia polling
      if (result.slow_running) {
        pollRef.current = setInterval(async () => {
          try {
            // GET /api/analysis/{id} ora include reputation_results col campo reputation_phase
            const updated = await getAnalysis(data.job_id)
            const rep = updated?.reputation_results
            if (!rep) return  // non ancora disponibile, riprova

            if (rep.reputation_phase === 'complete') {
              // Fase 2 completata: aggiorna tutto il repData con i risultati finali
              setRepData({
                job_id:           data.job_id,
                phase:            'complete',
                slow_running:     false,
                reputation_score: rep.reputation_score ?? 0,
                malicious_count:  rep.malicious_count  ?? 0,
                service_registry: rep.service_registry ?? [],
                results:          rep,
              })
              clearInterval(pollRef.current)
              pollRef.current = null
            }
          } catch (_) { /* polling silenzioso */ }
        }, 5000)  // ogni 5 secondi
      }
    } catch (err) {
      setRepError(err.response?.data?.detail || err.message || 'Errore sconosciuto')
    } finally {
      setRepLoading(false)
    }
  }

  // Cleanup polling allo smontaggio
  useEffect(() => () => { if (pollRef.current) clearInterval(pollRef.current) }, [])

  async function handleSaveNotes() {
    setNotesSaving(true); setNotesSaved(false)
    try {
      await updateNotes(data.job_id, notes)
      setNotesSaved(true)
      setTimeout(() => setNotesSaved(false), 2500)
    } catch (_) {}
    finally { setNotesSaving(false) }
  }

  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.75)',
      zIndex: 100, display: 'flex', alignItems: 'flex-start',
      justifyContent: 'center', overflowY: 'auto', padding: '24px 16px',
    }}>
      <div style={{
        width: '100%', maxWidth: 920,
        background: 'var(--bg-secondary)', border: '1px solid var(--border)',
        borderRadius: 'var(--radius-lg)', boxShadow: 'var(--shadow)',
      }}>
        {/* Header */}
        <div style={{
          display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start',
          padding: '18px 24px', borderBottom: '1px solid var(--border)', gap: 12,
        }}>
          <div style={{ minWidth: 0 }}>
            <div style={{ fontWeight: 600, fontSize: 15, color: 'var(--text-primary)', marginBottom: 4, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {email?.subject || t('detail.no_subject')}
            </div>
            <div style={{ color: 'var(--text-muted)', fontSize: 12 }}>{email?.from} · {email?.date}</div>
          </div>
          <div style={{ display: 'flex', gap: 8, flexShrink: 0 }}>
            <a href={getReportUrl(data.job_id)} download style={{
              padding: '6px 12px', borderRadius: 'var(--radius)',
              background: 'var(--bg-card)', border: '1px solid var(--border)',
              color: 'var(--text-primary)', fontSize: 12, cursor: 'pointer',
              textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: 4,
            }}>📄 {t('detail.report_btn')}</a>
            <button onClick={onClose} style={{ background:'none', border:'none', color:'var(--text-muted)', fontSize:20, cursor:'pointer' }}>×</button>
          </div>
        </div>

        {/* Tabs */}
        <div style={{ display: 'flex', borderBottom: '1px solid var(--border)', padding: '0 24px', overflowX: 'auto' }}>
          {TABS.map((tabLabel, i) => (
            <button key={i} onClick={() => setTab(i)} style={{
              padding: '10px 16px', background: 'none', border: 'none',
              borderBottom: `2px solid ${tab === i ? 'var(--accent-blue)' : 'transparent'}`,
              color: tab === i ? 'var(--text-primary)' : 'var(--text-muted)',
              cursor: 'pointer', fontSize: 13, fontWeight: tab === i ? 600 : 400,
              whiteSpace: 'nowrap', transition: 'color 0.15s',
            }}>{tabLabel}</button>
          ))}
        </div>

        {/* Content */}
        <div style={{ padding: '24px' }}>
          {tab === 0 && <TabSummary email={email} risk={risk} t={t} notes={notes} setNotes={setNotes} onSaveNotes={handleSaveNotes} notesSaving={notesSaving} notesSaved={notesSaved} />}
          {tab === 1 && <TabHeader data={header_analysis} t={t} />}
          {tab === 2 && <TabBody data={body_analysis} t={t} />}
          {tab === 3 && <TabURL data={url_analysis} t={t} />}
          {tab === 4 && <TabAttachments data={attachment_analysis} t={t} />}
          {tab === 5 && <TabReputation data={repData} loading={repLoading} error={repError} onRun={handleReputation} t={t} lang={lang} />}
        </div>
      </div>
    </div>
  )
}

// ── TAB RIEPILOGO ──────────────────────────────────────────────────────────────
function TabSummary({ email, risk, t, notes, setNotes, onSaveNotes, notesSaving, notesSaved }) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '200px 1fr', gap: 24, alignItems: 'start' }}>
      <RiskMeter score={risk?.score || 0} label={risk?.label || 'low'} contributions={risk?.contributions} t={t} />
      <div>
        <Section title={t('summary.email_metadata')} icon="📧">
          <KeyValue label={t('summary.from')}       value={email?.from} />
          <KeyValue label={t('summary.to')}         value={Array.isArray(email?.to) ? email.to.join(', ') : email?.to} />
          <KeyValue label={t('summary.subject')}    value={email?.subject} />
          <KeyValue label={t('summary.date')}       value={email?.date} />
          <KeyValue label={t('summary.message_id')} value={email?.message_id} mono />
          <KeyValue label={t('summary.sha256')}     value={email?.file_hash_sha256} mono />
        </Section>
        <Section title={t('summary.risk_explanation')} icon="🔍">
          {risk?.explanation?.length > 0
            ? risk.explanation.map((line, i) => (
                <div key={i} style={{ padding: '5px 10px', marginBottom: 4, borderRadius: 4, background: 'var(--bg-card)', color: 'var(--text-secondary)', fontSize: 12, fontFamily: 'var(--font-mono)' }}>{line}</div>
              ))
            : <EmptyState message={t('summary.no_anomaly')} />
          }
        </Section>
        {email?.parse_errors?.length > 0 && (
          <Section title={t('summary.parse_warnings')} icon="⚠️">
            {email.parse_errors.map((e, i) => <div key={i} style={{ color: 'var(--risk-medium)', fontSize: 12, marginBottom: 4 }}>{e}</div>)}
          </Section>
        )}

        <Section title={t('summary.analyst_notes')} icon="📝">
          <textarea
            value={notes}
            onChange={e => setNotes(e.target.value)}
            placeholder={t('summary.notes_placeholder')}
            rows={5}
            style={{
              width: '100%', padding: '10px 12px',
              background: 'var(--bg-secondary)', border: '1px solid var(--border)',
              borderRadius: 'var(--radius)', color: 'var(--text-primary)',
              fontFamily: 'var(--font-sans)', fontSize: 13, lineHeight: 1.6,
              resize: 'vertical', outline: 'none', boxSizing: 'border-box',
            }}
          />
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 8 }}>
            <button
              onClick={onSaveNotes}
              disabled={notesSaving}
              style={{
                padding: '6px 16px', borderRadius: 'var(--radius)',
                background: notesSaved ? 'var(--risk-low-bg)' : 'var(--accent-blue)',
                border: notesSaved ? '1px solid var(--risk-low)' : 'none',
                color: notesSaved ? 'var(--risk-low)' : '#fff',
                fontSize: 13, fontWeight: 500, cursor: notesSaving ? 'not-allowed' : 'pointer',
                opacity: notesSaving ? 0.7 : 1, transition: 'all 0.2s',
              }}
            >
              {notesSaving ? '...' : notesSaved ? t('summary.notes_saved') : t('summary.notes_save')}
            </button>
            <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>
              {notes.length}/10000
            </span>
          </div>
        </Section>
      </div>
    </div>
  )
}

// ── TAB HEADER ─────────────────────────────────────────────────────────────────
function TabHeader({ data, t }) {
  if (!data) return <EmptyState message="–" />

  const ad = data.auth_detail || {}
  const AUTH_PROTOCOLS = [
    {
      proto: 'SPF',
      ok: data.spf_ok,
      result: data.spf_result,
      desc: t('header.spf_desc'),
      headers: 'Authentication-Results: spf=… · Received-SPF: …',
    },
    {
      proto: 'DKIM',
      ok: data.dkim_ok,
      result: data.dkim_result,
      desc: t('header.dkim_desc'),
      headers: 'Authentication-Results: dkim=… · DKIM-Signature: …',
    },
    {
      proto: 'DMARC',
      ok: data.dmarc_ok,
      result: data.dmarc_result,
      desc: t('header.dmarc_desc'),
      headers: 'Authentication-Results: dmarc=…',
    },
  ]

  return (
    <>
      <Section title={t('header.auth')} icon="🔐">
        {data.auth_summary && (
          <div style={{ marginBottom: 10, fontSize: 12, color: 'var(--text-secondary)' }}>
            {data.auth_summary}
          </div>
        )}
        {AUTH_PROTOCOLS.map(({ proto, ok, result, desc, headers }) => (
          <AuthDetailRow key={proto} proto={proto} ok={ok} result={result} desc={desc} headers={headers} authDetail={ad} t={t} />
        ))}
      </Section>

      {data.identity_mismatches?.length > 0 && (
        <Section title={t('header.mismatches')} icon="⚠️">
          {data.identity_mismatches.map((m, i) => (
            <div key={i} style={{ padding: '6px 10px', marginBottom: 4, borderRadius: 4, background: 'var(--risk-high-bg)', border: '1px solid var(--risk-high)', color: 'var(--risk-high)', fontSize: 12 }}>{m}</div>
          ))}
        </Section>
      )}

      {data.bulk_sender_detected && (
        <Section title={t('header.bulk_sender')} icon="📮">
          <div style={{ color: 'var(--risk-medium)', fontSize: 13 }}>{data.bulk_sender_tool}</div>
        </Section>
      )}

      <Section title={t('header.findings')} icon="🔎">
        {data.findings?.length > 0
          ? data.findings.map((f, i) => <FindingRow key={i} finding={f} />)
          : <EmptyState message={t('header.no_findings')} />}
      </Section>

      {data.received_hops?.length > 0 && (
        <Section title={t('header.smtp_chain')} icon="🌐">
          {/* Avviso ordine hop */}
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8, padding: '7px 10px', marginBottom: 10, borderRadius: 6, background: 'var(--bg-secondary)', border: '1px solid var(--border)', fontSize: 11, color: 'var(--text-muted)' }}>
            <span style={{ flexShrink: 0, fontSize: 13 }}>ℹ️</span>
            <span>{t('header.smtp_chain_note')}</span>
          </div>
          {data.received_hops.map((hop, i) => {
            const isFirst = i === 0
            const isLast  = i === data.received_hops.length - 1
            const badge = isFirst
              ? { label: t('header.hop_sender'),      color: 'var(--accent-blue)',  bg: '#0f1f3d' }
              : isLast
                ? { label: t('header.hop_destination'), color: 'var(--risk-low)',     bg: 'var(--risk-low-bg)' }
                : null
            return (
              <div key={i} style={{ padding: '6px 10px', marginBottom: 4, borderRadius: 4, background: 'var(--bg-card)', border: `1px solid ${isFirst ? 'var(--accent-blue)44' : isLast ? 'var(--risk-low)44' : 'var(--border)'}`, fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>
                <span style={{ color: 'var(--accent-blue)' }}>hop {hop.hop}</span>
                {badge && (
                  <span style={{ marginLeft: 6, padding: '1px 6px', borderRadius: 3, fontSize: 10, fontWeight: 700, letterSpacing: '0.04em', color: badge.color, background: badge.bg, border: `1px solid ${badge.color}44` }}>
                    {badge.label}
                  </span>
                )}
                {hop.ip && <> · IP: <span style={{ color: hop.private_ip ? 'var(--risk-medium)' : 'var(--text-primary)' }}>{hop.ip}</span></>}
                {hop.by && <> · by: {hop.by}</>}
                {hop.timestamp && <> · {hop.timestamp}</>}
              </div>
            )
          })}
        </Section>
      )}

      {data.injection_attempts?.length > 0 && (
        <Section title={t('header.injection')} icon="💉">
          {data.injection_attempts.map((f, i) => <div key={i} style={{ color: 'var(--risk-high)', fontSize: 13, marginBottom: 4 }}>{f}</div>)}
        </Section>
      )}
    </>
  )
}

// Sub-row helper per i dettagli verbosi
function SubRow({ label, value, mono = false, warn = false }) {
  if (!value) return null
  return (
    <div style={{ display: 'flex', gap: 8, alignItems: 'flex-start', padding: '1px 0' }}>
      <span style={{ fontSize: 10, color: 'var(--text-muted)', minWidth: 140, flexShrink: 0 }}>{label}</span>
      <span style={{
        fontSize: 10,
        color: warn ? 'var(--risk-medium)' : 'var(--text-secondary)',
        fontFamily: mono ? 'var(--font-mono)' : 'inherit',
        wordBreak: 'break-all', lineHeight: 1.4,
      }}>{value}</span>
    </div>
  )
}

function SpfSubDetail({ ad, t }) {
  const hasData = ad.spf_client_ip || ad.spf_envelope_from || ad.spf_dns_record || ad.spf_dns_error || ad.spf_failure_reason
  if (!hasData) return null
  return (
    <>
      {ad.spf_failure_reason && (
        <SubRow label={t('header.auth_detail_failure_reason')} value={ad.spf_failure_reason} warn />
      )}
      <SubRow label={t('header.auth_detail_client_ip')} value={ad.spf_client_ip} mono />
      <SubRow label={t('header.auth_detail_envelope')} value={ad.spf_envelope_from} mono />
      {ad.spf_dns_record
        ? <SubRow label={t('header.auth_detail_spf_dns')} value={ad.spf_dns_record} mono />
        : ad.spf_dns_error
          ? <SubRow label={t('header.auth_detail_spf_dns')} value={`⚠️ ${ad.spf_dns_error}`} warn />
          : null}
    </>
  )
}

function DkimSubDetail({ ad, t }) {
  const sigs = ad.dkim_signatures || []
  if (!sigs.length) return null
  return sigs.map((sig, idx) => (
    <div key={idx} style={{ marginBottom: idx < sigs.length - 1 ? 8 : 0 }}>
      {sigs.length > 1 && (
        <div style={{ fontSize: 10, fontWeight: 600, color: 'var(--accent-blue)', marginBottom: 3 }}>
          {t('header.auth_detail_sig')} {idx + 1}: {sig.d || '—'}
        </div>
      )}
      {sig.d && <SubRow label="d=" value={sig.d} mono />}
      {sig.s && <SubRow label={t('header.auth_detail_selector')} value={`${sig.s}._domainkey.${sig.d}`} mono />}
      {sig.a && <SubRow label={t('header.auth_detail_dkim_algo')} value={sig.a} mono />}
      {sig.c && <SubRow label={t('header.auth_detail_dkim_canon')} value={sig.c} mono />}
      {sig.h?.length > 0 && <SubRow label={t('header.auth_detail_dkim_headers')} value={sig.h.join(' · ')} />}
      {sig.bh && <SubRow label={t('header.auth_detail_dkim_bh')} value={sig.bh} mono />}
      <SubRow
        label={t('header.auth_detail_dkim_key')}
        value={
          sig.dns_key_found
            ? `✓ ${t('header.auth_detail_dkim_key_ok')}`
            : (sig.dns_error
                ? `✗ ${t('header.auth_detail_dkim_key_ko')} — ${sig.dns_error}`
                : null)
        }
        warn={!sig.dns_key_found}
      />
      {/* Motivo fallimento: solo se la firma non passa ma la chiave DNS esiste
          (se chiave non trovata il motivo è già evidente dalla riga DNS key) */}
      {sig.result && sig.result !== 'pass' && sig.dns_key_found && (
        <SubRow
          label={t('header.auth_detail_failure_reason')}
          value={ad.dkim_failure_reason || t('header.auth_detail_dkim_fail_sig')}
          warn
        />
      )}
    </div>
  ))
}

function DmarcSubDetail({ ad, t }) {
  const hasData = ad.dmarc_from_domain || ad.dmarc_policy || ad.dmarc_dns_record || ad.dmarc_dns_error || ad.dmarc_failure_reason
  if (!hasData) return null
  const POLICY_COLORS = {
    reject:     { color: 'var(--risk-low)',    bg: 'var(--risk-low-bg)' },
    quarantine: { color: 'var(--risk-medium)', bg: 'var(--risk-medium-bg)' },
    none:       { color: 'var(--text-muted)',  bg: 'var(--bg-secondary)' },
  }
  const pc = POLICY_COLORS[ad.dmarc_policy] || POLICY_COLORS.none
  const alignLabel = (v) => v === 'r' ? 'relaxed' : v === 's' ? 'strict' : v
  return (
    <>
      {ad.dmarc_failure_reason && (
        <SubRow label={t('header.auth_detail_failure_reason')} value={ad.dmarc_failure_reason} warn />
      )}
      {ad.dmarc_from_domain && <SubRow label={t('header.auth_detail_dmarc_from')} value={ad.dmarc_from_domain} mono />}
      {ad.dmarc_policy && (
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', padding: '1px 0' }}>
          <span style={{ fontSize: 10, color: 'var(--text-muted)', minWidth: 140, flexShrink: 0 }}>{t('header.auth_detail_dmarc_policy')}</span>
          <span style={{ padding: '1px 8px', borderRadius: 4, fontSize: 10, fontWeight: 700, color: pc.color, background: pc.bg, border: `1px solid ${pc.color}44`, fontFamily: 'var(--font-mono)' }}>
            {ad.dmarc_policy}
          </span>
        </div>
      )}
      {ad.dmarc_subdomain_policy && <SubRow label={t('header.auth_detail_dmarc_sp')} value={ad.dmarc_subdomain_policy} mono />}
      {ad.dmarc_adkim && <SubRow label={t('header.auth_detail_dmarc_adkim')} value={alignLabel(ad.dmarc_adkim)} />}
      {ad.dmarc_aspf  && <SubRow label={t('header.auth_detail_dmarc_aspf')}  value={alignLabel(ad.dmarc_aspf)} />}
      {ad.dmarc_pct && ad.dmarc_pct !== '100' && <SubRow label={t('header.auth_detail_dmarc_pct')} value={`${ad.dmarc_pct}%`} />}
      {ad.dmarc_rua  && <SubRow label={t('header.auth_detail_dmarc_rua')} value={ad.dmarc_rua} mono />}
      {ad.dmarc_dns_record
        ? <SubRow label={t('header.auth_detail_dmarc_dns')} value={ad.dmarc_dns_record} mono />
        : ad.dmarc_dns_error
          ? <SubRow label={t('header.auth_detail_dmarc_dns')} value={`⚠️ ${ad.dmarc_dns_error}`} warn />
          : null}
    </>
  )
}

function AuthDetailRow({ proto, ok, result, desc, headers, authDetail = {}, t }) {
  const absent = !result
  let pillColor, pillBg
  if (absent) {
    pillColor = 'var(--text-muted)'
    pillBg    = 'var(--bg-card)'
  } else if (ok) {
    pillColor = 'var(--risk-low)'
    pillBg    = 'var(--risk-low-bg)'
  } else if (['softfail', 'neutral'].includes(result)) {
    pillColor = 'var(--risk-medium)'
    pillBg    = 'var(--risk-medium-bg)'
  } else {
    pillColor = 'var(--risk-high)'
    pillBg    = 'var(--risk-high-bg)'
  }
  const icon  = absent ? '' : ok ? '✓ ' : '✗ '
  const label = absent ? t('header.auth_absent_val') : result

  const subDetail = proto === 'SPF'
    ? <SpfSubDetail  ad={authDetail} t={t} />
    : proto === 'DKIM'
      ? <DkimSubDetail  ad={authDetail} t={t} />
      : <DmarcSubDetail ad={authDetail} t={t} />

  return (
    <div style={{
      padding: '10px 12px', borderRadius: 8, background: 'var(--bg-card)',
      marginBottom: 6,
    }}>
      {/* riga principale */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 16 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontWeight: 700, fontSize: 13, letterSpacing: '0.04em', marginBottom: 4 }}>
            {proto}
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginBottom: 4, lineHeight: 1.4 }}>
            {desc}
          </div>
          <div style={{ fontSize: 10, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
            {headers}
          </div>
        </div>
        <div style={{
          padding: '4px 12px', borderRadius: 20, fontSize: 12, fontWeight: 700,
          color: pillColor, background: pillBg, border: `1px solid ${pillColor}55`,
          whiteSpace: 'nowrap', alignSelf: 'center', fontFamily: 'var(--font-mono)',
          flexShrink: 0,
        }}>
          {icon}{label}
        </div>
      </div>
      {/* sub-dettagli */}
      {subDetail && (
        <div style={{
          marginTop: 8, paddingTop: 8,
          borderTop: '1px solid var(--border)',
          display: 'flex', flexDirection: 'column', gap: 2,
        }}>
          {subDetail}
        </div>
      )}
    </div>
  )
}

// ── TAB BODY ───────────────────────────────────────────────────────────────────
function TabBody({ data, t }) {
  if (!data) return <EmptyState message="–" />

  const stats = [
    [t('body.urgency'),  data.urgency_count,            data.urgency_count >= 3 ? 'high' : data.urgency_count > 0 ? 'medium' : 'ok'],
    [t('body.cta'),      data.phishing_cta_count,       data.phishing_cta_count >= 2 ? 'high' : data.phishing_cta_count > 0 ? 'medium' : 'ok'],
    [t('body.cred_kw'),  data.credential_keyword_count, data.credential_keyword_count > 0 ? 'high' : 'ok'],
    [t('body.forms'),    data.forms_found,              data.forms_found > 0 ? 'high' : 'ok'],
    [t('body.javascript'), data.js_found ? t('body.yes') : t('body.no'), data.js_found ? 'high' : 'ok'],
    [t('body.hidden'),   data.invisible_elements,       data.invisible_elements > 0 ? 'medium' : 'ok'],
    [t('body.urls'),     data.extracted_urls_count,     'ok'],
    [t('body.obfuscated'), data.obfuscated_links?.length || 0, (data.obfuscated_links?.length || 0) > 0 ? 'high' : 'ok'],
  ]

  return (
    <>
      <Section title={t('body.stats')} icon="📊">
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(155px, 1fr))', gap: 10 }}>
          {stats.map(([label, value, sev]) => <StatCard key={label} label={label} value={String(value ?? 0)} severity={sev} />)}
        </div>
      </Section>

      {/* ── Sezione NLP ── */}
      <NLPSection nlp={data.nlp} t={t} />

      {/* ── Sezione HTML Nascosto espansa ── */}
      {data.invisible_elements > 0 && <HiddenHTMLSection data={data} t={t} />}

      {data.obfuscated_links?.length > 0 && (
        <Section title={t('body.obfuscated_title')} icon="🎭">
          {data.obfuscated_links.map((lnk, i) => (
            <div key={i} style={{ padding: '8px 12px', marginBottom: 6, borderRadius: 6, background: 'var(--bg-card)', border: '1px solid var(--risk-high)' }}>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 3 }}>{t('body.visible_text')}</div>
              <div style={{ fontSize: 12, color: 'var(--risk-medium)', fontFamily: 'var(--font-mono)', wordBreak: 'break-all' }}>{lnk.visible_text}</div>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', margin: '4px 0 2px' }}>{t('body.actual_href')}</div>
              <div style={{ fontSize: 12, color: 'var(--risk-high)', fontFamily: 'var(--font-mono)', wordBreak: 'break-all' }}>{lnk.actual_href}</div>
            </div>
          ))}
        </Section>
      )}

      <Section title={t('body.findings_title')} icon="🔎">
        {data.findings?.length > 0
          ? data.findings.map((f, i) => <FindingRow key={i} finding={f} />)
          : <EmptyState message={t('body.no_findings')} />}
      </Section>
    </>
  )
}


// ── NLP Section ────────────────────────────────────────────────────────────
function NLPSection({ nlp, t }) {
  if (!nlp) return null

  const LABEL_COLORS = {
    phishing:   { color: 'var(--risk-high)',     bg: 'var(--risk-high-bg)' },
    suspicious: { color: 'var(--risk-medium)',   bg: 'var(--risk-medium-bg)' },
    legitimate: { color: 'var(--risk-low)',      bg: 'var(--risk-low-bg)' },
    unknown:    { color: 'var(--text-muted)',    bg: 'var(--bg-card)' },
  }
  const lc = LABEL_COLORS[nlp.label] || LABEL_COLORS.unknown
  const pct = Math.round((nlp.phishing_probability || 0) * 100)

  return (
    <Section title={t('body.nlp_section')} icon="🤖">
      {!nlp.available ? (
        <div style={{ color: 'var(--text-muted)', fontSize: 12, fontStyle: 'italic' }}>
          {t('body.nlp_unavailable')}
        </div>
      ) : (
        <div style={{ display: 'flex', gap: 16, alignItems: 'flex-start', flexWrap: 'wrap' }}>
          {/* Label + Probability */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, minWidth: 180 }}>
            <span style={{
              padding: '4px 14px', borderRadius: 20, fontWeight: 700, fontSize: 12,
              letterSpacing: '0.05em', textTransform: 'uppercase',
              color: lc.color, background: lc.bg,
              border: `1px solid ${lc.color}55`,
              alignSelf: 'flex-start',
            }}>
              {t(`body.nlp_label_${nlp.label}`) || nlp.label}
            </span>
            {/* Probability bar */}
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4, fontSize: 11 }}>
                <span style={{ color: 'var(--text-muted)' }}>Phishing probability</span>
                <span style={{ color: lc.color, fontWeight: 700, fontFamily: 'var(--font-mono)' }}>{pct}%</span>
              </div>
              <div style={{ height: 6, borderRadius: 3, background: 'var(--border)', overflow: 'hidden' }}>
                <div style={{
                  height: '100%', borderRadius: 3,
                  width: `${pct}%`,
                  background: pct >= 75 ? 'var(--risk-high)' : pct >= 50 ? 'var(--risk-medium)' :
                               pct >= 35 ? 'var(--risk-medium)' : 'var(--risk-low)',
                  transition: 'width 0.5s ease',
                }} />
              </div>
              <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 3 }}>
                Confidenza: {nlp.confidence}
              </div>
            </div>
          </div>

          {/* Top features */}
          {nlp.top_features?.length > 0 && (
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 6 }}>
                Feature rilevanti (TF-IDF):
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
                {nlp.top_features.map(f => (
                  <span key={f} style={{
                    padding: '2px 8px', borderRadius: 4,
                    background: 'var(--bg-card)', border: '1px solid var(--border)',
                    color: 'var(--text-secondary)', fontSize: 11,
                    fontFamily: 'var(--font-mono)',
                  }}>{f}</span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </Section>
  )
}

// ── Sezione HTML Nascosto — visualizzazione completa ──────────────────────────
function HiddenHTMLSection({ data, t }) {
  const [expanded, setExpanded] = useState(false)

  // Cerca i finding con elementi nascosti e recupera l'evidence
  const hiddenFindings = (data.findings || []).filter(f =>
    f.category === 'html' && (
      f.description?.toLowerCase().includes('nascost') ||
      f.description?.toLowerCase().includes('hidden') ||
      f.description?.toLowerCase().includes('css')
    )
  )

  return (
    <Section title={t('body.hidden_section')} icon="👁️">
      {/* Badge di allerta */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 12,
        padding: '10px 14px', borderRadius: 8, marginBottom: 12,
        background: '#2a180044', border: '1px solid var(--severity-medium)',
      }}>
        <span style={{ fontSize: 22 }}>⚠️</span>
        <div>
          <div style={{ color: 'var(--severity-medium)', fontWeight: 600, fontSize: 13 }}>
            {t('body.hidden_count', { n: data.invisible_elements })}
          </div>
          <div style={{ color: 'var(--text-muted)', fontSize: 11, marginTop: 2 }}>
            {t('body.hidden_evidence')}
          </div>
        </div>
      </div>

      {/* Tecniche rilevate */}
      {hiddenFindings.map((f, i) => (
        <div key={i} style={{ marginBottom: 8 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
            <SeverityBadge severity={f.severity} />
            <span style={{ color: 'var(--text-primary)', fontSize: 13 }}>{f.description}</span>
          </div>
          {f.evidence && (
            <div style={{
              padding: '6px 10px', borderRadius: 4, background: 'var(--bg-card)',
              border: '1px solid var(--border)',
              fontFamily: 'var(--font-mono)', fontSize: 11,
              color: 'var(--text-muted)', wordBreak: 'break-all',
            }}>
              {f.evidence}
            </div>
          )}
        </div>
      ))}

      {/* Contenuto HTML estratto con toggle */}
      {data.raw_hidden_content && (
        <div style={{ marginTop: 8 }}>
          <button onClick={() => setExpanded(e => !e)} style={{
            background: 'none', border: '1px solid var(--border)',
            borderRadius: 4, color: 'var(--text-secondary)', fontSize: 11,
            padding: '4px 10px', cursor: 'pointer', marginBottom: 8,
          }}>
            {expanded ? '▼' : '▶'} {t('body.hidden_content_label')}
          </button>
          {expanded && (
            <div style={{
              padding: '10px 12px', borderRadius: 6,
              background: '#0a0a14', border: '2px solid var(--severity-medium)',
              fontFamily: 'var(--font-mono)', fontSize: 11,
              color: 'var(--severity-medium)', whiteSpace: 'pre-wrap',
              wordBreak: 'break-all', maxHeight: 300, overflowY: 'auto',
            }}>
              {data.raw_hidden_content}
            </div>
          )}
        </div>
      )}

      {/* Mostra i CSS attributes usati per nascondere */}
      <HiddenCSSPatterns t={t} />
    </Section>
  )
}

function HiddenCSSPatterns({ t }) {
  const patterns = [
    'display:none', 'visibility:hidden', 'font-size:0',
    'color:#fff / color:white', 'opacity:0',
  ]
  return (
    <div style={{ marginTop: 10 }}>
      <div style={{ color: 'var(--text-muted)', fontSize: 11, marginBottom: 6 }}>
        {t('body.hidden_technique', { technique: 'CSS' })}:
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
        {patterns.map(p => (
          <span key={p} style={{
            padding: '2px 8px', borderRadius: 4,
            background: '#2a180033', border: '1px solid var(--severity-medium)44',
            color: 'var(--severity-medium)', fontSize: 10,
            fontFamily: 'var(--font-mono)',
          }}>{p}</span>
        ))}
      </div>
    </div>
  )
}

function StatCard({ label, value, severity = 'ok' }) {
  const c = { ok: 'var(--text-secondary)', medium: 'var(--severity-medium)', high: 'var(--severity-high)' }
  const bg = { ok: 'var(--bg-card)', medium: '#2a180033', high: '#2a0a0a55' }
  return (
    <div style={{ padding: '12px 14px', borderRadius: 8, background: bg[severity] || bg.ok, border: '1px solid var(--border)', textAlign: 'center' }}>
      <div style={{ fontSize: 20, fontWeight: 700, fontFamily: 'var(--font-mono)', color: c[severity] || c.ok }}>{value}</div>
      <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>{label}</div>
    </div>
  )
}

// ── TAB URL ────────────────────────────────────────────────────────────────────
function TabURL({ data, t }) {
  if (!data) return <EmptyState message="–" />
  return (
    <>
      <div style={{ display: 'flex', gap: 20, marginBottom: 20 }}>
        <div style={{ color: 'var(--text-secondary)', fontSize: 13 }}>
          <b style={{ color: 'var(--text-primary)' }}>{data.total_urls}</b> {t('url.total', { n: '' }).trim()}
        </div>
        <div style={{ color: 'var(--risk-high)', fontSize: 13 }}>
          <b>{data.high_risk_count}</b> {t('url.high_risk', { n: '' }).trim()}
        </div>
      </div>
      {data.urls?.length > 0
        ? data.urls.map((u, i) => <URLCard key={i} url={u} t={t} />)
        : <EmptyState message={t('url.no_urls')} />}
    </>
  )
}

function URLCard({ url, t }) {
  const rc = url.risk_score >= 25 ? 'var(--risk-high)' : url.risk_score >= 10 ? 'var(--risk-medium)' : 'var(--risk-low)'
  return (
    <div style={{ padding: '10px 14px', marginBottom: 8, borderRadius: 8, background: 'var(--bg-card)', border: `1px solid ${url.risk_score >= 25 ? 'var(--risk-high)33' : 'var(--border)'}` }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 10, marginBottom: 6 }}>
        <div style={{ fontSize: 12, fontFamily: 'var(--font-mono)', color: 'var(--text-primary)', wordBreak: 'break-all', flex: 1 }}>{url.url}</div>
        <div style={{ fontSize: 11, fontWeight: 700, fontFamily: 'var(--font-mono)', color: rc, flexShrink: 0 }}>{url.risk_score?.toFixed(0)}/100</div>
      </div>
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: url.findings?.length ? 6 : 0 }}>
        {url.https  && <Tag color="var(--risk-low)">{t('url.https_ok')}</Tag>}
        {!url.https && <Tag color="var(--risk-medium)">{t('url.http_only')}</Tag>}
        {url.is_ip  && <Tag color="var(--risk-high)">{t('url.ip_direct')}</Tag>}
        {url.is_shortener && <Tag color="var(--risk-medium)">{t('url.shortener')}</Tag>}
        {url.is_punycode  && <Tag color="var(--risk-high)">{t('url.punycode')}</Tag>}
        {url.resolved_ip  && <Tag color="var(--text-muted)">{url.resolved_ip}</Tag>}
        {/* Badge WHOIS età dominio */}
        {!url.is_ip && url.whois_attempted === true && (
          url.domain_age_days != null
            ? url.domain_age_days < 30
              ? <Tag color="var(--risk-high)">{t('url.age_new', { days: url.domain_age_days })}</Tag>
              : url.domain_age_days < 90
                ? <Tag color="var(--risk-medium)">{t('url.age_recent', { days: url.domain_age_days })}</Tag>
                : <Tag color="var(--risk-low)">{t('url.age_ok', { days: url.domain_age_days })}</Tag>
            : <Tag color="var(--text-muted)">{t('url.whois_no_data')}</Tag>
        )}
        {!url.is_ip && !url.whois_attempted && (
          <Tag color="var(--text-muted)" title={t('url.whois_disabled_hint')}>{t('url.whois_disabled')}</Tag>
        )}
      </div>
      {url.findings?.map((f, i) => (
        <div key={i} style={{ fontSize: 11, color: 'var(--text-muted)', paddingLeft: 8, borderLeft: '2px solid var(--border)', marginTop: 3 }}>
          <SeverityBadge severity={f.severity} /> {f.description}
        </div>
      ))}
    </div>
  )
}

function Tag({ children, color, title }) {
  return (
    <span title={title} style={{ padding: '1px 7px', borderRadius: 3, fontSize: 10, fontWeight: 600, letterSpacing: '0.04em', color, background: color + '22', border: `1px solid ${color}44`, cursor: title ? 'help' : 'default' }}>
      {children}
    </span>
  )
}

// ── TAB ALLEGATI ───────────────────────────────────────────────────────────────
function TabAttachments({ data, t }) {
  if (!data || data.total === 0) return <EmptyState message={t('att.no_attachments')} />
  return (
    <>
      <div style={{ color: 'var(--text-secondary)', fontSize: 13, marginBottom: 16 }}>
        <b style={{ color: 'var(--text-primary)' }}>{data.total}</b> {t('att.total', { n: '' }).replace('{n}','').trim()} ·{' '}
        <b style={{ color: 'var(--risk-high)' }}>{data.critical_count}</b> {t('att.critical', { n: '' }).replace('{n}','').trim()}
      </div>
      {data.attachments?.map((att, i) => (
        <div key={i} style={{
          padding: '12px 16px', marginBottom: 10, borderRadius: 8, background: 'var(--bg-card)',
          border: `1px solid ${att.risk_score >= 40 ? 'var(--severity-critical)' : att.risk_score >= 20 ? 'var(--severity-high)' : 'var(--border)'}`,
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
            <span style={{ fontWeight: 600, fontSize: 13 }}>{att.filename}</span>
            <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: att.risk_score >= 40 ? 'var(--severity-critical)' : att.risk_score >= 20 ? 'var(--severity-high)' : 'var(--risk-low)' }}>
              {att.risk_score?.toFixed(0)}/100
            </span>
          </div>
          <KeyValue label={t('att.declared_mime')} value={att.declared_mime} mono />
          <KeyValue label={t('att.real_mime')}     value={att.real_mime}     mono />
          <KeyValue label={t('att.sha256')}        value={att.hash_sha256}   mono />
          <div style={{ display: 'flex', gap: 6, margin: '8px 0' }}>
            {att.mime_mismatch && <Tag color="var(--severity-high)">{t('att.mime_mismatch')}</Tag>}
            {att.has_macro     && <Tag color="var(--severity-critical)">{t('att.macro')}</Tag>}
            {att.has_js        && <Tag color="var(--severity-critical)">{t('att.js')}</Tag>}
          </div>
          {att.findings?.map((f, j) => <FindingRow key={j} finding={f} />)}
        </div>
      ))}
    </>
  )
}