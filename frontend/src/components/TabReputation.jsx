// src/components/TabReputation.jsx
// Scheda reputazione: mostra lo stato di TUTTI i servizi,
// anche quelli non configurati o che non hanno trovato nulla.

import { useState, useEffect } from 'react'
import { Button } from './ui'
import { getSettings } from '../api/client'

const STATE_CONFIG = {
  malicious:       { icon: '🔴', label_it: 'MALEVOLO',       label_en: 'MALICIOUS',       color: 'var(--risk-high)',     bg: 'var(--risk-high-bg)' },
  clean:           { icon: '✅', label_it: 'Pulito',          label_en: 'Clean',           color: 'var(--risk-low)',      bg: 'var(--risk-low-bg)' },
  skipped:         { icon: '🔑', label_it: 'Chiave mancante', label_en: 'Key missing',     color: 'var(--text-muted)',    bg: 'var(--bg-card)' },
  not_applicable:  { icon: '➖', label_it: 'Non applicabile', label_en: 'Not applicable',  color: 'var(--accent-blue)',   bg: '#0f1f3d' },
  pending:         { icon: '⏳', label_it: 'In elaborazione', label_en: 'Processing',       color: 'var(--risk-medium)',    bg: 'var(--risk-medium-bg)' },
  error:           { icon: '⚠️', label_it: 'Errore',          label_en: 'Error',           color: 'var(--risk-medium)',   bg: 'var(--risk-medium-bg)' },
}

const ENTITY_ICONS = {
  ip:           '🌐',
  url:          '🔗',
  hash:         '🔢',
  'ip+url+hash': '🔍',
}

export default function TabReputation({ data, loading, error, onRun, t, lang }) {

  const [expanded, setExpanded] = useState({})
  const [apiKeys,   setApiKeys]  = useState({})   // { AbuseIPDB: bool, VirusTotal: bool, ... }
  const toggle = (name) => setExpanded(e => ({ ...e, [name]: !e[name] }))

  // Carica lo stato delle chiavi API al mount — indipendente dall'analisi
  useEffect(() => {
    getSettings().then(s => { if (s?.reputation_keys) setApiKeys(s.reputation_keys) }).catch(() => {})
  }, [])

  // Prima della prima esecuzione
  if (!data) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        <p style={{ color: 'var(--text-secondary)', fontSize: 13 }}>
          {t('rep.description')}
        </p>

        {/* Anteprima servizi disponibili */}
        <ServicePreview lang={lang} apiKeys={apiKeys} />

        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <Button onClick={onRun} loading={loading}>
            🔍 {t('rep.run_btn')}
          </Button>
          {error && <span style={{ color: 'var(--risk-high)', fontSize: 12 }}>{error}</span>}
        </div>
      </div>
    )
  }

  const registry = data.service_registry || []
  const allResults = [
    ...(data.results?.ip_results || []),
    ...(data.results?.url_results || []),
    ...(data.results?.hash_results || []),
  ]

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>

      {/* Sommario numerico */}
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: 4 }}>
        <SummaryPill
          value={`${data.reputation_score?.toFixed(0) ?? 0}/100`}
          label={t('rep.score')}
          color={data.reputation_score > 50 ? 'var(--risk-high)' : data.reputation_score > 0 ? 'var(--risk-medium)' : 'var(--risk-low)'}
        />
        <SummaryPill
          value={String(data.malicious_count ?? 0)}
          label={t('rep.malicious')}
          color={data.malicious_count > 0 ? 'var(--risk-high)' : 'var(--risk-low)'}
        />
        <SummaryPill
          value={String(registry.filter(s => s.state === 'clean' || s.state === 'malicious').length)}
          label={lang === 'it' ? 'Servizi interrogati' : 'Services queried'}
          color="var(--risk-low)"
        />
        <SummaryPill
          value={String(registry.filter(s => s.state === 'skipped').length)}
          label={lang === 'it' ? 'Chiave mancante' : 'Key missing'}
          color="var(--text-muted)"
        />
        {data.entities_analyzed && (<>
          <SummaryPill
            value={String(data.entities_analyzed.ips ?? 0)}
            label={t('rep.entities_ips')}
            color="var(--text-muted)"
          />
          <SummaryPill
            value={String(data.entities_analyzed.urls ?? 0)}
            label={t('rep.entities_urls')}
            color="var(--text-muted)"
          />
          {(data.entities_analyzed.hashes ?? 0) > 0 && (
            <SummaryPill
              value={String(data.entities_analyzed.hashes)}
              label={t('rep.entities_hashes')}
              color="var(--text-muted)"
            />
          )}
        </>)}
        <SummaryPill
          value={String(registry.filter(s => s.state === 'not_applicable').length)}
          label={lang === 'it' ? 'N/A per questa email' : 'N/A for this email'}
          color="var(--accent-blue)"
        />
      </div>

      {/* Griglia servizi */}
      {data.slow_running && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px', marginBottom: 8, borderRadius: 6, background: 'var(--bg-secondary)', border: '1px solid var(--accent-blue)44', fontSize: 12, color: 'var(--text-secondary)' }}>
          <span style={{ fontSize: 14 }}>⏳</span>
          <span>{t('rep.slow_running')}</span>
        </div>
      )}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {registry.map(svc => (
          <ServiceCard
            key={svc.name}
            svc={svc}
            expanded={!!expanded[svc.name]}
            onToggle={() => toggle(svc.name)}
            lang={lang}
          />
        ))}
      </div>

      {/* Risultati grezzi dettagliati (collassabili) */}
      {allResults.filter(r => r.queried).length > 0 && (
        <RawResults results={allResults} lang={lang} />
      )}

      <div style={{ marginTop: 4 }}>
        <Button onClick={onRun} loading={loading} variant="ghost">
          {t('rep.rerun_btn')}
        </Button>
      </div>
    </div>
  )
}

// ── Card singolo servizio ─────────────────────────────────────────────────────
function ServiceCard({ svc, expanded, onToggle, lang }) {
  const cfg = STATE_CONFIG[svc.state] || STATE_CONFIG.skipped
  const stateLabel = lang === 'it' ? cfg.label_it : cfg.label_en
  const hasDetails = svc.detail_results?.length > 0

  return (
    <div style={{
      borderRadius: 8,
      border: `1px solid ${svc.state === 'malicious' ? 'var(--risk-high)' : svc.state === 'error' ? 'var(--risk-medium)' : 'var(--border)'}`,
      background: 'var(--bg-card)',
      overflow: 'hidden',
    }}>
      {/* Header della card */}
      <div
        onClick={hasDetails ? onToggle : undefined}
        style={{
          display: 'flex', alignItems: 'center', gap: 10,
          padding: '10px 14px',
          cursor: hasDetails ? 'pointer' : 'default',
          background: svc.state === 'malicious' ? 'var(--risk-high-bg)' : 'transparent',
        }}
      >
        {/* Icona stato */}
        <span style={{ fontSize: 16, flexShrink: 0 }}>{cfg.icon}</span>

        {/* Nome servizio */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
            <span style={{ fontWeight: 600, fontSize: 13, color: 'var(--text-primary)' }}>
              {svc.name}
            </span>
            {/* Badge tipo entità */}
            <span style={{
              fontSize: 10, padding: '1px 6px', borderRadius: 3,
              background: 'var(--bg-secondary)', color: 'var(--text-muted)',
              border: '1px solid var(--border)',
            }}>
              {ENTITY_ICONS[svc.entity_type] || '📋'} {svc.entity_type}
            </span>
            {/* Badge stato */}
            <span style={{
              fontSize: 10, fontWeight: 700, padding: '1px 8px', borderRadius: 10,
              color: cfg.color, background: cfg.bg,
              border: `1px solid ${cfg.color}44`,
              letterSpacing: '0.04em',
            }}>
              {stateLabel}
            </span>
            {/* Badge conteggio se malicious */}
            {svc.malicious_count > 0 && (
              <span style={{
                fontSize: 10, fontWeight: 700, padding: '1px 8px', borderRadius: 10,
                color: '#fff', background: 'var(--risk-high)',
              }}>
                {svc.malicious_count} {lang === 'it' ? 'malevoli' : 'malicious'}
              </span>
            )}
          </div>
          {/* Descrizione e stato */}
          <div style={{ marginTop: 2 }}>
            <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>
              {svc.description}
            </span>
          </div>
          <div style={{ marginTop: 2 }}>
            <span style={{
              color: svc.state === 'malicious' ? 'var(--risk-high)' :
                     svc.state === 'error'     ? 'var(--risk-medium)' :
                     svc.state === 'clean'     ? 'var(--risk-low)' :
                     'var(--text-muted)',
              fontSize: 11,
            }}>
              {svc.state_detail}
            </span>
          </div>
        </div>

        {/* Toggle expand se ci sono dettagli */}
        {hasDetails && (
          <span style={{ color: 'var(--text-muted)', fontSize: 12, flexShrink: 0 }}>
            {expanded ? '▲' : '▼'} {svc.queried_count} {lang === 'it' ? 'risultati' : 'results'}
          </span>
        )}

        {/* Badge chiave richiesta */}
        {svc.state === 'skipped' && svc.requires_key && (
          <span style={{
            fontSize: 10, padding: '1px 7px', borderRadius: 3,
            color: 'var(--text-muted)', background: 'var(--bg-secondary)',
            border: '1px solid var(--border)', flexShrink: 0,
          }}>
            🔑 {lang === 'it' ? 'chiave richiesta' : 'key required'}
          </span>
        )}
      </div>

      {/* Dettagli espansi */}
      {expanded && hasDetails && (
        <div style={{
          borderTop: '1px solid var(--border)',
          padding: '10px 14px',
          display: 'flex', flexDirection: 'column', gap: 6,
        }}>
          {svc.detail_results.map((r, i) => (
            <DetailRow key={i} r={r} lang={lang} />
          ))}
        </div>
      )}
    </div>
  )
}

// ── Riga dettaglio singola entità ─────────────────────────────────────────────
function DetailRow({ r, lang }) {
  // Servizi informativi: non malevoli per natura, mostrano dati contestuali
  const isInfoService = ['ASN Lookup', 'crt.sh', 'Redirect Chain', 'Shodan InternetDB', 'CIRCL Passive DNS'].includes(r.source)
  const icon = r.is_malicious ? '🔴'
             : r.error        ? '⚠️'
             : isInfoService  ? 'ℹ️'
             : '✅'
  const bgColor = r.is_malicious ? 'var(--risk-high-bg)'
                : isInfoService  ? 'var(--bg-tertiary, var(--bg-secondary))'
                : 'var(--bg-secondary)'
  return (
    <div style={{
      padding: '6px 10px', borderRadius: 6,
      background: bgColor,
      border: `1px solid ${r.is_malicious ? 'var(--risk-high)33' : 'var(--border)'}`,
    }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
        <span style={{ flexShrink: 0, fontSize: 13 }}>{icon}</span>
        <div style={{ minWidth: 0, flex: 1 }}>
          {/* Entità */}
          <div style={{
            fontFamily: 'var(--font-mono)', fontSize: 11,
            color: 'var(--text-secondary)', wordBreak: 'break-all', marginBottom: 2,
          }}>
            {r.entity}
          </div>
          {/* Dettaglio */}
          {r.detail && (
            <div style={{ color: r.is_malicious ? 'var(--risk-high)' : 'var(--text-muted)', fontSize: 11 }}>
              {r.detail}
            </div>
          )}
          {/* Errore */}
          {r.error && (
            <div style={{ color: 'var(--risk-medium)', fontSize: 11 }}>
              ⚠ {r.error}
            </div>
          )}
          {/* Confidence bar */}
          {r.confidence > 0 && (
            <div style={{ marginTop: 4 }}>
              <div style={{
                height: 3, borderRadius: 2,
                background: 'var(--border)', overflow: 'hidden', width: '100%',
              }}>
                <div style={{
                  height: '100%', borderRadius: 2,
                  width: `${r.confidence}%`,
                  background: r.confidence > 60 ? 'var(--risk-high)' :
                               r.confidence > 30 ? 'var(--risk-medium)' : 'var(--risk-low)',
                  transition: 'width 0.4s ease',
                }} />
              </div>
              <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 1 }}>
                Confidence: {r.confidence.toFixed(0)}%
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// ── Anteprima servizi prima dell'esecuzione ───────────────────────────────────
function ServicePreview({ lang, apiKeys }) {
  const services = [
    // ── IP ───────────────────────────────────────────────────────────────────
    { name: 'AbuseIPDB',         needs_key: true,  type: 'ip',          desc_it: 'Reputazione IP (header SMTP, X-Originating-IP, IP negli URL)', desc_en: 'IP reputation (SMTP hops, X-Originating-IP, direct IPs)' },
    { name: 'VirusTotal',        needs_key: true,  type: 'ip+url+hash', desc_it: 'Multi-engine: IP, URL e hash allegati',                        desc_en: 'Multi-engine: IP, URL and attachment hashes' },
    { name: 'Spamhaus DROP',     needs_key: false, type: 'ip',          desc_it: 'Blocklist IP malevoli di alto profilo — no chiave',             desc_en: 'High-profile malicious IP blocklist — no key' },
    { name: 'ASN Lookup',        needs_key: false, type: 'ip',          desc_it: 'Autonomous System per ogni IP (ipinfo.io) — no chiave',         desc_en: 'ASN info for each IP (ipinfo.io) — no key' },
    { name: 'Shodan InternetDB', needs_key: false, type: 'ip',          desc_it: 'Porte aperte, CVE e tag per ogni IP (Shodan) — no chiave',                   desc_en: 'Open ports, CVEs and tags per IP (Shodan) — no key' },
    { name: 'CIRCL Passive DNS', needs_key: true,  type: 'ip+url',      desc_it: 'Passive DNS storico IP/domini — CIRCL_API_KEY (gratuita, circl.lu/pdns)',    desc_en: 'Historical passive DNS for IPs/domains — CIRCL_API_KEY (free, circl.lu/pdns)' },
    // ── URL ──────────────────────────────────────────────────────────────────
    { name: 'OpenPhish',         needs_key: false, type: 'url',         desc_it: 'Feed URL phishing aggiornato — no chiave',                      desc_en: 'Live phishing URL feed — no key' },
    { name: 'PhishTank',         needs_key: true,  type: 'url',         desc_it: 'URL phishing verificati dalla community',                       desc_en: 'Community-verified phishing URLs' },
    { name: 'Redirect Chain',    needs_key: false, type: 'url',         desc_it: 'Segue i redirect degli URL shortener — no chiave',              desc_en: 'Follows URL shortener redirects — no key' },
    { name: 'crt.sh',            needs_key: false, type: 'url',         desc_it: 'Certificati TLS del dominio (età, sottodomini) — no chiave',    desc_en: 'Domain TLS certificates (age, subdomains) — no key' },
    { name: 'URLhaus',           needs_key: true,  type: 'url',         desc_it: 'Database URL malware di abuse.ch (ABUSECH_API_KEY)',            desc_en: 'Malware URL database by abuse.ch (ABUSECH_API_KEY)' },
    // ── Hash ─────────────────────────────────────────────────────────────────
    { name: 'MalwareBazaar',     needs_key: true,  type: 'hash',        desc_it: 'Hash allegati nel database malware (API key richiesta)',         desc_en: 'Attachment hashes in malware database (API key required)' },
    // ── Multi-tipo ───────────────────────────────────────────────────────────
    { name: 'ThreatFox',         needs_key: true,  type: 'ip+url+hash', desc_it: 'Database IOC abuse.ch (IP, URL, hash) (ABUSECH_API_KEY)',       desc_en: 'abuse.ch IOC database (IPs, URLs, hashes) (ABUSECH_API_KEY)' },
  ]
  return (
    <div style={{
      borderRadius: 8, border: '1px solid var(--border)',
      background: 'var(--bg-card)', overflow: 'hidden',
    }}>
      <div style={{
        padding: '8px 14px', borderBottom: '1px solid var(--border)',
        fontSize: 11, color: 'var(--text-muted)', fontWeight: 600,
        textTransform: 'uppercase', letterSpacing: '0.05em',
      }}>
        {lang === 'it' ? 'Servizi disponibili' : 'Available services'}
      </div>
      {services.map(s => (
        <div key={s.name} style={{
          display: 'flex', alignItems: 'center', gap: 10,
          padding: '8px 14px', borderBottom: '1px solid var(--border)',
        }}>
          <span style={{ fontSize: 12 }}>{ENTITY_ICONS[s.type] || '📋'}</span>
          <div style={{ flex: 1 }}>
            <span style={{ fontWeight: 600, fontSize: 12, color: 'var(--text-primary)' }}>{s.name}</span>
            <span style={{ color: 'var(--text-muted)', fontSize: 11, marginLeft: 8 }}>
              {lang === 'it' ? s.desc_it : s.desc_en}
            </span>
          </div>
          {s.needs_key ? (() => {
            // Cerca nel service_registry se la chiave è effettivamente configurata
            // apiKeys = { "AbuseIPDB": true/false, ... } da /api/settings/
            const isConfigured = apiKeys[s.name] === true
            return !isConfigured
              ? <span style={{ fontSize: 10, color: 'var(--risk-medium)', padding: '1px 6px', borderRadius: 3, border: '1px solid var(--risk-medium)44' }}>
                  🔑 {lang === 'it' ? 'API key non configurata' : 'API key not configured'}
                </span>
              : <span style={{ fontSize: 10, color: 'var(--risk-low)', padding: '1px 6px', borderRadius: 3, border: '1px solid var(--risk-low)44' }}>
                  ✓ {lang === 'it' ? 'API key configurata' : 'API key configured'}
                </span>
          })() : (
            <span style={{ fontSize: 10, color: 'var(--risk-low)', padding: '1px 6px', borderRadius: 3, border: '1px solid var(--risk-low)44' }}>
              ✓ {lang === 'it' ? 'gratuito' : 'free'}
            </span>
          )}
        </div>
      ))}
    </div>
  )
}

// ── Risultati grezzi collassabili ─────────────────────────────────────────────
function RawResults({ results, lang }) {
  const [open, setOpen] = useState(false)
  const queried = results.filter(r => r.queried)
  return (
    <div style={{ borderRadius: 8, border: '1px solid var(--border)', overflow: 'hidden' }}>
      <button onClick={() => setOpen(o => !o)} style={{
        width: '100%', padding: '8px 14px',
        background: 'var(--bg-card)', border: 'none', cursor: 'pointer',
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        color: 'var(--text-secondary)', fontSize: 12,
      }}>
        <span>{lang === 'it' ? `📋 Tutti i risultati grezzi (${queried.length})` : `📋 All raw results (${queried.length})`}</span>
        <span>{open ? '▲' : '▼'}</span>
      </button>
      {open && (
        <div style={{ padding: '10px 14px', borderTop: '1px solid var(--border)', display: 'flex', flexDirection: 'column', gap: 4 }}>
          {queried.map((r, i) => (
            <div key={i} style={{
              padding: '5px 10px', borderRadius: 4,
              background: 'var(--bg-secondary)', border: '1px solid var(--border)',
              display: 'flex', gap: 10, alignItems: 'flex-start',
            }}>
              <span style={{
                padding: '1px 6px', borderRadius: 3, fontSize: 10, fontWeight: 700, flexShrink: 0,
                background: r.is_malicious ? 'var(--risk-high-bg)' : 'var(--risk-low-bg)',
                color: r.is_malicious ? 'var(--risk-high)' : 'var(--risk-low)',
                border: `1px solid ${r.is_malicious ? 'var(--risk-high)' : 'var(--risk-low)'}44`,
              }}>{r.source}</span>
              <div style={{ minWidth: 0, flex: 1 }}>
                <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-secondary)', wordBreak: 'break-all' }}>{r.entity}</div>
                {r.detail && <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 1 }}>{r.detail}</div>}
                {r.error  && <div style={{ fontSize: 10, color: 'var(--risk-medium)', marginTop: 1 }}>⚠ {r.error}</div>}
              </div>
              {r.is_malicious && (
                <span style={{ color: 'var(--risk-high)', fontWeight: 700, fontSize: 10, flexShrink: 0 }}>
                  {lang === 'it' ? '⚠ MALEVOLO' : '⚠ MALICIOUS'}
                </span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Pill sommario ─────────────────────────────────────────────────────────────
function SummaryPill({ value, label, color }) {
  return (
    <div style={{
      padding: '8px 14px', borderRadius: 8, textAlign: 'center',
      background: 'var(--bg-card)', border: '1px solid var(--border)',
      minWidth: 80,
    }}>
      <div style={{ fontSize: 18, fontWeight: 700, fontFamily: 'var(--font-mono)', color }}>{value}</div>
      <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 1 }}>{label}</div>
    </div>
  )
}