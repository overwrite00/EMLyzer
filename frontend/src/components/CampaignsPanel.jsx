// src/components/CampaignsPanel.jsx
import { useState } from 'react'
import { getCampaigns } from '../api/client'
import { Button, Spinner } from './ui'
import { useLang } from '../i18n/LangContext'

const TYPE_ICONS = {
  subject:       '📝',
  body_hash:     '📋',
  message_id:    '🔖',
  campaign_id:   '📣',
  sender_domain: '🌐',
}

const RISK_COLORS = {
  low:      'var(--risk-low)',
  medium:   'var(--risk-medium)',
  high:     'var(--risk-high)',
  critical: 'var(--risk-critical)',
}

export default function CampaignsPanel() {
  const { t } = useLang()
  const [data, setData]         = useState(null)
  const [loading, setLoading]   = useState(false)
  const [threshold, setThreshold] = useState(0.6)
  const [expanded, setExpanded] = useState({})

  async function run() {
    setLoading(true)
    try {
      const result = await getCampaigns({ threshold, minSize: 2 })
      setData(result)
      setExpanded({})
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  const toggle = (id) => setExpanded(e => ({ ...e, [id]: !e[id] }))

  return (
    <section style={{ marginBottom: 32 }}>
      <h2 style={{
        fontSize: 13, fontWeight: 600, color: 'var(--text-secondary)',
        marginBottom: 12, letterSpacing: '0.06em', textTransform: 'uppercase',
      }}>
        🕸 {t('camp.title')}
      </h2>

      {/* Controlli */}
      <div style={{
        display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap',
        padding: '12px 16px', background: 'var(--bg-secondary)',
        border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)',
        marginBottom: 12,
      }}>
        <p style={{ color: 'var(--text-secondary)', fontSize: 13, flex: 1 }}>
          {t('camp.description')}
        </p>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <label style={{ fontSize: 12, color: 'var(--text-muted)' }}>
            {t('camp.threshold')}
          </label>
          <input
            type="range" min="0.3" max="1.0" step="0.1"
            value={threshold}
            onChange={e => setThreshold(parseFloat(e.target.value))}
            style={{ width: 80, accentColor: 'var(--accent-blue)' }}
          />
          <span style={{ fontSize: 12, fontFamily: 'var(--font-mono)', color: 'var(--text-primary)', minWidth: 30 }}>
            {Math.round(threshold * 100)}%
          </span>
        </div>
        <Button onClick={run} loading={loading} variant={data ? 'ghost' : 'primary'}>
          {data ? t('camp.rerun_btn') : t('camp.run_btn')}
        </Button>
      </div>

      {/* Loading */}
      {loading && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '16px 0', color: 'var(--text-muted)', fontSize: 13 }}>
          <Spinner size={16} /> {t('camp.loading')}
        </div>
      )}

      {/* Risultati */}
      {!loading && data && (
        <>
          {/* Sommario */}
          <div style={{ display: 'flex', gap: 12, marginBottom: 12, flexWrap: 'wrap' }}>
            {[
              [t('camp.total',   { n: data.total_emails_analyzed }), 'var(--text-secondary)'],
              [t('camp.found',   { n: data.clusters_found }),        data.clusters_found > 0 ? 'var(--risk-high)' : 'var(--risk-low)'],
              [t('camp.isolated', { n: data.isolated_emails }),      'var(--text-muted)'],
            ].map(([label, color]) => (
              <div key={label} style={{
                padding: '6px 14px', borderRadius: 8,
                background: 'var(--bg-card)', border: '1px solid var(--border)',
                fontSize: 13, color,
              }}>
                {label}
              </div>
            ))}
          </div>

          {/* Nessun cluster */}
          {data.clusters_found === 0 ? (
            <div style={{
              padding: '24px', textAlign: 'center',
              color: 'var(--text-muted)', fontSize: 13,
              background: 'var(--bg-secondary)', borderRadius: 'var(--radius-lg)',
              border: '1px solid var(--border)',
            }}>
              ✅ {t('camp.no_clusters')}
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {data.clusters.map(cluster => (
                <ClusterCard
                  key={cluster.cluster_id}
                  cluster={cluster}
                  expanded={!!expanded[cluster.cluster_id]}
                  onToggle={() => toggle(cluster.cluster_id)}
                  t={t}
                />
              ))}
            </div>
          )}
        </>
      )}
    </section>
  )
}

function ClusterCard({ cluster, expanded, onToggle, t }) {
  const maxRiskColor = RISK_COLORS[cluster.risk_labels?.reduce(
    (worst, l) => {
      const order = { critical: 3, high: 2, medium: 1, low: 0 }
      return (order[l] ?? 0) > (order[worst] ?? 0) ? l : worst
    }, 'low'
  )] || 'var(--text-muted)'

  const typeIcon = TYPE_ICONS[cluster.similarity_type] || '📌'
  const typeLabel = t(`camp.type.${cluster.similarity_type}`) || cluster.similarity_type

  return (
    <div style={{
      borderRadius: 8,
      border: `1px solid ${cluster.max_risk_score > 50 ? 'var(--risk-high)33' : 'var(--border)'}`,
      background: 'var(--bg-card)', overflow: 'hidden',
    }}>
      {/* Header */}
      <div
        onClick={onToggle}
        style={{
          display: 'flex', alignItems: 'center', gap: 12,
          padding: '12px 16px', cursor: 'pointer',
          background: cluster.max_risk_score > 70 ? 'var(--risk-high-bg)' : 'transparent',
        }}
      >
        {/* Cluster ID */}
        <span style={{
          fontFamily: 'var(--font-mono)', fontSize: 11, fontWeight: 700,
          color: 'var(--accent-blue)', flexShrink: 0,
        }}>
          {cluster.cluster_id}
        </span>

        {/* Tipo */}
        <span style={{
          fontSize: 10, padding: '2px 8px', borderRadius: 3,
          background: 'var(--bg-secondary)', color: 'var(--text-muted)',
          border: '1px solid var(--border)', flexShrink: 0,
        }}>
          {typeIcon} {typeLabel}
        </span>

        {/* Descrizione */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 13, color: 'var(--text-primary)', fontWeight: 500 }}>
            {cluster.description}
          </div>
          {cluster.common_value && (
            <div style={{
              fontSize: 11, color: 'var(--text-muted)',
              fontFamily: 'var(--font-mono)', marginTop: 2,
              overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
            }}>
              {t('camp.common_value')} {cluster.common_value}
            </div>
          )}
        </div>

        {/* Badge email count */}
        <span style={{
          padding: '2px 10px', borderRadius: 20, fontSize: 11, fontWeight: 700,
          color: maxRiskColor, background: maxRiskColor + '22',
          border: `1px solid ${maxRiskColor}44`, flexShrink: 0,
        }}>
          {t('camp.emails_in_cluster', { n: cluster.email_count })}
        </span>

        {/* Max risk score */}
        <span style={{
          fontSize: 12, fontFamily: 'var(--font-mono)',
          color: maxRiskColor, fontWeight: 700, flexShrink: 0,
        }}>
          {cluster.max_risk_score.toFixed(0)}
        </span>

        <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>
          {expanded ? '▲' : '▼'}
        </span>
      </div>

      {/* Dettagli espansi */}
      {expanded && (
        <div style={{
          borderTop: '1px solid var(--border)',
          padding: '12px 16px',
        }}>
          <div style={{ display: 'flex', gap: 24, marginBottom: 10, flexWrap: 'wrap' }}>
            {cluster.first_seen && (
              <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                {t('camp.first_seen')} <span style={{ color: 'var(--text-secondary)' }}>{cluster.first_seen.slice(0,10)}</span>
              </div>
            )}
            {cluster.last_seen && cluster.last_seen !== cluster.first_seen && (
              <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                {t('camp.last_seen')} <span style={{ color: 'var(--text-secondary)' }}>{cluster.last_seen.slice(0,10)}</span>
              </div>
            )}
            <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
              {t('camp.max_risk')} <span style={{ color: maxRiskColor, fontWeight: 700 }}>{cluster.max_risk_score.toFixed(1)}</span>
            </div>
          </div>

          {/* Lista job_id */}
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {cluster.job_ids.map((id, i) => (
              <span key={id} style={{
                padding: '2px 8px', borderRadius: 4,
                background: 'var(--bg-secondary)', border: '1px solid var(--border)',
                fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)',
              }}>
                {id.slice(0, 8)}…
                {cluster.risk_labels[i] && (
                  <span style={{ color: RISK_COLORS[cluster.risk_labels[i]], marginLeft: 4 }}>
                    {cluster.risk_labels[i]}
                  </span>
                )}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
