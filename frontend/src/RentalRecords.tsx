import { LinkedCareEvidence, type CaseCareEvidence } from './TenancyCare';
import { FormEvent, useEffect, useState } from 'react';

type Api = <T>(path: string, options?: RequestInit) => Promise<T>;
type Download = { filename: string; content_base64: string };
type Tenancy = { id: string; address_line: string; status: string };
type Lease = { terms: Record<string, string | number>; tenant_acknowledged_at: string | null; landlord_acknowledged_at: string | null };
type Ledger = { id: string; period_month: string; entry_type: string; amount: number; reason?: string; payment_request_id?: string };
type Invoice = { id: string; period_month: string; status: string; amount: number };
type Statement = { address: string; ledger: Ledger[]; invoices: Invoice[]; posted_total: number; outstanding_total: number };
type Case = { id: string; reason: string; status: string; created_at: string; entity_type: string; resolution_note?: string };
type CaseDetail = Case & { can_review: boolean; care_evidence: CaseCareEvidence[]; timeline: { id: number; kind: string; message: string; filename?: string; role: string; created_at: string }[] };
type CaseSource = { entity_type: 'tenancy' | 'payment_request'; entity_id: string };

const label = (value: string) => value.replaceAll('_', ' ');
const money = (value: number) => new Intl.NumberFormat(undefined, { style: 'currency', currency: 'BDT' }).format(value);
const when = (value: string) => new Date(value).toLocaleString();

function saveFile(file: Download) {
  const bytes = Uint8Array.from(atob(file.content_base64), value => value.charCodeAt(0));
  const url = URL.createObjectURL(new Blob([bytes]));
  const link = document.createElement('a');
  link.href = url;
  link.download = file.filename;
  link.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function attachmentData(file: File): Promise<string> {
  if (file.size > 2 * 1024 * 1024) return Promise.reject(new Error('Choose an attachment up to 2 MB.'));
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error('Could not read the evidence file.'));
    reader.onload = () => resolve(String(reader.result).split(',')[1]);
    reader.readAsDataURL(file);
  });
}

export function RentalRecords({ view, setView, role, request, caseId }: { view: string; setView: (view: string) => void; role: string; request: Api; caseId?: string }) {
  const party = role === 'tenant' || role === 'landlord';
  const [tenancies, setTenancies] = useState<Tenancy[]>([]);
  const [tenancyId, setTenancyId] = useState('');
  const [agreement, setAgreement] = useState<Lease | null>();
  const [statement, setStatement] = useState<{ data: Statement; query: string }>();
  const [cases, setCases] = useState<Case[]>([]);
  const [activeCase, setActiveCase] = useState<CaseDetail>();
  const [source, setSource] = useState<CaseSource>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const currentMonth = new Date();
  const [startMonth, setStartMonth] = useState(`${currentMonth.getFullYear()}-01`);
  const [endMonth, setEndMonth] = useState(`${currentMonth.getFullYear()}-${String(currentMonth.getMonth() + 1).padStart(2, '0')}`);

  async function run(action: () => Promise<void>) {
    setBusy(true);
    setError('');
    setNotice('');
    try { await action(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Something went wrong'); }
    finally { setBusy(false); }
  }

  const casesPath = '/records/cases';
  const leasePath = `/records/leases/${tenancyId}`;
  const statementPath = `/records/statements/${tenancyId}`;
  const post = (body?: unknown): RequestInit => ({ method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) });

  async function loadCases() { setCases(await request<Case[]>(casesPath)); }
  async function loadCase(id: string) { setActiveCase(await request<CaseDetail>(`${casesPath}/${id}`)); }
  useEffect(() => {
    if (view === 'cases') void run(async () => {
      await loadCases();
      if (caseId) await loadCase(caseId);
    });
    else if (party) void run(async () => {
      const items = await request<Tenancy[]>('/records/tenancies');
      setTenancies(items);
      setTenancyId(current => items.some(item => item.id === current) ? current : items[0]?.id || '');
    });
  }, [view, party, caseId]);
  useEffect(() => {
    setAgreement(undefined);
    setStatement(undefined);
    if (view === 'leases' && tenancyId) void run(async () => setAgreement(await request<Lease | null>(leasePath)));
  }, [tenancyId, view]);

  function startCase(entity_type: CaseSource['entity_type'], entity_id: string) {
    setSource({ entity_type, entity_id });
    setActiveCase(undefined);
    setView('cases');
  }
  function submitCase(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const record = source?.entity_id ? source : { entity_type: 'tenancy', entity_id: String(form.get('tenancy')) };
    void run(async () => {
      const result = await request<{ id: string }>(casesPath, post({ ...record, reason: form.get('reason') }));
      setSource(undefined);
      await loadCases();
      await loadCase(result.id);
      setNotice('Dispute submitted.');
    });
  }
  function addMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeCase) return;
    const form = event.currentTarget;
    const fields = new FormData(form);
    const file = fields.get('evidence');
    const id = activeCase.id;
    void run(async () => {
      await request(`${casesPath}/${id}`, post({
        message: fields.get('message'), status: fields.get('status') || null,
        content_base64: file instanceof File && file.size ? await attachmentData(file) : null,
      }));
      form.reset();
      await loadCase(id);
      await loadCases();
      setNotice('Case updated.');
    });
  }
  const myAcknowledgement = role === 'tenant' ? agreement?.tenant_acknowledged_at : agreement?.landlord_acknowledged_at;
  const caseIsOpen = activeCase && ['open', 'under_review'].includes(activeCase.status);
  return <>
    {error && <p className="alert error" role="alert">{error}</p>}
    {notice && <p className="alert success" role="status">{notice}</p>}
    {view !== 'cases' && <section className="panel">
      <form className="auth-form" onSubmit={event => {
        event.preventDefault();
        const query = new URLSearchParams({ start: startMonth + '-01', end: endMonth + '-01' }).toString();
        void run(async () => setStatement({ data: await request<Statement>(`${statementPath}?${query}`), query }));
      }}>
        <label>Tenancy<select value={tenancyId} onChange={event => setTenancyId(event.target.value)} disabled={busy || !tenancies.length}>
          {!tenancies.length && <option value="">No tenancy records</option>}
          {tenancies.map(row => <option value={row.id} key={row.id}>{row.address_line} · {row.status}</option>)}
        </select></label>
        {view === 'statements' && <div className="search-filters">
          <label>From month<input type="month" required value={startMonth} onChange={e => setStartMonth(e.target.value)} /></label>
          <label>To month<input type="month" required min={startMonth} value={endMonth} onChange={e => setEndMonth(e.target.value)} /></label>
          <button className="primary" disabled={busy || !tenancyId}>View statement</button>
        </div>}
      </form>
      {busy && <p role="status">Loading…</p>}
    </section>}
    {view === 'leases' && tenancyId && agreement === null && <section className="panel"><h2>Prepare a draft</h2>
      <p>Capture the tenancy terms for both parties to review and acknowledge.</p>
      <button className="primary" disabled={busy} onClick={() => void run(async () => setAgreement(await request<Lease>(leasePath, post())))}>Prepare draft</button>
    </section>}
    {view === 'leases' && agreement && <section className="panel">
      <h2>{agreement.tenant_acknowledged_at && agreement.landlord_acknowledged_at ? 'Acknowledged agreement' : 'Agreement draft'}</h2>
      <dl className="profile-facts">{Object.entries(agreement.terms).map(([key, value]) => <div className="record-fact" key={key}><dt>{label(key)}</dt><dd>{['deposit', 'monthly_rent'].includes(key) ? money(Number(value)) : value}</dd></div>)}</dl>
      <p>Tenant acknowledgement {agreement.tenant_acknowledged_at ? when(agreement.tenant_acknowledged_at) : 'pending'}</p>
      <p>Landlord acknowledgement {agreement.landlord_acknowledged_at ? when(agreement.landlord_acknowledged_at) : 'pending'}</p>
      <div className="button-row">
        {!myAcknowledgement && <button className="primary" disabled={busy} onClick={() => void run(async () => {
          setAgreement(await request<Lease>(`${leasePath}/acknowledge`, post())); setNotice('Agreement acknowledged.');
        })}>Acknowledge these terms</button>}
        <button className="secondary" disabled={busy} onClick={() => void run(async () => saveFile(await request<Download>(`${leasePath}/pdf`)))}>Download PDF</button>
        <button className="secondary" disabled={busy} onClick={() => startCase('tenancy', tenancyId)}>Open a dispute</button>
      </div>
    </section>}
    {view === 'statements' && statement && <section className="panel">
      <div className="panel-heading"><div><h2>{statement.data.address}</h2><p>Posted {money(statement.data.posted_total)} · Outstanding {money(statement.data.outstanding_total)}</p></div>
        <button className="secondary" disabled={busy} onClick={() => void run(async () => saveFile(await request<Download>(`${statementPath}/pdf?${statement.query}`)))}>Download PDF</button></div>
      <h3>Ledger entries</h3>
      {!statement.data.ledger.length && <p>No ledger entries for this period.</p>}
      {statement.data.ledger.map(row => <div className="record-row" key={row.id}><div><strong>{row.period_month.slice(0, 7)} · {label(row.entry_type)}</strong>{row.reason && <small>{row.reason}</small>}</div><b>{money(row.amount)}</b>
        {row.payment_request_id && <button className="secondary small-button" onClick={() => startCase('payment_request', row.payment_request_id!)}>Dispute payment</button>}</div>)}
      <h3>Outstanding invoices</h3>
      {!statement.data.invoices.length && <p>No outstanding invoices for this period.</p>}
      {statement.data.invoices.map(row => <div className="record-row" key={row.id}><div><strong>{row.period_month.slice(0, 7)} · {row.status === 'submitted' ? 'Awaiting confirmation' : 'Awaiting payment'}</strong></div><b>{money(row.amount)}</b>
        <button className="secondary small-button" onClick={() => startCase('payment_request', row.id)}>Dispute invoice</button></div>)}
    </section>}
    {view === 'cases' && <>
      <section className="panel"><div className="panel-heading"><h2>Rental disputes</h2>{party && !source && <button className="secondary" disabled={busy} onClick={() => void run(async () => {
        const items = await request<Tenancy[]>('/records/tenancies');
        setTenancies(items);
        setActiveCase(undefined);
        setSource({ entity_type: 'tenancy', entity_id: '' });
      })}>Open a case</button>}</div>
        {!cases.length && <p>No disputes to show.</p>}
        {cases.map(item => <article className="record-row" key={item.id}><div><strong>{item.reason}</strong><small>{label(item.entity_type)} · {when(item.created_at)}</small></div>
          <button className="secondary small-button" disabled={busy} onClick={() => { setSource(undefined); void run(() => loadCase(item.id)); }}>{label(item.status)} · View case</button></article>)}
      </section>
      {party && source && <section className="panel"><h2>Open a dispute</h2><form className="auth-form" onSubmit={submitCase}>
        {source.entity_id ? <p>Related record: {label(source.entity_type)}</p> : <label>Tenancy<select required name="tenancy"><option value="">Select a tenancy</option>{tenancies.map(item => <option key={item.id} value={item.id}>{item.address_line}</option>)}</select></label>}
        <label>What happened?<textarea name="reason" rows={4} required maxLength={4000} /></label>
        <div className="button-row"><button className="primary" disabled={busy}>Submit dispute</button><button type="button" className="secondary" onClick={() => setSource(undefined)}>Cancel</button></div>
      </form></section>}
      {activeCase && <section className="panel"><div className="panel-heading"><h2>Case timeline</h2><span className="status">{label(activeCase.status)}</span></div>
        <article className="record-row"><div><strong>Case opened</strong><small>{when(activeCase.created_at)}</small><p>{activeCase.reason}</p></div></article>
        <LinkedCareEvidence records={activeCase.care_evidence ?? []} />
        {activeCase.timeline.map(entry => <article className="record-row" key={entry.id}>
          <div><strong>{label(entry.kind)} · {entry.role}</strong><small>{when(entry.created_at)}</small><p>{entry.message}</p></div>
          {entry.filename && <button className="secondary small-button" disabled={busy} onClick={() => void run(async () => saveFile(
            await request<Download>(`${casesPath}/${activeCase.id}/evidence/${entry.id}`)
          ))}>Download evidence</button>}
        </article>)}
        {caseIsOpen && <form className="auth-form" onSubmit={addMessage}>
          <label>Case update<textarea required name="message" rows={3} maxLength={4000} /></label>
          <label>Evidence<input name="evidence" type="file" accept="application/pdf,image/png,image/jpeg" /></label>
          <small>PDF, PNG or JPEG up to 2 MB.</small>
          {activeCase.can_review && <label>Status<select name="status"><option value="">Add a message</option>{activeCase.status === 'open'
            ? <option value="under_review">Start review</option>
            : <><option value="resolved">Resolve</option><option value="rejected">Reject</option></>}</select></label>}
          <button className="primary" disabled={busy}>Post update</button>
        </form>}
      </section>}
    </>}
  </>;
}

