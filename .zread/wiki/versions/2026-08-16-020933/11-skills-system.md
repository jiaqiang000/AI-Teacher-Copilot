# 技能系统

## 架构概述

- **渐进式披露** —— 通过分层加载技能内容（从轻量级元数据到完整指令集，再到按需加载的资源文件），最小化 token 消耗。
- **安全优先隔离** —— 每个技能，无论是内置的还是用户编写的，在影响 Agent 行为之前，都必须经过静态和动态安全扫描。
- **延迟发现** —— 目录仅暴露技能名称，让 LLM 通过 `describe_skill` 工具按需获取元数据，而不是将所有技能描述硬编码到系统提示词中。



## 技能结构与 Frontmatter

### 目录结构

```
skill-name/
├── SKILL.md              ├── scripts/              # 可选 — 可执行代码 (Python, JS, shell)
│   └── generate.py
├── references/           # 可选 — 按需加载到上下文中的文档
│   └── guide.md
├── assets/               # 可选 — 输出中使用的文件 (模板, 图标)
│   └── template.md
├── templates/            # 可选 — 输出模板
│   └── report.md
└── evals/                # 可选 — 测试用例和断言
    └── evals.json
```

### Frontmatter 模式

| 属性 | 类型 | 必需 | 描述 |
|---|---|---|---|
| name | string | 是 | 连字符格式的技能标识符 (^[a-z0-9-]+$)，最长 64 个字符，不允许前导、尾随或连续连字符 |
| description | string | 是 | 触发描述（最长 1024 个字符，不含尖括号）—— 技能激活的主要机制 |
| license | string | 否 | 技能的许可证标识符 |
| allowed-tools | list[string] | 否 | 此技能激活时可用工具的白名单；None 表示允许所有工具 |
| required-secrets | list[string\|object] | 否 | 作为环境变量注入的请求级密钥；每项可以是名称字符串或 {name, optional} 对象 |
| secrets-autonomous | boolean | 否 | 密钥是否可在自主模型加载期间绑定（默认为 true）；false 则限制为仅通过显式 /slash 激活 |



## 技能类别与生命周期

| 类别 | 存储位置 | 可变性 | 描述 |
|---|---|---|---|
| PUBLIC | skills/public/<name>/ | 只读 | 与平台捆绑的内置技能；在沙箱中挂载于 /mnt/skills/public/<name>/ |
| CUSTOM | 用户专用存储目录 | 可编辑、可删除 | 通过 skill_manage 工具创建的用户自定义技能；在沙箱中挂载于 /mnt/skills/custom/<name>/ |
| INTEGRATION | 托管第三方目录 | 只读 | 托管的集成技能；在沙箱中挂载于 /mnt/skills/integrations/<name>/ |
| LEGACY | 全局自定义（迁移前） | 只读 | 用户隔离迁移前的技能；可见但不可编辑；在沙箱中挂载于 /mnt/skills/legacy/<name>/ |



## 渐进式披露模型

`deferred_discovery` 配置标志控制第 1 层是包含完整描述还是仅包含名称。启用时（`SkillsConfig.deferred_discovery = True`），系统提示词仅包含带有逗号分隔名称的 ``，Agent 必须调用 `describe_skill` 来了解每个技能的功能。这保持了系统提示词的紧凑性并有利于前缀缓存，但每次发现会增加一次工具调用往返。



## 发现与激活

### 通过 `describe_skill` 自主发现

```
<skill_system>
You have access to skills that provide optimized workflows for specific tasks.

**Skill Discovery:**
1. Check <skill_index> for a skill name that matches your task
2. Call describe_skill(name) to fetch its description and capabilities
3. If the skill matches, call read_file on the returned location to load full instructions
4. Follow the skill's instructions precisely

<skill_index>
chart-visualization, data-analysis, deep-research, podcast-generation, ...
</skill_index>

Skills are located at: /mnt/skills
</skill_system>
```

| 查询形式 | 语法 | 行为 | 最大结果数 |
|---|---|---|---|
| 精确选择 | select:data-analysis,deep-research | 通过精确名称匹配返回指定技能 | 无限制 |
| 必需前缀 | +podcast gen | 名称中要求包含 podcast，并按 gen 排序 | 5 |
| 自由文本正则 | chart visualization | 对名称 + 描述进行正则匹配；名称匹配得分更高 | 5 |

### 显式斜杠激活

```
/deep-research 比较用于长上下文理解的最新 transformer 架构
```



## 工具策略与能力范围界定

| 始终可用的工具 | 用途 |
|---|---|
| describe_skill | 技能元数据发现 |
| read_file | 读取技能指令和资源 |
| review_skill_package | 技能审查和质量评估 |
| tool_search | 延迟工具发现（不恢复已移除的工具） |



## 安全管道

### 安装安全性

| 保护措施 | 机制 | 缓解的威胁 |
|---|---|---|
| 拒绝路径遍历 | is_unsafe_zip_member 检查绝对路径、.. 组件和冒号 | 目录逃逸、Windows 上的 ADS 走私 |
| 跳过符号链接 | is_symlink_member 检查外部属性 | 基于符号链接的文件替换 |
| 可执行二进制检测 | Magic 字节前缀匹配 (ELF, PE, Mach-O) | 任意二进制执行 |
| Zip 炸弹防御 | 最大未压缩总大小 512MB，最多 4096 个条目 | 资源耗尽 |
| macOS 元数据过滤 | 跳过 __MACOSX 和点文件 | 噪声注入 |

### 静态和动态扫描

-
-

### 文件系统权限强化



## 技能管理工具

| 操作 | 参数 | 描述 |
|---|---|---|
| create | name, content | 使用 SKILL.md 内容创建新的自定义技能 |
| edit | name, content | 替换整个 SKILL.md |
| patch | name, find, replace, expected_count? | 在 SKILL.md 中进行查找和替换 |
| delete | name | 删除自定义技能 |
| write_file | name, path, content | 添加或替换支持文件（脚本、参考等） |
| remove_file | name, path | 移除支持文件 |



## 技能审查与质量契约

### 包快照 (v1)

### 审查事实 (v1)

### 审查报告 (v1)



## 存储与配置

### 路径解析

| 优先级 | 来源 | 示例 |
|---|---|---|
| 1 | 显式 SkillsConfig.path 字段 | path: /data/my-skills |
| 2 | DEER_FLOW_SKILLS_PATH 环境变量 | DEER_FLOW_SKILLS_PATH=/opt/skills |
| 3 | 项目根目录下的 skills/ | ./skills/ |
| 4 | 遗留的仓库根目录候选 | ../skills/（monorepo 兼容性） |

### 用户级存储



## 密钥与密钥绑定



## Frontmatter 验证规则

| 规则 | 约束 | 违规时报错 |
|---|---|---|
| 名称格式 | ^[a-z0-9-]+$（连字符格式） | 验证失败 |
| 名称长度 | 最长 64 个字符 | 验证失败 |
| 名称边界情况 | 无前导/尾随连字符，无连续连字符 | 验证失败 |
| 描述长度 | 最长 1024 个字符 | 验证失败 |
| 描述内容 | 无尖括号（< 或 >） | 验证失败 |
| 意外的键 | 仅接受允许的 frontmatter 属性 | 验证失败 |
| allowed-tools | 必须是非空字符串列表 | 验证失败 |
| required-secrets | 必须是列表（字符串或带有 name 的对象） | 验证失败 |
| secrets-autonomous | 必须是布尔值 | 验证失败 |



## 后续步骤

-
-
