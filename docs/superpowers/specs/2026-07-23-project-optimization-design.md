# CareerPilot AI 优化设计文档

Date: 2026-07-23
Branch: `claude/project-optimization-e559bf`
Status: Approved by user

## 背景

CareerPilot AI 的 MVP 与 Phase 2 功能已经完成（约 2842 行 Python，26 个测试通过）。本轮工作不是加功能优先，而是先偿还在快速迭代中积累的架构债，再在稳固的地基上补测试和新功能。

用户确认的优化方向覆盖四个方面：代码质量与架构重构、测试与健壮性、性能与成本、UI/UX 与产品功能。用户授权真实调用 DeepSeek API 做验证，接受 slice 4 的行为变更风险，并欢迎新增功能。

## 代码审查发现的问题

### P1. 编译好的 LangGraph 从未在运行路径上执行

`src/workflow/careerpilot_graph.py:154` 在模块加载时执行 `graph = build_graph()`，编译出一个 `CompiledStateGraph`。但：

- `app.py:51` 调用的是 `stream_workflow()`，即同文件里手写的顺序 runner。
- `src/services/comparison_evaluation.py:91` 的 "CareerPilot Full" 方法调用 `run_workflow()`，它同样只是 `stream_workflow()` 的包装。
- `graph` 对象只在 `tests/test_workflow.py:60` 一处被 `invoke`。

后果：项目的核心技术卖点在真实运行时是装饰性的；路由逻辑存在两份实现（`stream_workflow` 的 if/while 控制流 与 `build_graph` 的 conditional edges），任何一边修改都会造成行为漂移，而现有测试无法捕获这种漂移。

### P2. Prompt 中嵌入 Python dict 的 repr 而非 JSON

`src/agents/match_scoring_agent.py:58`：

```python
+ f"\nResume profile:\n{resume_profile}\nJD analysis:\n{jd_analysis}\nRetrieved context:\n{state.get('retrieved_context', {})}"
```

发送给模型的是 `{'name': 'Zhang', 'skills': ['Python']}` 这样的 Python 字面量，使用单引号、`None`、`True` 等非 JSON 记法。这既浪费 token，也削弱模型输出合法 JSON 的倾向 —— 与文档中反复记录的 "DeepSeek schema drift" 问题存在因果关联。

### P3. 十个 agent node 复制同一段控制流

每个 node 都是：

```python
try:
    if can_use_llm():
        <build prompt>
        result = invoke_structured(...)
    else:
        result = fallback_xxx(...)
    return {"<key>": result, "workflow_trace": [trace]}
except Exception as exc:
    result = fallback_xxx(...)
    return {"<key>": result, "errors": [...], "workflow_trace": [...]}
```

差异只在 schema 类、prompt 内容、fallback 函数和 trace 文案。样板代码淹没了各 node 真正的业务逻辑。

### P4. 模块边界错位

`KNOWN_SKILLS` 常量定义在 `src/agents/resume_parser_agent.py:12`，却被 `src/agents/jd_analyzer_agent.py:6` 反向 import。技能词表是领域数据，不属于任何单个 agent。

### P5. 独立节点串行执行

`resume_parser_node` 与 `jd_analyzer_node` 之间没有数据依赖（前者读 `raw_resume_text`，后者读 `raw_jd_text`），但工作流串行执行两者，在 LLM 路径上等于两次串行网络往返。项目已经在 Phase 2 证明了并行模式可行。

### P6. 缺少工程基建

- 无 `.github/workflows/` —— 没有 CI。
- 无 `pyproject.toml`，无 linter/formatter 配置。
- 无任何 parser 测试；`src/parsers/` 三个模块零覆盖。
- 全部 26 个测试都跑 fallback 路径，agent 的 LLM 分支零覆盖。
- 无 logging，所有异常靠 `except Exception` 吞掉后转成字符串塞进 `errors`。

### P7. UI 层问题

- `app.py` 263 行容纳 6 个 tab 的全部渲染逻辑。
- 侧边栏在每次 Streamlit rerun 时写 `os.environ`（`app.py:75,80,90`），用进程级全局状态传递 UI 配置。
- `app.py:216` 的签证/薪酬提示无条件渲染，即使用户还没运行过分析。

## 优化方案

分 9 个 slice。每个 slice 独立可合并，顺序执行，前三个是后续所有工作的地基。

### Slice 1: 工程基建

新增 `pyproject.toml`（ruff 配置、项目元数据）、`.github/workflows/ci.yml`（在 Ubuntu 上跑 ruff + pytest）、`docs/OPTIMIZATION_LOG.md` 骨架。

不改动任何现有业务代码。CI 必须在当前代码状态下通过 —— 若 ruff 报出既有问题，本 slice 只修机械性问题（未使用 import、格式），语义修改留给后续 slice。

验收：CI workflow 文件语法有效；本地 `ruff check` 与 `pytest` 均通过。

### Slice 2: 统一 agent 骨架

在 `src/agents/common.py` 中新增一个高阶函数，封装 P3 中的重复控制流。各 node 退化为声明式配置：schema 类、system prompt、prompt 构造函数、fallback 函数、trace 文案生成函数。

这是纯重构：现有 26 个测试不做修改，必须原样通过。

验收：`pytest` 26 个测试全绿；`src/agents/` 总行数显著下降；每个 node 文件不再包含 try/except 样板。

### Slice 3: 模块边界与 prompt 序列化

- `KNOWN_SKILLS` 迁至 `src/services/skill_taxonomy.py`，两个 agent 都从新位置 import。
- prompt 中所有结构化数据改为 `json.dumps(..., ensure_ascii=False)` 序列化，修复 P2。
- prompt 拼装逻辑收敛到 `src/services/prompts.py`。

验收：`pytest` 通过；一次真实 DeepSeek 端到端运行，`errors=0`，输出记入日志。

### Slice 4: LangGraph 归位（用户已确认接受风险）

`stream_workflow()` 改为优先使用编译好的 `graph.stream()`；仅当 `graph is None`（langgraph 未安装）时降级到现有手写 runner。手写 runner 保留为 fallback，不删除。

风险：trace 条目的产生顺序、reducer 的列表合并语义在两条路径下可能存在细微差异。

缓解：新增一致性测试，对同一输入分别跑 graph 路径和 fallback 路径，断言两者的关键输出等价（match score、bullet 数量、Phase 2 产物数量、trace 中出现的 node 集合）。该测试在本 slice 中先于实现编写。

验收：一致性测试通过；`pytest` 全绿；`eval/run_eval.py` 重新生成的 CSV 中 "CareerPilot Full" 各项指标与改动前一致；一次真实 DeepSeek 端到端运行成功。

### Slice 5: 并行化与可配置超时

- `resume_parser` 与 `jd_analyzer` 并行执行（graph 路径用 fan-out/join，fallback 路径复用 `ThreadPoolExecutor` 模式）。
- `src/services/llm_client.py:47-48` 硬编码的 `max_retries=2` 与 `request_timeout=60` 提升为 `provider_config` 中可通过环境变量配置的项，保持现有值为默认。

验收：并行执行体现在 trace 中；`pytest` 通过；真实 DeepSeek 运行记录改动前后的端到端耗时对比。

### Slice 6: 测试补强

- `tests/test_parsers.py`：TXT / PDF / DOCX 的正常路径与边界情况（空文件、损坏内容、缺失可选依赖、未知扩展名）。
- mock LLM 客户端，覆盖各 agent 的 LLM 分支与 LLM 抛异常时的 fallback 分支。
- 补齐 `structured_output` 已知 schema drift 之外的边界。

验收：`pytest` 通过且测试数显著增加；`src/parsers/` 与 agent 的 LLM 分支不再零覆盖。

### Slice 7: app.py 拆分与副作用清理

- 6 个 tab 的渲染逻辑拆分到 `src/ui/tabs/` 下的独立模块，`app.py` 仅保留装配。
- 侧边栏配置改为通过显式参数传递给 `get_provider_config()`，不再写 `os.environ`。
- 修复 P7 中签证提示无条件渲染的问题。

验收：`pytest` 通过；Streamlit 本地启动返回 HTTP 200；手动确认 6 个 tab 渲染正常。

### Slice 8: 报告导出（新功能）

Match Report 与 Resume Tips 一键导出为 Markdown 文件下载。导出内容包含匹配分数、匹配/缺失技能、优化后的 bullet、申请回答草稿、面试练习题，并保留 AI 生成内容的审阅提示。

验收：导出函数有单元测试；UI 中下载按钮可用。

### Slice 9: 多 JD 批量对比（新功能）

针对真实使用场景 —— 学生同时投递多个实习岗位。输入一份简历与多份 JD，复用现有工作流逐一分析，输出按匹配分数排序的对比视图，标出各岗位的共同缺失技能。

复用现有的 `run_workflow` 与缓存机制，不新增 LLM 调用模式。

验收：批量分析逻辑有单元测试；UI 新增 tab 可用；`pytest` 通过。

## 每个 Slice 的统一工作流程

1. 若涉及行为变更，先写测试（slice 4 的一致性测试尤其如此）。
2. 实现改动。
3. 运行 `pytest`（`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`）。
4. 运行 `eval/run_eval.py`，确认指标未回退。
5. slice 3、4、5 额外跑一次真实 DeepSeek 端到端。
6. 将问题证据（含文件行号）、改动、验证命令与**真实输出**、结论写入 `docs/OPTIMIZATION_LOG.md`。
7. 单独 commit（一个 slice 一个 commit），push 到 `claude/project-optimization-e559bf`。
8. 同步更新 `docs/IMPLEMENTATION_PLAN.md` 与 `AGENTS.md`。

全部完成后开 PR 供用户 review 合并。

## 不做的事

- 不改变 DeepSeek 作为 OpenAI 兼容端点的集成方式。
- 不硬编码模型名或 API key。
- 不破坏确定性 fallback 行为 —— 无 API key 时测试必须仍能全部通过。
- 不持久化简历原文或 JD 原文。
- 不做与上述 slice 无关的重构。

## 验证基线

改动前的基线，用于回归判断：

- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q` → 26 passed
- `python eval/run_eval.py` → 生成 `outputs/evaluation_results.csv` 与 `outputs/evaluation_comparison_summary.csv`
- Streamlit 本地启动 → HTTP 200
