// Faint nautical silhouettes for background decoration — same ink style as SloopSilhouette.
// Rendered at low opacity as chart illustrations scattered across the page.
import './ChartVessels.css'

const ink  = 'var(--navy-950)'
const sail = 'var(--navy-100)'
const sea  = 'var(--paper-sea)'

// Classic tall ship / barque — two masts, square sails
function TallShip({ width = 220, height = 150 }: { width?: number; height?: number }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 220 150" width={width} height={height} aria-hidden="true">
      <path d="M0,115 Q55,111 110,115 Q165,119 220,115 L220,150 L0,150 Z" fill={sea} opacity="0.5" />
      <path d="M15,121 Q40,118 65,121 Q90,124 115,121" fill="none" stroke={ink} strokeWidth="0.6" opacity="0.15" />
      <path d="M105,123 Q130,120 155,123 Q180,126 205,123" fill="none" stroke={ink} strokeWidth="0.6" opacity="0.15" />
      <path d="M30,112 Q28,117 32,120 Q75,128 110,128 Q145,128 188,120 Q192,117 190,112 Z" fill={ink} />
      <line x1="30" y1="112" x2="190" y2="112" stroke={ink} strokeWidth="1.2" />
      <line x1="185" y1="108" x2="210" y2="97" stroke={ink} strokeWidth="1.2" strokeLinecap="round" />
      <path d="M60,112 Q62,106 80,104 Q100,102 120,104 Q138,106 140,112 Z" fill={ink} opacity="0.8" />
      <line x1="80" y1="112" x2="80" y2="18" stroke={ink} strokeWidth="1.8" strokeLinecap="round" />
      <line x1="60" y1="35" x2="100" y2="35" stroke={ink} strokeWidth="1.2" strokeLinecap="round" />
      <line x1="55" y1="62" x2="105" y2="62" stroke={ink} strokeWidth="1.2" strokeLinecap="round" />
      <path d="M60,35 L100,35 L105,62 L55,62 Z" fill={sail} stroke={ink} strokeWidth="0.6" opacity="0.85" />
      <path d="M65,20 L95,20 L100,35 L60,35 Z" fill={sail} stroke={ink} strokeWidth="0.6" opacity="0.75" />
      <line x1="80" y1="18" x2="185" y2="108" stroke={ink} strokeWidth="0.5" opacity="0.3" />
      <line x1="80" y1="18" x2="210" y2="97" stroke={ink} strokeWidth="0.5" opacity="0.25" />
      <line x1="115" y1="112" x2="115" y2="12" stroke={ink} strokeWidth="2" strokeLinecap="round" />
      <line x1="90" y1="30" x2="140" y2="30" stroke={ink} strokeWidth="1.3" strokeLinecap="round" />
      <line x1="82" y1="60" x2="148" y2="60" stroke={ink} strokeWidth="1.3" strokeLinecap="round" />
      <path d="M90,30 L140,30 L148,60 L82,60 Z" fill={sail} stroke={ink} strokeWidth="0.7" opacity="0.9" />
      <path d="M96,14 L134,14 L140,30 L90,30 Z" fill={sail} stroke={ink} strokeWidth="0.7" opacity="0.8" />
      <line x1="115" y1="12" x2="32" y2="108" stroke={ink} strokeWidth="0.5" opacity="0.3" />
      <path d="M80,55 L210,97 L80,100 Z" fill={sail} stroke={ink} strokeWidth="0.6" opacity="0.6" />
      <path d="M80,35 L210,97 L80,55 Z" fill={sail} stroke={ink} strokeWidth="0.5" opacity="0.5" />
      <polygon points="115,12 115,6 124,9" fill="var(--chart-red)" opacity="0.8" />
    </svg>
  )
}

// Ketch / yawl — two masts, fore-and-aft rig
function Ketch({ width = 170, height = 120 }: { width?: number; height?: number }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 170 120" width={width} height={height} aria-hidden="true">
      <path d="M0,95 Q42,91 85,95 Q128,99 170,95 L170,120 L0,120 Z" fill={sea} opacity="0.45" />
      <path d="M8,101 Q28,98 48,101 Q68,104 88,101" fill="none" stroke={ink} strokeWidth="0.5" opacity="0.14" />
      <path d="M28,92 Q26,96 30,99 Q58,105 85,105 Q112,105 138,99 Q142,96 140,92 Z" fill={ink} />
      <line x1="28" y1="92" x2="140" y2="92" stroke={ink} strokeWidth="1.1" />
      <path d="M58,92 Q60,87 75,85 Q90,83 105,85 Q118,87 120,92 Z" fill={ink} opacity="0.8" />
      <path d="M78,105 Q81,113 83,113 Q85,113 87,105" fill={ink} opacity="0.4" />
      <line x1="80" y1="92" x2="80" y2="14" stroke={ink} strokeWidth="1.7" strokeLinecap="round" />
      <line x1="80" y1="86" x2="130" y2="92" stroke={ink} strokeWidth="1.1" strokeLinecap="round" />
      <line x1="80" y1="14" x2="136" y2="89" stroke={ink} strokeWidth="0.5" opacity="0.35" />
      <line x1="80" y1="14" x2="140" y2="90" stroke={ink} strokeWidth="0.5" opacity="0.3" />
      <path d="M80,18 L80,86 L130,92 Z" fill={sail} stroke={ink} strokeWidth="0.7" opacity="0.88" />
      <path d="M80,28 L140,90 L80,76 Z" fill={sail} stroke={ink} strokeWidth="0.7" opacity="0.8" />
      <line x1="118" y1="92" x2="118" y2="52" stroke={ink} strokeWidth="1.3" strokeLinecap="round" />
      <line x1="118" y1="87" x2="140" y2="92" stroke={ink} strokeWidth="0.9" strokeLinecap="round" />
      <path d="M118,55 L118,87 L140,92 Z" fill={sail} stroke={ink} strokeWidth="0.6" opacity="0.75" />
      <polygon points="80,14 80,8 89,11" fill="var(--chart-red)" opacity="0.75" />
    </svg>
  )
}

// Simple sloop — single mast, mainsail + jib
function Sloop({ width = 130, height = 100 }: { width?: number; height?: number }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 130 100" width={width} height={height} aria-hidden="true">
      <path d="M0,78 Q32,74 65,78 Q98,82 130,78 L130,100 L0,100 Z" fill={sea} opacity="0.4" />
      <path d="M22,76 Q24,79 28,81 Q50,87 65,87 Q80,87 100,81 Q104,79 106,76 Z" fill={ink} />
      <line x1="22" y1="76" x2="106" y2="76" stroke={ink} strokeWidth="1" />
      <line x1="100" y1="72" x2="118" y2="63" stroke={ink} strokeWidth="1" strokeLinecap="round" />
      <path d="M48,76 Q50,72 60,70 Q70,68 80,70 Q90,72 92,76 Z" fill={ink} opacity="0.75" />
      <line x1="60" y1="76" x2="60" y2="10" stroke={ink} strokeWidth="1.5" strokeLinecap="round" />
      <line x1="60" y1="70" x2="100" y2="76" stroke={ink} strokeWidth="0.9" strokeLinecap="round" />
      <line x1="60" y1="10" x2="104" y2="73" stroke={ink} strokeWidth="0.4" opacity="0.3" />
      <path d="M60,14 L60,70 L100,76 Z" fill={sail} stroke={ink} strokeWidth="0.6" opacity="0.85" />
      <path d="M60,22 L118,63 L60,58 Z" fill={sail} stroke={ink} strokeWidth="0.6" opacity="0.75" />
      <polygon points="60,10 60,5 68,7.5" fill="var(--chart-red)" opacity="0.7" />
    </svg>
  )
}

// Schooner — two masts, fore-and-aft, foremast shorter than mainmast
function Schooner({ width = 190, height = 130 }: { width?: number; height?: number }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 190 130" width={width} height={height} aria-hidden="true">
      <path d="M0,103 Q47,99 95,103 Q143,107 190,103 L190,130 L0,130 Z" fill={sea} opacity="0.45" />
      <path d="M10,109 Q35,106 60,109 Q85,112 110,109" fill="none" stroke={ink} strokeWidth="0.5" opacity="0.12" />
      <path d="M25,100 Q23,104 27,107 Q65,115 95,115 Q125,115 161,107 Q165,104 163,100 Z" fill={ink} />
      <line x1="25" y1="100" x2="163" y2="100" stroke={ink} strokeWidth="1.1" />
      <line x1="158" y1="96" x2="178" y2="87" stroke={ink} strokeWidth="1.1" strokeLinecap="round" />
      <path d="M55,100 Q57,95 72,93 Q88,91 104,93 Q118,95 120,100 Z" fill={ink} opacity="0.8" />
      {/* Foremast x=72 — shorter */}
      <line x1="72" y1="100" x2="72" y2="28" stroke={ink} strokeWidth="1.5" strokeLinecap="round" />
      <line x1="72" y1="93" x2="110" y2="100" stroke={ink} strokeWidth="1" strokeLinecap="round" />
      <line x1="72" y1="28" x2="160" y2="96" stroke={ink} strokeWidth="0.4" opacity="0.3" />
      <path d="M72,32 L72,93 L110,100 Z" fill={sail} stroke={ink} strokeWidth="0.6" opacity="0.82" />
      {/* Mainmast x=110 — taller */}
      <line x1="110" y1="100" x2="110" y2="14" stroke={ink} strokeWidth="1.8" strokeLinecap="round" />
      <line x1="110" y1="94" x2="158" y2="100" stroke={ink} strokeWidth="1.1" strokeLinecap="round" />
      <line x1="110" y1="14" x2="26" y2="96" stroke={ink} strokeWidth="0.4" opacity="0.3" />
      <path d="M110,18 L110,94 L158,100 Z" fill={sail} stroke={ink} strokeWidth="0.7" opacity="0.88" />
      {/* Jib */}
      <path d="M72,38 L178,87 L72,72 Z" fill={sail} stroke={ink} strokeWidth="0.6" opacity="0.7" />
      <polygon points="110,14 110,8 119,11" fill="var(--chart-red)" opacity="0.75" />
    </svg>
  )
}

// Motor vessel / coastal freighter — no sails, low superstructure
function MotorVessel({ width = 160, height = 80 }: { width?: number; height?: number }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 160 80" width={width} height={height} aria-hidden="true">
      <path d="M0,58 Q40,54 80,58 Q120,62 160,58 L160,80 L0,80 Z" fill={sea} opacity="0.4" />
      <path d="M15,56 Q15,60 20,63 Q55,70 80,70 Q105,70 138,63 Q143,60 143,56 Z" fill={ink} />
      <line x1="15" y1="56" x2="143" y2="56" stroke={ink} strokeWidth="1" />
      <line x1="138" y1="52" x2="152" y2="48" stroke={ink} strokeWidth="1" strokeLinecap="round" />
      {/* Superstructure */}
      <path d="M50,56 L50,42 L100,42 L100,56 Z" fill={ink} opacity="0.85" />
      <path d="M58,42 L58,34 L88,34 L88,42 Z" fill={ink} opacity="0.9" />
      {/* Bridge windows */}
      <line x1="64" y1="37" x2="64" y2="40" stroke="var(--paper)" strokeWidth="0.8" opacity="0.4" />
      <line x1="71" y1="37" x2="71" y2="40" stroke="var(--paper)" strokeWidth="0.8" opacity="0.4" />
      <line x1="78" y1="37" x2="78" y2="40" stroke="var(--paper)" strokeWidth="0.8" opacity="0.4" />
      {/* Mast */}
      <line x1="73" y1="34" x2="73" y2="16" stroke={ink} strokeWidth="1.2" strokeLinecap="round" />
      <line x1="65" y1="20" x2="81" y2="20" stroke={ink} strokeWidth="0.8" strokeLinecap="round" />
      {/* Cargo hatch */}
      <path d="M22,56 L22,50 L45,50 L45,56 Z" fill={ink} opacity="0.6" />
      <path d="M108,56 L108,50 L132,50 L132,56 Z" fill={ink} opacity="0.6" />
    </svg>
  )
}

// Scatter these across the page background — 8–9 vessels
export function ChartVesselsBackground() {
  return (
    <div aria-hidden="true" style={{
      position: 'fixed',
      inset: 0,
      pointerEvents: 'none',
      zIndex: 0,
      overflow: 'hidden',
    }}>
      {/* 1 — Tall ship far left, upper-mid */}
      <div className="vessel-1" style={{ position: 'absolute', left: '-3rem', top: '28%', opacity: 0.055, transform: 'rotate(-2deg)' }}>
        <TallShip width={270} height={184} />
      </div>

      {/* 2 — Ketch far right, upper */}
      <div className="vessel-2" style={{ position: 'absolute', right: '-1.5rem', top: '15%', opacity: 0.06, transform: 'scaleX(-1) rotate(1deg)' }}>
        <Ketch width={200} height={141} />
      </div>

      {/* 3 — Schooner centre-left, behind hero */}
      <div className="vessel-3" style={{ position: 'absolute', left: '18%', top: '8%', opacity: 0.04, transform: 'rotate(-1deg)' }}>
        <Schooner width={200} height={137} />
      </div>

      {/* 4 — Small sloop bottom-left */}
      <div className="vessel-4" style={{ position: 'absolute', left: '2%', bottom: '10%', opacity: 0.05, transform: 'rotate(1.5deg)' }}>
        <Sloop width={130} height={100} />
      </div>

      {/* 5 — Tall ship bottom-right */}
      <div className="vessel-5" style={{ position: 'absolute', right: '-3rem', bottom: '14%', opacity: 0.045, transform: 'scaleX(-1) rotate(-1.5deg)' }}>
        <TallShip width={210} height={143} />
      </div>

      {/* 6 — Motor vessel centre-right, low */}
      <div className="vessel-6" style={{ position: 'absolute', right: '12%', bottom: '5%', opacity: 0.04, transform: 'rotate(0.5deg)' }}>
        <MotorVessel width={170} height={85} />
      </div>

      {/* 7 — Small ketch top-right corner */}
      <div className="vessel-7" style={{ position: 'absolute', right: '3%', top: '52%', opacity: 0.038, transform: 'scaleX(-1) rotate(-1deg)' }}>
        <Ketch width={130} height={92} />
      </div>

      {/* 8 — Schooner bottom-centre */}
      <div className="vessel-8" style={{ position: 'absolute', left: '38%', bottom: '3%', opacity: 0.038, transform: 'scaleX(-1) rotate(1deg)' }}>
        <Schooner width={160} height={110} />
      </div>

      {/* 9 — Tiny sloop top-left, very faint */}
      <div className="vessel-9" style={{ position: 'absolute', left: '28%', top: '3%', opacity: 0.032, transform: 'rotate(-0.5deg)' }}>
        <Sloop width={100} height={77} />
      </div>
    </div>
  )
}
