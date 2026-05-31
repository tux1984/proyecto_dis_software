"""Pruebas unitarias del dominio: value objects y máquinas de estado (State)."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.domain.entities import Enrollment, Event
from app.domain.errors import (
    InvalidStateTransitionError,
    NoCapacityError,
    ValidationError,
)
from app.domain.value_objects import (
    CapacityCount,
    EmailAddress,
    EventStatus,
    Modality,
    RegistrationStatus,
)


@pytest.mark.unit
class TestValueObjects:
    def test_email_valid(self):
        assert str(EmailAddress("a@b.co")) == "a@b.co"

    def test_email_invalid(self):
        with pytest.raises(ValidationError):
            EmailAddress("no-arroba")

    def test_capacity_available(self):
        cap = CapacityCount(total=10, confirmed=3)
        assert cap.available == 7 and cap.has_capacity

    def test_capacity_no_oversell_invariant(self):
        with pytest.raises(ValidationError):
            CapacityCount(total=5, confirmed=6)

    def test_capacity_reserve_one_until_full(self):
        cap = CapacityCount(total=1, confirmed=0)
        cap = cap.reserve_one()
        assert cap.confirmed == 1 and not cap.has_capacity
        with pytest.raises(NoCapacityError):
            cap.reserve_one()


@pytest.mark.unit
class TestEnrollmentState:
    def _pending(self) -> Enrollment:
        from datetime import datetime, timezone

        return Enrollment.new_pending_payment(
            uuid4(), uuid4(), reserved_until=datetime.now(tz=timezone.utc)
        )

    def test_free_starts_confirmed(self):
        enr = Enrollment.new_free(uuid4(), uuid4())
        assert enr.status == RegistrationStatus.CONFIRMADA

    def test_pending_to_confirmed(self):
        enr = self._pending()
        enr.confirm(payment_reference="ref-1")
        assert enr.is_confirmed and enr.payment_reference == "ref-1"

    def test_pending_to_expired(self):
        enr = self._pending()
        enr.expire()
        assert enr.status == RegistrationStatus.EXPIRADA

    def test_confirmed_cannot_expire(self):
        enr = Enrollment.new_free(uuid4(), uuid4())
        with pytest.raises(InvalidStateTransitionError):
            enr.expire()

    def test_cancelled_is_terminal(self):
        enr = Enrollment.new_free(uuid4(), uuid4())
        enr.cancel()
        with pytest.raises(InvalidStateTransitionError):
            enr.confirm()


@pytest.mark.unit
class TestEventState:
    def _draft(self) -> Event:
        from datetime import datetime, timedelta, timezone

        now = datetime.now(tz=timezone.utc)
        return Event(
            id=uuid4(), title="X", description="Y", modality=Modality.VIRTUAL,
            starts_at=now + timedelta(days=1), ends_at=now + timedelta(days=1, hours=1),
            capacity=10, organizer_id=uuid4(),
        )

    def test_publish_from_draft(self):
        ev = self._draft()
        ev.publish()
        assert ev.status == EventStatus.PUBLICADO and ev.is_visible

    def test_approval_flow(self):
        ev = self._draft()
        ev.submit_for_approval()
        assert ev.status == EventStatus.PENDIENTE
        ev.approve()
        assert ev.status == EventStatus.PUBLICADO

    def test_cancel_published(self):
        ev = self._draft()
        ev.publish()
        ev.cancel()
        assert ev.status == EventStatus.CANCELADO and not ev.is_visible

    def test_cancelled_cannot_publish(self):
        ev = self._draft()
        ev.publish()
        ev.cancel()
        with pytest.raises(InvalidStateTransitionError):
            ev.publish()

    def test_invalid_dates_rejected(self):
        from datetime import datetime, timedelta, timezone

        now = datetime.now(tz=timezone.utc)
        with pytest.raises(ValidationError):
            Event(
                id=uuid4(), title="X", description="Y", modality=Modality.VIRTUAL,
                starts_at=now, ends_at=now - timedelta(hours=1),
                capacity=10, organizer_id=uuid4(),
            )
