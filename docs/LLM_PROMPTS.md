# LLM Prompt 设计

## 提示词文件

所有 prompt 模板在 `app/prompts/` 目录：

| 文件 | 用途 | 调用方 |
|------|------|--------|
| `analyze.txt` | 内容分析（主题/情绪/密度） | AnalysisAgent |
| `clip_select.txt` | 切片选择（钩子+评分） | ClipSelectAgent |
| `script_trim.txt` | 文稿裁剪（keep/remove） | ScriptTrimAgent |
| `title_gen.txt` | 标题生成 | TitleAgent |
| `sfx_plan.txt` | 音效规划（L3 层） | AudioAgent |
| `visual_prompt.txt` | 视觉风格提示 | (预留) |

## 设计原则

### 1. 结构化输出

所有 prompt 要求返回**严格 JSON**，通过 `LLMService.chat_json()` 解析：

```python
result = llm.chat_json(system_prompt, user_prompt)
# 自动 json.loads，失败会抛异常
```

### 2. 时间戳约束

涉及时间戳的 prompt 都强调：
- 时间必须来自原文 ASR 结果
- 不能编造时间
- 钩子时间必须在候选片段范围内

### 3. 完整性优先（v4+）

切片选择不再设固定时长限制，改为：
- 围绕金句扩展为完整论点
- 必须包含"问题→分析→结论"结构
- 时长由内容完整度决定

### 4. 钩子质量

钩子要求：
- 4-8 秒完整语句
- 有吸引力（反差/悬念/数字/痛点/冲突）
- 来自原文，不能改写

## DeepSeek 非确定性

同一个视频，每次分析可能返回不同的候选片段。这是 LLM 的特性，不是 bug。

应对策略：
- 用户指定话题时，固定源片段范围
- 多候选回退：第一个候选失败时自动尝试下一个
- `clip_select_agent.py` 对 LLM 返回做校验和评分
