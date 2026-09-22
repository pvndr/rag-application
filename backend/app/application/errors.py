class DocumentUploadError(Exception):
    status_code = 400


class UnsupportedFileTypeError(DocumentUploadError):
    pass


class EmptyDocumentError(DocumentUploadError):
    pass


class DocumentExtractionError(DocumentUploadError):
    pass


class EmbeddingModelError(DocumentUploadError):
    status_code = 503


class AnswerGenerationError(DocumentUploadError):
    status_code = 503
