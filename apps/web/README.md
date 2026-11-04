# AI Bull vs Bear · Web 作品版

面向 Web 前端求职的独立客户端；后续可以连接现有后端，扩展为 Full Stack 展示。

当前状态：**开发进行中**。原项目已建立检查点 `f804d10`，当前开发分支为 `codex/web-portfolio`。创建：2026-11-04；更新：2026-11-05（Pacific/Auckland）。实施记录见[开发进度](docs/progress.md)。

## 从这里开始

1. [开发总计划](docs/development-plan.md)：目标、页面范围、阶段顺序、交付与验收。
2. [工程架构](docs/architecture.md)：目录职责、依赖边界、模拟与真实接口。
3. [视觉与交互规范](docs/design-system.md)：shadcn/ui 组件、页面布局、响应式与动效。
4. [用户反馈表单与附件设计](docs/forms-and-uploads.md)：用户页入口、建议/问题反馈、联系信息、附件及后端接收闭环。
5. [编码与质量规范](docs/engineering-guidelines.md)：短函数、组件拆分、测试与维护约定。
6. [部署与发布计划](docs/deployment.md)：独立部署、构建模式、CI、上线验收与回滚。

以上均为 UTF-8 Markdown 文本文档，可直接阅读和继续维护。已做与待做以开发总计划中的清单为准。

## 技术方向

- React、TypeScript、Vite：浏览器客户端与构建。
- Tailwind CSS、shadcn/ui：样式、基础组件和设计变量。
- React Router：路由；TanStack Query：接口数据缓存与更新。
- React Hook Form、Zod：表单状态和数据校验。
- MSW：模拟 API；Vitest、Testing Library、Playwright：分层验证。
- 普通过渡优先；确有复杂布局动画需求时再加入 Motion。

用户在 `/user` 页面向下滚动到反馈区，点击 `Send feedback` 进入 `/feedback`。表单收集对应用的建议或问题；姓名、邮箱和性别是可选联系信息，邮箱在希望收到回复时必填。反馈可独立选择演示或真实接收模式，因此研究数据保留 Demo 时也可以后续接收真实意见。

具体版本在初始化时核对兼容性并锁入 `package-lock.json`；不沿用手机端锁文件。

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

## 下一步

G0 已完成；正在实现和验证 Web。现有文档与源码应保留，**不要在脚手架提示中选择清空目录**。

运行方式与阶段检查结果随实现更新；未验证的能力不视为已完成。
