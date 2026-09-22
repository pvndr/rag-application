from datetime import datetime

from pydantic import BaseModel, Field, field_validator


PASSWORD_POLICY_MESSAGE = (
    "Password must be at least 8 characters and include at least one uppercase "
    "letter, one lowercase letter, one number, and one special character."
)


def validate_password_policy(password: str) -> str:
    has_upper = any(char.isupper() for char in password)
    has_lower = any(char.islower() for char in password)
    has_number = any(char.isdigit() for char in password)
    has_special = any(not char.isalnum() for char in password)
    if len(password) < 8 or not all([has_upper, has_lower, has_number, has_special]):
        raise ValueError(PASSWORD_POLICY_MESSAGE)
    return password


class UserResponse(BaseModel):
    id: str
    name: str
    email: str
    role: str
    is_verified: bool
    created_at: datetime


class RegisterRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=80)
    email: str = Field(..., min_length=5, max_length=255)
    password: str = Field(..., min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def password_meets_policy(cls, password: str) -> str:
        return validate_password_policy(password)


class LoginRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=255)
    password: str = Field(..., min_length=8, max_length=128)


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(..., min_length=20)


class ForgotPasswordRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=255)


class ResetPasswordRequest(BaseModel):
    reset_token: str = Field(..., min_length=20)
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def password_meets_policy(cls, password: str) -> str:
        return validate_password_policy(password)


class AuthResponse(BaseModel):
    user: UserResponse
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int


class ForgotPasswordResponse(BaseModel):
    message: str


class DocumentResponse(BaseModel):
    id: str
    filename: str
    content_type: str
    status: str
    created_at: datetime
    characters: int
    size_bytes: int
    chunk_count: int


class DocumentDetailResponse(DocumentResponse):
    file_path: str
    metadata: dict[str, str | int | float] = Field(default_factory=dict)


class DocumentPreviewResponse(BaseModel):
    id: str
    filename: str
    content_type: str
    render_mode: str
    text: str
    file_url: str


class UploadStatusResponse(BaseModel):
    status: str
    message: str
    document: DocumentResponse


class QuestionRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000)
    limit: int = Field(default=4, ge=1, le=10)
    session_id: str = Field(default="default", min_length=1, max_length=120)


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000)
    limit: int = Field(default=5, ge=1, le=20)


class RenameConversationRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=80)


class ConversationResponse(BaseModel):
    id: str
    title: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


class MessageResponse(BaseModel):
    id: str
    chat_id: str
    role: str
    content: str
    structured: dict | None = None
    created_at: datetime


class ConversationDetailResponse(ConversationResponse):
    messages: list[MessageResponse] = Field(default_factory=list)


class CitationResponse(BaseModel):
    document_id: str
    filename: str
    chunk_id: str
    text: str
    score: float
    metadata: dict[str, str | int | float] = Field(default_factory=dict)


class SourceReferenceResponse(BaseModel):
    document: str
    page: int | None = None


class AnswerResponse(BaseModel):
    answer: str
    summary: str
    key_points: list[str] = Field(default_factory=list)
    sources: list[SourceReferenceResponse] = Field(default_factory=list)
    confidence: str
    follow_up_questions: list[str] = Field(default_factory=list)
    citations: list[CitationResponse]
    session_id: str = "default"


class SearchResponse(BaseModel):
    query: str
    results: list[CitationResponse]


class HealthResponse(BaseModel):
    status: str
    service: str
    environment: str


class SaveProviderCredentialRequest(BaseModel):
    provider: str = Field(default="gemini", min_length=1, max_length=50)
    api_key: str = Field(..., min_length=1, max_length=500)


class ProviderStatusResponse(BaseModel):
    provider: str
    masked_key: str | None = None
    is_configured: bool
    is_custom: bool
    has_system_fallback: bool
    updated_at: datetime | None = None
