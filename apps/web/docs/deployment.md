# 独立部署与发布计划

创建：2026-11-04；更新：2026-11-05。状态：发布设计，尚未创建 Web 云端项目或执行部署。

## 1. 发布拓扑

同一个 GitHub 仓库保留三个部分：新 Web `apps/web`、原客户端 `apps/mobile`、后端 `backend`。新 Web 单独构建、单独发布，有固定的作品地址；原系统继续按自己的流程维护。

第一阶段全演示构建使用静态托管，不要求同时启动数据库、模型服务或现有后端。后续可先连接真实反馈接收服务，而研究数据继续用 Demo；其他真实研究 API 再分模块接入。

本地 `render.yaml` 显示原前端构建根目录是 `apps/mobile`，后端是独立 Docker 服务。这只是仓库配置，不能据此宣称云端当前的分支、环境或运行状态。新增 Web 时不直接覆盖原服务。

## 2. 构建约定

G1 建立并验证下面的约定后再配置托管平台：

| 项目 | 目标值 |
| --- | --- |
| 仓库 | 现有 `ai-bull-vs-bear` |
| Web 构建根目录 | `apps/web` |
| 安装 | `npm ci`，使用 Web 自己的锁文件 |
| 构建 | `npm run build` |
| 输出 | `dist`，相对于 Web 根目录 |
| Node | 与 G1 验证并锁定的版本一致，先对齐现有 Node 24 系列 |
| 预览源 | 完成 G0 后的 Web 分支/PR |
| 正式源 | 明确选择的已验收分支与提交，记录 SHA |

可选支持 Vite 静态构建的托管平台，具体选型在 G8 根据现有账户和预览能力确定。本轮不预设已创建账户、项目或绑定域名，也不承诺平台价格和配额。

`vite preview` 用于本地验收构建产物，不作为线上生产服务器。

## 3. Demo 与 API 构建配置

```text
# 首轮全演示构建配置
VITE_DATA_MODE=demo
VITE_API_BASE_URL=/api
VITE_FEEDBACK_MODE=demo
VITE_FEEDBACK_API_BASE_URL=
```

研究和反馈分别选择数据来源：

| 研究模式 | 反馈模式 | 实际发布要求 |
| --- | --- | --- |
| `demo` | `demo` | 纯前端作品演示；反馈不会送到作者 |
| `demo` | `api` | 前端 + 已验证的反馈后端；研究仍模拟，作者可收到意见 |
| `api` | `api` | 真实研究与反馈服务；分别验证接口、身份与持久化 |

`VITE_FEEDBACK_MODE=disabled` 用于真实接收尚不可用且不提供演示时，禁用提交并说明。反馈 `api` 要求设置 `VITE_FEEDBACK_API_BASE_URL`，地址不含末尾 `/feedback`，由 service 追加路径；生产使用已验证的 HTTPS 接收地址。本地联调可显式使用 localhost。缺少配置、服务未实现或请求失败都不自动切换成模拟成功。

未来真实研究构建使用 `VITE_DATA_MODE=api` 与明确的研究后端 URL。研究与反馈可以同一后端，也可以分别部署；不能让一个总开关替代两者的实际能力状态。

Vite 变量在构建时进入浏览器代码。更换托管平台中的值后，需要重新构建/部署才生效。`VITE_*` 不能保存模型密钥、数据库密码、服务端 token；`.env.example` 只记录公开配置样例。

全演示预览与真实反馈公开版使用明确的发布地址和模式标识。首版不提供让访客任意填写未知后端 URL 的功能；从 Demo 切到无需 mock 的构建时，只清理本应用自己注册的旧 worker，不能注销同源的其他应用 worker。

## 4. 生产 Demo 的 MSW

1. 只要研究或反馈任一模式为 `demo`，就启动其需要的模拟层；不能仅判断开发模式。所有模块都无需 mock 时不启动。
2. 用 MSW CLI 在 G1 生成 `public/mockServiceWorker.js`，随构建发布；不手写或伪造 worker 文件。
3. 等待 worker 准备好，再挂载依赖模拟接口的组件；启动失败显示重试状态，避免未拦截的演示反馈提交。
4. 仅注册显式 Demo 模块的 handler；反馈为 `api` 时不注册反馈 mock，允许已校验的真实反馈地址正常发送。未知模拟 `/api/*` 返回清晰错误，静态请求正常通过；不把全部未知请求都放行。
5. 演示只用合成种子数据，不嵌入私有用户记录或真实上传文件。
6. 变更依赖时同步更新并检查 worker；部署后验证缓存更新及新旧构建切换。

反馈 Demo 在本浏览器完成，不连接后端、不发送邮件、不提供真实附件永久链接，明确标注作者未收到。真实反馈只有服务端验证并持久化后才显示 `received` 和编号；研究内容为 Demo 不影响真实反馈接收。

## 5. SPA 路由与静态文件

有效前端路由（如 `/stocks/AAPL`、`/user`、`/feedback`、`/history`）直接访问或刷新时，应回退到 `index.html`。但真实静态文件必须先正确响应：

- `/mockServiceWorker.js` 返回 JavaScript，不能返回 SPA HTML。
- `/assets/*` 返回对应构建资源及正确 MIME。
- 图标、图片和合成示例附件按真实路径返回。
- 未匹配的真实 API 不使用 HTML 假装接口响应。

浏览器 service worker 需安全上下文；本地开发通常可使用 localhost，公网使用 HTTPS。子路径发布时同时核对 Vite base、路由 basename 和 worker URL/scope；首版优先站点根路径部署，减少额外配置。

## 6. CI 与预览

现有 `.github/workflows/ci.yml` 只针对 `main` push 和以 `main` 为目标的 PR，没有新 Web job。G1/G8 需要增加独立 Web 检查，并明确 Web 分支 push/PR 也会触发，避免开发分支一直没有检查。

在 Web 目录完成：安装 → 类型检查 → lint/格式 → 单元/组件测试 → 构建 → 关键 E2E。初始配置可用 Node 24、Web 锁文件缓存和测试报告保留；按实际运行结果调整。

路径过滤至少覆盖 `apps/web/**` 及相关 workflow；未来共享包加入后，也纳入触发范围。文档-only 改动可以跳过昂贵的浏览器任务，但不能让源代码变化漏过检查。

Playwright 针对构建产物启动本地 preview，使用固定 Demo 数据模式；保留 worker，不能用额外网络 mock 掩盖启动问题。补充“研究 Demo + 反馈 API”组合检查，使用隔离的测试接收端验证真实网络链路，不把反馈 mock 成功当成送达。worker 专项自动化以工具实际支持的浏览器为准，补充实际 Firefox/Safari 验收，不据此断言 MSW 本身只支持单一浏览器。

首轮预览不必等 238 个历史提交全部并入 `main`。发布时记录分支和提交；后续合并要区分原开发成果与 Web 改版范围。

## 7. 正式发布验收

- [ ] G0 检查点、G1–G7 结果已记录；构建 SHA 与发布源明确。
- [ ] 干净浏览器首次访问无需账号即可进入研究 Demo；全演示版不依赖后端。
- [ ] `/stocks/AAPL`、`/user`、`/feedback`、`/history` 深链接直接访问、刷新和前进后退正常。
- [ ] worker 和 JS/CSS/图片返回正确内容及 MIME；无静态资源 404。
- [ ] 搜索、收藏、图表、证据、辩论回放和历史重开可完成。
- [ ] 用户页向下滚动找到反馈按钮，进入表单并返回时位置合理；条件字段、附件、取消和重试可用。
- [ ] 反馈 Demo 明确未发送；真实反馈版使用合成测试意见验证服务端持久化、编号及作者受保护查看，研究 Demo 不拦截真实发送。
- [ ] 重置只清除本应用命名空间，恢复合成数据；本地反馈草稿刷新即清空，已接收的真实意见不会被浏览器重置误删。
- [ ] 亮暗主题、窄屏、键盘、缩放和减少动态效果通过检查。
- [ ] 页面清楚标注 Demo 数据；About 只描述已实现/验证的能力。
- [ ] 控制台无未处理异常；数据请求不会意外访问真实个人服务。
- [ ] 发布说明记录 URL、SHA、日期、检查范围及未验证内容。
- [ ] 保存上一可用部署，明确可执行的回滚入口。

## 8. 回滚与后续真实集成

优先把固定作品地址切回上一已验收部署，不通过强制改写 Git 历史回滚。若改变本地存储结构，采用版本化/兼容读取；worker 缓存更新也要纳入回滚检查。

反馈接收可作为首个真实后端里程碑，先于其他 Full Stack 功能：实现反馈 API、校验、幂等/限流、持久化、私有附件存储和作者受保护的读取入口；验证从公开页面到后台查看的完整流程。匿名访客可以提交，作者后台仍需身份和权限控制。接收服务完成前不启用真实提交，邮件通知/答复为后续选项。

后续真实研究 API 再验证认证、CORS、接口兼容和业务持久化。前后端可分别发布，但接口契约变化仍需协调。

## 9. 官方依据

- [Vite：静态部署与 preview 边界](https://vite.dev/guide/static-deploy.html)
- [Vite：环境变量与构建模式](https://vite.dev/guide/env-and-mode.html)
- [MSW：浏览器集成](https://mswjs.io/guides/integrations/browser)
- [React Router：SPA 路由回退](https://reactrouter.com/how-to/spa)（文档以 Framework Mode 举例；本项目使用 Vite SPA，不照搬其输出目录）
- [Playwright：webServer](https://playwright.dev/docs/test-webserver)
- [Playwright：Service Workers](https://playwright.dev/docs/service-workers)

具体云平台配置、账户状态、定价与可用能力在真正部署前重新核对。
