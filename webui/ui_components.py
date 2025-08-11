import streamlit as st
from app.config import config
from webui.i18n import tr
from app.models.schema import VideoConcatMode, VideoTransitionMode, VideoAspect
from app.services import llm, voice
from app.utils import utils
from uuid import uuid4
import os

def create_settings_panel(locales):
    with st.expander(tr("Basic Settings", locales), expanded=False):
        config_panels = st.columns(3)
        left_config_panel = config_panels[0]
        middle_config_panel = config_panels[1]
        right_config_panel = config_panels[2]

        # 左侧面板 - 日志设置
        with left_config_panel:
            # 是否隐藏配置面板
            hide_config = st.checkbox(
                tr("Hide Basic Settings", locales), value=config.app.get("hide_config", False)
            )
            config.app["hide_config"] = hide_config

            # 是否禁用日志显示
            hide_log = st.checkbox(
                tr("Hide Log", locales), value=config.ui.get("hide_log", False)
            )
            config.ui["hide_log"] = hide_log

        # 中间面板 - LLM 设置

        with middle_config_panel:
            st.write(tr("LLM Settings", locales))
            llm_providers = [
                "OpenAI",
                "Moonshot",
                "Azure",
                "Qwen",
                "DeepSeek",
                "Gemini",
                "Ollama",
                "G4f",
                "OneAPI",
                "Cloudflare",
                "ERNIE",
                "Pollinations",
            ]
            saved_llm_provider = config.app.get("llm_provider", "OpenAI").lower()
            saved_llm_provider_index = 0
            for i, provider in enumerate(llm_providers):
                if provider.lower() == saved_llm_provider:
                    saved_llm_provider_index = i
                    break

            llm_provider = st.selectbox(
                tr("LLM Provider", locales),
                options=llm_providers,
                index=saved_llm_provider_index,
            )
            llm_helper = st.container()
            llm_provider = llm_provider.lower()
            config.app["llm_provider"] = llm_provider

            llm_api_key = config.app.get(f"{llm_provider}_api_key", "")
            llm_secret_key = config.app.get(
                f"{llm_provider}_secret_key", ""
            )  # only for baidu ernie
            llm_base_url = config.app.get(f"{llm_provider}_base_url", "")
            llm_model_name = config.app.get(f"{llm_provider}_model_name", "")
            llm_account_id = config.app.get(f"{llm_provider}_account_id", "")

            tips = ""
            if llm_provider == "ollama":
                if not llm_model_name:
                    llm_model_name = "qwen:7b"
                if not llm_base_url:
                    llm_base_url = "http://localhost:11434/v1"

                with llm_helper:
                    tips = """
                            ##### Ollama配置说明
                            - **API Key**: 随便填写，比如 123
                            - **Base Url**: 一般为 http://localhost:11434/v1
                                - 如果 `MoneyPrinterTurbo` 和 `Ollama` **不在同一台机器上**，需要填写 `Ollama` 机器的IP地址
                                - 如果 `MoneyPrinterTurbo` 是 `Docker` 部署，建议填写 `http://host.docker.internal:11434/v1`
                            - **Model Name**: 使用 `ollama list` 查看，比如 `qwen:7b`
                            """

            if llm_provider == "openai":
                if not llm_model_name:
                    llm_model_name = "gpt-3.5-turbo"
                with llm_helper:
                    tips = """
                            ##### OpenAI 配置说明
                            > 需要VPN开启全局流量模式
                            - **API Key**: [点击到官网申请](https://platform.openai.com/api-keys)
                            - **Base Url**: 可以留空
                            - **Model Name**: 填写**有权限**的模型，[点击查看模型列表](https://platform.openai.com/settings/organization/limits)
                            """

            if llm_provider == "moonshot":
                if not llm_model_name:
                    llm_model_name = "moonshot-v1-8k"
                with llm_helper:
                    tips = """
                            ##### Moonshot 配置说明
                            - **API Key**: [点击到官网申请](https://platform.moonshot.cn/console/api-keys)
                            - **Base Url**: 固定为 https://api.moonshot.cn/v1
                            - **Model Name**: 比如 moonshot-v1-8k，[点击查看模型列表](https://platform.moonshot.cn/docs/intro#%E6%A8%A1%E5%9E%8B%E5%88%97%E8%A1%A8)
                            """
            if llm_provider == "oneapi":
                if not llm_model_name:
                    llm_model_name = (
                        "claude-3-5-sonnet-20240620"  # 默认模型，可以根据需要调整
                    )
                with llm_helper:
                    tips = """
                        ##### OneAPI 配置说明
                        - **API Key**: 填写您的 OneAPI 密钥
                        - **Base Url**: 填写 OneAPI 的基础 URL
                        - **Model Name**: 填写您要使用的模型名称，例如 claude-3-5-sonnet-20240620
                        """

            if llm_provider == "qwen":
                if not llm_model_name:
                    llm_model_name = "qwen-max"
                with llm_helper:
                    tips = """
                            ##### 通义千问Qwen 配置说明
                            - **API Key**: [点击到官网申请](https://dashscope.console.aliyun.com/apiKey)
                            - **Base Url**: 留空
                            - **Model Name**: 比如 qwen-max，[点击查看模型列表](https://help.aliyun.com/zh/dashscope/developer-reference/model-introduction#3ef6d0bcf91wy)
                            """

            if llm_provider == "g4f":
                if not llm_model_name:
                    llm_model_name = "gpt-3.5-turbo"
                with llm_helper:
                    tips = """
                            ##### gpt4free 配置说明
                            > [GitHub开源项目](https://github.com/xtekky/gpt4free)，可以免费使用GPT模型，但是**稳定性较差**
                            - **API Key**: 随便填写，比如 123
                            - **Base Url**: 留空
                            - **Model Name**: 比如 gpt-3.5-turbo，[点击查看模型列表](https://github.com/xtekky/gpt4free/blob/main/g4f/models.py#L308)
                            """
            if llm_provider == "azure":
                with llm_helper:
                    tips = """
                            ##### Azure 配置说明
                            > [点击查看如何部署模型](https://learn.microsoft.com/zh-cn/azure/ai-services/openai/how-to/create-resource)
                            - **API Key**: [点击到Azure后台创建](https://portal.azure.com/#view/Microsoft_Azure_ProjectOxford/CognitiveServicesHub/~/OpenAI)
                            - **Base Url**: 留空
                            - **Model Name**: 填写你实际的部署名
                            """

            if llm_provider == "gemini":
                if not llm_model_name:
                    llm_model_name = "gemini-1.0-pro"

                with llm_helper:
                    tips = """
                            ##### Gemini 配置说明
                            > 需要VPN开启全局流量模式
                            - **API Key**: [点击到官网申请](https://ai.google.dev/)
                            - **Base Url**: 留空
                            - **Model Name**: 比如 gemini-1.0-pro
                            """

            if llm_provider == "deepseek":
                if not llm_model_name:
                    llm_model_name = "deepseek-chat"
                if not llm_base_url:
                    llm_base_url = "https://api.deepseek.com"
                with llm_helper:
                    tips = """
                            ##### DeepSeek 配置说明
                            - **API Key**: [点击到官网申请](https://platform.deepseek.com/api_keys)
                            - **Base Url**: 固定为 https://api.deepseek.com
                            - **Model Name**: 固定为 deepseek-chat
                            """

            if llm_provider == "ernie":
                with llm_helper:
                    tips = """
                            ##### 百度文心一言 配置说明
                            - **API Key**: [点击到官网申请](https://console.bce.baidu.com/qianfan/ais/console/applicationConsole/application)
                            - **Secret Key**: [点击到官网申请](https://console.bce.baidu.com/qianfan/ais/console/applicationConsole/application)
                            - **Base Url**: 填写 **请求地址** [点击查看文档](https://cloud.baidu.com/doc/WENXINWORKSHOP/s/jlil56u11#%E8%AF%B7%E6%B1%82%E8%AF%B4%E6%98%8E)
                            """

            if llm_provider == "pollinations":
                if not llm_model_name:
                    llm_model_name = "default"
                with llm_helper:
                    tips = """
                            ##### Pollinations AI Configuration
                            - **API Key**: Optional - Leave empty for public access
                            - **Base Url**: Default is https://text.pollinations.ai/openai
                            - **Model Name**: Use 'openai-fast' or specify a model name
                            """

            if tips and config.ui["language"] == "zh":
                st.warning(
                    "中国用户建议使用 **DeepSeek** 或 **Moonshot** 作为大模型提供商\n- 国内可直接访问，不需要VPN \n- 注册就送额度，基本够用"
                )
                st.info(tips)

            st_llm_api_key = st.text_input(
                tr("API Key", locales), value=llm_api_key, type="password"
            )
            st_llm_base_url = st.text_input(tr("Base Url", locales), value=llm_base_url)
            st_llm_model_name = ""
            if llm_provider != "ernie":
                st_llm_model_name = st.text_input(
                    tr("Model Name", locales),
                    value=llm_model_name,
                    key=f"{llm_provider}_model_name_input",
                )
                if st_llm_model_name:
                    config.app[f"{llm_provider}_model_name"] = st_llm_model_name
            else:
                st_llm_model_name = None

            if st_llm_api_key:
                config.app[f"{llm_provider}_api_key"] = st_llm_api_key
            if st_llm_base_url:
                config.app[f"{llm_provider}_base_url"] = st_llm_base_url
            if st_llm_model_name:
                config.app[f"{llm_provider}_model_name"] = st_llm_model_name
            if llm_provider == "ernie":
                st_llm_secret_key = st.text_input(
                    tr("Secret Key", locales), value=llm_secret_key, type="password"
                )
                config.app[f"{llm_provider}_secret_key"] = st_llm_secret_key

            if llm_provider == "cloudflare":
                st_llm_account_id = st.text_input(
                    tr("Account ID", locales), value=llm_account_id
                )
                if st_llm_account_id:
                    config.app[f"{llm_provider}_account_id"] = st_llm_account_id

        # 右侧面板 - API 密钥设置
        with right_config_panel:

            def get_keys_from_config(cfg_key):
                api_keys = config.app.get(cfg_key, [])
                if isinstance(api_keys, str):
                    api_keys = [api_keys]
                api_key = ", ".join(api_keys)
                return api_key

            def save_keys_to_config(cfg_key, value):
                value = value.replace(" ", "")
                if value:
                    config.app[cfg_key] = value.split(",")

            st.write(tr("Video Source Settings", locales))

            pexels_api_key = get_keys_from_config("pexels_api_keys")
            pexels_api_key = st.text_input(
                tr("Pexels API Key", locales), value=pexels_api_key, type="password"
            )
            save_keys_to_config("pexels_api_keys", pexels_api_key)

            pixabay_api_key = get_keys_from_config("pixabay_api_keys")
            pixabay_api_key = st.text_input(
                tr("Pixabay API Key", locales), value=pixabay_api_key, type="password"
            )
            save_keys_to_config("pixabay_api_keys", pixabay_api_key)


def create_script_panel(locales, support_locales, video_params):
    with st.container(border=True):
        st.write(tr("Video Script Settings", locales))
        video_params.video_subject = st.text_input(
            tr("Video Subject", locales),
            value=st.session_state["video_subject"],
            key="video_subject_input",
        ).strip()

        video_languages = [
            (tr("Auto Detect", locales), ""),
        ]
        for code in support_locales:
            video_languages.append((code, code))

        selected_index = st.selectbox(
            tr("Script Language", locales),
            index=0,
            options=range(
                len(video_languages)
            ),  # Use the index as the internal option value
            format_func=lambda x: video_languages[x][
                0
            ],  # The label is displayed to the user
        )
        video_params.video_language = video_languages[selected_index][1]

        if st.button(
            tr("Generate Video Script and Keywords", locales), key="auto_generate_script"
        ):
            with st.spinner(tr("Generating Video Script and Keywords", locales)):
                script = llm.generate_script(
                    video_subject=video_params.video_subject, language=video_params.video_language
                )
                terms = llm.generate_terms(video_params.video_subject, script)
                if "Error: " in script:
                    st.error(tr(script, locales))
                elif "Error: " in terms:
                    st.error(tr(terms, locales))
                else:
                    st.session_state["video_script"] = script
                    st.session_state["video_terms"] = ", ".join(terms)

        video_params.video_script = st.text_area(
            tr("Video Script", locales), value=st.session_state["video_script"], height=280
        )

        if st.button(tr("Generate Video Keywords", locales), key="auto_generate_terms"):
            if not video_params.video_script:
                st.error(tr("Please Enter the Video Subject", locales))
                st.stop()

            with st.spinner(tr("Generating Video Keywords", locales)):
                terms = llm.generate_terms(video_params.video_subject, video_params.video_script)
                if "Error: " in terms:
                    st.error(tr(terms, locales))
                else:
                    st.session_state["video_terms"] = ", ".join(terms)

        video_params.video_terms = st.text_area(
            tr("Video Keywords", locales), value=st.session_state["video_terms"]
        )
    return video_params


def create_video_panel(locales, video_params):
    uploaded_files = []
    with st.container(border=True):
        st.write(tr("Video Settings", locales))
        video_concat_modes = [
            (tr("Sequential", locales), "sequential"),
            (tr("Random", locales), "random"),
        ]
        video_sources = [
            (tr("Pexels", locales), "pexels"),
            (tr("Pixabay", locales), "pixabay"),
            (tr("Local file", locales), "local"),
            (tr("TikTok", locales), "douyin"),
            (tr("Bilibili", locales), "bilibili"),
            (tr("Xiaohongshu", locales), "xiaohongshu"),
        ]

        saved_video_source_name = config.app.get("video_source", "pexels")
        saved_video_source_index = [v[1] for v in video_sources].index(
            saved_video_source_name
        )

        selected_index = st.selectbox(
            tr("Video Source", locales),
            options=range(len(video_sources)),
            format_func=lambda x: video_sources[x][0],
            index=saved_video_source_index,
        )
        video_params.video_source = video_sources[selected_index][1]
        config.app["video_source"] = video_params.video_source

        if video_params.video_source == "local":
            uploaded_files = st.file_uploader(
                "Upload Local Files",
                type=["mp4", "mov", "avi", "flv", "mkv", "jpg", "jpeg", "png"],
                accept_multiple_files=True,
            )

        selected_index = st.selectbox(
            tr("Video Concat Mode", locales),
            index=1,
            options=range(
                len(video_concat_modes)
            ),  # Use the index as the internal option value
            format_func=lambda x: video_concat_modes[x][
                0
            ],  # The label is displayed to the user
        )
        video_params.video_concat_mode = VideoConcatMode(
            video_concat_modes[selected_index][1]
        )

        # 视频转场模式
        video_transition_modes = [
            (tr("None", locales), VideoTransitionMode.none.value),
            (tr("Shuffle", locales), VideoTransitionMode.shuffle.value),
            (tr("FadeIn", locales), VideoTransitionMode.fade_in.value),
            (tr("FadeOut", locales), VideoTransitionMode.fade_out.value),
            (tr("SlideIn", locales), VideoTransitionMode.slide_in.value),
            (tr("SlideOut", locales), VideoTransitionMode.slide_out.value),
        ]
        selected_index = st.selectbox(
            tr("Video Transition Mode", locales),
            options=range(len(video_transition_modes)),
            format_func=lambda x: video_transition_modes[x][0],
            index=0,
        )
        video_params.video_transition_mode = VideoTransitionMode(
            video_transition_modes[selected_index][1]
        )

        video_aspect_ratios = [
            (tr("Portrait", locales), VideoAspect.portrait.value),
            (tr("Landscape", locales), VideoAspect.landscape.value),
        ]
        selected_index = st.selectbox(
            tr("Video Ratio", locales),
            options=range(
                len(video_aspect_ratios)
            ),  # Use the index as the internal option value
            format_func=lambda x: video_aspect_ratios[x][
                0
            ],  # The label is displayed to the user
        )
        video_params.video_aspect = VideoAspect(video_aspect_ratios[selected_index][1])

        video_params.video_clip_duration = st.selectbox(
            tr("Clip Duration", locales), options=[2, 3, 4, 5, 6, 7, 8, 9, 10], index=1
        )
        video_params.video_count = st.selectbox(
            tr("Number of Videos Generated Simultaneously", locales),
            options=[1, 2, 3, 4, 5],
            index=0,
        )
    return video_params, uploaded_files


def create_audio_panel(locales, video_params):
    with st.container(border=True):
        st.write(tr("Audio Settings", locales))

        # 添加TTS服务器选择下拉框
        tts_servers = [
            ("azure-tts-v1", "Azure TTS V1"),
            ("azure-tts-v2", "Azure TTS V2"),
            ("siliconflow", "SiliconFlow TTS"),
        ]

        # 获取保存的TTS服务器，默认为v1
        saved_tts_server = config.ui.get("tts_server", "azure-tts-v1")
        saved_tts_server_index = 0
        for i, (server_value, _) in enumerate(tts_servers):
            if server_value == saved_tts_server:
                saved_tts_server_index = i
                break

        selected_tts_server_index = st.selectbox(
            tr("TTS Servers", locales),
            options=range(len(tts_servers)),
            format_func=lambda x: tts_servers[x][1],
            index=saved_tts_server_index,
        )

        selected_tts_server = tts_servers[selected_tts_server_index][0]
        config.ui["tts_server"] = selected_tts_server

        # 根据选择的TTS服务器获取声音列表
        filtered_voices = []

        if selected_tts_server == "siliconflow":
            # 获取硅基流动的声音列表
            filtered_voices = voice.get_siliconflow_voices()
        else:
            # 获取Azure的声音列表
            all_voices = voice.get_all_azure_voices(filter_locals=None)

            # 根据选择的TTS服务器筛选声音
            for v in all_voices:
                if selected_tts_server == "azure-tts-v2":
                    # V2版本的声音名称中包含"v2"
                    if "V2" in v:
                        filtered_voices.append(v)
                else:
                    # V1版本的声音名称中不包含"v2"
                    if "V2" not in v:
                        filtered_voices.append(v)

        friendly_names = {
            v: v.replace("Female", tr("Female", locales))
            .replace("Male", tr("Male", locales))
            .replace("Neural", "")
            for v in filtered_voices
        }

        saved_voice_name = config.ui.get("voice_name", "")
        saved_voice_name_index = 0

        # 检查保存的声音是否在当前筛选的声音列表中
        if saved_voice_name in friendly_names:
            saved_voice_name_index = list(friendly_names.keys()).index(saved_voice_name)
        else:
            # 如果不在，则根据当前UI语言选择一个默认声音
            for i, v in enumerate(filtered_voices):
                if v.lower().startswith(st.session_state["ui_language"].lower()):
                    saved_voice_name_index = i
                    break

        # 如果没有找到匹配的声音，使用第一个声音
        if saved_voice_name_index >= len(friendly_names) and friendly_names:
            saved_voice_name_index = 0

        # 确保有声音可选
        if friendly_names:
            selected_friendly_name = st.selectbox(
                tr("Speech Synthesis", locales),
                options=list(friendly_names.values()),
                index=min(saved_voice_name_index, len(friendly_names) - 1)
                if friendly_names
                else 0,
            )

            voice_name = list(friendly_names.keys())[
                list(friendly_names.values()).index(selected_friendly_name)
            ]
            video_params.voice_name = voice_name
            config.ui["voice_name"] = voice_name
        else:
            # 如果没有声音可选，显示提示信息
            st.warning(
                tr(
                    "No voices available for the selected TTS server. Please select another server.", locales
                )
            )
            video_params.voice_name = ""
            config.ui["voice_name"] = ""

        # 只有在有声音可选时才显示试听按钮
        if friendly_names and st.button(tr("Play Voice", locales)):
            play_content = video_params.video_subject
            if not play_content:
                play_content = video_params.video_script
            if not play_content:
                play_content = tr("Voice Example", locales)
            with st.spinner(tr("Synthesizing Voice", locales)):
                temp_dir = utils.storage_dir("temp", create=True)
                audio_file = os.path.join(temp_dir, f"tmp-voice-{str(uuid4())}.mp3")
                sub_maker = voice.tts(
                    text=play_content,
                    voice_name=voice_name,
                    voice_rate=video_params.voice_rate,
                    voice_file=audio_file,
                    voice_volume=video_params.voice_volume,
                )
                # if the voice file generation failed, try again with a default content.
                if not sub_maker:
                    play_content = "This is a example voice. if you hear this, the voice synthesis failed with the original content."
                    sub_maker = voice.tts(
                        text=play_content,
                        voice_name=voice_name,
                        voice_rate=video_params.voice_rate,
                        voice_file=audio_file,
                        voice_volume=video_params.voice_volume,
                    )

                if sub_maker and os.path.exists(audio_file):
                    st.audio(audio_file, format="audio/mp3")
                    if os.path.exists(audio_file):
                        os.remove(audio_file)

        # 当选择V2版本或者声音是V2声音时，显示服务区域和API key输入框
        if selected_tts_server == "azure-tts-v2" or (
            video_params.voice_name and voice.is_azure_v2_voice(video_params.voice_name)
        ):
            saved_azure_speech_region = config.azure.get("speech_region", "")
            saved_azure_speech_key = config.azure.get("speech_key", "")
            azure_speech_region = st.text_input(
                tr("Speech Region", locales),
                value=saved_azure_speech_region,
                key="azure_speech_region_input",
            )
            azure_speech_key = st.text_input(
                tr("Speech Key", locales),
                value=saved_azure_speech_key,
                type="password",
                key="azure_speech_key_input",
            )
            config.azure["speech_region"] = azure_speech_region
            config.azure["speech_key"] = azure_speech_key

        # 当选择硅基流动时，显示API key输入框和说明信息
        if selected_tts_server == "siliconflow" or (
            video_params.voice_name and voice.is_siliconflow_voice(video_params.voice_name)
        ):
            saved_siliconflow_api_key = config.siliconflow.get("api_key", "")

            siliconflow_api_key = st.text_input(
                tr("SiliconFlow API Key", locales),
                value=saved_siliconflow_api_key,
                type="password",
                key="siliconflow_api_key_input",
            )

            # 显示硅基流动的说明信息
            st.info(
                tr("SiliconFlow TTS Settings", locales)
                + ":\n"
                + "- "
                + tr("Speed: Range [0.25, 4.0], default is 1.0", locales)
                + "\n"
                + "- "
                + tr("Volume: Uses Speech Volume setting, default 1.0 maps to gain 0", locales)
            )

            config.siliconflow["api_key"] = siliconflow_api_key

        video_params.voice_volume = st.selectbox(
            tr("Speech Volume", locales),
            options=[0.6, 0.8, 1.0, 1.2, 1.5, 2.0, 3.0, 4.0, 5.0],
            index=2,
        )

        video_params.voice_rate = st.selectbox(
            tr("Speech Rate", locales),
            options=[0.8, 0.9, 1.0, 1.1, 1.2, 1.3, 1.5, 1.8, 2.0],
            index=2,
        )

        bgm_options = [
            (tr("No Background Music", locales), ""),
            (tr("Random Background Music", locales), "random"),
            (tr("Custom Background Music", locales), "custom"),
        ]
        selected_index = st.selectbox(
            tr("Background Music", locales),
            index=1,
            options=range(
                len(bgm_options)
            ),  # Use the index as the internal option value
            format_func=lambda x: bgm_options[x][
                0
            ],  # The label is displayed to the user
        )
        # Get the selected background music type
        video_params.bgm_type = bgm_options[selected_index][1]

        # Show or hide components based on the selection
        if video_params.bgm_type == "custom":
            custom_bgm_file = st.text_input(
                tr("Custom Background Music File", locales), key="custom_bgm_file_input"
            )
            if custom_bgm_file and os.path.exists(custom_bgm_file):
                video_params.bgm_file = custom_bgm_file
                # st.write(f":red[已选择自定义背景音乐]：**{custom_bgm_file}**")
        video_params.bgm_volume = st.selectbox(
            tr("Background Music Volume", locales),
            options=[0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
            index=2,
        )
    return video_params


def create_subtitle_panel(locales, video_params, font_names):
    with st.container(border=True):
        st.write(tr("Subtitle Settings", locales))
        video_params.subtitle_enabled = st.checkbox(tr("Enable Subtitles", locales), value=True)
        saved_font_name = config.ui.get("font_name", "MicrosoftYaHeiBold.ttc")
        saved_font_name_index = 0
        if saved_font_name in font_names:
            saved_font_name_index = font_names.index(saved_font_name)
        video_params.font_name = st.selectbox(
            tr("Font", locales), font_names, index=saved_font_name_index
        )
        config.ui["font_name"] = video_params.font_name

        subtitle_positions = [
            (tr("Top", locales), "top"),
            (tr("Center", locales), "center"),
            (tr("Bottom", locales), "bottom"),
            (tr("Custom", locales), "custom"),
        ]
        selected_index = st.selectbox(
            tr("Position", locales),
            index=2,
            options=range(len(subtitle_positions)),
            format_func=lambda x: subtitle_positions[x][0],
        )
        video_params.subtitle_position = subtitle_positions[selected_index][1]

        if video_params.subtitle_position == "custom":
            custom_position = st.text_input(
                tr("Custom Position (% from top)", locales),
                value="70.0",
                key="custom_position_input",
            )
            try:
                video_params.custom_position = float(custom_position)
                if video_params.custom_position < 0 or video_params.custom_position > 100:
                    st.error(tr("Please enter a value between 0 and 100", locales))
            except ValueError:
                st.error(tr("Please enter a valid number", locales))

        font_cols = st.columns([0.3, 0.7])
        with font_cols[0]:
            saved_text_fore_color = config.ui.get("text_fore_color", "#FFFFFF")
            video_params.text_fore_color = st.color_picker(
                tr("Font Color", locales), saved_text_fore_color
            )
            config.ui["text_fore_color"] = video_params.text_fore_color

        with font_cols[1]:
            saved_font_size = config.ui.get("font_size", 60)
            video_params.font_size = st.slider(tr("Font Size", locales), 30, 100, saved_font_size)
            config.ui["font_size"] = video_params.font_size

        stroke_cols = st.columns([0.3, 0.7])
        with stroke_cols[0]:
            video_params.stroke_color = st.color_picker(tr("Stroke Color", locales), "#000000")
        with stroke_cols[1]:
            video_params.stroke_width = st.slider(tr("Stroke Width", locales), 0.0, 10.0, 1.5)
    return video_params
