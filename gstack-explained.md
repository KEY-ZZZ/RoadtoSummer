# gstack 项目流程解析

---

## 一、通俗易懂版

### 这是什么？

想象你是一个独立开发者，有一个很好的产品想法，但以前你一个人做意味着：写代码、自己检查有没有 bug、自己做设计评审、自己写测试、自己发布……每一步都要你亲力亲为。

gstack 做的事情就是：**把 Claude Code 这个 AI 编程助手，变成一整个虚拟团队**。你一个人，但背后像有 CEO、工程主管、设计师、安全官、QA 工程师在帮你工作。

---

### 整体流程（就像做一个功能）

```
你有一个想法
     ↓
1. 开会讨论（/office-hours）
     ↓
2. 做计划（/autoplan）
     ↓
3. 写代码（正常写，AI 帮你）
     ↓
4. 检查代码（/review）
     ↓
5. 在浏览器里测试（/qa）
     ↓
6. 发布上线（/ship）
     ↓
7. 上线后监控（/canary）
```

每一步都是一个"斜杠命令"，打出来 AI 就自动执行那个角色的工作。

---

### 每个步骤在干什么？

#### 第一步：跟 AI 开"头脑风暴会" — `/office-hours`
就像找 YC 的导师谈你的想法。AI 扮演一个既懂产品又懂工程的顾问，帮你想清楚：这个功能到底要不要做？用户真正需要的是什么？有没有更简单的方案？

#### 第二步：自动跑完所有评审 — `/autoplan`
这一步相当于 AI 替你开了四个会：
- **CEO 视角**：这个功能值不值得做，商业价值够不够
- **工程视角**：架构合不合理，有没有技术债
- **设计视角**：用户体验有没有问题，界面逻辑对不对
- **开发体验视角**：API 好不好用，代码结构清不清晰

四个角色开完会，给你一份最终计划，你确认一下就能动手了。

#### 第三步：写完代码后做代码审查 — `/review`
AI 扮演一个挑剔的 reviewer，把你的代码改动从头到尾检查一遍，找逻辑错误、安全漏洞、代码风格问题，就像公司里的 Pull Request 被同事 review 一样。

#### 第四步：真实浏览器里测试 — `/qa`
gstack 内置了一个"一直开着的浏览器"。AI 会自动打开你的网站，像真实用户一样点来点去，看看有没有加载失败、按钮没反应、表单提交出错之类的问题。这个浏览器是长驻的，不用每次都重新打开，所以登录状态、Cookie 都保留着。

#### 第五步：安全审查 — `/cso`
专门检查常见的安全漏洞，比如 SQL 注入、XSS 攻击、权限控制不当等。跑完之后给你一份报告。

#### 第六步：一键发布 — `/ship`
自动帮你：合并分支 → 跑测试 → 更新版本号 → 写 Changelog → 提交代码 → 创建 PR。你只需要最后确认一下。

#### 第七步：上线后持续监控 — `/canary`
发布之后 AI 继续在浏览器里盯着，看看上线的版本有没有出现新的问题。

---

### 有什么特别的设计？

**浏览器一直开着**：传统方式是每次测试都重新打开浏览器（要等 3-5 秒），gstack 让浏览器作为后台进程一直运行，每次操作只需要 100 毫秒左右。而且登录状态不会丢失。

**全是 Markdown 文件**：每个"技能"（skill）的行为规则都写在 `.md` 文件里，任何人都可以看懂、修改。不是黑盒，不需要懂编程才能调整 AI 的行为。

**记忆系统（GBrain）**：AI 会记住你项目里学到的东西，下次再开会话可以接着用，不用每次从头解释背景。

---

### 一句话总结

> gstack 就是把"一个人做产品"这件事，从"你一个人干所有事"变成"你指挥一支AI团队干所有事"，靠的是一套写好的规则文件，加上一个常驻的真实浏览器。

---

---

## 二、详细正式版

### 1. 项目定位与设计哲学

gstack 是一套面向 Claude Code CLI 的开源工作流增强框架，由 Y Combinator CEO Garry Tan 开发并维护，MIT 协议。其核心设计目标是通过角色分化的 Prompt 模板体系（Skills），将 AI 辅助编程从单一问答模式提升为具备完整软件工程生命周期覆盖能力的多角色协作流程。

设计哲学来自三个原则（详见 `ETHOS.md`）：
- **Boil the Lake（烧干湖）**：AI 降低了完整实现的边际成本，因此应始终选择完整方案而非快捷方案。
- **Search Before Building（先搜索再构建）**：复用运行时内置能力优先于重新实现，避免引入不必要的依赖。
- **Completeness is Cheap（完整性成本趋零）**：在 AI 辅助下，过去需要数天的任务可以压缩到分钟级，因此不应以"成本高"为由跳过测试、文档或边界条件处理。

---

### 2. 系统架构层次

```
┌─────────────────────────────────────────────────────┐
│                   用户 / Claude Code                  │
└──────────────────────────┬──────────────────────────┘
                           │ 斜杠命令触发 (Skill)
┌──────────────────────────▼──────────────────────────┐
│              Skills 层（Markdown 模板）               │
│  /office-hours  /autoplan  /review  /qa  /ship  …   │
│  每个 skill = SKILL.md.tmpl → 生成 SKILL.md          │
└──────────────────────────┬──────────────────────────┘
                           │
         ┌─────────────────┼────────────────────┐
         ▼                 ▼                    ▼
┌────────────────┐ ┌──────────────┐ ┌─────────────────────┐
│  Browse 引擎   │ │  Design CLI  │ │  GBrain 记忆系统      │
│  (Bun 编译     │ │  (GPT Image  │ │  (Supabase 持久化    │
│   Chromium CDP)│ │   API)       │ │   跨会话知识库)       │
└────────────────┘ └──────────────┘ └─────────────────────┘
```

#### 2.1 Skills 层

所有技能均以 Markdown 格式定义。`SKILL.md.tmpl` 是编辑源，通过 `bun run gen:skill-docs` 渲染为可供 Claude Code 读取的 `SKILL.md`。模板引擎支持 Resolver 机制（位于 `scripts/resolvers/`），可注入通用的 Preamble、设计规范、代码审查标准等模块化内容，避免重复定义。

每个 `SKILL.md` 包含：
- **frontmatter**：元数据（name、version、description、allowed-tools、triggers）
- **Preamble**：会话初始化 Shell 脚本（检查更新、加载配置、读取项目记忆）
- **步骤化指令**：用自然语言描述的执行逻辑（非 Shell 脚本，Claude 负责解析执行）

#### 2.2 Browse 引擎（持久化浏览器守护进程）

Browse 引擎是 gstack 最关键的基础设施，解决了 AI 与真实浏览器交互的两个核心问题：**延迟**和**状态丢失**。

架构设计：

```
Claude Code
    │  工具调用：$B snapshot -i
    ▼
CLI 二进制（Bun 编译，~58MB）
    │  POST /command → localhost:PORT
    ▼
Server（Bun.serve）
    │  CDP 协议
    ▼
Chromium 进程（长驻守护）
    │  - 持久化 Cookie / Session
    │  - 多 Tab 保持
    │  - 30 分钟空闲自动退出
```

性能特征：首次启动约 3 秒；后续每次工具调用约 100-200 毫秒。

CLI 二进制使用 `bun build --compile` 编译为单文件可执行程序，无需运行时依赖。Cookie 解密通过 Bun 内置 SQLite 直读 Chromium 的 Cookie 数据库，无需 `better-sqlite3` 等 Native Addon。

**安全架构（v1.6.0.0+）**：  
守护进程绑定两个 HTTP Listener——本地监听器（127.0.0.1，完整命令集）和隧道监听器（锁定白名单 26 条浏览器驱动指令 + scoped token）。ngrok 仅转发隧道端口，根级 token 请求返回 403。SSE 端点通过 `POST /sse-session` 签发 30 分钟 HttpOnly Cookie，与命令端点 token 严格隔离。

**Prompt 注入防御**（多层 ensemble）：

| 层级 | 模块 | 作用域 |
|------|------|--------|
| L1-L3 | content-security.ts | 服务端 + 代理端 |
| L4 | TestSavantAI ONNX 分类器（112MB） | 仅代理端 |
| L4b | Claude Haiku 转录分类器 | 仅代理端 |
| L5 | Canary 字符串注入检测 | 服务端 + 代理端 |
| L6 | combineVerdict ensemble | 服务端 + 代理端 |

阻断条件：ML 内容分类器 AND 转录分类器同时 ≥ 0.75 才触发 BLOCK，避免单层高置信度误报（Stack Overflow 指令场景的 FP 缓解机制）。

---

### 3. 核心工作流详解

#### 3.1 产品决策阶段 — `/office-hours`

触发场景：用户有功能想法或产品问题，需要结构化分析。

执行逻辑：AI 扮演 YC 创业顾问角色，通过一系列问题框架提炼：
1. 用户真实需求（区分需求与解决方案）
2. 功能的商业价值与优先级
3. 最简可行路径（识别"湖"与"海"的边界）

输出：结构化的功能描述文档，供后续评审阶段使用。

#### 3.2 多角色计划评审阶段 — `/autoplan`

`/autoplan` 是 CEO → Design → Eng → DX 四条评审链的自动化串联，遵循 6 条自动决策原则，仅在"品味判断"类问题（接近方案间的权衡、边界 scope、Codex 与 Claude 意见分歧）时暂停询问用户。

| 子评审 | 对应 Skill | 关注维度 |
|--------|-----------|---------|
| CEO Review | /plan-ceo-review | 战略价值、用户影响、Scope 合理性 |
| Design Review | /plan-design-review | 用户体验、信息架构、视觉一致性 |
| Eng Review | /plan-eng-review | 架构选型、技术债、可测试性 |
| DX Review | /plan-devex-review | API 设计、代码可读性、开发者摩擦 |

输出：通过所有评审的最终实现计划，含 risk list 和 scope 决策记录。

#### 3.3 代码审查阶段 — `/review`

基于 `git diff` 对当前分支与 base branch 的差异进行全量审查，覆盖：
- **功能正确性**：逻辑漏洞、边界条件、竞态条件
- **安全性**：OWASP Top 10 相关模式，含 SQL 注入、XSS、权限绕过
- **性能**：N+1 查询、不必要的同步阻塞、内存泄漏风险
- **代码质量**：命名一致性、抽象合理性、冗余代码

审查结果分级：BLOCK（必须修复才能继续）/ WARN（建议修复）/ NOTE（参考意见）。

#### 3.4 浏览器 QA 阶段 — `/qa`

`/qa` 调用 Browse 引擎，对目标 URL 执行行为驱动测试，流程：

1. 导航至目标页面，截取初始快照
2. 遍历主要用户路径（golden path）：登录 → 核心功能 → 边界场景
3. 捕获交互截图，标注异常元素
4. 对比 before/after 状态差异（DOM diff + 视觉 diff）
5. 输出带截图证据的 Bug Report

`/qa-only` 为只输出报告不自动修复的只读变体，适合 CI 集成。

#### 3.5 安全审计阶段 — `/cso`

基于 OWASP Top 10 + STRIDE 威胁建模框架，对代码库进行静态分析，输出包含：
- 威胁分类（Spoofing / Tampering / Repudiation / Information Disclosure / DoS / Elevation of Privilege）
- 每条发现的严重级别（Critical / High / Medium / Low）
- 修复建议与参考代码示例

#### 3.6 发布阶段 — `/ship`

自动化执行完整发布序列：

```
Step 1   检测 base branch（main/master/动态识别）
Step 2   merge origin/<base> 到当前分支
Step 3   运行项目测试套件（读取 CLAUDE.md 中的 test 命令）
Step 4   运行 /review 全量代码审查
Step 5   确定 VERSION bump 级别（patch/minor/major）
Step 6   更新 VERSION 文件
Step 7   生成 CHANGELOG 条目（用户视角，聚焦交付价值，非实现细节）
Step 8   Commit（包含 VERSION + CHANGELOG）
Step 9   Push 到 remote
Step 10  gh pr create（带结构化 PR 描述）
Step 11  可选：触发 /canary 上线后监控
```

VERSION 遵循四段式 `X.Y.Z.W` 格式（workspace-aware），bump 级别语义：PATCH（<500 行，无新用户功能）/ MINOR（新能力，>2000 行变更）/ MAJOR（破坏性变更或里程碑级发布）。

CHANGELOG 写作约束：
- 以用户视角描述"现在能做什么"，而非"改了什么代码"
- 禁止出现分支内部版本号、评审过程记录、plan approval 信息
- 必须包含数字化指标（性能变化、压缩比等），无数据时不编造

#### 3.7 上线监控 — `/canary`

`/canary` 在 `ship` 后持续循环执行浏览器探测，验证：
- 关键页面可访问性（HTTP 200 / 非 5xx）
- 核心交互路径可用性
- 性能指标未出现显著回退（LCP、FID 等）

检测到异常时自动触发 `/investigate`（根因分析技能），输出具体异常截图 + 复现路径。

---

### 4. 辅助基础设施

#### 4.1 GBrain 跨会话记忆系统

GBrain 将项目维度的知识（决策记录、已知 bug 、代码约定）持久化至 Supabase，通过 `gstack-brain-*` 系列 CLI 工具管理。每次 Skill Preamble 执行时自动加载当前项目的 learnings（`~/.gstack/projects/{slug}/learnings.jsonl`），无需用户在每次会话中重新提供背景。

#### 4.2 测试分层体系

| 层级 | 触发方式 | 成本 | 覆盖范围 |
|------|---------|------|---------|
| Tier 1：静态验证 | `bun test`（<2s） | 免费 | Skill 格式合规、模板渲染正确性 |
| Tier 2：LLM-as-Judge | `bun run test:evals`（~$0.15） | 低 | Skill 行为质量评估 |
| Tier 3：E2E 浏览器测试 | `bun run test:e2e`（~$3.85） | 中 | 真实 `claude -p` 端到端验证 |

E2E 测试采用 diff-based 选择机制：仅运行与当前分支改动相关的测试文件（依赖声明在 `test/helpers/touchfiles.ts`），避免全量运行开销。CI 仅运行 `gate` tier（安全护栏 + 确定性功能测试）；`periodic` tier（质量基准、Opus 模型测试）按周触发或手动运行。

#### 4.3 Slop Scan 代码质量检测

集成 [slop-scan](https://github.com/benvinegar/slop-scan) 工具，专门检测 AI 生成代码的典型质量退化模式：
- 空 catch 块吞没文件操作错误（应使用 `safeUnlink()` / `safeKill()`）
- 冗余 `return await`（无 try 块时应移除）
- 字符串匹配错误消息（脆弱的模式，应使用类型判断）

明确区分"需修复的质量问题"与"不应修复的正确模式"（如扩展代码的 catch-and-log、清理路径的 swallowAll catch），避免为通过 lint 而引入工程上更差的代码。

---

### 5. 安装与团队协作模式

```bash
# 个人安装（30 秒）
git clone --single-branch --depth 1 \
  https://github.com/garrytan/gstack.git \
  ~/.claude/skills/gstack && \
cd ~/.claude/skills/gstack && ./setup

# 团队模式（所有成员自动获得 gstack，无版本漂移）
(cd ~/.claude/skills/gstack && ./setup --team) && \
~/.claude/skills/gstack/bin/gstack-team-init required && \
git add .claude/ CLAUDE.md && \
git commit -m "require gstack for AI-assisted work"
```

团队模式通过 `gstack-update-check`（每小时限速一次，网络故障静默跳过）在每次 Skill Preamble 执行时自动检查更新，无需手动维护版本一致性。

`required` 参数在 CLAUDE.md 中写入强制要求；替换为 `optional` 则为建议模式。

---

### 6. 平台兼容性说明

Browse 引擎编译二进制为平台特定：`bun build --compile` 在各平台分别生成 arm64/x64 可执行文件（约 58MB）。`./setup` 脚本在每台机器上本地编译，因此 `browse/dist/` 和 `design/dist/` 目录中的文件**永远不应提交到 git**（尽管历史原因已被 track，staging 时必须手动排除）。

---

*文档基于 gstack v1.x，核心架构参考 `README.md`、`ARCHITECTURE.md`、`CLAUDE.md`、`ETHOS.md`。*
