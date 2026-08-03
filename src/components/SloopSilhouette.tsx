interface Props {
  width?: number
  height?: number
  className?: string
  style?: React.CSSProperties
}

// Hand-drawn sloop (single-masted sailing yacht) silhouette.
// Viewbox 200×140: hull centred, mast rising, mainsail + jib set.
export function SloopSilhouette({ width = 200, height = 140, className, style }: Props) {
  const ink = 'var(--navy-950)'
  const sail = 'var(--navy-100)'
  const sea  = 'var(--paper-sea)'

  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 200 140"
      width={width}
      height={height}
      aria-label="Sailing yacht silhouette"
      className={className}
      style={style}
    >
      {/* Waterline / sea tint */}
      <path d="M0,105 Q50,102 100,105 Q150,108 200,105 L200,140 L0,140 Z" fill={sea} opacity="0.6" />
      {/* Gentle wave lines */}
      <path d="M10,110 Q30,107 50,110 Q70,113 90,110" fill="none" stroke={ink} strokeWidth="0.6" opacity="0.18" />
      <path d="M110,112 Q130,109 150,112 Q170,115 190,112" fill="none" stroke={ink} strokeWidth="0.6" opacity="0.18" />

      {/* Hull — classic sloop form */}
      <path
        d="M40,103 Q38,107 42,110 Q70,116 100,116 Q130,116 158,110 Q162,107 160,103 Z"
        fill={ink}
      />
      {/* Cabin/coamings */}
      <path
        d="M72,103 Q74,97 90,95 Q106,93 120,95 Q134,97 136,103 Z"
        fill={ink}
        opacity="0.85"
      />
      {/* Gunwale line */}
      <line x1="40" y1="103" x2="160" y2="103" stroke={ink} strokeWidth="1.2" />
      {/* Stem/bow */}
      <path d="M155,103 Q164,99 163,106" fill={ink} />
      {/* Keel hint */}
      <path d="M95,116 Q98,124 100,124 Q102,124 105,116" fill={ink} opacity="0.5" />

      {/* Mast — stepped at ~col 98 */}
      <line x1="98" y1="103" x2="98" y2="18" stroke={ink} strokeWidth="1.8" strokeLinecap="round" />
      {/* Boom */}
      <line x1="98" y1="97" x2="148" y2="103" stroke={ink} strokeWidth="1.2" strokeLinecap="round" />
      {/* Backstay */}
      <line x1="98" y1="18" x2="155" y2="100" stroke={ink} strokeWidth="0.6" opacity="0.4" />
      {/* Forestay */}
      <line x1="98" y1="18" x2="158" y2="101" stroke={ink} strokeWidth="0.6" opacity="0.35" />

      {/* Mainsail — full and drawing */}
      <path
        d="M98,22 L98,97 L148,103 Z"
        fill={sail}
        stroke={ink}
        strokeWidth="0.8"
        opacity="0.9"
      />
      {/* Mainsail roach curve */}
      <path
        d="M98,22 Q126,58 148,103"
        fill="none"
        stroke={ink}
        strokeWidth="0.5"
        opacity="0.3"
      />

      {/* Jib — hanked to forestay */}
      <path
        d="M98,32 L158,101 L98,88 Z"
        fill={sail}
        stroke={ink}
        strokeWidth="0.8"
        opacity="0.85"
      />

      {/* Burgee at masthead */}
      <polygon points="98,18 98,11 108,15" fill="var(--chart-red)" opacity="0.9" />
    </svg>
  )
}
