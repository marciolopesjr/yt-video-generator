import os
import platform
import sys
from uuid import uuid4

import streamlit as st
from loguru import logger

# Add the root directory of the project to the system path to allow importing modules from the project
root_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if root_dir not in sys.path:
    sys.path.append(root_dir)
    print("******** sys.path ********")
    print(sys.path)
    print("")

from app.config import config
from app.models.schema import (
    MaterialInfo,
    VideoAspect,
    VideoConcatMode,
    VideoParams,
    VideoTransitionMode,
)
from app.services import llm, voice
from app.services import task as tm
from app.utils import utils
from webui.i18n import load_locales, tr
from webui.utils import (
    get_all_fonts,
    get_all_songs,
    open_task_folder,
    scroll_to_bottom,
    init_log,
)
from webui.ui_components import (
    create_settings_panel,
    create_script_panel,
    create_video_panel,
    create_audio_panel,
    create_subtitle_panel,
)

st.set_page_config(
    page_title="MoneyPrinterTurbo",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="auto",
    menu_items={
        "Report a bug": "https://github.com/harry0703/MoneyPrinterTurbo/issues",
        "About": "# MoneyPrinterTurbo\nSimply provide a topic or keyword for a video, and it will "
        "automatically generate the video copy, video materials, video subtitles, "
        "and video background music before synthesizing a high-definition short "
        "video.\n\nhttps://github.com/harry0703/MoneyPrinterTurbo",
    },
)


streamlit_style = """
<style>
h1 {
    padding-top: 0 !important;
}
</style>
"""
st.markdown(streamlit_style, unsafe_allow_html=True)

# 定义资源目录
font_dir = os.path.join(root_dir, "resource", "fonts")
song_dir = os.path.join(root_dir, "resource", "songs")
i18n_dir = os.path.join(root_dir, "webui", "i18n")
config_file = os.path.join(root_dir, "webui", ".streamlit", "webui.toml")
system_locale = utils.get_system_locale()


if "video_subject" not in st.session_state:
    st.session_state["video_subject"] = ""
if "video_script" not in st.session_state:
    st.session_state["video_script"] = ""
if "video_terms" not in st.session_state:
    st.session_state["video_terms"] = ""
if "ui_language" not in st.session_state:
    st.session_state["ui_language"] = config.ui.get("language", system_locale)

# 加载语言文件
locales = load_locales(i18n_dir)

# 创建一个顶部栏，包含标题和语言选择
title_col, lang_col = st.columns([3, 1])

with title_col:
    st.title(f"MoneyPrinterTurbo v{config.project_version}")

with lang_col:
    display_languages = []
    selected_index = 0
    for i, code in enumerate(locales.keys()):
        display_languages.append(f"{code} - {locales[code].get('Language')}")
        if code == st.session_state.get("ui_language", ""):
            selected_index = i

    selected_language = st.selectbox(
        "Language / 语言",
        options=display_languages,
        index=selected_index,
        key="top_language_selector",
        label_visibility="collapsed",
    )
    if selected_language:
        code = selected_language.split(" - ")[0].strip()
        st.session_state["ui_language"] = code
        config.ui["language"] = code

support_locales = [
    "zh-CN",
    "zh-HK",
    "zh-TW",
    "de-DE",
    "en-US",
    "fr-FR",
    "vi-VN",
    "th-TH",
]


init_log()

locales = load_locales(i18n_dir)


# 创建基础设置折叠框
if not config.app.get("hide_config", False):
    create_settings_panel(locales)

llm_provider = config.app.get("llm_provider", "").lower()
panel = st.columns(3)
left_panel = panel[0]
middle_panel = panel[1]
right_panel = panel[2]

params = VideoParams(video_subject="")
uploaded_files = []

with left_panel:
    params = create_script_panel(locales, support_locales, params)

with middle_panel:
    params, uploaded_files = create_video_panel(locales, params)
    params = create_audio_panel(locales, params)

with right_panel:
    font_names = get_all_fonts()
    params = create_subtitle_panel(locales, params, font_names)

start_button = st.button(tr("Generate Video", locales), use_container_width=True, type="primary")
if start_button:
    config.save_config()
    task_id = str(uuid4())
    if not params.video_subject and not params.video_script:
        st.error(tr("Video Script and Subject Cannot Both Be Empty", locales))
        scroll_to_bottom()
        st.stop()

    if params.video_source not in ["pexels", "pixabay", "local"]:
        st.error(tr("Please Select a Valid Video Source", locales))
        scroll_to_bottom()
        st.stop()

    if params.video_source == "pexels" and not config.app.get("pexels_api_keys", ""):
        st.error(tr("Please Enter the Pexels API Key", locales))
        scroll_to_bottom()
        st.stop()

    if params.video_source == "pixabay" and not config.app.get("pixabay_api_keys", ""):
        st.error(tr("Please Enter the Pixabay API Key", locales))
        scroll_to_bottom()
        st.stop()

    if uploaded_files:
        local_videos_dir = utils.storage_dir("local_videos", create=True)
        for file in uploaded_files:
            file_path = os.path.join(local_videos_dir, f"{file.file_id}_{file.name}")
            with open(file_path, "wb") as f:
                f.write(file.getbuffer())
                m = MaterialInfo()
                m.provider = "local"
                m.url = file_path
                if not params.video_materials:
                    params.video_materials = []
                params.video_materials.append(m)

    log_container = st.empty()
    log_records = []

    def log_received(msg):
        if config.ui["hide_log"]:
            return
        with log_container:
            log_records.append(msg)
            st.code("\n".join(log_records))

    logger.add(log_received)

    st.toast(tr("Generating Video", locales))
    logger.info(tr("Start Generating Video", locales))
    logger.info(utils.to_json(params))
    scroll_to_bottom()

    result = tm.start(task_id=task_id, params=params)
    if not result or "videos" not in result:
        st.error(tr("Video Generation Failed", locales))
        logger.error(tr("Video Generation Failed", locales))
        scroll_to_bottom()
        st.stop()

    video_files = result.get("videos", [])
    st.success(tr("Video Generation Completed", locales))
    try:
        if video_files:
            player_cols = st.columns(len(video_files) * 2 + 1)
            for i, url in enumerate(video_files):
                player_cols[i * 2 + 1].video(url)
    except Exception:
        pass

    open_task_folder(task_id)
    logger.info(tr("Video Generation Completed", locales))
    scroll_to_bottom()

config.save_config()
