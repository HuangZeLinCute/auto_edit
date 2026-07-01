# AutoEdit - 数据结构设计

## 核心数据实体

所有 Agent 围绕以下数据结构协作，每个结构对应一个 JSON Schema。

---

## 1. Transcript（ASR 输出）

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "Transcript",
  "type": "object",
  "required": ["project_id", "language", "duration", "segments"],
  "properties": {
    "project_id": {"type": "string"},
    "language": {"type": "string", "enum": ["zh", "en", "mixed"]},
    "duration": {"type": "number", "description": "音频总时长（秒）"},
    "segments": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["id", "start", "end", "text", "words"],
        "properties": {
          "id": {"type": "integer"},
          "start": {"type": "number"},
          "end": {"type": "number"},
          "text": {"type": "string"},
          "words": {
            "type": "array",
            "items": {
              "type": "object",
              "required": ["word", "start", "end"],
              "properties": {
                "word": {"type": "string"},
                "start": {"type": "number"},
                "end": {"type": "number"},
                "score": {"type": "number", "minimum": 0, "maximum": 1}
              }
            }
          }
        }
      }
    },
    "filler_words": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "word": {"type": "string"},
          "start": {"type": "number"},
          "end": {"type": "number"},
          "segment_id": {"type": "integer"},
          "type": {"type": "string", "enum": ["filler", "repetition", "hesitation"]}
        }
      }
    },
    "silences": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "start": {"type": "number"},
          "end": {"type": "number"},
          "duration": {"type": "number"}
        }
      }
    },
    "risk_words": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "word": {"type": "string"},
          "start": {"type": "number"},
          "end": {"type": "number"},
          "segment_id": {"type": "integer"},
          "level": {"type": "string", "enum": ["low", "medium", "high"]}
        }
      }
    }
  }
}
```

---

## 2. AnalysisResult（内容分析结果）

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "AnalysisResult",
  "type": "object",
  "required": ["project_id", "chapters", "golden_sentences", "main_topics"],
  "properties": {
    "project_id": {"type": "string"},
    "main_topics": {
      "type": "array",
      "items": {"type": "string"}
    },
    "chapters": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["start", "end", "topic", "summary", "value_score"],
        "properties": {
          "start": {"type": "number"},
          "end": {"type": "number"},
          "topic": {"type": "string"},
          "summary": {"type": "string"},
          "value_score": {"type": "number", "minimum": 0, "maximum": 10},
          "sub_topics": {"type": "array", "items": {"type": "string"}}
        }
      }
    },
    "golden_sentences": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["start", "end", "text", "reason"],
        "properties": {
          "start": {"type": "number"},
          "end": {"type": "number"},
          "text": {"type": "string"},
          "reason": {"type": "string"},
          "hook_potential": {"type": "number", "minimum": 0, "maximum": 10}
        }
      }
    }
  }
}
```

---

## 3. ClipPlan（切片计划）

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "ClipPlan",
  "type": "object",
  "required": ["project_id", "candidates"],
  "properties": {
    "project_id": {"type": "string"},
    "candidates": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["clip_id", "topic", "source_start", "source_end", "duration", "score", "hook"],
        "properties": {
          "clip_id": {"type": "string"},
          "topic": {"type": "string"},
          "source_start": {"type": "number"},
          "source_end": {"type": "number"},
          "duration": {"type": "number"},
          "score": {"type": "number"},
          "reason": {"type": "string"},
          "hook": {
            "type": "object",
            "required": ["start", "end", "text"],
            "properties": {
              "start": {"type": "number"},
              "end": {"type": "number"},
              "text": {"type": "string"},
              "reason": {"type": "string"}
            }
          },
          "scores": {
            "type": "object",
            "properties": {
              "hook_score": {"type": "number"},
              "information_density": {"type": "number"},
              "completeness_score": {"type": "number"},
              "shareability_score": {"type": "number"},
              "emotion_score": {"type": "number"},
              "visualizable_score": {"type": "number"},
              "risk_score": {"type": "number"}
            }
          }
        }
      }
    }
  }
}
```

---

## 4. EditDecision（剪辑决策）

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "EditDecision",
  "type": "object",
  "required": ["project_id", "clip_id", "edited_script", "keep_segments", "remove_segments", "hook"],
  "properties": {
    "project_id": {"type": "string"},
    "clip_id": {"type": "string"},
    "edited_script": {"type": "string", "description": "裁剪后完整文案"},
    "target_duration": {"type": "number"},
    "hook": {
      "type": "object",
      "required": ["source_start", "source_end", "target_start", "target_end", "text"],
      "properties": {
        "source_start": {"type": "number"},
        "source_end": {"type": "number"},
        "target_start": {"type": "number"},
        "target_end": {"type": "number"},
        "text": {"type": "string"},
        "keep_original_video": {"type": "boolean"},
        "keep_original_audio": {"type": "boolean"}
      }
    },
    "keep_segments": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["source_start", "source_end", "text"],
        "properties": {
          "source_start": {"type": "number"},
          "source_end": {"type": "number"},
          "text": {"type": "string"},
          "target_start": {"type": "number"},
          "target_end": {"type": "number"}
        }
      }
    },
    "remove_segments": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["source_start", "source_end", "text", "reason"],
        "properties": {
          "source_start": {"type": "number"},
          "source_end": {"type": "number"},
          "text": {"type": "string"},
          "reason": {"type": "string", "enum": ["filler", "silence", "repetition", "off_topic", "risk_word", "low_value"]}
        }
      }
    },
    "mute_words": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "word": {"type": "string"},
          "start": {"type": "number"},
          "end": {"type": "number"},
          "action": {"type": "string", "enum": ["mute", "beep", "delete"]}
        }
      }
    }
  }
}
```

---

## 5. RenderPlan（渲染计划）

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "RenderPlan",
  "type": "object",
  "required": ["project_id", "output", "timeline", "subtitles", "sfx", "bgm"],
  "properties": {
    "project_id": {"type": "string"},
    "output": {
      "type": "object",
      "required": ["aspect_ratio", "resolution", "fps", "duration"],
      "properties": {
        "aspect_ratio": {"type": "string", "enum": ["9:16", "16:9", "1:1"]},
        "resolution": {"type": "string"},
        "fps": {"type": "integer"},
        "duration": {"type": "number"}
      }
    },
    "visual_style": {"type": "string"},
    "timeline": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["target_start", "target_end", "type"],
        "properties": {
          "target_start": {"type": "number"},
          "target_end": {"type": "number"},
          "type": {"type": "string", "enum": ["hook_original", "ai_image_with_audio", "text_card_with_audio"]},
          "source_start": {"type": "number"},
          "source_end": {"type": "number"},
          "text": {"type": "string"},
          "image_prompt": {"type": "string"},
          "image_path": {"type": "string"},
          "motion": {"type": "string", "enum": ["static", "slow_zoom_in", "slow_zoom_out", "pan_left", "pan_right", "ken_burns"]},
          "transition": {"type": "string"}
        }
      }
    },
    "subtitles": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["start", "end", "text"],
        "properties": {
          "start": {"type": "number"},
          "end": {"type": "number"},
          "text": {"type": "string"},
          "highlight_words": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "word": {"type": "string"},
                "type": {"type": "string"},
                "color": {"type": "string"},
                "effect": {"type": "string"}
              }
            }
          }
        }
      }
    },
    "sfx": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["time", "file"],
        "properties": {
          "time": {"type": "number"},
          "file": {"type": "string"},
          "volume_db": {"type": "number"},
          "reason": {"type": "string"}
        }
      }
    },
    "bgm": {
      "type": "object",
      "required": ["file", "volume_db"],
      "properties": {
        "file": {"type": "string"},
        "volume_db": {"type": "number"},
        "fade_in": {"type": "number"},
        "fade_out": {"type": "number"},
        "category": {"type": "string"}
      }
    }
  }
}
```

---

## 6. OutputPackage（最终输出）

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "OutputPackage",
  "type": "object",
  "required": ["project_id", "clip_id", "video", "titles", "topics"],
  "properties": {
    "project_id": {"type": "string"},
    "clip_id": {"type": "string"},
    "video": {
      "type": "object",
      "required": ["path", "duration", "resolution", "file_size"],
      "properties": {
        "path": {"type": "string"},
        "duration": {"type": "number"},
        "resolution": {"type": "string"},
        "file_size": {"type": "number"}
      }
    },
    "subtitle_path": {"type": "string"},
    "titles": {
      "type": "object",
      "properties": {
        "contrast": {"type": "array", "items": {"type": "string"}},
        "pain_point": {"type": "array", "items": {"type": "string"}},
        "result": {"type": "array", "items": {"type": "string"}},
        "knowledge": {"type": "array", "items": {"type": "string"}},
        "suspense": {"type": "array", "items": {"type": "string"}},
        "number": {"type": "array", "items": {"type": "string"}},
        "tutorial": {"type": "array", "items": {"type": "string"}},
        "controversy": {"type": "array", "items": {"type": "string"}}
      }
    },
    "cover_texts": {
      "type": "array",
      "items": {"type": "string"}
    },
    "topics": {
      "type": "array",
      "items": {"type": "string"}
    },
    "description": {
      "type": "array",
      "items": {"type": "string"}
    },
    "edit_decision_path": {"type": "string"},
    "render_plan_path": {"type": "string"}
  }
}
```

---

## 数据流转关系

```
Transcript  ->  AnalysisResult  ->  ClipPlan
                                        |
                                        v
                                   EditDecision
                                        |
                                        v
                                    RenderPlan
                                        |
                                        v
                                   OutputPackage
```

每个数据结构对应一个文件，保存在项目的 storage/ 目录下：

```
storage/
  {project_id}/
    transcript.json        # Transcript
    analysis.json          # AnalysisResult
    clip_plan.json         # ClipPlan
    edit_decision.json     # EditDecision
    render_plan.json       # RenderPlan
    output/
      output_package.json  # OutputPackage
      final.mp4
      subtitles.ass
```
