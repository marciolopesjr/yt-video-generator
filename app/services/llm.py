# app/services/llm.py

import json
import logging
import re
import requests
from typing import List

import g4f
from loguru import logger
from openai import AzureOpenAI, OpenAI
from openai.types.chat import ChatCompletion

from app.config import config
# NEW: Importando os novos schemas
from app.models.schema import Scene, StructuredScript

_max_retries = 5


def _generate_response(prompt: str) -> str:
    # ... (esta função auxiliar permanece a mesma, pois é genérica)
    try:
        content = ""
        llm_provider = config.app.get("llm_provider", "openai")
        logger.info(f"llm provider: {llm_provider}")
        if llm_provider == "g4f":
            model_name = config.app.get("g4f_model_name", "")
            if not model_name:
                model_name = "gpt-3.5-turbo-16k-0613"
            content = g4f.ChatCompletion.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
            )
        else:
            api_version = ""  # for azure
            if llm_provider == "moonshot":
                api_key = config.app.get("moonshot_api_key")
                model_name = config.app.get("moonshot_model_name")
                base_url = "https://api.moonshot.cn/v1"
            elif llm_provider == "ollama":
                api_key = "ollama"
                model_name = config.app.get("ollama_model_name")
                base_url = config.app.get("ollama_base_url", "http://localhost:11434/v1")
            # ... (outros provedores LLM permanecem os mesmos) ...
            else:
                client = OpenAI(api_key=api_key, base_url=base_url)

            response = client.chat.completions.create(
                model=model_name,
                # NEW: Solicita explicitamente o formato JSON para modelos que o suportam
                response_format={"type": "json_object"},
                messages=[{"role": "user", "content": prompt}]
            )
            if response:
                if isinstance(response, ChatCompletion):
                    content = response.choices[0].message.content
                else:
                    raise Exception(f'[{llm_provider}] returned an invalid response: "{response}"')
            else:
                raise Exception(f"[{llm_provider}] returned an empty response")

        return content
    except Exception as e:
        logger.error(f"Error generating response: {e}")
        return f'{{"error": "Failed to generate response from LLM: {str(e)}"}}'


# --------------------------------------------------------------------------------
# NEW: Nova função principal para gerar o roteiro estruturado
# --------------------------------------------------------------------------------
def generate_structured_script(video_subject: str, language: str = "Português", paragraph_number: int = 5) -> StructuredScript:
    prompt = f"""
# ROLE: Roteirista de Vídeos Curtos e Diretor de Arte

## OBJETIVO:
Criar um roteiro detalhado e estruturado para um vídeo curto sobre o tema fornecido. O roteiro deve ser dividido em {paragraph_number} cenas distintas. Para cada cena, você deve fornecer o texto da narração e uma descrição visual rica e detalhada que servirá como prompt para um gerador de imagens de IA.

## RESTRIÇÕES:
1.  **Formato de Saída OBRIGATÓRIO:** A sua resposta deve ser um único objeto JSON válido que corresponda ao seguinte schema: `{{ "scenes": [ {{ "scene_number": int, "voiceover_text": str, "visual_description": str, "keywords": [str] }} ] }}`.
2.  **NÃO inclua texto ou explicações fora do objeto JSON.** Sua resposta deve começar com `{{` e terminar com `}}`.
3.  **Estrutura de cada Cena:** Cada objeto de cena no array deve conter EXATAMENTE as seguintes chaves:
    - `scene_number`: (Inteiro) O número da cena, começando em 1.
    - `voiceover_text`: (String) O texto da narração para esta cena. Deve ser conciso e impactante.
    - `visual_description`: (String) Uma descrição vívida e detalhada da imagem a ser gerada. Pense em iluminação, composição, cores e emoção. Seja específico. Ex: "Close-up de um relógio antigo de bolso em uma mesa de madeira escura, com a luz suave da janela iluminando a poeira no ar."
    - `keywords`: (Array de Strings) 3 a 4 palavras-chave em INGLÊS que resumem a cena para buscar vídeos de estoque.
4.  **Idioma:** O `voiceover_text` deve ser gerado no idioma: {language}. A `visual_description` e as `keywords` devem ser em INGLÊS para compatibilidade com geradores de imagem e APIs de busca.

## TAREFA:
Agora, crie o roteiro estruturado para o seguinte tema.

- **Tema do Vídeo:** {video_subject}
- **Idioma da Narração:** {language}
- **Número de Cenas:** {paragraph_number}
""".strip()

    logger.info(f"Gerando roteiro estruturado para o tema: {video_subject}")
    
    response_text = ""
    for i in range(_max_retries):
        try:
            response_text = _generate_response(prompt=prompt)
            # Tenta encontrar o bloco JSON na resposta, caso a LLM adicione texto extra
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if not json_match:
                logger.warning(f"Tentativa {i+1}: JSON não encontrado na resposta da LLM. Resposta: {response_text}")
                continue

            json_str = json_match.group(0)
            data = json.loads(json_str)

            if "error" in data:
                raise ValueError(data["error"])

            # Valida com o Pydantic
            structured_script = StructuredScript.parse_obj(data)
            logger.success(f"Roteiro estruturado gerado e validado com sucesso com {len(structured_script.scenes)} cenas.")
            return structured_script

        except json.JSONDecodeError as e:
            logger.warning(f"Tentativa {i+1}: Falha ao decodificar JSON. Erro: {e}. Resposta recebida: {response_text}")
        except Exception as e:
            logger.error(f"Tentativa {i+1}: Erro ao gerar roteiro estruturado. Erro: {e}")
        
        if i < _max_retries -1:
            logger.info("Tentando novamente...")

    logger.error("Falha ao gerar o roteiro estruturado após múltiplas tentativas.")
    return StructuredScript(scenes=[]) # Retorna um objeto vazio em caso de falha total


# MODIFIED: A antiga função generate_script agora está obsoleta.
# A lógica agora está em generate_structured_script.
# Se precisar de compatibilidade, pode-se criar uma função que chame a nova e formate a saída.

# MODIFIED: A antiga função generate_terms agora é redundante.
# As palavras-chave são geradas por cena no roteiro estruturado.
# Esta função pode ser mantida para extrair/agregar keywords se necessário.
def get_aggregated_keywords_from_script(script: StructuredScript, amount: int = 10) -> List[str]:
    all_keywords = []
    if not script or not script.scenes:
        return []
        
    for scene in script.scenes:
        all_keywords.extend(scene.keywords)
    
    # Remove duplicatas mantendo a ordem e limita a quantidade
    unique_keywords = list(dict.fromkeys(all_keywords))
    return unique_keywords[:amount]