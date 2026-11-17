import { EngineerProfile } from './EngineerProfile';
import engineerPhoto from '../../Assets/Developer/kushal.jpg';
import logoImage from '../../Assets/Logo/logo_ctrx.png';
import { TenancyCare } from './TenancyCare';
import { RentalTools } from './RentalTools';
import { RentalRecords } from './RentalRecords';
import { SupportCenter } from './SupportCenter';
import { TrustHistory } from './TrustHistory';
import { FormEvent, ReactElement, useEffect, useMemo, useRef, useState } from 'react';

type Role = 'tenant' | 'landlord' | 'government' | 'admin';
type User = { id: string; email: string; role: Role; is_active: boolean; created_at: string };
type Area = { id: number; division: string; division_code: string; district: string; district_code: string; name: string; upazila_code: string };
type Application = {
  id: string; applicant_name: string; email?: string; status: string; area_name?: string;
  area_id?: number; submitted_at: string; identity_last4?: string; rejection_reason?: string;
  local_note?: string; central_note?: string;
};
type Certificate = { id: string; ric_number: string; status: string; issued_at: string; applicant_name: string; area_name: string };
type GovernmentOverviewData = {
  official: { full_name: string; designation?: string | null; level: 'local' | 'central'; area_name?: string | null; district?: string | null; division?: string | null };
  status_counts: Record<string, number>;
  pending_review_count: number;
  ready_to_issue_count: number;
  issued_certificate_count: number;
};
type Property = { id: string; area_id: number; area_name?: string; district?: string; division?: string; address_line: string; property_type: string; monthly_rent: number; floor_area_sqft: number; bedrooms: number; bathrooms: number; floor_number: number; available_from: string; landlord_id: string; created_at: string; updated_at: string };
type Listing = { id: string; property_id: string; unit_id?: string; status: string; title?: string; description?: string; published_at?: string; created_at: string; updated_at: string };
type AvailableListing = Listing & { area_id: number; area_name: string; district: string; division: string; property_address: string; property_type: string; monthly_rent: number; floor_area_sqft: number; bedrooms: number; bathrooms: number; floor_number: number; unit_number?: string };
type Viewing = { id: string; tenant_id: string; listing_id: string; proposed_time: string; message?: string; status: string; expires_at: string; confirmed_time?: string; alternative_time?: string; created_at: string; updated_at: string; property_address?: string; area_name?: string; district?: string; division?: string; property_type?: string; unit_number?: string; monthly_rent?: number; listing_title?: string; landlord_name?: string; tenant_name?: string };
type Tenancy = { id: string; property_id: string; tenant_id: string; landlord_id: string; start_date: string; end_date?: string; rent: number; deposit: number; rent_due_day: number; status: string; created_at: string; updated_at: string; property_address?: string; property_type?: string };
type RentalOffer = { id: string; listing_id: string; tenant_id: string; landlord_id: string; proposed_rent: number; counter_rent?: number; status: string; move_in_date: string; message?: string; landlord_response?: string; tenant_response?: string; expires_at: string; responded_at?: string; created_at: string; updated_at?: string; property_address?: string; listing_title?: string; landlord_name?: string; tenant_name?: string };
type RentInvoice = { id: string; amount: number; status: string; period_month: string; description?: string; created_at: string; paid_on: string; payment_method?: string; note?: string };
type RentOverview = { active: boolean; tenancy_id?: string; tenant_id?: string; property_address?: string; property_type?: string; monthly_rent?: number; deposit?: number; rent_due_day?: number; start_date?: string; period_month?: string; invoice?: RentInvoice | null; paid_current_period?: boolean; total_paid?: number; outstanding?: number };
type LandlordRentRow = { tenancy_id: string; tenant_id: string; tenant_name?: string; property_address?: string; monthly_rent: number; rent_due_day: number; period_month: string; invoice_id?: string; invoice_status: string; payment_method?: string; payment_note?: string; paid_on?: string };
type RentPaymentReport = { payment_method: string; note?: string };
type PropertyUnit = { id: string; property_id: string; unit_number: string; floor_number: number; monthly_rent: number; floor_area_sqft: number; bedrooms: number; bathrooms: number; available_from: string; status: string; created_at: string; updated_at: string };

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL || (import.meta.env.DEV ? 'http://127.0.0.1:8003' : window.location.origin)).replace(/\/api\/?$/, '');
const token = () => localStorage.getItem('access_token') || '';

async function request<T>(path: string, options: RequestInit = {}, canRefresh = true): Promise<T> {
  const response = await fetch(`${apiBaseUrl}/api${path}`, {
    ...options,
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token()}`, ...(options.headers || {}) },
  });
  if (response.status === 401 && canRefresh && !path.startsWith('/auth/')) {
    const refresh = await fetch(`${apiBaseUrl}/api/auth/refresh`, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
    });
    if (refresh.ok) {
      const refreshed = await refresh.json() as { access_token: string };
      localStorage.setItem('access_token', refreshed.access_token);
      return request<T>(path, options, false);
    }
  }
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = Array.isArray(body.detail) ? body.detail.map((item: { msg: string }) => item.msg).join(', ') : body.detail;
    throw new Error(detail || `Request failed (HTTP ${response.status})`);
  }

  return body as T;
}

function AdminForm({ busy, onSubmit }: { busy: boolean; onSubmit: (payload: { email: string; password: string; full_name: string }) => void }) {
  function submit(event: FormEvent<HTMLFormElement>) { event.preventDefault(); const form = new FormData(event.currentTarget); onSubmit({ email: String(form.get('email')), password: String(form.get('password')), full_name: String(form.get('full_name')) }); }
  return <section className="panel form-panel"><span className="step">ADMINISTRATION · ACCESS CONTROL</span><h2>Create administrator account</h2><p>Only an authenticated administrator can create additional administrator accounts.</p><form onSubmit={submit} className="form-grid"><label>Administrator full name<input name="full_name" required /></label><label>Email<input name="email" type="email" required /></label><label className="wide">Password<input name="password" type="password" minLength={8} required /></label><div className="wide form-actions"><button className="primary" disabled={busy}>{busy ? 'Creating account…' : 'Create administrator'} <span>→</span></button></div></form></section>;
}

function formatStatus(status: string) {
  return status.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatLabel(value: string) {
  return value.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function AreaPicker({ areas, label, className = '', required = true }: { areas: Area[]; label: string; className?: string; required?: boolean }) {
  const [division, setDivision] = useState('');
  const [district, setDistrict] = useState('');
  const [areaId, setAreaId] = useState('');
  const divisions = useMemo(() => [...new Set(areas.map((area) => area.division))].sort((a, b) => a.localeCompare(b)), [areas]);
  const districts = useMemo(() => [...new Set(areas.filter((area) => area.division === division).map((area) => area.district))].sort((a, b) => a.localeCompare(b)), [areas, division]);
  const upazilas = useMemo(() => areas.filter((area) => area.division === division && area.district === district).sort((a, b) => a.name.localeCompare(b.name)), [areas, division, district]);

  return <div className={`area-location-picker ${className}`}>
    <label>Division<select value={division} required={required} onChange={(event) => { setDivision(event.target.value); setDistrict(''); setAreaId(''); }}><option value="">{required ? 'Select division' : 'All divisions'}</option>{divisions.map((name) => <option key={name} value={name}>{name}</option>)}</select></label>
    <label>District / Zilla<select value={district} required={required} disabled={!division} onChange={(event) => { setDistrict(event.target.value); setAreaId(''); }}><option value="">{required ? 'Select district' : 'All districts'}</option>{districts.map((name) => <option key={name} value={name}>{name}</option>)}</select></label>
    <label>{label}<select name="area_id" value={areaId} required={required} disabled={!district} onChange={(event) => setAreaId(event.target.value)}><option value="">{required ? 'Select upazila / thana' : 'All upazilas / thanas'}</option>{upazilas.map((area) => <option key={area.id} value={area.id}>{area.name}</option>)}</select></label>
  </div>;
}

function App() {
  const [user, setUser] = useState<User | null>(null);
  const [resetToken, setResetToken] = useState(() => new URLSearchParams(window.location.search).get('reset_token') || '');
  const [screen, setScreen] = useState<'home' | 'login' | 'register' | 'bootstrap' | 'forgot' | 'reset'>(() => new URLSearchParams(window.location.search).has('reset_token') ? 'reset' : 'home');
  const [loginRole, setLoginRole] = useState<Role>('tenant');
  const [registerRole, setRegisterRole] = useState<'tenant' | 'landlord'>('tenant');
  const [workspace, setWorkspace] = useState('overview');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [applications, setApplications] = useState<Application[]>([]);
  const [certificates, setCertificates] = useState<Certificate[]>([]);
  const [areas, setAreas] = useState<Area[]>([]);
  const [properties, setProperties] = useState<Property[]>([]);
  const [listings, setListings] = useState<Listing[]>([]);
  const [availableListings, setAvailableListings] = useState<AvailableListing[]>([]);
  const [viewings, setViewings] = useState<Viewing[]>([]);
  const [landlordViewings, setLandlordViewings] = useState<Viewing[]>([]);
  const [tenancies, setTenancies] = useState<Tenancy[]>([]);
  const [rentalOffers, setRentalOffers] = useState<RentalOffer[]>([]);
  const [landlordRentalOffers, setLandlordRentalOffers] = useState<RentalOffer[]>([]);
  const [rentOverview, setRentOverview] = useState<RentOverview | null>(null);
  const [landlordRent, setLandlordRent] = useState<LandlordRentRow[]>([]);
  const [selectedApp, setSelectedApp] = useState<Application | null>(null);
  const certificateRequestId = useRef(0);

  useEffect(() => {
    if (resetToken) {
      window.history.replaceState({}, document.title, `${window.location.pathname}${window.location.hash}`);
      return;
    }
    if (token()) request<User>('/auth/me').then(setUser).catch(() => localStorage.removeItem('access_token'));
  }, [resetToken]);

  useEffect(() => {
    certificateRequestId.current += 1;
    setCertificates([]);
    setError('');
    setApplications([]);
    setProperties([]);
    setListings([]);
    setAvailableListings([]);
    setViewings([]);
    setLandlordViewings([]);
    setTenancies([]);
    setRentalOffers([]);
    setLandlordRentalOffers([]);
    setRentOverview(null);
    setLandlordRent([]);
    setAreas([]);
    if (!user) return;
    if (user?.role === 'tenant') {
      request<Area[]>('/ric_applications/areas').then(setAreas).catch(() => undefined);
      loadTenantApplications();
      loadCertificates(true);
      loadTenantViewings();
      loadTenantTenancies();
      loadTenantRentalOffers();
      loadRentOverview();
    }
    if (user?.role === 'landlord') {
      request<Area[]>('/ric_applications/areas').then(setAreas).catch((reason) => setError(getMessage(reason)));
      loadLandlordProperties(); loadLandlordListings(); loadLandlordViewings();
      loadLandlordRentalOffers();
      loadLandlordRent();
    }
    if (user?.role === 'government') {
      loadQueue();
      loadCertificates();
    }
    if (user?.role === 'admin') {
      request<Area[]>('/ric_applications/areas').then(setAreas).catch(() => undefined);
    }
  }, [user]);

  async function loadLandlordProperties() {
    try { setProperties(await request<Property[]>('/properties/mine')); } catch (reason) { setError(getMessage(reason)); }
  }
  async function loadLandlordListings() {
    try { setListings(await request<Listing[]>('/properties/listings/mine')); } catch (reason) { setError(getMessage(reason)); }
  }
  async function loadAvailableProperties(areaId?: number) {
    try { setAvailableListings(await request<AvailableListing[]>(`/properties/available-listings${areaId ? `?area_id=${areaId}` : ''}`)); } catch (reason) { setError(getMessage(reason)); }
  }
  async function loadTenantViewings() {
    try { setViewings(await request<Viewing[]>('/viewings/mine')); } catch (reason) { setError(getMessage(reason)); }
  }
  async function loadLandlordViewings() {
    try { setLandlordViewings(await request<Viewing[]>('/viewings/landlord')); } catch (reason) { setError(getMessage(reason)); }
  }
  async function updateViewingStatus(id: string, nextStatus: 'confirmed' | 'declined' | 'countered', alternativeTime?: string) {
    setBusy(true); setError(''); setNotice('');
    try {
      await request(`/viewings/${id}/status`, { method: 'POST', body: JSON.stringify({ status: nextStatus, alternative_time: alternativeTime }) });
      setNotice(`Viewing request ${nextStatus}.`);
      await (user?.role === 'tenant' ? loadTenantViewings() : loadLandlordViewings());
    } catch (reason) { setError(getMessage(reason)); } finally { setBusy(false); }
  }
  async function loadTenantTenancies() {
    try { setTenancies(await request<Tenancy[]>('/tenancies/mine')); } catch (reason) { setError(getMessage(reason)); }
  }
  async function loadTenantRentalOffers() {
    try { setRentalOffers(await request<RentalOffer[]>('/rental_offers/mine')); } catch (reason) { setError(getMessage(reason)); }
  }
  async function loadLandlordRentalOffers() {
    try { setLandlordRentalOffers(await request<RentalOffer[]>('/rental_offers/landlord')); } catch (reason) { setError(getMessage(reason)); }
  }
  async function loadRentOverview() {
    try { setRentOverview(await request<RentOverview>('/rent/overview')); } catch (reason) { setError(getMessage(reason)); }
  }
  async function loadLandlordRent() {
    try { setLandlordRent(await request<LandlordRentRow[]>('/rent/tenancies')); } catch (reason) { setError(getMessage(reason)); }
  }
  async function payRent(invoiceId: string, report: RentPaymentReport) {
    setBusy(true); setError(''); setNotice('');
    try { await request(`/rent/invoices/${invoiceId}/pay`, { method: 'POST', body: JSON.stringify(report) }); setNotice('Payment reported. Your landlord must confirm receipt before it is recorded as paid.'); await loadRentOverview(); }
    catch (reason) { setError(getMessage(reason)); } finally { setBusy(false); }
  }
  async function confirmRentPayment(invoiceId: string) {
    setBusy(true); setError(''); setNotice('');
    try { await request(`/rent/invoices/${invoiceId}/confirm`, { method: 'POST' }); setNotice('Payment confirmed and added to the rent ledger.'); await loadLandlordRent(); }
    catch (reason) { setError(getMessage(reason)); } finally { setBusy(false); }
  }
  async function generateRent(tenancyId: string) {
    setBusy(true); setError(''); setNotice('');
    try { await request(`/rent/${tenancyId}/invoice`, { method: 'POST', body: JSON.stringify({}) }); setNotice('Monthly rent invoice generated.'); await loadLandlordRent(); }
    catch (reason) { setError(getMessage(reason)); } finally { setBusy(false); }
  }
  async function createRentalOffer(listingId: string, proposedRent: number, moveInDate: string, message?: string) {
    setBusy(true); setError(''); setNotice('');
    try {
      await request<RentalOffer>('/rental_offers', {
        method: 'POST',
        body: JSON.stringify({ listing_id: listingId, proposed_rent: proposedRent, move_in_date: moveInDate, message }),
      });
      setNotice('Rental offer submitted.');
      await loadTenantRentalOffers();
    } catch (reason) { setError(getMessage(reason)); } finally { setBusy(false); }
  }
  async function respondToRentalOffer(offerId: string, action: 'accept' | 'reject' | 'counter', counterRent?: number, responseMessage?: string) {
    setBusy(true); setError(''); setNotice('');
    try {
      await request<RentalOffer>(`/rental_offers/${offerId}/respond`, {
        method: 'POST',
        body: JSON.stringify({ action, counter_rent: counterRent, response_message: responseMessage }),
      });
      setNotice(`Offer ${action}.`);
      await loadLandlordRentalOffers();
    } catch (reason) { setError(getMessage(reason)); } finally { setBusy(false); }
  }
  async function tenantRespondToRentalOffer(offerId: string, action: 'accept' | 'counter' | 'withdraw', counterRent?: number, responseMessage?: string) {
    setBusy(true); setError(''); setNotice('');
    try {
      await request<RentalOffer>(`/rental_offers/${offerId}/tenant-respond`, {
        method: 'POST',
        body: JSON.stringify({ action, counter_rent: counterRent, response_message: responseMessage }),
      });
      setNotice(`Offer ${action}.`);
      await loadTenantRentalOffers();
    } catch (reason) { setError(getMessage(reason)); } finally { setBusy(false); }
  }
  async function endTenancy(tenancyId: string) {
    if (!window.confirm('Mark this tenancy as ended? Its history will remain preserved.')) return;
    setBusy(true); setError(''); setNotice('');
    try {
      await request(`/tenancies/${tenancyId}/status`, { method: 'POST', body: JSON.stringify({ status: 'ended' }) });
      setNotice('Tenancy ended. The historical record remains in your profile.');
      await loadTenantTenancies();
    } catch (reason) { setError(getMessage(reason)); } finally { setBusy(false); }
  }
  async function submitViewing(listingId: string, proposedTime: string) {
    setBusy(true); setError(''); setNotice('');
    try {
      await request('/viewings', { method: 'POST', body: JSON.stringify({ listing_id: listingId, proposed_time: new Date(proposedTime).toISOString() }) });
      setNotice('Viewing request sent. You can track it in Viewing requests.');
      await loadTenantViewings(); setWorkspace('viewings');
    } catch (reason) { setError(getMessage(reason)); } finally { setBusy(false); }
  }

  async function loadTenantApplications() {
    try {
      const result = await request<Application[]>('/ric_applications/mine');
      setApplications(result);
      await loadAvailableProperties(result[0]?.area_id);
    } catch (reason) { setError(getMessage(reason)); }
  }
  async function loadQueue() {
    try { setApplications(await request<Application[]>('/government/queue')); setError(''); } catch (reason) { setError(getMessage(reason)); }
  }
  async function loadCertificates(tenant = false) {
    const requestId = ++certificateRequestId.current;
    try {
      const result = await request<Certificate[]>(tenant ? '/certificates/mine' : '/certificates');
      if (requestId === certificateRequestId.current) { setCertificates(result); setError(''); }
    } catch (reason) {
      if (requestId === certificateRequestId.current) setError(getMessage(reason));
    }
  }
  async function downloadCertificate(id: string) {
    setError('');
    try {
      const response = await fetch(`${apiBaseUrl}/api/certificates/${id}/pdf-data`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token()}` },
      });
      if (!response.ok) throw new Error(response.status === 202 ? 'Certificate PDF is still being generated. Try again shortly.' : `Download failed (HTTP ${response.status})`);
      const payload = await response.json() as { filename: string; content_base64: string };
      const binary = atob(payload.content_base64);
      const bytes = Uint8Array.from(binary, (character) => character.charCodeAt(0));
      const blob = new Blob([bytes], { type: 'application/pdf' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url; link.download = payload.filename || `ric-${id}.pdf`; link.click(); URL.revokeObjectURL(url);
      setError('');
      setNotice('Certificate PDF downloaded.');
    } catch (reason) { setError(getMessage(reason)); }
  }
  function getMessage(reason: unknown) { return reason instanceof Error ? reason.message : 'Something went wrong'; }

  async function submitLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError('');
    const form = new FormData(event.currentTarget);
    try {
      const result = await request<{ access_token: string }>('/auth/login', {
        method: 'POST', body: JSON.stringify({ email: form.get('email'), password: form.get('password') }),
      });
      localStorage.setItem('access_token', result.access_token);
      const signedInUser = await request<User>('/auth/me');
      if (signedInUser.role !== loginRole) throw new Error(`This account is registered as ${signedInUser.role}.`);
      setUser(signedInUser); setWorkspace('overview');
    } catch (reason) { localStorage.removeItem('access_token'); setError(getMessage(reason)); }
    finally { setBusy(false); }
  }

  async function submitDemoPasswordReset(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError(''); setNotice('');
    const form = new FormData(event.currentTarget);
    if (form.get('password') !== form.get('confirm_password')) { setError('Passwords do not match'); setBusy(false); return; }
    try {
      const result = await request<{ message: string }>('/auth/password-reset/demo', {
        method: 'POST', body: JSON.stringify({ email: form.get('email'), password: form.get('password') }),
      });
      localStorage.removeItem('access_token');
      setUser(null); setResetToken(''); setScreen('login'); setLoginRole('tenant'); setNotice(result.message);
    } catch (reason) { setError(getMessage(reason)); } finally { setBusy(false); }
  }

  async function submitPasswordReset(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError(''); setNotice('');
    const form = new FormData(event.currentTarget);
    if (form.get('password') !== form.get('confirm_password')) { setError('Passwords do not match'); setBusy(false); return; }
    try {
      const result = await request<{ message: string }>('/auth/password-reset/confirm', {
        method: 'POST', body: JSON.stringify({ token: resetToken, password: form.get('password') }),
      });
      localStorage.removeItem('access_token');
      setUser(null); setResetToken(''); setScreen('login'); setLoginRole('tenant');
      setNotice(result.message);
    } catch (reason) { setError(getMessage(reason)); } finally { setBusy(false); }
  }

  async function submitRegistration(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError('');
    const form = new FormData(event.currentTarget);
    if (form.get('password') !== form.get('confirm_password')) { setError('Passwords do not match'); setBusy(false); return; }
    try {
      await request('/auth/register', { method: 'POST', body: JSON.stringify({
        email: form.get('email'), password: form.get('password'), full_name: form.get('full_name'),
        phone: form.get('phone') || null, role: registerRole,
      })});
      setScreen('login'); setLoginRole(registerRole); setNotice('Account created. Sign in to continue.');
    } catch (reason) { setError(getMessage(reason)); } finally { setBusy(false); }
  }

  async function submitBootstrapAdmin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError('');
    const form = new FormData(event.currentTarget);
    try {
      await request('/auth/bootstrap-admin', { method: 'POST', body: JSON.stringify({
        email: form.get('email'), password: form.get('password'), full_name: form.get('full_name'),
        bootstrap_password: form.get('bootstrap_password'),
      })});
      setScreen('login'); setLoginRole('admin'); setNotice('Administrator created. Sign in to continue.');
    } catch (reason) { setError(getMessage(reason)); } finally { setBusy(false); }
  }

  async function submitApplication(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError(''); setNotice('');
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    try {
      await request('/ric_applications', { method: 'POST', body: JSON.stringify({
        full_name: form.get('full_name'), identity_number: form.get('identity_number'),
        date_of_birth: form.get('date_of_birth') || null, permanent_address: form.get('permanent_address') || null,
        household_address: form.get('household_address'), area_id: Number(form.get('area_id')),
        members: JSON.parse(String(form.get('members') || '[]')),
      })});
      setNotice('Your RIC application was submitted and is now visible in My applications.');
      formElement.reset(); await loadTenantApplications(); setWorkspace('applications');
    } catch (reason) { setError(getMessage(reason)); } finally { setBusy(false); }
  }
  async function submitRelocation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError(''); setNotice('');
    const form = new FormData(event.currentTarget);
    try {
      await request('/ric_applications/relocate', { method: 'POST', body: JSON.stringify({
        area_id: Number(form.get('area_id')), household_address: form.get('household_address'),
        permanent_address: form.get('permanent_address') || null,
      })});
      setNotice('Relocation submitted. Your previous RIC record remains preserved while the new area reviews this update.');
      await loadTenantApplications(); setWorkspace('applications');
    } catch (reason) { setError(getMessage(reason)); } finally { setBusy(false); }
  }

  async function reviewApplication(id: string, action: 'forward' | 'reject' | 'approve' | 'return_to_local', note?: string) {
    setBusy(true); setError(''); setNotice('');
    try {
      await request(`/government/review/${id}`, { method: 'POST', body: JSON.stringify({ action, note: note || null }) });
      setNotice(action === 'approve' ? 'Application approved. Issue the RIC certificate from the queue.' : action === 'return_to_local' ? 'Application returned to the local office with your review notes.' : action === 'forward' ? 'Application forwarded to central review.' : 'Application rejected with the recorded reason.');
      await loadQueue();
    } catch (reason) { setError(getMessage(reason)); } finally { setBusy(false); }
  }

  async function issueCertificate(id: string) {
    setBusy(true); setError(''); setNotice('');
    try {
      const result = await request<{ ric_number: string }>(`/certificates/issue/${id}`, { method: 'POST' });
      setNotice(`Certificate ${result.ric_number} issued and linked to the tenant's household. PDF generation is queued if needed.`);
      await Promise.all([loadQueue(), loadCertificates()]);
    } catch (reason) { setError(getMessage(reason)); } finally { setBusy(false); }
  }

  function logout() { localStorage.removeItem('access_token'); setUser(null); setScreen('home'); setError(''); setNotice(''); }
  const pendingCount = user?.role === 'government' ? applications.length : applications.filter((app) => app.status.startsWith('pending')).length;

  if (user) {
    return <Workspace user={user} workspace={workspace} setWorkspace={setWorkspace} applications={applications}
      selectedApp={selectedApp} certificates={certificates} areas={areas} pendingCount={pendingCount} busy={busy} error={error} notice={notice}
      properties={properties} listings={listings} availableListings={availableListings} viewings={viewings} landlordViewings={landlordViewings} tenancies={tenancies} rentalOffers={rentalOffers} landlordRentalOffers={landlordRentalOffers} rentOverview={rentOverview} landlordRent={landlordRent}
      onLogout={logout} onApply={submitApplication} onRefresh={user.role === 'tenant' ? loadTenantApplications : loadQueue}
      onSelectApplication={(id) => setSelectedApp(id ? applications.find((a) => a.id === id) || null : null)} onReview={reviewApplication} onIssue={issueCertificate} onDownloadCertificate={downloadCertificate} onCreateOfficial={async (payload) => {
        setBusy(true); setError(''); setNotice('');
        try { await request('/admin/officials', { method: 'POST', body: JSON.stringify(payload) }); setNotice('Government profile created. The official can sign in with the issued credentials.'); }
        catch (reason) { setError(getMessage(reason)); } finally { setBusy(false); }
      }} onCreateAdmin={async (payload) => {
        setBusy(true); setError(''); setNotice('');
        try { await request('/admin/admins', { method: 'POST', body: JSON.stringify(payload) }); setNotice('Administrator account created successfully.'); }
        catch (reason) { setError(getMessage(reason)); } finally { setBusy(false); }
      }} onCreateProperty={async (payload) => {
        setBusy(true); setError(''); setNotice('');
        try { await request('/properties', { method: 'POST', body: JSON.stringify(payload) }); setNotice('Property saved. Add a listing when you are ready to publish it.'); await loadLandlordProperties(); setWorkspace('properties'); }
        catch (reason) { setError(getMessage(reason)); } finally { setBusy(false); }
      }} onCreateListing={async (propertyId, payload, unitId) => {
        setBusy(true); setError(''); setNotice('');
        try {
          const path = unitId ? `/properties/units/${unitId}/listing` : `/properties/${propertyId}/listing`;
          await request(path, { method: 'POST', body: JSON.stringify({ ...payload, property_id: propertyId }) });
          setNotice(unitId ? 'Apartment listing created successfully.' : 'Building listing created successfully.');
          await loadLandlordListings(); setWorkspace('listings');
        }
        catch (reason) { setError(getMessage(reason)); } finally { setBusy(false); }
      }} onRequestViewing={submitViewing} onEndTenancy={endTenancy} onRelocate={submitRelocation} onRefreshListings={loadLandlordListings} onUpdateViewing={updateViewingStatus} onCreateRentalOffer={createRentalOffer} onRefreshTenantRentalOffers={loadTenantRentalOffers} onRespondToRentalOffer={respondToRentalOffer} onRefreshLandlordRentalOffers={loadLandlordRentalOffers} onTenantRespondToRentalOffer={tenantRespondToRentalOffer} onPayRent={payRent} onConfirmRentPayment={confirmRentPayment} onGenerateRent={generateRent} onRefreshRent={user.role === 'landlord' ? loadLandlordRent : loadRentOverview} />; 
  }

  if (screen === 'home') return <Landing onLogin={(role) => { setLoginRole(role); setScreen('login'); }} onRegister={() => { setRegisterRole('tenant'); setScreen('register'); }} />;
  return <AuthScreen screen={screen} loginRole={loginRole} registerRole={registerRole} resetToken={resetToken} busy={busy} error={error} notice={notice}
    onBack={() => { setError(''); setScreen('home'); }} onLogin={submitLogin} onRegister={submitRegistration}
    onRegisterRole={setRegisterRole} onBootstrap={submitBootstrapAdmin} onDemoPasswordReset={submitDemoPasswordReset} onPasswordReset={submitPasswordReset} onSwitch={(next) => { setError(''); setNotice(''); setScreen(next); }} />;
}

function Landing({ onLogin, onRegister }: { onLogin: (role: Role) => void; onRegister: () => void }) {
  const [statistics, setStatistics] = useState<{ registered_users: number; properties: number; active_tenancies: number }>();
  useEffect(() => {
    const controller = new AbortController();
    request<{ registered_users: number; properties: number; active_tenancies: number }>('/public/statistics', { signal: controller.signal })
      .then(setStatistics).catch(() => {});
    return () => controller.abort();
  }, []);
  return <div className="public-site" id="top"><div className="landing-atmosphere" aria-hidden="true"><span /><span /></div>
    <a className="skip-link" href="#main-content">Skip to content</a><header className="public-header"><Brand /><nav className="public-nav" aria-label="Main navigation"><a href="#platform-features">The platform</a><a href="#engineer">The engineer</a></nav><div className="button-row">
      <details className="signin-menu"><summary>Sign in <span aria-hidden="true">⌄</span></summary><div>{(['tenant', 'landlord', 'government', 'admin'] as Role[]).map(role => <button key={role} onClick={() => onLogin(role)}><Icon name={role === 'tenant' ? 'user' : role === 'landlord' ? 'building' : 'shield'} />{role === 'government' ? 'Government official' : role === 'admin' ? 'Administrator' : formatLabel(role)}</button>)}</div></details>
      <button className="primary" onClick={onRegister}>Create account</button>
    </div></header>
    <main className="public-content" id="main-content">
      <section className="public-hero">
        <div className="hero-copy"><span className="hero-kicker"><span /> A clearer way to rent</span><h1>Your next home.<br /><em>A trusted record.</em></h1>
          <p>Apply for a household Rental Identity Certificate, find a home, and keep a record of rent payments in one place.</p>
          <div className="hero-actions"><button className="primary" onClick={onRegister}>Start your rental journey <span aria-hidden="true">→</span></button><a href="#platform-features">Explore the platform <span aria-hidden="true">↗</span></a></div><div className="hero-note"><Icon name="shield" /> Identity, tenancy, and rental history. Connected.</div>
        </div>
        <div className="public-hero-card">
          <div className="identity-card-heading"><span className="identity-emblem"><Icon name="award" /></span><span>THE FOUNDATION OF YOUR JOURNEY<small>Rental Identity Certificate</small></span></div>
          <h2>One identity.<br />A connected rental history.</h2>
          <p>Start with your household details. Follow each review, then keep your verified certificate close.</p>
          <ol className="identity-steps">{[['01', 'Apply', 'Your address and household'], ['02', 'Review', 'Local verification and central approval'], ['03', 'Receive', 'Download your issued certificate']].map(([number, title, detail]) => <li key={number}><span>{number}</span><div><strong>{title}</strong><small>{detail}</small></div><Icon name={number === '03' ? 'award' : 'check'} /></li>)}</ol>
          <div className="identity-card-footer"><Icon name="files" /> Your records, together in one workspace</div>
        </div>
      </section>
      {statistics && <section className="community-statistics" aria-label="Platform statistics">{[['users', statistics.registered_users, 'Registered active accounts'], ['building', statistics.properties, 'Registered properties'], ['key', statistics.active_tenancies, 'Active tenancies']].map(([icon, value, label]) => <div key={label}><Icon name={String(icon)} /><strong>{Number(value).toLocaleString()}</strong><span>{label}</span></div>)}</section>}
      <section className="landing-features" id="platform-features"><div><span className="eyebrow">FROM FINDING A HOME TO MOVING OUT</span><h2>A clearer rental journey.</h2><p>Your documents, your home, and the conversations that matter. Together in one workspace.</p></div>{[['key', 'A home with a history', 'Arrange viewings, make offers, and keep your lease and inspection records together.'], ['card', 'Clarity on every payment', 'Track monthly rent, view statements, and review deposit deductions with evidence.'], ['shield', 'Records both parties can trust', 'Acknowledge inspections, share selected history, and follow a dispute through review.'], ['layers', 'Care beyond move-in', 'Report maintenance, follow repair updates, and keep the details with your tenancy.']].map(([icon, title, description]) => <article key={title}><span className="feature-icon"><Icon name={icon} /></span><h3>{title}</h3><p>{description}</p></article>)}</section>
      <EngineerProfile photo={engineerPhoto} />
      <section className="landing-closing"><div><span className="eyebrow">YOUR NEXT CHAPTER</span><h2>Bring your rental records together.</h2><p>Create a tenant or landlord account and start building your rental history.</p></div><button className="primary" onClick={onRegister}>Create your account <span aria-hidden="true">→</span></button></section>
    </main>
    <footer className="site-footer"><div className="footer-main"><div className="footer-brand"><img className="footer-logo" src={logoImage} alt="CTRx" /><div className="footer-identity"><strong>Central Tenant Records</strong><span>A trusted record for verified rentals and tenancy history.</span></div></div><div><h3>Explore CTRx</h3><a href="#platform-features">What we offer</a><a href="#engineer">Meet the engineer</a><button onClick={onRegister}>Create an account</button></div><div><h3>Inside your workspace</h3><p>Rental identity certificates<br />Tenancy and payment records<br />Inspections and maintenance<br />Deposit settlement and disputes</p></div></div><div className="footer-bottom"><span>© {new Date().getFullYear()} Central Tenant Records</span><a href="#top">Back to top ↑</a></div></footer>
  </div>;
}

function navigationGroup(key: string) {
  if (['overview', 'inbox'].includes(key)) return '1 Workspace';
  if (['browse', 'properties', 'units', 'listings', 'viewings', 'offers'].includes(key)) return '2 Homes & discovery';
  if (['rent', 'care', 'tenancies', 'leases', 'statements'].includes(key)) return '3 My rental';
  if (['apply', 'applications', 'relocate', 'certificates', 'queue'].includes(key)) return '4 Identity & certificates';
  return '5 Resources';
}

function Workspace(props: {
  user: User; workspace: string; setWorkspace: (value: string) => void; applications: Application[]; selectedApp: Application | null; certificates: Certificate[];
  areas: Area[]; properties: Property[]; listings: Listing[]; availableListings: AvailableListing[]; viewings: Viewing[]; landlordViewings: Viewing[]; tenancies: Tenancy[]; rentalOffers: RentalOffer[]; landlordRentalOffers: RentalOffer[]; rentOverview: RentOverview | null; landlordRent: LandlordRentRow[]; pendingCount: number; busy: boolean; error: string; notice: string; onLogout: () => void;
  onApply: (event: FormEvent<HTMLFormElement>) => void; onRefresh: () => void; onSelectApplication: (id: string | null) => void; onReview: (id: string, action: 'forward' | 'reject' | 'approve' | 'return_to_local', note?: string) => void;
  onIssue: (id: string) => void; onDownloadCertificate: (id: string) => void; onCreateOfficial: (payload: { email: string; password: string; full_name: string; level: string; area_id?: number }) => void;
  onCreateAdmin: (payload: { email: string; password: string; full_name: string }) => void;
  onCreateProperty: (payload: Omit<Property, 'id' | 'landlord_id' | 'created_at' | 'updated_at'>) => void;
  onCreateListing: (propertyId: string, payload: { property_id: string; status: string; title?: string; description?: string }, unitId?: string) => void;
  onRefreshListings: () => void;
  onRequestViewing: (listingId: string, proposedTime: string) => void;
  onEndTenancy: (tenancyId: string) => void;
  onRelocate: (event: FormEvent<HTMLFormElement>) => void;
  onUpdateViewing: (id: string, status: 'confirmed' | 'declined' | 'countered', alternativeTime?: string) => void;
  onCreateRentalOffer: (listingId: string, proposedRent: number, moveInDate: string, message?: string) => void;
  onRefreshTenantRentalOffers: () => void;
  onRespondToRentalOffer: (offerId: string, action: 'accept' | 'reject' | 'counter', counterRent?: number, responseMessage?: string) => void;
  onRefreshLandlordRentalOffers: () => void;
  onTenantRespondToRentalOffer: (offerId: string, action: 'accept' | 'counter' | 'withdraw', counterRent?: number, responseMessage?: string) => void;
  onPayRent: (invoiceId: string, report: RentPaymentReport) => void;
  onConfirmRentPayment: (invoiceId: string) => void;
  onGenerateRent: (tenancyId: string) => void;
  onRefreshRent: () => void;
}) {
  const { user, workspace, setWorkspace, onSelectApplication, selectedApp } = props;
  const isGov = user.role === 'government'; const isAdmin = user.role === 'admin';
  const [notificationCase, setNotificationCase] = useState<string>();
  const [appearanceError, setAppearanceError] = useState('');
  const [accountProfile, setAccountProfile] = useState<AccountProfile>();
  useEffect(() => {
    let active = true;
    setAccountProfile(undefined);
    setAppearanceError('');
    request<AccountProfile>('/profile').then(profile => {
      if (active) setAccountProfile(profile);
    }).catch(reason => {
      if (active) setAppearanceError(reason instanceof Error ? reason.message : 'Profile could not be loaded');
    });
    return () => { active = false; };
  }, [user.id]);
  const appearance = accountProfile?.appearance || 'light';
  const theme = accountProfile?.theme || 'teal';
  useEffect(() => {
    document.documentElement.dataset.appearance = appearance;
    document.documentElement.dataset.theme = theme;
    return () => {
      delete document.documentElement.dataset.appearance;
      delete document.documentElement.dataset.theme;
    };
  }, [appearance, theme]);
  const displayName = accountProfile?.display_name || user.email.split('@')[0];
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    if (menuOpen) document.getElementById("workspace-menu-close")?.focus();
  }, [menuOpen]);

  function closeNavigation() {
    setMenuOpen(false);
    document.getElementById("workspace-menu-toggle")?.focus();
  }
  const [inbox, setInbox] = useState<Inbox>({ items: [], unread: 0 });
  const [inboxError, setInboxError] = useState('');
  async function refreshInbox() {
    try {
      setInbox(await request<Inbox>('/workspace/notifications'));
      setInboxError('');
    } catch (error) {
      setInboxError(error instanceof Error ? error.message : 'Inbox unavailable');
    }
  }
  useEffect(() => {
    void refreshInbox();
    const timer = window.setInterval(refreshInbox, 30_000);
    return () => window.clearInterval(timer);
  }, [user.email]);
  const nav: string[][] = isGov ? [['overview', 'Overview', 'home'], ['queue', 'Review queue', 'inbox'], ['certificates', 'Issued certificates', 'award']] : isAdmin ? [['overview', 'Overview', 'home'], ['official', 'Create government profile', 'shield'], ['admins', 'Create administrator', 'users']] : user.role === 'landlord' ? [['overview', 'Overview', 'home'], ['properties', 'My buildings', 'building'], ['units', 'Apartments', 'layers'], ['listings', 'Listings', 'tag'], ['viewings', 'Viewing requests', 'calendar'], ['offers', 'Rental offers', 'file-text'], ['rent', 'Rent', 'card']] : [['overview', 'Overview', 'home'], ['apply', 'New application', 'file-plus'], ['applications', 'My applications', 'files'], ['relocate', 'Update location', 'map-pin'], ['browse', 'Find a home', 'search'], ['viewings', 'Viewing requests', 'calendar'], ['tenancies', 'My tenancies', 'key'], ['offers', 'My offers', 'file-text'], ['rent', 'Rent', 'card'], ['certificates', 'My certificates', 'award']];
  const rentalParty = user.role === 'tenant' || user.role === 'landlord';
  if (rentalParty) nav.push(['care', 'Tenancy care', 'key'], ['leases', 'Lease agreements', 'files'], ['statements', 'Rent statements', 'card']);
  nav.push(['cases', 'Disputes', 'shield'], ['tools', 'Tools', 'layers'], ['profile', 'Profile settings', 'gear']);
  nav.splice(1, 0, ['inbox', 'Inbox', 'inbox']);
  nav.push(['support', 'Support', 'message-circle']);
  if (rentalParty) nav.push(['trust', 'Records & privacy', 'shield'], ['sharing', 'Shared history', 'users']);
  if (user.role === 'tenant') nav.push(['reliability', 'Reliability', 'shield']);
  return <div className="app-shell" onKeyDown={event => { if (menuOpen && event.key === "Escape") closeNavigation(); }}><aside id="workspace-navigation" className={menuOpen ? "sidebar open" : "sidebar"}>{menuOpen && <button id="workspace-menu-close" className="mobile-nav-close" onClick={closeNavigation}>Close menu</button>}<Brand /><div className="workspace-label">{isAdmin ? 'Administrator' : isGov ? 'Government workspace' : user.role === 'landlord' ? 'Landlord workspace' : 'Tenant workspace'}</div><nav aria-label="Workspace">{Array.from(new Set(nav.filter(([key]) => key !== 'profile').map(([key]) => navigationGroup(key)))).sort().map(group => <details className="navigation-section" key={group + workspace} open={group === '1 Workspace' || nav.some(([key]) => key === workspace && navigationGroup(key) === group)}>
      <summary>{group.slice(2)}<span aria-hidden="true">⌄</span></summary>
      {nav.filter(([key]) => key !== 'profile' && navigationGroup(key) === group).map(([key, label, icon]) => <button key={key} className={`nav-item ${workspace === key ? 'active' : ''}`} aria-current={workspace === key ? 'page' : undefined} onClick={() => { setWorkspace(key); setNotificationCase(undefined); if (menuOpen) closeNavigation(); if (key === 'inbox') void refreshInbox(); }}><Icon name={icon} /><span className="nav-label">{label}</span>{key === 'queue' && props.pendingCount > 0 && <b className="nav-count">{props.pendingCount}</b>}{key === 'inbox' && inbox.unread > 0 && <b className="nav-count">{inbox.unread}</b>}</button>)}
    </details>)}</nav><div className="sidebar-footer"><div className="profile-chip"><span className="profile-avatar">{accountProfile?.photo_url ? <img src={accountProfile.photo_url} alt="" /> : displayName.slice(0, 1).toUpperCase()}</span><div className="profile-meta"><strong>{displayName}</strong><small>{user.email}</small></div></div><button className="logout-link" onClick={props.onLogout}><Icon name="log-out" /> Log out</button></div></aside>
    {menuOpen && <button className="navigation-backdrop" aria-label="Close navigation" tabIndex={-1} onClick={closeNavigation} />}
    <main className="content" data-workspace={workspace}><button id="workspace-menu-toggle" className="secondary mobile-nav-toggle" aria-expanded={menuOpen} aria-controls="workspace-navigation" onClick={() => setMenuOpen(!menuOpen)}><Icon name="menu" /> Menu</button><header className="topbar"><div><span className="eyebrow">{isAdmin ? 'Platform controls' : isGov ? 'Authorized official workspace' : 'Your secure workspace'}</span><h1>{workspace === 'overview' ? `Welcome, ${displayName}.` : nav.find(([key]) => key === workspace)?.[1]}</h1></div><button className="secondary" disabled={!accountProfile} aria-pressed={appearance === 'dark'} onClick={async () => {
      setAppearanceError('');
      try {
        setAccountProfile(await request<AccountProfile>('/profile/appearance', { method: 'PUT', body: JSON.stringify({ appearance: appearance === 'dark' ? 'light' : 'dark', theme }) }));
      } catch (reason) { setAppearanceError(reason instanceof Error ? reason.message : 'Could not change appearance'); }
    }}>{appearance === 'dark' ? 'Light mode' : 'Dark mode'}</button><button className="secondary inbox-shortcut" onClick={() => setWorkspace('inbox')} aria-label={`Open inbox, ${inbox.unread} unread notifications`}><Icon name="inbox" />{inbox.unread > 0 && <span>{inbox.unread}</span>}</button><button className="account-menu secondary" onClick={() => setWorkspace('profile')} aria-label="Open profile settings"><span className="profile-avatar">{accountProfile?.photo_url ? <img src={accountProfile.photo_url} alt="" /> : displayName.slice(0, 1).toUpperCase()}</span><span>{displayName}<small>Profile & settings</small></span><Icon name="gear" /></button></header>{appearanceError && <p className="alert error" role="alert">{appearanceError}</p>}{props.error && <div className="alert error" role="alert">{props.error}</div>}{props.notice && <div className="alert success" role="status">{props.notice}</div>}
      {workspace === 'overview' && <Overview user={user} applications={props.applications} certificates={props.certificates} pendingCount={props.pendingCount} rentOverview={props.rentOverview} setWorkspace={setWorkspace} unread={inbox.unread} properties={props.properties.length} listings={props.listings.filter(item => item.status === "available").length} onRefresh={props.onRefresh} />}
      {workspace === 'inbox' && <InboxPanel inbox={inbox} error={inboxError} refresh={refreshInbox} open={(item) => {
        setWorkspace(item.destination);
        if (item.destination === 'applications') onSelectApplication(item.record_id);
        if (item.destination === 'cases') setNotificationCase(item.record_id);
      }} />}
      {workspace === 'support' && <SupportCenter request={request} staff={user.role === 'admin' || user.role === 'government'} />}
      {workspace === 'trust' && rentalParty && <TrustHistory request={request} certificates={user.role === 'tenant' ? props.certificates : []} tenant={user.role === 'tenant'} landlord={user.role === 'landlord'} onDownload={props.onDownloadCertificate} />}
      {workspace === 'care' && rentalParty && <TenancyCare role={user.role} request={request} openCase={id => { setNotificationCase(id); setWorkspace('cases'); }} />}
      {workspace === 'tools' && <RentalTools />}
      {['leases', 'statements', 'cases'].includes(workspace) && <RentalRecords view={workspace} setView={setWorkspace} role={user.role} request={request} caseId={notificationCase} />}
      {workspace === 'profile' && <ProfileSettings user={user} onSaved={setAccountProfile} />}
      {workspace === 'sharing' && <SharingPanel tenant={user.role === 'tenant'} tenancies={props.tenancies} />}
      {workspace === 'reliability' && <ReliabilityPanel />}
      {workspace === 'apply' && <ApplicationForm areas={props.areas} busy={props.busy} onSubmit={props.onApply} />}
      {workspace === 'relocate' && <RelocationForm areas={props.areas} busy={props.busy} onSubmit={props.onRelocate} />}
      {workspace === 'applications' && (selectedApp ? <ApplicationDetail application={selectedApp} onBack={() => onSelectApplication(null)} /> : <ApplicationList applications={props.applications} onRefresh={props.onRefresh} onSelect={onSelectApplication} />)}
      {workspace === 'queue' && <ReviewQueue applications={props.applications} busy={props.busy} onRefresh={props.onRefresh} onReview={props.onReview} onIssue={props.onIssue} />}
      {workspace === 'certificates' && <CertificateList certificates={props.certificates} onDownload={props.onDownloadCertificate} tenant={user.role === 'tenant'} />}
      {workspace === 'properties' && <PropertyManager properties={props.properties} areas={props.areas} busy={props.busy} onCreate={props.onCreateProperty} />}
      {workspace === 'units' && <UnitManager properties={props.properties} />}
      {workspace === 'listings' && <ListingManager onSaved={props.onRefreshListings} properties={props.properties} listings={props.listings} busy={props.busy} onCreate={props.onCreateListing} />}
      {workspace === 'browse' && <PropertyBrowser areas={props.areas} listings={props.availableListings} busy={props.busy} onRequest={props.onRequestViewing} />}
      {workspace === 'viewings' && user.role === 'tenant' && <ViewingList viewings={props.viewings} busy={props.busy} onUpdate={props.onUpdateViewing} />}
      {workspace === 'viewings' && user.role === 'landlord' && <LandlordViewingList viewings={props.landlordViewings} busy={props.busy} onUpdate={props.onUpdateViewing} />}
      {workspace === 'tenancies' && <TenancyList tenancies={props.tenancies} busy={props.busy} onEnd={props.onEndTenancy} />}
      {workspace === 'offers' && user.role === 'tenant' && <TenantRentalOfferList offers={props.rentalOffers} listings={props.availableListings} busy={props.busy} onCreate={props.onCreateRentalOffer} onRefresh={props.onRefreshTenantRentalOffers} onTenantRespond={props.onTenantRespondToRentalOffer} />}
      {workspace === 'offers' && user.role === 'landlord' && <LandlordRentalOfferList offers={props.landlordRentalOffers} busy={props.busy} onRespond={props.onRespondToRentalOffer} onRefresh={props.onRefreshLandlordRentalOffers} />}
      {workspace === 'rent' && user.role === 'tenant' && <TenantRentPanel overview={props.rentOverview} busy={props.busy} onPay={props.onPayRent} onRefresh={props.onRefreshRent} />}
      {workspace === 'rent' && user.role === 'landlord' && <LandlordRentPanel rows={props.landlordRent} busy={props.busy} onGenerate={props.onGenerateRent} onConfirm={props.onConfirmRentPayment} onRefresh={props.onRefreshRent} />}
      {workspace === 'official' && <OfficialForm areas={props.areas} busy={props.busy} onSubmit={props.onCreateOfficial} />}
      {workspace === 'admins' && <AdminForm busy={props.busy} onSubmit={props.onCreateAdmin} />}
      <footer>CTRx · Central Tenant Records <span>Audit-ready · Role-based access</span></footer></main></div>;
}

function Overview({ user, applications, certificates, pendingCount, rentOverview, setWorkspace, unread, properties, listings, onRefresh }: {
  user: User; applications: Application[]; certificates: Certificate[]; pendingCount: number;
  rentOverview: RentOverview | null; setWorkspace: (value: string) => void;
  unread: number; properties: number; listings: number; onRefresh: () => void;
}) {
  if (user.role === 'government') return <GovernmentDashboard applications={applications} certificates={certificates} unread={unread} setWorkspace={setWorkspace} onRefresh={onRefresh} />;
  const links = {
    tenant: [
      { key: 'applications', icon: 'files', count: applications.length, label: 'RIC applications' },
      { key: 'certificates', icon: 'award', count: certificates.length, label: 'Certificates' },
    ],
    landlord: [
      { key: 'properties', icon: 'building', count: properties, label: 'Buildings' },
      { key: 'listings', icon: 'tag', count: listings, label: 'Published listings' },
    ],
    government: [
      { key: 'queue', icon: 'files', count: pendingCount, label: 'Applications to review' },
      { key: 'certificates', icon: 'award', count: certificates.length, label: 'Issued certificates' },
    ],
    admin: [
      { key: 'official', icon: 'shield', count: null, label: 'Create government profile' },
      { key: 'admins', icon: 'users', count: null, label: 'Create administrator' },
    ],
  };
  const rentalParty = user.role === 'tenant' || user.role === 'landlord';
  const actions = rentalParty ? [
    { key: 'care', icon: 'key', title: 'Tenancy care', description: 'Inspections, repair updates, and deposit settlement.' },
    { key: 'leases', icon: 'files', title: 'Lease agreements', description: 'Review your tenancy terms and acknowledgements.' },
    { key: 'tools', icon: 'layers', title: 'Rental planning tools', description: 'Plan costs, organize your move, or draft a repair message.' },
  ] : [
    { key: 'official', icon: 'shield', title: 'Manage official access', description: 'Create accounts for government reviewers.' },
    { key: 'cases', icon: 'file-text', title: 'Follow rental disputes', description: 'Review case details, evidence, and updates.' },
    { key: 'tools', icon: 'layers', title: 'Rental planning tools', description: 'Practical planning tools in one place.' },
  ];
  return <><section className="overview-focus"><div><h2>{unread ? 'Unread notifications' : user.role === 'tenant' ? 'Your rental records' : user.role === 'landlord' ? 'Your rental portfolio' : 'Platform administration'}</h2><p>{unread ? 'Your inbox brings together changes to your records and requests.' : 'Choose a task below or explore your records from the navigation.'}</p></div><button className="primary" onClick={() => setWorkspace('inbox')}><Icon name="inbox" /> Open inbox{unread > 0 && <span> · {unread}</span>}</button></section>
  <section className="dashboard-grid" aria-label="Workspace shortcuts">
    {[...links[user.role], { key: 'inbox', icon: 'inbox', count: unread, label: 'Unread notifications' }].map(link =>
      <button className="dashboard-card" key={link.key} onClick={() => setWorkspace(link.key)}>
        <span className="stat-icon"><Icon name={link.icon} /></span>
        <span>{link.count !== null && <strong>{link.count}</strong>}{link.label}</span>
        <span className="dashboard-arrow" aria-hidden="true">→</span>
      </button>)}
  </section>

  {user.role === 'tenant' && applications.length === 0 && <section className="panel dashboard-start">
    <div><h2>Apply for a Rental Identity Certificate</h2><p>Add your address and household members to start local review.</p></div>
    <button className="primary" onClick={() => setWorkspace('apply')}>Start an application</button>
  </section>}
    {user.role === 'tenant' && rentOverview?.active && <section className="panel"><div className="panel-heading"><div><span className="step">CURRENT HOME</span><h2>{rentOverview.property_address}</h2><p>{formatLabel(rentOverview.property_type || 'Home')} · ৳{Number(rentOverview.monthly_rent || 0).toLocaleString()}/month · Rent due day {rentOverview.rent_due_day ?? 1}</p></div><button className="text-button" onClick={() => setWorkspace('rent')}>Manage rent →</button></div><div className="stats" style={{ margin: 0 }}><Stat icon="building" title={rentOverview.paid_current_period ? 'Paid' : 'Due'} text={`This month: ${rentOverview.period_month ? new Date(rentOverview.period_month).toLocaleDateString(undefined, { month: 'long', year: 'numeric' }) : 'current'}`} /><Stat icon="card" title={`৳${Number(rentOverview.total_paid || 0).toLocaleString()}`} text="Total rent paid" /><Stat icon="check" title={`৳${Number(rentOverview.outstanding || 0).toLocaleString()}`} text="Outstanding this month" /></div></section>}
    {user.role === 'tenant' && applications.length > 0 && <section className="panel"><div className="panel-heading"><div><span className="step">LATEST APPLICATION</span><h2>Track your progress</h2></div><button className="text-button" onClick={() => setWorkspace('applications')}>View all →</button></div><ApplicationTimeline application={applications[0]} /></section>}
  <section className="overview-actions" aria-label="Recommended workspace actions">{actions.map(action => <button key={action.key} onClick={() => setWorkspace(action.key)}><span className="stat-icon"><Icon name={action.icon} /></span><strong>{action.title}</strong><span>{action.description}</span><span className="action-link">Open workspace →</span></button>)}</section></>;
}

function GovernmentDashboard({ applications, certificates, unread, setWorkspace, onRefresh }: {
  applications: Application[]; certificates: Certificate[]; unread: number;
  setWorkspace: (value: string) => void; onRefresh: () => void;
}) {
  const { data, error, busy, reload } = useWorkspaceResource<GovernmentOverviewData>('/government/overview');
  const official = data?.official;
  const local = official?.level === 'local';
  const statusCounts = data?.status_counts || {};
  const distribution = Object.entries(statusCounts).filter(([, count]) => count > 0);
  const totalApplications = distribution.reduce((total, [, count]) => total + count, 0);
  const [queueSearch, setQueueSearch] = useState("");
  const pendingReview = data?.pending_review_count ?? applications.filter(app => app.status === (local ? 'pending_local' : 'pending_central')).length;
  const readyToIssue = data?.ready_to_issue_count ?? applications.filter(app => app.status === 'approved').length;
  const queue = [...applications].sort((left, right) => new Date(left.submitted_at).getTime() - new Date(right.submitted_at).getTime());
  const query = queueSearch.trim().toLowerCase();
  const matchingQueue = queue.filter(application =>
    [application.applicant_name, application.area_name, formatStatus(application.status)]
      .some(value => value?.toLowerCase().includes(query)),
  );
  const scope = local
    ? [official?.area_name, official?.district].filter(Boolean).join(', ')
    : official ? 'Nationwide authority' : 'Official workspace';
  function refresh() { void reload().catch(() => undefined); onRefresh(); }

  return <div className="government-dashboard">
    <section className="government-welcome">
      <div className="government-welcome-copy">
        <span className="eyebrow">GOVERNMENT SERVICES · RIC OPERATIONS</span>
        <h2>{official?.full_name ? `Welcome, ${official.full_name}.` : 'Your official workspace'}</h2>
        <p>{official?.designation || (local ? 'Local verification officer' : 'Rental Identity Certificate administration')}</p>
        <div className="government-scope"><Icon name="map-pin" /><span>{scope || 'Loading official assignment…'}</span><span className="government-level">{official ? `${official.level} official` : 'Secure access'}</span></div>
      </div>
      <div className="government-welcome-actions">
        <button className="secondary" onClick={refresh} disabled={busy}><Icon name="radar" /> {busy ? 'Refreshing…' : 'Refresh overview'}</button>
        <button className="primary" onClick={() => setWorkspace(applications.length ? 'queue' : 'inbox')}><Icon name="inbox" /> {applications.length ? 'Open review work' : 'Open inbox'}{unread > 0 && <span> · {unread}</span>}</button>
      </div>
    </section>
    {error && <div className="alert error" role="alert">Government overview unavailable: {error}</div>}

    <section className="government-metrics" aria-label="Government workload summary">
      <button className="government-metric metric-review" onClick={() => setWorkspace('queue')}>
        <span className="government-metric-icon"><Icon name="inbox" /></span><span className="government-metric-label">Awaiting your review</span><strong>{pendingReview}</strong><small>{local ? 'Local verification' : 'Central verification'}</small>
      </button>
      {local ? <button className="government-metric metric-forwarded" onClick={() => setWorkspace('queue')}>
        <span className="government-metric-icon"><Icon name="files" /></span><span className="government-metric-label">Forwarded to central</span><strong>{statusCounts.pending_central ?? 0}</strong><small>Applications from your assigned area</small>
      </button> : <button className="government-metric metric-issuance" onClick={() => setWorkspace('queue')}>
        <span className="government-metric-icon"><Icon name="award" /></span><span className="government-metric-label">Ready for certificate</span><strong>{readyToIssue}</strong><small>Approved and awaiting issuance</small>
      </button>}
      <button className="government-metric metric-issued" onClick={() => setWorkspace('certificates')}>
        <span className="government-metric-icon"><Icon name="check" /></span><span className="government-metric-label">Certificates issued</span><strong>{data?.issued_certificate_count ?? certificates.length}</strong><small>{local ? 'Within your assigned area' : 'Across the country'}</small>
      </button>
    </section>

    <div className="government-review-layout">
    <section className="government-queue-preview panel">
      <div className="panel-heading"><div><span className="step">NEXT IN YOUR WORKLIST</span><h2>Applications requiring action</h2><p>Items appear here in submission order so older applications stay visible.</p></div><span className="panel-number">{queue.length}</span></div>
      {queue.length > 0 && <label className="government-queue-search">Search worklist<input type="search" value={queueSearch} onChange={event => setQueueSearch(event.target.value)} placeholder="Applicant, area, or status" /></label>}
      {queue.length === 0 ? <Empty title="Your queue is clear" text={local ? 'New applications for your assigned area will appear here.' : 'Applications forwarded for central review and approved cases awaiting issuance will appear here.'} /> : matchingQueue.length === 0 ? <Empty title="No matching applications" text="Try another applicant, area, or status." /> : <div className="record-list">{matchingQueue.slice(0, 5).map(application => <div className="record-row" key={application.id}>
        <div className="government-applicant"><strong>{application.applicant_name}</strong><small>{application.area_name || 'Area not available'} · Submitted {new Date(application.submitted_at).toLocaleDateString()}</small></div>
        <div className="government-row-actions"><Status status={application.status} /><button className="secondary small-button" onClick={() => setWorkspace('queue')}>{application.status === 'approved' ? 'Issue certificate' : 'Review application'} <span aria-hidden="true">→</span></button></div>
      </div>)}{matchingQueue.length > 5 && <button className="text-button government-view-all" onClick={() => setWorkspace('queue')}>Open the full review queue →</button>}</div>}
    </section>

    <section className="government-distribution panel" aria-busy={busy}>
      <div className="panel-heading"><div><h2>Application status</h2><p>{data ? `${totalApplications.toLocaleString()} applications in scope` : "Applications in your assigned scope"}</p></div></div>
      {data && distribution.length > 0 ? <ul>{distribution.map(([status, count]) => <li key={status}>
        <div><Status status={status} /><strong>{count.toLocaleString()}</strong></div>
        <progress aria-label={formatStatus(status)} value={count} max={totalApplications} />
      </li>)}</ul> : <p className="muted">{error ? "Status breakdown unavailable." : data ? "No applications recorded yet." : "Loading application statuses…"}</p>}
    </section>
    </div>

    <section className="government-workflow panel">
      <div className="panel-heading"><div><span className="step">REVIEW PIPELINE</span><h2>{local ? 'Local verification' : 'Central review and issuance'}</h2><p>{local ? 'Check applications for your assigned area, then forward verified cases for final review.' : 'Review forwarded applications, approve eligible cases, and issue approved certificates.'}</p></div><button className="text-button" onClick={() => setWorkspace('queue')}>Open queue →</button></div>
      <div className="government-step-grid">
        <button onClick={() => setWorkspace('queue')}><span className="step-number">01</span><span><strong>{local ? 'Verify applicant' : 'Review forwarded case'}</strong><small>{local ? 'Check identity and household details for your area.' : 'Inspect local verification and submitted details.'}</small></span><b>{local ? statusCounts.pending_local ?? pendingReview : statusCounts.pending_central ?? pendingReview}</b></button>
        <button onClick={() => setWorkspace('queue')}><span className="step-number">02</span><span><strong>{local ? 'Forward for final review' : 'Approve and issue'}</strong><small>{local ? 'Forward verified applications to central authority.' : 'Issue an RIC after final approval.'}</small></span><b>{local ? statusCounts.pending_central ?? 0 : readyToIssue}</b></button>
        <button onClick={() => setWorkspace('certificates')}><span className="step-number">03</span><span><strong>Certificate register</strong><small>Find issued RICs and download certificate PDFs.</small></span><b>{data?.issued_certificate_count ?? certificates.length}</b></button>
      </div>
    </section>

    <section className="government-footer-actions">
      <button className="government-utility-card" onClick={() => setWorkspace('certificates')}><span className="government-metric-icon"><Icon name="award" /></span><span><strong>Certificate register</strong><small>Review issued certificates and download PDFs.</small></span><b aria-hidden="true">→</b></button>
      <button className="government-utility-card" onClick={() => setWorkspace('inbox')}><span className="government-metric-icon"><Icon name="inbox" /></span><span><strong>Official notifications</strong><small>{unread ? `${unread} unread update${unread === 1 ? '' : 's'}` : 'Application progress and decisions appear here.'}</small></span><b aria-hidden="true">→</b></button>
    </section>
  </div>;
}

type InboxItem = { id: number; destination: string; record_id: string; message: string; created_at: string; read_at: string | null };
type Inbox = { items: InboxItem[]; unread: number };
type AccountProfile = { display_name: string | null; contact_phone: string | null; photo_url: string | null; appearance: 'light' | 'dark'; theme: 'teal' | 'indigo' | 'amber' | 'rose' | 'forest' | 'ocean' };
type Reliability = { score: number | null; events: { id: string; period_month: string; reason: string; points: number }[] };
type Share = { id: number; other_email: string; categories: string[]; expires_at: string; revoked_at: string | null };
type SharedHistory = { tenancies?: { start_date: string; end_date: string | null; status: string }[]; reliability?: Reliability };

function useWorkspaceResource<T>(path: string) {
  const [data, setData] = useState<T>();
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  async function run(action: () => Promise<void>) {
    setBusy(true);
    setError('');
    try { await action(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Something went wrong'); }
    finally { setBusy(false); }
  }
  async function reload() { setData(await request<T>(path)); }
  useEffect(() => { void run(reload); }, [path]);
  return { data, setData, error, busy, reload, run };
}

function ProfileSettings({ user, onSaved }: { user: User; onSaved: (profile: AccountProfile) => void }) {
  const { data, setData, error, busy, reload, run } = useWorkspaceResource<AccountProfile>('/profile');
  const [message, setMessage] = useState('');
  const [photo, setPhoto] = useState<File>();
  function update(options: RequestInit, success: string, path = '/profile') {
    setMessage('');
    void run(async () => {
      const profile = await request<AccountProfile>(path, options);
      setData(profile);
      onSaved(profile);
      setMessage(success);
      if (path === '/profile/photo') setPhoto(undefined);
    });
  }
  function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const fields = new FormData(event.currentTarget);
    update({ method: 'PUT', body: JSON.stringify({
      display_name: fields.get('display_name'),
      contact_phone: String(fields.get('contact_phone') || '').trim() || null,
    }) }, 'Profile saved.');
  }
  return <>
    {error && <p className="alert error" role="alert">{error}</p>}
    {message && <p className="alert success" role="status">{message}</p>}
    {!data ? busy || !error ? <p role="status">Loading profile…</p> : <button className="secondary" onClick={() => void run(reload)}>Try again</button> :
      <div className="sharing-layout">
        <section className="panel"><h2>Personal details</h2>
          <form className="auth-form" onSubmit={save}>
            <label>Display name<input name="display_name" maxLength={100} required defaultValue={data.display_name || user.email.split('@')[0]} /></label>
            <label>Private contact number<input name="contact_phone" type="tel" autoComplete="tel" maxLength={16} pattern="[+]?[0-9]{7,15}" defaultValue={data.contact_phone || ''} /></label>
            <small>Use 7–15 digits, with an optional leading +.</small>
            <button className="primary" disabled={busy}>Save details</button>
          </form>
          <dl className="profile-facts"><dt>Sign-in email</dt><dd>{user.email}</dd><dt>Account role</dt><dd>{formatLabel(user.role)}</dd></dl>
          <p>Your display name appears in your workspace. Verified identity details and official assignments are managed through their existing workflows.</p>
        </section>
        <section className="panel"><h2>Appearance</h2>
          <form className="auth-form" onSubmit={event => {
            event.preventDefault();
            const fields = new FormData(event.currentTarget);
            update({ method: 'PUT', body: JSON.stringify({ appearance: fields.get('appearance'), theme: fields.get('theme') }) }, 'Appearance saved.', '/profile/appearance');
          }}>
            <label>Mode<select name="appearance" defaultValue={data.appearance}><option value="light">Light</option><option value="dark">Dark</option></select></label>
            <fieldset className="theme-picker"><legend>Color palette</legend>{[['teal', 'Jade', '#286b59'], ['indigo', 'Iris', '#625197'], ['amber', 'Sandstone', '#8b6427'], ['rose', 'Rosewood', '#934c64'], ['forest', 'Olive', '#596d39'], ['ocean', 'Harbor', '#326b85']].map(([value, label, color]) => <label key={value}><input type="radio" name="theme" value={value} defaultChecked={data.theme === value} /><span className="theme-swatch" style={{ background: color }} /><span>{label}</span></label>)}</fieldset>
            <button className="primary" disabled={busy}>Save appearance</button>
          </form>
        </section>
        <section className="panel"><h2>Profile photo</h2>
          <div className="profile-photo-preview">{data.photo_url ? <img src={data.photo_url} alt="Your current profile photo" /> : (data.display_name || user.email).slice(0, 1).toUpperCase()}</div>
          <form className="auth-form" onSubmit={event => {
            event.preventDefault();
            if (photo) update({ method: 'PUT', body: photo, headers: { 'Content-Type': 'application/octet-stream' } }, 'Photo uploaded.', '/profile/photo');
          }}>
            <label>Choose photo<input key={data.photo_url || 'empty'} type="file" accept="image/jpeg,image/png,image/webp" onChange={event => setPhoto(event.target.files?.[0])} /></label>
            <small>JPEG, PNG or WebP up to 4 MB. The photo is cropped to a square.</small>
            <div className="button-row"><button className="primary" disabled={busy || !photo}>Upload photo</button>
              {data.photo_url && <button className="secondary" type="button" disabled={busy} onClick={() => update({ method: 'DELETE' }, 'Photo removed.', '/profile/photo')}>Remove photo</button>}
            </div>
          </form>
        </section>
      </div>}
  </>;
}

function InboxPanel({ inbox, error, refresh, open }: { inbox: Inbox; error: string; refresh: () => Promise<void>; open: (item: InboxItem) => void }) {
  const [actionError, setActionError] = useState('');
  const [pending, setPending] = useState<number>();
  async function read(item: InboxItem, navigate = false) {
    setPending(item.id);
    setActionError('');
    try {
      if (!item.read_at) await request(`/workspace/notifications/${item.id}/read`, { method: 'POST' });
      await refresh();
      if (navigate) open(item);
    } catch (reason) {
      setActionError(reason instanceof Error ? reason.message : 'Could not mark this notification as read');
    } finally { setPending(undefined); }
  }
  return <section className="panel"><div className="panel-heading"><h2>{inbox.unread} unread</h2><button className="secondary" onClick={refresh}>Refresh</button></div>
    {(error || actionError) && <p className="alert error" role="alert">{actionError || error}</p>}
    {!error && inbox.items.length === 0 && <Empty title="Your inbox is empty" text="Updates to your applications, rent, or viewings appear here." />}
    {inbox.items.map(item => <article className={`record-row ${item.read_at ? '' : 'unread-row'}`} key={item.id}>
      <div><strong>{item.message}</strong><small>{new Date(item.created_at).toLocaleString()}</small></div>
      <div className="button-row">{!item.read_at && <button className="secondary small-button" disabled={pending !== undefined} onClick={() => void read(item)}>Mark as read</button>}
      <button className="secondary small-button" disabled={pending !== undefined} onClick={() => void read(item, true)}>Open {item.destination}</button></div>
    </article>)}
  </section>;
}

function ScoreHistory({ history }: { history: Reliability }) {
  return <><div className="score-summary"><strong>{history.score === null ? 'No score yet' : `${history.score} / 100`}</strong><p>Based on rent payments confirmed in the ledger.</p></div>
    {history.events.map(event => <div className="record-row" key={event.id}><div><strong>{event.reason}</strong><small>{event.period_month.slice(0, 7)}</small></div><b>{event.points > 0 ? '+' : ''}{event.points}</b></div>)}</>;
}

function ReliabilityPanel() {
  const { data, error, busy, reload, run } = useWorkspaceResource<Reliability>('/workspace/reliability');
  return <section className="panel"><div className="panel-heading"><h2>Payment history</h2><button className="secondary" disabled={busy} onClick={() => void run(reload)}>Refresh</button></div>
    {error && <p className="alert error" role="alert">{error}</p>}
    {busy && !data && <p role="status">Loading payment history…</p>}
    {data && <ScoreHistory history={data} />}
  </section>;
}

function SharingPanel({ tenant, tenancies }: { tenant: boolean; tenancies: Tenancy[] }) {
  const { data, error, busy, reload, run } = useWorkspaceResource<Share[]>('/workspace/sharing');
  const [selected, setSelected] = useState<{ id: number; history: SharedHistory }>();
  const landlords = Array.from(new Map(tenancies.map(row => [row.landlord_id, row.property_address || 'Registered landlord'])));
  function grant(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const fields = new FormData(form);
    void run(async () => {
      await request('/workspace/sharing', { method: 'POST', body: JSON.stringify({
        landlord_id: fields.get('landlord_id'), categories: fields.getAll('categories'),
        expires_at: new Date(String(fields.get('expires_at'))).toISOString(),
      }) });
      form.reset();
      await reload();
    });
  }
  return <div className="sharing-layout">
    {error && <p className="alert error" role="alert">{error}</p>}
    {tenant && <section className="panel"><h2>Share your rental history</h2>
      {landlords.length === 0 ? <p>Choose a landlord once you have a tenancy record.</p> : <form className="auth-form" onSubmit={grant}>
        <label>Landlord for<select name="landlord_id" required>{landlords.map(([id, address]) => <option key={id} value={id}>{address}</option>)}</select></label>
        <fieldset className="choice-group"><legend>Information to share</legend>
          <label><input type="checkbox" name="categories" value="tenancies" defaultChecked /> Tenancy dates and statuses</label>
          <label><input type="checkbox" name="categories" value="reliability" /> Reliability score and payment events</label>
          <label><input type="checkbox" name="categories" value="certificates" /> Rental Identity Certificates and delivery history</label>
        </fieldset>
        <label>Expires at<input name="expires_at" type="datetime-local" required /></label>
        <button className="primary" disabled={busy}>Grant access</button>
      </form>}
    </section>}
    <section className="panel"><h2>{tenant ? 'Access you granted' : 'History shared with you'}</h2>
      {busy && !data && <p role="status">Loading access grants…</p>}
      {data?.length === 0 && <Empty title="No access grants" text="Shared rental history will appear here." />}
      {data?.map(item => <article key={item.id} className="record-row"><div><strong>{item.other_email}</strong>
        <small>{item.categories.join(', ')} · {item.revoked_at ? 'Revoked' : `Expires ${new Date(item.expires_at).toLocaleString()}`}</small></div>
        {tenant ? !item.revoked_at && new Date(item.expires_at).getTime() > Date.now() && <div className="record-actions">
          {!item.categories.includes('certificates') && <button className="secondary" disabled={busy} onClick={() => void run(async () => {
            await request(`/workspace/sharing/${item.id}`, { method: 'PUT', body: JSON.stringify({ categories: [...item.categories, 'certificates'] }) }); await reload();
          })}>Share certificates too</button>}
          <button className="secondary" disabled={busy} onClick={() => void run(async () => {
            await request(`/workspace/sharing/${item.id}`, { method: 'DELETE' }); await reload();
          })}>Revoke access</button>
        </div> : <button className="secondary" disabled={busy} onClick={() => {
          setSelected(undefined);
          void run(async () => setSelected({ id: item.id, history: await request<SharedHistory>(`/workspace/sharing/${item.id}/history`) }));
        }}>View history</button>}
      </article>)}
      {selected && <div className="shared-detail"><button className="secondary" onClick={() => setSelected(undefined)}>Close history</button>
        {selected.history.tenancies?.map((row, index) => <p key={index}>{row.start_date} to {row.end_date || 'present'} · {formatStatus(row.status)}</p>)}
        {selected.history.reliability && <ScoreHistory history={selected.history.reliability} />}
      </div>}
    </section>
  </div>;
}

function ApplicationTimeline({ application }: { application: Application }) {
  const stages = ['Submitted', 'Local review', 'Central review', 'Certificate'];
  const { status } = application;
  const rejected = status.startsWith('rejected');
  const active = status === 'approved' ? 3 : status.includes('central') ? 2 : status.includes('local') ? 1 : 0;
  return <div className="application-progress">
    <ol aria-label="Application progress">
      {stages.map((stage, index) => {
        const completed = index < active || status === 'approved' || index === 0 && !rejected;
        const current = index === active && !completed;
        const state = completed ? 'done' : current ? rejected ? 'rejected' : 'current' : 'waiting';
        return <li key={stage} data-state={state} aria-current={current ? 'step' : undefined}>
          <span className="progress-marker" aria-hidden="true">{completed ? '✓' : current && rejected ? '×' : index + 1}</span>
          <strong>{stage}</strong>
          <small>{index === 0 ? new Date(application.submitted_at).toLocaleDateString() : completed ? 'Complete' : current ? rejected ? 'Rejected' : 'In review' : 'Pending'}</small>
        </li>;
      })}
    </ol>
    {rejected && <div className="timeline-rejection"><strong>{formatStatus(status)}</strong><small>{application.rejection_reason || 'Please contact the reviewing office.'}</small></div>}
  </div>;
}

function ApplicationDetail({ application, onBack }: { application: Application; onBack: () => void }) {
  const isRejected = application.status.startsWith('rejected');
  const isApproved = application.status === 'approved';
  const isPending = application.status.startsWith('pending');
  const statusTone = isRejected ? 'tone-red' : isApproved ? 'tone-green' : isPending ? 'tone-blue' : 'tone-gray';
  return (
    <section className="panel">
      <div className="panel-heading">
        <button className="secondary small-button" onClick={onBack}>← Back to applications</button>
        <div>
          <span className="step">APPLICATION DETAIL</span>
          <h2>{application.applicant_name}</h2>
        </div>
      </div>
      <div className="record-grid">
        <div className="record-card">
          <div className="field">
            <label>Application reference</label>
            <span className="value">{application.id.slice(0, 8).toUpperCase()}</span>
          </div>
          <div className="field">
            <label>Applicant</label>
            <span className="value">{application.applicant_name}</span>
          </div>
          <div className="field">
            <label>Email</label>
            <span className="value">{application.email || '—'}</span>
          </div>
          <div className="field">
            <label>Area</label>
            <span className="value">{application.area_name || '—'}</span>
          </div>
          <div className="field">
            <label>Submitted</label>
            <span className="value">{new Date(application.submitted_at).toLocaleDateString()}</span>
          </div>
          <div className="field">
            <label>Status</label>
            <span className={`value ${statusTone}`}>{application.status.replace(/_/g, ' ')}</span>
          </div>
        </div>
        <div className="record-card">
          <h3>Review timeline</h3>
          <ApplicationTimeline application={application} />
          {isRejected && application.rejection_reason && (
            <div className="field">
              <label>Rejection reason</label>
              <span className="value tone-red">{application.rejection_reason}</span>
            </div>
          )}
          {application.local_note && (
            <div className="field">
              <label>Local reviewer note</label>
              <span className="value">{application.local_note}</span>
            </div>
          )}
          {application.central_note && (
            <div className="field">
              <label>Central reviewer note</label>
              <span className="value">{application.central_note}</span>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

function RelocationForm({ areas, busy, onSubmit }: { areas: Area[]; busy: boolean; onSubmit: (event: FormEvent<HTMLFormElement>) => void }) {
  return <section className="panel form-panel"><div className="form-intro"><span className="step">RIC PROFILE · RELOCATION</span><h2>Update your registered location</h2><p>Your previous area record will remain in your history. This creates a new application for review in your new area.</p></div><form onSubmit={onSubmit} className="form-single"><AreaPicker areas={areas} label="Upazila / Thana" /><div className="field-group"><label>New household address<textarea name="household_address" required /></label></div><div className="field-group"><label>Permanent address<textarea name="permanent_address" /></label></div><div className="form-actions"><button className="primary" disabled={busy}>{busy ? 'Submitting…' : 'Submit relocation'} <span>→</span></button></div></form></section>;
}

function ApplicationForm({ areas, busy, onSubmit }: { areas: Area[]; busy: boolean; onSubmit: (event: FormEvent<HTMLFormElement>) => void }) {
  const [members, setMembers] = useState<Array<{ full_name: string; relationship: string; date_of_birth: string }>>([]);
  function addMember() { setMembers([...members, { full_name: '', relationship: '', date_of_birth: '' }]); }
  function removeMember(index: number) { setMembers(members.filter((_, memberIndex) => memberIndex !== index)); }
  function updateMember(index: number, field: 'full_name' | 'relationship' | 'date_of_birth', value: string) {
    setMembers(members.map((member, memberIndex) => memberIndex === index ? { ...member, [field]: value } : member));
  }
  return <section className="panel form-panel"><div className="form-intro"><span className="step">RIC APPLICATION · STEP 1 OF 1</span><h2>Tell us about your household</h2><p>Submit accurate information for official review. Your identity number is encrypted before it is stored.</p></div><form onSubmit={onSubmit} className="form-grid"><label>Full name<input name="full_name" required /></label><label>National identity number<input name="identity_number" required /></label><label>Date of birth<input name="date_of_birth" type="date" /></label><AreaPicker areas={areas} label="Upazila / Thana" className="wide" /><label className="wide">Permanent address<textarea name="permanent_address" /></label><label className="wide">Current household address<textarea name="household_address" required /></label><div className="wide member-section"><div className="panel-heading"><div><span className="step">HOUSEHOLD MEMBERS</span><h3>Other members living at this address</h3></div><button type="button" className="secondary small-button" onClick={addMember}>+ Add member</button></div>{members.map((member, index) => <div className="member-row" key={index}><input aria-label={`Member ${index + 1} name`} placeholder="Full name" value={member.full_name} onChange={(event) => updateMember(index, 'full_name', event.target.value)} required /><input aria-label={`Member ${index + 1} relationship`} placeholder="Relationship" value={member.relationship} onChange={(event) => updateMember(index, 'relationship', event.target.value)} /><input aria-label={`Member ${index + 1} date of birth`} type="date" value={member.date_of_birth} onChange={(event) => updateMember(index, 'date_of_birth', event.target.value)} /><button type="button" className="text-button" onClick={() => removeMember(index)}>Remove</button></div>)}<input type="hidden" name="members" value={JSON.stringify(members.filter((member) => member.full_name.trim()).map((member) => ({ ...member, relationship: member.relationship || null, date_of_birth: member.date_of_birth || null })))} /></div><div className="wide form-actions"><button className="primary" disabled={busy}>{busy ? 'Submitting…' : 'Submit application'} <span>→</span></button></div></form></section>;
}
function ApplicationList({ applications, onRefresh, onSelect }: { applications: Application[]; onRefresh: () => void; onSelect: (id: string) => void }) {
  return <section className="panel"><div className="panel-heading"><div><span className="step">APPLICATION HISTORY</span><h2>Your RIC applications</h2></div><button className="secondary small-button" onClick={onRefresh}>Refresh</button></div>{applications.length === 0 ? <Empty title="No applications yet" text="Start your first application to create a trackable rental identity record." /> : <div className="record-list">{applications.map((application) => <div className="record-row clickable" key={application.id} onClick={() => onSelect(application.id)}><div><strong>{application.applicant_name}</strong><small>Submitted {new Date(application.submitted_at).toLocaleDateString()} · Ref {application.id.slice(0, 8)}</small></div><div className="record-actions"><Status status={application.status} /><span className="text-button">View details</span></div></div>)}</div>}</section>;
}

function ReviewQueue({ applications, busy, onRefresh, onReview, onIssue }: { applications: Application[]; busy: boolean; onRefresh: () => void; onReview: (id: string, action: 'forward' | 'reject' | 'approve' | 'return_to_local', note?: string) => void; onIssue: (id: string) => void }) {
  const [reasonFor, setReasonFor] = useState<{ id: string; action: 'reject' | 'return_to_local' } | null>(null);
  const [reason, setReason] = useState('');
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const statuses = [...new Set(applications.map(application => application.status))];
  const query = search.trim().toLowerCase();
  const visibleApplications = applications.filter(application =>
    (!statusFilter || application.status === statusFilter) &&
    [application.applicant_name, application.area_name]
      .some(value => value?.toLowerCase().includes(query)),
  );
  function openReason(id: string, action: 'reject' | 'return_to_local') {
    setReasonFor({ id, action });
    setReason('');
  }
  function submitReason(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const note = reason.trim();
    if (!reasonFor || !note) return;
    onReview(reasonFor.id, reasonFor.action, note);
    setReasonFor(null);
    setReason('');
  }

  return <section className="panel"><div className="panel-heading"><div><span className="step">OFFICIAL REVIEW QUEUE</span><h2>Applications requiring action</h2><p>Reject with a written reason, or return a central review to the local office with clear follow-up notes.</p></div><button className="secondary small-button" onClick={onRefresh}>Refresh queue</button></div>
    {applications.length > 0 && <div className="review-filters">
      <label>Search applications<input type="search" value={search} onChange={event => setSearch(event.target.value)} placeholder="Applicant or area" /></label>
      <label>Status<select value={statusFilter} onChange={event => setStatusFilter(event.target.value)}>
        <option value="">All statuses</option>
        {statusFilter && !statuses.includes(statusFilter) && <option value={statusFilter}>{formatStatus(statusFilter)}</option>}
        {statuses.map(status => <option key={status} value={status}>{formatStatus(status)}</option>)}
      </select></label>
      <span role="status" className="muted">{visibleApplications.length} of {applications.length} applications</span>
    </div>}
    {applications.length === 0 ? <Empty title="Queue is clear" text="No applications are currently assigned to this official profile." /> : visibleApplications.length === 0 ? <Empty title="No matching applications" text="Change the search or status filter to see more applications." /> : <div className="review-list">{visibleApplications.map((application) => <div className="review-card" key={application.id}>
      <div className="review-main"><div className="avatar">{application.applicant_name.slice(0, 1).toUpperCase()}</div><div><strong>{application.applicant_name}</strong><small>{application.email} · {application.area_name}</small><small>Submitted {new Date(application.submitted_at).toLocaleDateString()} · ID ending {application.identity_last4 || '—'}</small>{application.status === 'pending_local' && application.central_note && <small className="return-note"><strong>Central review notes:</strong> {application.central_note}</small>}</div></div>
      <div className="review-side"><Status status={application.status} /><div className="button-row">
        {application.status === 'pending_local' && <><button className="secondary small-button" disabled={busy} onClick={() => openReason(application.id, 'reject')}>Reject</button><button className="primary small-button" disabled={busy} onClick={() => onReview(application.id, 'forward')}>Forward to central</button></>}
        {application.status === 'pending_central' && <><button className="secondary small-button" disabled={busy} onClick={() => openReason(application.id, 'reject')}>Reject</button><button className="secondary small-button" disabled={busy} onClick={() => openReason(application.id, 'return_to_local')}>Return to local</button><button className="primary small-button" disabled={busy} onClick={() => { if (window.confirm('Approve this rental identity application?')) onReview(application.id, 'approve'); }}>Approve</button></>}
        {application.status === 'approved' && <button className="primary small-button" disabled={busy} onClick={() => { if (window.confirm("Issue the Rental Identity Certificate for this application?")) onIssue(application.id); }}>Issue RIC certificate</button>}
      </div></div>
      {reasonFor?.id === application.id && <form className="review-note-form" onSubmit={submitReason}>
        <label>{reasonFor.action === 'return_to_local' ? 'What should the local office verify?' : 'Reason for rejection'}<textarea value={reason} onChange={event => setReason(event.target.value)} rows={3} maxLength={2000} required placeholder={reasonFor.action === 'return_to_local' ? 'Describe the missing details or checks needed…' : 'Provide the written reason for this decision…'} /></label>
        <div className="button-row"><button type="button" className="secondary small-button" disabled={busy} onClick={() => { setReasonFor(null); setReason(''); }}>Cancel</button><button className="primary small-button" disabled={busy || !reason.trim()}>{reasonFor.action === 'return_to_local' ? 'Return for local review' : 'Confirm rejection'}</button></div>
      </form>}
    </div>)}</div>}
  </section>;
}

function CertificateList({ certificates, onDownload, tenant }: { certificates: Certificate[]; onDownload: (id: string) => void; tenant: boolean }) {
  return <section className="panel"><div className="panel-heading"><div><span className="step">{tenant ? 'MY LINKED CERTIFICATES' : 'CERTIFICATE REGISTER'}</span><h2>{tenant ? 'Certificates linked to your household' : 'Issued RIC certificates'}</h2></div><span className="panel-number">{certificates.length}</span></div>{certificates.length === 0 ? <Empty title="No certificates issued" text={tenant ? 'Your certificate will appear here automatically after government approval and issuance.' : 'Issued certificates will appear here after central approval.'} /> : <div className="record-list">{certificates.map((certificate) => <div className="record-row" key={certificate.id}><div><strong>{certificate.ric_number}</strong><small>{certificate.applicant_name} · {certificate.area_name} · {new Date(certificate.issued_at).toLocaleDateString()}</small></div><div className="record-actions"><Status status={certificate.status} /><button className="secondary small-button" onClick={() => onDownload(certificate.id)}>Download PDF</button></div></div>)}</div>}</section>;
}

function OfficialForm({ areas, busy, onSubmit }: { areas: Area[]; busy: boolean; onSubmit: (payload: { email: string; password: string; full_name: string; level: string; area_id?: number }) => void }) {
  const [level, setLevel] = useState('local');
  function submit(event: FormEvent<HTMLFormElement>) { event.preventDefault(); const form = new FormData(event.currentTarget); onSubmit({ email: String(form.get('email')), password: String(form.get('password')), full_name: String(form.get('full_name')), level, area_id: level === 'local' ? Number(form.get('area_id')) : undefined }); }
  return <section className="panel form-panel"><span className="step">ADMINISTRATION · GOVERNMENT PROFILES</span><h2>Create a government profile ID</h2><p>Provision an official account and assign the smallest jurisdiction needed for its work.</p><form onSubmit={submit} className="form-grid"><label>Official full name<input name="full_name" required /></label><label>Official email<input name="email" type="email" required /></label><label>Password<input name="password" type="password" minLength={8} required /></label><label>Access level<select name="level" value={level} onChange={(event) => setLevel(event.target.value)}><option value="local">Local reviewer</option><option value="central">Central issuer</option></select></label>{level === 'local' && <AreaPicker areas={areas} label="Assigned upazila / thana" className="wide" />}<div className="wide form-actions"><button className="primary" disabled={busy}>{busy ? 'Creating profile…' : 'Create government profile'} <span>→</span></button></div></form></section>;
}

function AuthScreen({ screen, loginRole, registerRole, resetToken, busy, error, notice, onBack, onLogin, onRegister, onRegisterRole, onBootstrap, onDemoPasswordReset, onPasswordReset, onSwitch }: { screen: 'login' | 'register' | 'bootstrap' | 'forgot' | 'reset'; loginRole: Role; registerRole: 'tenant' | 'landlord'; resetToken: string; busy: boolean; error: string; notice: string; onBack: () => void; onLogin: (event: FormEvent<HTMLFormElement>) => void; onRegister: (event: FormEvent<HTMLFormElement>) => void; onRegisterRole: (role: 'tenant' | 'landlord') => void; onBootstrap: (event: FormEvent<HTMLFormElement>) => void; onDemoPasswordReset: (event: FormEvent<HTMLFormElement>) => void; onPasswordReset: (event: FormEvent<HTMLFormElement>) => void; onSwitch: (screen: 'login' | 'register' | 'bootstrap' | 'forgot' | 'reset') => void }) {
  const title = screen === 'login' ? `Sign in as ${loginRole}` : screen === 'register' ? `Create a ${registerRole} account` : screen === 'forgot' ? 'Reset your password' : screen === 'reset' ? 'Choose a new password' : 'Create the first administrator';
  return <main className="content auth-content">
    <button className="auth-home-button" onClick={onBack}><span aria-hidden="true">←</span> Back to home</button>
    <div className="auth-layout">
      <aside className="auth-introduction">
        <span className="eyebrow">CENTRAL TENANT RECORDS</span>
        <h2>A place for every part of renting.</h2>
        <p>Keep your identity, home, and rental history connected.</p>
        <div><Icon name="award" /><span>Follow your certificate application</span></div>
        <div><Icon name="key" /><span>Manage your tenancy and home</span></div>
        <div><Icon name="card" /><span>Keep payments and records together</span></div>
      </aside>
      <section className="panel auth-panel">
        <Brand />
        <span className="eyebrow">{screen === 'login' ? `${loginRole} sign in` : screen === 'register' ? `${registerRole} registration` : screen === 'forgot' || screen === 'reset' ? 'Account recovery' : 'One-time platform setup'}</span>
        <h1>{title}</h1>
        {notice && <div className="alert success">{notice}</div>}
        {error && <div className="alert error" role="alert">{error}</div>}
        {screen === 'login' ? <form onSubmit={onLogin} className="auth-form">
          <label>Email<input name="email" type="email" autoComplete="username" required /></label>
          <label>Password<input name="password" type="password" autoComplete="current-password" required /></label>
          <button type="button" className="text-button auth-forgot-link" onClick={() => onSwitch('forgot')}>Forgot password?</button>
          <button className="primary" disabled={busy}>{busy ? 'Signing in…' : 'Sign in'} <span>→</span></button>
        </form> : screen === 'register' ? <form onSubmit={onRegister} className="auth-form">
          <label>Account type<select value={registerRole} onChange={(event) => onRegisterRole(event.target.value as 'tenant' | 'landlord')}><option value="tenant">Tenant</option><option value="landlord">Landlord</option></select></label>
          <label>Full name<input name="full_name" autoComplete="name" required /></label>
          <label>Email<input name="email" type="email" autoComplete="email" required /></label>
          <label>Phone (optional)<input name="phone" type="tel" autoComplete="tel" /></label>
          <label>Password<input name="password" type="password" autoComplete="new-password" minLength={8} required /></label>
          <label>Confirm password<input name="confirm_password" type="password" autoComplete="new-password" minLength={8} required /></label>
          <button className="primary" disabled={busy}>{busy ? 'Creating account…' : 'Create account'} <span>→</span></button>
        </form> : screen === 'forgot' ? <form onSubmit={onDemoPasswordReset} className="auth-form">
          <p className="muted">Demo account reset. Enter the account email and choose a new password; no email step is needed.</p>
          <label>Email<input name="email" type="email" autoComplete="email" required /></label>
          <label>New password<input name="password" type="password" autoComplete="new-password" minLength={8} required /></label>
          <label>Confirm new password<input name="confirm_password" type="password" autoComplete="new-password" minLength={8} required /></label>
          <button className="primary" disabled={busy}>{busy ? 'Updating password…' : 'Reset demo password'} <span>→</span></button>
        </form> : screen === 'reset' ? <form onSubmit={onPasswordReset} className="auth-form">
          <p className="muted">Choose a new password for your account. This link works once and expires after a short time.</p>
          {!resetToken && <div className="alert error" role="alert">This reset link is missing or invalid. Request a new one.</div>}
          <label>New password<input name="password" type="password" autoComplete="new-password" minLength={8} required /></label>
          <label>Confirm new password<input name="confirm_password" type="password" autoComplete="new-password" minLength={8} required /></label>
          <button className="primary" disabled={busy || !resetToken}>{busy ? 'Updating password…' : 'Update password'} <span>→</span></button>
        </form> : <form onSubmit={onBootstrap} className="auth-form">
          <p className="muted">Available only while this database has no administrator. Enter the one-time setup password provided by your platform operator; the server checks it without storing it.</p>
          <label>Administrator name<input name="full_name" autoComplete="name" required /></label>
          <label>Administrator email<input name="email" type="email" autoComplete="email" required /></label>
          <label>Administrator password<input name="password" type="password" autoComplete="new-password" minLength={8} required /></label>
          <label>Bootstrap password<input name="bootstrap_password" type="password" autoComplete="current-password" required /></label>
          <button className="primary" disabled={busy}>{busy ? 'Creating administrator…' : 'Create first administrator'} <span>→</span></button>
        </form>}
        {screen === 'login' && <button className="text-button" onClick={() => onSwitch('bootstrap')}>First-time administrator setup</button>}
        {screen === 'forgot' && <button className="text-button" onClick={() => onSwitch('login')}>Back to sign in</button>}
        {screen === 'reset' && <button className="text-button" onClick={() => onSwitch('forgot')}>Request a new reset link</button>}
        {screen === 'register' && <button className="text-button" onClick={() => onSwitch('login')}>Already have an account? Sign in</button>}
        {screen === 'login' && <button className="text-button" onClick={() => onSwitch('register')}>Create an account</button>}
        <p className="muted auth-note">Government and administrator accounts are provisioned by authorized administrators.</p>
      </section>
    </div>
  </main>;
}

function UnitManager({ properties }: { properties: Property[] }) {
  const [propertyId, setPropertyId] = useState('');
  const [units, setUnits] = useState<PropertyUnit[]>([]);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const loadSequence = useRef(0);
  async function load(property: string) {
    const sequence = ++loadSequence.current;
    setPropertyId(property);
    setUnits([]);
    setError('');
    if (!property) return;
    try {
      const result = await request<PropertyUnit[]>(`/properties/${property}/units`);
      if (sequence === loadSequence.current) setUnits(result);
    } catch (reason) {
      if (sequence === loadSequence.current) setError(reason instanceof Error ? reason.message : 'Unable to load apartments');
    }
  }
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    setBusy(true);
    setError('');
    try {
      await request<PropertyUnit>(`/properties/${propertyId}/units`, { method: 'POST', body: JSON.stringify({
        unit_number: form.get('unit_number'), floor_number: Number(form.get('floor_number')),
        monthly_rent: Number(form.get('monthly_rent')), floor_area_sqft: Number(form.get('floor_area_sqft')),
        bedrooms: Number(form.get('bedrooms')), bathrooms: Number(form.get('bathrooms')),
        available_from: form.get('available_from'), status: form.get('status'),
      })});
      formElement.reset();
      await load(propertyId);
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Unable to add apartment'); }
    finally { setBusy(false); }
  }
  return <section className="panel-layout"><section className="panel form-panel"><span className="step">BUILDING INVENTORY · APARTMENTS</span><h2>Manage apartment units</h2><p>Each building can have its own apartment count, numbering, rent and availability.</p><label>Building<select value={propertyId} onChange={(event) => void load(event.target.value)}><option value="">Select a building</option>{properties.map((property) => <option value={property.id} key={property.id}>{property.address_line}</option>)}</select></label>{propertyId && <form onSubmit={submit} className="form-grid unit-form"><label>Apartment number<input name="unit_number" required placeholder="A-101" /></label><label>Floor<input name="floor_number" type="number" min="0" required /></label><label>Monthly rent<input name="monthly_rent" type="number" min="1" required /></label><label>Floor area<input name="floor_area_sqft" type="number" min="1" required /></label><label>Bedrooms<input name="bedrooms" type="number" min="0" required /></label><label>Bathrooms<input name="bathrooms" type="number" min="0" required /></label><label>Available from<input name="available_from" type="date" required /></label><label>Status<select name="status" defaultValue="available"><option value="available">Available</option><option value="occupied">Occupied</option><option value="maintenance">Maintenance</option></select></label><div className="wide form-actions"><button className="primary" disabled={busy}>{busy ? 'Saving apartment…' : 'Add apartment'} <span>→</span></button></div></form>}{error && <div className="alert error" role="alert">{error}</div>}</section><section className="panel"><div className="panel-heading"><div><span className="step">UNIT REGISTER</span><h2>Apartments</h2></div><span className="panel-number">{units.length}</span></div>{!propertyId ? <Empty title="Choose a building" text="Select a building to see and manage its apartment units." /> : error && units.length === 0 ? <Empty title="Apartments could not be loaded" text="Check the message beside the form and try selecting the building again." /> : units.length === 0 ? <Empty title="No apartments yet" text="Add the first unit for this building." /> : <div className="record-list">{units.map((unit) => <div className="record-row" key={unit.id}><div><strong>Apartment {unit.unit_number}</strong><small>Floor {unit.floor_number} · {unit.bedrooms} bed · {unit.bathrooms} bath</small><small>৳{unit.monthly_rent.toLocaleString()} / month</small></div><Status status={unit.status} /></div>)}</div>}</section></section>;
}

function PropertyManager({ properties, areas, busy, onCreate }: { properties: Property[]; areas: Area[]; busy: boolean; onCreate: (payload: Omit<Property, 'id' | 'landlord_id' | 'created_at' | 'updated_at'>) => void }) {
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    onCreate({
      area_id: Number(form.get('area_id')),
      address_line: String(form.get('address_line')),
      property_type: String(form.get('property_type')),
      monthly_rent: Number(form.get('monthly_rent')),
      floor_area_sqft: Number(form.get('floor_area_sqft')),
      bedrooms: Number(form.get('bedrooms')),
      bathrooms: Number(form.get('bathrooms')),
      floor_number: Number(form.get('floor_number')),
      available_from: String(form.get('available_from')),
    });
  }
  return <section className="panel-layout"><section className="panel form-panel"><span className="step">LANDLORD WORKSPACE · PROPERTY REGISTER</span><h2>Add a property</h2><p>Keep your inventory organized before publishing a listing for prospective tenants.</p><form onSubmit={submit} className="form-grid"><label className="wide">Address<input name="address_line" required placeholder="Street, building and neighborhood" /></label><label>Property type<select name="property_type" defaultValue="house"><option value="house">House</option><option value="apartment">Apartment</option><option value="room">Room</option><option value="studio">Studio</option><option value="duplex">Duplex</option><option value="other">Other</option></select></label><AreaPicker areas={areas} label="Upazila / Thana" className="wide" /><label>Monthly rent<input name="monthly_rent" type="number" min="1" required /></label><label>Floor area (sq ft)<input name="floor_area_sqft" type="number" min="1" required /></label><label>Bedrooms<input name="bedrooms" type="number" min="0" required /></label><label>Bathrooms<input name="bathrooms" type="number" min="0" required /></label><label>Floor number<input name="floor_number" type="number" min="0" required /></label><label>Available from<input name="available_from" type="date" required /></label><div className="wide form-actions"><button className="primary" disabled={busy || areas.length === 0}>{busy ? 'Saving property…' : areas.length === 0 ? 'Loading areas…' : 'Save property'} <span>→</span></button></div></form></section><section className="panel"><div className="panel-heading"><div><span className="step">YOUR INVENTORY</span><h2>Properties</h2></div><span className="panel-number">{properties.length}</span></div>{properties.length === 0 ? <Empty title="Your inventory is empty" text="Add your first property to start building a trusted listing." /> : <div className="record-list">{properties.map((property) => <div className="record-row" key={property.id}><div><strong>{formatLabel(property.property_type)}</strong><small>{property.address_line}</small><small>{property.area_name || 'Area unavailable'} · {property.district || ''}{property.division ? `, ${property.division}` : ''}</small><small>{property.bedrooms} bed · {property.bathrooms} bath · ৳{property.monthly_rent.toLocaleString()}</small></div><Status status="active" /></div>)}</div>}</section></section>;
}

function ListingManager({ properties, listings, busy, onCreate, onSaved }: { onSaved: () => void; properties: Property[]; listings: Listing[]; busy: boolean; onCreate: (propertyId: string, payload: { property_id: string; status: string; title?: string; description?: string }, unitId?: string) => void }) {
  const [propertyId, setPropertyId] = useState('');
  const [units, setUnits] = useState<PropertyUnit[]>([]);
  const [unitId, setUnitId] = useState('');
  const [unitsError, setUnitsError] = useState('');
  const [loadingUnits, setLoadingUnits] = useState(false);
  const unitLoadSequence = useRef(0);
  async function selectProperty(value: string) {
    const sequence = ++unitLoadSequence.current;
    setPropertyId(value); setUnitId(''); setUnits([]); setUnitsError('');
    if (!value) return;
    setLoadingUnits(true);
    try {
      const result = await request<PropertyUnit[]>(`/properties/${value}/units`);
      if (sequence === unitLoadSequence.current) setUnits(result);
    } catch (reason) {
      if (sequence === unitLoadSequence.current) setUnitsError(reason instanceof Error ? reason.message : 'Apartments could not be loaded');
    } finally { if (sequence === unitLoadSequence.current) setLoadingUnits(false); }
  }
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    onCreate(propertyId, { property_id: propertyId, status: String(form.get('status')), title: String(form.get('title')), description: String(form.get('description')) }, unitId || undefined);
  }
  const selectedUnit = units.find((unit) => unit.id === unitId);
  return <section className="panel-layout"><section className="panel form-panel"><span className="step">PUBLISH A HOME</span><h2>Create a rental listing</h2><p>Choose the building and apartment this listing represents. Apartment listings use that unit’s rent and availability details.</p><form onSubmit={submit} className="auth-form"><label>Building<select name="property_id" value={propertyId} onChange={(event) => void selectProperty(event.target.value)} required><option value="" disabled>Select a building</option>{properties.map((property) => <option value={property.id} key={property.id}>{property.address_line}</option>)}</select></label>{propertyId && <label>Apartment<select name="unit_id" value={unitId} onChange={(event) => setUnitId(event.target.value)} required disabled={loadingUnits || Boolean(unitsError)}><option value="" disabled>{loadingUnits ? 'Loading apartments…' : unitsError ? 'Apartments unavailable' : 'Select an apartment'}</option>{units.map((unit) => <option value={unit.id} key={unit.id}>Apartment {unit.unit_number} · Floor {unit.floor_number} · ৳{unit.monthly_rent.toLocaleString()}</option>)}</select></label>}{unitsError && <p className="alert error" role="alert">{unitsError} <button type="button" className="text-button" onClick={() => void selectProperty(propertyId)}>Try again</button></p>}{propertyId && !loadingUnits && !unitsError && units.length === 0 && <p className="muted">Add an apartment in Apartments before creating a listing.</p>}{selectedUnit && <div className="unit-summary"><strong>Apartment {selectedUnit.unit_number}</strong><span>{selectedUnit.bedrooms} bedrooms · {selectedUnit.bathrooms} bathrooms · {selectedUnit.floor_area_sqft} sq ft · Available {selectedUnit.available_from}</span></div>}<label>Listing title<input name="title" required placeholder="Bright apartment near..." /></label><label>Description<textarea name="description" rows={5} /></label><label>Visibility<select name="status" defaultValue="available"><option value="available">Publish now</option><option value="draft">Save as draft</option></select></label><button className="primary" disabled={busy || !propertyId || !unitId || loadingUnits || Boolean(unitsError)}>{busy ? 'Publishing…' : 'Create apartment listing'} <span>→</span></button></form></section><section className="panel"><div className="panel-heading"><div><span className="step">LISTING PIPELINE</span><h2>Your listings</h2></div><span className="panel-number">{listings.length}</span></div>{listings.length === 0 ? <Empty title="No listings yet" text="Publish an apartment when you are ready to welcome tenants." /> : <div className="record-list">{listings.map((listing) => <div className="record-row" key={listing.id}><div><strong>{listing.title || 'Untitled listing'}</strong><small>{listing.unit_id ? 'Apartment listing' : 'Building listing'} · {listing.description || 'No description added.'}</small></div><div className="button-row"><Status status={listing.status} />{["draft", "available"].includes(listing.status) && <ListingEditor listing={listing} onSaved={onSaved} />}</div></div>)}</div>}</section></section>;
}

function ListingEditor({ listing, onSaved }: { listing: Listing; onSaved: () => void }) {
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setSaving(true);
    setError('');
    try {
      await request(`/properties/listings/${listing.id}`, {
        method: 'PATCH', body: JSON.stringify(Object.fromEntries(form)),
      });
      setOpen(false);
      onSaved();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Could not save listing');
    } finally {
      setSaving(false);
    }
  }
  if (!open) return <button className="secondary small-button" onClick={() => setOpen(true)}>Edit listing</button>;
  return <form className="auth-form listing-editor" onSubmit={save}>
    <label>Title<input name="title" defaultValue={listing.title} maxLength={160} required /></label>
    <label>Description<textarea name="description" rows={3} defaultValue={listing.description} /></label>
    <label>Visibility<select name="status" defaultValue={listing.status}>
      <option value="draft">Draft</option><option value="available">Published</option><option value="withdrawn">Withdraw listing</option>
    </select></label>
    {error && <p className="alert error" role="alert">{error}</p>}
    <div className="button-row"><button className="primary" disabled={saving}>Save changes</button>
      <button className="secondary" type="button" disabled={saving} onClick={() => setOpen(false)}>Cancel</button></div>
  </form>;
}

function PropertyBrowser({ areas, listings, busy, onRequest }: { areas: Area[]; listings: AvailableListing[]; busy: boolean; onRequest: (listingId: string, proposedTime: string) => void }) {
  const [searchResults, setSearchResults] = useState<AvailableListing[]>();
  const [searchError, setSearchError] = useState('');
  const [searching, setSearching] = useState(false);
  const [areaFilterKey, setAreaFilterKey] = useState(0);
  const results = searchResults ?? listings;
  async function search(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const params = new URLSearchParams();
    new FormData(event.currentTarget).forEach((value, name) => {
      if (value) params.set(name, String(value));
    });
    setSearchError('');
    setSearching(true);
    try {
      setSearchResults(await request<AvailableListing[]>(`/properties/available-listings?${params}`));
      setSelectedListing(null);
    } catch (reason) {
      setSearchError(reason instanceof Error ? reason.message : 'Search unavailable');
    } finally { setSearching(false); }
  }
  const [selectedListing, setSelectedListing] = useState<AvailableListing | null>(null);
  const [proposedTime, setProposedTime] = useState('');
  const now = new Date();
  const minimumTime = new Date(now.getTime() - now.getTimezoneOffset() * 60_000).toISOString().slice(0, 16);
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (selectedListing && proposedTime) {
      onRequest(selectedListing.id, proposedTime);
      setSelectedListing(null);
      setProposedTime('');
    }
  }
  return <section className="panel"><div className="panel-heading"><div><span className="step">TENANT DISCOVERY</span><h2>Find a home that fits</h2><p>Browse verified available properties shared by registered landlords.</p></div><span className="panel-number">{results.length}</span></div><form className="search-filters" onSubmit={search}>
  <AreaPicker key={areaFilterKey} areas={areas} label="Upazila / Thana" required={false} className="search-area-picker" />
  <label>Minimum monthly rent<input type="number" min="0" name="min_rent" /></label>
  <label>Maximum monthly rent<input type="number" min="0" name="max_rent" /></label>
  <button className="primary" disabled={searching}>{searching ? 'Searching…' : 'Search homes'}</button>
  <button className="secondary" type="reset" disabled={searching} onClick={() => { setAreaFilterKey((key) => key + 1); setSearchResults(undefined); setSearchError(''); }}>Reset</button>
  </form>{searchError && <p className="alert error" role="alert">{searchError}</p>}{results.length === 0 ? <Empty title="No matching homes" text="Try a wider rent range or check back for new listings." /> : <div className="property-grid">{results.map((listing) => <article className="property-card" key={listing.id}><div className="property-cover"><span className="property-type">{formatLabel(listing.property_type)}</span><span className="property-cover-badge"><Icon name="building" />{listing.unit_number ? ` Apt ${listing.unit_number}` : ' Listing'}</span></div><div className="property-body"><h3>{listing.property_address}</h3><small className="property-location">{listing.area_name} · {listing.district}, {listing.division}</small><strong>৳{listing.monthly_rent.toLocaleString()} <small>/ month</small></strong><p>{listing.bedrooms} bedrooms · {listing.bathrooms} bathrooms · {listing.floor_area_sqft} sq ft</p></div><button className="secondary small-button" disabled={busy} onClick={() => setSelectedListing(listing)}>Request a viewing <span>→</span></button></article>)}</div>}{selectedListing && <div className="viewing-request-panel"><div className="form-intro"><span className="step">VIEWING REQUEST</span><h3>Choose a convenient time</h3><p>{selectedListing.property_address} · {selectedListing.area_name}, {selectedListing.district}, {selectedListing.division}{selectedListing.unit_number ? ` · Apartment ${selectedListing.unit_number}` : ''}</p></div><form onSubmit={submit} className="form-single"><div className="field-group"><label>Preferred date and time<input type="datetime-local" value={proposedTime} min={minimumTime} onChange={(event) => setProposedTime(event.target.value)} required /></label></div><div className="form-actions"><button type="button" className="secondary" onClick={() => setSelectedListing(null)}>Cancel</button><button className="primary" disabled={busy}>{busy ? 'Sending…' : 'Send viewing request'} <span>→</span></button></div></form></div>}</section>;
}

function ViewingList({ viewings, busy, onUpdate }: { viewings: Viewing[]; busy: boolean; onUpdate: (id: string, status: 'confirmed' | 'declined') => void }) {
  return <section className="panel"><div className="panel-heading"><div><span className="step">TENANT PROFILE · VIEWINGS</span><h2>Viewing requests</h2><p>Track every viewing request sent to a landlord.</p></div><span className="panel-number">{viewings.length}</span></div>{viewings.length === 0 ? <Empty title="No viewing requests yet" text="Request a viewing from Find a home and it will appear here." /> : <div className="record-list">{viewings.map((viewing) => <div className="record-row" key={viewing.id}><div><strong>{viewing.listing_title || 'Viewing request'}</strong><small>{viewing.property_address || 'Property details unavailable'}{viewing.unit_number ? ` · Apartment ${viewing.unit_number}` : ''}</small><small>{[viewing.area_name, viewing.district, viewing.division].filter(Boolean).join(' · ')}</small><small>Landlord: {viewing.landlord_name || 'Registered landlord'} · Proposed {new Date(viewing.proposed_time).toLocaleString()}</small><small>৳{(viewing.monthly_rent || 0).toLocaleString()} / month · Sent {new Date(viewing.created_at).toLocaleDateString()}</small></div><div className="button-row"><Status status={viewing.status} />{viewing.confirmed_time && <small>{new Date(viewing.confirmed_time).toLocaleString()}</small>}
  {viewing.status === 'countered' && viewing.alternative_time && <><small>New time {new Date(viewing.alternative_time).toLocaleString()}</small>
  <button className="primary small-button" disabled={busy} onClick={() => onUpdate(viewing.id, 'confirmed')}>Accept new time</button>
  <button className="secondary small-button" disabled={busy} onClick={() => onUpdate(viewing.id, 'declined')}>Decline</button></>}</div></div>)}</div>}</section>;
}

function LandlordViewingList({ viewings, busy, onUpdate }: { viewings: Viewing[]; busy: boolean; onUpdate: (id: string, status: 'confirmed' | 'declined' | 'countered', alternativeTime?: string) => void }) {
  const pendingCount = viewings.filter((viewing) => viewing.status === 'pending').length;
  return <section className="panel"><div className="panel-heading"><div><span className="step">LANDLORD WORKSPACE · VIEWINGS</span><h2>Incoming viewing requests</h2><p>Review proposed times from tenants across your buildings and apartments.</p></div><span className="panel-number">{pendingCount}</span></div>{viewings.length === 0 ? <Empty title="No viewing requests yet" text="Tenant requests for your published listings will appear here." /> : <div className="record-list">{viewings.map((viewing) => <div className="record-row" key={viewing.id}><div><strong>{viewing.listing_title || 'Viewing request'}</strong><small>{viewing.property_address || 'Property'}{viewing.unit_number ? ` · Apartment ${viewing.unit_number}` : ''}</small><small>{[viewing.area_name, viewing.district, viewing.division].filter(Boolean).join(' · ')}</small><small>Tenant: {viewing.tenant_name || 'Tenant'} · Proposed {new Date(viewing.proposed_time).toLocaleString()}</small></div><div className="button-row"><Status status={viewing.status} />{viewing.status === 'pending' && <><button className="secondary small-button" disabled={busy} onClick={() => onUpdate(viewing.id, 'declined')}>Decline</button><button className="primary small-button" disabled={busy} onClick={() => onUpdate(viewing.id, 'confirmed')}>Confirm</button><form className="inline-action" onSubmit={event => {
    event.preventDefault();
    const time = String(new FormData(event.currentTarget).get('alternative'));
    onUpdate(viewing.id, 'countered', new Date(time).toISOString());
  }}><label>Alternative time<input type="datetime-local" name="alternative" required /></label><button className="secondary small-button" disabled={busy}>Propose</button></form></>}</div></div>)}</div>}</section>;
}

function TenancyList({ tenancies, busy, onEnd }: { tenancies: Tenancy[]; busy: boolean; onEnd: (id: string) => void }) {
  return <section className="panel"><div className="panel-heading"><div><span className="step">TENANT PROFILE · RESIDENCE HISTORY</span><h2>My tenancies</h2><p>Ended tenancies remain visible as historical records. A future move creates a new tenancy instead of overwriting this history.</p></div><span className="panel-number">{tenancies.length}</span></div>{tenancies.length === 0 ? <Empty title="No tenancy records yet" text="Confirmed rental agreements will appear here." /> : <div className="record-list">{tenancies.map((tenancy) => <div className="record-row" key={tenancy.id}><div><strong>{tenancy.property_address || 'Property'}</strong><small>{formatLabel(tenancy.status)} · {tenancy.start_date}{tenancy.end_date ? ` to ${tenancy.end_date}` : ' · Current'}</small><small>৳{tenancy.rent.toLocaleString()} / month · Rent due day {tenancy.rent_due_day}</small></div><div className="button-row"><Status status={tenancy.status} />{tenancy.status === 'active' && <button className="secondary small-button" disabled={busy} onClick={() => onEnd(tenancy.id)}>Moved out</button>}</div></div>)}</div>}</section>;
}

function TenantRentPanel({ overview, busy, onPay, onRefresh }: { overview: RentOverview | null; busy: boolean; onPay: (invoiceId: string, report: RentPaymentReport) => void; onRefresh: () => void }) {
  const [reporting, setReporting] = useState(false);
  const [paymentMethod, setPaymentMethod] = useState('Mobile banking');
  const [paymentNote, setPaymentNote] = useState('');
  if (!overview || !overview.active) {
    return <section className="panel"><div className="panel-heading"><div><span className="step">TENANT WORKSPACE · RENT</span><h2>Monthly rent</h2><p>Your current home and rent payments appear here once you have an active tenancy.</p></div><button className="secondary small-button" onClick={onRefresh}>Refresh</button></div><Empty title="No active tenancy" text="When a landlord accepts your rental offer, your monthly rent will show up here." /></section>;
  }
  const periodLabel = overview.period_month ? new Date(overview.period_month).toLocaleDateString(undefined, { month: 'long', year: 'numeric' }) : 'This month';
  const invoice = overview.invoice;
  const rent = Number(overview.monthly_rent || 0);
  return (
    <section className="panel">
      <div className="panel-heading"><div><span className="step">TENANT WORKSPACE · RENT</span><h2>Monthly rent</h2><p>Pay your rent for {periodLabel} and review your outstanding balance.</p></div><button className="secondary small-button" onClick={onRefresh}>Refresh</button></div>
      <div className="stats" style={{ marginTop: 0 }}>
        <Stat icon="building" title={overview.property_address || 'Current home'} text={`${formatLabel(overview.property_type || 'Home')} · ৳${rent.toLocaleString()}/month`} />
        <Stat icon="calendar" title={`Day ${overview.rent_due_day ?? 1}`} text="Rent due day" />
        <Stat icon={overview.paid_current_period ? 'check' : 'card'} title={overview.paid_current_period ? 'Paid' : `৳${rent.toLocaleString()}`} text={overview.paid_current_period ? `${periodLabel} settled` : `${periodLabel} outstanding`} />
      </div>
      <div className="record-list" style={{ marginTop: 16 }}>
        <div className="record-row">
          <div>
            <strong>{periodLabel} rent</strong>
            <small>{invoice ? `Invoice ${invoice.id.slice(0, 8)} · ${formatLabel(invoice.status)}` : 'No invoice raised yet'}</small>
            <small>Outstanding this month: ৳{Number(overview.outstanding || 0).toLocaleString()} · Total paid: ৳{Number(overview.total_paid || 0).toLocaleString()}</small>
          </div>
          <div className="record-actions">
            {overview.paid_current_period ? <span className="status status-active">Paid</span> : invoice?.status === 'submitted' ? <span className="status status-pending">Awaiting landlord confirmation</span> : invoice?.status === 'pending' ? <button className="primary small-button" disabled={busy} onClick={() => setReporting(true)}>Report payment</button> : invoice ? <span className={`status status-${invoice.status}`}>{formatLabel(invoice.status)}</span> : <span className="status status-pending">Awaiting invoice</span>}
          </div>
        </div>
        {invoice?.status === 'submitted' && <div className="alert success">Your payment report was sent to the landlord. It will only count as paid after they confirm receipt.</div>}
        {invoice?.status === 'pending' && reporting && <form className="form-grid" onSubmit={(event) => { event.preventDefault(); onPay(invoice.id, { payment_method: paymentMethod, note: paymentNote || undefined }); setPaymentNote(''); setReporting(false); }}>
          <label>Payment method<select value={paymentMethod} onChange={(event) => setPaymentMethod(event.target.value)}><option>Mobile banking</option><option>Bank transfer</option><option>Cash</option><option>Other</option></select></label>
          <label>Transaction reference or note<input value={paymentNote} maxLength={500} onChange={(event) => setPaymentNote(event.target.value)} placeholder="Optional reference for your landlord" /></label>
          <div className="wide form-actions"><button className="primary" disabled={busy}>Submit payment report</button><button type="button" className="secondary" disabled={busy} onClick={() => setReporting(false)}>Cancel</button></div>
          <p className="wide">Reporting a payment does not mark the rent paid. Your landlord must confirm receipt.</p>
        </form>}
      </div>
    </section>
  );
}

function LandlordRentPanel({ rows, busy, onGenerate, onConfirm, onRefresh }: { rows: LandlordRentRow[]; busy: boolean; onGenerate: (tenancyId: string) => void; onConfirm: (invoiceId: string) => void; onRefresh: () => void }) {
  const periodLabel = rows[0]?.period_month ? new Date(rows[0].period_month).toLocaleDateString(undefined, { month: 'long', year: 'numeric' }) : 'This month';
  return (
    <section className="panel">
      <div className="panel-heading"><div><span className="step">LANDLORD WORKSPACE · RENT</span><h2>Monthly rent</h2><p>Raise {periodLabel} rent invoices for your active tenancies and track payments.</p></div><button className="secondary small-button" onClick={onRefresh}>Refresh</button></div>
      {rows.length === 0 ? <Empty title="No active tenancies" text="When a tenant accepts your rental offer, their monthly rent will appear here." /> : (
        <div className="record-list">
          {rows.map((row) => (
            <div className="record-row" key={row.tenancy_id}>
              <div>
                <strong>{row.property_address || 'Property'}</strong>
                <small>{row.tenant_name || 'Tenant'} · ৳{Number(row.monthly_rent).toLocaleString()}/month · due day {row.rent_due_day}</small>
                <small>{periodLabel}: {row.invoice_status === 'none' ? 'no invoice raised' : formatLabel(row.invoice_status)}</small>
                {row.invoice_status === 'submitted' && <small>Reported paid {row.paid_on || 'date not provided'} by {row.payment_method || 'unspecified method'}{row.payment_note ? ` · Reference: ${row.payment_note}` : ''}</small>}
              </div>
              <div className="record-actions">
                {row.invoice_status === 'none' ? <button className="primary small-button" disabled={busy} onClick={() => onGenerate(row.tenancy_id)}>Raise rent</button> : row.invoice_status === 'submitted' && row.invoice_id ? <button className="primary small-button" disabled={busy} onClick={() => { if (row.invoice_id) onConfirm(row.invoice_id); }}>Confirm receipt</button> : <span className={`status status-${row.invoice_status === 'accepted' ? 'active' : 'pending'}`}>{row.invoice_status === 'accepted' ? 'Paid' : row.invoice_status === 'pending' ? 'Awaiting tenant payment' : formatLabel(row.invoice_status)}</span>}
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function TenantRentalOfferList({ offers, listings, busy, onCreate, onRefresh, onTenantRespond }: { offers: RentalOffer[]; listings: AvailableListing[]; busy: boolean; onCreate: (listingId: string, proposedRent: number, moveInDate: string, message?: string) => void; onRefresh: () => void; onTenantRespond: (offerId: string, action: 'accept' | 'counter' | 'withdraw', counterRent?: number, responseMessage?: string) => void }) {
  const [openCreate, setOpenCreate] = useState(false);
  const [formListing, setFormListing] = useState('');
  const [formRent, setFormRent] = useState(0);
  const [formMoveIn, setFormMoveIn] = useState('');
  const [formMessage, setFormMessage] = useState('');
  function openNew() {
    setOpenCreate(true);
    if (!formListing && listings.length > 0) { setFormListing(listings[0].id); setFormRent(listings[0].monthly_rent); }
  }
  return (
    <section className="panel">
      <div className="panel-heading">
        <div>
          <span className="step">TENANT WORKSPACE · RENTAL OFFERS</span>
          <h2>My rental offers</h2>
          <p>Make an offer on a home. Landlords can accept, reject, or counter with a different rent.</p>
        </div>
        <div className="button-row">
          <button className="secondary small-button" onClick={onRefresh}>Refresh</button>
          <button className="primary small-button" onClick={openNew}>New offer</button>
        </div>
        <span className="panel-number">{offers.filter((o) => o.status === 'pending' || o.status === 'countered').length}</span>
      </div>
      {openCreate && (
        <div className="form-grid" style={{ marginBottom: 16 }}>
          <label>Home<select name="listing_id" value={formListing} onChange={(e) => { setFormListing(e.target.value); const l = listings.find((x) => x.id === e.target.value); if (l) setFormRent(l.monthly_rent); }} required>
            <option value="" disabled>Select an available home</option>
            {listings.map((l) => <option key={l.id} value={l.id}>{l.property_address}{l.unit_number ? ` · Apt ${l.unit_number}` : ''} — ৳{l.monthly_rent.toLocaleString()}/mo</option>)}
          </select></label>
          <label>Proposed monthly rent (৳)<input name="rent" type="number" min="1" value={formRent || ''} onChange={(e) => setFormRent(Number(e.target.value))} required /></label>
          <label>Move-in date<input name="move_in_date" type="date" value={formMoveIn} onChange={(e) => setFormMoveIn(e.target.value)} required /></label>
          <label>Message to landlord<textarea name="message" rows={3} value={formMessage} onChange={(e) => setFormMessage(e.target.value)} /></label>
          <div className="wide form-actions">
            <button type="button" className="secondary" onClick={() => setOpenCreate(false)}>Cancel</button>
            <button type="button" className="primary" disabled={busy || !formListing || !formRent || !formMoveIn} onClick={() => { onCreate(formListing, formRent, formMoveIn, formMessage || undefined); setOpenCreate(false); setFormListing(''); setFormRent(0); setFormMoveIn(''); setFormMessage(''); }}>Create offer</button>
          </div>
        </div>
      )}
      {offers.length === 0 ? (
        <Empty title="No rental offers yet" text="Browse listings and make an offer on a home you want to rent." />
      ) : (
        <div className="record-list">
          {offers.map((offer) => (
            <div className="record-row" key={offer.id}>
              <div>
                <strong>{offer.listing_title || 'Listing'}</strong>
                <small>{offer.property_address || 'Property'} · {offer.landlord_name || 'Landlord'}</small>
                <small>Your offer: ৳{offer.proposed_rent.toLocaleString()}/month · Move in {new Date(offer.move_in_date).toLocaleDateString()}</small>
                {offer.status === 'countered' && <small>Landlord counter: ৳{(offer.counter_rent || 0).toLocaleString()}/month{offer.landlord_response ? ` · "${offer.landlord_response}"` : ''}</small>}
              </div>
              <div className="record-actions">
                <Status status={offer.status} />
                {(offer.status === 'pending' || offer.status === 'countered') && <button className="secondary small-button" disabled={busy} onClick={() => onTenantRespond(offer.id, 'withdraw')}>Withdraw</button>}
                {offer.status === 'countered' && <button className="primary small-button" disabled={busy} onClick={() => onTenantRespond(offer.id, 'accept')}>Accept counter</button>}
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function LandlordRentalOfferList({ offers, busy, onRespond, onRefresh }: { offers: RentalOffer[]; busy: boolean; onRespond: (offerId: string, action: 'accept' | 'reject' | 'counter', counterRent?: number, responseMessage?: string) => void; onRefresh: () => void }) {
  const [respondOpen, setRespondOpen] = useState<string | null>(null);
  const [respondAction, setRespondAction] = useState<'accept' | 'reject' | 'counter'>('accept');
  const [respondRent, setRespondRent] = useState(0);
  const [respondMessage, setRespondMessage] = useState('');
  const offer = offers.find((o) => o.id === respondOpen);
  return (
    <section className="panel">
      <div className="panel-heading">
        <div>
          <span className="step">LANDLORD WORKSPACE · RENTAL OFFERS</span>
          <h2>Offers on your listings</h2>
          <p>Tenants have made offers on your properties. Accept, reject, or counter with your preferred rent.</p>
        </div>
        <button className="secondary small-button" onClick={onRefresh}>Refresh</button>
        <span className="panel-number">{offers.filter((o) => o.status === 'pending' || o.status === 'countered').length}</span>
      </div>
      {offers.length === 0 ? (
        <Empty title="No offers yet" text="Offers from tenants on your published listings will appear here." />
      ) : (
        <div className="record-list">
          {offers.map((offer) => (
            <div className="record-row" key={offer.id}>
              <div>
                <strong>{offer.tenant_name || 'Tenant'}</strong>
                <small>{offer.listing_title || 'Listing'} · {offer.property_address || 'Property'}</small>
                <small>Offer: ৳{offer.proposed_rent.toLocaleString()}/month · Move in {new Date(offer.move_in_date).toLocaleDateString()}{offer.message ? ` · "${offer.message}"` : ''}</small>
              </div>
              <div className="record-actions">
                <Status status={offer.status} />
                {offer.status === 'pending' && (
                  <>
                    <button className="secondary small-button" disabled={busy} onClick={() => { setRespondOpen(offer.id); setRespondAction('reject'); }}>Reject</button>
                    <button className="primary small-button" disabled={busy} onClick={() => { setRespondOpen(offer.id); setRespondAction('accept'); }}>Accept</button>
                    <button className="outline secondary small-button" disabled={busy} onClick={() => { setRespondOpen(offer.id); setRespondAction('counter'); setRespondRent(offer.counter_rent || offer.proposed_rent); }}>Counter</button>
                  </>
                )}
                {offer.status === 'countered' && <span className="tone-amber">Countered at ৳{offer.counter_rent?.toLocaleString()}</span>}
              </div>
            </div>
          ))}
        </div>
      )}
      {respondOpen && offer && (
        <div className="form-grid" style={{ marginTop: 12, borderTop: '1px solid var(--ink-200)', paddingTop: 12 }}>
          <label>Action<select name="action" value={respondAction} onChange={(e) => setRespondAction(e.target.value as any)}>
            <option value="accept">Accept</option>
            <option value="reject">Reject</option>
            <option value="counter">Counter with different rent</option>
          </select></label>
          {respondAction === 'counter' && (
            <label>Counter rent (৳)<input name="counter_rent" type="number" defaultValue={respondRent} onChange={(e) => setRespondRent(Number(e.target.value))} required /></label>
          )}
          <label>Response message<textarea name="message" defaultValue={respondMessage} onChange={(e) => setRespondMessage(e.target.value)} /></label>
          <div className="wide form-actions">
            <button className="outline secondary" onClick={() => setRespondOpen(null)}>Cancel</button>
            <button className="primary" disabled={busy || (respondAction === 'counter' && !respondRent)} onClick={() => {
              onRespond(offer.id, respondAction, respondAction === 'counter' ? respondRent : undefined, respondMessage || undefined);
              setRespondOpen(null);
            }}>{respondAction === 'counter' ? 'Send counter' : respondAction === 'accept' ? 'Accept offer' : 'Reject offer'}</button>
          </div>
        </div>
      )}
    </section>
  );
}

const ICONS: Record<string, ReactElement> = {
  menu: <path d="M4 6h16M4 12h16M4 18h16" />,
  home: <><path d="M3 10.5 12 3l9 7.5V21a1 1 0 0 1-1 1h-5v-7H9v7H4a1 1 0 0 1-1-1z" /></>,
  inbox: <><path d="M5 5h14l2 8v5a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1v-5z" /><path d="M3 13h5l2 3h4l2-3h5" /></>,
  'message-circle': <><path d="M20 11.5a7.5 7.5 0 0 1-7.5 7.5H5l-2 2v-6a7.5 7.5 0 1 1 17-3.5z" /><path d="M8 11h.01M12 11h.01M16 11h.01" /></>,
  award: <><circle cx="12" cy="8" r="5" /><path d="M8.5 12.5 7 21l5-3 5 3-1.5-8.5" /></>,
  shield: <><path d="M12 3 5 6v6c0 4 3 7 7 9 4-2 7-5 7-9V6z" /><path d="m9 12 2 2 4-4" /></>,
  users: <><circle cx="9.5" cy="7" r="3.5" /><path d="M4 20v-1.5a5 5 0 0 1 5-5h1a5 5 0 0 1 5 5V20" /><path d="M17 4.2a3.5 3.5 0 0 1 0 6.6" /></>,
  building: <><path d="M4 21V5a2 2 0 0 1 2-2h6a2 2 0 0 1 2 2v16" /><path d="M14 9h4a2 2 0 0 1 2 2v10" /><path d="M8 7h2M8 11h2M8 15h2" /></>,
  layers: <><path d="m12 3 9 5-9 5-9-5z" /><path d="m3 13 9 5 9-5" /></>,
  tag: <><path d="M20 12 12 20 4 12V4h8z" /><circle cx="8" cy="8" r="1.4" /></>,
  calendar: <><rect x="3" y="5" width="18" height="16" rx="2" /><path d="M3 9h18M8 3v4M16 3v4" /></>,
  card: <><rect x="2" y="5" width="20" height="14" rx="2" /><path d="M2 10h20" /></>,
  'file-plus': <><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" /><path d="M14 3v5h5M12 12v6M9 15h6" /></>,
  'file-text': <><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" /><path d="M14 3v5h5M9 13h6M9 17h6" /></>,
  files: <><path d="M8 3h6l4 4v10a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z" /><path d="M14 3v4h4" /></>,
  'map-pin': <><path d="M12 21s7-6 7-11a7 7 0 1 0-14 0c0 5 7 11 7 11z" /><circle cx="12" cy="10" r="2.5" /></>,
  search: <><circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" /></>,
  key: <><circle cx="7.5" cy="16.5" r="3.5" /><path d="M10 14 20 4M17 4l3 3M15 6l3 3" /></>,
  'log-out': <><path d="M15 12H3" /><path d="m7 8-4 4 4 4" /><path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4" /></>,
  check: <><path d="m5 12 4.5 4.5L19 7" /></>,
  radar: <><circle cx="12" cy="12" r="9" /><circle cx="12" cy="12" r="4" /><path d="M12 12 19 5" /></>,
  grid: <><rect x="3" y="3" width="7" height="7" rx="1.5" /><rect x="14" y="3" width="7" height="7" rx="1.5" /><rect x="3" y="14" width="7" height="7" rx="1.5" /><rect x="14" y="14" width="7" height="7" rx="1.5" /></>,
  badge: <><path d="M12 3 4 6v6c0 4.5 3.4 7.6 8 9 4.6-1.4 8-4.5 8-9V6z" /><path d="m9 12 2 2 4-4" /></>,
  plus: <><path d="M12 5v14M5 12h14" /></>,
  gear: <><circle cx="12" cy="12" r="3" /><path d="M12 2v3M12 19v3M4.2 4.2l2.1 2.1M17.7 17.7l2.1 2.1M2 12h3M19 12h3M4.2 19.8l2.1-2.1M17.7 6.3l2.1-2.1" /></>,
  user: <><circle cx="12" cy="8" r="4" /><path d="M4 21a8 8 0 0 1 16 0" /></>,
  chart: <><path d="M4 20V10M10 20V4M16 20v-7M22 20H2" /></>,
};

function Icon({ name }: { name: string }) {
  const path = ICONS[name];
  if (!path) return <span aria-hidden="true">{name}</span>;
  return <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{path}</svg>;
}

function Brand() { return <div className="brand"><img className="brand-mark" src={logoImage} alt="CTRx logo" /><div><strong>CTRx</strong><span>Central Tenant Records</span></div></div>; }
function Stat({ icon, title, text }: { icon: string; tone?: string; title: string; text: string }) { return <div className="stat-card"><span className="stat-icon"><Icon name={icon} /></span><div><strong>{title}</strong><span>{text}</span></div></div>; }
function Status({ status }: { status: string }) { return <span className={`status status-${status}`}>{formatStatus(status)}</span>; }
function Empty({ title, text }: { title: string; text: string }) { return <div className="empty-state"><div className="empty-icon"><Icon name="inbox" /></div><strong>{title}</strong><p>{text}</p></div>; }

export default App;

