"""Allow central officials to return a case for local verification.

Revision ID: 20261125_return_local
Revises: 20261124_ric_consent_scope
"""

from alembic import op

revision = "20261125_return_local"
down_revision = "20261124_ric_consent_scope"
branch_labels = None
depends_on = None


_UPGRADE_FUNCTION = """
CREATE OR REPLACE FUNCTION public.guard_ric_application()
RETURNS trigger
LANGUAGE plpgsql
AS $function$
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
$function$;
"""


_DOWNGRADE_FUNCTION = """
CREATE OR REPLACE FUNCTION public.guard_ric_application()
RETURNS trigger
LANGUAGE plpgsql
AS $function$
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
    ELSIF OLD.status = 'pending_central'
          AND NEW.status IN ('approved','rejected_central') THEN
        IF NOT EXISTS (
            SELECT 1 FROM official_profiles
             WHERE user_id = NEW.central_reviewed_by
               AND level = 'central') THEN
            RAISE EXCEPTION 'reviewer is not a central official';
        END IF;
    ELSE
        RAISE EXCEPTION 'invalid application transition % -> %', OLD.status, NEW.status;
    END IF;
    RETURN NEW;
END;
$function$;
"""


def upgrade():
    op.execute(_UPGRADE_FUNCTION)


def downgrade():
    op.execute(_DOWNGRADE_FUNCTION)
