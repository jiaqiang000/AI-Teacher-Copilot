# 沙箱与文件系统

## 抽象沙箱接口



## Provider 架构与生命周期



## Provider 实现

| Provider | 类路径 | 隔离性 | 后端 | 热池 | 适用场景 |
|---|---|---|---|---|---|
| LocalSandbox | deerflow.sandbox.local:LocalSandboxProvider | 无（宿主机进程） | 宿主机文件系统 | N/A（单例） | 本地开发、受信任环境 |
| AioSandbox | deerflow.community.aio_sandbox:AioSandboxProvider | Docker 容器 | 本地 Docker 或远程 HTTP | 是（LRU 淘汰） | 生产环境、多租户 |
| E2BSandbox | deerflow.community.e2b_sandbox:E2BSandboxProvider | 云端 VM (E2B SDK) | E2B 云 API | 是（带容量管理） | 远程隔离、弹性伸缩 |
| Boxlite | deerflow.community.boxlite:BoxliteProvider | OCI VM (BoxLite) | BoxLite 运行时 | 是（跳过回收检查） | 轻量级 OCI 隔离 |

### LocalSandbox

### AioSandboxProvider

### E2BSandboxProvider 和 BoxliteProvider



## 虚拟路径映射与文件系统抽象

### LocalSandbox 中的路径解析

| 方向 | 方法 | 目的 |
|---|---|---|
| 容器 → 宿主机 | _resolve_path_with_mapping() | 在文件系统访问前转换 Agent 路径 |
| 宿主机 → 容器 | _reverse_resolve_path() | 将命令输出中的宿主机路径转换回虚拟形式 |
| 命令注入 | _resolve_paths_in_command() | 执行前重写 bash 命令中的路径 |
| 输出脱敏 | _reverse_resolve_paths_in_output() | 从 stdout/stderr 中清除宿主机路径 |

### 文件操作锁



## 安全：环境策略与能力管控

### 环境变量清洗

- **通配符模式**（`*KEY*`、`*SECRET*`、`*TOKEN*`、`*PASS*`、`*CREDENTIAL*`、`*DSN*`）捕获任何其大写名称中包含这些标记的变量，包括 `DB_PASS` 等缩写形式和 `GIT_ASKPASS` 等凭证助手。
- **精确名称黑名单**涵盖不含 KEY/SECRET 标记但通常会嵌入密码的连接字符串变量（`DATABASE_URL`、`REDIS_URL`、`MYSQL_PWD`、`PGSERVICEFILE` 等）。

### 本地 Bash 管控

### 输出大小限制

| 工具 | 配置键 | 默认值 | 截断策略 |
|---|---|---|---|
| Bash | bash_output_max_chars | 20,000 | 中间截断（头 + 尾） |
| 读取文件 | read_file_output_max_chars | 50,000 | 头部截断 |
| 列目录 | ls_output_max_chars | 20,000 | 头部截断 |
| 写入文件 | DEERFLOW_WRITE_FILE_MAX_BYTES (环境变量) | 80 KB | 拒绝超大写入 |



## SandboxMiddleware：图状态集成



## 配置参考



## 架构总结



## 后续步骤

- 要了解沙箱如何连接到 LLM 后端，请参阅 。
- 了解 Agent 轮次间的沙箱状态持久化，请参阅 。
- 了解包含沙箱容器网络的 Docker 部署策略，请参阅 。
- 要了解护栏如何与沙箱工具输出交互，请参阅 。
