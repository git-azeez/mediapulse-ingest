use crate::batch::PendingEvent;
use serde_json::Value;
use sqlx::{PgPool, Row};
use uuid::Uuid;

pub(crate) async fn find_pending(db: &PgPool) -> Result<Vec<PendingEvent>, sqlx::Error> {
    let rows = sqlx::query(
        "SELECT e.sequence_number, e.event_id, e.payload
         FROM cinderroute.events e
         JOIN cinderroute.outbox o ON o.event_id=e.event_id AND o.published_at IS NOT NULL
         LEFT JOIN cinderroute.audit_archives a ON a.event_id=e.event_id
         WHERE a.event_id IS NULL
         ORDER BY e.sequence_number LIMIT 500",
    )
    .fetch_all(db)
    .await?;

    Ok(rows
        .into_iter()
        .map(|row| PendingEvent {
            sequence_number: row.get("sequence_number"),
            event_id: row.get("event_id"),
            payload: row.get::<Value, _>("payload"),
        })
        .collect())
}

pub(crate) async fn mark_archived(
    db: &PgPool,
    event_ids: &[Uuid],
    object_key: &str,
) -> Result<(), sqlx::Error> {
    let mut tx = db.begin().await?;
    for event_id in event_ids {
        sqlx::query(
            "INSERT INTO cinderroute.audit_archives(event_id, object_key, archived_at)
             VALUES ($1,$2,now()) ON CONFLICT (event_id) DO NOTHING",
        )
        .bind(event_id)
        .bind(object_key)
        .execute(&mut *tx)
        .await?;
    }
    tx.commit().await
}
