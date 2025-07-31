# app/services/task.py

import math
import os.path
import re
from os import path

from loguru import logger

from app.config import config
from app.models import const
# MODIFIED: Importando os novos schemas para o roteiro estruturado
from app.models.schema import VideoConcatMode, VideoParams, StructuredScript, Scene
from app.services import llm, material, subtitle, video, voice
from app.services import state as sm
from app.utils import utils

# MODIFIED: Esta função foi reescrita para gerar um roteiro estruturado.
def generate_structured_script(task_id: str, params: VideoParams) -> StructuredScript | None:
    """
    Gera um roteiro estruturado. Se o usuário fornecer um roteiro manual, ele será
    analisado e convertido em uma estrutura de cena. Caso contrário, a IA é usada para
    gerar um roteiro completo a partir do tema.
    """
    logger.info("\n\n## 1. Gerando Roteiro Estruturado por Cenas")

    structured_script = None

    # Caso 1: O usuário forneceu um roteiro de texto personalizado.
    if params.video_script.strip():
        logger.info("Roteiro personalizado detectado. Analisando para criar estrutura de cenas.")
        # Divide o roteiro em frases para simular cenas individuais.
        sentences = utils.split_string_by_punctuations(params.video_script.strip())
        scenes = []
        for i, sentence in enumerate(sentences):
            if not sentence:
                continue
            
            # Cria uma cena para cada frase.
            new_scene = Scene(
                scene_number=i + 1,
                voiceover_text=sentence,
                # A descrição visual será genérica, pois não foi gerada pela IA.
                # A próxima etapa seria usar a IA para gerar esta parte também.
                visual_description=f"A visual representation of: '{sentence}'",
                # As palavras-chave serão extraídas do tema do vídeo ou deixadas em branco.
                keywords=list(set([kw.strip() for kw in params.video_subject.split(",") if kw.strip()]))
            )
            scenes.append(new_scene)
        
        if scenes:
            structured_script = StructuredScript(scenes=scenes)

    # Caso 2: O roteiro precisa ser gerado pela IA a partir de um tema.
    else:
        logger.info("Nenhum roteiro personalizado encontrado. Gerando roteiro com IA a partir do tema.")
        structured_script = llm.generate_structured_script(
            video_subject=params.video_subject,
            language=params.video_language,
            paragraph_number=params.paragraph_number,
        )

    # Validação final e tratamento de erro.
    if not structured_script or not structured_script.scenes:
        sm.state.update_task(task_id, state=const.TASK_STATE_FAILED)
        logger.error("Falha ao gerar o roteiro estruturado. O resultado está vazio ou nulo.")
        return None

    logger.success(f"Roteiro estruturado criado com sucesso com {len(structured_script.scenes)} cenas.")
    return structured_script


# MODIFIED: Salva o novo roteiro estruturado em um arquivo JSON.
def save_script_data(task_id: str, structured_script: StructuredScript, params: VideoParams):
    """
    Salva o roteiro estruturado completo e os parâmetros da tarefa em um arquivo JSON.
    """
    script_file = path.join(utils.task_dir(task_id), "script.json")
    try:
        script_data = {
            "structured_script": structured_script.dict(),
            "params": params.dict(exclude_none=True), # Exclui valores nulos para um JSON mais limpo
        }
        with open(script_file, "w", encoding="utf-8") as f:
            f.write(utils.to_json(script_data))
        logger.info(f"Roteiro e parâmetros salvos em: {script_file}")
    except Exception as e:
        logger.error(f"Erro ao salvar os dados do roteiro: {e}")


def generate_audio(task_id, params, video_script):
    """
    Função auxiliar para encapsular a lógica de geração de áudio.
    """
    logger.info("\n\n## 2. Gerando Áudio")
    audio_file = path.join(utils.task_dir(task_id), "audio.mp3")
    sub_maker = voice.tts(
        text=video_script,
        voice_name=voice.parse_voice_name(params.voice_name),
        voice_rate=params.voice_rate,
        voice_file=audio_file,
    )
    if sub_maker is None:
        sm.state.update_task(task_id, state=const.TASK_STATE_FAILED)
        logger.error("Falha ao gerar áudio.")
        return None, None, None

    audio_duration = math.ceil(voice.get_audio_duration(sub_maker))
    logger.success(f"Áudio gerado com sucesso. Duração: {audio_duration}s")
    return audio_file, audio_duration, sub_maker


def generate_subtitle(task_id, params, video_script, sub_maker, audio_file):
    """
    Função auxiliar para encapsular a lógica de geração de legendas.
    """
    if not params.subtitle_enabled:
        return ""

    logger.info("\n\n## 3. Gerando Legendas")
    subtitle_path = path.join(utils.task_dir(task_id), "subtitle.srt")
    subtitle_provider = config.app.get("subtitle_provider", "edge").strip().lower()

    subtitle_fallback = False
    if subtitle_provider == "edge":
        voice.create_subtitle(
            text=video_script, sub_maker=sub_maker, subtitle_file=subtitle_path
        )
        if not os.path.exists(subtitle_path):
            subtitle_fallback = True
            logger.warning("Arquivo de legenda não encontrado, usando Whisper como fallback.")

    if subtitle_provider == "whisper" or subtitle_fallback:
        subtitle.create(audio_file=audio_file, subtitle_file=subtitle_path)
        logger.info("Corrigindo legendas...")
        subtitle.correct(subtitle_file=subtitle_path, video_script=video_script)

    subtitle_lines = subtitle.file_to_subtitles(subtitle_path)
    if not subtitle_lines:
        logger.warning(f"Arquivo de legenda inválido ou vazio: {subtitle_path}")
        return ""
    
    logger.success(f"Legendas geradas com sucesso: {subtitle_path}")
    return subtitle_path


def get_video_materials(task_id, params, video_terms, audio_duration):
    """
    Função auxiliar para baixar materiais de vídeo de fontes online ou locais.
    """
    logger.info(f"\n\n## 4. Obtendo Materiais de Vídeo (Fonte: {params.video_source})")
    
    if params.video_source == "local":
        materials = video.preprocess_video(
            materials=params.video_materials, clip_duration=params.video_clip_duration
        )
        if not materials:
            sm.state.update_task(task_id, state=const.TASK_STATE_FAILED)
            logger.error("Nenhum material local válido encontrado.")
            return None
        return [material_info.url for material_info in materials]
    else:
        downloaded_videos = material.download_videos(
            task_id=task_id,
            search_terms=video_terms,
            source=params.video_source,
            video_aspect=params.video_aspect,
            video_contact_mode=params.video_concat_mode,
            audio_duration=audio_duration * params.video_count,
            max_clip_duration=params.video_clip_duration,
        )
        if not downloaded_videos:
            sm.state.update_task(task_id, state=const.TASK_STATE_FAILED)
            logger.error("Falha ao baixar vídeos.")
            return None
        return downloaded_videos


def generate_final_videos(task_id, params, downloaded_videos, audio_file, subtitle_path):
    """
    Função auxiliar para combinar clipes e renderizar o vídeo final com áudio e legendas.
    """
    logger.info("\n\n## 5. Gerando Vídeos Finais")
    final_video_paths = []
    combined_video_paths = []
    
    _progress = 50
    for i in range(params.video_count):
        index = i + 1
        combined_video_path = path.join(utils.task_dir(task_id), f"combined-{index}.mp4")
        logger.info(f"Combinando vídeo: {index} => {combined_video_path}")
        video.combine_videos(
            combined_video_path=combined_video_path,
            video_paths=downloaded_videos,
            audio_file=audio_file,
            video_aspect=params.video_aspect,
            video_concat_mode=params.video_concat_mode,
            video_transition_mode=params.video_transition_mode,
            max_clip_duration=params.video_clip_duration,
            threads=params.n_threads,
        )

        _progress += 50 / params.video_count / 2
        sm.state.update_task(task_id, progress=_progress)

        final_video_path = path.join(utils.task_dir(task_id), f"final-{index}.mp4")
        logger.info(f"Renderizando vídeo final: {index} => {final_video_path}")
        video.generate_video(
            video_path=combined_video_path,
            audio_path=audio_file,
            subtitle_path=subtitle_path,
            output_file=final_video_path,
            params=params,
        )

        _progress += 50 / params.video_count / 2
        sm.state.update_task(task_id, progress=_progress)

        final_video_paths.append(final_video_path)
        combined_video_paths.append(combined_video_path)

    logger.success("Vídeos finais gerados com sucesso.")
    return final_video_paths, combined_video_paths


def start(task_id: str, params: VideoParams, stop_at: str = "video"):
    """
    Função principal que orquestra todo o processo de criação de vídeo.
    """
    logger.info(f"Iniciando tarefa: {task_id}, Parar em: {stop_at}")
    sm.state.update_task(task_id, state=const.TASK_STATE_PROCESSING, progress=5)

    # Passo 1: Gerar Roteiro Estruturado
    structured_script = generate_structured_script(task_id, params)
    if not structured_script:
        return  # A função interna já definiu a tarefa como falha

    sm.state.update_task(task_id, state=const.TASK_STATE_PROCESSING, progress=15, script=structured_script.dict())
    
    # Passo 2: Agregar dados do roteiro estruturado para os próximos serviços.
    # Junta a narração de todas as cenas em um único texto para o TTS.
    full_narration_text = " ".join([scene.voiceover_text for scene in structured_script.scenes])
    # Agrega palavras-chave de todas as cenas para a busca de materiais.
    video_terms = llm.get_aggregated_keywords_from_script(structured_script)
    
    # Salva o roteiro e os parâmetros no disco.
    save_script_data(task_id, structured_script, params)

    if stop_at == "script":
        sm.state.update_task(task_id, state=const.TASK_STATE_COMPLETE, progress=100, script=structured_script.dict())
        return {"script": structured_script.dict()}

    # Passo 3: Gerar Áudio
    audio_file, audio_duration, sub_maker = generate_audio(task_id, params, full_narration_text)
    if not audio_file:
        return

    sm.state.update_task(task_id, state=const.TASK_STATE_PROCESSING, progress=30)
    if stop_at == "audio":
        sm.state.update_task(task_id, state=const.TASK_STATE_COMPLETE, progress=100, audio_file=audio_file)
        return {"audio_file": audio_file, "audio_duration": audio_duration}

    # Passo 4: Gerar Legendas
    subtitle_path = generate_subtitle(task_id, params, full_narration_text, sub_maker, audio_file)
    if stop_at == "subtitle":
        sm.state.update_task(task_id, state=const.TASK_STATE_COMPLETE, progress=100, subtitle_path=subtitle_path)
        return {"subtitle_path": subtitle_path}

    sm.state.update_task(task_id, state=const.TASK_STATE_PROCESSING, progress=40)

    # Passo 5: Obter Materiais de Vídeo
    downloaded_videos = get_video_materials(task_id, params, video_terms, audio_duration)
    if not downloaded_videos:
        return

    if stop_at == "materials":
        sm.state.update_task(task_id, state=const.TASK_STATE_COMPLETE, progress=100, materials=downloaded_videos)
        return {"materials": downloaded_videos}

    sm.state.update_task(task_id, state=const.TASK_STATE_PROCESSING, progress=50)

    # Passo 6: Gerar Vídeos Finais
    final_video_paths, combined_video_paths = generate_final_videos(
        task_id, params, downloaded_videos, audio_file, subtitle_path
    )
    if not final_video_paths:
        sm.state.update_task(task_id, state=const.TASK_STATE_FAILED)
        return

    logger.success(f"Tarefa {task_id} finalizada. Gerados {len(final_video_paths)} vídeos.")

    # Monta o resultado final com todos os artefatos gerados.
    kwargs = {
        "videos": final_video_paths,
        "combined_videos": combined_video_paths,
        "script": structured_script.dict(),
        "terms": video_terms,
        "audio_file": audio_file,
        "audio_duration": audio_duration,
        "subtitle_path": subtitle_path,
        "materials": downloaded_videos,
    }
    sm.state.update_task(task_id, state=const.TASK_STATE_COMPLETE, progress=100, **kwargs)
    return kwargs