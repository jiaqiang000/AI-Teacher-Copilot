/**
 * 关于页面的项目说明。内容直接内嵌，避免在 Turbopack 下引入原始 Markdown 文件。
 */
import { APP_VERSION } from "@/version";

export const aboutMarkdown = `# 智能作业批改 ${APP_VERSION}

> AI Teacher Copilot：让每一份作业都被看见。

智能作业批改面向中学教师，提供作业发布、学生作答、AI 批改、学情分析和教师 Copilot 一体化能力。

## 主要能力

- **作业管理**：支持手动录入、题目图片识别和题库选择。
- **学生批改**：上传单题手写作答图片，查看 OCR（光学字符识别）、解析、批改和结果组装进度。
- **数学步骤批改**：尊重学生的实际解法，输出步骤分、错误诊断和证据区块。
- **英语作文评分**：按内容、结构、语法、词汇四个维度评分，总分 20 分。
- **学情分析**：查看班级、学生、作业和题目的真实数据分析。
- **教师 Copilot**：通过业务工具查询学情，并生成讲评和分层练习建议。

## 数据说明

页面展示的数据来自业务数据库和批改服务。教师与学生的访问范围由登录身份和业务归属校验共同决定；本项目不使用页面临时数据替代真实业务结果。

## 开源底座

本项目在 DeerFlow 2.0 开源运行时基础上进行教育业务扩展，复用其 Agent（智能体）、工具、技能、记忆、沙箱、线程和流式执行能力。底层包和内部命名保持兼容，方便后续维护与升级。

## 项目仓库

[AI Teacher Copilot GitHub 仓库](https://github.com/jiaqiang000/AI-Teacher-Copilot)

## 许可证

本项目遵循仓库中的 MIT License。原始开源项目及贡献者致谢见 [LICENSE](https://github.com/jiaqiang000/AI-Teacher-Copilot/blob/main/LICENSE)。
`;
