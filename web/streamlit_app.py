import json
import logging
import os
import shutil
import sys
import uuid
from pathlib import Path
from typing import List, Optional, Tuple

import streamlit as st

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.config import OUTPUTS_DIR, UPLOADS_DIR
from app.config import get_settings


APP_TITLE = "AutoEdit"
APP_SUBTITLE = "图文口播智能切片系统"

PLATFORMS = {
    "抖音": "douyin",
    "小红书": "xiaohongshu",
    "视频号": "shipinhao",
    "Bilibili": "bilibili",
    "快手": "kuaishou",
}

STYLES = {
    "商务科技": "business_tech",
    "知识干货": "knowledge",
    "情绪共鸣": "emotional",
    "高能节奏": "energetic",
}

STEP_LABELS = {
    "preprocess": "预处理",
    "asr": "语音识别",
    "analyze": "内容分析",
    "select_clip": "切片选择",
    "trim_script": "文稿裁剪",
    "generate_visuals": "视觉规划",
    "generate_subtitles": "字幕生成",
    "plan_audio": "音频处理",
    "render": "渲染合成",
    "generate_titles": "标题生成",
}

STEP_ORDER = list(STEP_LABELS.keys())

TITLE_TYPE_LABELS = {
    "contrast": "反差型",
    "pain_point": "痛点型",
    "result": "结果型",
    "knowledge": "认知型",
    "suspense": "悬念型",
    "number": "数字型",
    "tutorial": "教程型",
    "controversy": "争议型",
}


def configure_page() -> None:
    st.set_page_config(
        page_title=f"{APP_TITLE} · Streamlit",
        page_icon="🎬",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(
        """
        <style>
        .block-container { padding-top: 1.5rem; }
        .AutoEdit-hero {
            padding: 1.25rem 1.5rem;
            border-radius: 18px;
            background: linear-gradient(135deg, #111827 0%, #2563eb 100%);
            color: white;
            margin-bottom: 1rem;
        }
        .AutoEdit-hero h1 { margin: 0; font-size: 2.1rem; }
        .AutoEdit-hero p { margin: .35rem 0 0; color: #dbeafe; }
        .small-muted { color: #6b7280; font-size: .9rem; }
        .result-card {
            padding: 1rem;
            border: 1px solid #e5e7eb;
            border-radius: 14px;
            background: #ffffff;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def init_state() -> None:
    defaults = {
        "project_id": "",
        "result": None,
        "logs": [],
        "last_error": "",
        "local_video_path": "",
        "user_intent": "",
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def render_header() -> None:
    st.markdown(
        f"""
        <div class="AutoEdit-hero">
            <h1>{APP_TITLE}</h1>
            <p>{APP_SUBTITLE} · 上传长视频，自动生成短视频、字幕、标题和封面文案。</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as file:
            return json.load(file)
    except Exception:
        return {}


def list_projects() -> List[Path]:
    if not OUTPUTS_DIR.exists():
        return []
    return sorted(
        [path for path in OUTPUTS_DIR.iterdir() if path.is_dir()],
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )


def project_output_path(project_id: str) -> Path:
    return OUTPUTS_DIR / project_id / "output.mp4"


def check_runtime_environment() -> List[Tuple[str, bool, str]]:
    settings = get_settings()
    checks = []
    checks.append(("FFmpeg", shutil.which("ffmpeg") is not None, "视频/音频处理"))
    checks.append(("LLM API Key", bool(settings.llm_api_key), "标题、分析、切片决策"))
    checks.append(("上传目录", UPLOADS_DIR.exists(), str(UPLOADS_DIR)))
    checks.append(("输出目录", OUTPUTS_DIR.exists(), str(OUTPUTS_DIR)))
    return checks


def render_environment_check() -> None:
    with st.expander("环境检查", expanded=False):
        for name, ok, detail in check_runtime_environment():
            icon = "✅" if ok else "⚠️"
            st.write(f"{icon} **{name}** · {detail}")


def save_uploaded_video(uploaded_file) -> Tuple[str, Path]:
    project_id = f"proj_{uuid.uuid4().hex[:12]}"
    suffix = Path(uploaded_file.name).suffix or ".mp4"
    upload_dir = UPLOADS_DIR / project_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    video_path = upload_dir / f"input{suffix}"

    with open(video_path, "wb") as file:
        file.write(uploaded_file.getbuffer())

    return project_id, video_path


def run_pipeline(project_id: str, params: dict) -> dict:
    from app.workflows.slice_workflow import run_full_pipeline

    st.session_state.logs = []
    logger = logging.getLogger("AutoEdit")
    handler = StreamlitLogHandler(st.session_state.logs)
    handler.setFormatter(
        logging.Formatter("%(asctime)s | %(levelname)-7s | %(message)s", "%H:%M:%S")
    )
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    try:
        return run_full_pipeline(project_id, params=params)
    finally:
        logger.removeHandler(handler)


class StreamlitLogHandler(logging.Handler):
    def __init__(self, logs: List[str]):
        super().__init__(logging.INFO)
        self.logs = logs

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.logs.append(self.format(record))
        except Exception:
            pass


def render_control_panel() -> Tuple[object, dict, bool]:
    st.markdown("### AutoEdit")
    st.caption("智能短视频切片")

    st.markdown("#### 输入设置")
    input_mode = st.radio(
        "视频来源",
        ["本地路径", "上传小文件"],
        horizontal=True,
        help="大视频建议使用本地路径，不走浏览器上传。",
    )

    uploaded_file = None
    local_video_path = ""
    if input_mode == "本地路径":
        local_video_path = st.text_input(
            "本地视频路径",
            value=st.session_state.local_video_path,
            placeholder=r"例如：C:\Users\你\Videos\input.mp4",
            help="Streamlit 在本机运行时，可以直接读取这个路径。",
        ).strip().strip('"')
        st.session_state.local_video_path = local_video_path
        if local_video_path:
            if Path(local_video_path).expanduser().exists():
                st.success("已找到本地视频文件")
            else:
                st.warning("这个路径暂时不存在，请检查文件路径。")
    else:
        uploaded_file = st.file_uploader(
            "选择视频文件",
            type=["mp4", "mov", "mkv", "avi", "webm"],
            help="适合 200MB 以下小文件；大文件请使用本地路径。",
        )

    platform_label = st.selectbox("目标平台", list(PLATFORMS.keys()), index=0)
    style_label = st.selectbox("视觉风格", list(STYLES.keys()), index=0)
    target_duration = st.number_input(
        "目标时长（秒）",
        min_value=0,
        max_value=600,
        value=0,
        step=5,
        help="0 表示自适应。",
    )
    batch_clip_count = st.number_input(
        "输出片段数量",
        min_value=1,
        max_value=50,
        value=1,
        step=1,
        help="从同一个长视频中批量生成多个独立短视频。",
    )
    params = {
        "platform": PLATFORMS[platform_label],
        "style": STYLES[style_label],
        "target_duration": int(target_duration),
        "batch_clip_count": int(batch_clip_count),
        "user_intent": st.session_state.user_intent.strip(),
    }
    if local_video_path:
        params["source_video"] = local_video_path

    start_clicked = st.button(
        "开始处理",
        type="primary",
        use_container_width=True,
        disabled=(not local_video_path and uploaded_file is None),
    )

    render_environment_check()

    if st.session_state.project_id:
        st.caption(f"当前项目：{st.session_state.project_id}")

    st.divider()
    render_history(compact=True)
    return uploaded_file, params, start_clicked


def load_project_result(project_id: str) -> dict:
    project_dir = OUTPUTS_DIR / project_id
    output_package = read_json(project_dir / "output_package.json")
    render_result = read_json(project_dir / "render_result.json")

    if output_package:
        return output_package
    if render_result:
        return {"project_id": project_id, "video": render_result}
    return {"project_id": project_id}


def get_display_package(result: Optional[dict], project_id: str) -> dict:
    if isinstance(result, dict):
        output_package = result.get("output_package")
        if isinstance(output_package, dict) and output_package:
            return output_package

        if result.get("titles") or result.get("cover_texts") or result.get("topics"):
            return result

        render_result = result.get("render_result")
        if isinstance(render_result, dict) and render_result:
            package = load_project_result(project_id)
            if package.get("titles") or package.get("cover_texts"):
                return package
            return {"project_id": project_id, "video": render_result}

    return load_project_result(project_id)


def render_progress(result: Optional[dict]) -> None:
    st.markdown("### 处理进度")
    completed = []
    if result:
        completed = result.get("completed_steps") or []
    if not completed and st.session_state.project_id:
        checkpoint = read_json(OUTPUTS_DIR / st.session_state.project_id / "_checkpoint.json")
        completed = checkpoint.get("completed_steps", [])

    done_count = len([step for step in STEP_ORDER if step in completed])
    st.progress(done_count / len(STEP_ORDER), text=f"流程进度：{done_count}/{len(STEP_ORDER)}")

    columns = st.columns(5)
    for index, step in enumerate(STEP_ORDER):
        label = STEP_LABELS[step]
        icon = "✅" if step in completed else "○"
        columns[index % 5].markdown(f"{icon} {label}")


def find_video_path(result: Optional[dict], project_id: str) -> Optional[Path]:
    if result:
        video = result.get("video") or result.get("render_result") or {}
        video_path = video.get("video_path") if isinstance(video, dict) else ""
        if video_path and Path(video_path).exists():
            return Path(video_path)

    fallback = project_output_path(project_id)
    if fallback.exists():
        return fallback
    return None


def render_result_panel(result: Optional[dict]) -> None:
    project_id = st.session_state.project_id
    if not project_id:
        st.info("请在左侧上传视频并开始处理。")
        return

    package = get_display_package(result, project_id)
    clips = package.get("clips", []) if isinstance(package, dict) else []
    if clips:
        st.markdown(f"### 批量切片结果（{len(clips)} 个）")
        for clip in clips:
            clip_index = clip.get("clip_index", 0)
            clip_id = clip.get("clip_id", f"clip_{clip_index}")
            title = clip.get("topic") or clip_id
            with st.expander(f"片段 {clip_index} · {title}", expanded=(clip_index == 1)):
                video_info = clip.get("video", {}) if isinstance(clip, dict) else {}
                video_path = video_info.get("video_path", "")
                if video_path and Path(video_path).exists():
                    st.video(video_path)
                    with open(video_path, "rb") as file:
                        st.download_button(
                            "下载这个片段",
                            data=file,
                            file_name=f"{project_id}_{clip_id}.mp4",
                            mime="video/mp4",
                            use_container_width=True,
                            key=f"download_{clip_id}",
                        )
                else:
                    st.warning("还没有找到这个片段的视频文件。")

                metric_cols = st.columns(4)
                metric_cols[0].metric("片段 ID", clip_id)
                metric_cols[1].metric(
                    "源区间",
                    f"{clip.get('source_start', 0):.1f}-{clip.get('source_end', 0):.1f}s",
                )
                metric_cols[2].metric(
                    "时长", f"{video_info.get('duration', 0):.1f}s" if video_info else "-"
                )
                size_mb = video_info.get("file_size", 0) / 1024 / 1024 if video_info else 0
                metric_cols[3].metric("大小", f"{size_mb:.1f} MB" if size_mb else "-")

                if clip.get("viewpoint"):
                    st.markdown(f"**观点/理由：** {clip.get('viewpoint')}")
                titles = clip.get("titles", {})
                if titles:
                    st.markdown("#### 标题建议")
                    render_title_suggestions(titles)
                topics = clip.get("topics", [])
                if topics:
                    st.markdown("#### 标签")
                    st.write(" ".join(topics))
                cover_texts = clip.get("cover_texts", [])
                if cover_texts:
                    st.markdown("#### 封面文案")
                    for text in cover_texts:
                        st.write(f"- {text}")
        return

    st.markdown("### 视频预览")
    video_path = find_video_path(result, project_id)

    if video_path:
        st.video(str(video_path))
        with open(video_path, "rb") as file:
            st.download_button(
                "下载成片",
                data=file,
                file_name=f"{project_id}.mp4",
                mime="video/mp4",
                use_container_width=True,
            )
    else:
        st.warning("还没有找到输出视频。")

    video_info = package.get("video", {}) if isinstance(package, dict) else {}
    metric_cols = st.columns(3)
    metric_cols[0].metric("项目 ID", project_id)
    metric_cols[1].metric("时长", f"{video_info.get('duration', 0):.1f}s" if video_info else "-")
    size_mb = video_info.get("file_size", 0) / 1024 / 1024 if video_info else 0
    metric_cols[2].metric("文件大小", f"{size_mb:.1f} MB" if size_mb else "-")

    titles = package.get("titles", {}) if isinstance(package, dict) else {}
    if titles:
        st.markdown("### 标题建议")
        render_title_suggestions(titles)

    cover_texts = package.get("cover_texts", []) if isinstance(package, dict) else []
    if cover_texts:
        st.markdown("### 封面文案")
        for text in cover_texts:
            st.write(f"- {text}")


def render_workspace() -> None:
    render_progress(st.session_state.result)
    st.divider()
    render_logs()
    st.divider()
    render_result_panel(st.session_state.result)


def render_title_suggestions(titles: dict) -> None:
    for title_type, title_list in titles.items():
        label = TITLE_TYPE_LABELS.get(title_type, title_type)
        with st.expander(label, expanded=title_type in ("contrast", "pain_point")):
            if not title_list:
                st.caption("暂无标题")
                continue
            for index, title in enumerate(title_list, start=1):
                st.write(f"{index}. {title}")


def render_ai_edit_brief_panel() -> None:
    st.markdown("### AI 剪辑需求")
    st.caption("用自然语言描述你想剪成什么样")

    user_intent = st.text_area(
        "剪辑目标",
        value=st.session_state.user_intent,
        placeholder=(
            "例如：剪辑有关争议的视频"
        ),
        height=180,
        help="这段需求会传给选片、文稿裁剪和标题生成环节。",
        key="ai_edit_intent_textarea",
    ).strip()
    st.session_state.user_intent = user_intent

    quick_prompts = {
        "干货 60 秒": "剪一条 60 秒左右的知识干货短视频，保留核心方法和结论，删除闲聊、重复和铺垫。",
        "冲突开头": "开头选择最有冲突感、反差感或争议感的一句话，后面保留解释原因和结论。",
        "情绪共鸣": "剪一条情绪共鸣强的短视频，保留真实经历、痛点表达和有代入感的句子。",
        "小红书风格": "剪成小红书风格，语气自然、有故事感，标题和封面文案要像真实经验分享。",
    }
    for index, (label, prompt) in enumerate(quick_prompts.items()):
        if st.button(label, use_container_width=True, key=f"ai_edit_quick_{index}"):
            st.session_state.user_intent = prompt
            st.rerun()

    if st.button("清空需求", use_container_width=True, key="ai_edit_clear_intent"):
        st.session_state.user_intent = ""
        st.rerun()

    st.divider()
    if st.session_state.user_intent:
        st.success("当前需求会在开始处理时生效。")
        st.markdown("#### 当前需求")
        st.write(st.session_state.user_intent)
    else:
        st.info("未填写时，系统会按默认爆款短视频标准自动剪辑。")

    render_project_summary()

def render_project_summary() -> None:
    project_id = st.session_state.project_id
    if not project_id:
        return

    package = get_display_package(st.session_state.result, project_id)
    topics = package.get("topics", []) if isinstance(package, dict) else []
    descriptions = package.get("descriptions", []) if isinstance(package, dict) else []

    st.divider()
    st.markdown("#### 项目摘要")
    st.caption(project_id)
    if topics:
        st.markdown("**话题标签**")
        st.write(" ".join(topics[:8]))
    if descriptions:
        st.markdown("**简介**")
        st.write(descriptions[0])


def render_logs() -> None:
    st.subheader("运行日志")
    if st.session_state.last_error:
        st.error(st.session_state.last_error)
    if st.session_state.logs:
        st.code("\n".join(st.session_state.logs[-300:]), language="text")
    else:
        st.caption("暂无日志。")


def render_history(compact: bool = False) -> None:
    if compact:
        st.markdown("#### 历史项目")
    else:
        st.subheader("历史项目")
    projects = list_projects()
    if not projects:
        st.caption("暂无历史项目。")
        return

    labels = [path.name for path in projects[:20]]
    selected = st.selectbox("选择历史项目", labels, index=0, label_visibility="collapsed" if compact else "visible")
    if st.button("加载历史项目", use_container_width=True, key="load_history_compact" if compact else "load_history"):
        st.session_state.project_id = selected
        st.session_state.result = load_project_result(selected)
        st.session_state.last_error = ""
        st.rerun()

    if compact:
        for project_dir in projects[:8]:
            done = (project_dir / "output_package.json").exists() or (project_dir / "output.mp4").exists()
            icon = "✅" if done else "○"
            st.caption(f"{icon} {project_dir.name}")


def handle_start(uploaded_file, params: dict) -> None:
    source_video = params.get("source_video", "")
    if source_video:
        source_path = Path(source_video).expanduser()
        if not source_path.exists():
            st.warning("请先填写有效的本地视频路径。")
            return
        project_id = f"proj_{uuid.uuid4().hex[:12]}"
        video_path = source_path
    else:
        if uploaded_file is None:
            st.warning("请先选择视频文件。")
            return
        project_id, video_path = save_uploaded_video(uploaded_file)

    st.session_state.project_id = project_id
    st.session_state.result = None
    st.session_state.last_error = ""

    with st.status("正在处理视频，请不要关闭页面...", expanded=True) as status:
        if source_video:
            st.write(f"使用本地视频：{video_path}")
        else:
            st.write(f"已保存视频：{video_path}")
        st.write("启动 AutoEdit 管线...")
        result = run_pipeline(project_id, params)

        if result.get("error"):
            st.session_state.last_error = str(result["error"])
            status.update(label="处理失败", state="error", expanded=True)
        else:
            st.session_state.result = result
            status.update(label="处理完成", state="complete", expanded=False)


def main() -> None:
    configure_page()
    init_state()
    render_header()

    left, center, right = st.columns([1.15, 2.7, 1.35], gap="large")
    with left:
        uploaded_file, params, start_clicked = render_control_panel()

    if start_clicked:
        handle_start(uploaded_file, params)

    with center:
        render_workspace()

    with right:
        render_ai_edit_brief_panel()


if __name__ == "__main__":
    main()
