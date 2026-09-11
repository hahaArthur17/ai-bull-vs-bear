# WP8L 当前进度与剩余路线

复核日期：2026-09-12。已提交功能代码基线：`901cddb`。Live Queue 验证器、托管 interruption/Queue 修复、真实 provider 节流、Turn/Judge Prompt 上限及下一请求历史论点边界均已提交；本文已同步对应验证证据与剩余路线。
本文汇总当前执行顺序；详细验收仍以 Phase 8 remediation、UI acceptance matrix 和 verification record 为准。历史 checkpoint 描述的是当时状态，不代表当前待办。

## 当前位置

当前处于 **Phase 8 / WP8L.5 托管停止与插话已验证、完整真实模型联合运行收口前**。停止、恢复、插话、Continue、不完整前缀 Explanation、托管 PostgREST/Queue 和当前数据预检已经完成；完整两轮真实模型运行仍缺最终一次成功记录，之后才进入 Expo Go 产品负责人验收。

| 工作包 | 已有证据 | 尚未完成 |
| --- | --- | --- |
| WP8L.1 数据口径 | 最新 Finnhub 报价与完成日线分开冻结；行情、新闻/公告、SEC 财务事实、七项宏观输入有准入检查 | 权威交易日/提前收市日历；宏观发布时差与节假日边界；财务覆盖不等于完整报表 |
| WP8L.2 数据预检 | 2026-09-11 当前 AAPL 预检通过：115 条完成日线至 09-10、63 条周线、13 条新闻、4 份 filing、155 项财务事实、7 项宏观；Finnhub 当前 quote 读取成功 | 最终验收若跨日期，只重新检查并刷新到期来源；历史 capture 不是永久“最新”证明 |
| WP8L.3 Queue 与真实模型 | 当前 SHA Queue 202、真实 Groq Bull/Bear、durable SSE、引用和账本已联合运行；61 秒免费档节流曾完成六个 Round 1 Turn。已修复引用遗漏、8K TPM 节流、Turn/Judge 请求大小及 334→300 字符历史论点投影冲突；失败态 verifier 也会回读真实账本 | 后续 quota window 只运行一次修复后完整两轮：12 attempts、Interim/Final Judge、重载和分角色用量必须同时通过 |
| WP8L.4 显示调度 | 英文按词、中文按字素、单一活动气泡；生成完成不强制全文展开；有自动化测试 | 真机流畅度、屏幕阅读器实际播报、后台/重连及与 Stop 的联合体验 |
| WP8L.5 停止与插话 | provider-attempt 审计、首字前/中途停止、恢复、插话、Continue/End、冻结快照、稳定重试键和不完整前缀 Explanation 已提交；托管迁移、PostgREST/Queue、重启恢复、所有权、幂等和清理验证通过 | 弱网、原生强退/重开、各角色联合流程和 Expo Go 体验验收 |
| WP8L.6–7 | 单 API/Worker/SSE 进程的首轮验收边界已确定 | 专门测试账号的 Expo Go 联合验收；重启、拓扑与发布证据 |
| WP9 / WP10 | 验收要求已规划 | 产品负责人完成 Expo Go 视觉/交互验收；现有 Render 后端同 SHA 发布检查与回滚复核。不创建独立 staging，不要求测试或发布静态 Web 前端 |
| Phase 9 | 保留在后续路线中 | Replay、可观测性、韧性/负载、最终发布证明与演示材料 |

最近复核：提交 `901cddb` 后端 **516** 项通过；移动端 **111** 项与 TypeScript 当前复跑通过。隔离 PostgreSQL migration/replay、托管 Supabase interruption/Queue、启用 interruption flag 的 Web export 及 bounded checkpoint batching 均通过。这些仍不能替代完整两轮真实模型记录或 Expo Go 实机验收。

## 下一步执行顺序

### 1. 已完成：停止状态和数据库契约（WP8L.5a）

- `69368de` 已提交 provider-attempt ledger、Stop 与下一请求的原子 admission、首字前空 anchor、Continue/End 竞争和正式迁移；已报告 Token 保留，未报告用量保持 unknown。
- 隔离 PostgreSQL 与托管 Supabase 均已验证重复迁移、RPC、RLS/两用户隔离、外键、前缀、幂等、checkpoint 清理、Worker 崩溃与 retry draft 清理。应用冲突码已从会触发 PostgREST 重试的 `40001` 改为 `PT409`，Continue Queue 权限已收紧并通过托管验证。
- 托管逐 delta checkpoint 的 p95 约 309 ms；`2abdec6` 已改为最多 240 字符或 12 个 provider chunk 的 durable batch，并保持“先持久化累计前缀、后发 SSE”的顺序。
- `38495e3` 增加 `DEBATE_JOB_MAX_ATTEMPTS`；真实限额验收必须设为 1，以防 Worker 重试越过 12 次名义调用预算。

完成证据：真实 PostgreSQL 事务测试、可重现的并发边界测试、数据库写入预算和延迟记录。迁移与功能启用是分开的步骤。

### 2. 自动化/托管完成，待实机：停止边界与恢复（WP8L.5b）

- queued、`turn.started` 后但首个 delta 前、空前缀及已有 provider 内容但尚未显示文字的客户端路径已实现并测试；Judge 和完成早于显示的完整联合流程仍需托管/实机验收。
- 未确认 Stop 的账号/会话级本地持久恢复、前台重连和远端确认重载已提交；网络超时、History 重载及原生 App 强制退出/重开的实机证据仍待补齐。
- 停止确认前不自动恢复显示、不自动 Continue；错误明确区分“本地已冻结”和“服务器已确认”。测试重复点击、两个客户端和终止与继续的冲突。
- 客户端点击只保证本机立即冻结；服务器接受中断后禁止旧 generation 的新 admission。网络传输期间或此前已发出的请求可能已经消费 Token，需尽力取消并照实计量。
- 若必须保证“上一角色尚未显示完，下一角色连模型请求都不发”，需增加显示完成确认/背压协议及失联超时策略。当前单气泡显示调度不具备该保证；实现前不能把它写成已完成行为。

完成证据：自动化恢复测试、弱网/重开验证和可见前缀逐字一致性。

### 3. 自动化/托管完成，待实机：插话和明确继续（WP8L.5c）

`69368de`、`2478804` 与后续托管修复已提交 API、repository、SQL、移动端输入框和状态机。插话与 Continue 使用 Stop 返回的等待 generation；Continue 原子创建新 generation/job。保存观点不调用模型，End 不要求先保存观点，Continue 要求已保存观点。`46b4a73` 已补齐冻结不完整前缀的只读 Explanation。

- 停止确认后显示输入框，分别提供提问/表达观点、只读解释、结束、明确继续。输入或提交观点本身不触发模型。
- 中断点 Explanation 使用冻结前缀和服务端边界，保持只读且不把不完整内容提升为证据；仍需 Expo Go 验收交互与辅助技术表现。
- 持久化 interjection、所有者、目标中断点和幂等键。用户观点属于用户上下文，不能提升为已验证市场证据。
- 明确从 Bull、Bear、Interim Judge、Final Judge 中断后的恢复位置、剩余角色顺序和有限轮次；空观点是否允许 Continue 也须在契约中定死。
- Continue 原子创建新 generation 与唯一 Queue job，使用最后完整消息前缀、显式标记的不完整内容及用户插话。保持原冻结市场快照；若已超出继续的有效期，要求创建带新快照的新会话，不能静默替换旧输入。
- 取消/结束优先于竞争中的 Continue；旧 Worker 不得修改新 generation；消息、引用、任务和费用不得重复。

完成证据：各中断位置的完整状态机测试和无隐式模型调用验证。

### 4. 重做实时数据预检和小额端到端检测（WP8L.1–3 收口）

`583610c` 已支持仅刷新过期宏观系列；`38495e3` 可关闭 Worker 重试；`cf8b9e7` 在 `/health` 暴露显式 build SHA。`63406d4` 提交了当前 SHA Live Queue 验证器。2026-09-11 当前数据和模型目录预检通过；四个有界 Session 依次暴露并修复 SSE 所有权/事务重放、Turn 引用遗漏、Groq 8K TPM 节流和过大的 Judge Prompt。最后一个 Session 在 61 秒节流下完成全部六个 Round 1 Turn 与有效引用，但旧 Judge Prompt 在输出前被拒绝。`399e6fe` 已将同一输入的 Judge Prompt 离线缩小 68.5%；`7f6a4da` 又将同一托管 Session 的 Round 2 开场 Turn 从 24,954 缩到 12,813 字符、十二消息后期投影从 31,127 缩到 16,289 字符，均未再次消耗模型额度。

2026-09-12 的新 SHA Session `820646d0-cb0f-5a2f-8e24-c3ca9529175b`
完成五个 paced Round 1 Turn 后，在第六次 provider admission 前因历史
`rebuttal_point` 334 字符超过 request item 的 300 字符上限而安全失败。
账本为 5 次 dispatch/completion、13,366 reported Tokens、0 unknown usage、
0 retry。`19b9d85` 修复投影边界；`901cddb` 修复 verifier 在失败终态低报
请求数的问题。该 Session 不是 Round 1 通过记录，本窗口不重复模型调用。

- 先读缓存与调用记录，只补过期/不足数据。用户已授权限额刷新和微小模型检测，不必每次重复请求同一授权。
- 补交易日历、提前收盘、跨时区/宏观发布日期测试；统一七项宏观的固定年龄阈值需要源级规则复核，避免休市日误挡或把旧数据当新数据。
- 每个来源记录当天已知请求数、预计请求数和允许上限。无法确认剩余额度时先用缓存/离线检查，不凭本次调用次数推断整个账号剩余额度。
- 后续 quota window 只做一次标准 AAPL 联合运行：单进程、`max_attempts=1`、`DEBATE_PROVIDER_MIN_INTERVAL_SECONDS=61`，并要求 Queue 202、两轮 Bull/Bear、Interim/Final Judge、引用、重载和 provider ledger 全部通过。不要再用未节流、未压缩 Prompt 或未修复历史论点边界的旧 SHA；最低基线为 `901cddb`。
- 分开记录 Bull、Bear、Judge、Explanation 的模型与请求/Token；失败也计入请求数，未知 Token 单独标记。历史 Judge 的 612 Token 仅属于那次成功请求，不包含此前两次未知用量的失败。

完成证据：当前 SHA、当前 capture 时间与预算下的验证记录；不把历史单项检测拼成一次并未发生的完整验收。

### 5. Expo Go 和跨状态验收（WP8L.6、WP8 与 WP9）

- 专门测试账号、standard 模式，单进程单实例 API/Worker/SSE，无热重载；核对手机网络、登录和 API 地址。
- 验证真实数据标签、冻结快照、Queue 等待、各角色渐进输出、Stop、插话、Continue、结束、重连、后台、重开 History 和费用。
- 补齐 Web 四宽度、200% 缩放、键盘、降低动态效果、屏幕阅读器、原生键盘/焦点、iOS/Android 与至少一台物理设备的缺失证据。缺设备明确记录，不以浏览器模拟替代。
- 用户以实际界面验收视觉层级、图表可读性、Judge 结论及异常恢复；反馈转为小步修复并重新验证。

### 6. 现有 Render 后端发布与回滚（WP8L.7、WP10）

- 不创建独立 staging，不测试或发布静态 Web 前端。Expo Go 客户端从待验收提交运行，现有 Render API 部署同一提交，并以 `/health.build_sha` 核对实际后端版本。
- 核对 Auth/CORS、数据来源、迁移兼容性、冷启动、SSE/重启和限定 Live 路径；使用专门测试账号，避免把验收会话与普通数据混在一起。
- 写出迁移与应用版本先后关系，以及关闭 V2/Queue/live provider/Stop 的回滚顺序；优先保留审计数据的兼容回滚，不以删除会话数据作为回滚。
- 现有 Render API 保持单进程。若以后拆分 Worker 或扩容 API，另行实现共享事件传递、游标/重放、重复/过期事件与跨进程中断测试。当前 draft checkpoint RPC 不能自动把 Worker 的 delta 送到 API。
- 记录部署前 SHA、目标 SHA、健康检查、关键接口 smoke、冷启动/重启结果和可恢复的旧版本。独立 staging 与静态 Web 前端不再是 Phase 8/9 完成门槛。

### 7. Phase 9：可靠演示和最终交付

Phase 8 完成后：采集并脱敏一个带版本的真实 Debate fixture；通过共享事件协议实现明确标记的 Replay；增加安全日志及 job/cache 指标；运行不调用真实模型的有界压力测试，测量 Queue 背压和 Redis 缓存；补全 RLS/重启/CORS/发布检查；更新架构、API、安装与里程碑报告；准备课堂演示脚本及与证据一致的项目描述。

旧 backlog 中 clone-prefix 分支、任意 Web 文本选择仍是后续增强，不能与当前 Stop/插话必须实现的能力混淆。多股票扩展和多实例生产架构也不由本轮 AAPL 验收自动证明。

## 提交与协作

每个可独立验证的小步单独 commit，并在 verification record 记录测试和限制。Root 统一审阅所有共享工作区改动。本轮用户要求所有子 Agent 固定使用 `gpt-5.6-luna` 和 `xhigh`（Extra High）；只有文件范围、数据库状态与外部调用互不冲突的任务才并行，存在顺序依赖时保持串行。如果子 Agent 配额不可用，由 Root 继续，不把代理配额与应用 Groq 用量混为一谈。

本轮已获授权在已有每日免费额度和仓库 hard cap 内直接访问模型 API 与股票/市场数据，不再重复询问。每次真实调用前仍先读缓存、当天已知调用记录和目标预算；只刷新过期或不足来源，失败请求也计数，未知 Token 单独记录，任何日志和提交均不得包含密钥、访问令牌或生成全文。

除产品负责人必须完成的 Expo Go 实机/界面验收外，Root 应先更换方法完成自动化排查。若同一阻塞在 2–3 次有实质差异的尝试后仍无法推进，并且确实需要用户操作，则停止该路径，说明已验证事实、未完成影响和用户需要执行的精确步骤。开发中发现 material incident 时，先查 `issue-log.md` 是否已有记录；没有则按其症状、证据、缓解、验证和 owner 格式追加，子 Agent 的发现仍由 Root 审核后入库。
