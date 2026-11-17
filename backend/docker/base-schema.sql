-- Reviewed schema-only snapshot from ctrx.backup; baseline 20261127_rent_confirmation.
--
-- PostgreSQL database dump
--



SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: btree_gist; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS btree_gist WITH SCHEMA public;


--
-- Name: EXTENSION btree_gist; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION btree_gist IS 'support for indexing common datatypes in GiST';


--
-- Name: citext; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS citext WITH SCHEMA public;


--
-- Name: EXTENSION citext; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION citext IS 'data type for case-insensitive character strings';


--
-- Name: pgcrypto; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA public;


--
-- Name: EXTENSION pgcrypto; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION pgcrypto IS 'cryptographic functions';


--
-- Name: dispute_status; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.dispute_status AS ENUM (
    'open',
    'under_review',
    'resolved',
    'rejected'
);


--
-- Name: grant_scope; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.grant_scope AS ENUM (
    'tenancy_history',
    'payment_history',
    'reliability_score',
    'ric_certificate'
);


--
-- Name: household_member_role; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.household_member_role AS ENUM (
    'primary_holder',
    'member'
);


--
-- Name: ledger_entry_type; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.ledger_entry_type AS ENUM (
    'payment',
    'correction'
);


--
-- Name: listing_status; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.listing_status AS ENUM (
    'draft',
    'available',
    'rented',
    'withdrawn'
);


--
-- Name: official_level; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.official_level AS ENUM (
    'local',
    'central'
);


--
-- Name: payment_status; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.payment_status AS ENUM (
    'pending',
    'accepted',
    'rejected',
    'cancelled',
    'submitted'
);


--
-- Name: property_type; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.property_type AS ENUM (
    'apartment',
    'house',
    'room',
    'studio',
    'duplex',
    'other'
);


--
-- Name: rental_offer_status; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.rental_offer_status AS ENUM (
    'pending',
    'countered',
    'accepted',
    'rejected',
    'withdrawn',
    'expired'
);


--
-- Name: ric_app_status; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.ric_app_status AS ENUM (
    'pending_local',
    'pending_central',
    'approved',
    'rejected_local',
    'rejected_central'
);


--
-- Name: ric_status; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.ric_status AS ENUM (
    'active',
    'expired',
    'revoked'
);


--
-- Name: score_event_type; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.score_event_type AS ENUM (
    'on_time',
    'late',
    'missed',
    'correction'
);


--
-- Name: tenancy_status; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.tenancy_status AS ENUM (
    'active',
    'ended',
    'terminated'
);


--
-- Name: user_role; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.user_role AS ENUM (
    'tenant',
    'landlord',
    'government',
    'admin'
);


--
-- Name: viewing_status; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.viewing_status AS ENUM (
    'pending',
    'countered',
    'confirmed',
    'declined',
    'expired',
    'cancelled'
);


--
-- Name: applicant_belongs_to_ric(text, character); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.applicant_belongs_to_ric(p_identity_hmac text, p_ric_number character) RETURNS uuid
    LANGUAGE sql STABLE
    AS $$
    SELECT c.id
      FROM rental_identity_certificates c
      JOIN household_members m ON m.household_id = c.household_id AND m.left_at IS NULL
      JOIN persons p ON p.id = m.person_id
     WHERE c.ric_number = p_ric_number
       AND c.status <> 'revoked'
       AND p.identity_number_hmac = p_identity_hmac
     LIMIT 1;
$$;


--
-- Name: check_household_has_primary(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.check_household_has_primary() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
    v_household UUID;
BEGIN
    IF TG_OP = 'DELETE' THEN
        v_household := OLD.household_id;
    ELSE
        v_household := NEW.household_id;
    END IF;

    IF EXISTS (SELECT 1 FROM household_members
                WHERE household_id = v_household AND left_at IS NULL)
       AND NOT EXISTS (SELECT 1 FROM household_members
                WHERE household_id = v_household AND left_at IS NULL
                  AND member_role = 'primary_holder') THEN
        RAISE EXCEPTION 'household % has active members but no primary holder', v_household;
    END IF;
    RETURN NULL;
END;
$$;


--
-- Name: expire_stale_viewings(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.expire_stale_viewings() RETURNS integer
    LANGUAGE plpgsql
    AS $$
DECLARE
    n INT;
BEGIN
    UPDATE viewing_requests
       SET status = 'expired', responded_at = COALESCE(responded_at, now())
     WHERE status IN ('pending','countered') AND expires_at <= now();
    GET DIAGNOSTICS n = ROW_COUNT;
    RETURN n;
END;
$$;


--
-- Name: forbid_mutation(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.forbid_mutation() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    RAISE EXCEPTION '% on % is not allowed: table is append-only',
        TG_OP, TG_TABLE_NAME;
END;
$$;


--
-- Name: generate_ric_number(integer); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.generate_ric_number(p_area_id integer) RETURNS character
    LANGUAGE plpgsql
    AS $$
DECLARE
    v_division_code CHAR(2);
    v_district_code CHAR(2);
    v_upazila_code  CHAR(3);
    v_sequence      INT;
BEGIN
    SELECT division_code, district_code, upazila_code
      INTO v_division_code, v_district_code, v_upazila_code
      FROM areas WHERE id = p_area_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Unknown area_id: %', p_area_id;
    END IF;

    INSERT INTO ric_counters(area_id) VALUES (p_area_id)
    ON CONFLICT (area_id) DO NOTHING;

    -- Row lock serializes concurrent approvals for the same area.
    SELECT next_value INTO v_sequence
      FROM ric_counters WHERE area_id = p_area_id FOR UPDATE;

    IF v_sequence > 99999 THEN
        RAISE EXCEPTION 'RIC sequence exhausted for area_id %', p_area_id;
    END IF;

    UPDATE ric_counters SET next_value = v_sequence + 1 WHERE area_id = p_area_id;

    RETURN (v_division_code || v_district_code || v_upazila_code ||
            lpad(v_sequence::TEXT, 5, '0'))::CHAR(12);
END;
$$;


--
-- Name: guard_certificate_document(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.guard_certificate_document() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'certificate documents cannot be deleted';
    END IF;
    IF NEW.is_current AND NOT OLD.is_current THEN
        RAISE EXCEPTION 'a superseded document cannot become current again';
    END IF;
    IF (NEW.certificate_id, NEW.version, NEW.template_id, NEW.render_data,
        NEW.pdf_storage_key, NEW.pdf_sha256)
       IS DISTINCT FROM
       (OLD.certificate_id, OLD.version, OLD.template_id, OLD.render_data,
        OLD.pdf_storage_key, OLD.pdf_sha256) THEN
        RAISE EXCEPTION 'certificate document content is immutable';
    END IF;
    RETURN NEW;
END;
$$;


--
-- Name: guard_payment_request(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.guard_payment_request() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
        BEGIN
            IF OLD.status = 'pending' AND NEW.status IN ('pending', 'submitted', 'cancelled', 'rejected') THEN
                RETURN NEW;
            END IF;
            IF OLD.status = 'submitted' AND NEW.status IN ('accepted', 'rejected') THEN
                RETURN NEW;
            END IF;
            RAISE EXCEPTION 'payment_request % cannot transition from % to %',
                OLD.id, OLD.status, NEW.status;
        END;
        $$;


--
-- Name: guard_ric_application(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.guard_ric_application() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    IF OLD.status IN ('approved','rejected_local','rejected_central') THEN
        RAISE EXCEPTION 'application % is final (%), cannot modify', OLD.id, OLD.status;
    END IF;

    IF NEW.status = OLD.status THEN
        RETURN NEW;
    END IF;

    IF OLD.status = 'pending_local'
       AND NEW.status IN ('pending_central','rejected_local') THEN
        IF NOT EXISTS (
            SELECT 1 FROM official_profiles
             WHERE user_id = NEW.local_reviewed_by
               AND level = 'local'
               AND area_id = NEW.area_id) THEN
            RAISE EXCEPTION 'reviewer is not a local official for this application''s area';
        END IF;
        IF NEW.status = 'rejected_local'
           AND NULLIF(btrim(NEW.rejection_reason), '') IS NULL THEN
            RAISE EXCEPTION 'a written reason is required to reject an application';
        END IF;
    ELSIF OLD.status = 'pending_central'
          AND NEW.status IN ('approved','rejected_central','pending_local') THEN
        IF NOT EXISTS (
            SELECT 1 FROM official_profiles
             WHERE user_id = NEW.central_reviewed_by
               AND level = 'central') THEN
            RAISE EXCEPTION 'reviewer is not a central official';
        END IF;
        IF NEW.status = 'rejected_central'
           AND NULLIF(btrim(NEW.rejection_reason), '') IS NULL THEN
            RAISE EXCEPTION 'a written reason is required to reject an application';
        END IF;
        IF NEW.status = 'pending_local'
           AND NULLIF(btrim(NEW.central_note), '') IS NULL THEN
            RAISE EXCEPTION 'a written reason is required to return an application to local review';
        END IF;
    ELSE
        RAISE EXCEPTION 'invalid application transition % -> %', OLD.status, NEW.status;
    END IF;
    RETURN NEW;
END;
$$;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: rental_identity_certificates; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.rental_identity_certificates (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    ric_number character(12) NOT NULL,
    verify_token text DEFAULT encode(public.gen_random_bytes(16), 'hex'::text) NOT NULL,
    household_id uuid NOT NULL,
    application_id uuid NOT NULL,
    status public.ric_status DEFAULT 'active'::public.ric_status NOT NULL,
    issued_by uuid NOT NULL,
    issued_at timestamp with time zone DEFAULT now() NOT NULL,
    expires_at timestamp with time zone,
    revoked_at timestamp with time zone,
    revoked_by uuid,
    revocation_reason text,
    CONSTRAINT rental_identity_certificates_check CHECK (((expires_at IS NULL) OR (expires_at > issued_at))),
    CONSTRAINT rental_identity_certificates_check1 CHECK (((status <> 'revoked'::public.ric_status) OR ((revoked_at IS NOT NULL) AND (revoked_by IS NOT NULL) AND (revocation_reason IS NOT NULL)))),
    CONSTRAINT rental_identity_certificates_ric_number_check CHECK ((ric_number ~ '^[0-9]{12}$'::text))
);


--
-- Name: issue_certificate(uuid, uuid, uuid); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.issue_certificate(p_application_id uuid, p_household_id uuid, p_issued_by uuid) RETURNS public.rental_identity_certificates
    LANGUAGE plpgsql
    AS $$
DECLARE
    v_app   ric_applications%ROWTYPE;
    v_years INT;
    v_row   rental_identity_certificates;
BEGIN
    -- NFR-05: only a central official may issue.
    IF NOT EXISTS (SELECT 1 FROM official_profiles
                    WHERE user_id = p_issued_by AND level = 'central') THEN
        RAISE EXCEPTION 'issuer % is not a central official', p_issued_by;
    END IF;

    SELECT * INTO v_app FROM ric_applications WHERE id = p_application_id FOR UPDATE;
    IF NOT FOUND OR v_app.status <> 'approved' THEN
        RAISE EXCEPTION 'application % is not approved', p_application_id;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM households
                    WHERE id = p_household_id AND application_id = p_application_id) THEN
        RAISE EXCEPTION 'household % does not belong to application %',
            p_household_id, p_application_id;
    END IF;

    SELECT (value #>> '{}')::INT INTO v_years
      FROM system_settings
     WHERE key = 'certificate.validity_years' AND jsonb_typeof(value) = 'number';

    INSERT INTO rental_identity_certificates
        (ric_number, household_id, application_id, issued_by, expires_at)
    VALUES
        (generate_ric_number(v_app.area_id), p_household_id, p_application_id, p_issued_by,
         CASE WHEN v_years IS NULL THEN NULL
              ELSE now() + make_interval(years => v_years) END)
    RETURNING * INTO v_row;

    RETURN v_row;
END;
$$;


--
-- Name: notify_workspace_change(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.notify_workspace_change() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
        DECLARE recipient uuid; destination text; message text;
        BEGIN
            IF TG_OP = 'UPDATE' AND NEW.status = OLD.status THEN RETURN NEW; END IF;
            IF TG_TABLE_NAME = 'ric_applications' THEN
                SELECT id INTO recipient FROM users WHERE email = NEW.email AND role = 'tenant';
                destination := 'applications';
                message := 'RIC application: ' || replace(NEW.status::text, '_', ' ');
            ELSIF TG_TABLE_NAME = 'payment_requests' THEN
                destination := 'rent';
                IF NEW.status::text = 'submitted' THEN
                    SELECT landlord_id INTO recipient FROM tenancies WHERE id = NEW.tenancy_id;
                    message := 'A tenant reported a rent payment';
                ELSE
                    SELECT tenant_id INTO recipient FROM tenancies WHERE id = NEW.tenancy_id;
                    message := CASE NEW.status::text
                        WHEN 'pending' THEN 'A new rent invoice is available'
                        WHEN 'accepted' THEN 'Your rent payment was confirmed'
                        ELSE 'Rent invoice: ' || NEW.status::text END;
                END IF;
            ELSE
                recipient := NEW.tenant_id;
                destination := 'viewings';
                message := CASE NEW.status::text WHEN 'countered' THEN 'Your landlord proposed a new viewing time'
                    ELSE 'Viewing request: ' || NEW.status::text END;
            END IF;
            IF recipient IS NOT NULL THEN
                INSERT INTO workspace_notifications (recipient_id, destination, record_id, message)
                VALUES (recipient, destination, NEW.id, message);
            END IF;
            RETURN NEW;
        END;
        $$;


--
-- Name: prepare_tenancy_lease(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.prepare_tenancy_lease() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
        BEGIN
            INSERT INTO lease_agreements (tenancy_id, terms)
            SELECT NEW.id, jsonb_build_object('property', p.address_line, 'tenant', tp.full_name,
                'landlord', lp.full_name, 'start_date', NEW.start_date, 'monthly_rent', NEW.monthly_rent,
                'deposit', NEW.deposit, 'rent_due_day', NEW.rent_due_day)
            FROM properties p, tenant_profiles tp, landlord_profiles lp
            WHERE p.id = NEW.property_id AND tp.user_id = NEW.tenant_id AND lp.user_id = NEW.landlord_id
            ON CONFLICT (tenancy_id) DO NOTHING;
            RETURN NEW;
        END
        $$;


--
-- Name: certificate_documents; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.certificate_documents (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    certificate_id uuid NOT NULL,
    version integer NOT NULL,
    template_id uuid,
    renderer text,
    render_data jsonb NOT NULL,
    pdf_storage_key text NOT NULL,
    pdf_sha256 character(64) NOT NULL,
    file_size_bytes bigint,
    is_current boolean DEFAULT true NOT NULL,
    generated_by uuid,
    generated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT certificate_documents_version_check CHECK ((version > 0))
);


--
-- Name: register_certificate_document(uuid, uuid, text, jsonb, text, character, bigint, uuid); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.register_certificate_document(p_certificate_id uuid, p_template_id uuid, p_renderer text, p_render_data jsonb, p_pdf_storage_key text, p_pdf_sha256 character, p_file_size_bytes bigint, p_generated_by uuid) RETURNS public.certificate_documents
    LANGUAGE plpgsql
    AS $$
DECLARE
    v_next INT;
    v_row  certificate_documents;
BEGIN
    PERFORM 1 FROM rental_identity_certificates WHERE id = p_certificate_id FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'unknown certificate %', p_certificate_id;
    END IF;

    SELECT COALESCE(MAX(version), 0) + 1 INTO v_next
      FROM certificate_documents WHERE certificate_id = p_certificate_id;

    UPDATE certificate_documents SET is_current = FALSE
     WHERE certificate_id = p_certificate_id AND is_current;

    INSERT INTO certificate_documents
        (certificate_id, version, template_id, renderer, render_data,
         pdf_storage_key, pdf_sha256, file_size_bytes, generated_by)
    VALUES
        (p_certificate_id, v_next, p_template_id, p_renderer, p_render_data,
         p_pdf_storage_key, p_pdf_sha256, p_file_size_bytes, p_generated_by)
    RETURNING * INTO v_row;

    RETURN v_row;
END;
$$;


--
-- Name: set_updated_at(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.set_updated_at() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END;
$$;


--
-- Name: verify_ric(text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.verify_ric(p_token text) RETURNS TABLE(ric_number character, status text, issued_at timestamp with time zone, expires_at timestamp with time zone)
    LANGUAGE sql STABLE SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
    SELECT c.ric_number,
           CASE WHEN c.status = 'active'
                     AND c.expires_at IS NOT NULL AND c.expires_at <= now()
                THEN 'expired' ELSE c.status::TEXT END,
           c.issued_at,
           c.expires_at
      FROM rental_identity_certificates c
     WHERE c.verify_token = p_token;
$$;


--
-- Name: access_grants; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.access_grants (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    landlord_id uuid NOT NULL,
    scopes public.grant_scope[] NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    revoked_at timestamp with time zone,
    CONSTRAINT access_grants_check CHECK ((expires_at > created_at)),
    CONSTRAINT access_grants_scopes_check CHECK ((cardinality(scopes) > 0))
);


--
-- Name: account_profiles; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.account_profiles (
    user_id uuid NOT NULL,
    display_name character varying(100),
    contact_phone_enc bytea,
    photo bytea,
    appearance text DEFAULT 'light'::text NOT NULL,
    theme text DEFAULT 'teal'::text NOT NULL
);


--
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


--
-- Name: amenities; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.amenities (
    id integer NOT NULL,
    code text NOT NULL,
    label text NOT NULL
);


--
-- Name: amenities_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.amenities_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: amenities_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.amenities_id_seq OWNED BY public.amenities.id;


--
-- Name: application_documents; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.application_documents (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    application_id uuid NOT NULL,
    doc_type text NOT NULL,
    storage_key text NOT NULL,
    sha256 character(64) NOT NULL,
    mime_type text NOT NULL,
    uploaded_at timestamp with time zone DEFAULT now() NOT NULL,
    review_status text DEFAULT 'pending'::text NOT NULL,
    reviewed_by uuid,
    reviewed_at timestamp with time zone,
    review_note text,
    CONSTRAINT application_documents_review_status_check CHECK ((review_status = ANY (ARRAY['pending'::text, 'under_review'::text, 'approved'::text, 'rejected'::text])))
);


--
-- Name: application_members; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.application_members (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    application_id uuid NOT NULL,
    full_name text NOT NULL,
    relationship text,
    date_of_birth date,
    identity_number_enc bytea,
    identity_number_hmac text,
    identity_last4 character(4)
);


--
-- Name: areas; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.areas (
    id integer NOT NULL,
    division text NOT NULL,
    division_code character(2) NOT NULL,
    district text NOT NULL,
    district_code character(2) NOT NULL,
    name text NOT NULL,
    upazila_code character(3) NOT NULL,
    CONSTRAINT areas_district_code_check CHECK ((district_code ~ '^[0-9]{2}$'::text)),
    CONSTRAINT areas_division_code_check CHECK ((division_code ~ '^[0-9]{2}$'::text)),
    CONSTRAINT areas_upazila_code_check CHECK ((upazila_code ~ '^[0-9]{3}$'::text))
);


--
-- Name: areas_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.areas_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: areas_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.areas_id_seq OWNED BY public.areas.id;


--
-- Name: audit_logs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.audit_logs (
    id bigint NOT NULL,
    actor_id uuid,
    actor_role public.user_role,
    action text NOT NULL,
    entity_type text,
    entity_id uuid,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    ip_address inet,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: audit_logs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.audit_logs_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: audit_logs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.audit_logs_id_seq OWNED BY public.audit_logs.id;


--
-- Name: certificate_delivery_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.certificate_delivery_events (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    certificate_id uuid NOT NULL,
    document_id uuid,
    actor_id uuid,
    event_type text NOT NULL,
    delivery_channel text,
    recipient_email public.citext,
    success boolean DEFAULT true NOT NULL,
    failure_reason text,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT certificate_delivery_events_delivery_channel_check CHECK (((delivery_channel IS NULL) OR (delivery_channel = ANY (ARRAY['web'::text, 'email'::text, 'system'::text, 'other'::text])))),
    CONSTRAINT certificate_delivery_events_event_type_check CHECK ((event_type = ANY (ARRAY['generated'::text, 'regenerated'::text, 'downloaded'::text, 'emailed'::text, 'viewed'::text, 'delivery_failed'::text]))),
    CONSTRAINT chk_delivery_failure CHECK (((success = true) OR (failure_reason IS NOT NULL)))
);


--
-- Name: certificate_templates; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.certificate_templates (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    code text NOT NULL,
    version integer DEFAULT 1 NOT NULL,
    name text NOT NULL,
    renderer text DEFAULT 'backend'::text NOT NULL,
    config jsonb DEFAULT '{}'::jsonb NOT NULL,
    asset_storage_key text,
    is_default boolean DEFAULT false NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: consent_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.consent_events (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    access_grant_id uuid,
    tenant_id uuid NOT NULL,
    landlord_id uuid NOT NULL,
    event_type text NOT NULL,
    scopes public.grant_scope[] NOT NULL,
    actor_id uuid NOT NULL,
    reason text,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT consent_events_event_type_check CHECK ((event_type = ANY (ARRAY['granted'::text, 'revoked'::text, 'expired'::text]))),
    CONSTRAINT consent_events_scopes_check CHECK ((cardinality(scopes) > 0))
);


--
-- Name: dispute_timeline; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.dispute_timeline (
    id bigint NOT NULL,
    dispute_id uuid NOT NULL,
    actor_id uuid NOT NULL,
    kind text NOT NULL,
    message text NOT NULL,
    filename text,
    attachment bytea,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: dispute_timeline_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.dispute_timeline ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.dispute_timeline_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: disputes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.disputes (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    raised_by uuid NOT NULL,
    entity_type text NOT NULL,
    entity_id uuid NOT NULL,
    reason text NOT NULL,
    status public.dispute_status DEFAULT 'open'::public.dispute_status NOT NULL,
    resolution_note text,
    resolved_by uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    resolved_at timestamp with time zone,
    CONSTRAINT disputes_entity_type_check CHECK ((entity_type = ANY (ARRAY['ledger_entry'::text, 'payment_request'::text, 'tenancy'::text, 'reliability_score'::text, 'ric_application'::text, 'household'::text, 'certificate'::text])))
);


--
-- Name: household_members; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.household_members (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    household_id uuid NOT NULL,
    person_id uuid NOT NULL,
    member_role public.household_member_role DEFAULT 'member'::public.household_member_role NOT NULL,
    relationship text,
    joined_at timestamp with time zone DEFAULT now() NOT NULL,
    left_at timestamp with time zone,
    CONSTRAINT household_members_check CHECK (((left_at IS NULL) OR (left_at > joined_at)))
);


--
-- Name: households; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.households (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    application_id uuid NOT NULL,
    area_id integer NOT NULL,
    household_address text NOT NULL,
    permanent_address text,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: landlord_profiles; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.landlord_profiles (
    user_id uuid NOT NULL,
    full_name text NOT NULL,
    phone_enc bytea,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: lease_agreements; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.lease_agreements (
    tenancy_id uuid NOT NULL,
    terms jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    tenant_acknowledged_at timestamp with time zone,
    landlord_acknowledged_at timestamp with time zone
);


--
-- Name: ledger_entries; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ledger_entries (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenancy_id uuid NOT NULL,
    payment_request_id uuid,
    entry_type public.ledger_entry_type NOT NULL,
    amount numeric(12,2) NOT NULL,
    period_month date NOT NULL,
    paid_on date NOT NULL,
    corrects_entry_id uuid,
    reason text,
    actor_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ledger_entries_check CHECK ((((entry_type = 'payment'::public.ledger_entry_type) AND (payment_request_id IS NOT NULL) AND (corrects_entry_id IS NULL) AND (amount > (0)::numeric)) OR ((entry_type = 'correction'::public.ledger_entry_type) AND (corrects_entry_id IS NOT NULL) AND (amount <> (0)::numeric) AND (reason IS NOT NULL) AND (length(TRIM(BOTH FROM reason)) > 0)))),
    CONSTRAINT ledger_entries_period_month_check CHECK ((EXTRACT(day FROM period_month) = (1)::numeric))
);


--
-- Name: listings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.listings (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    property_id uuid NOT NULL,
    status public.listing_status DEFAULT 'draft'::public.listing_status NOT NULL,
    title text,
    description text,
    published_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    unit_id uuid
);


--
-- Name: media_files; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.media_files (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    storage_key text NOT NULL,
    original_filename text,
    mime_type text NOT NULL,
    file_size_bytes bigint NOT NULL,
    width integer,
    height integer,
    sha256 character(64) NOT NULL,
    uploaded_by uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    deleted_at timestamp with time zone,
    CONSTRAINT media_files_file_size_bytes_check CHECK ((file_size_bytes > 0)),
    CONSTRAINT media_files_height_check CHECK ((height > 0)),
    CONSTRAINT media_files_mime_type_check CHECK ((mime_type = ANY (ARRAY['image/jpeg'::text, 'image/png'::text, 'image/webp'::text]))),
    CONSTRAINT media_files_sha256_check CHECK ((sha256 ~ '^[0-9a-f]{64}$'::text)),
    CONSTRAINT media_files_width_check CHECK ((width > 0))
);


--
-- Name: notifications; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.notifications (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id uuid NOT NULL,
    notification_type text NOT NULL,
    title text NOT NULL,
    message text NOT NULL,
    entity_type text,
    entity_id uuid,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    is_read boolean DEFAULT false NOT NULL,
    read_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT chk_notification_read CHECK ((((is_read = false) AND (read_at IS NULL)) OR ((is_read = true) AND (read_at IS NOT NULL)))),
    CONSTRAINT notifications_notification_type_check CHECK ((notification_type = ANY (ARRAY['application_submitted'::text, 'application_forwarded'::text, 'application_approved'::text, 'application_rejected'::text, 'document_reviewed'::text, 'certificate_issued'::text, 'certificate_ready'::text, 'payment_update'::text, 'viewing_update'::text, 'system'::text, 'other'::text])))
);


--
-- Name: official_profiles; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.official_profiles (
    user_id uuid NOT NULL,
    full_name text NOT NULL,
    designation text,
    level public.official_level NOT NULL,
    area_id integer,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT official_profiles_check CHECK ((((level = 'local'::public.official_level) AND (area_id IS NOT NULL)) OR ((level = 'central'::public.official_level) AND (area_id IS NULL))))
);


--
-- Name: password_reset_tokens; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.password_reset_tokens (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id uuid,
    email_digest character varying(64) NOT NULL,
    token_digest character varying(64),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    used_at timestamp with time zone
);


--
-- Name: payment_requests; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.payment_requests (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenancy_id uuid NOT NULL,
    requested_by uuid NOT NULL,
    amount numeric(12,2) NOT NULL,
    period_month date NOT NULL,
    paid_on date NOT NULL,
    payment_method text,
    note text,
    status public.payment_status DEFAULT 'pending'::public.payment_status NOT NULL,
    rejection_reason text,
    submitted_at timestamp with time zone DEFAULT now() NOT NULL,
    decided_at timestamp with time zone,
    decided_by uuid,
    description text,
    CONSTRAINT payment_requests_amount_check CHECK ((amount > (0)::numeric)),
    CONSTRAINT payment_requests_check CHECK (((status <> 'rejected'::public.payment_status) OR (rejection_reason IS NOT NULL))),
    CONSTRAINT payment_requests_check1 CHECK (((decided_by IS DISTINCT FROM requested_by) OR ((status = 'accepted'::public.payment_status) AND (payment_method IS NOT NULL)))),
    CONSTRAINT payment_requests_period_month_check CHECK ((EXTRACT(day FROM period_month) = (1)::numeric))
);


--
-- Name: persons; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.persons (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    full_name text NOT NULL,
    identity_number_enc bytea,
    identity_number_hmac text,
    identity_last4 character(4),
    date_of_birth date,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: photos; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.photos (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    media_id uuid NOT NULL,
    user_id uuid,
    person_id uuid,
    property_id uuid,
    photo_type text NOT NULL,
    is_primary boolean DEFAULT false NOT NULL,
    verification_status text DEFAULT 'unverified'::text NOT NULL,
    verified_by uuid,
    verified_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT chk_photo_owner CHECK ((num_nonnulls(user_id, person_id, property_id) = 1)),
    CONSTRAINT chk_photo_verification CHECK (((verification_status <> 'verified'::text) OR ((verified_by IS NOT NULL) AND (verified_at IS NOT NULL)))),
    CONSTRAINT photos_photo_type_check CHECK ((photo_type = ANY (ARRAY['profile'::text, 'identity'::text, 'verification'::text, 'property'::text, 'other'::text]))),
    CONSTRAINT photos_verification_status_check CHECK ((verification_status = ANY (ARRAY['unverified'::text, 'pending'::text, 'verified'::text, 'rejected'::text])))
);


--
-- Name: properties; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.properties (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    landlord_id uuid NOT NULL,
    area_id integer NOT NULL,
    address_line text NOT NULL,
    property_type public.property_type NOT NULL,
    monthly_rent numeric(12,2) NOT NULL,
    floor_area_sqft numeric(8,2) NOT NULL,
    bedrooms smallint NOT NULL,
    bathrooms smallint NOT NULL,
    floor_number smallint NOT NULL,
    available_from date NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT properties_bathrooms_check CHECK ((bathrooms >= 0)),
    CONSTRAINT properties_bedrooms_check CHECK ((bedrooms >= 0)),
    CONSTRAINT properties_floor_area_sqft_check CHECK ((floor_area_sqft > (0)::numeric)),
    CONSTRAINT properties_monthly_rent_check CHECK ((monthly_rent > (0)::numeric))
);


--
-- Name: property_amenities; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.property_amenities (
    property_id uuid NOT NULL,
    amenity_id integer NOT NULL,
    value text
);


--
-- Name: property_units; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.property_units (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    property_id uuid NOT NULL,
    unit_number character varying(40) NOT NULL,
    floor_number smallint DEFAULT '0'::smallint NOT NULL,
    monthly_rent numeric(12,2) NOT NULL,
    floor_area_sqft numeric(8,2) NOT NULL,
    bedrooms smallint DEFAULT '0'::smallint NOT NULL,
    bathrooms smallint DEFAULT '0'::smallint NOT NULL,
    available_from date NOT NULL,
    status character varying(20) DEFAULT 'available'::character varying NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: reliability_score_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.reliability_score_events (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    score_id uuid NOT NULL,
    ledger_entry_id uuid,
    tenancy_id uuid,
    event_type public.score_event_type NOT NULL,
    points_delta numeric(6,2) NOT NULL,
    description text,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: reliability_scores; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.reliability_scores (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    score smallint,
    has_history boolean DEFAULT false NOT NULL,
    model_version text DEFAULT 'v1'::text NOT NULL,
    computed_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT reliability_scores_score_check CHECK (((score >= 0) AND (score <= 100)))
);


--
-- Name: rental_history_grants; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.rental_history_grants (
    id bigint NOT NULL,
    tenant_id uuid NOT NULL,
    landlord_id uuid NOT NULL,
    categories text[] NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    revoked_at timestamp with time zone
);


--
-- Name: rental_history_grants_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.rental_history_grants ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.rental_history_grants_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: rental_offers; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.rental_offers (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    listing_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    landlord_id uuid NOT NULL,
    proposed_rent numeric(12,2) NOT NULL,
    counter_rent numeric(12,2),
    status public.rental_offer_status DEFAULT 'pending'::public.rental_offer_status NOT NULL,
    move_in_date date NOT NULL,
    message text,
    landlord_response text,
    tenant_response text,
    expires_at timestamp with time zone NOT NULL,
    responded_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: ric_application_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ric_application_events (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    application_id uuid NOT NULL,
    actor_id uuid,
    event_type text NOT NULL,
    previous_status public.ric_app_status,
    new_status public.ric_app_status,
    note text,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ric_application_events_event_type_check CHECK ((event_type = ANY (ARRAY['submitted'::text, 'document_uploaded'::text, 'document_reviewed'::text, 'reviewed_local'::text, 'forwarded_central'::text, 'reviewed_central'::text, 'approved'::text, 'rejected_local'::text, 'rejected_central'::text, 'resubmitted'::text, 'note_added'::text, 'other'::text])))
);


--
-- Name: ric_applications; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ric_applications (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    email public.citext NOT NULL,
    full_name text NOT NULL,
    identity_number_enc bytea NOT NULL,
    identity_number_hmac text NOT NULL,
    identity_last4 character(4),
    date_of_birth date,
    permanent_address text,
    household_address text NOT NULL,
    area_id integer NOT NULL,
    previous_ric_id uuid,
    status public.ric_app_status DEFAULT 'pending_local'::public.ric_app_status NOT NULL,
    resubmission_of uuid,
    submitted_at timestamp with time zone DEFAULT now() NOT NULL,
    local_reviewed_by uuid,
    local_reviewed_at timestamp with time zone,
    local_note text,
    central_reviewed_by uuid,
    central_reviewed_at timestamp with time zone,
    central_note text,
    rejection_reason text,
    applicant_user_id uuid,
    CONSTRAINT ric_applications_check CHECK (((status <> ALL (ARRAY['rejected_local'::public.ric_app_status, 'rejected_central'::public.ric_app_status])) OR ((rejection_reason IS NOT NULL) AND (length(TRIM(BOTH FROM rejection_reason)) > 0)))),
    CONSTRAINT ric_applications_check1 CHECK (((status <> ALL (ARRAY['pending_central'::public.ric_app_status, 'approved'::public.ric_app_status, 'rejected_central'::public.ric_app_status])) OR ((local_reviewed_by IS NOT NULL) AND (local_reviewed_at IS NOT NULL)))),
    CONSTRAINT ric_applications_check2 CHECK (((status <> ALL (ARRAY['approved'::public.ric_app_status, 'rejected_central'::public.ric_app_status])) OR ((central_reviewed_by IS NOT NULL) AND (central_reviewed_at IS NOT NULL)))),
    CONSTRAINT ric_applications_check3 CHECK (((status <> 'rejected_local'::public.ric_app_status) OR ((local_reviewed_by IS NOT NULL) AND (local_reviewed_at IS NOT NULL))))
);


--
-- Name: ric_counters; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ric_counters (
    area_id integer NOT NULL,
    next_value integer DEFAULT 1 NOT NULL,
    CONSTRAINT ric_counters_next_value_check CHECK (((next_value >= 1) AND (next_value <= 100000)))
);


--
-- Name: support_ticket_messages; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.support_ticket_messages (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    ticket_id uuid NOT NULL,
    sender_id uuid NOT NULL,
    message text NOT NULL,
    is_internal boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: support_tickets; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.support_tickets (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    ticket_number bigint NOT NULL,
    created_by uuid NOT NULL,
    assigned_to uuid,
    category text DEFAULT 'general'::text NOT NULL,
    subject text NOT NULL,
    description text NOT NULL,
    priority text DEFAULT 'normal'::text NOT NULL,
    status text DEFAULT 'open'::text NOT NULL,
    related_entity_type text,
    related_entity_id uuid,
    resolution_note text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    resolved_at timestamp with time zone,
    closed_at timestamp with time zone,
    CONSTRAINT support_tickets_category_check CHECK ((category = ANY (ARRAY['general'::text, 'account'::text, 'ric_application'::text, 'certificate'::text, 'property'::text, 'payment'::text, 'technical'::text, 'other'::text]))),
    CONSTRAINT support_tickets_priority_check CHECK ((priority = ANY (ARRAY['low'::text, 'normal'::text, 'high'::text, 'urgent'::text]))),
    CONSTRAINT support_tickets_status_check CHECK ((status = ANY (ARRAY['open'::text, 'in_progress'::text, 'waiting_user'::text, 'resolved'::text, 'closed'::text])))
);


--
-- Name: support_tickets_ticket_number_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.support_tickets ALTER COLUMN ticket_number ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.support_tickets_ticket_number_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: system_settings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.system_settings (
    key text NOT NULL,
    value jsonb NOT NULL,
    updated_by uuid,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: tenancies; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tenancies (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    property_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    landlord_id uuid NOT NULL,
    start_date date NOT NULL,
    end_date date,
    monthly_rent numeric(12,2) NOT NULL,
    deposit numeric(12,2) DEFAULT 0 NOT NULL,
    rent_due_day smallint DEFAULT 5 NOT NULL,
    status public.tenancy_status DEFAULT 'active'::public.tenancy_status NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT tenancies_check CHECK (((end_date IS NULL) OR (end_date > start_date))),
    CONSTRAINT tenancies_deposit_check CHECK ((deposit >= (0)::numeric)),
    CONSTRAINT tenancies_monthly_rent_check CHECK ((monthly_rent > (0)::numeric)),
    CONSTRAINT tenancies_rent_due_day_check CHECK (((rent_due_day >= 1) AND (rent_due_day <= 28)))
);


--
-- Name: tenancy_care; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tenancy_care (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenancy_id uuid NOT NULL,
    kind text NOT NULL,
    content jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT tenancy_care_kind_check CHECK ((kind = ANY (ARRAY['move_in'::text, 'move_out'::text, 'maintenance'::text, 'deposit'::text])))
);


--
-- Name: tenant_profiles; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tenant_profiles (
    user_id uuid NOT NULL,
    person_id uuid NOT NULL,
    full_name text NOT NULL,
    phone_enc bytea,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: user_sessions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.user_sessions (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id uuid NOT NULL,
    refresh_token_hash text NOT NULL,
    device_name text,
    user_agent text,
    ip_address inet,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    last_used_at timestamp with time zone,
    expires_at timestamp with time zone NOT NULL,
    revoked_at timestamp with time zone,
    revocation_reason text,
    CONSTRAINT chk_session_expiry CHECK ((expires_at > created_at)),
    CONSTRAINT chk_session_revocation CHECK (((revoked_at IS NULL) OR (revoked_at >= created_at)))
);


--
-- Name: users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.users (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    email public.citext NOT NULL,
    password_hash text NOT NULL,
    role public.user_role NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    last_login_at timestamp with time zone,
    token_version integer DEFAULT 0 NOT NULL
);


--
-- Name: v_certificate_render_data; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_certificate_render_data AS
 SELECT c.id AS certificate_id,
    c.ric_number,
    jsonb_build_object('ric_number', c.ric_number, 'status', c.status, 'issued_at', c.issued_at, 'expires_at', c.expires_at, 'verify_token', c.verify_token, 'household_address', h.household_address, 'area', jsonb_build_object('division', a.division, 'district', a.district, 'upazila', a.name), 'primary_holder', ( SELECT jsonb_build_object('full_name', p.full_name, 'id_last4', p.identity_last4) AS jsonb_build_object
           FROM (public.household_members m
             JOIN public.persons p ON ((p.id = m.person_id)))
          WHERE ((m.household_id = h.id) AND (m.member_role = 'primary_holder'::public.household_member_role) AND (m.left_at IS NULL))), 'members', COALESCE(( SELECT jsonb_agg(jsonb_build_object('full_name', p.full_name, 'relationship', m.relationship, 'role', m.member_role) ORDER BY m.joined_at) AS jsonb_agg
           FROM (public.household_members m
             JOIN public.persons p ON ((p.id = m.person_id)))
          WHERE ((m.household_id = h.id) AND (m.left_at IS NULL))), '[]'::jsonb), 'issuing_authority', jsonb_build_object('name', co.full_name, 'designation', co.designation), 'approvals', jsonb_build_object('local_reviewed_at', app.local_reviewed_at, 'local_official', lo.full_name, 'central_reviewed_at', app.central_reviewed_at, 'central_official', co2.full_name)) AS data
   FROM ((((((public.rental_identity_certificates c
     JOIN public.households h ON ((h.id = c.household_id)))
     JOIN public.areas a ON ((a.id = h.area_id)))
     JOIN public.ric_applications app ON ((app.id = c.application_id)))
     LEFT JOIN public.official_profiles co ON ((co.user_id = c.issued_by)))
     LEFT JOIN public.official_profiles lo ON ((lo.user_id = app.local_reviewed_by)))
     LEFT JOIN public.official_profiles co2 ON ((co2.user_id = app.central_reviewed_by)));


--
-- Name: viewing_counter_proposals; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.viewing_counter_proposals (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    viewing_id uuid NOT NULL,
    proposed_by uuid NOT NULL,
    proposed_time timestamp with time zone NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: viewing_requests; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.viewing_requests (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    listing_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    proposed_time timestamp with time zone NOT NULL,
    confirmed_time timestamp with time zone,
    status public.viewing_status DEFAULT 'pending'::public.viewing_status NOT NULL,
    message text,
    expires_at timestamp with time zone NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    responded_at timestamp with time zone,
    alternative_time timestamp with time zone
);


--
-- Name: workspace_notifications; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.workspace_notifications (
    id bigint NOT NULL,
    recipient_id uuid NOT NULL,
    destination text NOT NULL,
    record_id uuid NOT NULL,
    message text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    read_at timestamp with time zone
);


--
-- Name: workspace_notifications_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.workspace_notifications ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.workspace_notifications_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: amenities id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.amenities ALTER COLUMN id SET DEFAULT nextval('public.amenities_id_seq'::regclass);


--
-- Name: areas id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.areas ALTER COLUMN id SET DEFAULT nextval('public.areas_id_seq'::regclass);


--
-- Name: audit_logs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_logs ALTER COLUMN id SET DEFAULT nextval('public.audit_logs_id_seq'::regclass);


--
-- Name: access_grants access_grants_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.access_grants
    ADD CONSTRAINT access_grants_pkey PRIMARY KEY (id);


--
-- Name: account_profiles account_profiles_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.account_profiles
    ADD CONSTRAINT account_profiles_pkey PRIMARY KEY (user_id);


--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: amenities amenities_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.amenities
    ADD CONSTRAINT amenities_code_key UNIQUE (code);


--
-- Name: amenities amenities_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.amenities
    ADD CONSTRAINT amenities_pkey PRIMARY KEY (id);


--
-- Name: application_documents application_documents_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.application_documents
    ADD CONSTRAINT application_documents_pkey PRIMARY KEY (id);


--
-- Name: application_members application_members_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.application_members
    ADD CONSTRAINT application_members_pkey PRIMARY KEY (id);


--
-- Name: areas areas_division_code_district_code_upazila_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.areas
    ADD CONSTRAINT areas_division_code_district_code_upazila_code_key UNIQUE (division_code, district_code, upazila_code);


--
-- Name: areas areas_division_district_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.areas
    ADD CONSTRAINT areas_division_district_name_key UNIQUE (division, district, name);


--
-- Name: areas areas_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.areas
    ADD CONSTRAINT areas_pkey PRIMARY KEY (id);


--
-- Name: audit_logs audit_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_logs
    ADD CONSTRAINT audit_logs_pkey PRIMARY KEY (id);


--
-- Name: certificate_delivery_events certificate_delivery_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.certificate_delivery_events
    ADD CONSTRAINT certificate_delivery_events_pkey PRIMARY KEY (id);


--
-- Name: certificate_documents certificate_documents_certificate_id_version_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.certificate_documents
    ADD CONSTRAINT certificate_documents_certificate_id_version_key UNIQUE (certificate_id, version);


--
-- Name: certificate_documents certificate_documents_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.certificate_documents
    ADD CONSTRAINT certificate_documents_pkey PRIMARY KEY (id);


--
-- Name: certificate_templates certificate_templates_code_version_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.certificate_templates
    ADD CONSTRAINT certificate_templates_code_version_key UNIQUE (code, version);


--
-- Name: certificate_templates certificate_templates_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.certificate_templates
    ADD CONSTRAINT certificate_templates_pkey PRIMARY KEY (id);


--
-- Name: consent_events consent_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.consent_events
    ADD CONSTRAINT consent_events_pkey PRIMARY KEY (id);


--
-- Name: dispute_timeline dispute_timeline_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dispute_timeline
    ADD CONSTRAINT dispute_timeline_pkey PRIMARY KEY (id);


--
-- Name: disputes disputes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.disputes
    ADD CONSTRAINT disputes_pkey PRIMARY KEY (id);


--
-- Name: household_members household_members_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.household_members
    ADD CONSTRAINT household_members_pkey PRIMARY KEY (id);


--
-- Name: households households_application_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.households
    ADD CONSTRAINT households_application_id_key UNIQUE (application_id);


--
-- Name: households households_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.households
    ADD CONSTRAINT households_pkey PRIMARY KEY (id);


--
-- Name: landlord_profiles landlord_profiles_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.landlord_profiles
    ADD CONSTRAINT landlord_profiles_pkey PRIMARY KEY (user_id);


--
-- Name: lease_agreements lease_agreements_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lease_agreements
    ADD CONSTRAINT lease_agreements_pkey PRIMARY KEY (tenancy_id);


--
-- Name: ledger_entries ledger_entries_payment_request_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ledger_entries
    ADD CONSTRAINT ledger_entries_payment_request_id_key UNIQUE (payment_request_id);


--
-- Name: ledger_entries ledger_entries_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ledger_entries
    ADD CONSTRAINT ledger_entries_pkey PRIMARY KEY (id);


--
-- Name: listings listings_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.listings
    ADD CONSTRAINT listings_pkey PRIMARY KEY (id);


--
-- Name: media_files media_files_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.media_files
    ADD CONSTRAINT media_files_pkey PRIMARY KEY (id);


--
-- Name: media_files media_files_storage_key_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.media_files
    ADD CONSTRAINT media_files_storage_key_key UNIQUE (storage_key);


--
-- Name: notifications notifications_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notifications
    ADD CONSTRAINT notifications_pkey PRIMARY KEY (id);


--
-- Name: official_profiles official_profiles_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.official_profiles
    ADD CONSTRAINT official_profiles_pkey PRIMARY KEY (user_id);


--
-- Name: password_reset_tokens password_reset_tokens_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.password_reset_tokens
    ADD CONSTRAINT password_reset_tokens_pkey PRIMARY KEY (id);


--
-- Name: payment_requests payment_requests_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payment_requests
    ADD CONSTRAINT payment_requests_pkey PRIMARY KEY (id);


--
-- Name: persons persons_identity_number_hmac_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.persons
    ADD CONSTRAINT persons_identity_number_hmac_key UNIQUE (identity_number_hmac);


--
-- Name: persons persons_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.persons
    ADD CONSTRAINT persons_pkey PRIMARY KEY (id);


--
-- Name: photos photos_media_id_user_id_person_id_property_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.photos
    ADD CONSTRAINT photos_media_id_user_id_person_id_property_id_key UNIQUE (media_id, user_id, person_id, property_id);


--
-- Name: photos photos_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.photos
    ADD CONSTRAINT photos_pkey PRIMARY KEY (id);


--
-- Name: properties properties_id_landlord_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.properties
    ADD CONSTRAINT properties_id_landlord_id_key UNIQUE (id, landlord_id);


--
-- Name: properties properties_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.properties
    ADD CONSTRAINT properties_pkey PRIMARY KEY (id);


--
-- Name: property_amenities property_amenities_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.property_amenities
    ADD CONSTRAINT property_amenities_pkey PRIMARY KEY (property_id, amenity_id);


--
-- Name: property_units property_units_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.property_units
    ADD CONSTRAINT property_units_pkey PRIMARY KEY (id);


--
-- Name: reliability_score_events reliability_score_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reliability_score_events
    ADD CONSTRAINT reliability_score_events_pkey PRIMARY KEY (id);


--
-- Name: reliability_scores reliability_scores_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reliability_scores
    ADD CONSTRAINT reliability_scores_pkey PRIMARY KEY (id);


--
-- Name: rental_history_grants rental_history_grants_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rental_history_grants
    ADD CONSTRAINT rental_history_grants_pkey PRIMARY KEY (id);


--
-- Name: rental_identity_certificates rental_identity_certificates_application_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rental_identity_certificates
    ADD CONSTRAINT rental_identity_certificates_application_id_key UNIQUE (application_id);


--
-- Name: rental_identity_certificates rental_identity_certificates_household_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rental_identity_certificates
    ADD CONSTRAINT rental_identity_certificates_household_id_key UNIQUE (household_id);


--
-- Name: rental_identity_certificates rental_identity_certificates_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rental_identity_certificates
    ADD CONSTRAINT rental_identity_certificates_pkey PRIMARY KEY (id);


--
-- Name: rental_identity_certificates rental_identity_certificates_ric_number_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rental_identity_certificates
    ADD CONSTRAINT rental_identity_certificates_ric_number_key UNIQUE (ric_number);


--
-- Name: rental_identity_certificates rental_identity_certificates_verify_token_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rental_identity_certificates
    ADD CONSTRAINT rental_identity_certificates_verify_token_key UNIQUE (verify_token);


--
-- Name: rental_offers rental_offers_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rental_offers
    ADD CONSTRAINT rental_offers_pkey PRIMARY KEY (id);


--
-- Name: ric_application_events ric_application_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ric_application_events
    ADD CONSTRAINT ric_application_events_pkey PRIMARY KEY (id);


--
-- Name: ric_applications ric_applications_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ric_applications
    ADD CONSTRAINT ric_applications_pkey PRIMARY KEY (id);


--
-- Name: ric_counters ric_counters_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ric_counters
    ADD CONSTRAINT ric_counters_pkey PRIMARY KEY (area_id);


--
-- Name: support_ticket_messages support_ticket_messages_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.support_ticket_messages
    ADD CONSTRAINT support_ticket_messages_pkey PRIMARY KEY (id);


--
-- Name: support_tickets support_tickets_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.support_tickets
    ADD CONSTRAINT support_tickets_pkey PRIMARY KEY (id);


--
-- Name: support_tickets support_tickets_ticket_number_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.support_tickets
    ADD CONSTRAINT support_tickets_ticket_number_key UNIQUE (ticket_number);


--
-- Name: system_settings system_settings_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.system_settings
    ADD CONSTRAINT system_settings_pkey PRIMARY KEY (key);


--
-- Name: tenancies tenancies_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tenancies
    ADD CONSTRAINT tenancies_pkey PRIMARY KEY (id);


--
-- Name: tenancies tenancies_property_id_daterange_excl; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tenancies
    ADD CONSTRAINT tenancies_property_id_daterange_excl EXCLUDE USING gist (property_id WITH =, daterange(start_date, COALESCE(end_date, 'infinity'::date), '[)'::text) WITH &&) WHERE ((status = 'active'::public.tenancy_status));


--
-- Name: tenancy_care tenancy_care_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tenancy_care
    ADD CONSTRAINT tenancy_care_pkey PRIMARY KEY (id);


--
-- Name: tenant_profiles tenant_profiles_person_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tenant_profiles
    ADD CONSTRAINT tenant_profiles_person_id_key UNIQUE (person_id);


--
-- Name: tenant_profiles tenant_profiles_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tenant_profiles
    ADD CONSTRAINT tenant_profiles_pkey PRIMARY KEY (user_id);


--
-- Name: property_units uq_property_unit_number; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.property_units
    ADD CONSTRAINT uq_property_unit_number UNIQUE (property_id, unit_number);


--
-- Name: user_sessions user_sessions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_sessions
    ADD CONSTRAINT user_sessions_pkey PRIMARY KEY (id);


--
-- Name: user_sessions user_sessions_refresh_token_hash_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_sessions
    ADD CONSTRAINT user_sessions_refresh_token_hash_key UNIQUE (refresh_token_hash);


--
-- Name: users users_email_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_email_key UNIQUE (email);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: viewing_counter_proposals viewing_counter_proposals_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.viewing_counter_proposals
    ADD CONSTRAINT viewing_counter_proposals_pkey PRIMARY KEY (id);


--
-- Name: viewing_requests viewing_requests_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.viewing_requests
    ADD CONSTRAINT viewing_requests_pkey PRIMARY KEY (id);


--
-- Name: workspace_notifications workspace_notifications_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.workspace_notifications
    ADD CONSTRAINT workspace_notifications_pkey PRIMARY KEY (id);


--
-- Name: dispute_timeline_dispute_id_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX dispute_timeline_dispute_id_id_idx ON public.dispute_timeline USING btree (dispute_id, id);


--
-- Name: idx_app_docs_app; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_app_docs_app ON public.application_documents USING btree (application_id);


--
-- Name: idx_app_docs_review; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_app_docs_review ON public.application_documents USING btree (review_status, uploaded_at);


--
-- Name: idx_app_members_app; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_app_members_app ON public.application_members USING btree (application_id);


--
-- Name: idx_audit_action_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_audit_action_created ON public.audit_logs USING btree (action, created_at DESC);


--
-- Name: idx_audit_actor; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_audit_actor ON public.audit_logs USING btree (actor_id, created_at DESC);


--
-- Name: idx_audit_entity; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_audit_entity ON public.audit_logs USING btree (entity_type, entity_id);


--
-- Name: idx_cert_delivery_certificate; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_cert_delivery_certificate ON public.certificate_delivery_events USING btree (certificate_id, created_at DESC);


--
-- Name: idx_cert_delivery_document; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_cert_delivery_document ON public.certificate_delivery_events USING btree (document_id);


--
-- Name: idx_cert_delivery_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_cert_delivery_type ON public.certificate_delivery_events USING btree (event_type, created_at DESC);


--
-- Name: idx_cert_issued_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_cert_issued_at ON public.rental_identity_certificates USING btree (issued_at DESC);


--
-- Name: idx_cert_status_issued; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_cert_status_issued ON public.rental_identity_certificates USING btree (status, issued_at DESC);


--
-- Name: idx_consent_grant; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_consent_grant ON public.consent_events USING btree (access_grant_id, created_at DESC);


--
-- Name: idx_consent_landlord; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_consent_landlord ON public.consent_events USING btree (landlord_id, created_at DESC);


--
-- Name: idx_consent_tenant; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_consent_tenant ON public.consent_events USING btree (tenant_id, created_at DESC);


--
-- Name: idx_dispute_entity; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_dispute_entity ON public.disputes USING btree (entity_type, entity_id) WHERE (status = ANY (ARRAY['open'::public.dispute_status, 'under_review'::public.dispute_status]));


--
-- Name: idx_grant_lookup; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_grant_lookup ON public.access_grants USING btree (landlord_id, tenant_id) WHERE (revoked_at IS NULL);


--
-- Name: idx_household_members_household; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_household_members_household ON public.household_members USING btree (household_id);


--
-- Name: idx_household_members_person; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_household_members_person ON public.household_members USING btree (person_id);


--
-- Name: idx_ledger_tenancy; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ledger_tenancy ON public.ledger_entries USING btree (tenancy_id, period_month);


--
-- Name: idx_listing_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_listing_status ON public.listings USING btree (status);


--
-- Name: idx_notifications_unread; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_notifications_unread ON public.notifications USING btree (user_id, created_at DESC) WHERE (is_read = false);


--
-- Name: idx_notifications_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_notifications_user ON public.notifications USING btree (user_id, created_at DESC);


--
-- Name: idx_payreq_tenancy_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_payreq_tenancy_status ON public.payment_requests USING btree (tenancy_id, status);


--
-- Name: idx_photos_media; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_photos_media ON public.photos USING btree (media_id);


--
-- Name: idx_photos_person; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_photos_person ON public.photos USING btree (person_id) WHERE (person_id IS NOT NULL);


--
-- Name: idx_photos_property; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_photos_property ON public.photos USING btree (property_id) WHERE (property_id IS NOT NULL);


--
-- Name: idx_photos_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_photos_user ON public.photos USING btree (user_id) WHERE (user_id IS NOT NULL);


--
-- Name: idx_prop_search; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_prop_search ON public.properties USING btree (area_id, monthly_rent, available_from);


--
-- Name: idx_property_units_property; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_property_units_property ON public.property_units USING btree (property_id, status);


--
-- Name: idx_rental_offer_listing; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_rental_offer_listing ON public.rental_offers USING btree (listing_id);


--
-- Name: idx_rental_offer_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_rental_offer_status ON public.rental_offers USING btree (status);


--
-- Name: idx_ric_app_applicant; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ric_app_applicant ON public.ric_applications USING btree (applicant_user_id) WHERE (applicant_user_id IS NOT NULL);


--
-- Name: idx_ric_app_area_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ric_app_area_status ON public.ric_applications USING btree (area_id, status, submitted_at DESC);


--
-- Name: idx_ric_app_central_review; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ric_app_central_review ON public.ric_applications USING btree (central_reviewed_at DESC) WHERE (central_reviewed_at IS NOT NULL);


--
-- Name: idx_ric_app_email; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ric_app_email ON public.ric_applications USING btree (email);


--
-- Name: idx_ric_app_idhmac; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ric_app_idhmac ON public.ric_applications USING btree (identity_number_hmac);


--
-- Name: idx_ric_app_local_review; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ric_app_local_review ON public.ric_applications USING btree (local_reviewed_at DESC) WHERE (local_reviewed_at IS NOT NULL);


--
-- Name: idx_ric_app_previous_ric; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ric_app_previous_ric ON public.ric_applications USING btree (previous_ric_id);


--
-- Name: idx_ric_app_queue; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ric_app_queue ON public.ric_applications USING btree (status, area_id, submitted_at);


--
-- Name: idx_ric_app_status_submitted; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ric_app_status_submitted ON public.ric_applications USING btree (status, submitted_at DESC);


--
-- Name: idx_ric_events_actor; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ric_events_actor ON public.ric_application_events USING btree (actor_id, created_at DESC);


--
-- Name: idx_ric_events_application; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ric_events_application ON public.ric_application_events USING btree (application_id, created_at DESC);


--
-- Name: idx_ric_events_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ric_events_type ON public.ric_application_events USING btree (event_type);


--
-- Name: idx_score_events_score; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_score_events_score ON public.reliability_score_events USING btree (score_id);


--
-- Name: idx_score_tenant; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_score_tenant ON public.reliability_scores USING btree (tenant_id, computed_at DESC);


--
-- Name: idx_sessions_active; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_sessions_active ON public.user_sessions USING btree (user_id, expires_at) WHERE (revoked_at IS NULL);


--
-- Name: idx_sessions_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_sessions_user ON public.user_sessions USING btree (user_id, created_at DESC);


--
-- Name: idx_support_assignee; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_support_assignee ON public.support_tickets USING btree (assigned_to, status);


--
-- Name: idx_support_creator; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_support_creator ON public.support_tickets USING btree (created_by, created_at DESC);


--
-- Name: idx_support_messages_ticket; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_support_messages_ticket ON public.support_ticket_messages USING btree (ticket_id, created_at);


--
-- Name: idx_support_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_support_status ON public.support_tickets USING btree (status, priority, created_at DESC);


--
-- Name: idx_tenancy_landlord; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_tenancy_landlord ON public.tenancies USING btree (landlord_id);


--
-- Name: idx_tenancy_tenant; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_tenancy_tenant ON public.tenancies USING btree (tenant_id);


--
-- Name: idx_viewing_listing; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_viewing_listing ON public.viewing_requests USING btree (listing_id, status);


--
-- Name: idx_viewing_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_viewing_status ON public.viewing_requests USING btree (status);


--
-- Name: ix_password_reset_email_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_password_reset_email_created ON public.password_reset_tokens USING btree (email_digest, created_at);


--
-- Name: ix_password_reset_token_digest; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_password_reset_token_digest ON public.password_reset_tokens USING btree (token_digest);


--
-- Name: tenancy_care_single_report; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX tenancy_care_single_report ON public.tenancy_care USING btree (tenancy_id, kind) WHERE (kind <> 'maintenance'::text);


--
-- Name: tenancy_care_tenancy_id_created_at_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX tenancy_care_tenancy_id_created_at_idx ON public.tenancy_care USING btree (tenancy_id, created_at);


--
-- Name: uq_cert_one_current_document; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_cert_one_current_document ON public.certificate_documents USING btree (certificate_id) WHERE is_current;


--
-- Name: uq_household_one_active_primary; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_household_one_active_primary ON public.household_members USING btree (household_id) WHERE ((member_role = 'primary_holder'::public.household_member_role) AND (left_at IS NULL));


--
-- Name: uq_one_default_template; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_one_default_template ON public.certificate_templates USING btree ((true)) WHERE is_default;


--
-- Name: uq_open_application_per_person; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_open_application_per_person ON public.ric_applications USING btree (identity_number_hmac) WHERE (status = ANY (ARRAY['pending_local'::public.ric_app_status, 'pending_central'::public.ric_app_status]));


--
-- Name: uq_open_building_listing; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_open_building_listing ON public.listings USING btree (property_id) WHERE ((unit_id IS NULL) AND (status = ANY (ARRAY['draft'::public.listing_status, 'available'::public.listing_status])));


--
-- Name: uq_open_unit_listing; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_open_unit_listing ON public.listings USING btree (unit_id) WHERE ((unit_id IS NOT NULL) AND (status = ANY (ARRAY['draft'::public.listing_status, 'available'::public.listing_status])));


--
-- Name: uq_person_one_active_household; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_person_one_active_household ON public.household_members USING btree (person_id) WHERE (left_at IS NULL);


--
-- Name: uq_person_primary_photo; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_person_primary_photo ON public.photos USING btree (person_id, photo_type) WHERE ((person_id IS NOT NULL) AND is_primary);


--
-- Name: uq_property_primary_photo; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_property_primary_photo ON public.photos USING btree (property_id, photo_type) WHERE ((property_id IS NOT NULL) AND is_primary);


--
-- Name: uq_rental_offer_tenant_listing_open; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_rental_offer_tenant_listing_open ON public.rental_offers USING btree (tenant_id, listing_id) WHERE (status = ANY (ARRAY['pending'::public.rental_offer_status, 'countered'::public.rental_offer_status]));


--
-- Name: uq_score_event_ledger; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_score_event_ledger ON public.reliability_score_events USING btree (ledger_entry_id) WHERE (ledger_entry_id IS NOT NULL);


--
-- Name: uq_user_primary_photo; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_user_primary_photo ON public.photos USING btree (user_id, photo_type) WHERE ((user_id IS NOT NULL) AND is_primary);


--
-- Name: uq_viewing_tenant_listing; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_viewing_tenant_listing ON public.viewing_requests USING btree (tenant_id, listing_id) WHERE (status = ANY (ARRAY['pending'::public.viewing_status, 'countered'::public.viewing_status]));


--
-- Name: workspace_notifications_recipient_id_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX workspace_notifications_recipient_id_id_idx ON public.workspace_notifications USING btree (recipient_id, id DESC);


--
-- Name: payment_requests notify_rent; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER notify_rent AFTER INSERT OR UPDATE OF status ON public.payment_requests FOR EACH ROW EXECUTE FUNCTION public.notify_workspace_change();


--
-- Name: ric_applications notify_ric; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER notify_ric AFTER INSERT OR UPDATE OF status ON public.ric_applications FOR EACH ROW EXECUTE FUNCTION public.notify_workspace_change();


--
-- Name: viewing_requests notify_viewing; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER notify_viewing AFTER UPDATE OF status ON public.viewing_requests FOR EACH ROW EXECUTE FUNCTION public.notify_workspace_change();


--
-- Name: tenancies prepare_tenancy_lease; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER prepare_tenancy_lease AFTER INSERT ON public.tenancies FOR EACH ROW EXECUTE FUNCTION public.prepare_tenancy_lease();


--
-- Name: audit_logs trg_audit_logs_append_only; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_audit_logs_append_only BEFORE DELETE OR UPDATE ON public.audit_logs FOR EACH ROW EXECUTE FUNCTION public.forbid_mutation();


--
-- Name: audit_logs trg_audit_logs_no_truncate; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_audit_logs_no_truncate BEFORE TRUNCATE ON public.audit_logs FOR EACH STATEMENT EXECUTE FUNCTION public.forbid_mutation();


--
-- Name: certificate_documents trg_cert_document_guard; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_cert_document_guard BEFORE DELETE OR UPDATE ON public.certificate_documents FOR EACH ROW EXECUTE FUNCTION public.guard_certificate_document();


--
-- Name: certificate_delivery_events trg_certificate_delivery_events_append_only; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_certificate_delivery_events_append_only BEFORE DELETE OR UPDATE ON public.certificate_delivery_events FOR EACH ROW EXECUTE FUNCTION public.forbid_mutation();


--
-- Name: certificate_delivery_events trg_certificate_delivery_events_no_truncate; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_certificate_delivery_events_no_truncate BEFORE TRUNCATE ON public.certificate_delivery_events FOR EACH STATEMENT EXECUTE FUNCTION public.forbid_mutation();


--
-- Name: consent_events trg_consent_events_append_only; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_consent_events_append_only BEFORE DELETE OR UPDATE ON public.consent_events FOR EACH ROW EXECUTE FUNCTION public.forbid_mutation();


--
-- Name: consent_events trg_consent_events_no_truncate; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_consent_events_no_truncate BEFORE TRUNCATE ON public.consent_events FOR EACH STATEMENT EXECUTE FUNCTION public.forbid_mutation();


--
-- Name: household_members trg_household_primary; Type: TRIGGER; Schema: public; Owner: -
--

CREATE CONSTRAINT TRIGGER trg_household_primary AFTER INSERT OR DELETE OR UPDATE ON public.household_members DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION public.check_household_has_primary();


--
-- Name: ledger_entries trg_ledger_entries_append_only; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_ledger_entries_append_only BEFORE DELETE OR UPDATE ON public.ledger_entries FOR EACH ROW EXECUTE FUNCTION public.forbid_mutation();


--
-- Name: ledger_entries trg_ledger_entries_no_truncate; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_ledger_entries_no_truncate BEFORE TRUNCATE ON public.ledger_entries FOR EACH STATEMENT EXECUTE FUNCTION public.forbid_mutation();


--
-- Name: listings trg_listings_updated; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_listings_updated BEFORE UPDATE ON public.listings FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: payment_requests trg_payreq_guard; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_payreq_guard BEFORE UPDATE ON public.payment_requests FOR EACH ROW EXECUTE FUNCTION public.guard_payment_request();


--
-- Name: properties trg_properties_updated; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_properties_updated BEFORE UPDATE ON public.properties FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: reliability_score_events trg_reliability_score_events_append_only; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_reliability_score_events_append_only BEFORE DELETE OR UPDATE ON public.reliability_score_events FOR EACH ROW EXECUTE FUNCTION public.forbid_mutation();


--
-- Name: reliability_score_events trg_reliability_score_events_no_truncate; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_reliability_score_events_no_truncate BEFORE TRUNCATE ON public.reliability_score_events FOR EACH STATEMENT EXECUTE FUNCTION public.forbid_mutation();


--
-- Name: reliability_scores trg_reliability_scores_append_only; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_reliability_scores_append_only BEFORE DELETE OR UPDATE ON public.reliability_scores FOR EACH ROW EXECUTE FUNCTION public.forbid_mutation();


--
-- Name: reliability_scores trg_reliability_scores_no_truncate; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_reliability_scores_no_truncate BEFORE TRUNCATE ON public.reliability_scores FOR EACH STATEMENT EXECUTE FUNCTION public.forbid_mutation();


--
-- Name: ric_application_events trg_ric_application_events_append_only; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_ric_application_events_append_only BEFORE DELETE OR UPDATE ON public.ric_application_events FOR EACH ROW EXECUTE FUNCTION public.forbid_mutation();


--
-- Name: ric_application_events trg_ric_application_events_no_truncate; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_ric_application_events_no_truncate BEFORE TRUNCATE ON public.ric_application_events FOR EACH STATEMENT EXECUTE FUNCTION public.forbid_mutation();


--
-- Name: ric_applications trg_ric_application_guard; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_ric_application_guard BEFORE UPDATE ON public.ric_applications FOR EACH ROW EXECUTE FUNCTION public.guard_ric_application();


--
-- Name: support_tickets trg_support_tickets_updated; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_support_tickets_updated BEFORE UPDATE ON public.support_tickets FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: access_grants access_grants_landlord_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.access_grants
    ADD CONSTRAINT access_grants_landlord_id_fkey FOREIGN KEY (landlord_id) REFERENCES public.landlord_profiles(user_id);


--
-- Name: access_grants access_grants_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.access_grants
    ADD CONSTRAINT access_grants_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenant_profiles(user_id);


--
-- Name: account_profiles account_profiles_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.account_profiles
    ADD CONSTRAINT account_profiles_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: application_documents application_documents_application_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.application_documents
    ADD CONSTRAINT application_documents_application_id_fkey FOREIGN KEY (application_id) REFERENCES public.ric_applications(id) ON DELETE CASCADE;


--
-- Name: application_documents application_documents_reviewed_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.application_documents
    ADD CONSTRAINT application_documents_reviewed_by_fkey FOREIGN KEY (reviewed_by) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: application_members application_members_application_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.application_members
    ADD CONSTRAINT application_members_application_id_fkey FOREIGN KEY (application_id) REFERENCES public.ric_applications(id) ON DELETE CASCADE;


--
-- Name: audit_logs audit_logs_actor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_logs
    ADD CONSTRAINT audit_logs_actor_id_fkey FOREIGN KEY (actor_id) REFERENCES public.users(id);


--
-- Name: certificate_delivery_events certificate_delivery_events_actor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.certificate_delivery_events
    ADD CONSTRAINT certificate_delivery_events_actor_id_fkey FOREIGN KEY (actor_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: certificate_delivery_events certificate_delivery_events_certificate_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.certificate_delivery_events
    ADD CONSTRAINT certificate_delivery_events_certificate_id_fkey FOREIGN KEY (certificate_id) REFERENCES public.rental_identity_certificates(id) ON DELETE RESTRICT;


--
-- Name: certificate_delivery_events certificate_delivery_events_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.certificate_delivery_events
    ADD CONSTRAINT certificate_delivery_events_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.certificate_documents(id) ON DELETE RESTRICT;


--
-- Name: certificate_documents certificate_documents_certificate_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.certificate_documents
    ADD CONSTRAINT certificate_documents_certificate_id_fkey FOREIGN KEY (certificate_id) REFERENCES public.rental_identity_certificates(id) ON DELETE RESTRICT;


--
-- Name: certificate_documents certificate_documents_generated_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.certificate_documents
    ADD CONSTRAINT certificate_documents_generated_by_fkey FOREIGN KEY (generated_by) REFERENCES public.users(id);


--
-- Name: certificate_documents certificate_documents_template_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.certificate_documents
    ADD CONSTRAINT certificate_documents_template_id_fkey FOREIGN KEY (template_id) REFERENCES public.certificate_templates(id);


--
-- Name: consent_events consent_events_access_grant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.consent_events
    ADD CONSTRAINT consent_events_access_grant_id_fkey FOREIGN KEY (access_grant_id) REFERENCES public.access_grants(id) ON DELETE RESTRICT;


--
-- Name: consent_events consent_events_actor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.consent_events
    ADD CONSTRAINT consent_events_actor_id_fkey FOREIGN KEY (actor_id) REFERENCES public.users(id) ON DELETE RESTRICT;


--
-- Name: consent_events consent_events_landlord_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.consent_events
    ADD CONSTRAINT consent_events_landlord_id_fkey FOREIGN KEY (landlord_id) REFERENCES public.landlord_profiles(user_id) ON DELETE RESTRICT;


--
-- Name: consent_events consent_events_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.consent_events
    ADD CONSTRAINT consent_events_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenant_profiles(user_id) ON DELETE RESTRICT;


--
-- Name: dispute_timeline dispute_timeline_actor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dispute_timeline
    ADD CONSTRAINT dispute_timeline_actor_id_fkey FOREIGN KEY (actor_id) REFERENCES public.users(id);


--
-- Name: dispute_timeline dispute_timeline_dispute_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dispute_timeline
    ADD CONSTRAINT dispute_timeline_dispute_id_fkey FOREIGN KEY (dispute_id) REFERENCES public.disputes(id);


--
-- Name: disputes disputes_raised_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.disputes
    ADD CONSTRAINT disputes_raised_by_fkey FOREIGN KEY (raised_by) REFERENCES public.users(id);


--
-- Name: disputes disputes_resolved_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.disputes
    ADD CONSTRAINT disputes_resolved_by_fkey FOREIGN KEY (resolved_by) REFERENCES public.users(id);


--
-- Name: listings fk_listings_unit_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.listings
    ADD CONSTRAINT fk_listings_unit_id FOREIGN KEY (unit_id) REFERENCES public.property_units(id) ON DELETE CASCADE;


--
-- Name: ric_applications fk_previous_ric; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ric_applications
    ADD CONSTRAINT fk_previous_ric FOREIGN KEY (previous_ric_id) REFERENCES public.rental_identity_certificates(id) ON DELETE RESTRICT;


--
-- Name: household_members household_members_household_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.household_members
    ADD CONSTRAINT household_members_household_id_fkey FOREIGN KEY (household_id) REFERENCES public.households(id) ON DELETE RESTRICT;


--
-- Name: household_members household_members_person_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.household_members
    ADD CONSTRAINT household_members_person_id_fkey FOREIGN KEY (person_id) REFERENCES public.persons(id) ON DELETE RESTRICT;


--
-- Name: households households_application_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.households
    ADD CONSTRAINT households_application_id_fkey FOREIGN KEY (application_id) REFERENCES public.ric_applications(id);


--
-- Name: households households_area_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.households
    ADD CONSTRAINT households_area_id_fkey FOREIGN KEY (area_id) REFERENCES public.areas(id);


--
-- Name: landlord_profiles landlord_profiles_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.landlord_profiles
    ADD CONSTRAINT landlord_profiles_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE RESTRICT;


--
-- Name: lease_agreements lease_agreements_tenancy_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lease_agreements
    ADD CONSTRAINT lease_agreements_tenancy_id_fkey FOREIGN KEY (tenancy_id) REFERENCES public.tenancies(id);


--
-- Name: ledger_entries ledger_entries_actor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ledger_entries
    ADD CONSTRAINT ledger_entries_actor_id_fkey FOREIGN KEY (actor_id) REFERENCES public.users(id);


--
-- Name: ledger_entries ledger_entries_corrects_entry_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ledger_entries
    ADD CONSTRAINT ledger_entries_corrects_entry_id_fkey FOREIGN KEY (corrects_entry_id) REFERENCES public.ledger_entries(id);


--
-- Name: ledger_entries ledger_entries_payment_request_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ledger_entries
    ADD CONSTRAINT ledger_entries_payment_request_id_fkey FOREIGN KEY (payment_request_id) REFERENCES public.payment_requests(id);


--
-- Name: ledger_entries ledger_entries_tenancy_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ledger_entries
    ADD CONSTRAINT ledger_entries_tenancy_id_fkey FOREIGN KEY (tenancy_id) REFERENCES public.tenancies(id);


--
-- Name: listings listings_property_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.listings
    ADD CONSTRAINT listings_property_id_fkey FOREIGN KEY (property_id) REFERENCES public.properties(id);


--
-- Name: media_files media_files_uploaded_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.media_files
    ADD CONSTRAINT media_files_uploaded_by_fkey FOREIGN KEY (uploaded_by) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: notifications notifications_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notifications
    ADD CONSTRAINT notifications_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: official_profiles official_profiles_area_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.official_profiles
    ADD CONSTRAINT official_profiles_area_id_fkey FOREIGN KEY (area_id) REFERENCES public.areas(id);


--
-- Name: official_profiles official_profiles_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.official_profiles
    ADD CONSTRAINT official_profiles_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE RESTRICT;


--
-- Name: password_reset_tokens password_reset_tokens_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.password_reset_tokens
    ADD CONSTRAINT password_reset_tokens_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: payment_requests payment_requests_decided_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payment_requests
    ADD CONSTRAINT payment_requests_decided_by_fkey FOREIGN KEY (decided_by) REFERENCES public.users(id);


--
-- Name: payment_requests payment_requests_requested_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payment_requests
    ADD CONSTRAINT payment_requests_requested_by_fkey FOREIGN KEY (requested_by) REFERENCES public.users(id);


--
-- Name: payment_requests payment_requests_tenancy_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payment_requests
    ADD CONSTRAINT payment_requests_tenancy_id_fkey FOREIGN KEY (tenancy_id) REFERENCES public.tenancies(id);


--
-- Name: photos photos_media_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.photos
    ADD CONSTRAINT photos_media_id_fkey FOREIGN KEY (media_id) REFERENCES public.media_files(id) ON DELETE RESTRICT;


--
-- Name: photos photos_person_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.photos
    ADD CONSTRAINT photos_person_id_fkey FOREIGN KEY (person_id) REFERENCES public.persons(id) ON DELETE CASCADE;


--
-- Name: photos photos_property_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.photos
    ADD CONSTRAINT photos_property_id_fkey FOREIGN KEY (property_id) REFERENCES public.properties(id) ON DELETE CASCADE;


--
-- Name: photos photos_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.photos
    ADD CONSTRAINT photos_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: photos photos_verified_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.photos
    ADD CONSTRAINT photos_verified_by_fkey FOREIGN KEY (verified_by) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: properties properties_area_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.properties
    ADD CONSTRAINT properties_area_id_fkey FOREIGN KEY (area_id) REFERENCES public.areas(id);


--
-- Name: properties properties_landlord_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.properties
    ADD CONSTRAINT properties_landlord_id_fkey FOREIGN KEY (landlord_id) REFERENCES public.landlord_profiles(user_id);


--
-- Name: property_amenities property_amenities_amenity_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.property_amenities
    ADD CONSTRAINT property_amenities_amenity_id_fkey FOREIGN KEY (amenity_id) REFERENCES public.amenities(id);


--
-- Name: property_amenities property_amenities_property_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.property_amenities
    ADD CONSTRAINT property_amenities_property_id_fkey FOREIGN KEY (property_id) REFERENCES public.properties(id) ON DELETE CASCADE;


--
-- Name: property_units property_units_property_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.property_units
    ADD CONSTRAINT property_units_property_id_fkey FOREIGN KEY (property_id) REFERENCES public.properties(id) ON DELETE CASCADE;


--
-- Name: reliability_score_events reliability_score_events_ledger_entry_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reliability_score_events
    ADD CONSTRAINT reliability_score_events_ledger_entry_id_fkey FOREIGN KEY (ledger_entry_id) REFERENCES public.ledger_entries(id);


--
-- Name: reliability_score_events reliability_score_events_score_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reliability_score_events
    ADD CONSTRAINT reliability_score_events_score_id_fkey FOREIGN KEY (score_id) REFERENCES public.reliability_scores(id) ON DELETE RESTRICT;


--
-- Name: reliability_score_events reliability_score_events_tenancy_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reliability_score_events
    ADD CONSTRAINT reliability_score_events_tenancy_id_fkey FOREIGN KEY (tenancy_id) REFERENCES public.tenancies(id);


--
-- Name: reliability_scores reliability_scores_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reliability_scores
    ADD CONSTRAINT reliability_scores_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenant_profiles(user_id);


--
-- Name: rental_history_grants rental_history_grants_landlord_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rental_history_grants
    ADD CONSTRAINT rental_history_grants_landlord_id_fkey FOREIGN KEY (landlord_id) REFERENCES public.users(id);


--
-- Name: rental_history_grants rental_history_grants_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rental_history_grants
    ADD CONSTRAINT rental_history_grants_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.users(id);


--
-- Name: rental_identity_certificates rental_identity_certificates_application_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rental_identity_certificates
    ADD CONSTRAINT rental_identity_certificates_application_id_fkey FOREIGN KEY (application_id) REFERENCES public.ric_applications(id) ON DELETE RESTRICT;


--
-- Name: rental_identity_certificates rental_identity_certificates_household_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rental_identity_certificates
    ADD CONSTRAINT rental_identity_certificates_household_id_fkey FOREIGN KEY (household_id) REFERENCES public.households(id) ON DELETE RESTRICT;


--
-- Name: rental_identity_certificates rental_identity_certificates_issued_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rental_identity_certificates
    ADD CONSTRAINT rental_identity_certificates_issued_by_fkey FOREIGN KEY (issued_by) REFERENCES public.users(id);


--
-- Name: rental_identity_certificates rental_identity_certificates_revoked_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rental_identity_certificates
    ADD CONSTRAINT rental_identity_certificates_revoked_by_fkey FOREIGN KEY (revoked_by) REFERENCES public.users(id);


--
-- Name: rental_offers rental_offers_landlord_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rental_offers
    ADD CONSTRAINT rental_offers_landlord_id_fkey FOREIGN KEY (landlord_id) REFERENCES public.landlord_profiles(user_id) ON DELETE RESTRICT;


--
-- Name: rental_offers rental_offers_listing_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rental_offers
    ADD CONSTRAINT rental_offers_listing_id_fkey FOREIGN KEY (listing_id) REFERENCES public.listings(id) ON DELETE CASCADE;


--
-- Name: rental_offers rental_offers_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rental_offers
    ADD CONSTRAINT rental_offers_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenant_profiles(user_id) ON DELETE RESTRICT;


--
-- Name: ric_application_events ric_application_events_actor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ric_application_events
    ADD CONSTRAINT ric_application_events_actor_id_fkey FOREIGN KEY (actor_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: ric_application_events ric_application_events_application_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ric_application_events
    ADD CONSTRAINT ric_application_events_application_id_fkey FOREIGN KEY (application_id) REFERENCES public.ric_applications(id) ON DELETE RESTRICT;


--
-- Name: ric_applications ric_applications_applicant_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ric_applications
    ADD CONSTRAINT ric_applications_applicant_user_id_fkey FOREIGN KEY (applicant_user_id) REFERENCES public.users(id) ON DELETE RESTRICT;


--
-- Name: ric_applications ric_applications_area_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ric_applications
    ADD CONSTRAINT ric_applications_area_id_fkey FOREIGN KEY (area_id) REFERENCES public.areas(id);


--
-- Name: ric_applications ric_applications_central_reviewed_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ric_applications
    ADD CONSTRAINT ric_applications_central_reviewed_by_fkey FOREIGN KEY (central_reviewed_by) REFERENCES public.users(id);


--
-- Name: ric_applications ric_applications_local_reviewed_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ric_applications
    ADD CONSTRAINT ric_applications_local_reviewed_by_fkey FOREIGN KEY (local_reviewed_by) REFERENCES public.users(id);


--
-- Name: ric_applications ric_applications_resubmission_of_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ric_applications
    ADD CONSTRAINT ric_applications_resubmission_of_fkey FOREIGN KEY (resubmission_of) REFERENCES public.ric_applications(id);


--
-- Name: ric_counters ric_counters_area_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ric_counters
    ADD CONSTRAINT ric_counters_area_id_fkey FOREIGN KEY (area_id) REFERENCES public.areas(id) ON DELETE RESTRICT;


--
-- Name: support_ticket_messages support_ticket_messages_sender_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.support_ticket_messages
    ADD CONSTRAINT support_ticket_messages_sender_id_fkey FOREIGN KEY (sender_id) REFERENCES public.users(id) ON DELETE RESTRICT;


--
-- Name: support_ticket_messages support_ticket_messages_ticket_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.support_ticket_messages
    ADD CONSTRAINT support_ticket_messages_ticket_id_fkey FOREIGN KEY (ticket_id) REFERENCES public.support_tickets(id) ON DELETE RESTRICT;


--
-- Name: support_tickets support_tickets_assigned_to_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.support_tickets
    ADD CONSTRAINT support_tickets_assigned_to_fkey FOREIGN KEY (assigned_to) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: support_tickets support_tickets_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.support_tickets
    ADD CONSTRAINT support_tickets_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(id) ON DELETE RESTRICT;


--
-- Name: system_settings system_settings_updated_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.system_settings
    ADD CONSTRAINT system_settings_updated_by_fkey FOREIGN KEY (updated_by) REFERENCES public.users(id);


--
-- Name: tenancies tenancies_landlord_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tenancies
    ADD CONSTRAINT tenancies_landlord_id_fkey FOREIGN KEY (landlord_id) REFERENCES public.landlord_profiles(user_id);


--
-- Name: tenancies tenancies_property_id_landlord_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tenancies
    ADD CONSTRAINT tenancies_property_id_landlord_id_fkey FOREIGN KEY (property_id, landlord_id) REFERENCES public.properties(id, landlord_id);


--
-- Name: tenancies tenancies_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tenancies
    ADD CONSTRAINT tenancies_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenant_profiles(user_id);


--
-- Name: tenancy_care tenancy_care_tenancy_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tenancy_care
    ADD CONSTRAINT tenancy_care_tenancy_id_fkey FOREIGN KEY (tenancy_id) REFERENCES public.tenancies(id);


--
-- Name: tenant_profiles tenant_profiles_person_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tenant_profiles
    ADD CONSTRAINT tenant_profiles_person_id_fkey FOREIGN KEY (person_id) REFERENCES public.persons(id) ON DELETE RESTRICT;


--
-- Name: tenant_profiles tenant_profiles_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tenant_profiles
    ADD CONSTRAINT tenant_profiles_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE RESTRICT;


--
-- Name: user_sessions user_sessions_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_sessions
    ADD CONSTRAINT user_sessions_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: viewing_counter_proposals viewing_counter_proposals_proposed_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.viewing_counter_proposals
    ADD CONSTRAINT viewing_counter_proposals_proposed_by_fkey FOREIGN KEY (proposed_by) REFERENCES public.users(id);


--
-- Name: viewing_counter_proposals viewing_counter_proposals_viewing_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.viewing_counter_proposals
    ADD CONSTRAINT viewing_counter_proposals_viewing_id_fkey FOREIGN KEY (viewing_id) REFERENCES public.viewing_requests(id) ON DELETE CASCADE;


--
-- Name: viewing_requests viewing_requests_listing_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.viewing_requests
    ADD CONSTRAINT viewing_requests_listing_id_fkey FOREIGN KEY (listing_id) REFERENCES public.listings(id);


--
-- Name: viewing_requests viewing_requests_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.viewing_requests
    ADD CONSTRAINT viewing_requests_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenant_profiles(user_id);


--
-- Name: workspace_notifications workspace_notifications_recipient_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.workspace_notifications
    ADD CONSTRAINT workspace_notifications_recipient_id_fkey FOREIGN KEY (recipient_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--


