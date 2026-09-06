# Teacher Copilot 启动说明(就地扩展版本)

本项目基于 DeerFlow 2.0 二次开发,Teacher Copilot 业务代码在 DeerFlow 项目内就地扩展:
后端业务模块 `backend/app/teacher_copilot/`,技能 `skills/public/`,评测 `evals/`,
前端页面在 `frontend/src/` 既有路由内新增。DeerFlow 核心代码保持原样。

## 1. 环境准备

```text
Python 3.12+ / Node.js 22+ / uv(可选 uv sync)
依赖:MySQL 8(或默认 SQLite 零依赖,演示可用)、Redis(画像缓存,可禁用)
模型:云端 API(数学 Qwen3.5-4B / DeepSeek v4 Flash、OCR GLM-OCR),密钥由用户提供;
      密钥未配置时批改走 mock 退路(宪法 VII:先报告再实现,不硬扛)
```

## 2. 数据初始化

```bash
cd AI-Teacher-Copilot/backend
# 建表 + 写入标准分类字典与题库 Fixture
uv run python -m app.teacher_copilot.db.init_db --seed
# (可选)写入演示数据(teacher_01 / class_03 八三班 / 30 学生 / hw_004)
uv run python - <<'PY'
import asyncio
from app.teacher_copilot.db.engine import init_db, dispose_db
from app.teacher_copilot.config.settings import get_config
from app.teacher_copilot.db.seed.demo import seed_demo

async def main():
    cfg = get_config()
    await init_db(cfg.database_url)
    await seed_demo()
    await dispose_db()

asyncio.run(main())
PY
```

## 3. 启动

```bash
# 后端 Gateway(挂载了 teacher_copilot 路由:T004)
cd AI-Teacher-Copilot && make dev            # 或 uv run --project backend uvicorn app.gateway.app:app

# 前端
cd frontend && npm install && npm run dev

# 验证:GET /api/teacher-copilot/healthz → {"status":"ok","service":"teacher_copilot"}
```

## 4. 配置合并

将 `config.teacher-copilot.example.yaml` 中 Agents/Tools/Sub-Agents/Extensions
合并到 deer-flow 主配置(复制 config.example.yaml 为 config.yaml 后合并);
环境变量(TC_ 前缀)见 `backend/app/teacher_copilot/config/settings.py`。

## 5. 卡点清单(宪法 VII)

1. 模型/OCR 云端 API 密钥(LLM_SMALL_API_KEY / LLM_STRONG_API_KEY / OCR_API_KEY)
2. MySQL/Redis 实例(未提供时默认 SQLite + 禁用 Redis)
3. Figma 设计文件访问权限(UI 对照用,非硬依赖)


## 6b. 评测与验收(参考 quickstart 场景 H)

```bash
cd backend
# 确定性算法门禁(Profile/Analysis,不依赖 LLM)
python3 -m evals.runtime.run --gate profile_algorithm
python3 -m evals.runtime.run --gate analysis_calculation
```
门禁结果:Profile 6/6、Analysis 5/5(已实测通过)。

## 6c. 关键待办与卡点(宪法 VII)

1. **图片公网 URL**:学生上传图片需先传至阿里云 OSS 等对象存储,取公网链接后
   传入 OCR(见 models/clients/ocr.py 待办注释与 tasks.md Notes)。
2. **前端运行**:完整前端需 `cd frontend && npm install && npm run dev`
   (本次未执行 npm install,页面为 MVP 演示级,按 Figma 信息架构实现)。

## 6. 前端页面(对照 Figma 设计稿,宪法 VIII)

Teacher 01-06 / Student 07-08 共 8 页,见 plan.md 前端设计基准节。
