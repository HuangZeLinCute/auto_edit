# AutoEdit - API 规范

## 基础信息

- Base URL: `http://localhost:8000/api/v1`
- Content-Type: `application/json`
- 认证：Bearer Token（后期添加）

---

## 1. 上传视频

```
POST /upload
Content-Type: multipart/form-data
```

**请求参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| file | file | 是 | 视频文件（mp4/mov/avi/mkv） |
| platform | string | 否 | 目标平台（douyin/xiaohongshu/shipinhao/bilibili），默认 douyin |
| style | string | 否 | 视觉风格预设，默认 business_tech |
| target_duration | int | 否 | 目标时长（秒），默认 90 |

**响应：**

```json
{
  "project_id": "proj_20260610_abc123",
  "status": "uploaded",
  "file_info": {
    "filename": "live_recording.mp4",
    "duration": 1800,
    "size_mb": 450,
    "format": "mp4"
  }
}
```

---

## 2. 启动切片任务

```
POST /task/{project_id}/start
```

**响应：**

```json
{
  "project_id": "proj_20260610_abc123",
  "task_id": "task_001",
  "status": "processing",
  "estimated_time_seconds": 720
}
```

---

## 3. 查询任务状态

```
GET /task/{project_id}/status
```

**响应：**

```json
{
  "project_id": "proj_20260610_abc123",
  "task_id": "task_001",
  "status": "processing",
  "current_step": "generate_visuals",
  "progress": 0.65,
  "steps": [
    {"name": "preprocess", "status": "completed", "duration_s": 12},
    {"name": "asr", "status": "completed", "duration_s": 180},
    {"name": "analyze", "status": "completed", "duration_s": 30},
    {"name": "select_clip", "status": "completed", "duration_s": 15},
    {"name": "trim_script", "status": "completed", "duration_s": 20},
    {"name": "generate_visuals", "status": "in_progress", "duration_s": null},
    {"name": "generate_subtitles", "status": "pending", "duration_s": null},
    {"name": "plan_audio", "status": "pending", "duration_s": null},
    {"name": "render", "status": "pending", "duration_s": null},
    {"name": "generate_titles", "status": "pending", "duration_s": null}
  ],
  "error": null
}
```

**status 枚举值：**

| 值 | 说明 |
|------|------|
| uploaded | 已上传 |
| processing | 处理中 |
| preview_ready | 预览就绪（候选切片已生成） |
| rendering | 渲染中 |
| completed | 已完成 |
| failed | 失败 |

---

## 4. 获取候选切片预览

```
GET /task/{project_id}/preview
```

当任务状态为 `preview_ready` 时可调用。

**响应：**

```json
{
  "project_id": "proj_20260610_abc123",
  "candidates": [
    {
      "clip_id": "clip_001",
      "topic": "直播切片的核心不是剪辑，而是选内容",
      "duration": 86,
      "score": 9.1,
      "hook_text": "你以为爆款是剪出来的，其实爆款是选出来的。",
      "reason": "观点清晰，有反差，有金句",
      "edited_script_preview": "你以为爆款是剪出来的，其实爆款是选出来的。很多人做直播切片...",
      "recommended": true
    },
    {
      "clip_id": "clip_002",
      "topic": "AI 剪辑工具的正确用法",
      "duration": 72,
      "score": 8.3,
      "hook_text": "99%的人用AI剪辑工具都用错了。",
      "reason": "数字钩子强，方法论清晰",
      "edited_script_preview": "99%的人用AI剪辑工具都用错了。正确的做法是...",
      "recommended": false
    }
  ]
}
```

---

## 5. 选择切片并渲染

```
POST /task/{project_id}/render
```

**请求参数：**

```json
{
  "clip_id": "clip_001",
  "style": "business_tech",
  "platform": "douyin",
  "target_duration": 90
}
```

**响应：**

```json
{
  "project_id": "proj_20260610_abc123",
  "clip_id": "clip_001",
  "status": "rendering",
  "estimated_time_seconds": 300
}
```

---

## 6. 获取渲染结果

```
GET /task/{project_id}/result/{clip_id}
```

**响应：**

```json
{
  "project_id": "proj_20260610_abc123",
  "clip_id": "clip_001",
  "status": "completed",
  "video": {
    "url": "/storage/outputs/proj_20260610_abc123/clip_001/final.mp4",
    "duration": 86.4,
    "resolution": "1080x1920",
    "file_size_mb": 32
  },
  "titles": {
    "contrast": ["你以为爆款靠剪辑，其实靠这一步"],
    "pain_point": ["为什么你剪了100条视频还是不爆？"],
    "knowledge": ["短视频切片的本质，不是剪辑，而是筛选"]
  },
  "cover_texts": ["爆款不是剪出来的", "直播切片真正核心"],
  "topics": ["#直播切片", "#AI剪辑", "#短视频运营"],
  "descriptions": ["一条高质量直播切片的完整制作流程分享"]
}
```

---

## 7. 下载文件

```
GET /download/{project_id}/{clip_id}/{filename}
```

**支持下载的文件：**

| 文件 | 说明 |
|------|------|
| final.mp4 | 最终视频 |
| subtitles.ass | 字幕文件 |
| edit_decision.json | 剪辑决策 |
| render_plan.json | 渲染计划 |
| output_package.json | 完整输出包 |

---

## 8. 重新生成

```
POST /task/{project_id}/regenerate/{clip_id}
```

**请求参数：**

```json
{
  "type": "titles|visuals|subtitles|sfx|all",
  "style": "business_tech",
  "custom_instructions": "标题要更口语化"
}
```

---

## 9. 健康检查

```
GET /health
```

**响应：**

```json
{
  "status": "healthy",
  "version": "0.1.0",
  "services": {
    "redis": "connected",
    "postgresql": "connected",
    "ffmpeg": "available",
    "whisper": "loaded",
    "llm": "connected"
  }
}
```

---

## WebSocket 实时进度（可选）

```
WS /ws/task/{project_id}/progress
```

**推送消息格式：**

```json
{
  "type": "step_update",
  "step": "generate_visuals",
  "status": "in_progress",
  "progress": 0.65,
  "message": "正在生成第 12/18 张图片"
}
```
