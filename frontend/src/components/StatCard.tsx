interface StatCardProps {
  label: string
  value: string | number
}

export function StatCard({ label, value }: StatCardProps) {
  return (
    <article className="card">
      <label>{label}</label>
      <strong>{value}</strong>
    </article>
  )
}
