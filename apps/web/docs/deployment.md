# 独立部署与发布计划

创建：2026-11-04；更新：2026-11-05（Pacific/Auckland）。状态：Sites 云端项目已创建，项目身份与静态输出配置已保存；发布及公开访问验收待完成。未记录成功部署回执前，不把预期地址写成已上线作品。

## 1. 发布拓扑

同一个 GitHub 仓库保留三个部分：新 Web `apps/web`、原客户端 `apps/mobile`、后端 `backend`。新 Web 单独构建、单独发布，有固定的作品地址；原系统继续按自己的流程维护。

第一阶段全演示构建使用静态托管，不要求同时启动数据库、模型服务或现有后端。后续可先连接真实反馈接收服务，而研究数据继续用 Demo；其他真实研究 API 再分模块接入。

本地 `render.yaml` 显示原前端构建根目录是 `apps/mobile`，后端是独立 Docker 服务。这只是仓库配置，不能据此宣称云端当前的分支、环境或运行状态。新增 Web 时不直接覆盖原服务。

## 2. 构建约定

当前 Web 工程使用以下约定：

| 项目 | 目标值 |
| --- | --- |
| 仓库 | 现有 `ai-bull-vs-bear` |
| Web 构建根目录 | `apps/web` |
| 安装 | `npm ci`，使用 Web 自己的锁文件 |
| 构建 | `npm run build` |
| 输出 | `dist`，相对于 Web 根目录 |
| Node | 与现有 Web CI 一致的 Node 24 系列；包引擎要求 >=24 |
| 预览源 | `codex/web-portfolio` 分支/PR |
| 正式源 | 明确选择的已验收分支与提交，记录 SHA |

本轮采用 Sites。`apps/web/.openai/hosting.json` 已记录实际项目身份，静态目录为 `dist`，并显式设置 `not_found_handling: single-page-application`，不是待创建的占位配置。该文件应保留并随来源一起同步，不为同一作品重复注册新项目。站点当前的发布版本、访问权限和最终 URL 仍需以工具回执与实际访问检查为准。

构建与本地预览命令：

```sh
# 从仓库根目录进入
cd apps/web
npm ci
npm run build
npm run preview -- --port 4173
```

Sites 发布时保存对应来源版本并上传/打包已经构建的 `dist`，使用项目已有身份发布；记录成功回执中的版本、部署标识与准确 URL。当前只确认项目和 manifest 已存在，不把它们等同于站点已经公开可访问。

后续若迁移到 Vercel 或 Render，继续独立指定 `apps/web`、`npm ci`、`npm run build` 和 `dist`，补齐该平台的 SPA 回退、环境变量和部署源配置即可。无需迁移或覆盖原 `apps/mobile` 与后端服务，也不在本文件预设新平台账户、价格或配额。

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

上表描述模式组合的部署条件，不代表全部组合已实现。目前完整可展示的是 `demo + demo`。真实研究只对现有股票 bundle 提供部分字段映射，真实目录、收藏、历史和回放尚未接入；真实反馈接收后端也尚未实现，G9A 完成前不启用接收能力。

`VITE_FEEDBACK_MODE=disabled` 用于真实接收尚不可用且不提供演示时，禁用提交并说明。反馈 `api` 要求设置 `VITE_FEEDBACK_API_BASE_URL`，地址不含末尾 `/feedback`，由 service 追加路径；生产使用已验证的 HTTPS 接收地址。本地联调可显式使用 localhost。缺少配置、服务未实现或请求失败都不自动切换成模拟成功。

未来真实研究构建使用 `VITE_DATA_MODE=api` 与明确的研究后端 URL。研究与反馈可以同一后端，也可以分别部署；不能让一个总开关替代两者的实际能力状态。

`npm run build` 显式选择 Vite 的 `demo` 模式；没有额外环境变量时研究和反馈默认 Demo。`npm run build:api` 选择 `production` 模式，此模式要求显式提供 `VITE_DATA_MODE` 与 `VITE_FEEDBACK_MODE`。命令名称不是能力开关，也不会自动部署 API；配置错误会阻止正常启动，不应以假成功掩盖。

Vite 变量在构建时进入浏览器代码。更换托管平台中的值后，需要重新构建/部署才生效。`VITE_*` 不能保存模型密钥、数据库密码、服务端 token；`.env.example` 只记录公开配置样例。

全演示预览与真实反馈公开版使用明确的发布地址和模式标识。首版不提供让访客任意填写未知后端 URL 的功能；从 Demo 切到无需 mock 的构建时，只清理本应用自己注册的旧 worker，不能注销同源的其他应用 worker。

## 4. 生产 Demo 的 MSW

1. 只要研究或反馈任一模式为 `demo`，就启动其需要的模拟层；不能仅判断开发模式。所有模块都无需 mock 时不启动。
2. `public/mockServiceWorker.js` 已由 MSW CLI 生成并纳入工程，随构建发布；不手写或伪造 worker 文件。
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

独立工作流 `.github/workflows/web.yml` 已加入，不依赖原手机端/后端 CI 才检查 Web。当前触发条件是：

- 向 `main` 或 `codex/web-portfolio` 推送，且涉及 `apps/web/**` 或该 workflow。
- 以 `main` 为目标创建/更新 PR，且涉及相同路径。

工作流使用 Node 24、Web 自己的锁文件和 npm 缓存。在 Web 目录依次完成安装、类型检查、lint/格式、单元/组件测试、构建、安装 Chromium 和关键 E2E，并保留浏览器报告。配置已存在不代表远程运行已经通过；每次发布核对对应 SHA 的 GitHub Actions 结果。

当前路径过滤会让 Web 文档改动也触发完整工作流。未来共享包加入后需纳入触发范围；可以后续优化文档-only 检查，但不能让源代码变化漏过检查。

Playwright 针对构建产物启动本地 `4173` 端口 preview，使用 Demo 数据与真实 worker，不能用额外网络 mock 掩盖启动问题。当前浏览器配置仅运行 Chromium；另有 Node 集成测试使用临时 HTTP 接收端验证四种研究/反馈模式组合、multipart 和幂等键。生产反馈服务仍未实现，Firefox/Safari 也未验收。

首轮预览不必等 238 个历史提交全部并入 `main`。发布时记录分支和提交；后续合并要区分原开发成果与 Web 改版范围。

## 7. 发布记录与验收

实际发布记录（2026-11-05）：

| 项目 | 当前记录 |
| --- | --- |
| 托管 | Sites 静态站点 |
| 项目身份 | 已保存在 `apps/web/.openai/hosting.json` |
| 来源分支 | `codex/web-portfolio` |
| GitHub 来源 SHA | `04fbf93c19ff04979fe070fbc571da7df7f56645` |
| Sites 镜像来源 SHA | `e4165448607278808df4b4cdea9d85f24e033c61` |
| 保存版本 / 部署标识 | 版本 1；`appgprj_6aeb94eedb208191a2b08ae5fc7e0723~appgver_08252f03003c81919dfe40f07402223c` / `appgdep_6aebd9ec03048191932d5473400d5f45` |
| 实际 URL | [Counterpoint](https://counterpoint-research.silly-titan-8618.chatgpt.site) |
| 发布日期与时间 | 2026-11-05 14:20 NZDT（Pacific/Auckland） |
| 访问权限 | public；匿名 HTTP 返回 200，浏览器无需应用账号即可进入 |
| 线上检查 | 深链接 200；worker/JS MIME 正确；实际打开股票图表、用户页反馈入口并完成合成 Demo 提交，日志无 warning/error |
| 回滚基线 | 首次发布，无更早 Web 部署；保留版本 1，后续可重新部署此已保存版本，不强推 Git |

GitHub 是保留完整阶段历史的主仓库。Sites 使用独立发布镜像：只复制已提交的 Web 来源及同一来源构建的 `dist`，不复制父仓库、手机端、后端、个人数据、依赖目录或本地环境文件。镜像由官方 helper 提交并推送后，使用其确切 SHA 和对应产物保存版本，再部署。两个 Git SHA 不同是因为仓库根目录与提交历史不同；运行时代码相同。发布后仅补充本文等文档，运行时代码没有变化。

回滚操作：选择上述 Sites 项目，重新部署已保存的版本 1；也可使用 `deploy_site_version` 传入记录的精确项目与版本 ID。此次没有实际执行回滚演练。

执行顺序为：确认源提交和模式 → 完成质量与浏览器检查 → 构建 `dist` → 同步来源并保存版本 → 发布该版本 → 等待终态回执 → 核对访问权限与真实 URL → 验收深链接、worker 和主流程 → 记录回滚版本。任何一项未完成，均不提前改成已发布。

正式发布验收清单：

- [x] G0 检查点和本轮质量结果已记录；构建 SHA 与发布源明确。
- [x] 干净浏览器首次访问无需账号即可进入研究 Demo；全演示版不依赖后端。
- [x] `/stocks/AAPL`、`/user`、`/feedback`、`/history` 深链接直接访问、刷新和前进后退正常。
- [x] 已核对 worker 与入口 JS 返回正确内容及 MIME；线上页面正常加载。
- [x] 本地真实浏览器验证搜索、收藏、图表、证据、回放和历史重开；线上抽查图表和反馈流程。
- [x] 本地验证入口、条件字段、附件及失败重试；线上从用户页进入表单并完成模拟提交。
- [ ] 反馈 Demo 明确未发送；真实反馈版使用合成测试意见验证服务端持久化、编号及作者受保护查看，研究 Demo 不拦截真实发送。
- [ ] 重置只清除本应用命名空间，恢复合成数据；本地反馈草稿刷新即清空，已接收的真实意见不会被浏览器重置误删。
- [ ] 亮暗主题、窄屏、键盘、缩放和减少动态效果通过检查。
- [x] 页面清楚标注 Demo 数据；About 只描述已实现/验证的能力。
- [x] 控制台无未处理异常；数据请求不会意外访问真实个人服务。
- [x] 发布说明记录 URL、SHA、日期、检查范围及未验证内容。
- [x] 保留首个可用版本 1，并记录再次部署该版本的入口。

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

后续更换托管平台或开启真实接口时，重新核对对应平台配置与实际接收能力；本次 Sites 项目已建立的事实与待完成的发布结果应分别记录。
