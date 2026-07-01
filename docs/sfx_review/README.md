# 音效库汇报表（知识分享类口播）

> 筛选范围：`assets/sfx/` 全部 20 个文件 + `sfx_old_cinematic/` 8 个
> 入库：13 个 | 排除：15 个（详见末尾）
> 音频文件：`docs/sfx_review/audio/`（13 个 wav，可直接试听）

## 入库音效（按类别分组）

| # | 文件 | 时长 | 类别 | 情绪标签 | 使用场景（推荐） | 强度 |
|---|------|-----:|------|---------|----------------|:----:|
| 1 | `pop_explainer.wav` | 0.18s | 强调 | 中性/专注 | 干货知识点轻点、方法罗列 | 低 |
| 2 | `pop_dry.wav` | 0.30s | 强调 | 中性/专注 | 数字强调（3倍/50%）、第一第二计数 | 低 |
| 3 | `pop_bubble.wav` | 0.38s | 轻松 | 轻松/趣味 | 举例「比如说」、幽默点缀 | 低 |
| 4 | `pop_long.wav` | 0.48s | 冲击 | 震撼/冲击 | 金句落点重击、震撼词（炸裂/颠覆） | 高 |
| 5 | `pop_hard_click.wav` | 1.17s | 强调 | 严肃/警示 | 警告「千万别」、踩坑风险点 | 中 |
| 6 | `ding_sparkle_hybrid.wav` | 1.25s | 顿悟 | 惊喜/灵感 | 灵感闪现、反常识观点亮出 | 中 |
| 7 | `ding_3.wav` | 1.40s | 提示 | 中性/专注 | 引出新信息、「注意，重点来了」 | 低 |
| 8 | `ding_uplifting_bells.wav` | 2.93s | 顿悟 | 顿悟/升华 | 核心结论、底层逻辑、最高潮 | 高 |
| 9 | `ding_sparkle.wav` | 7.01s | 顿悟 | 惊喜/灵感 | 递进段落氛围上升（备选 rise） | 中 |
| 10 | `click_check.wav` | 1.74s | 计数 | 肯定/成就 | 步骤完成打钩、「这就是正确答案」 | 低 |
| 11 | `whoosh_arrow.wav` | 3.44s | 转场 | 中性/专注 | 引出下一要点、配合箭头动效 | 中 |
| 12 | `whoosh_air.wav` | 5.02s | 转场 | 平静/舒缓 | 章节柔和过渡、知识模块切换 | 低 |
| 13 | `whoosh_fast.wav` | 5.24s | 转场 | 紧张/反转 | 「但是/然而」反转、钩子→正文快切 | 中 |

## 排除清单（不适合口播）

| 文件 | 时长 | 排除原因 |
|------|-----:|---------|
| `click_classic.wav` | 22s | loop 床音，非点状点击 |
| `click_select.wav` | 19s | loop 床音，非瞬时选中音 |
| `click_cool.wav` | 9s | 游戏/酷炫质感，调性不符 |
| `ding_doorbell.wav` | 4s | 门铃过于具象，易出戏 |
| `notif_bell.wav` | 22s | loop 床音（短提示请用 `ding_3`） |
| `whoosh_cinematic.wav` | 19s | 电影感长床 |
| `whoosh_swirl.wav` | 14s | 旋转长床，易喧宾夺主 |
| `sfx_old_cinematic/*` × 8 | — | 电影混剪风格整套，仅 L1 结构音效历史遗留 |

## 当前系统接入情况

- **已接入 5 个**：`pop_explainer` / `pop_dry` / `pop_long` / `ding_uplifting_bells` / `whoosh_fast`
- **储备待启用 8 个**：其余 8 个已分类但暂未配进 `subtitle_service.py` 的关键词规则

完整结构化索引见 `configs/sfx_library.yaml`。
