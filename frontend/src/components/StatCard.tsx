interface StatCardProps {
  label: string
  value: string | number
}

export function StatCard({ label, value }: StatCardProps) {
  return (
    <article className="card">
      <div className="card-label">{label}</div>
      <strong>{value}</strong>
    </article>
  )
}
