import { FormEvent, useEffect, useState } from 'react';

type RequestApi = <T>(path: string, options?: RequestInit) => Promise<T>;
type Ticket = { id: string; ticket_number: number; subject: string; description: string; category: string; priority: string; status: string; created_at: string };
type Message = { id: string; sender_role: string; message: string; is_internal: boolean; created_at: string };

export function SupportCenter({ request, staff }: { request: RequestApi; staff: boolean }) {
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [selected, setSelected] = useState<Ticket>();
  const [messages, setMessages] = useState<Message[]>([]);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function load() {
    setTickets(await request<Ticket[]>('/support/tickets'));
  }
  async function open(ticket: Ticket) {
    setSelected(ticket);
    setMessages(await request<Message[]>(`/support/tickets/${ticket.id}`));
  }
  useEffect(() => { void load().catch(reason => setError(reason.message)); }, []);

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    const payload = Object.fromEntries(data);
    setBusy(true);
    setError('');
    const action = selected
      ? request(`/support/tickets/${selected.id}/messages`, { method: 'POST', body: JSON.stringify({ message: payload.message }) })
      : request('/support/tickets', { method: 'POST', body: JSON.stringify(payload) });
    void action.then(async () => {
      form.reset();
      await load();
      if (selected) await open(selected);
    }).catch(reason => setError(reason.message)).finally(() => setBusy(false));
  }

  async function setStatus(status: string) {
    if (!selected) return;
    setBusy(true);
    try {
      await request(`/support/tickets/${selected.id}`, { method: 'PATCH', body: JSON.stringify({ status }) });
      await load();
      const next = tickets.find(item => item.id === selected.id);
      if (next) setSelected({ ...next, status });
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Could not update ticket'); }
    finally { setBusy(false); }
  }

  return <div className="support-layout">
    <section className="panel"><header className="panel-heading"><h2>Support requests</h2><button className="secondary" onClick={() => setSelected(undefined)}>New request</button></header>
      {error && <p className="alert error" role="alert">{error}</p>}
      {!tickets.length && <p>No support requests yet.</p>}
      {tickets.map(ticket => <button className="support-ticket" key={ticket.id} onClick={() => void open(ticket)}>
        <strong>#{ticket.ticket_number} · {ticket.subject}</strong><small>{ticket.category} · {ticket.status} · {new Date(ticket.created_at).toLocaleDateString()}</small>
      </button>)}
    </section>
    <section className="panel">
      {selected ? <><header className="panel-heading"><div><h2>#{selected.ticket_number} · {selected.subject}</h2><small>{selected.category} · {selected.status}</small></div>
        {staff && <select aria-label="Ticket status" value={selected.status} disabled={busy} onChange={event => void setStatus(event.target.value)}>
          {['open','in_progress','waiting_user','resolved','closed'].map(status => <option key={status}>{status}</option>)}
        </select>}</header>
        <div className="support-messages">{messages.map(message => <article className="record-row" key={message.id}><div><strong>{message.sender_role}</strong><small>{new Date(message.created_at).toLocaleString()}</small><p>{message.message}</p></div></article>)}</div>
        {selected.status !== 'closed' && selected.status !== 'resolved' && <form className="auth-form" onSubmit={submit}>
          <label>Reply<textarea name="message" rows={3} required maxLength={4000} /></label><button className="primary" disabled={busy}>Send reply</button>
        </form>}
      </> : <><h2>Contact CTRx support</h2><p>Send a question about your account or a problem using the service.</p>
        <form className="auth-form" onSubmit={submit}>
          <label>Category<select name="category"><option value="general">General</option><option value="account">Account</option><option value="ric_application">RIC application</option><option value="certificate">Certificate</option><option value="property">Property</option><option value="payment">Payment</option><option value="technical">Technical</option><option value="other">Other</option></select></label>
          <label>Subject<input name="subject" required minLength={4} maxLength={160} /></label>
          <label>Details<textarea name="description" rows={5} required minLength={10} maxLength={4000} /></label>
          <button className="primary" disabled={busy}>Submit request</button>
        </form>
      </>}
    </section>
  </div>;
}
