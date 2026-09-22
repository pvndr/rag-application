import json
from collections.abc import Iterator

from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse, StreamingResponse

from app.api.dependencies import get_auth_service, get_current_user, get_provider_service, get_rag_service
from app.api.schemas import (
    AnswerResponse,
    AuthResponse,
    CitationResponse,
    ConversationDetailResponse,
    DocumentDetailResponse,
    DocumentPreviewResponse,
    DocumentResponse,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    HealthResponse,
    LoginRequest,
    MessageResponse,
    ProviderStatusResponse,
    QuestionRequest,
    ConversationResponse,
    RefreshTokenRequest,
    RegisterRequest,
    RenameConversationRequest,
    ResetPasswordRequest,
    SaveProviderCredentialRequest,
    SearchRequest,
    SearchResponse,
    UploadStatusResponse,
    UserResponse,
)
from app.application.auth_service import AuthError, AuthService, TokenPair
from app.application.errors import DocumentUploadError
from app.application.provider_service import ProviderService, ProviderServiceError
from app.application.rag_service import RagService
from app.core.config import settings
from app.domain.entities import ConversationMessage, ConversationSession, Document, User

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        environment=settings.environment,
    )


@router.post("/api/auth/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(
    request: RegisterRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> AuthResponse:
    try:
        user, tokens = auth_service.register(request.name, request.email, request.password)
    except AuthError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _auth_response(user, tokens)


@router.post("/api/auth/login", response_model=AuthResponse)
def login(
    request: LoginRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> AuthResponse:
    try:
        user, tokens = auth_service.login(request.email, request.password)
    except AuthError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    return _auth_response(user, tokens)


@router.post("/api/auth/refresh", response_model=AuthResponse)
def refresh_token(
    request: RefreshTokenRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> AuthResponse:
    try:
        tokens = auth_service.refresh(request.refresh_token)
        user = auth_service.get_user_from_access_token(tokens.access_token)
    except AuthError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    return _auth_response(user, tokens)


@router.post("/api/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: RefreshTokenRequest,
    auth_service: AuthService = Depends(get_auth_service),
    _: User = Depends(get_current_user),
) -> None:
    auth_service.logout(request.refresh_token)


@router.get("/api/auth/me", response_model=UserResponse)
def profile(user: User = Depends(get_current_user)) -> UserResponse:
    return _user_response(user)


@router.post("/api/auth/forgot-password", response_model=ForgotPasswordResponse)
def forgot_password(
    request: ForgotPasswordRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> ForgotPasswordResponse:
    try:
        auth_service.send_password_reset_email(request.email)
    except AuthError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    return ForgotPasswordResponse(
        message="If an account exists for this email, a password reset link has been sent.",
    )


@router.post("/api/auth/reset-password", status_code=status.HTTP_204_NO_CONTENT)
def reset_password(
    request: ResetPasswordRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> None:
    try:
        auth_service.reset_password(request.reset_token, request.new_password)
    except AuthError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/api/settings/providers", response_model=list[ProviderStatusResponse])
def list_providers(
    user: User = Depends(get_current_user),
    provider_service: ProviderService = Depends(get_provider_service),
) -> list[ProviderStatusResponse]:
    statuses = provider_service.list_provider_statuses(user.id)
    return [
        ProviderStatusResponse(
            provider=s.provider,
            masked_key=s.masked_key,
            is_configured=s.is_configured,
            is_custom=s.is_custom,
            has_system_fallback=s.has_system_fallback,
            updated_at=s.updated_at,
        )
        for s in statuses
    ]


@router.put("/api/settings/providers", response_model=ProviderStatusResponse)
def save_provider(
    request: SaveProviderCredentialRequest,
    user: User = Depends(get_current_user),
    provider_service: ProviderService = Depends(get_provider_service),
) -> ProviderStatusResponse:
    try:
        status_info = provider_service.save_provider_key(
            user_id=user.id,
            provider=request.provider,
            api_key=request.api_key,
        )
    except ProviderServiceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return ProviderStatusResponse(
        provider=status_info.provider,
        masked_key=status_info.masked_key,
        is_configured=status_info.is_configured,
        is_custom=status_info.is_custom,
        has_system_fallback=status_info.has_system_fallback,
        updated_at=status_info.updated_at,
    )


@router.delete("/api/settings/providers/{provider}", status_code=status.HTTP_204_NO_CONTENT)
def delete_provider(
    provider: str,
    user: User = Depends(get_current_user),
    provider_service: ProviderService = Depends(get_provider_service),
) -> None:
    try:
        provider_service.delete_provider_key(user_id=user.id, provider=provider)
    except ProviderServiceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post(
    "/api/documents",
    response_model=UploadStatusResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    file: UploadFile = File(...),
    service: RagService = Depends(get_rag_service),
    user: User = Depends(get_current_user),
) -> UploadStatusResponse:
    filename = file.filename or "untitled"
    content_type = file.content_type or "application/octet-stream"
    _validate_upload(filename, content_type)

    contents = await file.read()
    if len(contents) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Uploaded file exceeds the configured size limit.",
        )

    try:
        document = service.ingest_document(user.id, filename, content_type, contents)
    except DocumentUploadError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=str(exc),
        ) from exc

    return UploadStatusResponse(
        status=document.status,
        message="Document uploaded, extracted, chunked, embedded, and indexed.",
        document=_document_response(document),
    )


@router.get("/api/documents", response_model=list[DocumentResponse])
def list_documents(
    service: RagService = Depends(get_rag_service),
    user: User = Depends(get_current_user),
) -> list[DocumentResponse]:
    return [_document_response(document) for document in service.list_documents(user.id)]


@router.get("/api/documents/{document_id}", response_model=DocumentDetailResponse)
def get_document(
    document_id: str,
    service: RagService = Depends(get_rag_service),
    user: User = Depends(get_current_user),
) -> DocumentDetailResponse:
    document = service.get_document(document_id, user.id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
    return _document_detail_response(document)


@router.get("/api/documents/{document_id}/preview", response_model=DocumentPreviewResponse)
def preview_document(
    document_id: str,
    service: RagService = Depends(get_rag_service),
    user: User = Depends(get_current_user),
) -> DocumentPreviewResponse:
    document = service.get_document(document_id, user.id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    return DocumentPreviewResponse(
        id=document.id,
        filename=document.filename,
        content_type=document.content_type,
        render_mode="pdf" if document.content_type == "application/pdf" else "text",
        text=document.text,
        file_url=f"/api/documents/{document.id}/file",
    )


@router.get("/api/documents/{document_id}/file")
def view_document_file(
    document_id: str,
    request: Request,
    access_token: str | None = None,
    service: RagService = Depends(get_rag_service),
    auth_service: AuthService = Depends(get_auth_service),
) -> FileResponse:
    user = _user_from_request_token(request, access_token, auth_service)
    document = service.get_document(document_id, user.id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    path = Path(document.file_path)
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Original file not found.")

    return FileResponse(
        path,
        media_type=document.content_type,
        filename=document.filename,
        content_disposition_type="inline",
    )


def _user_from_request_token(
    request: Request,
    access_token: str | None,
    auth_service: AuthService,
) -> User:
    header = request.headers.get("Authorization", "")
    token = access_token
    if header.lower().startswith("bearer "):
        token = header.split(" ", maxsplit=1)[1]
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")
    try:
        return auth_service.get_user_from_access_token(token)
    except AuthError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc


@router.delete("/api/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: str,
    service: RagService = Depends(get_rag_service),
    user: User = Depends(get_current_user),
) -> None:
    service.delete_document(document_id, user.id)


@router.post("/api/documents/{document_id}/reindex", response_model=UploadStatusResponse)
def reindex_document(
    document_id: str,
    service: RagService = Depends(get_rag_service),
    user: User = Depends(get_current_user),
) -> UploadStatusResponse:
    try:
        document = service.reindex_document(document_id, user.id)
    except DocumentUploadError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    return UploadStatusResponse(
        status=document.status,
        message="Document re-indexed and synchronized with ChromaDB.",
        document=_document_response(document),
    )


@router.post("/api/search", response_model=SearchResponse)
def search(
    request: SearchRequest,
    service: RagService = Depends(get_rag_service),
    user: User = Depends(get_current_user),
) -> SearchResponse:
    try:
        results = service.search_chunks(user.id, request.query, limit=request.limit)
    except DocumentUploadError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=str(exc),
        ) from exc

    return SearchResponse(
        query=request.query,
        results=[
            CitationResponse(
                document_id=result.document_id,
                filename=result.filename,
                chunk_id=result.chunk_id,
                text=result.text,
                score=result.score,
                metadata=result.metadata,
            )
            for result in results
        ],
    )


@router.get("/api/conversations", response_model=list[ConversationDetailResponse])
def list_conversations(
    service: RagService = Depends(get_rag_service),
    user: User = Depends(get_current_user),
) -> list[ConversationDetailResponse]:
    return [_conversation_response(session) for session in service.list_conversations(user.id)]


@router.patch("/api/conversations/{session_id}", response_model=ConversationResponse)
def rename_conversation(
    session_id: str,
    request: RenameConversationRequest,
    service: RagService = Depends(get_rag_service),
    user: User = Depends(get_current_user),
) -> ConversationResponse:
    title = service.rename_conversation(user.id, session_id, request.title.strip())
    return ConversationResponse(id=session_id, title=title)


@router.delete("/api/conversations/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(
    session_id: str,
    service: RagService = Depends(get_rag_service),
    user: User = Depends(get_current_user),
) -> None:
    service.delete_conversation(user.id, session_id)


@router.post("/api/chat", response_model=AnswerResponse)
def chat(
    request: QuestionRequest,
    service: RagService = Depends(get_rag_service),
    user: User = Depends(get_current_user),
) -> AnswerResponse:
    try:
        answer = service.answer_question(
            user.id,
            request.question,
            limit=request.limit,
            session_id=request.session_id,
        )
    except DocumentUploadError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=str(exc),
        ) from exc
    return AnswerResponse(
        answer=answer.response.answer,
        summary=answer.response.summary,
        key_points=answer.response.key_points,
        sources=[
            {"document": source.document, "page": source.page}
            for source in answer.response.sources
        ],
        confidence=answer.response.confidence,
        follow_up_questions=answer.response.follow_up_questions,
        session_id=request.session_id,
        citations=[
            CitationResponse(
                document_id=citation.document_id,
                filename=citation.filename,
                chunk_id=citation.chunk_id,
                text=citation.text,
                score=citation.score,
                metadata=citation.metadata,
            )
            for citation in answer.citations
        ],
    )


@router.post("/api/chat/stream")
def chat_stream(
    request: QuestionRequest,
    service: RagService = Depends(get_rag_service),
    user: User = Depends(get_current_user),
) -> StreamingResponse:
    try:
        answer = service.answer_question(
            user.id,
            request.question,
            limit=request.limit,
            session_id=request.session_id,
        )
    except DocumentUploadError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=str(exc),
        ) from exc

    def events() -> Iterator[str]:
        structured_response = {
            "answer": answer.response.answer,
            "summary": answer.response.summary,
            "key_points": answer.response.key_points,
            "sources": [
                {"document": source.document, "page": source.page}
                for source in answer.response.sources
            ],
            "confidence": answer.response.confidence,
            "follow_up_questions": answer.response.follow_up_questions,
        }
        citations = [
            CitationResponse(
                document_id=citation.document_id,
                filename=citation.filename,
                chunk_id=citation.chunk_id,
                text=citation.text,
                score=citation.score,
                metadata=citation.metadata,
            ).model_dump()
            for citation in answer.citations
        ]
        yield _stream_event("sources", citations)
        yield _stream_event("structured", structured_response)

        words = answer.response.answer.split(" ")
        for index, word in enumerate(words):
            suffix = "" if index == len(words) - 1 else " "
            yield _stream_event("delta", f"{word}{suffix}")

        yield _stream_event("done", {"ok": True})

    return StreamingResponse(events(), media_type="application/x-ndjson")


def _document_response(document: Document) -> DocumentResponse:
    return DocumentResponse(
        id=document.id,
        filename=document.filename,
        content_type=document.content_type,
        status=document.status,
        created_at=document.created_at,
        characters=len(document.text),
        size_bytes=document.size_bytes,
        chunk_count=document.chunk_count,
    )


def _auth_response(user: User, tokens: TokenPair) -> AuthResponse:
    return AuthResponse(
        user=_user_response(user),
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        token_type=tokens.token_type,
        expires_in=tokens.expires_in,
    )


def _user_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        name=user.name,
        email=user.email,
        role=user.role,
        is_verified=user.is_verified,
        created_at=user.created_at,
    )


def _conversation_response(session: ConversationSession) -> ConversationDetailResponse:
    return ConversationDetailResponse(
        id=session.id,
        title=session.title,
        created_at=session.created_at,
        updated_at=session.updated_at,
        messages=[_message_response(message) for message in session.messages],
    )


def _message_response(message: ConversationMessage) -> MessageResponse:
    return MessageResponse(
        id=message.id,
        chat_id=message.chat_id or "",
        role=message.role,
        content=message.content,
        structured=message.structured,
        created_at=message.created_at,
    )


def _document_detail_response(document: Document) -> DocumentDetailResponse:
    return DocumentDetailResponse(
        id=document.id,
        filename=document.filename,
        content_type=document.content_type,
        status=document.status,
        created_at=document.created_at,
        characters=len(document.text),
        size_bytes=document.size_bytes,
        chunk_count=document.chunk_count,
        file_path=document.file_path,
        metadata={
            "document_id": document.id,
            "filename": document.filename,
            "content_type": document.content_type,
            "size_bytes": document.size_bytes,
            "chunk_count": document.chunk_count,
            "created_at": document.created_at.isoformat(),
        },
    )


def _validate_upload(filename: str, content_type: str) -> None:
    extension = filename.lower().rsplit(".", maxsplit=1)[-1] if "." in filename else ""
    allowed_extensions = {"pdf", "docx", "txt"}
    allowed_content_types = {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "text/plain",
        "application/octet-stream",
    }

    if extension not in allowed_extensions or content_type not in allowed_content_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file type. Upload a PDF, DOCX, or TXT file.",
        )


def _stream_event(event: str, data: object) -> str:
    return json.dumps({"event": event, "data": data}) + "\n"
