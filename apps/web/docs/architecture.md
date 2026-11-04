# 工程架构与目录职责

创建：2026-11-04；更新：2026-11-05。本文描述目标架构；当前只建立目录与规划，不代表其中的实现文件已经存在。

## 1. 应用边界

`apps/web` 是同一仓库中的独立浏览器客户端，有自己的依赖、锁文件、构建与发布。`apps/mobile` 和 `backend` 保持现有职责。首版无需引入微前端、Turborepo、全局 Redux 或通用插件系统。

采用按业务功能组织的模块：应用启动 → 页面组合 → 功能模块 → 基础 UI / 契约 / HTTP。页面不直接读取 fixture，shadcn 基础组件不请求股票或用户反馈接口。

## 2. 实际建立的目录骨架

```text
apps/web/
├── README.md
├── .env.example
├── .gitignore
├── docs/
├── public/
│   ├── images/
│   └── demo-files/
├── src/
│   ├── app/
│   │   ├── config/              环境、能力开关与演示模式解析
│   │   ├── layout/              AppShell、侧栏、顶栏和移动导航
│   │   ├── providers/           Query、主题和其他应用级上下文
│   │   └── router/              路由表、路由错误与懒加载
│   ├── pages/
│   │   ├── workbench/
│   │   ├── research/
│   │   ├── debate/
│   │   ├── history/
│   │   ├── user/
│   │   ├── feedback/
│   │   ├── about/
│   │   └── not-found/
│   ├── features/
│   │   ├── research/
│   │   │   ├── api/
│   │   │   ├── components/
│   │   │   │   ├── search/
│   │   │   │   ├── overview/
│   │   │   │   └── charts/
│   │   │   ├── hooks/
│   │   │   └── model/
│   │   ├── watchlist/           api/ components/ hooks/ model/
│   │   ├── debate/              api/ components/ hooks/ model/
│   │   ├── evidence/            api/ components/ hooks/ model/
│   │   ├── history/             api/ components/ hooks/ model/
│   │   └── feedback/            api/ components/ hooks/ model/ tests/
│   ├── components/
│   │   ├── ui/                  按需加入的 shadcn 源码
│   │   └── shared/              跨功能且已确认重复的组件
│   │       ├── status/          EmptyState、ErrorState 等通用状态反馈
│   │       └── charts/          通用图表外框、图例、替代数据表
│   ├── lib/
│   │   ├── http/                请求、超时、取消、错误归一化
│   │   ├── contracts/           多模块共用的 DTO 和接口类型
│   │   ├── storage/             版本化本地演示状态
│   │   └── format/              日期、数字、文件大小等通用格式化
│   ├── mocks/
│   │   ├── browser/             MSW worker 启停
│   │   ├── handlers/
│   │   │   ├── stocks/
│   │   │   ├── watchlist/
│   │   │   ├── debates/
│   │   │   ├── history/
│   │   │   └── feedback/
│   │   ├── fixtures/
│   │   │   ├── market/
│   │   │   ├── debates/
│   │   │   └── feedback/
│   │   ├── scenarios/           正常、空数据、延迟、错误
│   │   └── state/               本访客的模拟变更与重置
│   ├── styles/                 语义 token、主题、全局样式
│   └── test/
│       ├── setup/
│       └── helpers/
└── tests/
    └── e2e/
        ├── flows/
        └── fixtures/
```

目录占位用 `.gitkeep` 保存。G1 再增加 `package.json`、锁文件、`components.json`、`index.html`、Vite/TS/ESLint/Vitest/Playwright 配置以及 `src/main.tsx` 等实现文件。上述配置文件当前不伪造为空的可运行配置。

根 `.gitignore` 来自 Python 模板，包含会忽略所有同名目录的 `lib/` 规则。Web 局部 `.gitignore` 已为 `src/lib` 添加例外；后续配置 Git 时要继续检查新增源文件是否被意外忽略。

## 3. 模块职责和依赖

| 位置 | 可以负责 | 不应负责 |
| --- | --- | --- |
| `app` | 启动顺序、全局 Provider、路由、能力配置 | 全部页面业务和请求细节 |
| `pages` | 读取路由参数、组合 feature、安排页面区域 | 巨型表单、图表计算和计时器实现 |
| `features/*/components` | 呈现业务状态、发出用户操作 | 直接读取 mock 文件或环境变量 |
| `features/*/hooks` | 协调请求、状态和生命周期 | 同时返回整页巨型 JSX |
| `features/*/model` | schema、纯计算、状态转换、常量 | React DOM 和 HTTP 副作用 |
| `features/*/api` | 服务函数、查询键、DTO 映射 | 页面通知和导航决定 |
| `components/ui` | shadcn 基础组件和通用变体 | 股票、邮箱、API 和本地业务状态 |
| `lib` | 稳定的跨模块基础设施 | 汇集所有领域逻辑的万能工具箱 |
| `mocks` | 独立模拟实现和合成数据 | 直接被业务组件依赖 |

依赖方向：`app/pages → features → components/lib`。`model` 保持纯净；`lib` 与基础 UI 不反向导入 feature。feature 的跨模块组合放在页面中，必要的跨 feature 调用只能使用明确的公开入口，避免读取另一模块内部 hooks 或产生循环。

搜索和研究详情属于 `research`；收藏属于 `watchlist`；证据在不同页面复用，因此单独为 `evidence`。只因一个类型被两个模块需要时，可放入 `lib/contracts`，不立即制造一整套 entity/service/repository 框架。

测试默认与受测文件相邻；用户反馈模块可集中到自己的 `tests`，因为条件校验与附件边界较多。公共测试准备才进入 `src/test`，完整业务流程进入 `tests/e2e`。

`pages/user` 只组合本地偏好、体验概况和下部的反馈入口；`pages/feedback` 组合反馈表单。业务反馈放在 `features/feedback`，与 `components/shared/status` 中的通用错误/空状态提示区分。入口点击和返回滚动恢复由页面/路由协调，不塞进通用 Button。

## 4. 数据访问与模式

### 请求链路

```text
页面 / 组件
  → feature hook / Query
  → feature service + DTO mapper
  → HTTP client
      ├── 研究 demo：/api/... → 本应用 MSW → 合成 fixture / 本访客状态
      ├── 研究 api：配置的后端地址 + 既有路径 → 现有后端
      └── 反馈独立 adapter：demo / api / disabled → 拟议反馈接收契约
```

MSW 模拟同一 HTTP 契约，不在每个组件写 `if (demo)`。回放和附件模拟这类平台能力由有明确接口的 adapter 注入，而不是对整个应用做复杂依赖注入。

`VITE_DATA_MODE` 只控制股票/研究等数据，接受 `demo` 或 `api`；未配置或无效值显示配置错误，不猜测。首个公开构建显式设为 `demo`。研究 Demo 的 API base 固定当前站点 `/api`；真实研究模式要求有效的后端 base URL。

`VITE_FEEDBACK_MODE` 独立接受 `demo`、`api` 或 `disabled`，不从研究数据模式推断。`demo` 使用 `/api/feedback` 并清楚标注未实际发送；`api` 要求 `VITE_FEEDBACK_API_BASE_URL` 指向已实现并验证的真实接收后端；`disabled` 保留表单说明并禁用提交。无效配置或未知模式明确报错，不回退成模拟送达。

因此 `VITE_DATA_MODE=demo` 可以与 `VITE_FEEDBACK_MODE=api` 同时使用：行情和辩论为演示，反馈真实送达。前端模式配置不替代服务端的验证和后台访问控制。

只要任一模块为 Demo 就初始化所需 MSW handler，不能只看 `import.meta.env.DEV`；启动完成后再渲染依赖 mock 的页面。反馈 handler 仅在反馈为 `demo` 时注册。worker 失败时阻止演示提交并显示重试，不把反馈发给未知地址。全真实或禁用且无需任何 mock 时，不启动 worker。

handler 只拦截明确的演示 origin/路径；已配置并校验的真实反馈 base URL + `/feedback` 允许正常网络访问，不被研究 Demo 拦截。未知模拟 `/api/*` 请求返回明确未实现错误，不能透传到真实服务。静态资源正常处理；不为方便真实反馈而放开所有未知请求。

### 已有契约与拟议契约

| 服务 | 原有后端路径 | Web 处理 |
| --- | --- | --- |
| 股票搜索 | `GET /stocks?q=&limit=` | DTO 映射为搜索结果，保留覆盖状态 |
| 股票详情/研究包 | `GET /stocks/:ticker`、`GET /stocks/:ticker/bundle` | 复用字段语义，显示缺失和过期情况 |
| 收藏 | `GET/POST /watchlist`、`DELETE /watchlist/:ticker` | Demo 内本地访客状态；API 模式遵守真实身份要求 |
| 分析历史 | `GET /analysis/page`、`GET /analysis/:id` | 适配已有分页响应；API 模式只读；删除仅限 Demo 本地记录 |
| 辩论 | `POST /debates`、`GET /debates/:id`、消息/事件子路径 | 首版明确脚本回放；真实流式协议单独集成 |
| 用户反馈 | **拟议** `POST /feedback` | Demo 为 `/api/feedback`；真实接收尚未实现，独立于研究数据模式 |

`/api` 是浏览器 Demo 的请求前缀，不意味着现有 FastAPI 本身有 `/api` 或 `/api/v1` 路由。服务层负责 base URL，不能直接把两种路径拼混。

现有后端没有历史删除能力。Demo 的删除由本地演示 adapter/state 完成；API 模式隐藏或禁用删除入口。不臆造既有 `DELETE /analysis/:id`，也不以本地隐藏记录表示服务器已删除。

HTTP client 根据 body 类型决定请求头：JSON 才设置 JSON Content-Type，FormData 交给浏览器生成 boundary。统一处理超时、AbortSignal、非 JSON 错误和字段校验错误。不要把取消识别成普通请求失败并弹出错误通知。

## 5. 状态归属

- URL：股票代码、查询词、排序、区间、选中的证据等可分享状态。
- Query：股票/历史数据、缓存、变更和失效。`AbortSignal` 传到底层，避免旧请求覆盖。
- React 局部状态：侧栏、当前选择、短暂 UI 反馈。
- React Hook Form：反馈内容、联系信息、dirty/touched、条件字段错误与提交。
- feature reducer：辩论回放、附件队列等具有互斥状态的流程。
- localStorage：仅主题、非个人收藏、合成历史；使用命名空间/版本，处理容量和解析失败。
- 内存：访客反馈正文、姓名、邮箱、File、Object URL、反馈回执与本页草稿；刷新清除。

反馈 `api` 模式的持久化发生在后端：服务器保存意见并返回 `received` 与编号，作者通过受保护的后台/管理查询读取。不能用浏览器 localStorage 代替作者接收，也不能把其他访客反馈放到公开列表中。后端接收闭环作为独立阶段实现，当前不存在这些接口或数据表。

演示数据使用可注入时钟和固定场景，避免随机错误。页面显示数据时间与演示来源；历史记录状态不等于真实后端的持久化保证。

## 6. 原代码复用策略

优先评估 `apps/mobile/src/types.ts`、`research/chartMath.ts` 等纯类型和算法。复用时保留来源、验证边界，并迁入适合 Web 的小模块。不要直接导入 React Native 组件或整份 mobile `api.ts`，后者耦合 Expo 变量、身份会话与流客户端。

首轮不改动手机端实现。两个客户端真正需要共享同一算法时，再建立小型共享包并补好跨端测试；避免长期维护无标注、各自修改的复制实现。

## 7. 官方依据

- [MSW Browser integration](https://mswjs.io/guides/integrations/browser)：worker 的浏览器集成与脚本。
- [Vite 环境变量](https://vite.dev/guide/env-and-mode.html)：`VITE_*` 为客户端构建配置，不存密钥。
- [React Router Data Mode](https://reactrouter.com/start/data/installation)：路由组织；接口缓存职责由本项目另行规定。
- [TanStack Query](https://tanstack.com/query/latest/docs/framework/react/overview)：异步数据状态。

产品模块划分、存储策略和功能开关为本项目的设计决定，并非上述工具的默认行为。
