# AutoEdit - 开发方案

## 项目结构

```
视频剪辑AI/
├── docs/                           # 文档
│   ├── 01_TECHNICAL_ROADMAP.md     # 技术路线图
│   ├── 02_DEVELOPMENT_PLAN.md      # 开发方案（本文件）
│   ├── 03_ACCEPTANCE_CRITERIA.md   # 验收标准
│   ├── 04_API_SPECIFICATION.md     # API 规范
│   ├── 05_DATA_SCHEMA.md           # 数据结构设计
│   └── 06_PROMPT_LIBRARY.md        # Prompt 库
├── app/
│   ├── main.py                     # FastAPI 入口
│   ├── config.py                   # 配置管理
│   ├── api/
│   │   ├── upload.py               # 上传接口
│   │   ├── task.py                 # 任务管理接口
│   │   ├── preview.py              # 预览接口
│   │   └── export.py               # 导出接口
│   ├── agents/
│   │   ├── preprocess_agent.py     # 预处理 Agent
│   │   ├── asr_agent.py            # 语音识别 Agent
│   │   ├── analysis_agent.py       # 内容分析 Agent
│   │   ├── clip_select_agent.py    # 切片选择 Agent
│   │   ├── script_trim_agent.py    # 文稿裁剪 Agent
│   │   ├── visual_agent.py         # 图文画面 Agent
│   │   ├── subtitle_agent.py       # 字幕 Agent
│   │   ├── audio_agent.py          # 音频包装 Agent
│   │   └── title_agent.py          # 标题话题 Agent
│   ├── services/
│   │   ├── ffmpeg_service.py       # FFmpeg 封装
│   │   ├── whisper_service.py      # WhisperX 封装
│   │   ├── llm_service.py          # LLM 调用封装
│   │   ├── image_gen_service.py    # 图片生成封装
│   │   ├── subtitle_service.py     # 字幕生成封装
│   │   ├── audio_mix_service.py    # 音频混音封装
│   │   └── storage_service.py      # 存储服务
│   ├── workflows/
│   │   └── slice_workflow.py       # LangGraph 主工作流
│   ├── schemas/
│   │   ├── transcript.py           # ASR 输出结构
│   │   ├── clip_plan.py            # 切片计划结构
│   │   ├── edit_decision.py        # 剪辑决策结构
│   │   ├── render_plan.py          # 渲染计划结构
│   │   └── output.py               # 输出结果结构
│   ├── workers/
│   │   ├── celery_app.py           # Celery 配置
│   │   └── tasks.py                # 异步任务定义
│   ├── utils/
│   │   ├── time_utils.py           # 时间处理工具
│   │   ├── text_utils.py           # 文本处理工具
│   │   └── logger.py               # 日志工具
│   └── prompts/
│       ├── analyze.txt             # 内容分析 Prompt
│       ├── clip_select.txt         # 切片选择 Prompt
│       ├── script_trim.txt         # 文稿裁剪 Prompt
│       ├── visual_prompt.txt       # 图片提示词生成 Prompt
│       ├── sfx_plan.txt            # 音效规划 Prompt
│       └── title_gen.txt           # 标题生成 Prompt
├── render/
│   └── remotion/                   # Remotion 渲染项目（后期）
├── assets/
│   ├── sfx/
│   │   ├── hit/                    # 打击音效
│   │   ├── whoosh/                 # 转场音效
│   │   └── rise/                   # 递进音效
│   ├── bgm/                        # 背景音乐
│   └── fonts/                      # 字体文件
├── configs/
│   ├── forbidden_words.yaml        # 违禁词库
│   ├── filler_words.yaml           # 语气词库
│   ├── style_presets.yaml          # 视觉风格预设
│   ├── platform_presets.yaml       # 平台参数预设
│   └── sfx_rules.yaml              # 音效规则配置
├── tests/
│   ├── test_asr.py
│   ├── test_analysis.py
│   ├── test_trim.py
│   ├── test_render.py
│   └── test_e2e.py
├── scripts/
│   ├── setup_env.sh                # 环境初始化
│   ├── download_models.sh          # 下载模型
│   └── run_dev.sh                  # 开发启动脚本
├── storage/
│   ├── uploads/                    # 上传文件
│   ├── outputs/                    # 输出文件
│   └── temp/                       # 临时文件
├── requirements.txt
├── docker-compose.yml
├── Dockerfile
├── .env.example
└── Makefile
```

---

## Phase 0：基础设施搭建（第 1 周）

### 目标

搭建项目骨架，所有基础服务可运行。

### 任务清单

| 编号 | 任务 | 优先级 | 预估 |
|------|------|--------|------|
| 0.1 | 初始化 Python 项目，配置 poetry/pip | P0 | 2h |
| 0.2 | FastAPI 项目骨架 + 热重载 | P0 | 2h |
| 0.3 | Celery + Redis 配置 | P0 | 2h |
| 0.4 | PostgreSQL 表结构设计 + SQLAlchemy 模型 | P0 | 3h |
| 0.5 | MinIO / 本地存储服务 | P1 | 2h |
| 0.6 | FFmpeg 安装 + Python 调通 | P0 | 2h |
| 0.7 | WhisperX 安装 + 基础测试 | P0 | 3h |
| 0.8 | LLM API 接通（DeepSeek/Qwen/GPT） | P0 | 2h |
| 0.9 | docker-compose 编排 | P1 | 3h |
| 0.10 | 日志/配置/错误处理基础设施 | P1 | 2h |

### 验收标准

- [ ] `docker-compose up` 能启动 FastAPI + Celery + Redis + PostgreSQL
- [ ] FastAPI `/health` 接口返回 200
- [ ] Celery worker 能接收并执行测试任务
- [ ] FFmpeg 能通过 Python subprocess 执行基础命令
- [ ] WhisperX 能对一段测试音频生成带时间戳的文稿
- [ ] LLM API 能正常调用并返回结构化 JSON
- [ ] 文件上传到 storage/uploads 并能检索

---

## Phase 1：ASR + 文稿管道（第 2-3 周）

### 目标

输入任意视频/音频，输出带词级时间戳的完整文稿。

### 任务清单

| 编号 | 任务 | 优先级 | 预估 |
|------|------|--------|------|
| 1.1 | FFmpegService：提取音频 wav 16kHz | P0 | 2h |
| 1.2 | FFmpegService：获取视频元信息 | P0 | 1h |
| 1.3 | WhisperService：加载模型 + 推理 | P0 | 4h |
| 1.4 | 语气词检测（基于 filler_words.yaml） | P0 | 2h |
| 1.5 | 停顿检测（基于 WhisperX 词间隔） | P0 | 2h |
| 1.6 | 违禁词检测（基于 forbidden_words.yaml） | P0 | 2h |
| 1.7 | PreprocessAgent：完整预处理流程编排 | P0 | 3h |
| 1.8 | ASRAgent：完整 ASR 流程编排 | P0 | 3h |
| 1.9 | Transcript 数据结构定义 | P0 | 1h |
| 1.10 | ASR 结果持久化（PostgreSQL + JSON 文件） | P1 | 2h |
| 1.11 | 长音频分段处理（>30 分钟） | P1 | 3h |
| 1.12 | 中文 ASR 增强（FunASR 备选接入） | P2 | 4h |

### 核心数据流

```
input.mp4
    |
    v  FFmpegService.extract_audio()
audio.wav (16kHz mono)
    |
    v  WhisperService.transcribe()
{
  "segments": [
    {
      "id": 0,
      "start": 12.50,
      "end": 18.90,
      "text": "你以为直播切片最重要的是剪辑",
      "words": [
        {"word": "你", "start": 12.50, "end": 12.70, "score": 0.98},
        {"word": "以为", "start": 12.70, "end": 13.10, "score": 0.95},
        ...
      ]
    }
  ]
}
    |
    v  ASRAgent.post_process()
{
  "segments": [...],
  "filler_words": [
    {"word": "嗯", "start": 10.2, "end": 10.5, "segment_id": 0}
  ],
  "silences": [
    {"start": 45.3, "end": 46.8, "duration": 1.5}
  ],
  "risk_words": [
    {"word": "xxx", "start": 120.5, "end": 120.8, "segment_id": 15, "level": "high"}
  ]
}
```

### 验收标准

- [ ] 输入 30 分钟测试视频，10 分钟内完成 ASR
- [ ] 输出包含句级和词级时间戳
- [ ] 语气词识别准确率 > 85%（抽样 100 个）
- [ ] 停顿检测误报率 < 10%
- [ ] 违禁词库命中正常，无误伤
- [ ] 长音频（>30 分钟）能自动分段处理
- [ ] ASR 结果保存到数据库和 JSON 文件
- [ ] 处理异常时任务状态正确标记为 failed

---

## Phase 2：文稿分析 + 切片选择（第 4-5 周）

### 目标

从 30 分钟文稿中自动找出 1-3 个高价值切片候选，并选择最佳钩子。

### 任务清单

| 编号 | 任务 | 优先级 | 预估 |
|------|------|--------|------|
| 2.1 | AnalysisAgent：内容章节切分 | P0 | 4h |
| 2.2 | AnalysisAgent：核心观点提取 | P0 | 3h |
| 2.3 | AnalysisAgent：金句提取 | P0 | 2h |
| 2.4 | ClipSelectAgent：多维度评分算法 | P0 | 6h |
| 2.5 | ClipSelectAgent：钩子选择算法 | P0 | 4h |
| 2.6 | ClipSelectAgent：多候选切片输出 | P0 | 3h |
| 2.7 | Prompt 设计 + 调优（analyze） | P0 | 4h |
| 2.8 | Prompt 设计 + 调优（clip_select） | P0 | 4h |
| 2.9 | ClipPlan 数据结构定义 | P0 | 2h |
| 2.10 | LLM 结构化输出校验 | P1 | 2h |
| 2.11 | 规则评分 + LLM 评分融合策略 | P1 | 3h |
| 2.12 | 多轮对话式切片确认（可选） | P2 | 4h |

### 评分算法设计

```python
def compute_clip_score(clip):
    return (
        0.25 * hook_score +           # 钩子吸引力
        0.20 * information_density +   # 信息密度
        0.20 * completeness_score +    # 观点完整度
        0.15 * shareability_score +    # 传播性
        0.10 * emotion_score +         # 情绪强度
        0.10 * visualizable_score -    # 可视化程度
        0.20 * risk_score              # 违禁风险（扣分项）
    )
```

规则评分来源：

```python
# 信息密度：有效词数 / 总时长
information_density = effective_word_count / duration_seconds

# 情绪强度：基于关键词 + 音量变化
emotion_score = keyword_emotion_score * 0.6 + volume_change_score * 0.4

# 观点完整度：LLM 判断（1-10）
completeness_score = llm_completeness_rating

# 钩子强度：是否包含反转/数字/痛点/冲突
hook_score = (
    has_contrast * 3 +
    has_number * 2 +
    has_pain_point * 2 +
    has_conflict * 2 +
    under_5_seconds * 1
)
```

### 验收标准

- [ ] 对 5 段不同类型测试视频，每段输出至少 2 个候选切片
- [ ] 候选切片的主题和原文一致，无幻觉
- [ ] 钩子句子确实来自原文，时间戳准确
- [ ] 评分排序与人工判断相关性 > 70%
- [ ] 选出的切片时长在 30-180 秒之间
- [ ] 不包含高违禁风险内容
- [ ] LLM 输出为合法 JSON，解析无报错
- [ ] 处理失败时有明确错误信息和回退策略

---

## Phase 3：音频裁剪 + 钩子拼接（第 6 周）

### 目标

根据裁剪后的文稿时间戳，精确回剪音频和视频片段，前 5 秒保留原视频。

### 任务清单

| 编号 | 任务 | 优先级 | 预估 |
|------|------|--------|------|
| 3.1 | ScriptTrimAgent：LLM 文稿裁剪 | P0 | 6h |
| 3.2 | Prompt 设计 + 调优（script_trim） | P0 | 4h |
| 3.3 | 时间戳对齐校验 | P0 | 3h |
| 3.4 | FFmpegService：音频裁剪 + crossfade | P0 | 3h |
| 3.5 | FFmpegService：视频裁剪 | P0 | 2h |
| 3.6 | 钩子片段提取（前 5 秒原视频） | P0 | 2h |
| 3.7 | 音频片段拼接 + 降噪 | P0 | 3h |
| 3.8 | EditDecision 数据结构定义 | P0 | 2h |
| 3.9 | 裁剪后音频质量检测 | P1 | 2h |
| 3.10 | 缺口/断裂自动修复 | P1 | 3h |

### 裁剪流程

```
原始文稿（带时间戳）
    |
    v  ScriptTrimAgent（LLM）
裁剪后文稿（保留段 + 删除段，都带时间戳）
    |
    v  FFmpegService
keep_segments 按顺序裁剪音频
    |
    v  pydub / FFmpeg
拼接音频片段，每个切口加 40ms crossfade
    |
    v  FFmpegService
提取钩子对应的 5 秒原视频
    |
    v  输出
hook_video.mp4（5 秒原视频）
edited_audio.wav（裁剪后完整音频）
edit_decision.json（剪辑决策记录）
```

### 裁剪规则

```yaml
silence:
  under_0.3s: keep
  0.3s_to_0.8s: compress_to_0.2s
  over_0.8s: delete

filler_words:
  standalone: delete          # "嗯" 独立出现，删除
  in_sentence: evaluate       # 句内语气词，LLM 判断是否保留

repetition:
  same_meaning_within_10s: keep_first

crossfade:
  duration_ms: 40
  type: linear

forbidden_words:
  audio: mute_or_beep
  subtitle: replace_with_star
  severe: delete_full_sentence
```

### 验收标准

- [ ] 裁剪后音频无明显断裂感（人工听 10 个样本，8 个以上流畅）
- [ ] 裁剪后文案逻辑通顺，无语义跳跃
- [ ] 不存在原文中没有出现过的句子
- [ ] 钩子时长 3-5 秒，来自原视频
- [ ] crossfade 处理后无爆音和杂音
- [ ] 违禁词音频已消音或 beep 替换
- [ ] 总时长符合目标范围（30-180 秒）
- [ ] edit_decision.json 记录了所有保留段和删除段

---

## Phase 4：AI 图片生成 + 视觉层（第 7-8 周）

### 目标

5 秒后所有画面用 AI 生成图片替换，每 3-5 秒一张，风格统一。

### 任务清单

| 编号 | 任务 | 优先级 | 预估 |
|------|------|--------|------|
| 4.1 | VisualAgent：文案分段（每 3-5 秒一段） | P0 | 3h |
| 4.2 | VisualAgent：图片 prompt 生成 | P0 | 4h |
| 4.3 | Prompt 设计 + 调优（visual_prompt） | P0 | 4h |
| 4.4 | ImageGenService：ComfyUI API 接入 | P0 | 6h |
| 4.5 | ImageGenService：即梦/OpenAI API 备选 | P1 | 3h |
| 4.6 | 风格预设系统（5 套风格） | P0 | 2h |
| 4.7 | 图片生成质量检测（分辨率/色调） | P1 | 2h |
| 4.8 | 图片转视频片段（zoompan/pan） | P0 | 3h |
| 4.9 | RenderPlan 数据结构定义 | P0 | 2h |
| 4.10 | 批量图片生成（并行） | P1 | 3h |
| 4.11 | 生成失败重试 + 降级策略 | P1 | 2h |
| 4.12 | 素材库检索（后期扩展） | P2 | 4h |

### 视觉分段规则

```python
def split_visual_segments(edited_script, avg_segment_duration=4.0):
    """
    把裁剪后文稿按语义和时长拆成视觉段落
    每段 3-5 秒，生成一张图片
    """
    segments = []
    for sentence in edited_script.sentences:
        duration = sentence.end - sentence.start
        if duration <= 5.0:
            segments.append(sentence)
        else:
            # 长句拆分
            sub_segments = split_by_pause(sentence, target=4.0)
            segments.extend(sub_segments)
    return segments
```

### 图片 Prompt 模板

```
[全局风格前缀], [画面主体描述], [情绪/氛围], [构图/镜头], [技术参数]

示例：
"cinematic tech documentary style, a glowing golden sentence emerging from 
a long dim transcript, concept of finding valuable content, dramatic lighting, 
high contrast, dark background, 9:16 vertical composition, 4K, sharp focus"
```

### 5 套风格预设

```yaml
business_tech:
  prefix: "cinematic tech documentary style, dark background, golden highlights"
  mood: "professional, insightful"
  palette: "dark blue, gold, white"

knowledge_infographic:
  prefix: "clean minimal infographic style, light background, clear icons"
  mood: "educational, clear"
  palette: "white, blue, green"

emotional_impact:
  prefix: "high contrast dramatic style, intense atmosphere, bold composition"
  mood: "powerful, urgent"
  palette: "black, red, gold"

workplace_career:
  prefix: "modern business illustration style, warm lighting, professional"
  mood: "relatable, practical"
  palette: "warm grey, blue, orange"

text_card:
  prefix: "gradient background, bold Chinese typography, highlighted keywords"
  mood: "clean, direct"
  palette: "gradient purple-blue, white, yellow"
```

### 验收标准

- [ ] 每段 3-5 秒文案对应一张图片
- [ ] 所有图片风格统一（同一预设）
- [ ] 图片分辨率 >= 1080x1920（9:16 竖屏）
- [ ] 图片内容与文案语义相关（人工判断 10 张，7 张以上相关）
- [ ] 图片无明显违规/裸露/恐怖内容
- [ ] 生成失败有重试机制（最多 3 次）
- [ ] 90 秒视频图片生成总耗时 < 3 分钟
- [ ] 图片转视频后动效流畅（zoompan 无卡顿）

---

## Phase 5：字幕 + 重点词标注（第 9 周）

### 目标

生成 ASS 字幕，重点词高亮、放大、变色。

### 任务清单

| 编号 | 任务 | 优先级 | 预估 |
|------|------|--------|------|
| 5.1 | SubtitleAgent：字幕生成（基于词级时间戳） | P0 | 4h |
| 5.2 | 重点词识别算法 | P0 | 3h |
| 5.3 | 重点词类型分类（数字/结论/反转/情绪/行动） | P0 | 2h |
| 5.4 | ASS 字幕样式定义 | P0 | 3h |
| 5.5 | 重点词动效（放大/变色/弹跳） | P1 | 3h |
| 5.6 | 字幕换行算法（每行 <= 12 字） | P0 | 2h |
| 5.7 | SubtitleService：ASS 文件生成 | P0 | 3h |
| 5.8 | 字幕预览 + 调整接口 | P2 | 2h |

### 重点词规则

```yaml
keyword_types:
  number:
    patterns: ["\\d+", "几", "多少", "一半", "翻倍", "倍"]
    color: "#FFD84D"      # 金黄
    effect: scale_120
    priority: high

  conclusion:
    words: ["核心", "关键", "本质", "根本", "真正", "其实", "重点"]
    color: "#4DFFFF"      # 青色
    effect: bold
    priority: high

  reversal:
    words: ["但是", "然而", "没想到", "反而", "不是", "而是", "其实"]
    color: "#FF6B6B"      # 红色
    effect: pop
    priority: high

  emotion:
    words: ["崩了", "爆了", "离谱", "太强了", "绝了", "炸裂", "恐怖"]
    color: "#FF4D4F"      # 亮红
    effect: shake
    priority: medium

  action:
    words: ["必须", "一定", "千万别", "务必", "赶紧", "马上"]
    color: "#FFD84D"      # 金黄
    effect: pulse
    priority: medium

  pain_point:
    words: ["亏", "踩坑", "被骗", "不知道", "没人告诉你", "亏大了"]
    color: "#FF8C42"      # 橙色
    effect: underline
    priority: medium
```

### ASS 字幕样式

```ass
[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Alibaba PuHuiTi,72,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,2,0,1,6,3,2,30,30,60,1
Style: Highlight,Alibaba PuHuiTi,72,&H0000D8FF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,120,120,2,0,1,6,3,2,30,30,60,1
Style: GoldHit,Alibaba PuHuiTi,90,&H0000D8FF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,150,150,2,0,1,8,4,2,30,30,60,1
```

### 验收标准

- [ ] 字幕与音频时间同步，误差 < 200ms
- [ ] 每行字幕 <= 12 个汉字
- [ ] 重点词正确识别并高亮（抽样 50 个词，准确率 > 80%）
- [ ] 字幕不遮挡核心画面区域
- [ ] ASS 文件格式合法，FFmpeg 可正确渲染
- [ ] 字幕换行位置合理，不在词语中间断开
- [ ] 重点词颜色区分度明显

---

## Phase 6：音效 + BGM 混音（第 10 周）

### 目标

根据文案节奏自动添加音效和 BGM。

### 任务清单

| 编号 | 任务 | 优先级 | 预估 |
|------|------|--------|------|
| 6.1 | AudioAgent：音效节点规划 | P0 | 4h |
| 6.2 | Prompt 设计 + 调优（sfx_plan） | P0 | 3h |
| 6.3 | 音效素材库整理（hit/whoosh/rise） | P0 | 2h |
| 6.4 | BGM 素材库整理（分类标签） | P0 | 2h |
| 6.5 | BGM 自动选择算法 | P0 | 3h |
| 6.6 | AudioMixService：音效插入 | P0 | 3h |
| 6.7 | AudioMixService：BGM 混音 | P0 | 3h |
| 6.8 | 音量控制（人声优先） | P0 | 2h |
| 6.9 | 混音质量检测 | P1 | 2h |
| 6.10 | 音效规则配置（sfx_rules.yaml） | P0 | 2h |

### 音效规则

```yaml
sfx_rules:
  hook_start:
    trigger: "视频开始"
    sfx: "hit_01"
    volume_db: -8
    max_per_video: 1

  transition_to_visual:
    trigger: "从原视频切换到 AI 图片（第5秒）"
    sfx: "whoosh_01"
    volume_db: -12
    max_per_video: 1

  key_point:
    trigger: "核心观点/结论词出现"
    sfx: "hit_soft_01"
    volume_db: -10
    min_interval_s: 5
    max_per_video: 5

  reversal:
    trigger: "反转词出现（但是/然而/其实）"
    sfx: "whoosh_reverse_01"
    volume_db: -12
    min_interval_s: 8
    max_per_video: 3

  emotion_rise:
    trigger: "情绪递进段落"
    sfx: "rise_01"
    volume_db: -14
    duration_s: 3
    max_per_video: 2

  golden_sentence:
    trigger: "金句落点"
    sfx: "impact_01"
    volume_db: -8
    max_per_video: 2

  ending:
    trigger: "视频结尾"
    sfx: "soft_boom_01"
    volume_db: -10
    max_per_video: 1

bgm_rules:
  volume_db: -24
  fade_in_s: 1.0
  fade_out_s: 2.0
  duck_on_sfx: true
  duck_db: -6
  categories:
    knowledge: "light, tech, 90-110bpm"
    business: "tech, low_freq, 80-100bpm"
    emotional: "piano, ambient, 70-90bpm"
    high_energy: "drums, fast, 120-140bpm"
```

### 混音流程

```
edited_audio.wav（人声）
    |
    v  AudioMixService
1. 分析人声音量曲线
2. 选择 BGM（基于切片类型）
3. 确定音效插入点（基于 sfx_rules）
4. 插入音效（叠加到音轨）
5. 混入 BGM（音量 -24dB）
6. BGM 在音效处自动 duck -6dB
7. 整体 normalize
    |
    v  输出
mixed_audio.wav
```

### 验收标准

- [ ] 人声清晰可辨，BGM 不干扰
- [ ] BGM 音量在 -22dB 到 -28dB 之间
- [ ] 音效在关键节点正确触发（抽样 20 个节点，准确率 > 85%）
- [ ] 音效不重叠（同类型音效间隔 >= 5 秒）
- [ ] 无爆音/杂音/削波
- [ ] BGM 类型与内容情绪匹配
- [ ] 结尾 BGM 淡出自然
- [ ] 混音后音频峰值不超过 -1dB

---

## Phase 7：渲染合成 + 标题生成（第 11 周）

### 目标

将所有素材合成为最终视频，生成标题、话题、封面文案。

### 任务清单

| 编号 | 任务 | 优先级 | 预估 |
|------|------|--------|------|
| 7.1 | FFmpegService：钩子视频裁剪 | P0 | 2h |
| 7.2 | FFmpegService：图片序列转视频 | P0 | 3h |
| 7.3 | FFmpegService：音视频合成 | P0 | 3h |
| 7.4 | FFmpegService：字幕烧录 | P0 | 2h |
| 7.5 | FFmpegService：最终混音合成 | P0 | 2h |
| 7.6 | 完整渲染管线编排 | P0 | 4h |
| 7.7 | TitleAgent：标题生成 | P0 | 3h |
| 7.8 | Prompt 设计 + 调优（title_gen） | P0 | 3h |
| 7.9 | 多平台标题适配 | P1 | 2h |
| 7.10 | 封面文案生成 | P1 | 2h |
| 7.11 | 话题标签生成 | P1 | 1h |
| 7.12 | 输出包打包（视频 + 元数据） | P1 | 2h |

### 渲染管线

```
slice_plan.json
    |
    v
Step 1: 裁剪钩子视频
  FFmpeg -ss {hook_start} -to {hook_end} -i input.mp4 -c copy hook.mp4
    |
    v
Step 2: 生成图片视频片段
  for each visual_segment:
    FFmpeg -loop 1 -i image_N.png -t {duration} -vf "zoompan=z='min(zoom+0.001,1.3)'" segment_N.mp4
    |
    v
Step 3: 拼接所有视频片段
  FFmpeg -f concat -i filelist.txt -c copy video_only.mp4
    |
    v
Step 4: 替换音频
  FFmpeg -i video_only.mp4 -i mixed_audio.wav -c:v copy -c:a aac -map 0:v:0 -map 1:a:0 with_audio.mp4
    |
    v
Step 5: 烧录字幕
  FFmpeg -i with_audio.mp4 -vf ass=subtitles.ass -c:a copy final.mp4
    |
    v
Step 6: 转码输出
  FFmpeg -i final.mp4 -c:v libx264 -preset medium -crf 23 -c:a aac -b:a 128k output_{platform}.mp4
    |
    v
输出: output.mp4 + titles.json + topics.json + cover_texts.json
```

### 标题类型

```yaml
title_types:
  contrast:
    name: "反差型"
    template: "{A}，其实{B}"
    example: "你以为爆款靠剪辑，其实靠这一步"
    
  pain_point:
    name: "痛点型"
    template: "为什么你{A}还是{B}？"
    example: "为什么你剪了100条视频还是不爆？"
    
  result:
    name: "结果型"
    template: "{A}后，{B}"
    example: "搞懂这个逻辑后，切片播放量翻了10倍"
    
  knowledge:
    name: "认知型"
    template: "{A}的本质，不是{B}，而是{C}"
    example: "短视频切片的本质，不是剪辑，而是筛选"
    
  suspense:
    name: "悬念型"
    template: "{A}的秘密，{B}"
    example: "直播切片做不好的秘密，99%的人不知道"
    
  number:
    name: "数字型"
    template: "{N}个{A}，{B}"
    example: "3个直播切片技巧，新手也能出爆款"
    
  tutorial:
    name: "教程型"
    template: "如何{A}？{B}"
    example: "如何用AI做直播切片？完整流程分享"
    
  controversy:
    name: "争议型"
    template: "{A}，到底对不对？"
    example: "AI切片能不能替代人工剪辑？"
```

### 验收标准

- [ ] 渲染后视频可正常播放，无花屏/黑屏
- [ ] 视频分辨率 1080x1920（9:16）
- [ ] 前 5 秒是原视频 + 原音频
- [ ] 5 秒后是 AI 图片 + 原音频
- [ ] 字幕与音频同步
- [ ] 音效/BGM 与人声混音正常
- [ ] 视频文件大小合理（90 秒 < 50MB）
- [ ] 生成至少 8 种类型的标题，每类 2-3 个
- [ ] 标题无违禁词，可直接用于平台发布
- [ ] 话题标签与内容相关
- [ ] 完整输出包：视频 + 字幕 + 元数据

---

## Phase 8：端到端集成 + 测试（第 12-13 周）

### 目标

串联所有模块，实现从上传到输出的完整自动化流水线。

### 任务清单

| 编号 | 任务 | 优先级 | 预估 |
|------|------|--------|------|
| 8.1 | LangGraph 主工作流编排 | P0 | 6h |
| 8.2 | Celery 异步任务链 | P0 | 4h |
| 8.3 | 上传接口实现 | P0 | 3h |
| 8.4 | 任务状态查询接口 | P0 | 2h |
| 8.5 | 预览接口（候选切片列表） | P0 | 3h |
| 8.6 | 导出接口（触发渲染） | P0 | 3h |
| 8.7 | 进度通知（WebSocket / 轮询） | P1 | 3h |
| 8.8 | 错误处理 + 重试机制 | P0 | 4h |
| 8.9 | 端到端测试（5 段不同类型视频） | P0 | 6h |
| 8.10 | 性能测试 + 耗时优化 | P1 | 4h |
| 8.11 | 边界情况测试 | P1 | 4h |

### LangGraph 工作流

```python
from langgraph.graph import StateGraph, END

workflow = StateGraph(SliceState)

workflow.add_node("preprocess", preprocess_node)
workflow.add_node("asr", asr_node)
workflow.add_node("analyze", analyze_node)
workflow.add_node("select_clip", select_clip_node)
workflow.add_node("trim_script", trim_script_node)
workflow.add_node("generate_visuals", generate_visuals_node)
workflow.add_node("generate_subtitles", generate_subtitles_node)
workflow.add_node("plan_audio", plan_audio_node)
workflow.add_node("render", render_node)
workflow.add_node("generate_titles", generate_titles_node)

workflow.set_entry_point("preprocess")

workflow.add_edge("preprocess", "asr")
workflow.add_edge("asr", "analyze")
workflow.add_edge("analyze", "select_clip")
workflow.add_edge("select_clip", "trim_script")
workflow.add_edge("trim_script", "generate_visuals")
workflow.add_edge("generate_visuals", "generate_subtitles")
workflow.add_edge("generate_subtitles", "plan_audio")
workflow.add_edge("plan_audio", "render")
workflow.add_edge("render", "generate_titles")
workflow.add_edge("generate_titles", END)
```

### 端到端测试用例

| 用例 | 输入 | 预期 |
|------|------|------|
| 标准直播 | 30 分钟知识分享直播 | 输出 1-3 条 60-90 秒切片 |
| 短素材 | 10 分钟直播片段 | 至少输出 1 条切片 |
| 中英混合 | 中英混合直播 | ASR 正确识别，字幕正确 |
| 高噪音 | 背景噪音较大的直播 | ASR 能识别主要内容 |
| 单人独白 | 一个人连续讲 30 分钟 | 正常切片，无异常 |
| 多段高光 | 内容有多个明显高潮 | 输出多个候选切片 |
| 无高光 | 内容平淡无亮点 | 提示"未找到适合切片的内容" |
| 违禁词 | 包含多个违禁词 | 正确检测并处理 |

### 验收标准

- [ ] 上传 30 分钟视频后 15 分钟内完成全流程
- [ ] 全流程无人工干预（从上传到输出）
- [ ] 任何步骤失败都有明确的错误信息
- [ ] 失败任务可从断点重试，不需从头开始
- [ ] 任务状态实时可查
- [ ] 8 个端到端测试用例全部通过
- [ ] 连续处理 3 个视频无内存泄漏
- [ ] 生成视频可直接在抖音/视频号播放

---

## Phase 9：优化 + 产品化（第 14-15 周）

### 目标

提升质量、稳定性、用户体验。

### 任务清单

| 编号 | 任务 | 优先级 | 预估 |
|------|------|--------|------|
| 9.1 | LLM Prompt 全面调优（基于测试结果） | P0 | 6h |
| 9.2 | ASR 中文准确率优化 | P0 | 4h |
| 9.3 | 图片生成质量优化 | P1 | 4h |
| 9.4 | 渲染速度优化 | P1 | 3h |
| 9.5 | 多版本输出（30s/60s/90s） | P1 | 4h |
| 9.6 | 用户选择界面（选切片/选风格） | P1 | 4h |
| 9.7 | 配置管理界面（违禁词/风格/平台） | P2 | 4h |
| 9.8 | 日志 + 监控 + 告警 | P1 | 3h |
| 9.9 | 部署文档 + 运维手册 | P2 | 3h |
| 9.10 | 压力测试（连续处理 10 个视频） | P1 | 3h |

### 验收标准

- [ ] 端到端处理耗时 < 12 分钟（30 分钟输入视频）
- [ ] 生成视频人工评分 >= 7/10（5 人评估取均值）
- [ ] 连续处理 10 个视频无崩溃
- [ ] 用户可选择切片、风格、时长
- [ ] 配置修改无需重启服务
- [ ] 完整的部署文档

---

## 关键依赖版本

```
Python >= 3.10
FFmpeg >= 6.0
faster-whisper >= 1.0
whisperx >= 3.1
torch >= 2.1
celery >= 5.3
redis >= 7.0
postgresql >= 15
fastapi >= 0.109
langgraph >= 0.1
pydub >= 0.25
librosa >= 0.10
moviepy >= 1.0
```
