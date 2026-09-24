use crate::batch::AuditBatch;
use crate::handler::Archiver;

pub(crate) async fn upload(
    archiver: &Archiver,
    batch: &AuditBatch,
) -> anyhow::Result<()> {
    let url = format!(
        "{}/upload/storage/v1/b/{}/o?uploadType=media&name={}",
        archiver.gcp_endpoint, archiver.bucket, urlencoding::encode(&batch.object_key)
    );

    let resp = archiver.http
        .post(&url)
        .header("Content-Type", "application/x-ndjson")
        .header("x-goog-meta-sha256", &batch.checksum)
        .body(batch.ndjson.clone())
        .send()
        .await?;

    if !resp.status().is_success() {
        return Err(anyhow::anyhow!("GCS upload failed: HTTP {}", resp.status()));
    }

    Ok(())
}
