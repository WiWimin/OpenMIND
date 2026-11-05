from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, File, UploadFile, status

from app.api.deps import CurrentUser, DbSession
from app.api.page import PageParams, list_envelope
from app.schemas.common import Envelope, ListData
from app.schemas.knowledge import (
    KnowledgeDeleteResult,
    KnowledgeDocumentRead,
    KnowledgeSearchHit,
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
)
from app.services import knowledge_service

router = APIRouter(tags=["knowledge"])


@router.post(
    "/knowledge/documents",
    status_code=status.HTTP_201_CREATED,
    response_model=Envelope[KnowledgeDocumentRead],
)
async def upload_document(
    db: DbSession,
    current_user: CurrentUser,
    file: Annotated[UploadFile, File()],
) -> Envelope[KnowledgeDocumentRead]:
    content = await file.read()
    document = knowledge_service.upload_document(
        db,
        user_id=current_user.user_id,
        file_name=file.filename or "upload",
        content=content,
    )
    return Envelope(data=KnowledgeDocumentRead.model_validate(document))


@router.get(
    "/knowledge/documents",
    response_model=Envelope[ListData[KnowledgeDocumentRead]],
)
def list_documents(
    db: DbSession,
    current_user: CurrentUser,
    params: PageParams,
) -> Envelope[ListData[KnowledgeDocumentRead]]:
    items, total = knowledge_service.list_documents(
        db, user_id=current_user.user_id, page=params.page, page_size=params.page_size
    )
    return list_envelope(
        items,
        KnowledgeDocumentRead,
        page=params.page,
        page_size=params.page_size,
        total=total,
    )


@router.get(
    "/knowledge/documents/{document_id}",
    response_model=Envelope[KnowledgeDocumentRead],
)
def get_document(
    document_id: str, db: DbSession, current_user: CurrentUser
) -> Envelope[KnowledgeDocumentRead]:
    document = knowledge_service.get_owned_document(
        db, document_id, current_user.user_id
    )
    return Envelope(data=KnowledgeDocumentRead.model_validate(document))


@router.delete(
    "/knowledge/documents/{document_id}",
    response_model=Envelope[KnowledgeDeleteResult],
)
def delete_document(
    document_id: str, db: DbSession, current_user: CurrentUser
) -> Envelope[KnowledgeDeleteResult]:
    knowledge_service.delete_document(db, document_id, current_user.user_id)
    return Envelope(data=KnowledgeDeleteResult(document_id=document_id))


@router.post(
    "/knowledge/search",
    response_model=Envelope[KnowledgeSearchResponse],
)
def search_documents(
    payload: KnowledgeSearchRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> Envelope[KnowledgeSearchResponse]:
    items = knowledge_service.search_documents(
        db,
        user_id=current_user.user_id,
        query=payload.query,
        top_k=payload.top_k,
        min_score=payload.min_score,
    )
    return Envelope(
        data=KnowledgeSearchResponse(
            items=[
                KnowledgeSearchHit(
                    document_id=item.document_id,
                    file_name=item.document_name,
                    excerpt=item.excerpt,
                    score=item.score,
                )
                for item in items
            ]
        )
    )
