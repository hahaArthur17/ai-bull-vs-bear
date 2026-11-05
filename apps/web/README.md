# AI Bull vs Bear · Web 作品版

面向 Web 前端求职的独立客户端；后续可以连接现有后端，扩展为 Full Stack 展示。

当前状态：**Web Demo 已实现、验证并独立上线**。原项目检查点为 `f804d10`，标签为 `baseline/pre-web-2026-11-05`，开发分支为 `codex/web-portfolio`；检查点、标签及分支已推送。创建：2026-11-04；更新：2026-11-05（Pacific/Auckland）。实际验证与发布结果以[开发进度](docs/progress.md)为准。

公开演示：[打开 Counterpoint](https://counterpoint-research.silly-titan-8618.chatgpt.site)。研究数据、脚本回放和反馈提交均为明确标注的 Demo；反馈不会发送给开发者。

## 本地运行

使用 Node 24 系列，与 Web CI 保持一致；`package.json` 的引擎要求为 Node >=24。以下命令从仓库根目录开始：

```sh
cd apps/web
npm ci
npm run dev
```

开发地址为 `http://127.0.0.1:5173`。开发命令使用 Vite `demo` 模式；没有显式环境变量时，研究和反馈默认都是浏览器演示，不需要同时启动手机端、后端、数据库或模型服务。端口已占用时可用 `npm run dev -- --port 5174` 指定其他端口。

本地验收生产构建：

```sh
npm run build
npm run preview -- --port 4173
```

构建产物为本目录下的 `dist/`，预览地址为 `http://127.0.0.1:4173`。`preview` 只用于本地检查产物；线上发布静态文件，而不是运行 Vite 开发或预览服务器。

## 已实现的体验

- 工作台：股票搜索、收藏、搜索的空结果/失败/慢响应场景。
- 股票详情：合成价格图表、时间范围、表格替代视图、指标与证据侧栏。
- 辩论与历史：脚本回放、暂停/继续、证据定位、保存与重新打开、删除确认。
- 用户页：访客身份、实际收藏/历史计数、亮暗主题、演示设置及重置。
- 反馈页：建议/问题分类、条件字段、可选联系信息、附件选择与预览、校验、取消、重试和演示回执。
- 响应式导航、深链接、键盘焦点、减少动态效果等交互支持。

工作台中所有价格、公司指标和证据摘录均为合成演示数据，数据日期为 2026-10-30。辩论是脚本回放，不调用真实大模型，也不表示真实行情或实际引文。

## 从这里开始

1. [开发总计划](docs/development-plan.md)：目标、页面范围、阶段顺序、交付与验收。
2. [工程架构](docs/architecture.md)：目录职责、依赖边界、模拟与真实接口。
3. [视觉与交互规范](docs/design-system.md)：shadcn/ui 组件、页面布局、响应式与动效。
4. [用户反馈表单与附件设计](docs/forms-and-uploads.md)：用户页入口、建议/问题反馈、联系信息、附件及后端接收闭环。
5. [编码与质量规范](docs/engineering-guidelines.md)：短函数、组件拆分、测试与维护约定。
6. [部署与发布计划](docs/deployment.md)：独立部署、构建模式、CI、上线验收与回滚。

以上均为 UTF-8 Markdown 文本文档。总计划保留阶段顺序和验收目标；已经实现、已经验证和已经发布的状态分别记录在[开发进度](docs/progress.md)，不能用计划清单代替实际结果。

## 技术方向

- React、TypeScript、Vite：浏览器客户端与构建。
- Tailwind CSS、shadcn/ui：样式、基础组件和设计变量。
- React Router：路由；TanStack Query：接口数据缓存与更新。
- React Hook Form、Zod：表单状态和数据校验。
- MSW：模拟 API；Vitest、Testing Library、Playwright：分层验证。
- 普通过渡优先；确有复杂布局动画需求时再加入 Motion。

用户在 `/user` 页面向下滚动到反馈区，点击 `Send feedback` 进入 `/feedback`。表单收集对应用的建议或问题；姓名、邮箱和性别是可选联系信息，邮箱在希望收到回复时必填。反馈可独立选择演示或真实接收模式，因此研究数据保留 Demo 时也可以后续接收真实意见。

具体安装版本已锁入本目录的 `package-lock.json`，使用 `npm ci` 复现；不沿用手机端锁文件。

## 数据模式与当前边界

公开作品首版采用 `VITE_DATA_MODE=demo` 和 `VITE_FEEDBACK_MODE=demo`。研究 Demo 和反馈投递模式是两个独立开关；完整配置见[部署说明](docs/deployment.md)。

Demo 的收藏、合成回放历史和主题偏好仅保存在当前浏览器，访客之间不共享。反馈正文、联系信息及附件只保留在当前页面内存，不写入浏览器长期存储。模拟进度和回执明确标为演示，作者不会收到意见或文件。

真实研究模式当前只对现有 `GET /stocks/{ticker}/bundle` 提供部分字段适配。真实目录搜索、鉴权收藏、历史及回放尚未接入，界面会明确说明不可用，不把 Demo 数据伪装成真实返回。缺少价格等必要字段时也会报错。

反馈客户端已预留 `POST /feedback` 的真实接收契约，但现有后端尚未实现接收、持久化和作者查看闭环（G9A）。因此当前不能宣称意见已送达。`npm run build:api` 只是使用 Vite `production` 模式构建，不会补齐这些后端能力；必须显式配置研究和反馈的模式及必要 URL。

## 开发检查

在 `apps/web` 内运行：

```sh
npm run typecheck
npm run lint
npm run format:check
npm test
npm run build
npx playwright install chromium
npm run test:e2e
```

浏览器测试使用构建后的 preview；先执行 `npm run build`。Playwright 自动启动或复用本地 `4173` 端口的预览服务，测试配置保留真实 service worker，不用额外 mock 掩盖 Demo 启动问题。若该端口已有旧产物服务，先停止它，再运行对应新构建的检查。

`npm run format` 用于主动格式化源码；`format:check` 不修改文件。独立工作流 [web.yml](../../.github/workflows/web.yml) 已加入，针对 Web 分支和 `main` 的相关改动运行类型、质量、单元测试、构建和 Chromium E2E。

## 目录入口

```text
apps/web/
├── docs/               产品、设计、工程、表单与发布文档
├── public/             公共图片和合成演示附件
├── src/
│   ├── app/            启动、路由、Provider、应用布局、配置
│   ├── pages/          页面级组合
│   ├── features/       按业务功能组织的模块
│   ├── components/     shadcn 基础组件和跨功能组件
│   ├── lib/            HTTP、契约、存储和通用格式化
│   ├── mocks/          模拟接口、合成数据与可复现场景
│   ├── styles/         全局样式和设计变量
│   └── test/           测试初始化与公共辅助
└── tests/e2e/          完整用户流程的浏览器测试
```

空目录使用 `.gitkeep` 保存；实现对应文件时移除不再需要的占位文件。不为填满目录创建无意义组件。

## 独立发布

本轮采用 Sites 静态托管，项目身份已保存在 `.openai/hosting.json`，输出目录为 `dist`；版本 1 已成功公开发布并完成线上抽查。可用 URL、发布提交、部署版本与验证范围写入[发布记录](docs/deployment.md#7-发布记录与验收)。

这是一套独立 Web 工程，现有手机端和后端继续保留。以后可以把同一静态产物迁移到 Vercel 或 Render 等支持 SPA 的托管服务，无需把整个仓库拆成三个仓库。
