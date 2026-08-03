interface Props {
  note: string
}

export function DisambiguationBanner({ note }: Props) {
  return (
    <div
      role="note"
      className="mb-4 rounded border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900"
    >
      <span className="font-semibold">Similar courses exist: </span>
      {note}
    </div>
  )
}
