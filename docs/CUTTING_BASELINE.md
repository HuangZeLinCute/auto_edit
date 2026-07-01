# 切口对齐基准（v5）

## 问题背景

LLM 给的时间戳是句子级理解，不精确到词边界。如果直接用 `source_start/source_end` 下刀，会出现两类问题：

### 1. 向前溢出

起点早于 ASR 词起点，把上一段的尾音（如"呃"）吸进来。

**示例**：LLM 给的起点是 62.41s，但 ASR 标注的第一个词在 62.58s 开始，中间 0.17s 是上个被删段的"呃"尾音。

### 2. 跨词截断

起点落在一个词的中间，把词切成两半。

**示例**：LLM 给的起点是 65.53s，但 65.18-65.72s 说话人在说"特别"，起点落在了词中间。

## v5 基准方法

### `_snap_to_word_boundary()`

```
输入: target_time, kind(start/end), word_boundaries, window=0.30s
输出: 对齐后的时间戳
```

**处理逻辑**：

1. 从 transcript 提取所有 ASR word 的 `(start, end)` 边界
2. **start 类**：在 ±0.3s 窗口内找 word.start，取**最大的**（最晚的），再 -0.05s 前置静音
3. **end 类**：在 ±0.3s 窗口内找 word.end，取**最小的**（最早的），再 +0.05s 后置余量
4. 窗口内无候选时，扩大到 ±0.6s 搜索
5. 仍无则回退到 `_snap_to_low_energy`
6. 最后加 PAD=0.15s 安全边距

### `_check_remove_overlap()`

LLM 标记的 `remove_segments` 可能与 `keep_segments` 时间重叠。

```
检测: remove 段与 keep 段重叠 > 0.1s
动作: 放弃该删除，把时间范围合并回相邻 keep 段
后续: 重新合并相邻/重叠的 keep 段
```

## 验证结果

| 版本 | 问题 | 结果 |
|------|------|------|
| v4 | keep_00 开头截进"呃"声 | ❌ |
| v4 | keep_01 截进"特别"半句 | ❌ |
| v5 | 所有切口干净 | ✅ 用户确认 |

## 相关代码

- `app/agents/script_trim_agent.py`
  - `_extract_word_boundaries()` — 提取词边界
  - `_snap_to_word_boundary()` — 词边界对齐
  - `_check_remove_overlap()` — 删除段重叠校验
  - `_build_edited_media()` — 调用上述方法
