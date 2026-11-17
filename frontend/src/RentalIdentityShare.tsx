import { useEffect, useState } from 'react';

type Verification = {
  applicant_name: string;
  ric_number: string;
  issued_at: string;
  status: string;
  recorded_payment_periods: number;
  reliability_score: number | null;
};

export function VerifiedRentalIdentity({ apiBaseUrl, token }: { apiBaseUrl: string; token: string }) {
  const [record, setRecord] = useState<Verification | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    fetch(`${apiBaseUrl}/api/public/rental-identity/verify`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token }),
      signal: controller.signal,
      cache: 'no-store',
    }).then(async response => {
      if (!response.ok) throw new Error('Verification unavailable');
      setRecord(await response.json() as Verification);
    }).catch(() => { if (!controller.signal.aborted) setFailed(true); });
    return () => controller.abort();
  }, [apiBaseUrl, token]);

  return <main className="content verification-content">
    <section className="panel">
      <h1>Rental identity verification</h1>
      {failed ? <p role="alert">This link could not be verified. Ask the tenant for a fresh link.</p>
        : !record ? <p role="status">Verifying rental identity…</p>
        : <dl className="verification-facts">
          <dt>Certificate holder</dt><dd>{record.applicant_name}</dd>
          <dt>Rental Identity Certificate</dt><dd>{record.ric_number} · Active</dd>
          <dt>Issued</dt><dd>{new Date(record.issued_at).toLocaleDateString()}</dd>
          <dt>Months with recorded rent payments</dt><dd>{record.recorded_payment_periods}</dd>
          <dt>Rental reliability score</dt><dd>{record.reliability_score === null ? 'No score available' : `${record.reliability_score} / 100`}</dd>
        </dl>}
      <a href={window.location.pathname}>Go to CTRx</a>
    </section>
  </main>;
}

export function ShareRentalIdentity({ createToken }: { createToken: () => Promise<string> }) {
  const [link, setLink] = useState('');
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');

  async function copy(value: string) {
    try {
      await navigator.clipboard.writeText(value);
      setMessage('Verification link copied. It expires in 24 hours.');
    } catch {
      setMessage('Copy the verification link from the field below.');
    }
  }

  async function share() {
    setBusy(true);
    setMessage('');
    try {
      const token = await createToken();
      const url = new URL(window.location.pathname, window.location.origin);
      url.hash = new URLSearchParams({ rentalIdentity: token }).toString();
      setLink(url.href);
      await copy(url.href);
    } catch {
      setMessage('Could not create a verification link. Try again.');
    } finally {
      setBusy(false);
    }
  }

  return <div className="identity-share">
    <p>Anyone with this 24-hour link can see your name, active certificate status, and rent history summary.</p>
    <button type="button" className="secondary" disabled={busy} onClick={share}>{busy ? 'Creating link…' : 'Share verified rental identity'}</button>
    {link && <label>Verification link<input readOnly value={link} onFocus={event => event.target.select()} /></label>}
    {message && <p role="status">{message}</p>}
  </div>;
}
