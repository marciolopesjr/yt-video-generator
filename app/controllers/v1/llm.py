# app/controllers/v1/llm.py

from fastapi import Request

from app.controllers.v1.base import new_router
# MODIFIED: Importando e usando os novos schemas
from app.models.schema import (
    VideoScriptRequest,
    VideoScriptResponse,
    VideoTermsRequest,
    VideoTermsResponse,
    StructuredScript
)
from app.services import llm
from app.utils import utils

router = new_router()

# MODIFIED: O endpoint de roteiros agora retorna uma estrutura de cenas.
@router.post(
    "/scripts",
    response_model=VideoScriptResponse,
    summary="Create a structured script for the video with scenes"
)
def generate_video_script(request: Request, body: VideoScriptRequest):
    structured_script = llm.generate_structured_script(
        video_subject=body.video_subject,
        language=body.video_language,
        paragraph_number=body.paragraph_number,
    )
    if not structured_script.scenes:
        return utils.get_response(500, message="Failed to generate structured script")

    return utils.get_response(200, structured_script.dict())


# MODIFIED: O endpoint de termos agora extrai do roteiro estruturado.
@router.post(
    "/terms",
    response_model=VideoTermsResponse,
    summary="Generate video terms based on the video script (DEPRECATED, use script keywords)"
)
def generate_video_terms(request: Request, body: VideoTermsRequest):
    # Esta função agora é considerada legada, mas podemos mantê-la funcional.
    # Primeiro, criamos um roteiro estruturado (mesmo que apenas para extrair palavras-chave)
    structured_script = llm.generate_structured_script(
        video_subject=body.video_subject,
        language="en", # Linguagem não importa muito aqui
        paragraph_number=body.amount
    )
    video_terms = llm.get_aggregated_keywords_from_script(structured_script, amount=body.amount)
    
    response = {"video_terms": video_terms}
    return utils.get_response(200, response)