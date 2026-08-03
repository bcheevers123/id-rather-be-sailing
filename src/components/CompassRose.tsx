import { useEffect, useRef, useState } from 'react'

interface Props {
  size?: number
  className?: string
  style?: React.CSSProperties
}

export function CompassRose({ size = 120, className, style }: Props) {
  const svgRef = useRef<SVGSVGElement>(null)
  const [angle, setAngle] = useState(0)

  useEffect(() => {
    const onMove = (e: MouseEvent | TouchEvent) => {
      const el = svgRef.current
      if (!el) return
      const rect = el.getBoundingClientRect()
      const cx = rect.left + rect.width / 2
      const cy = rect.top + rect.height / 2
      const clientX = 'touches' in e ? e.touches[0].clientX : e.clientX
      const clientY = 'touches' in e ? e.touches[0].clientY : e.clientY
      const dx = clientX - cx
      const dy = clientY - cy
      // atan2 from compass centre to cursor; offset so 0° = north (up)
      const deg = (Math.atan2(dx, -dy) * 180) / Math.PI
      setAngle(deg)
    }
    window.addEventListener('mousemove', onMove)
    window.addEventListener('touchmove', onMove, { passive: true })
    return () => {
      window.removeEventListener('mousemove', onMove)
      window.removeEventListener('touchmove', onMove)
    }
  }, [])

  const navy  = 'var(--navy-950)'
  const light = 'var(--navy-100)'
  const red   = 'var(--chart-red)'

  return (
    <svg
      ref={svgRef}
      xmlns="http://www.w3.org/2000/svg"
      width={size}
      height={size}
      viewBox="0 0 100 100"
      aria-label="Compass rose — pointer follows cursor"
      className={className}
      style={{ ...style, cursor: 'crosshair' }}
    >
      {/* Static: outer rings */}
      <circle cx="50" cy="50" r="47" fill="none" stroke={navy} strokeWidth="0.8" opacity="0.25" />
      <circle cx="50" cy="50" r="40" fill="none" stroke={navy} strokeWidth="0.4" opacity="0.15" />

      {/* Static: 8 minor intercardinal tick marks */}
      {[22.5, 67.5, 112.5, 157.5, 202.5, 247.5, 292.5, 337.5].map((deg) => {
        const rad = (deg * Math.PI) / 180
        const x1 = 50 + 40 * Math.sin(rad)
        const y1 = 50 - 40 * Math.cos(rad)
        const x2 = 50 + 46 * Math.sin(rad)
        const y2 = 50 - 46 * Math.cos(rad)
        return <line key={deg} x1={x1} y1={y1} x2={x2} y2={y2} stroke={navy} strokeWidth="0.6" opacity="0.3" />
      })}

      {/* Static: intercardinal diamond points (NE/SE/SW/NW) */}
      {[45, 135, 225, 315].map((deg) => {
        const rad = (deg * Math.PI) / 180
        const tip = { x: 50 + 30 * Math.sin(rad), y: 50 - 30 * Math.cos(rad) }
        const l90 = { x: 50 + 7 * Math.sin(rad - Math.PI / 2), y: 50 - 7 * Math.cos(rad - Math.PI / 2) }
        const r90 = { x: 50 + 7 * Math.sin(rad + Math.PI / 2), y: 50 - 7 * Math.cos(rad + Math.PI / 2) }
        const base = { x: 50 + 12 * Math.sin(rad + Math.PI), y: 50 - 12 * Math.cos(rad + Math.PI) }
        return (
          <g key={deg}>
            <polygon points={`${tip.x},${tip.y} ${l90.x},${l90.y} ${base.x},${base.y}`} fill={navy} opacity="0.5" />
            <polygon points={`${tip.x},${tip.y} ${r90.x},${r90.y} ${base.x},${base.y}`} fill={light} opacity="0.5" />
          </g>
        )
      })}

      {/* Rotating group — tracks cursor */}
      <g transform={`rotate(${angle} 50 50)`} style={{ transition: 'transform 80ms linear' }}>
        {/* Cardinal arms: N (red), S, E, W */}
        <polygon points="50,4 46,50 50,44 54,50" fill={red} />
        <polygon points="50,4 46,50 50,44" fill={red} />
        <polygon points="50,4 54,50 50,44" fill="oklch(56% 0.16 24)" />

        <polygon points="50,96 46,50 50,56" fill={navy} />
        <polygon points="50,96 54,50 50,56" fill={light} />

        <polygon points="4,50 50,46 44,50" fill={navy} />
        <polygon points="4,50 50,54 44,50" fill={light} />

        <polygon points="96,50 50,46 56,50" fill={navy} />
        <polygon points="96,50 50,54 56,50" fill={light} />

        {/* N label travels with the pointer */}
        <text
          x="50" y="2.5"
          textAnchor="middle"
          fontSize="8"
          fontFamily="Georgia, serif"
          fontWeight="700"
          fill={red}
          letterSpacing="0.5"
        >N</text>
      </g>

      {/* Static: centre hub over the rotating layer */}
      <circle cx="50" cy="50" r="5" fill={navy} stroke={light} strokeWidth="1" />
      <circle cx="50" cy="50" r="2" fill={red} />
    </svg>
  )
}
