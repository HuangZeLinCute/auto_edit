# 架构设计

## 总体架构

```
┌─────────────────────────────────────────────┐
│                  GUI (PySide6)                │
│  ┌───────────┬──────────┬───────────────┐   │
│  │ 输入面板   │ 进度/日志 │ AI 助手对话    │   │
│  └───────────┴──────────┴───────────────┘   │
└──────────────────┬──────────────────────────┘
                   │
         ┌─────────▼─────────┐
         │ PipelineWorker     │
         │ (QThread)          │
         └─────────┬─────────┘
                   │
┌──────────────────▼──────────────────────────┐
│            LangGraph StateGraph              │
│                                              │
│  preprocess → asr → analyze → select_clip    │
│       → trim_script → subtitles → audio      │
│            → render → generate_titles        │
│                                              │
│  (支持断点续跑，每步保存 checkpoint)          │
└──────────────────┬──────────────────────────┘
                   │
         ┌─────────▼─────────┐
         │   Services 层      │
         │  ┌──────────────┐  │
         │  │ FFmpegService │  │
         │  │ WhisperService│  │
         │  │ LLMService    │  │
         │  │ SubtitleService│ │
         │  └──────────────┘  │
         └───────────────────┘
```

## Agent 职责

| Agent | 输入 | 输出 | 核心逻辑 |
|-------|------|------|---------|
| PreprocessAgent | 源视频 | 提取的音频 + 视频信息 | ffmpeg 提取音轨 |
| AsrAgent | 音频 | transcript.json | Whisper 转录 |
| AnalysisAgent | transcript | analysis.json | LLM 分析主题/情绪/密度 |
| ClipSelectAgent | transcript + analysis | clip_plan.json | LLM 选取候选切片 |
| ScriptTrimAgent | clip_plan + transcript | edit_decision.json | LLM 裁剪 + 词边界对齐 |
| SubtitleAgent | edit_decision | subtitle.ass | ASS 字幕 + 关键词高亮 |
| AudioAgent | edit_decision | mixed_audio.wav | 人声标准化 |
| TitleAgent | edit_decision | titles + topics | LLM 生成标题/话题 |

## 状态流转

```python
state = {
    "project_id": str,
    "params": dict,           # platform, style, target_duration
    "transcript": dict,       # ASR 结果
    "analysis": dict,         # LLM 分析
    "clip_plan": dict,        # 切片候选
    "edit_decision": dict,    # 最终剪辑决策
    "subtitle_plan": dict,    # 字幕方案
    "audio_plan": dict,       # 音频方案
    "render_result": dict,    # 渲染结果
    "completed_steps": list,  # 已完成步骤（用于断点续跑）
    "current_step": str,
    "error": str | None,
}
```

## 数据目录

```
storage/
├── uploads/{project_id}/      # 用户上传的源视频
├── outputs/{project_id}/      # 处理结果
│   ├── output.mp4             # 最终视频
│   ├── transcript.json        # ASR 结果
│   ├── edit_decision.json     # 剪辑决策
│   ├── subtitle_plan.json     # 字幕方案
│   ├── subtitles.ass          # ASS 字幕文件
│   ├── trim/                  # 中间产物
│   │   ├── edited_audio.wav
│   │   └── video_segments/
│   └── render/                # 渲染中间产物
└── temp/{project_id}/         # 临时文件
```

## GUI 线程模型

```
主线程 (Qt Event Loop)
  ├── 用户交互
  ├── 进度更新 (Signal/Slot)
  └── 视频播放

Worker 线程 (QThread)
  ├── run_full_pipeline()
  ├── logging.Handler → Signal → 主线程更新日志
  └── 完成后发 finished_ok/failed 信号
```

日志通过自定义 `logging.Handler` 捕获，转发为 Qt Signal，在主线程安全更新 UI。
