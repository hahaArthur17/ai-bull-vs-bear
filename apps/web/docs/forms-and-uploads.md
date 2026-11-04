# 用户反馈表单与附件设计

状态：规划，尚未实现。创建：2026-11-04；更新：2026-11-05（Pacific/Auckland）。

本功能用于让访客向网站开发者提交建议、问题和使用体验。它不是研究资料、用户注册或身份认证表单。用户填写后，未来真实后端应接收并保存反馈，供维护者在受限后台中查看；当前只有规划，现有后端尚无反馈或上传接口。

## 1. 用户入口与完整流程

入口位于用户页 `/user` 的较下方：用户向下滚动，看到“Help improve this app”反馈区和“Send feedback”按钮。该区安排在用户信息、偏好等主要内容之后，有简短用途说明；不使用遮住内容的悬浮按钮，不阻挡股票研究主流程。

点击按钮进入独立表单 `/feedback`。页面提供返回用户页的链接；返回时恢复到原反馈入口附近。支持直接访问反馈链接，首版不要求真实注册或登录。未来登录状态可以预填联络信息，但反馈入口不能依赖尚未实现的账户系统。

```text
/user 下方反馈区 → /feedback → 校验与提交
  ├── demo：演示编号，明确未发送给开发者
  ├── api：服务器确认的反馈编号与 received 状态
  └── disabled：说明尚未接通，禁止实际提交
```

Demo 表单持续显示“Demo mode: your feedback and files stay in this browser and are not sent to the developer.”。成功文案为“Demo submission complete”，不能写成“我们已收到反馈”。真实模式只有服务器确认接收后，才显示“Feedback received”。

## 2. 页面布局与视觉规范

与工作台共用 shadcn/ui 组件、颜色、字号、圆角、焦点和状态反馈规则。UI 文案首版使用英文，规划说明使用中文。

桌面采用主表单与窄说明栏。主区按“Your feedback → Attachments → Optional contact details → Submit”排列；反馈内容在前，姓名、邮箱和性别作为后面的可选联系信息，帮助访客先表达意见。侧栏解释用途、附件限制和当前提交模式。

平板/手机改成单列，提示靠近相关字段，提交按钮留在文档流中，不覆盖键盘。标题、描述和错误摘要占完整阅读宽度；可选联系字段在宽屏可并排。不要为每个字段单独套卡片。

首版使用单页分组，不做强制多步骤向导。提供“Fill sample feedback”；重置放在次级位置。有草稿时先确认覆盖。提交前显示简短摘要；成功区显示反馈编号、分类、附件数量和下一步，必要时遮蔽邮箱。

## 3. 字段与 shadcn/ui 控件

长度和必填设置为首版提议，统一保存在 schema 中。

| 字段 / 操作 | 首版规则 | 控件与反馈 |
| --- | --- | --- |
| 反馈类型 `category` | 必填：建议、Bug、使用体验、其他 | `Select`，配简短类型说明 |
| 标题 `title` | 必填；trim 后 5–100 字符 | `Input`，提供简短示例 |
| 详细内容 `description` | 必填；trim 后 20–3000 字符 | `Textarea`，显示字数与填写提示 |
| 相关页面 `relatedPage` | 可选；工作台、股票详情、辩论、历史、用户页或其他 | `Select`；只预填已知页面名称 |
| 体验评分 `experienceRating` | 可选；1–5，默认未选择 | `RadioGroup`，每项有文字等级，不只显示星形 |
| 复现步骤 `reproductionSteps` | Bug 时显示并必填；10–2000 字符 | 条件 `Textarea`，提示按步骤描述 |
| 预期结果 `expectedResult` | Bug 时显示，可选；最多 1000 字符 | `Textarea` |
| 实际结果 `actualResult` | Bug 时显示，可选；最多 1000 字符 | `Textarea` |
| 附件 `attachments` | 可选；PDF/PNG/JPEG，按下节限制 | 原生文件输入 + 选择区 + `Button`、`Progress`、`Badge` |
| 姓名 `fullName` | 可选；填写时 trim 后 1–80 字符；支持中文和其他文字 | `Field`、`Input`、`FieldDescription`、`FieldError` |
| 希望收到回复 `wantsReply` | 可选，默认 false | `Checkbox`，说明不会自动订阅或发送邮件 |
| 邮箱 `email` | 仅 `wantsReply=true` 时必填；否则可留空；填写时校验语法且不超过 254 字符 | `Input type="email"`，`autoComplete="email"` |
| 性别 `gender` | 可选，默认未选择；明确提供“不愿透露” | `Select` 或 `RadioGroup`，首版固定一种 |
| 填入示例 | 固定合成姓名、示例邮箱和反馈内容 | 次级 `Button`；有草稿时先确认覆盖 |
| 重置 | 清空字段、错误、文件和演示回执 | 次级 `Button`；dirty 时 `AlertDialog` 确认 |
| 提交 | 完整校验；提交期间防止重复操作 | 主 `Button`，加载状态和页内 `Alert` |

评分文字建议为“Very difficult / Difficult / Neutral / Easy / Very easy”。它描述使用体验，不能自动转换成处理优先级。没有评分也可提交。

性别选项建议为 `woman`、`man`、`non_binary`、`prefer_not_to_say`，未选择为 `null`。它是可选控件展示，不参与研究结果、反馈优先级、权限或身份判断。若真实产品没有收集用途，可以从真实反馈范围移除；不为它增加无关长问卷。

分类便于维护者处理，标题便于列表扫描，Bug 条件字段展示动态 schema 与交互设计。首版不要求地址、生日、证件、密码或无关信息。姓名与性别不能参与反馈处理顺序。

邮箱和姓名空字符串在提交 mapper 中归一化为 `null`；取消“希望回复”后邮箱允许留空，已有内容可在本会话保留，但未通过语法校验的非空邮箱不能发送。切换为非 Bug 时，不发送隐藏的 Bug 字段；前端可以在本会话保留草稿以便切回，重置时一并清除。

从用户页进入时只携带来源页面名称，不采集完整浏览历史，不把姓名、邮箱、反馈正文写进 URL。

## 4. 校验与数据职责

React Hook Form 管理字段、dirty/touched、提交和错误；Zod 定义 schema，通过 resolver 集成。反馈类型用 discriminated union 或等效条件规则处理 Bug 字段；邮箱与 `wantsReply` 联合校验。类型优先由 schema 推导，避免两份规则分别维护。

职责拆分：

1. `feedback.schema.ts`：内容、可选联系字段、分类和条件规则。
2. `attachment-policy.ts`：数量、大小、扩展名和 MIME 的纯函数规则。
3. `use-attachment-queue.ts`：`File`、预览地址与队列状态。
4. `use-feedback-form.ts`：协调字段、附件和提交，不渲染全部控件。
5. `feedback.mapper.ts`：组装契约，过滤隐藏或不适用字段。
6. `feedback.service.ts`：请求、取消、幂等标识与错误映射。

默认失焦校验；提交时完整校验；已出错字段修正后及时重新校验。不要首次输入时就把整个表单标红。字符计数在 UI 与 schema 一致，不因中文姓名或合法标点误拒绝。

提交失败保留输入。字段错误聚焦第一个错误控件，顶部显示可定位的错误摘要。label 与控件绑定，描述和错误通过 `aria-describedby` 关联，无效字段设置 `aria-invalid`。条件字段移出文档时不能留下透明但可聚焦的控件。

未来 `422` 的已知字段错误映射到对应控件，未知字段和一般失败显示在表单级。反馈正文作为纯文本显示，不把用户内容或服务器堆栈作为 HTML 渲染。

## 5. 附件规则与体验

首版默认：最多 3 个文件；单个不超过 5 MiB（5 × 1024 × 1024 字节）；合计不超过 10 MiB。支持 `.pdf`、`.png`、`.jpg`、`.jpeg`，对应 `application/pdf`、`image/png`、`image/jpeg`；拒绝 0 字节文件。附件用于截图或说明材料，不要求私人证件。

原生 `input type="file"` 是选择基础，拖放只是增强；两种方式走同一规则。`accept` 只是提示，不是安全校验。客户端检查大小、扩展名和 MIME；明显冲突时拒绝；MIME 为空可按扩展名作为演示准入并标注“类型未验证”。未来服务器仍需独立验证真实内容和文件限制。

文件行显示名称、大小、类型、状态和移除操作。PNG/JPEG 通过 Object URL 预览；PDF 首版只显示图标与元信息，不引入完整解析器。移除、替换、重置、成功清理和卸载时释放 Object URL，正在预览时不提前释放。

无效新文件不清空已有有效队列。超限逐项解释，不静默截断。同名不直接认定内容相同；`name + size + lastModified` 只提示疑似重复。处理原生输入后清空其 value，使移除后能重选同一文件，不把文件路径设为 React 受控值。

模拟处理阶段可取消或移除单个附件；最终请求前按当前有效队列组装 FormData。等待最终响应时冻结字段和附件修改，只保留整次提交取消，避免界面队列与已组装请求不一致。真实存储、清理和扫描属于待实现后端能力，Demo 不能标为已完成。

## 6. 提交状态与反馈

```text
editing → validating → submitting → success
                    ↘ editing（校验错误）
                                  ↘ failure → editing / retry
                                  ↘ cancelled → editing
```

附件独立使用 `selected / simulated-processing / ready / failed / cancelled`。Demo 进度标为“Simulated processing”，不表示已上传的真实字节。100% 后仍需等待模拟回执，不能把进度完成当作开发者已经收到反馈。

每次业务提交有请求标识。取消会终止 adapter 并清理计时器，保留字段和文件；迟到响应不能把取消改为成功。未修改内容的网络重试沿用幂等键；内容修改后使用新键。重复点击不会创建并发提交。

Demo 成功区显示 `demo_feedback_...`、演示时间、分类和附件数量，明确未发送给维护者。真实成功区显示服务器确认的反馈编号与 `received`，说明已接收，不承诺处理时限或自动答复。提供“Back to user page”和“Send another feedback”，不自动再次提交相同内容。

HTTP 失败、超时、取消和字段错误分别处理。取消真实请求不代表服务器没有收到；若结果不确定，以同一幂等键重试或后端回执查询确认，不能生成新 ID 假装消除重复。

## 7. 草稿与 Demo 数据生命周期

联系信息、反馈正文、`File`、字节、Object URL、草稿与回执只保留在当前反馈页面内存，不默认写入 localStorage、URL、控制台、分析事件或仓库 fixture。刷新后清空草稿、重新选择附件。

有未提交改动时，应用内离开显示确认：继续编辑保留本页草稿，确认离开则释放附件与清空草稿；返回用户页恢复滚动位置，重新进入表单开始新草稿。浏览器关闭/刷新提示可增强，但不承诺一定出现，不为了恢复文件把它转为 Base64 持久化。

“Fill sample feedback” 使用 `Avery Chen`、`avery.chen@example.com` 和预设内容；可以一键清空联系信息，展示无姓名、无邮箱也能提交的路径。合成 fixture 不含真实访客数据，股票收藏的本地存储机制不复用到个人反馈。

重置清空字段、隐藏的 Bug 草稿、错误、文件、计时器、预览地址与本会话演示回执。不同访客不共享反馈；MSW 不可用时禁止模拟提交，不悄悄透传到未知服务器。

## 8. 模拟接口与拟议真实契约

以下是新功能提议，**不是现有后端接口**：

```text
POST /feedback
Idempotency-Key: <本次反馈的稳定请求标识>
Content-Type: multipart/form-data（浏览器自动生成 boundary）

feedback: JSON 字符串
  category: suggestion | bug | usability | other
  title: string
  description: string
  relatedPage: enum | null
  experienceRating: 1 | 2 | 3 | 4 | 5 | null
  reproductionSteps: string | null
  expectedResult: string | null
  actualResult: string | null
  fullName: string | null
  email: string | null
  gender: enum | null
  wantsReply: boolean

attachments: File（重复字段，0–3 个）
```

不手动给 FormData 设置 multipart Content-Type，否则可能缺少 boundary。`wantsReply=true` 时服务端同样要求有效邮箱，不能只依靠前端。

Demo base 为当前站点 `/api`，由 `src/mocks/handlers/feedback` 拦截 `POST /api/feedback`。真实模式使用 `VITE_FEEDBACK_API_BASE_URL` 指定的明确后端 base URL 加 `/feedback`，不为现有 FastAPI 臆造 `/api/v1` 前缀。

拟议 Demo 回执：

```json
{
  "id": "demo_feedback_001",
  "mode": "demo",
  "status": "simulated",
  "submittedAt": "2026-11-05T00:00:00Z",
  "attachmentCount": 2
}
```

真实成功拟议为 `201 Created`，对应 `{ id, mode: "api", status: "received", submittedAt, attachmentCount }`。时间以服务器实际接收为准；Demo 使用可注入时钟，文档日期不是固定回执日期。不回显完整邮箱或公开附件地址。

拟议错误为 `422` 字段错误、`413` 超限、`415` 类型不支持、`429` 过频和 `500` 一般失败；结构 `{ code, message, fieldErrors? }`。同一幂等键、相同 payload 返回原回执；同键不同内容返回明确冲突，状态码和保留窗口在后端实现时固定。

## 9. 独立反馈模式与真实上线门槛

研究数据和反馈提交是两项独立能力：`VITE_DATA_MODE` 只控制股票、辩论等研究数据；`VITE_FEEDBACK_MODE=demo|api|disabled` 控制反馈，不能把“研究 Demo”与“反馈永远不能送达”绑定。

| 研究数据 | 反馈模式 | 实际行为 |
| --- | --- | --- |
| demo | demo | 研究和反馈均模拟，反馈明确未发送 |
| demo | api | 股票/辩论为 Demo，反馈真实发往已配置后端 |
| api | api | 分别使用真实研究和反馈接口 |
| demo 或 api | disabled | 表单可说明用途，实际提交禁用 |

只有反馈模式为 demo 时才注册 feedback mock。真实反馈 URL 不得被研究 Demo 的 worker 误拦截；研究 mock 仅匹配约定研究 API，不能有通配成功 handler。只要任一模块需要 Demo，就等待 worker 准备后挂载；全真实/禁用组合不启动无用 mock。

`VITE_FEEDBACK_MODE=api` 必须有有效 `VITE_FEEDBACK_API_BASE_URL`，且真实接收能力已完成验证。缺配置、后端未实现或连接失败时显示明确配置/网络错误，不退回模拟成功。Demo 则提供正常、字段错误、慢响应、失败、重复提交等固定场景。

真实反馈小闭环可以先于其他 Full Stack 模块上线。上线门槛包括：正文与附件真实接收、服务端校验、持久化确认、维护者可受限读取、重复提交处理、错误与取消行为、必要的跨域配置。只有通过门槛才将反馈模式配置为 api，并把 UI 文案改成真实接收。

## 10. 后端接收与维护者查看闭环

用户希望“后端可以收到意见”，真实版本必须覆盖前端之外的部分：

1. 接收与校验：服务端检查分类、长度、条件邮箱、附件数量/大小/实际内容；处理幂等重试与合理限流，不依赖前端能力开关。
2. 保存与回执：保存反馈、服务器时间、状态和附件关联。记录与附件写入有失败补偿，不能回执成功后丢失内容；服务重启后仍能读取，不能只放在进程内存中。
3. 附件存储：采用非公开存储与服务端生成标识，不直接信任原始文件名；下载受限。按实际部署需求增加内容检查/扫描，前端不虚构已扫描。
4. 维护者查看：仅维护者可访问列表/详情，按分类、日期和 `received / reviewing / resolved` 等状态筛选。公开用户页不列出其他访客反馈、邮箱或附件。
5. 处理结果：维护者可标记状态并记录内部备注。回复邮件为后续选项，实际发送能力建立后才启用；勾选 `wantsReply` 不代表已发送。
6. 数据维护：真实上线时说明用途、访问人员和保留期限，落实到期清理及必要删除；期限按产品实际需要确定，不编造法律承诺。

接收接口、受限查看、权限和真实存储均待实现；本轮不创建数据库、管理后台或云服务。真实验收必须证明“提交 → 反馈编号 → 后端可读取同一记录 → 维护者看到内容和附件 → 未授权访问被拒绝”。

跨域接收时允许已配置的 Web 来源及 `Idempotency-Key` 等实际使用的请求头，验证预检和失败路径。匿名反馈提交与维护者后台鉴权分开，不能为了让访客提交而开放后台读取权限。

## 11. 建议的功能拆分

```text
features/feedback/
├── api/
│   ├── feedback.contract.ts
│   ├── feedback.mapper.ts
│   └── feedback.service.ts
├── components/
│   ├── feedback-form.tsx
│   ├── feedback-details-fields.tsx
│   ├── bug-details-fields.tsx
│   ├── optional-contact-fields.tsx
│   ├── attachment-picker.tsx
│   ├── attachment-item.tsx
│   ├── feedback-summary.tsx
│   ├── submission-result.tsx
│   └── form-actions.tsx
├── hooks/
│   ├── use-feedback-form.ts
│   ├── use-attachment-queue.ts
│   └── use-simulated-transfer.ts
├── model/
│   ├── feedback.schema.ts
│   ├── attachment-policy.ts
│   └── feedback-state.ts
└── tests/
    ├── feedback-schema.test.ts
    ├── attachment-policy.test.ts
    └── feedback-form.test.tsx
```

用户页只组合反馈入口，表单业务属于 `features/feedback`。通用成功/错误状态组件位于 `components/shared/status`，避免与业务反馈命名混淆。校验、请求、计时和文件生命周期分别管理，页面与表单容器保持短小。

以上文件名是后续实现示意，不代表代码已存在。遵循工程约定的短函数与组件审查阈值，不为了凑行数拆成难以追踪的碎片。

## 12. 验收与面试讲解点

- 从 `/user` 向下滚动找到入口；进入 `/feedback`，返回恢复到入口；直接打开表单也正常。
- 可用合成内容演示；姓名、性别不填可提交；未要求回复时邮箱可为空，要求回复时邮箱必填。
- 分类、标题、描述及 Bug 条件字段校验准确；非 Bug 不发送隐藏字段；切回可恢复本会话草稿，重置彻底清空。
- 评分默认空且可跳过，每项有文字等级；性别不参与任何优先级或权限。
- 错误摘要、首错聚焦、描述/错误关联、键盘与拖放替代操作完整。
- 附件数量3、单个5MiB、合计10MiB边界通过；超出1字节、第四个、0字节和类型冲突清楚拒绝。
- 无效新文件不清空有效队列；移除后可重选；Object URL 正确释放。
- 进度、取消、重试、迟到响应和重复提交可复现；最终请求等待时队列冻结；100%不等于收到反馈。
- Demo 成功说明未发送；真实模式必须有服务器回执；配置/连接错误不变成假成功。
- 研究 Demo + 真实反馈组合正确：研究请求被模拟、真实反馈未被误拦截。
- 个人输入、正文和附件不进入本地持久化、URL或日志；离开确认、刷新与新草稿行为一致。
- 窄屏、缩放、两种主题和 reduced motion 下可操作。
- 真实接入后另验幂等、落库、附件关联、维护者受限读取和未授权访问；当前不能标为已通过。

面试可以讲解：从用户入口连接真实产品需求；条件 schema 减少无关字段；File 与可序列化值分离；取消/竞态/重复提交处理；独立反馈模式让研究 Demo 仍可真实收集建议；模拟成功与服务端确认的区别。

纯规则用单元测试，用户行为用 Testing Library + MSW，完整反馈流程用浏览器 E2E；避免只断言内部调用或大量快照。

## 13. 官方依据

工具行为沿用 2026-11-04 核对的资料；本次 2026-11-05 修订产品定位、字段与拟议契约。依赖版本在初始化时固定，字段和限制为本项目设计，并非工具默认行为。

- [shadcn/ui：React Hook Form 集成](https://ui.shadcn.com/docs/forms/react-hook-form)
- [React Hook Form：useForm](https://react-hook-form.com/docs/useform)
- [Zod：schema API](https://zod.dev/api)
- [MSW：浏览器集成](https://mswjs.io/guides/integrations/browser)
- [MDN：文件输入与 accept](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/input/file)
- [MDN：释放 Object URL](https://developer.mozilla.org/en-US/docs/Web/API/URL/revokeObjectURL_static)
- [MDN：使用 FormData](https://developer.mozilla.org/en-US/docs/Web/API/XMLHttpRequest_API/Using_FormData_Objects)
