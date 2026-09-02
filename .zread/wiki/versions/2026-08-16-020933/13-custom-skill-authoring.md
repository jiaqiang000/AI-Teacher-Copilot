# 自定义技能编写

## 技能结构与渐进式披露

| 层级 | 加载内容 | 时机 | 预算 |
|---|---|---|---|
| 元数据 | YAML frontmatter 中的 name + description | 始终在上下文中 | 约 100 词 |
| SKILL.md 正文 | 完整的 Markdown 指令 | 当技能触发时（自主触发或 /slash 触发） | 理想情况下 <500 行 |
| 捆绑资源 | scripts/、references/、assets/、templates/ | 按需——由 Agent 读取或执行 | 无限制 |

```
skill-name/
├── SKILL.md                 （必需 —— YAML frontmatter + Markdown 正文）
├── scripts/                 （可执行的 Python/shell —— 确定性任务）
├── references/              （按需加载到上下文中的文档）
├── assets/                  （模板、图标、字体 —— 用于输出）
├── templates/               （输出格式模板）
└── evals/                   （测试用例和评分固定装置）
    └── evals.json
```

## Frontmatter Schema 与校验

### 允许的 Frontmatter 属性

| 属性 | 类型 | 必需 | 约束条件 |
|---|---|---|---|
| name | string | ✅ | 连字符格式 (^[a-z0-9-]+$)，不允许前导/尾随/双连字符，最长 64 个字符 |
| description | string | ✅ | 无尖括号 (< 或 >)，最长 1024 个字符 |
| license | string | ❌ | 自由文本许可证标识符 |
| allowed-tools | list[string] | ❌ | 技能可使用的工具白名单；None = 所有工具，[] = 无工具 |
| required-secrets | list | ❌ | 技能所需的环境变量；每项为字符串或 {name, optional} 映射 |
| secrets-autonomous | bool | ❌ | 默认 true；false 将密钥绑定限制为仅在显式 /slash 激活时生效 |
| metadata | object | ❌ | 任意元数据 |
| compatibility | object | ❌ | 必需的工具/依赖声明 |
| version | string | ❌ | 版本标识符 |
| author | string | ❌ | 作者署名 |

### 校验流水线

-
-
-

## `skill_manage` 工具接口

### 操作参考

| 操作 | 目的 | 关键参数 | 安全扫描 |
|---|---|---|---|
| create | 创建新技能 | name, content (完整的 SKILL.md) | 静态 + 运行时 |
| edit | 替换整个 SKILL.md | name, content | 静态 + 运行时 |
| patch | 在 SKILL.md 中查找并替换 | name, find, replace, expected_count | 静态 + 运行时 |
| delete | 删除自定义技能 | name | 无（仅元数据） |
| write_file | 添加/更新支持文件 | name, path, content | 静态 + 运行时（若是脚本则包含可执行文件） |
| remove_file | 移除支持文件 | name, path | 无 |

### 并发模型

### 历史记录跟踪

## 存储架构与用户隔离

### 目录布局

```
<host_root>/public/<name>/SKILL.md                    ← 全局，只读
<user_custom_root>/<name>/SKILL.md                    ← 按用户，读-写
<integrations_root>/<provider>/<name>/SKILL.md        ← 全局，只读
<user_custom_root>/.history/<name>.jsonl              ← 按用户历史记录
<user_skills_root>/_skill_states.json                 ← 按用户启用状态
<global_custom_root>/<name>/SKILL.md                  ← 旧版回退，只读
```

### 旧版迁移与影子挂载语义

### 技能分类

| 分类 | 枚举值 | 可变性 | 存储位置 |
|---|---|---|---|
| PUBLIC | "public" | 只读 | 全局 skills/public/ |
| CUSTOM | "custom" | 读-写 | 按用户 <user_custom_root>/ |
| INTEGRATION | "integrations" | 只读 | 全局 integrations 根目录 |
| LEGACY | "legacy" | 只读（可见） | 全局 skills/custom/ 回退 |

### 按用户启用状态

## SkillScan：确定性静态安全

### 规则分类

| 领域 | 规则数 | 阻断严重性 | 捕获内容 |
|---|---|---|---|
| 包结构 | 11 | 路径遍历、绝对路径、符号链接、嵌套的 SKILL.md、超大的归档/文件、可执行二进制文件、隐藏的敏感文件、.git 目录 | 恶意或格式错误的归档负载 |
| 密钥检测 | 3 | 嵌入的私钥、云/API 令牌、类密钥环境变量赋值 | 技能内容中的凭据泄露 |
| 声明分析 | 4 | 提示词覆盖短语、敏感能力、敏感宿主路径、外部端点 | SKILL.md 中的提示词注入和能力滥用 |
| Python 代码分析 | 8 | 动态 exec、shell 执行、数据泄露、环境变量转储、反弹 shell、动态导入、subprocess 使用、敏感路径读取、不安全的反序列化 | scripts/*.py 中的恶意代码 |
| Shell 脚本分析 | 6 | 反弹 shell、敏感数据泄露、curl 管道传输 shell、破坏性命令、环境变量转储 | scripts/*.sh 中的恶意 shell 脚本 |

### 归档预检

### 静态 + 运行时扫描组合

## 斜杠激活与目录检索

### 斜杠命令解析

### 目录搜索

| 查询形式 | 语法 | 行为 |
|---|---|---|
| 精确选择 | select:data-analysis,deep-research | 返回名称完全匹配的技能 |
| 必需前缀 | +podcast gen | 名称中要求包含 podcast，按 gen 相关性排序 |
| 自由文本正则 | chart visualization | 对名称 + 描述进行正则匹配；名称匹配得分更高 |

## Skill-Creator 元技能工作流

### 评估系统 Schema

| 字段 | 类型 | 描述 |
|---|---|---|
| skill_name | string | 必须与 frontmatter 的 name 匹配 |
| evals[].id | integer | 唯一标识符 |
| evals[].prompt | string | 要执行的用户任务 |
| evals[].expected_output | string | 人类可读的成功描述 |
| evals[].files | string[] | 可选的输入文件路径（相对于技能根目录） |
| evals[].expectations | string[] | 可验证的成功声明 |

### 描述优化

## 技能审查与生产就绪

### 就绪级别

| 级别 | 含义 | 触发条件 |
|---|---|---|
| blocked | 未就绪——存在确定性或语义阻断 | CRITICAL 扫描发现、提示词注入、缺失必填字段 |
| revise | 未就绪——无阻断，但存在错误或重大问题 | HIGH 发现、完整性缺陷、描述问题 |
| publish_candidate | 在评估范围内已就绪 | 未发现重大问题 |

### 保障级别

| 级别 | 所需证据 |
|---|---|
| static_only | 仅限静态事实和语义检查 |
| trigger_checked | 执行了正负路由用例并保留了相关产出 |
| behavior_verified | 行为断言通过了已审查包摘要的验证 |
| regression_verified | 比较了包与基线，并保留了输出和评分证据 |

## 编写模式与最佳实践

### 描述编写

### 指令风格

### 输出格式定义

### 领域组织

```
cloud-deploy/
├── SKILL.md (workflow + selection logic)
└── references/
    ├── aws.md
    ├── gcp.md
    └── azure.md
```

### 长度管理

## 完整编写清单

| 阶段 | 操作 | 工具/文件 |
|---|---|---|
| 1. 捕获意图 | 采访用户，识别触发上下文，定义输出格式 | 对话 |
| 2. 起草 SKILL.md | 编写 frontmatter (name, description) + Markdown 正文 | 文本编辑器或 skill_manage(action="create") |
| 3. 验证 | 运行 quick_validate.py 检查 frontmatter | skills/public/skill-creator/scripts/quick_validate.py |
| 4. 持久化 | 在 DeerFlow 沙箱中调用 skill_manage(action="create") | skill_manage 工具 |
| 5. 测试 | 在 evals/evals.json 中编写 2-3 个真实的提示词 | evals/evals.json |
| 6. 评估 | 运行评估循环，审查定性和定量结果 | run_eval.py, generate_review.py |
| 7. 迭代 | 调用 skill_manage(action="edit") 或 action="patch" 进行改进 | skill_manage 工具 |
| 8. 优化描述 | 运行描述优化器以提高触发准确性 | improve_description.py |
| 9. 审查 | 调用 skill-reviewer 进行生产就绪审计 | review_skill_package 工具 |
| 10. 扩展 | 增加测试集多样性，大规模重新运行评估 | aggregate_benchmark.py |
