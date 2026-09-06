# AI Teacher Copilot（智能作业批改）

AI Teacher Copilot 是一个面向中学教师的智能作业批改与学情分析系统。系统围绕“教师布置作业 → 学生提交作答 → AI 批改 → 教师分析与讲评”建立完整闭环，重点服务数学步骤批改、英语作文评分和班级学情诊断。

> 业务层是本项目实现的 AI Teacher Copilot，底层 Agent（智能体）运行时复用 DeerFlow 2.0。保留底层运行时包、配置兼容和原项目许可证，是为了继续使用成熟的对话、工具、技能、记忆、沙箱和流式执行能力，并不代表产品页面使用 DeerFlow 作为品牌。

## 一、产品能力

### 教师端

- 教师工作台：查看负责的班级、最近作业、完成率和需要关注的学情。
- 班级与学生画像：查看掌握度、薄弱知识点、重复错误、学习趋势和近期表现。
- 作业管理：创建、编辑、发布作业，支持手动录入、题目图片识别和题库选择。
- 作业分析：查看完成率、成绩分布、题目表现、高错题和需要优先讲评的内容。
- Teacher Copilot：通过自然语言查询真实班级、学生、作业和题目数据，并获得讲评或分层练习建议。

### 学生端

- 查看当前账号被分配的作业和题目。
- 为单道题上传手写作答图片。
- 查看图片上传、OCR（光学字符识别）、作答解析、批改和结果组装进度。
- 查看数学步骤分、错误定位、知识点诊断和批改反馈。
- 已完成或失败的题目可以重新选择图片提交。

## 二、批改流程

```text
作业题目
   ↓
学生上传单题作答图片
   ↓
对象存储保存图片
   ↓
OCR 识别并保存文本区块与位置证据
   ↓
按题目学科路由批改
   ├─ 数学：动态识别学生解法并计算步骤分
   └─ 英语：按内容、结构、语法、词汇四个维度评分
   ↓
结构化结果校验与持久化
   ↓
学生结果页、作业分析和学生/班级画像
```

数学批改不强制学生匹配唯一解题路径。模型应根据学生实际书写的步骤判断等式变形、运算和结论，并使用 OCR 区块作为错误证据。英语作文使用固定四维标准，每个维度 0—5 分，总分 20 分。

## 三、页面入口

| 页面 | 地址 |
|---|---|
| 教师工作台 | `/workspace/teacher-copilot/dashboard` |
| 班级列表 | `/workspace/teacher-copilot/classes` |
| 班级详情 | `/workspace/teacher-copilot/classes/{class_id}` |
| 学生画像 | `/workspace/teacher-copilot/students/{student_id}` |
| 作业管理 | `/workspace/teacher-copilot/homeworks` |
| 作业编辑 | `/workspace/teacher-copilot/homeworks/{homework_id}/authoring` |
| 作业分析 | `/workspace/teacher-copilot/homeworks/{homework_id}/analysis` |
| Teacher Copilot 对话 | `/workspace/agents/teacher-copilot/chats/new` |
| 学生作业 | `/workspace/teacher-copilot/student/homework` |
| 学生批改详情 | `/workspace/teacher-copilot/student/grading?homework_id=...&question_id=...` |

页面布局和信息层级参照 AI Teacher Copilot Figma 设计稿中的 Teacher 01—06、Student 07—08 页面。

## 四、项目结构

```text
backend/
├── app/teacher_copilot/
│   ├── api/                 业务 API、登录身份和访问范围
│   ├── db/                  业务模型、数据库初始化和标准分类
│   ├── grading/             OCR、数学/英语批改、结果组装与校验
│   ├── services/            提交、画像、分析和权限服务
│   ├── tools/               教师 Copilot 业务工具
│   └── agents/              Teacher Copilot Agent、技能和中间件
└── packages/harness/deerflow/ DeerFlow Agent 运行时与基础能力

frontend/src/
├── app/workspace/teacher-copilot/ 教师和学生业务页面
├── components/                    共享组件与业务组件
└── core/                          API、国际化、线程和运行时适配

config.teacher-copilot.example.yaml 教师 Agent、工具和技能配置示例
deploy/helm/deer-flow/             Kubernetes 部署模板
```

## 五、本地运行

### 1. 环境要求

- Python 3.12 或更高版本
- Node.js 22 或更高版本
- `uv`
- `pnpm`
- 可访问批改模型、OCR 服务和对象存储服务的网络环境

### 2. 安装依赖

在仓库根目录执行：

```bash
make install
```

准备本地配置：

- 根据 `.env.example` 设置模型和 Gateway（网关）相关变量；
- 根据 `config.example.yaml` 准备根目录 `config.yaml`；
- 将 `config.teacher-copilot.example.yaml` 中的教师 Agent、工具和技能配置合并到实际配置；
- 将批改模型、OCR 和 OSS（对象存储）密钥放入本地环境变量或 `backend/.env`，不要提交。

### 3. 启动开发服务

```bash
make dev
```

默认地址：<http://localhost:3000>。

### 4. 启动本机生产式服务

```bash
./scripts/deploy-local.sh
```

脚本会启动 Gateway（网关后端）和 Next.js 前端。前端代码更新后可以使用：

```bash
./scripts/deploy-local.sh --rebuild
```

停止服务：

```bash
./scripts/deploy-local.sh --stop
```

## 六、数据与配置边界

- 教师和学生页面读取业务数据库中的真实作业、提交、批改、画像和分析数据。
- 业务数据库位于 `backend/tc-data/`，已被忽略，不随公开仓库提交。
- DeerFlow 运行时状态位于 `.deer-flow/`，同样不作为源码发布。
- `.zread/` 是本地生成的代码知识库，已加入忽略规则；本地已有内容保留。
- 普通启动不会重新生成三班业务事实，也不会用临时页面数据替代数据库。
- 登录身份通过 DeerFlow 的登录态映射到教师或学生业务身份；业务工具继续校验对象归属。

## 七、教师 Copilot 工具

当前教师 Copilot 使用业务工具读取真实数据，包括：

- 学生画像与批改历史；
- 班级画像与班级学生；
- 班级作业与作业分析；
- 题目分析；
- 题库搜索。

工具执行沿用底层运行时的对话、工具调用、技能、记忆和必要的任务编排能力。教师身份来自可信登录上下文，不接受对话内容中伪造的教师编号。

## 八、公开仓库与开源说明

公开仓库地址：<https://github.com/jiaqiang000/AI-Teacher-Copilot>。

本项目在 DeerFlow 2.0 开源代码基础上进行业务扩展，保留其底层包和相关内部命名，以便后续同步安全修复、复用运行能力和维护兼容性。原项目及本项目代码遵循仓库中的 MIT License，具体作者署名和许可条款见 [LICENSE](LICENSE)。

项目不提交 API 密钥、Cookie、业务数据库、运行日志或本地用户数据。提交代码前请检查 `.gitignore` 和敏感文件状态。

## 九、开发约定

- 教师业务优先使用已有 DeerFlow 组件、运行时和数据访问边界。
- 业务统计从真实数据库计算，页面不自行制造统计事实。
- 新增页面优先对照 Figma 的信息架构，再复用现有前端组件。
- 代码注释和项目文档使用中文；代码标识符、协议名和底层包名保留原始写法。
- 保留现有 Git 历史，不通过压缩历史或新建无历史分支发布。
