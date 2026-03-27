// src/components/RiskMeter.jsx

const RISK_COLOR = {
  low:      '#22c55e',
  medium:   '#f59e0b',
  high:     '#ef4444',
  critical: '#a855f7',
}

const RISK_LABEL = {
  low:      'Basso',
  medium:   'Moderato',
  high:     'Alto',
  critical: 'Critico',
}

export default function RiskMeter({ score = 0, label = 'low', contributions = [] }) {
  const color = RISK_COLOR[label] || '#22c55e'
  const pct   = Math.min(Math.max(score, 0), 100)

  // Arc SVG (semicircle gauge)
  const r   = 54
  const cx  = 70
  const cy  = 70
  const arc = Math.PI  // 180° semicircle
  const x1  = cx - r
  const y1  = cy
  const x2  = cx + r
  const y2  = cy

  // Needle angle: -180° (0%) → 0° (100%)
  const angleDeg = -180 + (pct / 100) * 180
  const angleRad = (angleDeg * Math.PI) / 180
  const needleX  = cx + (r - 8) * Math.cos(angleRad)
  const needleY  = cy + (r - 8) * Math.sin(angleRad)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4 }}>
      <svg width={140} height={82} viewBox="0 0 140 82" style={{ overflow: 'visible' }}>
        {/* Track */}
        <path
          d={`M ${x1} ${y1} A ${r} ${r} 0 0 1 ${x2} ${y2}`}
          fill="none"
          stroke="var(--border)"
          strokeWidth={10}
          strokeLinecap="round"
        />
        {/* Fill */}
        {pct > 0 && (
          <path
            d={`M ${x1} ${y1} A ${r} ${r} 0 0 1 ${x2} ${y2}`}
            fill="none"
            stroke={color}
            strokeWidth={10}
            strokeLinecap="round"
            strokeDasharray={`${(pct / 100) * Math.PI * r} ${Math.PI * r}`}
            style={{ filter: `drop-shadow(0 0 6px ${color}88)` }}
          />
        )}
        {/* Needle */}
        <line
          x1={cx} y1={cy}
          x2={needleX} y2={needleY}
          stroke={color}
          strokeWidth={2}
          strokeLinecap="round"
        />
        <circle cx={cx} cy={cy} r={4} fill={color} />

        {/* Labels */}
        <text x={x1 - 2} y={cy + 14} fill="var(--text-muted)" fontSize={9} textAnchor="middle">0</text>
        <text x={x2 + 2} y={cy + 14} fill="var(--text-muted)" fontSize={9} textAnchor="middle">100</text>

        {/* Score */}
        <text x={cx} y={cy - 10} fill={color} fontSize={22} fontWeight={700} textAnchor="middle"
          fontFamily="var(--font-mono)">
          {Math.round(pct)}
        </text>
      </svg>

      <div style={{
        padding: '4px 16px',
        borderRadius: 20,
        background: color + '22',
        border: `1px solid ${color}55`,
        color: color,
        fontWeight: 700,
        fontSize: 13,
        letterSpacing: '0.06em',
        textTransform: 'uppercase',
      }}>
        {RISK_LABEL[label] || label}
      </div>

      {/* Module breakdown */}
      {contributions?.length > 0 && (
        <div style={{ width: '100%', marginTop: 12 }}>
          {contributions.map(c => (
            <div key={c.module} style={{ marginBottom: 6 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 2 }}>
                <span style={{ color: 'var(--text-muted)', fontSize: 11, textTransform: 'capitalize' }}>
                  {c.module}
                </span>
                <span style={{ color: 'var(--text-secondary)', fontSize: 11, fontFamily: 'var(--font-mono)' }}>
                  {c.raw_score?.toFixed(0)}/100
                </span>
              </div>
              <div style={{
                height: 4,
                background: 'var(--border)',
                borderRadius: 2,
                overflow: 'hidden',
              }}>
                <div style={{
                  height: '100%',
                  width: `${c.raw_score || 0}%`,
                  background: c.raw_score > 60 ? 'var(--risk-high)' :
                               c.raw_score > 30 ? 'var(--risk-medium)' : 'var(--risk-low)',
                  borderRadius: 2,
                  transition: 'width 0.4s ease',
                }} />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
