// Faint nautical silhouettes for background decoration — same ink style as SloopSilhouette.
// Rendered at low opacity as chart illustrations scattered across the page.

const ink  = 'var(--navy-950)'
const sail = 'var(--navy-100)'
const sea  = 'var(--paper-sea)'

// Classic tall ship / barque — two masts, square sails
function TallShip({ width = 220, height = 150 }: { width?: number; height?: number }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 220 150" width={width} height={height} aria-hidden="true">
      {/* Sea tint */}
      <path d="M0,115 Q55,111 110,115 Q165,119 220,115 L220,150 L0,150 Z" fill={sea} opacity="0.5" />
      <path d="M15,121 Q40,118 65,121 Q90,124 115,121" fill="none" stroke={ink} strokeWidth="0.6" opacity="0.15" />
      <path d="M105,123 Q130,120 155,123 Q180,126 205,123" fill="none" stroke={ink} strokeWidth="0.6" opacity="0.15" />

      {/* Hull */}
      <path d="M30,112 Q28,117 32,120 Q75,128 110,128 Q145,128 188,120 Q192,117 190,112 Z" fill={ink} />
      {/* Raised sides */}
      <line x1="30" y1="112" x2="190" y2="112" stroke={ink} strokeWidth="1.2" />
      {/* Bow sprit */}
      <line x1="185" y1="108" x2="210" y2="97" stroke={ink} strokeWidth="1.2" strokeLinecap="round" />
      {/* Cabin */}
      <path d="M60,112 Q62,106 80,104 Q100,102 120,104 Q138,106 140,112 Z" fill={ink} opacity="0.8" />

      {/* Foremast at x=80 */}
      <line x1="80" y1="112" x2="80" y2="18" stroke={ink} strokeWidth="1.8" strokeLinecap="round" />
      {/* Fore top yard */}
      <line x1="60" y1="35" x2="100" y2="35" stroke={ink} strokeWidth="1.2" strokeLinecap="round" />
      {/* Fore lower yard */}
      <line x1="55" y1="62" x2="105" y2="62" stroke={ink} strokeWidth="1.2" strokeLinecap="round" />
      {/* Fore topsail */}
      <path d="M60,35 L100,35 L105,62 L55,62 Z" fill={sail} stroke={ink} strokeWidth="0.6" opacity="0.85" />
      {/* Fore topgallant */}
      <path d="M65,20 L95,20 L100,35 L60,35 Z" fill={sail} stroke={ink} strokeWidth="0.6" opacity="0.75" />
      {/* Fore stays */}
      <line x1="80" y1="18" x2="185" y2="108" stroke={ink} strokeWidth="0.5" opacity="0.3" />
      <line x1="80" y1="18" x2="210" y2="97" stroke={ink} strokeWidth="0.5" opacity="0.25" />

      {/* Mainmast at x=115 */}
      <line x1="115" y1="112" x2="115" y2="12" stroke={ink} strokeWidth="2" strokeLinecap="round" />
      {/* Main top yard */}
      <line x1="90" y1="30" x2="140" y2="30" stroke={ink} strokeWidth="1.3" strokeLinecap="round" />
      {/* Main lower yard */}
      <line x1="82" y1="60" x2="148" y2="60" stroke={ink} strokeWidth="1.3" strokeLinecap="round" />
      {/* Main topsail */}
      <path d="M90,30 L140,30 L148,60 L82,60 Z" fill={sail} stroke={ink} strokeWidth="0.7" opacity="0.9" />
      {/* Main topgallant */}
      <path d="M96,14 L134,14 L140,30 L90,30 Z" fill={sail} stroke={ink} strokeWidth="0.7" opacity="0.8" />
      {/* Backstay */}
      <line x1="115" y1="12" x2="32" y2="108" stroke={ink} strokeWidth="0.5" opacity="0.3" />

      {/* Jib sails on bowsprit */}
      <path d="M80,55 L210,97 L80,100 Z" fill={sail} stroke={ink} strokeWidth="0.6" opacity="0.6" />
      <path d="M80,35 L210,97 L80,55 Z" fill={sail} stroke={ink} strokeWidth="0.5" opacity="0.5" />

      {/* Burgee */}
      <polygon points="115,12 115,6 124,9" fill="var(--chart-red)" opacity="0.8" />
    </svg>
  )
}

// A smaller ketch / yawl variant — slightly different from the main sloop
function Ketch({ width = 170, height = 120 }: { width?: number; height?: number }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 170 120" width={width} height={height} aria-hidden="true">
      {/* Sea */}
      <path d="M0,95 Q42,91 85,95 Q128,99 170,95 L170,120 L0,120 Z" fill={sea} opacity="0.45" />
      <path d="M8,101 Q28,98 48,101 Q68,104 88,101" fill="none" stroke={ink} strokeWidth="0.5" opacity="0.14" />

      {/* Hull */}
      <path d="M28,92 Q26,96 30,99 Q58,105 85,105 Q112,105 138,99 Q142,96 140,92 Z" fill={ink} />
      <line x1="28" y1="92" x2="140" y2="92" stroke={ink} strokeWidth="1.1" />
      {/* Cabin */}
      <path d="M58,92 Q60,87 75,85 Q90,83 105,85 Q118,87 120,92 Z" fill={ink} opacity="0.8" />
      {/* Keel */}
      <path d="M78,105 Q81,113 83,113 Q85,113 87,105" fill={ink} opacity="0.4" />

      {/* Mainmast x=80 */}
      <line x1="80" y1="92" x2="80" y2="14" stroke={ink} strokeWidth="1.7" strokeLinecap="round" />
      {/* Boom */}
      <line x1="80" y1="86" x2="130" y2="92" stroke={ink} strokeWidth="1.1" strokeLinecap="round" />
      {/* Backstay */}
      <line x1="80" y1="14" x2="136" y2="89" stroke={ink} strokeWidth="0.5" opacity="0.35" />
      {/* Forestay */}
      <line x1="80" y1="14" x2="140" y2="90" stroke={ink} strokeWidth="0.5" opacity="0.3" />
      {/* Mainsail */}
      <path d="M80,18 L80,86 L130,92 Z" fill={sail} stroke={ink} strokeWidth="0.7" opacity="0.88" />
      {/* Jib */}
      <path d="M80,28 L140,90 L80,76 Z" fill={sail} stroke={ink} strokeWidth="0.7" opacity="0.8" />

      {/* Mizzen mast x=118 */}
      <line x1="118" y1="92" x2="118" y2="52" stroke={ink} strokeWidth="1.3" strokeLinecap="round" />
      {/* Mizzen boom */}
      <line x1="118" y1="87" x2="140" y2="92" stroke={ink} strokeWidth="0.9" strokeLinecap="round" />
      {/* Mizzen sail */}
      <path d="M118,55 L118,87 L140,92 Z" fill={sail} stroke={ink} strokeWidth="0.6" opacity="0.75" />

      {/* Burgee */}
      <polygon points="80,14 80,8 89,11" fill="var(--chart-red)" opacity="0.75" />
    </svg>
  )
}

// Scatter these across the page background
export function ChartVesselsBackground() {
  return (
    <div aria-hidden="true" style={{
      position: 'fixed',
      inset: 0,
      pointerEvents: 'none',
      zIndex: 0,
      overflow: 'hidden',
    }}>
      {/* Tall ship — far left, mid-page */}
      <div style={{ position: 'absolute', left: '-2rem', top: '35%', opacity: 0.055, transform: 'rotate(-2deg)' }}>
        <TallShip width={260} height={177} />
      </div>

      {/* Ketch — far right, upper */}
      <div style={{ position: 'absolute', right: '-1.5rem', top: '18%', opacity: 0.06, transform: 'scaleX(-1) rotate(1deg)' }}>
        <Ketch width={200} height={141} />
      </div>

      {/* Small sloop echo — bottom left */}
      <div style={{ position: 'absolute', left: '2%', bottom: '8%', opacity: 0.045, transform: 'rotate(1deg)' }}>
        <Ketch width={140} height={99} />
      </div>

      {/* Tall ship — bottom right, faint */}
      <div style={{ position: 'absolute', right: '-3rem', bottom: '12%', opacity: 0.04, transform: 'scaleX(-1) rotate(-1deg)' }}>
        <TallShip width={200} height={136} />
      </div>
    </div>
  )
}
