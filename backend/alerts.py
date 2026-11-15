from datetime import datetime, timezone

from sqlalchemy import select

from .models import AlertEvent, AlertRule, TradingSignal


def rule_matches_signal(rule, signal):
    condition = rule.condition.upper()
    signal_type = signal.signal_type.upper()
    mentioned_types = {
        signal_name
        for signal_name in ("BUY", "SELL", "HOLD")
        if signal_name in condition
    }
    return not mentioned_types or signal_type in mentioned_types


def create_signal_alert_events(db, signal):
    """Create missing user alert events for one newly-created trading signal."""
    rules = db.scalars(
        select(AlertRule).where(
            AlertRule.ticker == signal.ticker,
            AlertRule.enabled.is_(True),
        )
    ).all()
    created = []
    for rule in rules:
        if not rule_matches_signal(rule, signal):
            continue
        existing = db.scalar(
            select(AlertEvent).where(
                AlertEvent.rule_id == rule.id,
                AlertEvent.signal_id == signal.id,
            )
        )
        if existing is not None:
            continue
        event = AlertEvent(
            user_id=rule.user_id,
            rule_id=rule.id,
            signal_id=signal.id,
            title=f"{signal.ticker} changed to {signal.signal_type}",
            detail=f"{signal.model_name or 'Signal model'} signal generated",
            tone=signal.signal_type.lower(),
            created_at=(
                signal.created_at
                if isinstance(signal.created_at, datetime)
                else datetime.now(timezone.utc).replace(tzinfo=None)
            ),
        )
        db.add(event)
        created.append(event)
    if created:
        db.flush()
    return created


def sync_signal_alert_events(db):
    """Backfill events for existing signals and enabled rules without duplicates."""
    signals = db.scalars(select(TradingSignal)).all()
    created = []
    for signal in signals:
        created.extend(create_signal_alert_events(db, signal))
    if created:
        db.commit()
    return created
