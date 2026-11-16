type Props = { photo: string };

export function EngineerProfile({ photo }: Props) {
  return (
    <section className="engineer-section" id="engineer" aria-labelledby="engineer-name">
      <figure className="engineer-portrait">
        <img src={photo} alt="H M Ahsan Habib Kushal" loading="lazy" />
      </figure>
      <div className="engineer-copy">
        <span className="eyebrow">Meet the engineer</span>
        <h2 id="engineer-name">H M Ahsan Habib Kushal</h2>
        <p className="engineer-lead">AI/ML and Database Engineer · System Architect</p>
        <p>I built CTRx to bring identity verification, tenancy records, rent payments, and home maintenance into one workspace for tenants and landlords.</p>
        <div className="engineer-links">
          <a href="https://ahsanhabibkushal.vercel.app/" target="_blank" rel="noopener noreferrer">
            Explore my portfolio <span aria-hidden="true">↗</span>
          </a>
          <a href="https://github.com/AhsanCS64" target="_blank" rel="noopener noreferrer">
            GitHub <span aria-hidden="true">↗</span>
          </a>
        </div>
      </div>
    </section>
  );
}
