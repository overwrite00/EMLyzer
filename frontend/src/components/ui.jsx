// src/components/ui.jsx
// Componenti UI riusabili

export function Card({ children, className = '' }) {
  return (
    <div style={{
      background: 'var(--bg-card)',
      border: '1px solid var(--border)',
      borderRadius: 'var(--radius-lg)',
      padding: '20px',
      ...parseStyle(className),
    }}>
      {children}
    </div>
  )
}

export function Section({ title, icon, children, defaultOpen = true }) {
  return (
    <div style={{ marginBottom: 24 }}>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        marginBottom: 12,
        paddingBottom: 8,
        borderBottom: '1px solid var(--border)',
      }}>
        {icon && <span style={{ fontSize: 16 }}>{icon}</span>}
        <h3 style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)', letterSpacing: '0.02em' }}>
          {title}
        </h3>
      </div>
      {children}
    </div>
  )
}

const SEVERITY_STYLES = {
  info:     { color: 'var(--severity-info)',     bg: '#0c2340' },
  low:      { color: 'var(--severity-low)',      bg: '#052a12' },
  medium:   { color: 'var(--severity-medium)',   bg: '#2a1800' },
  high:     { color: 'var(--severity-high)',     bg: '#2a0a0a' },
  critical: { color: 'var(--severity-critical)', bg: '#1a0a2e' },
}

const RISK_STYLES = {
  low:      { color: 'var(--risk-low)',      bg: 'var(--risk-low-bg)' },
  medium:   { color: 'var(--risk-medium)',   bg: 'var(--risk-medium-bg)' },
  high:     { color: 'var(--risk-high)',     bg: 'var(--risk-high-bg)' },
  critical: { color: 'var(--risk-critical)', bg: 'var(--risk-critical-bg)' },
}

export function SeverityBadge({ severity }) {
  const s = SEVERITY_STYLES[severity?.toLowerCase()] || SEVERITY_STYLES.info
  return (
    <span style={{
      display: 'inline-block',
      padding: '1px 8px',
      borderRadius: 4,
      fontSize: 11,
      fontWeight: 700,
      letterSpacing: '0.06em',
      textTransform: 'uppercase',
      color: s.color,
      background: s.bg,
      border: `1px solid ${s.color}33`,
    }}>
      {severity}
    </span>
  )
}

export function RiskBadge({ label, score }) {
  const s = RISK_STYLES[label?.toLowerCase()] || RISK_STYLES.low
  return (
    <span style={{
      display: 'inline-flex',
      alignItems: 'center',
      gap: 6,
      padding: '3px 12px',
      borderRadius: 20,
      fontSize: 12,
      fontWeight: 700,
      letterSpacing: '0.05em',
      textTransform: 'uppercase',
      color: s.color,
      background: s.bg,
      border: `1px solid ${s.color}55`,
    }}>
      {score !== undefined && <span style={{ fontFamily: 'var(--font-mono)' }}>{score.toFixed(0)}</span>}
      {label}
    </span>
  )
}

export function KeyValue({ label, value, mono = false }) {
  if (!value && value !== 0) return null
  return (
    <div style={{ display: 'flex', gap: 8, marginBottom: 4, alignItems: 'flex-start' }}>
      <span style={{ color: 'var(--text-muted)', minWidth: 160, flexShrink: 0, fontSize: 12 }}>{label}</span>
      <span style={{
        color: 'var(--text-primary)',
        fontFamily: mono ? 'var(--font-mono)' : undefined,
        fontSize: mono ? '0.82em' : '13px',
        wordBreak: 'break-all',
      }}>
        {value}
      </span>
    </div>
  )
}

export function FindingRow({ finding }) {
  const { severity, description, evidence, category } = finding
  return (
    <div style={{
      display: 'flex',
      gap: 10,
      padding: '8px 10px',
      borderRadius: 6,
      background: 'var(--bg-secondary)',
      border: '1px solid var(--border)',
      marginBottom: 6,
      alignItems: 'flex-start',
    }}>
      <SeverityBadge severity={severity} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ color: 'var(--text-primary)', fontSize: 13 }}>{description}</div>
        {evidence && (
          <div style={{
            color: 'var(--text-muted)',
            fontSize: 11,
            fontFamily: 'var(--font-mono)',
            marginTop: 3,
            wordBreak: 'break-all',
          }}>
            {evidence}
          </div>
        )}
      </div>
    </div>
  )
}

export function EmptyState({ message = 'Nessun dato disponibile' }) {
  return (
    <div style={{ color: 'var(--text-muted)', fontSize: 13, padding: '8px 0', fontStyle: 'italic' }}>
      {message}
    </div>
  )
}

export function Spinner({ size = 20 }) {
  return (
    <div style={{
      width: size,
      height: size,
      border: `2px solid var(--border)`,
      borderTopColor: 'var(--accent-blue)',
      borderRadius: '50%',
      animation: 'spin 0.7s linear infinite',
    }} />
  )
}

export function Button({ children, onClick, variant = 'primary', disabled = false, loading = false, style = {} }) {
  const variants = {
    primary: { background: 'var(--accent-blue)', color: '#fff', border: 'none' },
    secondary: { background: 'var(--bg-card)', color: 'var(--text-primary)', border: '1px solid var(--border)' },
    danger: { background: '#7f1d1d', color: '#fca5a5', border: '1px solid #991b1b' },
    ghost: { background: 'transparent', color: 'var(--text-secondary)', border: '1px solid var(--border)' },
  }
  const v = variants[variant] || variants.primary
  return (
    <button
      onClick={onClick}
      disabled={disabled || loading}
      style={{
        ...v,
        padding: '7px 16px',
        borderRadius: 'var(--radius)',
        fontSize: 13,
        fontWeight: 500,
        cursor: disabled || loading ? 'not-allowed' : 'pointer',
        opacity: disabled || loading ? 0.6 : 1,
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
        transition: 'opacity 0.15s',
        fontFamily: 'var(--font-sans)',
        ...style,
      }}
    >
      {loading && <Spinner size={13} />}
      {children}
    </button>
  )
}

// Helper: non usato per styling ma utile
function parseStyle(className) { return {} }
