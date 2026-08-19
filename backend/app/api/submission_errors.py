"""HTTP mapping for approval and submission domain errors."""

from fastapi import HTTPException, status

from app.core import (
    ApprovalNotFoundError,
    InvalidApprovalStateError,
    InvalidSubmissionStateError,
    MissingRequiredDocumentsError,
    SubmissionDefinitionError,
    SubmissionTaskNotFoundError,
)


def submission_http_error(error: Exception) -> HTTPException:
    if isinstance(error, (ApprovalNotFoundError, SubmissionTaskNotFoundError)):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error))
    if isinstance(error, MissingRequiredDocumentsError):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "message": str(error),
                "missing_document_types": error.missing_document_types,
            },
        )
    if isinstance(error, (InvalidApprovalStateError, InvalidSubmissionStateError)):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error))
    if isinstance(error, SubmissionDefinitionError):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        )
    raise error
