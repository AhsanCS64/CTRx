"""Compute reliability from ledger activity, documented missed rent, and monthly feedback."""

from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import text
from sqlalchemy.orm import Session

BASE_SCORE = 50
ON_TIME_POINTS = 2
LATE_POINTS = -1
MISSED_POINTS = -3
MONTHLY_FEEDBACK_POINTS = 1


def score_for_events(events) -> int | None:
    return max(0, min(100, BASE_SCORE + sum(event["points"] for event in events))) if events else None


def reliability_history(db: Session, tenant_id):
    rows = db.execute(text("""
        WITH payments AS (
            SELECT payment.id, payment.tenancy_id, payment.period_month, payment.paid_on,
                   payment.created_at, payment.amount,
                   payment.paid_on <= LEAST(
                       (payment.period_month + interval '1 month - 1 day')::date,
                       GREATEST(
                           payment.period_month + (t.rent_due_day - 1),
                           t.start_date,
                           (invoice.submitted_at AT TIME ZONE 'Asia/Dhaka')::date
                       )
                   ) AS on_time
            FROM ledger_entries payment
            JOIN tenancies t ON t.id = payment.tenancy_id
            LEFT JOIN payment_requests invoice ON invoice.id = payment.payment_request_id
            WHERE t.tenant_id = :tenant AND payment.entry_type = 'payment'
        ), corrections AS (
            SELECT c.id, p.id AS original_id, p.tenancy_id, p.period_month, c.paid_on, c.created_at,
                   p.on_time, c.amount, p.amount + sum(c.amount) OVER (
                       PARTITION BY p.id ORDER BY c.created_at, c.id ROWS UNBOUNDED PRECEDING
                   ) AS balance
            FROM payments p
            JOIN ledger_entries c ON c.corrects_entry_id = p.id
                AND c.tenancy_id = p.tenancy_id AND c.entry_type = 'correction'
        ), payment_events AS (
            SELECT id, id AS original_id, tenancy_id, period_month, paid_on, created_at, on_time,
                   amount, NULL AS previous_balance, NULL AS balance
            FROM payments
            UNION ALL
            SELECT id, original_id, tenancy_id, period_month, paid_on, created_at, on_time,
                   amount, balance - amount, balance
            FROM corrections
        ), missed AS (
            SELECT e.id, e.tenancy_id, e.period_month, e.created_at, e.points_delta
            FROM reliability_score_events e
            JOIN reliability_scores s ON s.id = e.score_id
            WHERE s.tenant_id = :tenant AND e.event_type = 'missed' AND e.period_month IS NOT NULL
        ), feedback AS (
            SELECT f.period_month, max(f.updated_at) AS created_at
            FROM monthly_tenancy_feedback f
            JOIN tenancies t ON t.id = f.tenancy_id AND t.landlord_id = f.author_id
            WHERE t.tenant_id = :tenant
            GROUP BY f.period_month
            HAVING bool_or(f.rating = 'positive') AND NOT bool_or(f.rating = 'concern')
        )
        SELECT id, original_id, tenancy_id, period_month, paid_on, created_at, on_time, amount,
               previous_balance, balance, NULL AS missed_points, false AS monthly_feedback
        FROM payment_events
        UNION ALL
        SELECT id, NULL, tenancy_id, period_month, NULL, created_at, NULL, NULL,
               NULL, NULL, points_delta, false
        FROM missed
        UNION ALL
        SELECT NULL, NULL, NULL, period_month, NULL, created_at, NULL, NULL,
               NULL, NULL, NULL, true
        FROM feedback
        ORDER BY created_at DESC, id
    """), {"tenant": tenant_id}).mappings().all()

    net_payments = {}
    settled_periods = set()
    events = []
    missed_events = []
    has_monthly_feedback = False
    for row in rows:
        event = {key: row[key] for key in ("id", "tenancy_id", "period_month", "paid_on", "created_at")}
        if row.get("monthly_feedback"):
            has_monthly_feedback = True
            event.update(
                id=uuid5(NAMESPACE_URL, f"ctrx:monthly-feedback:{tenant_id}:{row['period_month']}"),
                event_type="monthly_feedback",
                reason="Positive monthly feedback from landlord",
                points=MONTHLY_FEEDBACK_POINTS,
            )
        elif row["missed_points"] is not None:
            event.update(event_type="missed", reason="Missed rent recorded by landlord", points=int(row["missed_points"]))
            missed_events.append((event, (row["tenancy_id"], row["period_month"])))
        else:
            payment = row["original_id"]
            period = (row["tenancy_id"], row["period_month"])
            previous_amount = net_payments.get(payment, (0, period))[0]
            net_payments[payment] = (previous_amount + row["amount"], period)
            payment_points = ON_TIME_POINTS if row["on_time"] else LATE_POINTS
            if row["balance"] is not None:
                delta = int(row["balance"] > 0) - int(row["previous_balance"] > 0)
                event.update(event_type="correction", reason="Ledger correction", points=delta * payment_points)
            else:
                event.update(
                    event_type="on_time" if row["on_time"] else "late",
                    reason="Confirmed on-time payment" if row["on_time"] else "Confirmed late payment",
                    points=payment_points,
                )
        events.append(event)

    settled_periods.update(period for amount, period in net_payments.values() if amount > 0)
    for event, period in missed_events:
        if period in settled_periods:
            event["points"] = 0
            event["reason"] = "Missed rent resolved by a confirmed payment"
    has_effective_history = bool(settled_periods or missed_events or has_monthly_feedback)
    return {
        "score": score_for_events(events) if has_effective_history else None,
        "events": events,
        "confirmed_payment_periods": len(settled_periods),
    }
