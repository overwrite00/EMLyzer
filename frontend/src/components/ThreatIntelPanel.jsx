// src/components/ThreatIntelPanel.jsx
//
// Pannello unico "Threat Intelligence" (v0.17): tre sotto-sezioni con
// linguaggio e componenti coerenti — Feed IOC (stato + refresh), Campagne
// Note (CRUD + backtest + proposte auto-apprendimento), Bollettini CERT-AGID
// (bacheca di spunti). Componente autonomo: può essere spostato in una
// futura sezione impostazioni senza riscrittura (oggi montato in Dashboard).
/* eslint-disable react-hooks/set-state-in-effect */
import { useEffect, useState, useCallback } from 'react'
import { useLang } from '../i18n/LangContext'
import { Button, Spinner, EmptyState } from './ui'
import {
  getIntelStatus, refreshIntelTarget, getBulletins,
  getKnownCampaigns, createKnownCampaign, updateKnownCampaign,
  deleteKnownCampaign, restoreKnownCampaign, backtestCampaign,
  generateCampaignProposals, listCampaignProposals,
  approveCampaignProposal, rejectCampaignProposal,
} from '../api/client'

const STATE_COLORS = {
  ok: 'var(--risk-low)',
  stale: 'var(--risk-medium)',
  unavailable: 'var(--risk-high)',
  never_fetched: 'var(--text-muted)',
}

function StateBadge({ state, t }) {
  const color = STATE_COLORS[state] || 'var(--text-muted)'
  return (
    <span style={{
      padding: '2px 8px', borderRadius: 20, fontSize: 10, fontWeight: 700,
      color, background: color + '22', border: `1px solid ${color}44`,
    }}>
      {t(`intel.state.${state}`) || state}
    </span>
  )
}

const TABS = ['feeds', 'campaigns', 'bulletins']

export default function ThreatIntelPanel() {
  const { t } = useLang()
  const [tab, setTab] = useState('feeds')
  const [status, setStatus] = useState(null)

  const loadStatus = useCallback(async () => {
    try {
      setStatus(await getIntelStatus())
    } catch (err) {
      console.error(err)
    }
  }, [])

  useEffect(() => { loadStatus() }, [loadStatus])

  return (
    <section style={{ marginBottom: 32 }}>
      <h2 style={{
        fontSize: 13, fontWeight: 600, color: 'var(--text-secondary)',
        marginBottom: 12, letterSpacing: '0.06em', textTransform: 'uppercase',
      }}>
        🛰 {t('intel.title')}
      </h2>

      <div style={{ display: 'flex', gap: 6, marginBottom: 12 }}>
        {TABS.map(id => (
          <button
            key={id}
            onClick={() => setTab(id)}
            style={{
              padding: '6px 14px', borderRadius: 20, fontSize: 12, fontWeight: 600,
              cursor: 'pointer', border: `1px solid ${tab === id ? 'var(--accent-blue)' : 'var(--border)'}`,
              background: tab === id ? 'var(--accent-blue)22' : 'var(--bg-card)',
              color: tab === id ? 'var(--accent-blue)' : 'var(--text-secondary)',
            }}
          >
            {t(`intel.tab.${id}`)}
          </button>
        ))}
      </div>

      {tab === 'feeds' && <FeedsTab status={status} onRefreshed={loadStatus} t={t} />}
      {tab === 'campaigns' && <CampaignsTab t={t} />}
      {tab === 'bulletins' && <BulletinsTab t={t} />}
    </section>
  )
}

// ---------------------------------------------------------------------------
// Feed IOC
// ---------------------------------------------------------------------------

function FeedsTab({ status, onRefreshed, t }) {
  const [refreshing, setRefreshing] = useState({})

  async function refresh(name) {
    setRefreshing(r => ({ ...r, [name]: true }))
    try {
      await refreshIntelTarget(name)
      // il refresh è asincrono lato server: un breve polling basta per la UI
      setTimeout(onRefreshed, 1500)
      setTimeout(onRefreshed, 4000)
    } catch (err) {
      console.error(err)
    } finally {
      setTimeout(() => setRefreshing(r => ({ ...r, [name]: false })), 4000)
    }
  }

  if (!status) return <Spinner size={16} />

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {status.feeds.map(feed => (
        <div key={feed.name} style={{
          display: 'flex', alignItems: 'center', gap: 12, padding: '10px 14px',
          background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8,
        }}>
          <span style={{ fontWeight: 600, fontSize: 13, minWidth: 100, textTransform: 'capitalize' }}>{feed.name}</span>
          <StateBadge state={feed.state} t={t} />
          <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
            {feed.entry_count != null ? t('intel.entries', { n: feed.entry_count.toLocaleString() }) : '—'}
          </span>
          {feed.age_hours != null && (
            <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{t('intel.age', { h: feed.age_hours.toFixed(1) })}</span>
          )}
          {feed.requires_key && !feed.key_configured && (
            <span style={{ fontSize: 11, color: 'var(--risk-medium)' }}>{t('intel.needs_key')}</span>
          )}
          {feed.last_error && (
            <span style={{ fontSize: 11, color: 'var(--risk-high)', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {t('intel.error_prefix')} {feed.last_error.category}
            </span>
          )}
          <div style={{ flex: 1 }} />
          <Button variant="ghost" onClick={() => refresh(feed.name)} loading={!!refreshing[feed.name]}>
            {t('intel.refresh_one')}
          </Button>
        </div>
      ))}
      <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>
        {t('intel.token_hint')}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Campagne note (CRUD + backtest + proposte)
// ---------------------------------------------------------------------------

function emptyForm() {
  return {
    id: '', name: '', keywords: '', required_keywords: '',
    risk_contribution: 25, enabled: true, description: '', reference_url: '',
  }
}

function CampaignsTab({ t }) {
  const [data, setData] = useState(null)
  const [editing, setEditing] = useState(null)   // null | 'new' | campaign object
  const [proposals, setProposals] = useState([])
  const [genLoading, setGenLoading] = useState(false)

  const load = useCallback(async () => {
    try {
      const [known, props] = await Promise.all([getKnownCampaigns(), listCampaignProposals('pending')])
      setData(known)
      setProposals(props.proposals)
    } catch (err) { console.error(err) }
  }, [])

  useEffect(() => { load() }, [load])

  async function handleDelete(id) {
    if (!window.confirm(t('intel.known.delete_confirm'))) return
    await deleteKnownCampaign(id)
    load()
  }

  async function handleRestore(id) {
    await restoreKnownCampaign(id)
    load()
  }

  async function handleGenerateProposals() {
    setGenLoading(true)
    try {
      await generateCampaignProposals()
      await load()
    } catch (err) { console.error(err) } finally { setGenLoading(false) }
  }

  async function handleApprove(id) {
    const res = await approveCampaignProposal(id)
    setEditing({ ...emptyForm(), ...res.payload_for_form, keywords: (res.payload_for_form.keywords || []).join('\n') })
    load()
  }

  async function handleReject(id) {
    await rejectCampaignProposal(id, 'rifiutata dall\'utente')
    load()
  }

  if (!data) return <Spinner size={16} />

  if (editing) {
    return <CampaignForm initial={editing === 'new' ? emptyForm() : editing} onDone={() => { setEditing(null); load() }} onCancel={() => setEditing(null)} t={t} />
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 10 }}>
        <Button onClick={() => setEditing('new')}>{t('intel.known.new')}</Button>
      </div>

      {data.campaigns.length === 0 ? (
        <EmptyState message={t('intel.known.empty')} />
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 20 }}>
          {data.campaigns.map(c => (
            <div key={c.id} style={{
              display: 'flex', alignItems: 'center', gap: 10, padding: '8px 14px',
              background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8,
              opacity: c.enabled === false ? 0.5 : 1,
            }}>
              <span style={{ fontWeight: 600, fontSize: 13 }}>{c.name}</span>
              <span style={{ fontSize: 11, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>{c.id}</span>
              <span style={{
                fontSize: 10, padding: '1px 7px', borderRadius: 10,
                background: 'var(--bg-secondary)', color: 'var(--text-muted)', border: '1px solid var(--border)',
              }}>
                {t(`intel.known.source.${c.source || 'builtin'}`)}
              </span>
              {data.overridden_ids?.includes(c.id) && (
                <span style={{ fontSize: 10, color: 'var(--risk-medium)' }}>{t('intel.known.overridden')}</span>
              )}
              <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>+{c.risk_contribution}</span>
              <div style={{ flex: 1 }} />
              {data.user_campaign_ids?.includes(c.id) ? (
                <>
                  <Button variant="ghost" onClick={() => setEditing({ ...c, keywords: (c.keywords || []).join('\n'), required_keywords: (c.required_keywords || []).join('\n') })}>{t('intel.known.edit')}</Button>
                  <Button variant="danger" onClick={() => handleDelete(c.id)}>{t('intel.known.delete')}</Button>
                </>
              ) : data.overridden_ids?.includes(c.id) ? (
                <Button variant="ghost" onClick={() => handleRestore(c.id)}>{t('intel.known.restore')}</Button>
              ) : null}
            </div>
          ))}
        </div>
      )}

      <h3 style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 8, textTransform: 'uppercase' }}>
        {t('intel.proposals.title')}
      </h3>
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 8 }}>
        <Button variant="ghost" onClick={handleGenerateProposals} loading={genLoading}>{t('intel.proposals.generate')}</Button>
      </div>
      {proposals.length === 0 ? (
        <EmptyState message={t('intel.proposals.empty')} />
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {proposals.map(p => (
            <div key={p.id} style={{
              display: 'flex', alignItems: 'center', gap: 10, padding: '8px 14px',
              background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8,
            }}>
              <span style={{ fontSize: 13 }}>{p.proposed_payload.name}</span>
              <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{t('intel.proposals.seen_count', { n: p.seen_count })}</span>
              {p.stale && <span style={{ fontSize: 11, color: 'var(--risk-medium)' }}>{t('intel.proposals.stale')}</span>}
              <div style={{ flex: 1 }} />
              <Button variant="ghost" disabled={p.stale} onClick={() => handleApprove(p.id)}>{t('intel.proposals.approve')}</Button>
              <Button variant="danger" onClick={() => handleReject(p.id)}>{t('intel.proposals.reject')}</Button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function CampaignForm({ initial, onDone, onCancel, t }) {
  const [form, setForm] = useState(initial)
  const [saving, setSaving] = useState(false)
  const [backtest, setBacktest] = useState(null)
  const [backtesting, setBacktesting] = useState(false)
  const [error, setError] = useState('')

  function update(field, value) {
    setForm(f => ({ ...f, [field]: value }))
  }

  function toPayload() {
    return {
      id: form.id.trim().toLowerCase(),
      name: form.name.trim(),
      keywords: form.keywords.split('\n').map(k => k.trim()).filter(Boolean),
      required_keywords: (form.required_keywords || '').split('\n').map(k => k.trim()).filter(Boolean),
      risk_contribution: Number(form.risk_contribution) || 25,
      enabled: !!form.enabled,
      description: form.description || '',
      reference_url: form.reference_url || '',
    }
  }

  async function runBacktest() {
    const payload = toPayload()
    if (payload.keywords.length === 0) return
    setBacktesting(true)
    try {
      setBacktest(await backtestCampaign({ keywords: payload.keywords, required_keywords: payload.required_keywords, risk_contribution: payload.risk_contribution }))
    } catch (err) {
      console.error(err)
    } finally {
      setBacktesting(false)
    }
  }

  async function save() {
    setSaving(true)
    setError('')
    try {
      const payload = toPayload()
      if (initial.id && initial.source === 'user') {
        await updateKnownCampaign(initial.id, payload)
      } else {
        await createKnownCampaign(payload)
      }
      onDone()
    } catch (err) {
      setError(err?.response?.data?.detail || String(err))
    } finally {
      setSaving(false)
    }
  }

  const falsePositives = backtest ? (backtest.matched_by_risk_label?.low || 0) + (backtest.matched_by_risk_label?.[''] || 0) : 0

  return (
    <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8, padding: 16 }}>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 }}>
        <Field label={t('intel.known.field.id')}>
          <input value={form.id} onChange={e => update('id', e.target.value)} disabled={!!initial.id} style={inputStyle} />
        </Field>
        <Field label={t('intel.known.field.name')}>
          <input value={form.name} onChange={e => update('name', e.target.value)} style={inputStyle} />
        </Field>
      </div>
      <Field label={t('intel.known.field.keywords')}>
        <textarea rows={4} value={form.keywords} onChange={e => update('keywords', e.target.value)} style={{ ...inputStyle, fontFamily: 'var(--font-mono)' }} />
      </Field>
      <Field label={t('intel.known.field.required_keywords')}>
        <textarea rows={2} value={form.required_keywords} onChange={e => update('required_keywords', e.target.value)} style={{ ...inputStyle, fontFamily: 'var(--font-mono)' }} />
      </Field>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 }}>
        <Field label={t('intel.known.field.risk')}>
          <input type="number" min={0} max={50} value={form.risk_contribution} onChange={e => update('risk_contribution', e.target.value)} style={inputStyle} />
        </Field>
        <Field label={t('intel.known.field.enabled')}>
          <input type="checkbox" checked={!!form.enabled} onChange={e => update('enabled', e.target.checked)} />
        </Field>
      </div>
      <Field label={t('intel.known.field.reference_url')}>
        <input value={form.reference_url} onChange={e => update('reference_url', e.target.value)} style={inputStyle} />
      </Field>

      <div style={{ borderTop: '1px solid var(--border)', marginTop: 12, paddingTop: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
          <strong style={{ fontSize: 12 }}>{t('intel.backtest.title')}</strong>
          <Button variant="ghost" onClick={runBacktest} loading={backtesting}>{t('intel.backtest.run')}</Button>
        </div>
        {backtest && (
          <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
            <div>{t('intel.backtest.coverage')} {backtest.coverage_note}</div>
            <div>{t('intel.backtest.matched', { n: backtest.matched_count })}</div>
            {falsePositives > 0 ? (
              <div style={{ color: 'var(--risk-medium)', marginTop: 4 }}>{t('intel.backtest.false_positive_warning', { n: falsePositives })}</div>
            ) : (
              <div style={{ color: 'var(--risk-low)', marginTop: 4 }}>{t('intel.backtest.ok')}</div>
            )}
          </div>
        )}
      </div>

      {error && <div style={{ color: 'var(--risk-high)', fontSize: 12, marginTop: 10 }}>{error}</div>}

      <div style={{ display: 'flex', gap: 8, marginTop: 16, justifyContent: 'flex-end' }}>
        <Button variant="ghost" onClick={onCancel}>{t('intel.known.cancel')}</Button>
        <Button onClick={save} loading={saving}>{t('intel.known.save')}</Button>
      </div>
    </div>
  )
}

function Field({ label, children }) {
  return (
    <div style={{ marginBottom: 12 }}>
      <label style={{ display: 'block', fontSize: 11, color: 'var(--text-muted)', marginBottom: 4 }}>{label}</label>
      {children}
    </div>
  )
}

const inputStyle = {
  width: '100%', padding: '6px 10px', borderRadius: 6,
  border: '1px solid var(--border)', background: 'var(--bg-secondary)',
  color: 'var(--text-primary)', fontSize: 13,
}

// ---------------------------------------------------------------------------
// Bollettini CERT-AGID
// ---------------------------------------------------------------------------

function BulletinsTab({ t }) {
  const [data, setData] = useState(null)
  const [creatingFrom, setCreatingFrom] = useState(null)
  const [refreshing, setRefreshing] = useState(false)

  const load = useCallback(async () => {
    const result = await getBulletins().catch(err => { console.error(err); return null })
    setData(result)
    return result
  }, [])

  const refresh = useCallback(async () => {
    setRefreshing(true)
    try {
      await refreshIntelTarget('bulletins')
      // il fetch del feed RSS gira in background: un breve polling basta per la UI
      setTimeout(load, 1500)
      setTimeout(load, 4000)
    } catch (err) {
      console.error(err)
    } finally {
      setTimeout(() => setRefreshing(false), 4000)
    }
  }, [load])

  useEffect(() => {
    load().then(result => {
      // Primo utilizzo: il bollettino non è mai stato scaricato (a differenza
      // dei feed IOC, non si aggiorna da solo in background) — lo scarichiamo
      // automaticamente una volta, così il tab non appare vuoto senza spiegazione.
      if (result?.status?.state === 'never_fetched') {
        refresh()
      }
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  if (creatingFrom) {
    return (
      <CampaignForm
        initial={{
          ...emptyForm(),
          name: creatingFrom.title,
          reference_url: creatingFrom.link,
          description: creatingFrom.excerpt,
        }}
        onDone={() => setCreatingFrom(null)}
        onCancel={() => setCreatingFrom(null)}
        t={t}
      />
    )
  }

  if (!data) return <Spinner size={16} />

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
        <p style={{ fontSize: 12, color: 'var(--text-secondary)', flex: 1, margin: 0 }}>{t('intel.bulletins.description')}</p>
        {data.status && <StateBadge state={data.status.state} t={t} />}
        <Button variant="ghost" onClick={refresh} loading={refreshing}>{t('intel.refresh_one')}</Button>
      </div>
      {data.items.length === 0 ? (
        <EmptyState message={refreshing ? t('intel.refreshing') : t('intel.bulletins.empty')} />
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {data.items.map((item, i) => (
            <div key={i} style={{ padding: '10px 14px', background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <a href={item.link} target="_blank" rel="noreferrer" style={{ fontSize: 13, fontWeight: 600, color: 'var(--accent-blue)' }}>
                  {item.title}
                </a>
                <div style={{ flex: 1 }} />
                <Button variant="ghost" onClick={() => setCreatingFrom(item)}>{t('intel.bulletins.create_from')}</Button>
              </div>
              {item.excerpt && <p style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 6 }}>{item.excerpt}</p>}
            </div>
          ))}
        </div>
      )}
      <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 10 }}>{t('intel.bulletins.source_note')}</div>
    </div>
  )
}
