use crate::batch::AuditBatch;
use aws_sdk_s3::{Client as S3Client, primitives::ByteStream};
use lambda_runtime::Error as LambdaError;

pub(crate) async fn upload(
    s3: &S3Client,
    bucket: &str,
    batch: &AuditBatch,
) -> Result<(), LambdaError> {
    s3.put_object()
        .bucket(bucket)
        .key(&batch.object_key)
        .content_type("application/x-ndjson")
        .metadata("sha256", &batch.checksum)
        .body(ByteStream::from(batch.ndjson.clone()))
        .send()
        .await?;
    Ok(())
}
