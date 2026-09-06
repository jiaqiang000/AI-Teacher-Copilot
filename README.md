# AI Teacher Copilot（智能作业批改）

<!-- Codex 原生差异展示测试：第二次 -->

面向中学教师的智能作业批改与学情分析系统。教师可以创建和发布作业，学生上传单题作答图片，系统完成真实 OCR（光学字符识别）、数学步骤批改或英语作文评分，并将结果沉淀为可查询的学生与班级学情数据。

> 本项目的业务能力由 AI Teacher Copilot 实现，底层 Agent（智能体）运行时复用 DeerFlow 2.0 的开源能力。仓库保留底层运行时包、环境变量兼容和原项目许可证，以保证后续复用与升级。

## 核心能力

- 教师工作台：查看班级概览、最近作业和待处理情况。
- 作业管理：支持手动录入、题目图片识别和题库选择，发布前校验题目信息。
- 学生作答：按题目上传手写作答图片，批改中显示 OCR、解析、批改和结果组装阶段。
- 数学批改：根据学生实际解法动态拆分步骤，提供步骤分、错误诊断和证据区块。
- 英语作文批改：按照内容、结构、语法、词汇四个维度评分，总分 20 分。
- 学情分析：提供作业完成率、成绩分布、高错题、知识点和学生画像。
- Teacher Copilot：通过作业批改相关的业务工具和技能，用自然语言查询班级、学生、作业与题目数据。

## 页面入口

- 教师工作台：`/workspace/teacher-copilot/dashboard`
- 班级管理：`/workspace/teacher-copilot/classes`
- 作业管理：`/workspace/teacher-copilot/homeworks`
- Teacher Copilot 对话：`/workspace/agents/teacher-copilot/chats/new`
- 学生作业：`/workspace/teacher-copilot/student/homework`

页面结构参照 AI Teacher Copilot 的 Figma 设计稿，业务数据由后端接口和真实运行库提供。

## 本地启动

### 环境要求

- Python 3.12+
- Node.js 22+
- `uv`
- `pnpm`
- 可访问批改模型、OCR 服务和对象存储服务的网络环境

### 安装依赖

```bash
make install
```

根据 [`.env.example`](.env.example) 和 [教师配置示例](config.teacher-copilot.example.yaml) 准备本地配置。密钥放在本地环境变量或 `backend/.env` 中，不要提交到仓库。

### 启动开发服务

```bash
make dev
```

启动后访问：<http://localhost:3000>。

### 本地生产式启动

```bash
./scripts/deploy-local.sh
```

脚本会启动 Gateway（网关后端）和前端服务。首次部署账号或迁移已有业务数据时，按照 `docs/部署.md` 操作；系统不会在普通启动时重新生成演示业务数据。

## 代码结构

```text
backend/app/teacher_copilot/       作业、提交、批改、画像、分析和业务工具
backend/packages/harness/deerflow/ DeerFlow Agent 运行时与基础能力
frontend/src/app/workspace/        教师和学生业务页面
frontend/src/components/           共享界面与业务组件
frontend/src/core/                 API、国际化、线程和运行时适配
config.teacher-copilot.example.yaml 教师 Agent、工具和技能配置示例
deploy/helm/deer-flow/             Kubernetes 部署模板
```

## 数据与安全

- 教师 Copilot 使用当前登录身份查询真实业务数据，并校验班级、学生、作业和题目归属。
- 业务数据库、运行时状态、日志和本地密钥不随仓库提交。
- `.zread/` 是本地生成的代码知识库，已加入忽略规则，但不会删除本地内容。
- 用户作答图片和模型密钥属于敏感数据，部署时请使用自己的存储和密钥配置。

## 开源说明

本项目基于 DeerFlow 2.0 进行业务扩展，复用其 Agent、工具、技能、记忆、沙箱、线程和流式运行能力。底层源码及其依赖关系保持原样，具体许可证和原作者署名见 [LICENSE](LICENSE)。

项目中文详细说明见 [README_zh.md](README_zh.md)。
