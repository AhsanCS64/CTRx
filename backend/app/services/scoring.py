"""Explain a tenant's score using verified ledger history."""

from sqlalchemy import text
from sqlalchemy.orm import Session


def reliability_history(db: Session, tenant_id):
    rows = db.execute(text("""
        WITH payments AS (
        SELECT payment.id, payment.tenancy_id, payment.period_month, payment.paid_on, payment.amount,
               payment.paid_on <= LEAST(
                   payment.period_month + (t.rent_due_day - 1),
                   (payment.period_month + interval '1 month - 1 day')::date
               ) AS on_time
        FROM ledger_entries payment
        JOIN tenancies t ON t.id = payment.tenancy_id
        WHERE t.tenant_id = :tenant AND payment.entry_type = 'payment'
        ), corrections AS (
            SELECT c.id, p.period_month, p.paid_on, p.on_time, c.amount,
                   p.amount + sum(c.amount) OVER (
                       PARTITION BY p.id ORDER BY c.created_at, c.id ROWS UNBOUNDED PRECEDING
                   ) AS balance
            FROM payments p
            JOIN ledger_entries c ON c.corrects_entry_id = p.id
                AND c.tenancy_id = p.tenancy_id AND c.entry_type = 'correction'
        )
        SELECT id, period_month, paid_on, on_time, NULL AS previous_balance, NULL AS balance FROM payments
        UNION ALL
        SELECT id, period_month, paid_on, on_time, balance - amount, balance FROM corrections
        ORDER BY period_month DESC, id
    """), {"tenant": tenant_id}).mappings()
    events = []
    for row in rows:
        payment_points = 2 if row["on_time"] else -1
        if row["balance"] is not None:
            delta = int(row["balance"] > 0) - int(row["previous_balance"] > 0)
            reason, points = "Ledger correction", delta * payment_points
        elif row["on_time"]:
            reason, points = "Confirmed on-time payment", payment_points
        else:
            reason, points = "Confirmed late payment", payment_points
        events.append({"id": row["id"], "period_month": row["period_month"],
                       "paid_on": row["paid_on"], "reason": reason, "points": points})
    score = max(0, min(100, 50 + sum(event["points"] for event in events))) if events else None
    return {"score": score, "events": events}
