#!/usr/bin/env python3
"""Seed development data into the database."""

from __future__ import annotations

import asyncio
import random
from datetime import datetime, timedelta, timezone

from app.core.security import generate_uuid
from app.infrastructure.database.session import async_session_factory
from app.models.anomaly import AnomalyRecord

CAMERAS = ["left_top", "left_bottom", "right_top", "right_bottom"]
SOURCES = ["patchcore", "filter_classifier", "rule_engine"]


async def seed() -> None:
    async with async_session_factory() as session:
        base_date = datetime.now(tz=timezone.utc)
        records = []

        for day_offset in range(7):
            date_folder = (base_date - timedelta(days=day_offset)).strftime("%Y-%m-%d")
            for _ in range(random.randint(10, 30)):
                record = AnomalyRecord(
                    id=generate_uuid(),
                    camera_id=random.choice(CAMERAS),
                    source=random.choice(SOURCES),
                    anomaly_score=random.uniform(0.5, 1.0),
                    date_folder=date_folder,
                    detected_at=base_date - timedelta(
                        days=day_offset, hours=random.randint(0, 23)
                    ),
                    status=random.choice(["pending", "embedded", "clustered", "reviewed"]),
                )
                records.append(record)

        session.add_all(records)
        await session.commit()
        print(f"Seeded {len(records)} anomaly records")


if __name__ == "__main__":
    asyncio.run(seed())
