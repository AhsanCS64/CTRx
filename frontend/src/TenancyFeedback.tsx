import { useEffect, useState, type FormEvent } from 'react';
import { Button } from './Button';

const categories = {
  communication: 'Communication',
  rent_handling: 'Rent and payment handling',
  property_care: 'Property care',
  repairs: 'Repairs and maintenance',
  conduct: 'Conduct',
} as const;

const ratings = { positive: 'Positive', satisfactory: 'Satisfactory', concern: 'Concern' } as const;
type Category = keyof typeof categories;
type Rating = keyof typeof ratings;
type Feedback = { period_month: string | null; category: Category; rating: Rating; remark: string; updated_at: string; mine: boolean };
type Tenancy = { unit_number?: string | null; id: string; address_line: string; counterpart_name: string | null; start_date: string; end_date: string | null; feedback: Feedback[] };
type RequestApi = <T>(path: string, options?: RequestInit) => Promise<T>;

export function TenancyFeedback({ request, tenant, initialTenancyId, onViewTenancy }: { request: RequestApi; tenant: boolean; initialTenancyId?: string; onViewTenancy: (id: string) => void }) {
  const [tenancies, setTenancies] = useState<Tenancy[]>([]);
  const [selected, setSelected] = useState(initialTenancyId ?? '');
  const [selectedMonth, setSelectedMonth] = useState('');
  const [category, setCategory] = useState<Category>('communication');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const tenancy = tenancies.find(item => item.id === selected) ?? tenancies[0];
  const counterpart = tenant ? 'Landlord' : 'Tenant';
  const today = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Dhaka', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date());
  const currentMonth = today.slice(0, 7);
  const firstMonth = tenancy?.start_date.slice(0, 7) ?? currentMonth;
  const endMonth = tenancy?.end_date?.slice(0, 7);
  const lastMonth = endMonth && endMonth < currentMonth ? endMonth : currentMonth;
  const canReview = Boolean(tenancy && tenancy.start_date <= today && firstMonth <= lastMonth);
  const month = selectedMonth >= firstMonth && selectedMonth <= lastMonth ? selectedMonth : lastMonth;
  const monthlyFeedback = tenancy?.feedback.filter(item => item.period_month?.slice(0, 7) === month) ?? [];
  const olderFeedback = tenancy?.feedback.filter(item => !item.period_month) ?? [];
  const existing = monthlyFeedback.find(item => item.mine && item.category === category);

  useEffect(() => {
    const controller = new AbortController();
    request<Tenancy[]>('/tenancies/feedback', { signal: controller.signal })
      .then(setTenancies)
      .catch(reason => { if (!controller.signal.aborted) setError(reason.message); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [request]);

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!tenancy || !canReview) return;
    const fields = new FormData(event.currentTarget);
    setSaving(true);
    setError('');
    setNotice('');
    try {
      await request(`/tenancies/${tenancy.id}/feedback/${category}`, {
        method: 'PUT', body: JSON.stringify({ period_month: `${month}-01`, rating: fields.get('rating'), remark: fields.get('remark') }),
      });
      setTenancies(await request<Tenancy[]>('/tenancies/feedback'));
      setNotice('Feedback saved.');
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Could not save feedback.');
    } finally {
      setSaving(false);
    }
  }

  return <section className="panel feedback-panel">
    <div className="panel-heading"><div><h2>{tenant ? 'Review your landlord' : 'Review your tenant'}</h2><p>Record feedback for a rental month. Both parties on this tenancy can see the remarks.</p></div></div>
    {error && <p className="alert error" role="alert">{error}</p>}
    {notice && <p className="alert success" role="status">{notice}</p>}
    {loading && <p role="status">Loading your tenancies…</p>}
    {!loading && !error && !tenancy && <p>Feedback becomes available once you have a tenancy record.</p>}
    {tenancy && <>
      <label>{tenant ? 'Choose a tenancy' : 'Choose a tenant'}<select value={tenancy.id} disabled={saving} onChange={event => { setSelected(event.target.value); setSelectedMonth(''); setNotice(''); setError(''); }}>
        {tenancies.map(item => <option key={item.id} value={item.id}>
          {item.counterpart_name || counterpart} · {item.address_line}{item.unit_number ? ` · Apartment ${item.unit_number}` : ''} · {item.start_date}{item.end_date ? ` to ${item.end_date}` : ''}
        </option>)}
      </select></label>
      <p>{counterpart}{tenancy.counterpart_name ? ` · ${tenancy.counterpart_name}` : ''}</p>
      <div className="record-row">
        <div><strong>Tenancy start</strong><small>{new Date(tenancy.start_date + 'T00:00:00').toLocaleDateString(undefined, { dateStyle: 'long' })}</small></div>
        {!canReview && <Button className="secondary small-button" onClick={() => onViewTenancy(tenancy.id)}>View tenancy details</Button>}
      </div>
      {!canReview && <p className="alert" role="status">
        This tenancy starts on {new Date(tenancy.start_date + 'T00:00:00').toLocaleDateString(undefined, { dateStyle: 'long' })}. Monthly reviews open once the tenancy starts.
      </p>}
      {canReview && <>
      <label>Feedback month<input type="month" min={firstMonth} max={lastMonth} value={month} disabled={saving} onChange={event => {
        setSelectedMonth(event.target.value);
        setNotice('');
      }} /></label>
      <p className="muted">{tenant ? 'Feedback you give about your landlord is separate from your reliability score.' : 'Positive feedback can add one point per month to the tenant’s score when there are no concerns recorded for that month.'}</p>
      <label>Category<select value={category} disabled={saving} onChange={event => { setCategory(event.target.value as Category); setNotice(''); }}>
        {Object.entries(categories).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
      </select></label>
      <form className="form-grid" key={`${tenancy.id}-${month}-${category}-${existing?.updated_at ?? 'new'}`} onSubmit={save}>
        <label>Assessment<select name="rating" defaultValue={existing?.rating ?? 'satisfactory'} disabled={saving}>
          {Object.entries(ratings).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
        </select></label>
        <label className="wide">Remark<textarea name="remark" maxLength={1500} rows={4} required disabled={saving} defaultValue={existing?.remark ?? ''} placeholder="Describe what went well or what happened." /></label>
        <div className="wide"><Button className="primary" type="submit" disabled={saving}>{saving ? 'Saving…' : existing ? 'Update remark' : 'Save remark'}</Button></div>
      </form>
      <h3>Feedback for this month</h3>
      {!monthlyFeedback.length && <p>No remarks for this month yet.</p>}
      <FeedbackList items={monthlyFeedback} counterpart={counterpart} />
      </>}
      {olderFeedback.length > 0 && <details><summary>Earlier feedback without a month</summary><FeedbackList items={olderFeedback} counterpart={counterpart} /></details>}
    </>}
  </section>;
}


function FeedbackList({ items, counterpart }: { items: Feedback[]; counterpart: string }) {
  return <ul className="record-list">
    {items.map(item => <li className="record-row" key={`${item.category}-${item.mine}`}>
      <div><strong>{categories[item.category]}</strong><small>{item.mine ? 'You' : counterpart} · {new Date(item.updated_at).toLocaleDateString()}</small><p>{item.remark}</p></div>
      <span className={`status status-${item.rating === 'positive' ? 'active' : item.rating === 'concern' ? 'pending' : 'draft'}`}>{ratings[item.rating]}</span>
    </li>)}
  </ul>;
}
