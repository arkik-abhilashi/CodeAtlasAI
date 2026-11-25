export function Hero() {
  return (
    <section className="ca-hero" aria-labelledby="hero-title">
      <div className="ca-eyebrow">
        <span className="ca-status-dot" />
        AI-POWERED DEVELOPER INTELLIGENCE
      </div>

      <h1 className="ca-hero__title" id="hero-title">
        Understand Your Code.
        <br />
        <span className="ca-gradient-text">Build Smarter.</span>
      </h1>

      <p className="ca-hero__description">
        Explore your codebase, visualize software architecture, and uncover
        connections across your projects.
      </p>

      <div className="ca-actions">
        <a className="ca-button ca-button--primary" href="#repositories">
          Import a repository <span aria-hidden="true">↓</span>
        </a>

        <a className="ca-button ca-button--secondary" href="#features">
          Explore Features
        </a>
      </div>

      <div
        className="ca-preview"
        aria-label="Illustrative CodeAtlas architecture preview"
      >
        <div className="ca-preview__topbar">
          <div className="ca-window-dots" aria-hidden="true">
            <i />
            <i />
            <i />
          </div>

          <span className="ca-preview__crumb">
            codeatlas <span>/</span> project-overview
          </span>

          <span className="ca-preview__ready">
            <span className="ca-status-dot" />
            PREVIEW
          </span>
        </div>

        <div className="ca-preview__body">
          <aside className="ca-preview__files">
            <span className="ca-mini-label">PROJECT EXPLORER</span>
            <span className="ca-file ca-file--active">⌘ &nbsp; src</span>
            <span className="ca-file">↳ &nbsp; components</span>
            <span className="ca-file">↳ &nbsp; services</span>
            <span className="ca-file">↳ &nbsp; utils</span>
            <span className="ca-file">▧ &nbsp; package.json</span>
          </aside>

          <div className="ca-preview__map">
            <span className="ca-mini-label">ARCHITECTURE MAP</span>

            <div className="ca-graph">
              <svg
                className="ca-graph__lines"
                viewBox="0 0 600 250"
                preserveAspectRatio="none"
                aria-hidden="true"
              >
                <path d="M300 42 L150 108 L240 190 L360 190 L450 108 L300 42" />
                <path d="M150 108 L450 108 M300 42 L300 190" />
              </svg>

              <span className="ca-node ca-node--main">Application</span>
              <span className="ca-node ca-node--left">Components</span>
              <span className="ca-node ca-node--right">API Services</span>
              <span className="ca-node ca-node--bottom-left">UI Layer</span>
              <span className="ca-node ca-node--bottom-right">Data Layer</span>
            </div>
          </div>

          <aside className="ca-preview__insights">
            <span className="ca-mini-label">AI INSIGHTS</span>

            <div className="ca-insight">
              <span className="ca-insight__icon">✳</span>
              <div>
                <strong>Dependencies mapped</strong>
                <small>Relationships identified</small>
              </div>
            </div>

            <div className="ca-insight">
              <span className="ca-insight__icon">⌁</span>
              <div>
                <strong>Structure analyzed</strong>
                <small>Architecture overview</small>
              </div>
            </div>
          </aside>
        </div>
      </div>
    </section>
  );
}

const features = [
  {
    icon: "⌘",
    title: "Architecture at a glance",
    text: "Understand how the pieces of your application connect through a clear visual map.",
  },
  {
    icon: "✳",
    title: "Ask Atlas",
    text: "Ask questions about code, design decisions, and unfamiliar parts of a project.",
  },
  {
    icon: "⌕",
    title: "Find the connections",
    text: "Explore dependencies and follow relationships between components and services.",
  },
];

export function Features() {
  return (
    <section className="ca-section" id="features">
      <div className="ca-section__heading">
        <div>
          <p className="ca-kicker">BUILT FOR DEVELOPERS</p>
          <h2>
            Make sense of{" "}
            <span className="ca-gradient-text">complex code.</span>
          </h2>
        </div>

        <p>
          Less time hunting through files. More time understanding how your
          system works.
        </p>
      </div>

      <div className="ca-feature-grid">
        {features.map((feature) => (
          <article className="ca-feature-card" key={feature.title}>
            <span
              className="ca-feature-card__icon"
              aria-hidden="true"
            >
              {feature.icon}
            </span>

            <h3>{feature.title}</h3>
            <p>{feature.text}</p>

            <a href="#assistant">
              Explore <span aria-hidden="true">↗</span>
            </a>
          </article>
        ))}
      </div>
    </section>
  );
}

export function Footer() {
  return (
    <footer className="ca-footer" id="about">
      <a className="ca-wordmark" href="#home">
        CODEATLAS <span>AI</span>
      </a>

      <p>Understand your code. Build smarter.</p>

      <a href="#home">Back to top ↑</a>
    </footer>
  );
}
