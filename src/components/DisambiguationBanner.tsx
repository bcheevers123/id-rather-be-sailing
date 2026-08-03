interface Props {
  note?: string | null
}

export function DisambiguationBanner({ note }: Props) {
  if (!note) return null
  return (
    <div
      role="note"
      style={{
        background: 'var(--warn-tint)',
        border: '1px solid oklch(82% 0.10 72)',
        borderRadius: '8px',
        padding: '0.75rem 1rem',
        fontSize: '0.875rem',
        color: 'oklch(36% 0.12 60)',
        marginBottom: '1.25rem',
        display: 'flex',
        gap: '0.5rem',
        alignItems: 'flex-start',
      }}
    >
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor"
        strokeWidth="1.5" strokeLinecap="round" style={{ flexShrink: 0, marginTop: '1px' }} aria-hidden="true">
        <circle cx="8" cy="8" r="6.5"/>
        <line x1="8" y1="5" x2="8" y2="8.5"/>
        <circle cx="8" cy="11" r="0.5" fill="currentColor"/>
      </svg>
      <span><strong>Note: </strong>{note}</span>
    </div>
  )
}
