import { useEffect, useState } from 'react';

type RequestApi = <T>(path: string) => Promise<T>;
type Certificate = { id: string; ric_number: string; status: string; issued_at: string; applicant_name: string; area_name: string };
type Event = { id: string; event_type: string; points_delta?: number; description?: string; created_at: string; success?: boolean; delivery_channel?: string; failure_reason?: string };
type Privacy = { grants: { id: number; landlord_email: string; categories: string[]; expires_at: string; revoked_at: string | null }[]; events: { id: string; event_type: string; scopes: string[]; reason?: string; created_at: string }[] };

function formatScopes(value: unknown) {
  if (Array.isArray(value)) return value.join(', ');
  return typeof value === 'string' ? value : '';
}

export function TrustHistory({ request, certificates, tenant, landlord, onDownload }: { request: RequestApi; certificates: Certificate[]; tenant: boolean; landlord: boolean; onDownload: (id: string) => void }) {
  const [privacy, setPrivacy] = useState<Privacy>();
  const [sharedCertificates, setSharedCertificates] = useState<Certificate[]>([]);
  const [selected, setSelected] = useState('');
  const [events, setEvents] = useState<Event[]>([]);
  const [scoreEvents, setScoreEvents] = useState<Event[]>([]);
  const [error, setError] = useState('');
  const [privacyError, setPrivacyError] = useState('');
  const [privacyAttempt, setPrivacyAttempt] = useState(0);
  const grants = Array.isArray(privacy?.grants) ? privacy.grants : [];
  const consentEvents = Array.isArray(privacy?.events) ? privacy.events : [];
  useEffect(() => {
    if (tenant) {

      void request<Event[]>('/workspace/reliability/events').then(setScoreEvents).catch(reason => setError(reason.message));
    }
    if (landlord) void request<Certificate[]>('/workspace/shared-certificates').then(setSharedCertificates).catch(reason => setError(reason.message));
  }, [tenant, landlord]);
  useEffect(() => {
    if (!tenant) return;
    let active = true;
    setPrivacyError('');
    void request<Privacy>('/workspace/privacy').then(data => {
      if (!active) return;
      if (!data || !Array.isArray(data.grants) || !Array.isArray(data.events)) {
        throw new Error('The server returned incomplete privacy history.');
      }
      setPrivacy(data);
    }).catch(reason => {
      if (active) setPrivacyError(reason instanceof Error ? reason.message : 'Could not load privacy history.');
    });
    return () => { active = false; };
  }, [request, tenant, privacyAttempt]);
  const visibleCertificates = tenant ? certificates : sharedCertificates;
  const selectedCertificate = visibleCertificates.find(certificate => certificate.id === selected);
  async function loadCertificate(id: string) {
    setSelected(id);
    if (!id) return setEvents([]);
    try { setEvents(await request<Event[]>(`/workspace/certificates/${id}/delivery`)); }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Could not load delivery history'); }
  }
  return <div className="sharing-layout">
    {error && <p className="alert error" role="alert">{error}</p>}
    <section className="panel"><h2>Certificate delivery history</h2>
      {visibleCertificates.length ? <label>Certificate<select value={selected} onChange={event => void loadCertificate(event.target.value)}>
        <option value="">Choose a certificate</option>{visibleCertificates.map(cert => <option value={cert.id} key={cert.id}>{cert.ric_number} · {cert.applicant_name}</option>)}
      </select></label> : <p>{landlord ? 'Tenants have not shared any certificates with you.' : 'No certificates are linked to this account.'}</p>}
      {selectedCertificate && <div className="record-actions"><button className="secondary small-button" onClick={() => onDownload(selectedCertificate.id)}>Download certificate PDF</button></div>}
      {selected && events.length === 0 && <p>No delivery events recorded yet.</p>}
      {events.map(event => <article className="record-row" key={event.id}><div><strong>{event.event_type} · {event.success ? 'Completed' : 'Needs attention'}</strong><small>{event.delivery_channel || 'In app'} · {new Date(event.created_at).toLocaleString()}</small>{event.failure_reason && <small>{event.failure_reason}</small>}</div></article>)}
    </section>
    {tenant && <section className="panel"><h2>Privacy activity</h2>
      {privacyError ? <div role="alert" className="alert error"><p>{privacyError}</p><button className="secondary small-button" onClick={() => setPrivacyAttempt(attempt => attempt + 1)}>Retry privacy history</button></div>
        : !privacy ? <p role="status">Loading privacy history…</p> : <><h3>Rental history access</h3>
      {!grants.length && <p>No sharing grants recorded.</p>}
      {grants.map(grant => <article className="record-row" key={grant.id}><div><strong>{grant.landlord_email}</strong><small>{formatScopes(grant.categories)} · {grant.revoked_at ? 'Revoked' : 'Active until ' + new Date(grant.expires_at).toLocaleDateString()}</small></div></article>)}
      <h3>Consent history</h3>{!consentEvents.length && <p>{grants.length ? 'This access grant predates consent event tracking. New grants and revocations will appear here.' : 'No consent events recorded yet.'}</p>}
      {consentEvents.map(event => <article className="record-row" key={event.id}><div><strong>{event.event_type === 'granted' ? 'Rental history access granted or updated' : event.event_type === 'revoked' ? 'Rental history access revoked' : event.event_type}</strong><small>{formatScopes(event.scopes)} · {new Date(event.created_at).toLocaleString()}</small>{event.reason && <small>{event.reason}</small>}</div></article>)}
      </>}
    </section>}
    {tenant && <section className="panel"><h2>Reliability score events</h2>
      {!scoreEvents.length && <p>No score events recorded yet.</p>}
      {scoreEvents.map(event => <article className="record-row" key={event.id}><div><strong>{event.description || event.event_type}</strong><small>{new Date(event.created_at).toLocaleString()}</small></div><b>{event.points_delta}</b></article>)}
    </section>}
  </div>;
}
