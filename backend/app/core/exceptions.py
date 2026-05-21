from __future__ import annotations


class AppError(Exception):
    """Base application error with error code and HTTP status."""

    def __init__(
        self,
        message: str,
        code: str = "INTERNAL_ERROR",
        status_code: int = 500,
    ) -> None:
        self.message = message
        self.code = code
        self.status_code = status_code
        super().__init__(message)


class NotFoundError(AppError):
    def __init__(self, entity: str, identifier: str) -> None:
        super().__init__(
            message=f"{entity} not found: {identifier}",
            code="NOT_FOUND",
            status_code=404,
        )


class ConflictError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(message=message, code="CONFLICT", status_code=409)


class ValidationError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(message=message, code="VALIDATION_ERROR", status_code=422)


class StorageError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(message=message, code="STORAGE_ERROR", status_code=500)


class EmbeddingGenerationError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(message=message, code="EMBEDDING_ERROR", status_code=500)


class ClusteringError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(message=message, code="CLUSTERING_ERROR", status_code=500)


class VLMAnalysisError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(message=message, code="VLM_ERROR", status_code=500)


class TrainingError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(message=message, code="TRAINING_ERROR", status_code=500)


class DeploymentError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(message=message, code="DEPLOYMENT_ERROR", status_code=500)


class ModelNotFoundError(AppError):
    def __init__(self, model_name: str, version: str) -> None:
        super().__init__(
            message=f"Model {model_name} version {version} not found",
            code="MODEL_NOT_FOUND",
            status_code=404,
        )
