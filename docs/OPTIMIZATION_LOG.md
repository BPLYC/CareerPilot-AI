# CareerPilot AI 优化日志

本文件记录 2026-07 优化轮次中每个 slice 的实际改动与验证输出。设计依据是
`docs/superpowers/specs/2026-07-23-project-optimization-design.md`。

记录原则：验证部分贴真实命令输出，不贴预期输出。未能验证的项明确标注为未验证，
不含糊带过。

## 改动前基线

在任何改动之前实测（2026-07-23）：

| 项目 | 结果 |
| --- | --- |
| `pytest` | 26 passed |
| `eval/run_eval.py` | exit 0，重新生成两个 CSV |
| Python 源码行数 | 2842 行（`src/` + `app.py` + `tests/`） |
| DeepSeek 余额 | 6.01 元人民币 |

环境注意事项：本环境下 pytest 必须带 `--basetemp`，否则用到 `tmp_path` 的
`tests/test_run_history.py` 会因沙箱禁止访问共享临时目录而报 `PermissionError`，
表现为 "25 passed, 1 error" 的假失败。

## Slice 1: 工程基建

### 动机

仓库缺少三样基础设施，导致后续所有优化都没有安全网：

1. 无 `.github/workflows/` —— 没有 CI。所有验证依赖人工在本地跑，且只在 Windows
   单一环境下跑过。
2. 无 `pyproject.toml`，无 linter 配置。代码风格问题（未使用的 import、import
   顺序）无法自动发现。
3. 无集中的优化记录文件。历史决策散落在 `IMPLEMENTATION_PLAN.md` 的时间线里。

### 改动

- 新增 `pyproject.toml`：项目元数据、ruff 配置（E/F/I/B/UP 规则集）、pytest 配置。
  忽略 E501 行长检查，因为 Streamlit UI 中的长字符串手工折行反而更难读，且
  `app.py` 会在 slice 7 拆分。
- 新增 `.github/workflows/ci.yml`：在 Ubuntu 上以 Python 3.11 和 3.12 双版本运行
  ruff、pytest 与 evaluation 冒烟测试。CI 不配置 `DEEPSEEK_API_KEY`，因此绿灯即
  证明离线确定性路径未被破坏。
- 新增本文件 `docs/OPTIMIZATION_LOG.md`。

### ruff 首次扫描结果

在既有代码上首次运行 ruff，报出 64 个问题：

```text
24	UP006	[*] non-pep585-annotation
13	I001 	[*] unsorted-imports
13	UP035	[-] deprecated-import
 6	UP015	[*] redundant-open-modes
 5	UP045	[*] non-pep604-annotation-optional
 1	E402 	[ ] module-import-not-at-top-of-file
 1	F401 	[*] unused-import
 1	UP017	[*] datetime-timezone-utc
Found 64 errors.
```

全部属于机械性问题，符合本 slice「只修机械性问题」的约定：

- `UP006` / `UP035` / `UP045`：`List[str]` → `list[str]`、`Optional[X]` → `X | None`。
  项目要求 Python 3.11+，PEP 585/604 写法可用。
- `I001`：import 排序。
- `UP015`：`open(path, "r")` 中冗余的 `"r"`。
- `F401`：未使用的 import。
- `UP017`：`datetime.timezone.utc` → `datetime.UTC`。

`ruff check . --fix` 修复 69 处（含修复过程中新暴露的问题），剩 1 处 `E402`：
`eval/run_eval.py:12` 在 import `src` 之前操作 `sys.path`。这是脚本独立运行所
必需的写法，不是缺陷，因此在 `pyproject.toml` 中为该文件添加 per-file-ignore，
而不是改动代码。

值得记录的一点：`src/workflow/state.py` 中 `Annotated[List[str], add]` 被改写为
`Annotated[list[str], add]`。`Annotated` 的元数据在运行时保留，LangGraph 的
reducer 语义不受影响 —— `tests/test_workflow.py` 中真正 invoke 编译图的那条测试
在改动后仍然通过，可作为佐证。

### 计划外发现：评估工具既不可复现，也在偷偷花钱

在用 `eval/run_eval.py` 验证 ruff 改动无回归时，生成的 CSV 与仓库中已提交的
版本出现大范围差异。逐项排查后发现差异与 ruff 无关，而是评估工具本身的两个缺陷。

**缺陷一：评估会静默调用真实 LLM。**

`src/services/provider_config.py:13` 在模块导入时调用 `load_dotenv()`。
python-dotenv 会向上层目录搜索 `.env`，实测确认：

```text
find_dotenv -> D:\CareerPilot_AI\.env
can_use_llm -> True
```

上面这次运行的工作目录是 worktree，其中并没有 `.env`，但仍然找到了上层仓库根目录
的那一份。因此在任何配置过 API key 的机器上（也就是 README 记录的标准配置），
`python eval/run_eval.py` 都会走真实 LLM 路径。后果有三：

- 每次运行都花钱。实测两次 live 运行共消耗约 0.14 元人民币。
- 每次运行结果都不同，无法作为回归判据 —— 而本轮优化的每个 slice 都依赖它做验证。
- `src/services/comparison_evaluation.py:1` 的 docstring 与项目文档均称评估路径
  "reproducible"，与实际行为不符。

**缺陷二：检索结果依赖 git 不跟踪的机器状态。**

`src/rag/build_vectorstore.py` 依据 `data/vectorstore/` 是否存在来决定走 Chroma
还是 markdown 回退。该目录被 `.gitignore` 忽略，因此全新 checkout 与运行过应用的
机器会走不同的检索路径。

**修复。** 为 `eval/run_eval.py` 增加显式的模式选择：

- 默认确定性运行 —— 清除 `DEEPSEEK_API_KEY` / `DEEPSEEK_MODEL`，并设置
  `CAREERPILOT_DISABLE_VECTORSTORE` 强制 markdown 检索。
- `--live` 显式选择真实 LLM 调用，并在 stdout 打印模式说明。

把安全的行为设为默认、把花钱的行为设为显式，符合仓库所有者设定的预算约束。

**关于 14 → 8 的差异。** 修复后 `avg_rag_snippet_count` 从已提交的 14.0 变为 8.0。
排查确认这不是回归，而是已提交的 CSV 本身是陈旧数据。当前知识库实测：

```text
chunks per collection: Counter({'resume_bullets': 2, 'star_examples': 2,
                                'skill_taxonomy': 2, 'application_examples': 1,
                                'interview_bank': 1})
vectorstore -> Chroma
chroma doc count -> 8
total snippets -> 8
```

Chroma 路径与 markdown 路径都返回 8 条，因为知识库总共只有 8 个 chunk，而
`retrieve_context()` 一共请求 16 条（5+3+3+2+3）。已提交的 14.0 生成于知识库或
分块逻辑变更之前，此后未重新生成。本 slice 用当前确定性结果覆盖它。

需要指出的是，`CAREERPILOT_DISABLE_VECTORSTORE` 在当前知识库规模下不改变任何
数字（两条路径都返回全部 8 条）。它的价值在于消除对未跟踪状态的依赖 —— 一旦
知识库增长到超过 k，两条路径就会分叉。

**顺带记录一个尚未处理的问题**：知识库规模（8 chunk）远小于检索请求量（16 条），
因此检索总是返回全部内容，对比表中的 `rag_snippet_count` 指标实际上没有在衡量
检索质量。这属于知识库内容工作，不在本轮优化范围内。

### 验证

```text
$ ruff check .
All checks passed!

$ pytest --basetemp=.pytest_tmp
28 passed in 1.78s
```

测试数从 26 增至 28，新增的两条在 `tests/test_eval_determinism.py`，用于锁定本
slice 建立的复现性保证：`CAREERPILOT_DISABLE_VECTORSTORE` 能关闭向量库，且
`use_deterministic_agents()` 确实清除了 LLM 凭据。

评估的复现性用连续两次运行的文件哈希比对来验证：

```text
Mode: deterministic. Pass --live to call the real LLM.
elapsed_1=3s
elapsed_2=2s
results_identical=True
summary_identical=True
```

修复前一次 live 运行耗时 4-5 分钟且结果每次不同，修复后 3 秒且逐字节一致。

DeepSeek 余额：本 slice 开始 6.01 元，结束 5.87 元，消耗约 0.14 元 —— 全部来自
修复前那两次误调真实 API 的评估运行，修复后的确定性运行不产生任何调用。需要说明
的是，DeepSeek 的账单结算存在延迟，余额读数不适合当作精确的单次计量表；离线运行
未发起网络调用的可靠证据是耗时（3 秒 vs 4-5 分钟）与逐字节可复现性。

### 与设计文档的偏离

spec 中 slice 1 写明「不改动任何现有业务代码」。实际改动了
`eval/run_eval.py` 与 `src/rag/build_vectorstore.py`。

理由：slice 1 的目的是建立可信的回归安全网，而后续 8 个 slice 全部依赖
`eval/run_eval.py` 作为验证手段。一个每次返回不同数字、且每次运行都花钱的工具
不构成安全网。若不在此处修复，后面每个 slice 的「指标未回退」验证都是无效断言。

改动范围控制在评估路径与检索开关上，未触及任何 agent 或工作流逻辑。

