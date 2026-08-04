export function StatusBadge({ children, tone = "blue" }: { children: React.ReactNode; tone?: "blue" | "green" | "amber" | "slate" }) {
  return <span className={`status-badge ${tone}`}><i />{children}</span>;
}
