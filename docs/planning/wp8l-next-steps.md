# WP8L 当前进度与剩余路线

复核日期：2026-09-11。已提交代码基线：`cf8b9e7`。当前按用户要求暂停；未提交工作区仅保留 Live Queue 验证器及其测试，review 尚未完成。
本文汇总当前执行顺序；详细验收仍以 Phase 8 remediation、UI acceptance matrix 和 verification record 为准。历史 checkpoint 描述的是当时状态，不代表当前待办。

## 当前位置

当前处于 **Phase 8 / WP8L.5 核心停止与插话路径已本地整合、托管与实机验收前**；不完整前缀 Explanation 仍未实现，因此 WP8L.5 和 Phase 8 都尚未完成。

| 工作包 | 已有证据 | 尚未完成 |
| --- | --- | --- |
| WP8L.1 数据口径 | 最新 Finnhub 报价与完成日线分开冻结；行情、新闻/公告、SEC 财务事实、七项宏观输入有准入检查 | 权威交易日/提前收市日历；宏观发布时差与节假日边界；财务覆盖不等于完整报表 |
| WP8L.2 数据预检 | 一次标准 AAPL capture：100 条日线、2 份合格证据、7 项宏观，离线一致性检查通过；有界新闻/宏观刷新与报价读取已有记录 | 正式验收前按当时日期重新检查，仅刷新过期来源；历史 capture 不是永久“最新”证明 |
| WP8L.3 Queue 与真实模型 | Queue/流式 Bull/Bear 有历史验证；独立流式 Interim/Final Judge 已实现，合成输入的小型 Groq Judge 检测通过 | 当前 SHA、同一真实 AAPL 快照的 Queue 202、两轮及两次 Judge、重载与分角色用量联合验证 |
| WP8L.4 显示调度 | 英文按词、中文按字素、单一活动气泡；生成完成不强制全文展开；有自动化测试 | 真机流畅度、屏幕阅读器实际播报、后台/重连及与 Stop 的联合体验 |
| WP8L.5 停止与插话 | provider-attempt 审计、下一请求原子准入、首字前停止、恢复、插话、明确 Continue/End、冻结快照和稳定重试键均已实现并提交；默认关闭；本地 PostgreSQL 与延迟基准通过 | 托管迁移/PostgREST/Queue、弱网与原生重开、各角色联合流程、不完整前缀 Explanation 和 Expo Go 验收 |
| WP8L.6–7 | 单 API/Worker/SSE 进程的首轮验收边界已确定 | 专门测试账号的 Expo Go 联合验收；重启、拓扑与发布证据 |
| WP9 / WP10 | 验收要求已规划 | 产品负责人视觉/交互验收；同 SHA staging、回滚及 staging 复核 |
| Phase 9 | 保留在后续路线中 | Replay、可观测性、韧性/负载、最终发布证明与演示材料 |

暂停前复核：已提交代码在排除未提交 Live verifier 测试时，后端 **480** 项通过；移动端 **111** 项与 TypeScript 通过。隔离 PostgreSQL migration/replay、启用 interruption flag 的 Web export 及 120 次 checkpoint 延迟预算均通过。这些仍不能替代托管环境或 Expo Go 实机验收。

## 下一步执行顺序

### 1. 先补齐停止的状态和数据库契约（WP8L.5a）

- `69368de` 已提交 provider-attempt ledger、Stop 与下一请求的原子 admission、首字前空 anchor、Continue/End 竞争和正式迁移；已报告 Token 保留，未报告用量保持 unknown。
- 隔离 PostgreSQL 已验证重复迁移、RPC、RLS/两用户隔离、外键、前缀、幂等、checkpoint 清理、Worker 崩溃与 retry draft 清理。下一步是在托管 Supabase 应用并验证 PostgREST/Queue 行为。
- `eba8b33` 的 120 次本地 checkpoint 基准为每 delta 一次写入，暂停前复跑 p95 0.122 ms、最大 1.954 ms。仍需测量托管网络延迟，再决定是否批量持久化。
- `38495e3` 增加 `DEBATE_JOB_MAX_ATTEMPTS`；真实限额验收必须设为 1，以防 Worker 重试越过 12 次名义调用预算。

完成证据：真实 PostgreSQL 事务测试、可重现的并发边界测试、数据库写入预算和延迟记录。迁移与功能启用是分开的步骤。

### 2. 补齐停止的边界与恢复（WP8L.5b）

- queued、`turn.started` 后但首个 delta 前、空前缀及已有 provider 内容但尚未显示文字的客户端路径已实现并测试；Judge 和完成早于显示的完整联合流程仍需托管/实机验收。
- 未确认 Stop 的账号/会话级本地持久恢复、前台重连和远端确认重载已提交；网络超时、History 重载及原生 App 强制退出/重开的实机证据仍待补齐。
- 停止确认前不自动恢复显示、不自动 Continue；错误明确区分“本地已冻结”和“服务器已确认”。测试重复点击、两个客户端和终止与继续的冲突。
- 客户端点击只保证本机立即冻结；服务器接受中断后禁止旧 generation 的新 admission。网络传输期间或此前已发出的请求可能已经消费 Token，需尽力取消并照实计量。
- 若必须保证“上一角色尚未显示完，下一角色连模型请求都不发”，需增加显示完成确认/背压协议及失联超时策略。当前单气泡显示调度不具备该保证；实现前不能把它写成已完成行为。

完成证据：自动化恢复测试、弱网/重开验证和可见前缀逐字一致性。

### 3. 接入插话和明确继续（WP8L.5c）

`69368de` 与 `2478804` 已提交 API、repository、SQL、移动端输入框和状态机。插话与 Continue 使用 Stop 返回的等待 generation；Continue 原子创建新 generation/job。保存观点不调用模型，End 不要求先保存观点，Continue 要求已保存观点。

- 停止确认后显示输入框，分别提供提问/表达观点、只读解释、结束、明确继续。输入或提交观点本身不触发模型。
- 定义中断点的解释请求契约仍未完成：现有 Explanation 只接受完整消息中的精确词语，不能直接复用于不完整前缀。
- 持久化 interjection、所有者、目标中断点和幂等键。用户观点属于用户上下文，不能提升为已验证市场证据。
- 明确从 Bull、Bear、Interim Judge、Final Judge 中断后的恢复位置、剩余角色顺序和有限轮次；空观点是否允许 Continue 也须在契约中定死。
- Continue 原子创建新 generation 与唯一 Queue job，使用最后完整消息前缀、显式标记的不完整内容及用户插话。保持原冻结市场快照；若已超出继续的有效期，要求创建带新快照的新会话，不能静默替换旧输入。
- 取消/结束优先于竞争中的 Continue；旧 Worker 不得修改新 generation；消息、引用、任务和费用不得重复。

完成证据：各中断位置的完整状态机测试和无隐式模型调用验证。

### 4. 重做实时数据预检和小额端到端检测（WP8L.1–3 收口）

暂停点：`583610c` 已支持仅刷新过期宏观系列；`38495e3` 可关闭 Worker 重试；`cf8b9e7` 在 `/health` 暴露显式 build SHA。`scripts/verify_current_sha_live_queue.py` 及其测试仍未提交，独立 review 被本次暂停中断，恢复工作时必须先复核再运行任何真实模型请求。

- 先读缓存与调用记录，只补过期/不足数据。用户已授权限额刷新和微小模型检测，不必每次重复请求同一授权。
- 补交易日历、提前收盘、跨时区/宏观发布日期测试；统一七项宏观的固定年龄阈值需要源级规则复核，避免休市日误挡或把旧数据当新数据。
- 每个来源记录当天已知请求数、预计请求数和允许上限。无法确认剩余额度时先用缓存/离线检查，不凭本次调用次数推断整个账号剩余额度。
- 当前版本先做离线/模拟故障，继而一次有明确预算的标准 AAPL 联合运行：Queue 202、两轮 Bull/Bear、Interim/Final Judge、引用、重载、重试与中断。
- 分开记录 Bull、Bear、Judge、Explanation 的模型与请求/Token；失败也计入请求数，未知 Token 单独标记。历史 Judge 的 612 Token 仅属于那次成功请求，不包含此前两次未知用量的失败。

完成证据：当前 SHA、当前 capture 时间与预算下的验证记录；不把历史单项检测拼成一次并未发生的完整验收。

### 5. Expo Go 和跨状态验收（WP8L.6、WP8 与 WP9）

- 专门测试账号、standard 模式，单进程单实例 API/Worker/SSE，无热重载；核对手机网络、登录和 API 地址。
- 验证真实数据标签、冻结快照、Queue 等待、各角色渐进输出、Stop、插话、Continue、结束、重连、后台、重开 History 和费用。
- 补齐 Web 四宽度、200% 缩放、键盘、降低动态效果、屏幕阅读器、原生键盘/焦点、iOS/Android 与至少一台物理设备的缺失证据。缺设备明确记录，不以浏览器模拟替代。
- 用户以实际界面验收视觉层级、图表可读性、Judge 结论及异常恢复；反馈转为小步修复并重新验证。

### 6. 同 SHA staging 与回滚（WP8L.7、WP10）

- 前后端同一 SHA；核对版本、Auth/CORS、数据来源、迁移兼容性、冷启动、SSE/重启和限定 Live 路径。
- 写出迁移与应用版本先后关系，以及关闭 V2/Queue/live provider/Stop 的回滚顺序；优先保留审计数据的兼容回滚，不以删除会话数据作为回滚。
- 单进程可以用于首轮 staging。若以后拆分 Worker 或扩容 API，另行实现共享事件传递、游标/重放、重复/过期事件与跨进程中断测试。当前 draft checkpoint RPC 不能自动把 Worker 的 delta 送到 API。
- staging 验收后才考虑公开演示/生产更新，并保留单独的公开发布授权边界。

### 7. Phase 9：可靠演示和最终交付

Phase 8 完成后：采集并脱敏一个带版本的真实 Debate fixture；通过共享事件协议实现明确标记的 Replay；增加安全日志及 job/cache 指标；运行不调用真实模型的有界压力测试，测量 Queue 背压和 Redis 缓存；补全 RLS/重启/CORS/发布检查；更新架构、API、安装与里程碑报告；准备课堂演示脚本及与证据一致的项目描述。

旧 backlog 中 clone-prefix 分支、任意 Web 文本选择仍是后续增强，不能与当前 Stop/插话必须实现的能力混淆。多股票扩展和多实例生产架构也不由本轮 AAPL 验收自动证明。

## 提交与协作

每个可独立验证的小步单独 commit，并在 verification record 记录测试和限制。Sol 适合事务/状态机，Terra 适合客户端交互，Luna 适合确定性检查与证据整理；Root 统一审阅。如果子 Agent 配额不可用，由 Root 继续，不把代理配额与应用 Groq 用量混为一谈。
