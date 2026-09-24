use crate::error::{ApiError, ApiResult};
use cinderroute::model::{CreateShipmentRequest, RecordCheckpointRequest, ShipmentStatus};

pub(super) fn create(input: &CreateShipmentRequest) -> ApiResult<()> {
    validate_text("ownerId", &input.owner_id, 1, 128)?;
    validate_text("reference", &input.reference, 1, 128)?;
    validate_text("origin", &input.origin, 1, 256)?;
    validate_text("destination", &input.destination, 1, 256)
}

pub(super) fn checkpoint(input: &RecordCheckpointRequest) -> ApiResult<()> {
    validate_text("location", &input.location, 1, 256)?;
    if let Some(note) = &input.note {
        validate_text("note", note, 0, 1000)?;
    }
    if input.status == ShipmentStatus::Created {
        return Err(ApiError::bad_request("CREATED is not a checkpoint status"));
    }
    Ok(())
}

fn validate_text(name: &str, value: &str, min: usize, max: usize) -> ApiResult<()> {
    let length = value.chars().count();
    if length < min || length > max {
        Err(ApiError::bad_request(format!(
            "{name} length must be between {min} and {max}"
        )))
    } else {
        Ok(())
    }
}
