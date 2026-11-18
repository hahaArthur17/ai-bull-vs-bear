# Counterpoint Glass 改版执行手册

编写日期 2026-11-05，更新日期 2026-11-19（Pacific/Auckland）。当前 Web 分支为 `codex/web-portfolio`，最初编写时的代码基线为 `76146ca`。这份手册采用 **Figma Design** 完成设计稿、组件和交互原型，再进入现有 React 工程实施。先完成工作台的桌面与手机样板，通过设计和交互验收后再推广到全部页面。

| 阶段 | 主要产出 | 进入下一阶段的条件 |
| --- | --- | --- |
| 1. 需求与基线 | 改版目标、范围、本地 v001 参考图 | 能指出三个具体问题和对应改进 |
| 2. Figma 设计与交接 | 工作台桌面与手机线框、高保真稿、组件、原型和 Frame 链接 | 可以从稿件和原型确认布局、状态、响应式规则与主要操作路径 |
| 3. 外观基础 | 三态选择、偏好兼容、Glass 样式 | 两处入口同步，刷新能恢复，现有两种配色通过抽查 |
| 4. 工作台样板 | 可操作的 Glass 首页 | 桌面和手机均可阅读、搜索、筛选和收藏 |
| 5. 页面推广 | 七类页面的 Glass 布局 | 关键业务、状态保留和响应式流程逐页验收 |
| 6. 验收与归档 | 测试结果、本地 v002 截图、发布记录 | 分支、构建、截图与实际发布版本可对应 |

个人项目可以依次用产品、设计、开发和 QA 的视角审查同一份记录。每次评审写清楚通过条件、待改问题和下一步负责人。由你亲自决定的版式、颜色和组件取舍，在设计稿或提交说明中写下原因，后续可用于作品讲解。

## 配对设计的学习方式与 AI 协作约定

2026-11-19 补充。本轮学习以已有的 Photoshop 基础、Figma Frame 和组件概念为起点，通过工作台改版积累实际操作经验。采用 **配对设计、独立复现和设计评审** 的方式，由 AI 提供方案、示范和排查提示，你负责做设计选择，并亲手完成部分关键组件与响应式调整。

### 每轮围绕一个小任务推进

每轮可以采用下面的顺序，按熟练程度调整任务大小。先完成一个工具栏或一个面板，再逐步组合页面。

| 环节 | 你来做的事 | AI 提供的支持 | 当轮留下的记录 |
| --- | --- | --- | --- |
| 1. 描述问题 | 对照 v001 指出具体感受和受影响的操作 | 把观察整理为设计目标和可验证的任务 | 当前问题、使用场景和希望改善的行为 |
| 2. 比较方案 | 从两个布局方案中选择一个，解释原因 | 说明内容空间、查找效率和窄屏布局的取舍 | 选定方案、理由和需要验证的假设 |
| 3. 观察示范 | 操作前预测结果，操作后用自己的话解释 | 示范一个局部，说明图层、布局属性与参数的依据 | 理解了哪些属性，还有哪些疑问 |
| 4. 独立复现 | 亲手完成一个相似区域，并检查结果 | 根据现象提供线索，再按需要补充操作说明 | 自己完成的 Frame、组件和遇到的困难 |
| 5. 应对变化 | 换成长文案、390px 宽度或错误状态，先观察再尝试修复 | 帮助分析原因、比较修复方案和验证影响 | 变化后的问题、尝试和最终结果 |
| 6. 设计评审 | 展示结果，说明选择并复查使用路径 | 核对任务目标、组件一致性和响应式表现 | 前后对照、已解决的问题和下一轮任务 |

AI 示范时，把操作拆成可理解的小段。例如选中搜索框后，解释父级采用什么布局、输入框为什么使用 Fill container、按钮为什么使用 Hug contents，再调整一次宽度观察结果。遇到问题时，你先描述现象和自己的判断，AI 先提示检查位置，随后按需要解释属性关系或示范修复。

如果某一轮主要由 AI 负责鼠标操作，你可以负责操作前预测、操作后解释，以及选择接受哪种设计。随后安排一次亲手复现，用实际操作检查理解程度。独立练习可以选相邻区域，例如看完搜索工具栏的示范后，自己完成股票筛选栏。

### 第一轮练习导航和搜索工具栏

第一轮以工作台的导航和搜索工具栏为范围，可以结合第 1 步与第 2 步执行。

1. 打开 v001 的桌面和手机工作台截图，写下最想改善的三个地方，并选定本轮优先处理的问题。
2. 让 AI 给出两个导航与搜索布局草案，例如悬浮侧栏和顶部导航。你比较它们如何分配内容空间、呈现搜索入口，以及适配手机，再选择一个并写下理由。
3. 在 Figma 建立工作台参考与线框 Frame。AI 示范导航或搜索工具栏中的一个组件，解释结构、Gap、Padding、尺寸策略和选中状态。
4. 你亲手完成相似的筛选区域，放入真实的按钮文字和公司名称。检查主组件、实例和文字属性的关系。
5. 将页面宽度调整到 390px，再加入较长文案或一个额外导航项。先提出原因判断，尝试修改，再请 AI 评审。
6. 展示桌面与手机结果，整理自己的操作、需要帮助的地方和仍想改善的细节，为下一轮确定任务。

这一轮可以用三个动作自查掌握程度。自己重新搭建相似的工具栏，解释 Hug contents 与 Fill container 在该结构里的作用，并处理一次窄屏下的挤压或换行问题。练习完成后保存相关 Frame 链接和前后对照图。

### 用实际任务积累设计和实现经验

以下场景用于选择练习题。记录里的困难、调整和结果以当轮真实观察和实际操作为依据。

| 练习任务 | 可能观察到的问题 | 需要理解和验证的内容 |
| --- | --- | --- |
| 悬浮搜索工具栏 | 窄屏时按钮挤压输入框或长文案换行 | Auto layout、父子尺寸关系和操作优先级 |
| Glass 导航 | 背景透出后文字或焦点难以辨认 | Fill 透明度、背景模糊、阅读层次和对比度 |
| 统一按钮与字段 | 调整主组件后部分页面实例出现差异 | 实例覆盖、文字属性和状态 Variants |
| 三种外观原型 | 选择器状态变化后，页面材质仍显示另一种外观 | 组件 Change to 与页面 Navigate to 的连接方式 |
| 设计稿实现到网页 | 相同参数在 Figma 和浏览器中的观感存在差异 | CSS 参数映射、浏览器调校和设计回填 |

### 与 AI 开始下一轮时可以使用的提示词

> 请以配对设计导师的方式指导我完成 Counterpoint 的 Glass 改版。我有 Photoshop 基础，理解 Figma 的 Frame 和组件概念，正在积累实操经验。每轮给我一个小任务和验收标准，先让我说明自己的方案，再提供建议。示范时解释选择图层、布局属性和参数的原因。给我一次独立复现和处理需求变化的机会。卡住时先提供线索，再逐步讲解。每轮结束后，根据我实际做过的操作整理问题、选择和验证结果。第一轮从工作台的导航和搜索工具栏开始。

## 第 1 步 确定问题、范围和开发基线

1. 在本地打开 `design-snapshots/v001-2026-11-05-counterpoint-baseline/`，对照桌面和手机版截图。先挑选两张 `01-workspace.jpg` 作为 Figma 首轮参考，其余页面在推广阶段使用。优先标记影响使用的问题，例如桌面导航占据较多空间、首屏找股票的入口不够突出、主要图表和辅助信息缺少层次。这些是观察方向，以你从截图中看到的问题为准。
2. 把目标写成可验收的用户行为。访客可从顶部或用户页选择 **Light / Dark / Glass**。选择 Glass 后能看到新的页面分区和材质。刷新可以恢复选择，切换时当前页面和已经输入的内容仍可继续使用。
3. 把首轮开发范围定为「三态入口、共享外观基础、工作台样板」。样板之后按同一视觉规则覆盖股票详情、辩论、历史、用户、反馈和关于页。Glass 复用现有路由、研究数据、收藏、回放和表单能力。
4. 从仓库根目录检查工作区和当前提交。处理好已有改动后，从 Web 分支创建独立的样式开发分支。以下是建议操作，分支名按实际情况调整。

```bash
git status --short --branch
git log -1 --oneline
git switch -c codex/glass-appearance codex/web-portfolio
cd apps/web
npm ci
npm run dev
```

使用项目要求的 Node 24 或更新版本。开发地址以终端打印为准，默认是 `http://127.0.0.1:5173`。开工记录保留起点提交、现有截图位置和三个希望改善的问题。参照 [Web README](../README.md) 和 [已有开发进度](progress.md)。

## 第 2 步 在 Figma 完成设计稿、原型和开发交接

### 2.1 新建设计文件并整理画布

1. 打开 Figma，在 Drafts 或自己的项目中创建一个 **Design 文件**，命名为 `Counterpoint — Glass v002`。
2. 在文件内建立一个 Page，命名为 `Glass v002`。在这个 Page 内创建下面的 Sections，用于整理不同阶段的稿件。Section 组织画布，Frame 承载具体页面和布局。
3. 在 `00 Reference` 写下第 1 步发现的三个问题、改版目标和预计调整的导航。开始设计后把尝试过的版式保留在探索区，方便回看取舍。

| Section 名称建议 | 放置内容 |
| --- | --- |
| `00 Reference` | v001 桌面与手机截图、问题标注、参考来源 |
| `01 Exploration` | 工作台线框、布局尝试、设计理由 |
| `02 Design System` | 颜色和文字样式、变量、材质样板、组件与状态 |
| `03 Desktop` | 桌面高保真稿及必要交互状态 |
| `04 Mobile` | 手机高保真稿、菜单和窄屏状态 |
| `05 Handoff` | 定稿说明、Frame 链接、组件对应、待处理问题 |

首轮的组织方式使用同一文件里的本地组件和样式。页面数量增加后，再按实际查找和协作需要拆分 Pages。

### 2.2 把现有截图导入 Figma，建立修改前参考

1. 从本地 `desktop-light/01-workspace.jpg` 和 `mobile-light/01-workspace.jpg` 拖入 `00 Reference`。后续使用相同方法导入另外六类页面。
2. 在右侧尺寸属性中保持图片宽高比例锁定。将桌面截图宽度设为 **1440**，手机截图宽度设为 **390**，高度按图片比例保留。全页截图的实际高度可以从 v001 版本根目录的 `manifest.json` 查询。
3. 为两张图分别建立包住完整图片的参考 Frame，高度采用图片的实际高度。图层命名中写上 `v001 / Workspace / Desktop` 和 `v001 / Workspace / Mobile`，锁定截图图层。
4. 在图旁标注截图日期、路由 `/`、亮色、AAPL、3M 图表及默认收藏和历史数量。用文字或评论标出希望改进的位置。
5. 在旁边绘制新的可编辑 Frame，用文字、形状和组件完成新版设计，使参考图与新稿可以并排检查。

这一步完成时，参考图的文字、按钮和卡片保持原始比例，可以直接比较相同宽度下的信息密度。

### 2.3 画工作台线框并设置响应式结构

1. 按 `F` 创建两个顶层 Frame，在右侧设置 **1440×1000** 和 **390×844**，命名为 `Workspace / Glass / Desktop` 与 `Workspace / Glass / Mobile`。这两组尺寸代表原型视口。
2. 先用灰色块和真实栏目名称画出导航、主标题、搜索、指标、图表和股票列表。把「找股票 → 查看概览 → 打开研究」画成连续的动作，对每个重点区块写一句设计理由。
3. 选中同一区块的图层，使用 `Shift+A` 添加 Auto layout。为页面内容使用纵向排列，为工具栏使用横向排列，再按需要嵌套概览、图表和列表。逐个设置 Gap、Padding、对齐和宽高策略。
4. 按下面的表设置尺寸行为。拖动 Frame 宽度，检查长标题、按钮文字、表格和导航如何变化，再调整最小宽度和换行。
5. 分别完成桌面与手机排布，并标注 768px 等中间宽度下的堆叠、导航收起和阅读顺序。将这些规则带到后续 CSS 断点实现。[Figma：Auto layout](https://help.figma.com/hc/en-us/articles/360040451373-Guide-to-auto-layout-in-Figma) · [Figma：Frames](https://help.figma.com/hc/en-us/articles/360041539473-Frames-in-Figma-Design)

| Figma 设置 | 适合的内容 | 需要观察的结果 |
| --- | --- | --- |
| `Hug contents` | 按钮、标签、紧贴文字的容器 | 文案变化后容器仍有合适内边距 |
| `Fill container` | 搜索框、卡片、列表和可伸展内容 | 按父容器可用空间扩展 |
| `Fixed` | 图标、头像、原型视口 | 保持明确的宽高 |
| `Constraints` | 普通 Frame 中需要贴边或居中的图层 | 调整父 Frame 后位置符合预期 |

Auto layout 内的常规子项主要用对齐和尺寸策略控制。对脱离布局流的悬浮元素，再配置位置及 Constraints。原型的滚动和固定位置在 2.6 中设置。

第一次搭建时可以采用下面的父子结构。顶层视口使用普通 Frame，内部 `Content` 使用纵向 Auto layout，宽度与视口相同，在 Constraints 中设置左右贴边，高度设为 Hug contents。`Content` 内的卡片和列表就可以把宽度设为 Fill container。该选项用于父级采用 Auto layout 的子项。

```text
Workspace / Glass / Desktop（普通 Frame，1440×1000）
├─ Content（纵向 Auto layout，实际内容高度）
│  ├─ Overview（宽度 Fill container）
│  ├─ Chart（宽度 Fill container）
│  └─ Stock list（宽度 Fill container）
└─ Toolbar（与 Content 同级，原型中设置固定位置）
```

在 `Content` 顶部留出工具栏需要的空间。手机稿沿用这个结构，把视口设为 390×844，再调整内部区域的排列。

下面的布局是样板的起始提案。由你确定最终组合、间距和颜色。

| 区域 | 桌面 Glass 样板 | 手机 Glass 样板 |
| --- | --- | --- |
| 导航 | 带页面留白的悬浮工具栏，搜索与外观入口容易找到 | 精简工具栏，次要导航沿用可展开的 Sheet |
| 首屏 | 股票概览与价格图表形成主区，辩论入口放在次区 | 按标题、概览、图表、下一步操作的顺序叠放 |
| 研究列表 | 搜索与筛选靠近表格，收藏按钮留在公司行内 | 优先呈现公司、价格和收藏，窄屏时表格可在自身容器滚动 |
| 内容阅读 | 图表、数据表和密集文字使用较实的阅读底色 | 保持文字、焦点、表单错误和触控操作清楚可辨 |

按用途把材质分为三类。**背景层**提供柔和颜色变化。**悬浮层**用于导航、工具栏和少量浮层。**阅读层**承载图表、表格、长文字和表单。可以把蓝灰渐变作为第一张草稿，再根据你自己的视觉方向定稿。苹果对 Liquid Glass 的介绍把导航与控件放在独立的功能层，这个层次关系适合用来参考工作台的设计。[Apple WWDC：Meet Liquid Glass](https://developer.apple.com/videos/play/wwdc2025/219/)

### 2.4 建立颜色变量、文字样式和复用组件

1. 在 `02 Design System` 放置一组颜色和文字样板。先建立背景、玻璃表面、阅读表面、正文、辅助文字、边框、焦点、Bull 和 Bear 等语义角色，给每个角色写出用途和数值。
2. 从 Figma 的 Variables 入口创建本地集合，例如 `Counterpoint`，增加 Color 和 Number 变量。颜色角色绑定到 Fill 或 Stroke，间距和圆角绑定到对应数字属性。也可以先用本地 Color styles 配合参数表完成颜色管理。账户支持多个 Modes 时，可进一步为配色建立模式。[Figma：创建变量与集合](https://help.figma.com/hc/en-us/articles/15145852043927-Create-and-manage-variables-and-collections)
3. 用项目已有的 Inter 正文字体建立 Text styles，分别命名标题、正文、辅助文字和数值。把最终字号、字重和行高记录到样板旁，标题的字体选择在评审中确定。
4. 先画按钮、输入框、外观选择器、工具栏和面板容器。选中一项，使用 `Create component` 创建主组件，从 Assets 面板放置实例到页面里。
5. 为默认、悬停、焦点、按下、禁用和错误等实际需要的状态建立 Variants。用 `State`、`Size`、`Appearance` 等独立属性表达差异，页面文案通过组件文字属性调整。修改一次主组件后，确认页面实例能同步更新。[Figma：组件 Variants](https://help.figma.com/hc/en-us/articles/360056440594-Create-and-use-variants)

在参数表中写上代码映射，供实现时查找。下面的名称是建议起点，由定稿中的实际变量统一。

| Figma 名称建议 | Web 对应位置 | 用途 |
| --- | --- | --- |
| `color/background` | `--background` | 页面背景 |
| `color/surface-content` | `--card` | 图表、表格、字段等阅读表面 |
| `color/surface-glass` | 拟在 `glass.css` 中定义的玻璃表面变量 | 悬浮导航、工具栏 |
| `color/foreground`、`color/muted-foreground` | 同名 CSS 语义变量 | 正文和辅助文字 |
| `color/border`、`color/ring` | `--border`、`--ring` | 边界与键盘焦点 |
| `color/bull`、`color/bear` | `--bull`、`--bear` | 涨跌及观点角色 |
| `space/*`、`radius/*` | 设计规范中的间距与圆角规则 | 组件与页面的一致性 |

### 2.5 在 Figma 做 Glass 材质样板，再应用到页面

1. 在背景层放一块柔和渐变，前方放导航面板、阅读卡片和按钮。先用相同背景比较三个表面的层次。
2. 选中导航面板，在 Fill 中调整颜色和透明度，再在 Effects 中添加 `Background blur`。随后调整 Stroke 和 Drop shadow，分别观察面板边界、背景透出和文字对比度。
3. 将文字作为面板里的独立内容层，给它设置明确的文字颜色。以 Fill 的透明度控制面板透光程度，让文字和图标保持清楚。
4. Figma 当前还提供 `Glass` 效果，可以用来探索折射和色散。为每个样板选定一种背景效果，并记录使用的效果类型。交接时将折射等光学表现列入浏览器样板评估，再确定实际实现范围。[Figma：图层效果与 Glass](https://help.figma.com/hc/en-us/articles/360041488473-Apply-effects-to-layers)
5. 在样板上放置一段长文字、一行股票数据、表单错误和键盘焦点状态，再补一张实色表面状态。分别检查复杂背景和简单背景下的阅读情况。

| Figma 属性 | Web 实现起点 | 需要在浏览器校准的内容 |
| --- | --- | --- |
| Fill 的颜色与透明度 | 带 alpha 的背景色 | 背景透出程度与文字对比度 |
| Background blur | `backdrop-filter: blur(...)` | 实际模糊强度、覆盖区域和滚动表现 |
| Layer blur | `filter: blur(...)` | 背景装饰图层自身的模糊 |
| Stroke、Corner radius | `border`、`border-radius` | 边界清晰度与圆角 |
| Drop shadow | `box-shadow` | 阴影的范围、颜色和层次 |

把 Figma 中的参数作为样板起点，浏览器调校后再回填最终值。完成高保真工作台时，至少能够看到新的页面分区、导航材质、阅读表面和完整的内容层级。

### 2.6 连接可点击原型并检查长页滚动

1. 为工作台准备同尺寸的 Light、Dark、Glass 三个完整 Frame，分别展示对应预设的布局与材质。切到 Prototype，给起始工作台设置 Flow 起点，在外观菜单的选项上配置 `On click → Navigate to`，目标指向相应的页面 Frame，让整页完成切换。
2. 连接两条主要路径。一条从工作台进入 AAPL 详情和辩论，另一条从用户页下部进入反馈表单再返回。为搜索弹窗和手机菜单准备浮层 Frame，用 `Open overlay` 打开，并配置关闭动作。组件内部的按钮或选中状态可使用 `Change to` 连接 Variants。反馈错误用需要的页面或字段状态表达。
3. 长页面保持顶层视口高度 1000 或 844，在其内部布置超出视口的内容。开启 `Clip content`，在 Prototype 的滚动设置中选择 Vertical，让 Present 中可以向下浏览完整页面。
4. 选中需要悬浮的工具栏，设置 Fixed 或 Sticky，并检查内容从其下方滚动时的层次。Auto layout 内的固定元素按需要设置为脱离布局流的位置，再验证父层的裁剪关系。[Figma：原型滚动与溢出](https://help.figma.com/hc/en-us/articles/360039818734-Prototype-scroll-and-overflow-behavior)
5. 点击 Present，从工作台实际走完研究路径和反馈入口路径。检查目标区域是否容易找到、手机上按钮能否点击、返回后位置是否合理。记录使用的过渡类型、时长和减少动态效果的实现要求。[Figma：添加原型连接](https://help.figma.com/hc/en-us/articles/31011968186007-FD4B-Add-prototype-connections)

用 Frame 或组件状态表达搜索结果、表单错误和提交回执，在后续 Web 实施阶段连接实际查询与表单行为。

### 2.7 做设计评审并准备交接记录

在 `05 Handoff` 放入定稿链接和下面这张交接清单。逐项确认「首屏先看到什么」「第一个主要操作在哪里」「手机上如何找到导航」，再记录需要调整的地方。

| 交接内容 | 记录方式 |
| --- | --- |
| 设计文件与定稿页面 | 文件链接、桌面 Frame 链接、手机 Frame 链接和确认日期 |
| 设计决策 | v001 的具体问题、版式调整、选择颜色和材质的理由 |
| 组件与状态 | 主组件、实例属性，以及焦点、禁用、错误、加载、空结果等状态 |
| Token 对照 | Figma 变量或样式名称、实际值、对应的 CSS 名称 |
| 响应式规则 | 桌面、手机和中间宽度的区域顺序、导航与换行行为 |
| 交互规则 | 原型起点、返回路径、菜单与弹窗行为、滚动与动效 |
| 开发清单 | 对应的现有组件、需要调整的文件、待验证的问题 |

选择定稿 Frame 后，用 Share 或 `Copy link to selection` 复制精确链接，便于自己、协作者或开发工具定位设计。普通属性面板与参数表可以支持本轮交接，账户有 Dev Mode 时可用它辅助查看属性。把选定方案同步到现有设计规范。[Figma：共享文件与原型](https://help.figma.com/hc/en-us/articles/360040531773-Share-files-and-prototypes) · [视觉与交互规范](design-system.md)

在文件菜单的 Version history 中为关键进度保存具名版本，例如 `Workspace wireframe`、`Workspace visual approved`。本地另存设计导出稿和代码截图，记录对应的 Figma Frame 链接与确认日期。[Figma：版本历史](https://help.figma.com/hc/en-us/articles/360038006754-View-a-file-s-version-history)

## 第 3 步 接入外观选择和材质基础

### 先让三个选项具有清晰的数据模型

让用户选择一个预设，再从预设派生明暗和外观。下面是建议的映射。Glass 首版采用亮色材质，后续有需要时可以扩展另一种组合。

```ts
type ColorMode = "light" | "dark";
type Appearance = "classic" | "glass";
type AppearancePreset = "light" | "dark" | "glass";

const presets: Record<AppearancePreset, { colorMode: ColorMode; appearance: Appearance }> = {
  light: { colorMode: "light", appearance: "classic" },
  dark: { colorMode: "dark", appearance: "classic" },
  glass: { colorMode: "light", appearance: "glass" },
};
```

1. 从主题上下文和 Provider 开始。保留一个预设状态作为唯一来源。应用到根元素时，按 `colorMode` 更新 `.dark` 与浏览器 `color-scheme`，按 `appearance` 更新 `data-appearance`。根元素上的样式变量也能被挂到 `body` 下的 Radix 弹窗和下拉菜单读取。[theme-context.ts](../src/app/providers/theme-context.ts) · [theme-provider.tsx](../src/app/providers/theme-provider.tsx)
2. 保存一个经过校验的预设值，例如 `counterpoint:appearance:v1`。读取顺序为有效的新值、有效的旧 `counterpoint:theme:v1` 值、系统明暗。遇到无效值或浏览器存储受限时，页面仍可使用内存中的选择。检查初次打开和刷新是否出现明显的外观闪烁。
3. 顶部当前是双态图标按钮，用户页是 `Appearance` 选择框。把两处都接到同一个预设状态，显示当前选择。顶部可复用 shadcn/ui 的 DropdownMenu 做单选，用户页可沿用 Select。检查键盘操作、焦点和选中项的文字提示。[app-header.tsx](../src/app/layout/app-header.tsx) · [preferences-panel.tsx](../src/pages/user/preferences-panel.tsx)

这一步完成时，三种选项可以切换，顶部和用户设置同步，旧偏好可以读取，刷新可以恢复，新旧状态可用浏览器验证。

### 然后把 Glass 外观集中到样式层

| 文件或位置 | 负责的内容 |
| --- | --- |
| [tokens.css](../src/styles/tokens.css) | 继续提供 `background`、`foreground`、`card`、`border`、`ring` 及涨跌色等语义变量 |
| 建议新增 `src/styles/glass.css` | 集中定义 Glass 的背景、半透明色、实色备选、描边、阴影和模糊强度，在 `globals.css` 中引入 |
| [components/ui](../src/components/ui) | 复用 shadcn 控件行为，按需为 Card、Dialog、Sheet 和菜单指定表面角色 |
| [layout.css](../src/styles/layout.css) 与 [AppLayout](../src/app/layout/app-layout.tsx) | 管理应用壳的导航、内容区、边距、断点和堆叠层级 |
| [pages](../src/pages) | 负责各路由的区域排布。复用现有功能组件、数据 hooks 和校验规则 |

先写可阅读的实色表面，再用 `@supports (backdrop-filter: blur(1px))` 叠加半透明背景和背后模糊。把玻璃效果放到少量明确的表面，滚动时重点检查悬浮工具栏。初始颜色、透明度和模糊强度由样板试验决定，最终数值回填到设计规范。[MDN：backdrop-filter](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Properties/backdrop-filter)

在支持 `prefers-reduced-transparency` 的环境里，用实色表面响应系统设置。减少透明度和减少动态效果分别验证。Light 和 Dark 也提供一条可直接选用的实色阅读路径。[MDN：prefers-reduced-transparency](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/At-rules/@media/prefers-reduced-transparency)

## 第 4 步 做出完整的工作台样板

1. 打开 Figma 已确认的工作台桌面与手机 Frame，对照标出已有的标题、指标、图表和股票列表。按交接表把 Figma 组件对应到现有 React 组件，再利用 Grid、间距和布局变体重新排布区块。若导航确实需要不同结构，把导航控件与内容容器拆成清楚的组件。[WorkbenchPage](../src/pages/workbench/workbench-page.tsx)
2. 保持 `Outlet` 和有状态组件的 React 位置与 key 稳定。例如 Glass 切换可以改变容器属性和 Grid 布局，使当前查询、图表区间和反馈表单继续挂载。键盘焦点顺序要与内容阅读顺序一致。
3. 给新工具栏和导航应用悬浮材质，给图表和列表应用阅读材质。检查下拉菜单、搜索弹窗和手机 Sheet 在玻璃层之上清楚显示，关闭后焦点能返回触发控件。
4. 在桌面和手机上走一遍工作台流程。搜索 AAPL、切换行业、加入或移除收藏，再打开股票详情。补查加载、空结果、失败重试，以及窄屏下收藏操作是否容易找到。

样板评审时，把 Figma 定稿、v001 工作台和当前 Glass 放在一起，使用相同宽度、数据和页面状态逐区比较。核对字体、间距、卡片大小、模糊观感、焦点和布局断点，记录偏差及修正原因，再把已确认的浏览器参数回填 Figma 和设计规范。通过条件是主要任务可以完整操作，桌面与手机都有清楚的视觉层次，表格与图表保持可读。评审后把验证过的样式提炼为共享组件，供其他页面复用。

## 第 5 步 按业务复杂度推广到全部页面

建议顺序为股票详情、历史与关于、用户与反馈、辩论。每一组先在 Figma 的 Desktop 与 Mobile Sections 补齐对应 Frame，复用已经确认的组件和变量，更新交接链接，再实施和验证。每一组在通过下面的检查后再提交代码。

| 页面 | 样式调整 | 验收动作 |
| --- | --- | --- |
| 工作台 `/` | 工具栏、重点图表、股票列表分区 | 搜索、筛选、收藏、空结果和重试 |
| 股票详情 `/stocks/AAPL` | 图表和指标优先，证据保持清楚的浮层 | 切到 1M 再切 Glass，区间保留；打开证据并返回焦点 |
| 辩论 `/debates/demo-aapl?ticker=AAPL` | 区分角色、消息和回放控制 | 播放、暂停、切换外观后继续、查看证据、保存 |
| 历史 `/history` | 强化日期、股票和摘要的层级 | 搜索、筛选、重开记录、验证删除确认弹窗 |
| 用户 `/user` | 清楚呈现外观设置和下部反馈入口 | 顶部与用户页选择一致；滚动进入反馈再返回入口 |
| 反馈 `/feedback` | 实色阅读区承载字段、错误和附件列表 | 填写并选择合成附件后切换外观，草稿和附件仍可用；验证失败重试和 Demo 回执 |
| 关于 `/about` | 复用字体、间距和内容表面 | 标题层级、导航和源码链接可用，窄屏文字可读 |

先验收同页切换，再验收导航与刷新。特别检查反馈页切换外观时不会出现离开确认，回放切换时仍停在当前进度。调整 TSX 时遵循现有职责与长度约定，优先拆出可命名的区域。[编码与质量规范](engineering-guidelines.md) · [反馈表单与附件设计](forms-and-uploads.md)

## 第 6 步 验收、留档和发布交接

在 `apps/web` 依次执行现有质量检查。Playwright 会启动静态预览，先构建当前版本。缺少 Chromium 时执行 `npx playwright install chromium`。[package.json](../package.json) · [playwright.config.ts](../playwright.config.ts)

```bash
npm run typecheck
npm run lint
npm run format:check
npm run test
npm run build
npm run test:e2e
```

顶部选择器改动会影响现有依赖双态按钮名称的测试。更新该测试，使它验证 Light、Dark、Glass 的选择、刷新恢复，以及至少一个容易因布局切换丢失的真实状态。当前 Playwright 默认 Chromium、1440×1000 和减少动态效果。日常动效、手机触控与 Safari 的渲染需要显式复验，并在记录里区分实测与待测。[导航与布局 E2E](../tests/e2e/flows/navigation-and-layout.spec.ts)

发布前安排一轮手工验收，依次检查布局、键盘、材质和运行状态。

1. **桌面和手机布局。** 三种外观都可切换。用 1440px 与 390px 做截图对照，补查 768px 过渡宽度及放大后的导航、表单和长文本。表格在自身容器内处理需要的横向滚动。
2. **可读性和键盘。** 检查渐变背景上最难读的文字，按现有规范核对对比度。依次用 Tab、Enter 和 Escape 操作导航、主题选择、搜索和弹窗。验证焦点可见、关闭后焦点返回、页面滚动可以恢复。
3. **材质降级和滚动。** 验证模糊关闭时实色表面仍清晰。用相同设备与场景对比 Classic 和 Glass 的长表格滚动、图表区间切换和弹窗操作。发现卡顿时先缩小模糊区域或降低强度，再用同一场景复测。记录设备和实际结果。
4. **运行状态。** 测试首次加载、刷新偏好、切换外观时的输入保留，以及关键深链接。以 Demo 模式验证反馈回执和附件体验，确保页面仍清楚表达提交结果。

将设计稿导出和浏览器截图放进同一个 **v002** 版本目录，以相同文件编号建立对照。

1. 在 Figma 选择已确认稿件，使用右侧 Export 导出 1× PNG。首屏对照使用 1440×1000 或 390×844 的视口 Frame。全页对照时，复制定稿为单独的导出 Frame，将高度扩展到完整内容，并核对顶部导航的位置和页面底部内容。
2. 在浏览器按相同视口、股票、3M 图表和默认交互状态拍摄新截图。保存时等数据、图表和字体加载完成。
3. 在本地 `apps/web/design-snapshots/` 建立独立版本目录，例如 `v002-YYYY-MM-DD-glass/`，用 `figma/desktop/`、`figma/mobile/` 和 `web/desktop/`、`web/mobile/` 保存两类对照图。文件编号沿用 v001 的 `01-workspace` 至 `07-about`。
4. 在版本记录里写下截图日期、样式、路由、视口、代码提交、Figma 文件和 Frame 链接，以及采用的具名版本。对照首屏或全页时，使用同一种导出范围。
5. 用 `git check-ignore -v` 核对截图目录命中规则，再检查暂存内容。查看截图时将 Figma 定稿与实际 Web 按同宽度并排显示，逐页记录接受的差异和需要修正的地方。[Web .gitignore](../.gitignore)

每次提交围绕一个可验证的改动，例如 `feat(web): add glass appearance preference`、`feat(web): build glass workspace layout`、`feat(web): extend glass surfaces across research pages`。PR 说明写具体问题、页面前后变化、测试结果和已知限制。可以根据实际需要另行共享用于评审的截图。当前 Web workflow 的 push 触发分支是 `main` 和 `codex/web-portfolio`，PR 触发目标是 `main`。新开发分支先记录本地检查结果，远程检查以实际运行回执为准。[Web workflow](../../../.github/workflows/web.yml)

正式发布时记录经过验收的源提交、Sites 版本和访问地址，在线复查三态切换、股票详情深链接与反馈 Demo。把上一可用的 Sites 版本保留为回滚入口，并按现有发布文档记录结果。[独立部署与回滚](deployment.md)

## 个人设计与实现记录

每轮配对设计或样板评审填写一条记录，保留你如何从问题走到最终选择。记下自己的判断、AI 提供的帮助和实际完成的操作，方便以后复现与讲解。以下模板可以直接复制到自己的开发记录里。

```text
页面与场景
本轮学习任务和验收目标
我从 v001 看到的问题
我的初步判断与操作前预测
我比较的方案和选定理由
Figma 文件、桌面与手机 Frame 链接
Figma 具名版本和确认日期
我在 Figma 画的桌面与手机布局
我选定的颜色、材质和组件规则
我修改的主组件、变量与原型路径
AI 示范、提示或协助排查的部分
我亲手完成并能再次复现的部分
加入的需求变化和当时观察到的现象
本轮遇到的具体困难
我尝试的修复与最终选择
我实现或调整的代码位置
我用来验证的操作、浏览器和视口
实际结果与需要继续改的地方
对应的代码提交和本地截图版本
下一轮想练习的问题
```

准备作品讲解或面试时，从记录中选一个实际解决的问题，依次讲清使用场景、最初判断、尝试过程、选择原因和验证结果。配合相应 Frame 和前后截图，解释自己与 AI 在这一轮各自承担的工作。例如，搜索栏确实出现过窄屏挤压时，可以展示父子尺寸设置如何影响布局，以及修改后怎样验证长文案和手机宽度。

第一次动手从上面的第一轮练习开始，按需要查阅第 1 步和 2.1–2.3 的具体操作。先在 Figma 完成导航与搜索工具栏的小任务、独立复现和一次需求变化，再逐步扩展工作台的变量、组件、玻璃材质和交互原型。
