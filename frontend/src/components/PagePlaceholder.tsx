interface PagePlaceholderProps {
  summary: string
  willShow: string[]
  needs: string[]
}

// Stand-in for a section that isn't built yet. It says what the page
// will hold and what data it is waiting on, so the plan is visible in the app.
export function PagePlaceholder({ summary, willShow, needs }: PagePlaceholderProps) {
  return (
    <div className="placeholder-grid">
      <section className="card layout-area">
        <span className="layout-label">Layout area</span>
        <p>{summary}</p>
      </section>

      <section className="card">
        <div className="card-head">
          <h2>Will show</h2>
        </div>
        <ul className="list">
          {willShow.map((w) => (
            <li key={w}>{w}</li>
          ))}
        </ul>
      </section>

      <section className="card">
        <div className="card-head">
          <h2>Waiting on</h2>
        </div>
        <ul className="list">
          {needs.map((n) => (
            <li key={n}>{n}</li>
          ))}
        </ul>
      </section>
    </div>
  )
}
