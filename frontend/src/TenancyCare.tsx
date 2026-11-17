import { useEffect, useState, type FormEvent, type ReactNode } from 'react';

type Request = <T>(path: string, options?: RequestInit) => Promise<T>;
type Kind = 'move_in' | 'move_out' | 'maintenance' | 'deposit';
type Photo = { taken_on: string; data: string };
type Room = { name: string; check: string; condition: string; notes: string };
type Deduction = { description: string; amount: string; evidence: string; photo?: Photo };
type Home = { unit_number?: string | null; id: string; address: string; status: string; start_date: string; deposit: string };
type Case = { id: string; entity_type: string; entity_id: string; reason: string };
type RecordBase = { id: string; created_at: string; case_ids?: string[] };
type Inspection = RecordBase & { kind: 'move_in' | 'move_out'; inspected_on: string; rooms: Room[]; meters: string; keys: string; photos: Photo[]; acknowledgements: Record<string, string> };
type Repair = RecordBase & { kind: 'maintenance'; title: string; description: string; photos: Photo[]; status: string; history: { status: string; note: string; scheduled_for?: string; at: string }[] };
type Settlement = RecordBase & { kind: 'deposit'; original: string; returned: string; balance: string; returned_on?: string; reference?: string; returns: { amount: string; returned_on: string; reference: string }[]; deductions: Deduction[]; responses: Record<string, { decision: string; note: string; at: string }> };
type CareRecord = Inspection | Repair | Settlement;

const labels: Record<Kind, string> = { move_in: 'Move-in inspection', move_out: 'Move-out inspection', maintenance: 'Maintenance', deposit: 'Deposit settlement' };
const money = (value: string | number) => '৳' + Number(value).toLocaleString('en-BD', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const readable = (value: string) => value.replaceAll('_', ' ');
const dateTime = (value: string) => new Date(value).toLocaleString();
const errorText = (error: unknown) => error instanceof Error ? error.message : 'Something went wrong.';
const post = (payload: object): RequestInit => ({ method: 'POST', body: JSON.stringify(payload) });

function PhotoFields({ multiple = false }: { multiple?: boolean }) {
  return <div className="care-fields">
    <label>{multiple ? 'Photos (up to 4)' : 'Evidence photo'}<input name="photo" type="file" accept="image/jpeg,image/png,image/webp" multiple={multiple} /></label>
    <label>Date photos were taken<input name="photo_date" type="date" /></label>
  </div>;
}

async function photosFrom(container: ParentNode): Promise<Photo[]> {
  const photos = Array.from(container.querySelector<HTMLInputElement>('input[name=photo]')?.files ?? []);
  const taken_on = container.querySelector<HTMLInputElement>('input[name=photo_date]')?.value ?? '';
  if (photos.length && !taken_on) throw new Error('Enter the date the photos were taken.');
  if (photos.length > 4 || photos.some(photo => photo.size > 1_000_000)) {
    throw new Error('Choose up to four photos, each no larger than 1 MB.');
  }
  return Promise.all(photos.map(photo => new Promise<Photo>((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error('Could not read the photo.'));
    reader.onload = () => resolve({ data: String(reader.result), taken_on });
    reader.readAsDataURL(photo);
  })));
}

export function PhotoGallery({ photos }: { photos: Photo[] }) {
  return photos.length > 0 && <div className="care-gallery">{photos.map(({ data, taken_on }, index) =>
    <figure key={index}><img src={data} alt={'Evidence photo ' + (index + 1)} loading="lazy" /><figcaption>{taken_on}</figcaption></figure>
  )}</div>;
}

function RepeatedFields({ label, limit, initial, children }: { label: string; limit: number; initial: number; children: ReactNode }) {
  const [ids, setIds] = useState(Array.from({ length: initial }, (_, index) => index));
  const [next, setNext] = useState(initial);
  return <div className="care-stack">
    {ids.map((id, index) => <fieldset data-line key={id}>
      <legend>{label} {index + 1}</legend>
      {children}
      {ids.length > initial && <button type="button" className="secondary small-button" onClick={() => setIds(ids.filter(item => item !== id))}>Remove {label.toLowerCase()}</button>}
    </fieldset>)}
    {ids.length < limit && <button type="button" className="secondary small-button" onClick={() => { setIds([...ids, next]); setNext(next + 1); }}>Add {label.toLowerCase()}</button>}
  </div>;
}

function CreateForm({ kind, home, busy, save }: { kind: Kind; home: Home; busy: boolean; save: (make: () => Promise<object>) => void }) {
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    const read = (name: string) => String(data.get(name) ?? '').trim();
    const lines = Array.from(form.querySelectorAll('[data-line]'));
    const field = (line: Element, name: string) => line.querySelector<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>('[name=' + name + ']')?.value.trim() ?? '';
    save(async () => {
      if (kind === 'maintenance') return { kind, title: read('title'), description: read('description'), photos: await photosFrom(form) };
      if (kind === 'deposit') {
        const deductions = await Promise.all(lines.map(async line => ({
          description: field(line, 'description'), amount: field(line, 'amount'),
          evidence: field(line, 'evidence'), photo: (await photosFrom(line))[0],
        })));
        return { kind, deductions, returned: read('returned'), returned_on: read('returned_on') || null, reference: read('reference') };
      }
      return {
        kind, inspected_on: read('inspected_on'), meters: read('meters'), keys: read('keys'),
        rooms: lines.map(line => ({ name: field(line, 'room'), check: field(line, 'check'), condition: field(line, 'condition'), notes: field(line, 'notes') })),
        photos: await photosFrom(form),
      };
    });
  }

  return <form className="care-stack" onSubmit={submit}>
    {kind === 'maintenance' ? <>
      <label>Issue<input name="title" maxLength={160} required /></label>
      <label>Description<textarea name="description" maxLength={2000} required /></label>
      <PhotoFields multiple />
    </> : kind === 'deposit' ? <>
      <p>Original deposit <strong>{money(home.deposit)}</strong></p>
      <RepeatedFields label="Deduction" initial={0} limit={8}>
        <div className="care-fields">
          <label>Item<input name="description" maxLength={160} required /></label>
          <label>Amount (৳)<input name="amount" type="number" min="0.01" max={home.deposit} step="0.01" required /></label>
        </div>
        <label>Evidence or receipt reference<textarea name="evidence" maxLength={2000} required /></label>
        <PhotoFields />
      </RepeatedFields>
      <div className="care-fields">
        <label>Amount returned (৳)<input name="returned" type="number" min="0" max={home.deposit} step="0.01" defaultValue={home.deposit} required /></label>
        <label>Return date<input name="returned_on" type="date" /></label>
      </div>
      <label>Payment reference<input name="reference" maxLength={160} /></label>
    </> : <>
      <label>Inspection date<input name="inspected_on" type="date" required /></label>
      <RepeatedFields label="Checklist item" initial={1} limit={30}>
        <div className="care-fields">
          <label>Room<input name="room" placeholder="Kitchen" maxLength={160} required /></label>
          <label>Item checked<input name="check" placeholder="Sink and taps" maxLength={160} required /></label>
          <label>Condition<select name="condition"><option value="good">Good</option><option value="worn">Worn</option><option value="damaged">Damaged</option><option value="not_checked">Not checked</option></select></label>
        </div>
        <label>Notes<input name="notes" maxLength={1000} /></label>
      </RepeatedFields>
      <div className="care-fields">
        <label>Meter readings<textarea name="meters" placeholder="Electricity meter, reading and unit, or N/A" maxLength={2000} required /></label>
        <label>Keys handed over<textarea name="keys" placeholder="Date, key types, counts and recipient" maxLength={2000} required /></label>
      </div>
      <PhotoFields multiple />
    </>}
    <button className="primary" disabled={busy}>{busy ? 'Saving…' : 'Save record'}</button>
  </form>;
}

function downloadStatement(home: Home, record: Settlement) {
  const lines = [
    'CTRx deposit closing statement', [home.address, home.unit_number && `Apartment ${home.unit_number}`].filter(Boolean).join(' · '), 'Tenancy reference ' + home.id,
    'Statement recorded ' + dateTime(record.created_at), '',
    'Original deposit ' + money(record.original),
    ...record.deductions.flatMap((item, index) => [
      (index + 1) + '. ' + item.description + ' · ' + money(item.amount),
      'Evidence: ' + item.evidence + (item.photo ? ' · photo dated ' + item.photo.taken_on : ''),
      'Tenant response: ' + (record.responses[index] ? readable(record.responses[index].decision) + ' · ' + record.responses[index].note : 'Awaiting response'),
    ]),
    '', 'Returned ' + money(record.returned), 'Balance due ' + money(record.balance),
    'Return date ' + (record.returned_on || '—'), 'Reference ' + (record.reference || '—'),
    ...record.returns.map(payment => 'Return payment ' + payment.returned_on + ' · ' + money(payment.amount) + ' · ' + payment.reference),
    ...(record.case_ids ?? []).map(id => 'Linked dispute ' + id),
  ];
  const url = URL.createObjectURL(new Blob([lines.join('\n')], { type: 'text/plain;charset=utf-8' }));
  const link = document.createElement('a');
  link.href = url;
  link.download = 'deposit-statement-' + record.id + '.txt';
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function CareCard({ record, home, role, cases, busy, change, openCase }: { record: CareRecord; home: Home; role: string; cases: Case[]; busy: boolean; change: (payload: object) => void; openCase: (id: string) => void }) {
  const linkedCases = record.case_ids ?? [];
  const candidates = cases.filter(item => !linkedCases.includes(item.id));
  return <article className="care-card care-stack">
    <header><h3>{record.kind === 'maintenance' ? record.title : labels[record.kind]}</h3><small>Recorded {dateTime(record.created_at)}</small></header>
    {record.kind === 'maintenance' ? <>
      <p>{record.description}</p>
      <PhotoGallery photos={record.photos} />
      <ol className="repair-history">
        <li><strong>Reported</strong> <small>{dateTime(record.created_at)}</small></li>
        {record.history.map((event, index) => <li key={index}><strong>{readable(event.status)}</strong> <small>{dateTime(event.at)}</small><p>{event.scheduled_for && 'Repair date ' + event.scheduled_for + ' · '}{event.note}</p></li>)}
      </ol>
      {role === 'landlord' && record.status !== 'completed' && <form className="care-stack" key={record.history.length} onSubmit={event => {
        event.preventDefault();
        const data = new FormData(event.currentTarget);
        change({ action: 'repair', status: data.get('status'), scheduled_for: data.get('scheduled_for') || null, note: data.get('note') });
      }}>
        <div className="care-fields">
          <label>Repair status<select name="status">
            {record.status !== 'in_progress' && <option value="scheduled">Scheduled</option>}
            {record.status === 'scheduled' && <option value="in_progress">In progress</option>}
            {record.status !== 'reported' && <option value="completed">Completed</option>}
          </select></label>
          <label>Repair date<input name="scheduled_for" type="date" /></label>
        </div>
        <label>Update<textarea name="note" required maxLength={2000} /></label>
        <button className="secondary" disabled={busy}>Save repair update</button>
      </form>}
    </> : record.kind === 'deposit' ? <>
      <div className="care-metrics"><div>Original<strong>{money(record.original)}</strong></div><div>Returned<strong>{money(record.returned)}</strong></div><div>Balance due<strong>{money(record.balance)}</strong></div></div>
      {record.returns.map((payment, index) => <p key={index}>Returned {money(payment.amount)} on {payment.returned_on}{payment.reference && ' · ' + payment.reference}</p>)}
      {role === 'landlord' && Number(record.balance) > 0 && <form className="care-fields" key={record.returns.length} onSubmit={event => {
        event.preventDefault();
        const data = new FormData(event.currentTarget);
        change({ action: 'record_return', amount: data.get('amount'), returned_on: data.get('returned_on'), reference: data.get('reference') });
      }}>
        <label>Additional return (৳)<input name="amount" type="number" min="0.01" max={record.balance} step="0.01" required /></label>
        <label>Return date<input name="returned_on" type="date" required /></label>
        <label>Payment reference<input name="reference" maxLength={160} /></label>
        <button className="secondary" disabled={busy}>Record return</button>
      </form>}
      {record.deductions.map((item, index) => <div className="care-line care-stack" key={index}>
        <strong>{item.description} · {money(item.amount)}</strong><p>{item.evidence}</p>
        {item.photo && <PhotoGallery photos={[item.photo]} />}
        {record.responses[index] && <p>Tenant {record.responses[index].decision} · {dateTime(record.responses[index].at)}{record.responses[index].note && ' · ' + record.responses[index].note}</p>}
        {role === 'tenant' && <form className="care-fields" onSubmit={event => {
          event.preventDefault();
          const data = new FormData(event.currentTarget);
          change({ action: 'deduction', index, decision: data.get('decision'), note: data.get('note') });
        }}>
          <label>Response<select name="decision" defaultValue={record.responses[index]?.decision}><option value="acknowledged">Acknowledge</option><option value="disputed">Dispute</option></select></label>
          <label>Reason if disputing<input name="note" maxLength={2000} defaultValue={record.responses[index]?.note} /></label>
          <button className="secondary" disabled={busy}>Save response</button>
        </form>}
      </div>)}
      <button className="secondary" onClick={() => downloadStatement(home, record)}>Download closing statement</button>
    </> : <>
      <p>Inspected on {record.inspected_on}</p>
      <div className="care-stack">{record.rooms.map((room, index) => <div className="care-line" key={index}>
        <strong>{room.name} · {room.check}</strong><span className="care-condition">{readable(room.condition)}</span>{room.notes && <p>{room.notes}</p>}
      </div>)}</div>
      <dl className="care-fields"><div><dt>Meter readings</dt><dd>{record.meters}</dd></div><div><dt>Key handover</dt><dd>{record.keys}</dd></div></dl>
      <PhotoGallery photos={record.photos} />
      <div className="care-fields">{['tenant', 'landlord'].map(party => <p key={party}><strong>{party === 'tenant' ? 'Tenant' : 'Landlord'}</strong><br />{record.acknowledgements[party] ? dateTime(record.acknowledgements[party]) : 'Awaiting acknowledgement'}</p>)}</div>
      {!record.acknowledgements[role] && <button className="primary" disabled={busy} onClick={() => change({ action: 'acknowledge' })}>Acknowledge inspection</button>}
    </>}
    {record.kind !== 'maintenance' && <>
      {linkedCases.map(id => <button key={id} className="secondary small-button" onClick={() => openCase(id)}>Open linked dispute · {id.slice(0, 8)}</button>)}
      {candidates.length > 0 && <form className="care-fields" onSubmit={event => {
        event.preventDefault();
        change({ action: 'link_case', case_id: new FormData(event.currentTarget).get('case') });
      }}>
        <label>Tenancy dispute<select name="case">{candidates.map(item => <option key={item.id} value={item.id}>{item.reason.slice(0, 90)}</option>)}</select></label>
        <button className="secondary" disabled={busy}>Link dispute</button>
      </form>}
      {!cases.length && <small>Open a case for this tenancy in Disputes to link it here.</small>}
    </>}
  </article>;
}

export function TenancyCare({ request, role, openCase }: { request: Request; role: string; openCase: (id: string) => void }) {
  const [homes, setHomes] = useState<Home[]>();
  const [cases, setCases] = useState<Case[]>([]);
  const [selected, setSelected] = useState('');
  const [kind, setKind] = useState<Kind>('move_in');
  const [error, setError] = useState('');
  useEffect(() => {
    let active = true;
    Promise.all([request<Home[]>('/tenancy-care'), request<Case[]>('/records/cases')]).then(([items, disputes]) => {
      if (!active) return;
      setHomes(items);
      setSelected(items[0]?.id ?? '');
      setCases(disputes);
    }).catch(reason => { if (active) setError(errorText(reason)); });
    return () => { active = false; };
  }, [request]);
  const home = homes?.find(item => item.id === selected);
  return <section className="panel care-stack">
    <header><h2>Tenancy care</h2><p>Shared records for your home, from key handover to deposit settlement.</p></header>
    {error && <p role="alert" className="care-error">{error}</p>}
    {!homes && !error && <p role="status">Loading tenancies…</p>}
    {homes?.length === 0 && <p>Confirmed tenancies will appear here.</p>}
    {home && <>
      <label>Tenancy<select value={selected} onChange={event => setSelected(event.target.value)}>
        {homes?.map(item => <option key={item.id} value={item.id}>{item.address}{item.unit_number ? ` · Apartment ${item.unit_number}` : ''} · {item.start_date} · {item.status}</option>)}
      </select></label>
      <div className="care-tabs" aria-label="Tenancy record types">{(Object.keys(labels) as Kind[]).map(item =>
        <button className={kind === item ? 'primary' : 'secondary'} aria-pressed={kind === item} key={item} onClick={() => setKind(item)}>{labels[item]}</button>
      )}</div>
      <CareRecords key={home.id} {...{ home, kind, request, role, openCase }} cases={cases.filter(item => item.entity_type === 'tenancy' && item.entity_id === home.id)} />
    </>}
  </section>;
}

function CareRecords({ home, kind, request, role, cases, openCase }: { home: Home; kind: Kind; request: Request; role: string; cases: Case[]; openCase: (id: string) => void }) {
  const [records, setRecords] = useState<CareRecord[]>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [form, setForm] = useState<Kind>();
  const path = '/tenancy-care/' + home.id;
  useEffect(() => {
    let active = true;
    request<CareRecord[]>(path).then(items => { if (active) setRecords(items); }).catch(reason => { if (active) setError(errorText(reason)); });
    return () => { active = false; };
  }, [path, request]);

  async function save(make: () => Promise<object>, id?: string) {
    setBusy(true);
    setError('');
    try {
      const updated = await request<CareRecord>(id ? path + '/' + id : path, post(await make()));
      setRecords(previous => id ? previous?.map(item => item.id === id ? updated : item) : [updated, ...(previous ?? [])]);
      if (!id) setForm(undefined);
    } catch (reason) {
      setError(errorText(reason));
    } finally {
      setBusy(false);
    }
  }

  const visible = records?.filter(record => record.kind === kind) ?? [];
  const canCreate = kind === 'maintenance' ? role === 'tenant' && home.status === 'active' :
    !visible.length && (kind !== 'deposit' || role === 'landlord' && home.status !== 'active');
  return <div className="care-stack">
    {error && <p role="alert" className="care-error">{error}</p>}
    {!records && !error && <p role="status">Loading records…</p>}
    {records && <>
      {!visible.length && <p>{kind === 'deposit' && home.status === 'active' ? 'Settlement becomes available after this tenancy ends.' : 'No records yet.'}</p>}
      {canCreate && <div className="care-stack">
        <button className="secondary" disabled={busy} onClick={() => setForm(form === kind ? undefined : kind)}>{form === kind ? 'Close form' : kind === 'maintenance' ? 'Report an issue' : 'Create ' + labels[kind].toLowerCase()}</button>
        {form === kind && <CreateForm key={kind} {...{ kind, home, busy }} save={make => { void save(make); }} />}
      </div>}
      {visible.map(record => <CareCard key={record.id} {...{ record, home, role, cases, busy, openCase }} change={payload => { void save(async () => payload, record.id); }} />)}
    </>}
  </div>;
}


export type CaseCareEvidence =
  | { id: string; kind: 'move_in' | 'move_out'; content: Pick<Inspection, 'inspected_on' | 'rooms' | 'meters' | 'keys' | 'acknowledgements' | 'photos'> }
  | { id: string; kind: 'deposit'; content: Pick<Settlement, 'original' | 'returned' | 'balance' | 'deductions' | 'responses'> };

export function LinkedCareEvidence({ records }: { records: CaseCareEvidence[] }) {
  if (!records.length) return null;
  return <div className="care-stack"><h3>Linked tenancy evidence</h3>{records.map(record =>
    <details key={record.id} className="care-card"><summary>{labels[record.kind]}</summary>
      {record.kind === 'deposit' ? <div className="care-stack">
        <p>Original {money(record.content.original)} · Returned {money(record.content.returned)} · Balance due {money(record.content.balance)}</p>
        {record.content.deductions.map((item, index) => <div className="care-line" key={index}>
          <strong>{item.description} · {money(item.amount)}</strong><p>{item.evidence}</p>
          {item.photo && <PhotoGallery photos={[item.photo]} />}
          {record.content.responses[index] && <p>Tenant {record.content.responses[index].decision} · {record.content.responses[index].note}</p>}
        </div>)}
      </div> : <div className="care-stack">
        <p>Inspected on {record.content.inspected_on}</p>
        {record.content.rooms.map((room, index) => <div className="care-line" key={index}>
          <strong>{room.name} · {room.check}</strong><p>{readable(room.condition)} · {room.notes}</p>
        </div>)}
        <dl className="care-fields"><div><dt>Meter readings</dt><dd>{record.content.meters}</dd></div><div><dt>Key handover</dt><dd>{record.content.keys}</dd></div></dl>
        <p>Tenant acknowledgement {record.content.acknowledgements.tenant ? dateTime(record.content.acknowledgements.tenant) : 'Pending'} · Landlord acknowledgement {record.content.acknowledgements.landlord ? dateTime(record.content.acknowledgements.landlord) : 'Pending'}</p>
        <PhotoGallery photos={record.content.photos} />
      </div>}
    </details>
  )}</div>;
}
