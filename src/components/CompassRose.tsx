// Public-domain compass rose — derived from CC0 Wikimedia simple plain variant.
// Recoloured to Admiralty palette: navy-950 major points, soundings minor points.
interface Props {
  size?: number
  className?: string
  style?: React.CSSProperties
}

export function CompassRose({ size = 120, className, style }: Props) {
  const navy  = 'var(--navy-950)'
  const light = 'var(--navy-100)'
  const red   = 'var(--chart-red)'

  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width={size}
      height={size}
      viewBox="0 0 100 100"
      aria-label="Compass rose"
      className={className}
      style={style}
    >
      {/* Outer ring */}
      <circle cx="50" cy="50" r="47" fill="none" stroke={navy} strokeWidth="0.8" opacity="0.25" />
      <circle cx="50" cy="50" r="40" fill="none" stroke={navy} strokeWidth="0.4" opacity="0.15" />

      {/* 8 minor cardinal tick marks */}
      {[22.5, 67.5, 112.5, 157.5, 202.5, 247.5, 292.5, 337.5].map((deg) => {
        const rad = (deg * Math.PI) / 180
        const x1 = 50 + 40 * Math.sin(rad)
        const y1 = 50 - 40 * Math.cos(rad)
        const x2 = 50 + 46 * Math.sin(rad)
        const y2 = 50 - 46 * Math.cos(rad)
        return <line key={deg} x1={x1} y1={y1} x2={x2} y2={y2} stroke={navy} strokeWidth="0.6" opacity="0.3" />
      })}

      {/* Major cardinal points — N, E, S, W (large diamond arms) */}
      {/* North arm — red */}
      <polygon points="50,4 46,50 50,44 54,50" fill={red} />
      <polygon points="50,4 46,50 50,44 54,50" fill={red} opacity="0.85" />
      {/* North left half */}
      <polygon points="50,4 46,50 50,44" fill={red} />
      {/* North right half slightly lighter */}
      <polygon points="50,4 54,50 50,44" fill="oklch(56% 0.16 24)" />

      {/* South arm */}
      <polygon points="50,96 46,50 50,56" fill={navy} />
      <polygon points="50,96 54,50 50,56" fill={light} />

      {/* West arm */}
      <polygon points="4,50 50,46 50,54" fill={navy} />
      <polygon points="4,50 50,46 44,50" fill={navy} />
      <polygon points="4,50 50,54 44,50" fill={light} />

      {/* East arm */}
      <polygon points="96,50 50,46 56,50" fill={navy} />
      <polygon points="96,50 50,54 56,50" fill={light} />

      {/* Intercardinal points — NE, SE, SW, NW (smaller) */}
      {[45, 135, 225, 315].map((deg) => {
        const rad = (deg * Math.PI) / 180
        const tip = { x: 50 + 32 * Math.sin(rad), y: 50 - 32 * Math.cos(rad) }
        const l90 = { x: 50 + 8 * Math.sin(rad - Math.PI / 2), y: 50 - 8 * Math.cos(rad - Math.PI / 2) }
        const r90 = { x: 50 + 8 * Math.sin(rad + Math.PI / 2), y: 50 - 8 * Math.cos(rad + Math.PI / 2) }
        const base = { x: 50 + 14 * Math.sin(rad + Math.PI), y: 50 - 14 * Math.cos(rad + Math.PI) }
        return (
          <g key={deg}>
            <polygon
              points={`${tip.x},${tip.y} ${l90.x},${l90.y} ${base.x},${base.y}`}
              fill={navy}
              opacity="0.7"
            />
            <polygon
              points={`${tip.x},${tip.y} ${r90.x},${r90.y} ${base.x},${base.y}`}
              fill={light}
              opacity="0.7"
            />
          </g>
        )
      })}

      {/* Centre hub */}
      <circle cx="50" cy="50" r="5" fill={navy} stroke={light} strokeWidth="1" />
      <circle cx="50" cy="50" r="2" fill={red} />

      {/* N label */}
      <text
        x="50" y="2.5"
        textAnchor="middle"
        fontSize="8"
        fontFamily="Georgia, serif"
        fontWeight="700"
        fill={red}
        letterSpacing="0.5"
      >N</text>
    </svg>
  )
}
