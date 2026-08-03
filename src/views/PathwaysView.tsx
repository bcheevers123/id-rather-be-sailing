import { useState, useEffect, useRef, useCallback } from 'react'
import { Link } from 'react-router-dom'
import confetti from 'canvas-confetti'

// ── Pathway data ──────────────────────────────────────────────────────────────
// Course IDs match the MCA course IDs in the data pipeline.
// Each pathway lists the courses required for a deck/engineering/safety role.

interface PathwayCourse {
  id: string           // matches course id in data
  label: string        // friendly name
  note?: string        // e.g. "or equivalent"
}

interface Pathway {
  id: string
  role: string
  description: string
  source: string
  sourceUrl: string
  courses: PathwayCourse[]
}

const PATHWAYS: Pathway[] = [
  {
    id: 'bosun',
    role: 'Bosun',
    description: 'Responsible for deck operations and crew safety on commercial vessels.',
    source: 'MCA MIN 668 — Ratings forming part of a navigational watch',
    sourceUrl: 'https://www.gov.uk/government/publications/min-668-stcw-ratings',
    courses: [
      { id: 'pst',   label: 'Personal Survival Techniques (PST)' },
      { id: 'fpff',  label: 'Fire Prevention & Fire Fighting (FPFF)' },
      { id: 'efa',   label: 'Elementary First Aid (EFA)' },
      { id: 'pssr',  label: 'Personal Safety & Social Responsibilities (PSSR)' },
      { id: 'helm_o', label: 'HELM (Operational)', note: 'Management of Operations' },
    ],
  },
  {
    id: 'ab',
    role: 'Able Seafarer (Deck)',
    description: 'Watch-keeping rating on deck with full STCW Basic Safety certification.',
    source: 'MCA MGN 671 — Able Seafarer Deck certification',
    sourceUrl: 'https://www.gov.uk/government/publications/mgn-671-able-seafarer-deck',
    courses: [
      { id: 'pst',   label: 'Personal Survival Techniques (PST)' },
      { id: 'fpff',  label: 'Fire Prevention & Fire Fighting (FPFF)' },
      { id: 'efa',   label: 'Elementary First Aid (EFA)' },
      { id: 'pssr',  label: 'Personal Safety & Social Responsibilities (PSSR)' },
      { id: 'pst_vt', label: 'PST Vessel Type Specific', note: 'If applicable' },
    ],
  },
  {
    id: 'officer_of_watch',
    role: 'Officer of the Watch (OOW)',
    description: 'Deck officer responsible for safe navigation during a watch.',
    source: 'STCW Convention Table A-II/1 — OOW near-coastal & unlimited',
    sourceUrl: 'https://www.gov.uk/guidance/mca-approved-training-providers-atp',
    courses: [
      { id: 'pst',        label: 'Personal Survival Techniques (PST)' },
      { id: 'fpff',       label: 'Fire Prevention & Fire Fighting (FPFF)' },
      { id: 'efa',        label: 'Elementary First Aid (EFA)' },
      { id: 'pssr',       label: 'Personal Safety & Social Responsibilities (PSSR)' },
      { id: 'advanced_ff', label: 'Advanced Fire Fighting' },
      { id: 'proficiency_survival', label: 'Proficiency in Survival Craft' },
      { id: 'medical_care', label: 'Medical Care (ship captain/officer)' },
      { id: 'helm_o',     label: 'HELM (Operational)' },
      { id: 'ecdis_generic', label: 'ECDIS Generic' },
    ],
  },
  {
    id: 'chief_officer',
    role: 'Chief Officer',
    description: 'First mate; responsible for cargo, stability, and crew management.',
    source: 'STCW Convention Table A-II/2 — Chief Mate',
    sourceUrl: 'https://www.gov.uk/guidance/mca-approved-training-providers-atp',
    courses: [
      { id: 'pst',        label: 'Personal Survival Techniques (PST)' },
      { id: 'fpff',       label: 'Fire Prevention & Fire Fighting (FPFF)' },
      { id: 'efa',        label: 'Elementary First Aid (EFA)' },
      { id: 'pssr',       label: 'Personal Safety & Social Responsibilities (PSSR)' },
      { id: 'advanced_ff', label: 'Advanced Fire Fighting' },
      { id: 'proficiency_survival', label: 'Proficiency in Survival Craft' },
      { id: 'medical_care', label: 'Medical Care' },
      { id: 'helm_o',     label: 'HELM (Operational)' },
      { id: 'helm_m',     label: 'HELM (Management)' },
      { id: 'ecdis_generic', label: 'ECDIS Generic' },
    ],
  },
  {
    id: 'master',
    role: 'Master Mariner',
    description: 'Qualified to command any ship on any voyage worldwide.',
    source: 'STCW Convention Table A-II/2 — Master on ships of 3,000 GT or more',
    sourceUrl: 'https://www.gov.uk/guidance/mca-approved-training-providers-atp',
    courses: [
      { id: 'pst',        label: 'Personal Survival Techniques (PST)' },
      { id: 'fpff',       label: 'Fire Prevention & Fire Fighting (FPFF)' },
      { id: 'efa',        label: 'Elementary First Aid (EFA)' },
      { id: 'pssr',       label: 'Personal Safety & Social Responsibilities (PSSR)' },
      { id: 'advanced_ff', label: 'Advanced Fire Fighting' },
      { id: 'proficiency_survival', label: 'Proficiency in Survival Craft' },
      { id: 'lifeboat',   label: 'Fast Rescue Boat' },
      { id: 'medical_care', label: 'Medical Care on Board' },
      { id: 'helm_o',     label: 'HELM (Operational)' },
      { id: 'helm_m',     label: 'HELM (Management)' },
      { id: 'ecdis_generic', label: 'ECDIS Generic' },
      { id: 'ecdis_type', label: 'ECDIS Type Specific', note: 'Equipment-specific' },
    ],
  },
  {
    id: 'engineer_watchkeeper',
    role: 'Engineer Officer of the Watch',
    description: 'Engineering officer responsible for propulsion and machinery during a watch.',
    source: 'STCW Convention Table A-III/1 — Engineer Officer of the Watch',
    sourceUrl: 'https://www.gov.uk/guidance/mca-approved-training-providers-atp',
    courses: [
      { id: 'pst',        label: 'Personal Survival Techniques (PST)' },
      { id: 'fpff',       label: 'Fire Prevention & Fire Fighting (FPFF)' },
      { id: 'efa',        label: 'Elementary First Aid (EFA)' },
      { id: 'pssr',       label: 'Personal Safety & Social Responsibilities (PSSR)' },
      { id: 'advanced_ff', label: 'Advanced Fire Fighting' },
      { id: 'proficiency_survival', label: 'Proficiency in Survival Craft' },
      { id: 'helm_o',     label: 'HELM (Operational)' },
    ],
  },
  {
    id: 'security_officer',
    role: 'Ship Security Officer (SSO)',
    description: 'Responsible for implementing and maintaining the ship\'s security plan.',
    source: 'STCW Convention Section A-VI/5 — Ship Security Officer',
    sourceUrl: 'https://www.gov.uk/guidance/mca-approved-training-providers-atp',
    courses: [
      { id: 'pst',   label: 'Personal Survival Techniques (PST)' },
      { id: 'fpff',  label: 'Fire Prevention & Fire Fighting (FPFF)' },
      { id: 'efa',   label: 'Elementary First Aid (EFA)' },
      { id: 'pssr',  label: 'Personal Safety & Social Responsibilities (PSSR)' },
      { id: 'sso',   label: 'Ship Security Officer' },
    ],
  },
  {
    id: 'gmdss',
    role: 'GMDSS Radio Operator',
    description: 'Certified to operate Global Maritime Distress and Safety System radio equipment.',
    source: 'STCW Convention Table A-IV/2 — GMDSS Radio Operator',
    sourceUrl: 'https://www.gov.uk/guidance/mca-approved-training-providers-atp',
    courses: [
      { id: 'pst',   label: 'Personal Survival Techniques (PST)' },
      { id: 'efa',   label: 'Elementary First Aid (EFA)' },
      { id: 'gmdss_got', label: 'GMDSS General Operator Certificate (GOC)' },
    ],
  },
]

// ── Confetti fireworks ────────────────────────────────────────────────────────
function launchFireworks() {
  const duration = 10_000
  const end = Date.now() + duration

  const colors = ['#c0001f', '#0a1628', '#d4af37', '#ffffff', '#4a90d9']

  // Burst from multiple origins
  const burst = (origin: { x: number; y: number }, particleCount: number) => {
    confetti({
      particleCount,
      spread: 120,
      startVelocity: 45,
      origin,
      colors,
      ticks: 300,
      gravity: 0.8,
      scalar: 1.2,
      shapes: ['square', 'circle'],
    })
  }

  // Continuous side cannons
  const frame = () => {
    if (Date.now() > end) return
    confetti({ particleCount: 4, angle: 60,  spread: 55, origin: { x: 0,    y: 0.7 }, colors })
    confetti({ particleCount: 4, angle: 120, spread: 55, origin: { x: 1,    y: 0.7 }, colors })
    requestAnimationFrame(frame)
  }

  // Opening salvos
  burst({ x: 0.5, y: 0.4 }, 120)
  setTimeout(() => burst({ x: 0.25, y: 0.5 }, 80), 400)
  setTimeout(() => burst({ x: 0.75, y: 0.5 }, 80), 700)
  setTimeout(() => burst({ x: 0.5,  y: 0.3 }, 100), 1200)
  setTimeout(() => burst({ x: 0.15, y: 0.4 }, 60), 1800)
  setTimeout(() => burst({ x: 0.85, y: 0.4 }, 60), 2100)
  setTimeout(() => burst({ x: 0.5,  y: 0.35 }, 150), 3000)

  frame()
}

// ── Component ─────────────────────────────────────────────────────────────────
export function PathwaysView() {
  const [selectedId, setSelectedId] = useState<string>(PATHWAYS[0].id)
  const [ticked, setTicked] = useState<Set<string>>(new Set())
  const [celebrating, setCelebrating] = useState(false)
  const celebratedRef = useRef(false)

  const pathway = PATHWAYS.find(p => p.id === selectedId)!
  const total = pathway.courses.length
  const done  = pathway.courses.filter(c => ticked.has(c.id)).length
  const allDone = done === total

  // Reset ticks + celebration flag when pathway changes
  useEffect(() => {
    setTicked(new Set())
    setCelebrating(false)
    celebratedRef.current = false
  }, [selectedId])

  // Fire confetti exactly once when all boxes ticked
  useEffect(() => {
    if (allDone && !celebratedRef.current) {
      celebratedRef.current = true
      setCelebrating(true)
      launchFireworks()
      setTimeout(() => setCelebrating(false), 10_500)
    }
  }, [allDone])

  const toggle = useCallback((id: string) => {
    setTicked(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }, [])

  return (
    <div className="mx-auto max-w-4xl px-4 py-8">
      {/* Header */}
      <div style={{
        borderTop: '3px solid var(--chart-red)',
        background: 'var(--surface)',
        border: '1px solid var(--border)',
        borderTopColor: 'var(--chart-red)',
        borderTopWidth: '3px',
        padding: '1rem 1.25rem',
        marginBottom: '1.5rem',
      }}>
        <div style={{
          fontFamily: 'var(--font-data)',
          fontSize: '0.6rem',
          fontWeight: 700,
          letterSpacing: '0.14em',
          textTransform: 'uppercase',
          color: 'var(--chart-red)',
          marginBottom: '0.25rem',
        }}>
          Career Pathways
        </div>
        <h1 style={{ fontSize: '1.4rem', marginBottom: '0.25rem', lineHeight: 1.2 }}>
          What courses do I need?
        </h1>
        <p style={{ fontSize: '0.8125rem', color: 'var(--ink-muted)', margin: 0, lineHeight: 1.6 }}>
          Select a maritime role to see the required MCA-approved training. Tick off courses as you complete them.
        </p>
      </div>

      <div className="flex gap-6 flex-col md:flex-row">
        {/* Role selector — pilot book index */}
        <aside style={{ flexShrink: 0 }} className="md:w-52">
          <p style={{
            fontFamily: 'var(--font-data)',
            fontSize: '0.6rem',
            fontWeight: 700,
            letterSpacing: '0.12em',
            textTransform: 'uppercase',
            color: 'var(--ink-faint)',
            marginBottom: '0.5rem',
          }}>
            Select role
          </p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
            {PATHWAYS.map(p => (
              <button
                key={p.id}
                onClick={() => setSelectedId(p.id)}
                style={{
                  textAlign: 'left',
                  padding: '0.5rem 0.75rem',
                  background: selectedId === p.id ? 'var(--navy-950)' : 'var(--surface)',
                  color: selectedId === p.id ? '#fff' : 'var(--ink)',
                  border: '1px solid var(--border)',
                  borderColor: selectedId === p.id ? 'var(--navy-950)' : 'var(--border)',
                  fontFamily: 'var(--font-ui)',
                  fontSize: '0.875rem',
                  fontWeight: selectedId === p.id ? 700 : 400,
                  cursor: 'pointer',
                  transition: 'background 100ms, color 100ms',
                  borderRadius: 0,
                }}
                className="hover:bg-[var(--paper-sea)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--chart-red)]"
              >
                {p.role}
              </button>
            ))}
          </div>
        </aside>

        {/* Course checklist */}
        <section style={{ flex: 1, minWidth: 0 }}>
          {/* Role title + progress */}
          <div style={{
            background: 'var(--surface)',
            border: '1px solid var(--border)',
            padding: '0.875rem 1rem',
            marginBottom: '0.5rem',
          }}>
            <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '1rem', flexWrap: 'wrap' }}>
              <div>
                <h2 style={{ fontSize: '1.1rem', marginBottom: '0.2rem' }}>{pathway.role}</h2>
                <p style={{ fontSize: '0.8125rem', color: 'var(--ink-muted)', margin: '0 0 0.3rem' }}>{pathway.description}</p>
                <p style={{ fontSize: '0.68rem', color: 'var(--ink-faint)', margin: 0, fontFamily: 'var(--font-data)' }}>
                  Pathway requirements source:{' '}
                  <a
                    href={pathway.sourceUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    style={{ color: 'var(--soundings)' }}
                  >
                    {pathway.source}
                  </a>
                </p>
              </div>
              {/* Progress pill */}
              <div style={{
                fontFamily: 'var(--font-data)',
                fontSize: '0.75rem',
                fontWeight: 700,
                color: allDone ? 'var(--verified)' : 'var(--ink-muted)',
                background: allDone ? 'var(--verified-bg)' : 'var(--paper-sea)',
                border: `1px solid ${allDone ? 'oklch(70% 0.08 158)' : 'var(--border)'}`,
                padding: '0.2rem 0.6rem',
                whiteSpace: 'nowrap',
                flexShrink: 0,
                alignSelf: 'flex-start',
                transition: 'all 200ms',
              }}>
                {done}/{total} complete
              </div>
            </div>

            {/* Progress bar */}
            <div style={{
              height: '4px',
              background: 'var(--border)',
              marginTop: '0.75rem',
              overflow: 'hidden',
            }}>
              <div style={{
                height: '100%',
                width: '100%',
                background: allDone ? 'var(--verified)' : 'var(--chart-red)',
                transform: `scaleX(${total ? done / total : 0})`,
                transformOrigin: 'left center',
                transition: 'transform 300ms ease-out, background 300ms',
              }} />
            </div>
          </div>

          {/* Course rows */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
            {pathway.courses.map(course => {
              const checked = ticked.has(course.id)
              return (
                <label
                  key={course.id}
                  style={{
                    display: 'flex',
                    alignItems: 'flex-start',
                    gap: '0.75rem',
                    padding: '0.75rem 1rem',
                    background: checked ? 'var(--verified-bg)' : 'var(--surface)',
                    border: `1px solid ${checked ? 'oklch(80% 0.06 158)' : 'var(--border)'}`,
                    cursor: 'pointer',
                    transition: 'background 150ms, border-color 150ms',
                  }}
                  className="hover:bg-[var(--paper-sea)]"
                >
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => toggle(course.id)}
                    style={{
                      marginTop: '2px',
                      accentColor: 'var(--chart-red)',
                      width: '16px',
                      height: '16px',
                      flexShrink: 0,
                      cursor: 'pointer',
                    }}
                  />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <span style={{
                      fontFamily: 'var(--font-ui)',
                      fontSize: '0.9375rem',
                      color: checked ? 'var(--verified)' : 'var(--ink)',
                      textDecoration: checked ? 'line-through' : 'none',
                      textDecorationColor: 'var(--verified)',
                      transition: 'color 150ms',
                    }}>
                      {course.label}
                    </span>
                    {course.note && (
                      <span style={{
                        display: 'block',
                        fontFamily: 'var(--font-data)',
                        fontSize: '0.72rem',
                        color: 'var(--ink-faint)',
                        marginTop: '0.1rem',
                      }}>
                        {course.note}
                      </span>
                    )}
                  </div>
                  {/* Link to find providers */}
                  <Link
                    to={`/course/${course.id}`}
                    onClick={e => e.stopPropagation()}
                    className="btn-chart"
                    style={{ flexShrink: 0, alignSelf: 'center', fontSize: '0.68rem' }}
                    tabIndex={-1}
                  >
                    Find dates →
                  </Link>
                </label>
              )
            })}
          </div>

          {/* Completion banner */}
          {allDone && (
            <div style={{
              marginTop: '1rem',
              padding: '1.25rem',
              background: 'var(--verified-bg)',
              border: '2px solid var(--verified)',
              textAlign: 'center',
              animation: 'chart-scan 1s ease-in-out',
            }}>
              <div style={{
                fontFamily: 'var(--font-ui)',
                fontSize: '1.25rem',
                fontWeight: 700,
                color: 'var(--verified)',
                marginBottom: '0.25rem',
              }}>
                All courses complete — well done, {pathway.role}!
              </div>
              <p style={{ fontSize: '0.8125rem', color: 'var(--ink-muted)', margin: 0 }}>
                You have the training required for this role. Fair winds! ⚓
              </p>
              {celebrating && (
                <p style={{
                  fontFamily: 'var(--font-data)',
                  fontSize: '0.7rem',
                  color: 'var(--ink-faint)',
                  marginTop: '0.5rem',
                  letterSpacing: '0.08em',
                  textTransform: 'uppercase',
                }}>
                  🎉 Stand by for fireworks…
                </p>
              )}
            </div>
          )}
        </section>
      </div>
    </div>
  )
}
