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

## Slice 2: 统一 agent 骨架

### 先更正一处此前的表述

设计文档与 slice 2 的任务标题都写作「消除 10 处重复控制流」。实际逐个读过
`src/agents/` 后确认是 **6 处**，不是 10 处。

有 LLM 分支、因而复制了同一段 try/except 的节点是：`resume_parser`、
`jd_analyzer`、`match_scoring`、`resume_optimizer`、`application_answer`、
`interview_coach`。

另外 4 个节点 —— `rag_retriever`、`low_match_warning`、`final_report`、
`reflection` —— 是纯确定性节点，没有 LLM 调用，也没有这段样板。它们本来就不该被
算进来。

### 动机

6 个节点各自手写了同一段控制流：

```python
try:
    if can_use_llm():
        result = <LLM 调用>
    else:
        result = <fallback>()
    <可选的后处理>
    return {key: result, "workflow_trace": [成功文案]}
except Exception as exc:
    result = <fallback>()
    return {key: result, "errors": [...], "workflow_trace": [失败文案]}
```

复制粘贴的控制流真正的代价不是行数，而是**两条分支会各自漂移**。实际已经漂移了
两处：

1. `match_scoring_agent.py`：低分警告只在成功分支计算。若 LLM 调用失败、
   fallback 打出低于 45 分的成绩，`warnings` 键根本不会出现在返回值里 ——
   UI 上那条「这个岗位可能不适合你」的提示就消失了。
2. `application_answer_agent.py`：`enforce_sensitive_question_boundaries()`
   只在成功分支调用。这个函数负责把签证、担保、薪酬类问题的答案强制交还给申请人，
   属于安全边界。错误分支绕过了它。

第二处在当前代码下不产生实际危害，因为 `fallback_application_answers()` 内部
已经对敏感问题做了处理，等价于再跑一遍。但依赖「另一个函数恰好也做了这件事」
来保证安全边界，是不该留着的结构。

### 改动

`src/agents/common.py` 新增 `run_node()`，把上述控制流收敛为一处。节点退化为
声明式配置：节点名、输出键、LLM 分支、fallback 分支、trace 描述函数，以及可选的
`refine`（后处理）与 `extra_state`（派生状态）。

关键设计决定：`refine` 与 `extra_state` **在两条分支上都执行**。这正是修复上述
两处漂移的方式 —— 派生状态和输出净化不再依赖于「哪条分支产生了结果」。

同时合并了两个近乎相同的 JSON 数组解析辅助函数
（`invoke_structured_array` 与 `invoke_interview_array`）为
`common.invoke_structured_list()`。

### 关于行数

净变化为 +214 / -179，基本持平 —— `common.py` 增加了 58 行共享骨架，抵消了
6 个节点各自减少的样板。收益不在行数：

| | 之前 | 之后 |
| --- | --- | --- |
| try/except/fallback 控制流副本 | 6 份 | 1 份 |
| JSON 数组解析辅助函数 | 2 份 | 1 份 |
| 错误路径与成功路径可能分叉 | 是 | 否 |

### 验证

行为保留的核心证据是评估输出逐字节不变：

```text
Mode: deterministic. Pass --live to call the real LLM.
=== diff vs slice-1 committed CSVs ===
OUTPUTS IDENTICAL - behaviour preserved
```

确定性路径上，重构前后的每一项指标完全相同。

```text
$ ruff check .
All checks passed!

$ pytest --basetemp=.pytest_tmp
31 passed in 1.72s
```

现有 28 个测试未作任何修改即通过。新增 3 个测试在
`tests/test_agent_fallback.py`，用于钉住错误路径上被修正的行为 —— 因为评估的
确定性路径不会触发 LLM 失败，覆盖不到这部分：

- LLM 失败时低分警告仍然产生。
- LLM 失败时敏感问题边界仍然强制执行。
- `run_node()` 记录失败原因的同时仍返回可用输出。

写这三个测试时，第三个一开始是失败的。原因是测试本身写错了：`tests/conftest.py`
会清除 API key，`can_use_llm()` 返回 False，`run_node()` 因此根本没进入 LLM 分支，
自然也不会有错误可记录。补上 `monkeypatch` 后通过 —— 也就是说，如果不显式伪造
凭据，这类测试会在完全没有验证失败处理的情况下「通过」。

DeepSeek 余额：未发生调用，本 slice 不产生费用。

## Slice 3: 模块边界与 prompt JSON 序列化

### 更正一处此前的判断

在设计文档中，把「prompt 里插入 Python dict repr」列为浪费 token 的问题。实测后
确认**这个判断是错的**：

```text
resume_profile: repr=1105 chars, json=1105 chars
jd_analysis:    repr=598 chars,  json=598 chars
match_report:   repr=437 chars,  json=437 chars
```

单引号与双引号长度相同，字符数完全一致。token 成本不是这里的问题。

### 真正的问题

问题在于格式一致性。所有 system prompt 都以「Return strict JSON only」结尾，
而 user prompt 递给模型的是 **不合法的 JSON**：

```text
valid JSON when parsed as-is?
  resume_profile: NO -> Expecting property name enclosed in double quotes: line 1 column 2
  jd_analysis:    NO -> Expecting property name enclosed in double quotes: line 1 column 2
```

样本数据中出现 220 处单引号。更麻烦的是含撇号的值会让 repr 在同一个对象内部
切换引号风格：

```text
repr: {'note': "the applicant's project", 'score': None, 'verified': True}
json: {"note": "the applicant's project", "score": null, "verified": true}
```

简历文本中撇号极其常见（"Dean's List"、"Master's degree"），因此这不是理论
边界情况。要求模型输出严格 JSON，却拿引号风格不一致的 Python 字面量做示范，与
项目文档中反复记录的 schema drift 存在合理的因果关系。

`None` / `True` 与 JSON 的 `null` / `true` 的差异在当前样本中未出现（计数为 0），
但一旦有可选字段为空即会出现。

### 改动

- 新增 `src/services/prompts.context_block(**sections)`，将命名段落统一渲染为
  JSON。4 个节点（`match_scoring`、`resume_optimizer`、`application_answer`、
  `interview_coach`）的 prompt 拼装改用它。字符串按原样传递，不做多余引号包裹。
- 新增 `src/services/skill_taxonomy.py`，承载 `KNOWN_SKILLS` 与
  `find_known_skills()`。此前该常量定义在 `resume_parser_agent.py`，由
  `jd_analyzer_agent.py` 反向 import —— 一个 agent 为了共享领域数据而依赖另一个
  agent。两个 agent 现在都从新模块获取。

### 验证

```text
$ ruff check .
All checks passed!

$ pytest --basetemp=.pytest_tmp
39 passed in 1.79s

$ python eval/run_eval.py
Mode: deterministic. Pass --live to call the real LLM.
OUTPUTS IDENTICAL - behaviour preserved
```

新增 8 个测试（`tests/test_prompts.py`），断言渲染结果确实可被 `json.loads`
解析、撇号不再切换引号风格、不可序列化的值不会抛异常、以及技能表的行为。

真实 DeepSeek 端到端验证（预算闸退出码 0，余额 5.82 元）：

```text
model=deepseek-v4-pro thinking=disabled effort=low
ResumeParserNode: Extracted 3 projects, 9 skills, 1 work experiences.
JDAnalyzerNode: Identified 4 required skills, 4 preferred skills, 6 keywords.
RAGRetrieverNode: Retrieved 8 knowledge snippets from local knowledge base.
MatchScoringNode: Score = 65/100. 9 matched skills, 4 missing skills.
ResumeOptimizerNode (Iteration 0): Generated 10 bullet suggestions.
ReflectionNode (Iteration 0): 0 issue(s) found. Finalizing.
PhaseTwoParallelNode: Running application answers and interview coaching in parallel.
ApplicationAnswerNode: Drafted conservative application answer starters.
InterviewCoachNode: Generated 10 interview practice questions.
FinalReportNode: Analysis complete. Report ready.
errors=0
score=65  bullets=10  interview_questions=10  custom_answers=1
```

关键证据不是 `errors=0`，而是 **10 条 trace 中没有任何一条包含
「Fallback used.」**。slice 2 的统一骨架规定：LLM 分支一旦失败即改用确定性
fallback 并在 trace 中标记。因此这次运行证明 6 个 LLM 节点全部成功解析了结构化
输出，没有任何一个静默退化 —— 这正是 JSON 化 prompt 想要达到的效果。

需要说明的是，单次运行无法证明 schema drift 已被消除，只能证明未引入回归。
真正的判据需要多次运行的统计，而在当前预算下不划算。

本次运行的余额变化：调用前 5.82 元，调用后读数仍为 5.82 元 —— DeepSeek 账单结算
有延迟，单次调用的费用尚未落账。本 slice 实际累计消耗见下一 slice 的读数。

## Slice 4: LangGraph 归位到真实运行路径

这是本轮唯一带行为变更风险的改动，仓库所有者已明确确认接受该风险。

### 动机

`build_graph()` 在模块加载时编译出一个 `CompiledStateGraph`，但它从未出现在任何
真实执行路径上：

- `app.py` 调用 `stream_workflow()` —— 同文件中手写的顺序执行器。
- `comparison_evaluation.py` 的「CareerPilot Full」方法调用 `run_workflow()`，
  它同样只是 `stream_workflow()` 的包装。
- 编译出的 `graph` 对象只在 `tests/test_workflow.py` 的一条测试里被 invoke。

也就是说，项目的核心技术卖点在生产路径上是装饰性的。更实际的代价是：路由规则、
反射循环上限、Phase 2 扇出结构被表达了两遍，改动其中一边不会有任何测试报警。

### 先写测试

按 spec 要求，一致性测试先于实现改动编写，这样任何既有分歧会表现为测试失败，
而不会被误记为「切换引擎导致的行为变化」。

`tests/test_workflow_parity.py` 对同一输入分别运行两个引擎，比较用户可见的结果：
分数、匹配/缺失技能、相关项目、bullet 数量与文本、面试题数量、申请回答键、
自定义回答、警告、错误数、反射状态、以及 trace 中出现过的节点集合。覆盖正常匹配、
低匹配、带自定义申请问题三种情形。

刻意不比较 trace 的顺序与文案 —— 两个引擎对并行 Phase 2 节点的交错方式不同，
这属于允许的差异。

**结果：在切换之前，5 条一致性测试全部通过。** 两个引擎在确定性路径上本就一致，
用户接受的风险没有兑现。这个结论只有先写测试才能得到；先改实现再测的话，通过
与否都无法区分「本来就一致」和「改对了」。

### 改动

`stream_workflow()` 现在优先使用编译好的图，`graph is None`（langgraph 未安装）
时降级到顺序执行器。顺序执行器保留，未删除。

实现上使用 `graph.stream(..., stream_mode=["updates", "values"])` 双模式：
`updates` 提供节点名，`values` 提供 LangGraph 自身 reducer 计算出的完整状态。
配对两者，意味着累积状态来自 LangGraph 而非本文件里的第二套合并实现 ——
这正是消除双重语义的关键。

并行的 Phase 2 节点会连续产生两个 `updates` 后才有一个 `values`，两者都记在
join 之后的状态上，因为那是任一节点输出真正可观测的最早时刻。

### 切换过程中发现的陷阱

`run_workflow()` 是 `stream_workflow()` 的包装。切换之后它也走图了，于是原先
「`graph.invoke()` vs `run_workflow()`」的一致性测试变成了**图与自己比较**，
会永远通过且什么都没验证。

这与 slice 2 中遇到的测试失效是同一类问题：测试看起来是绿的，实际上没有测任何
东西。修法是新增 `run_sequential_workflow()` 作为顺序执行器的显式入口，让一致性
测试能够真正比较两个引擎。

同时新增两条互为对照的测试：一条把 `_stream_sequential` 替换为抛异常的桩函数后
仍能跑通（证明确实走图），另一条把 `graph` 设为 `None` 后仍能跑通（证明降级路径
仍然有效）。两条都通过，说明分支是真实可区分的。

### 验证

```text
$ ruff check .
All checks passed!

$ pytest --basetemp=.pytest_tmp
47 passed in 1.74s

$ python eval/run_eval.py
Mode: deterministic. Pass --live to call the real LLM.
OUTPUTS IDENTICAL - metrics unchanged
```

评估指标未变这一点尤其关键：`comparison_evaluation.py` 的「CareerPilot Full」
方法现在经由 LangGraph 执行，而全部指标与切换前逐字节相同。

真实 DeepSeek 端到端验证（预算闸退出码 0，余额 5.78 元）：

```text
ResumeParserNode: Extracted 3 projects, 9 skills, 1 work experiences.
JDAnalyzerNode: Identified 4 required skills, 4 preferred skills, 6 keywords.
RAGRetrieverNode: Retrieved 8 knowledge snippets from local knowledge base.
MatchScoringNode: Score = 62/100. 3 matched skills, 2 missing skills.
ResumeOptimizerNode (Iteration 0): Generated 10 bullet suggestions.
ReflectionNode (Iteration 0): 0 issue(s) found. Finalizing.
PhaseTwoParallelNode: Running application answers and interview coaching in parallel.
ApplicationAnswerNode: Drafted conservative application answer starters.
InterviewCoachNode: Generated 12 interview practice questions.
FinalReportNode: Analysis complete. Report ready.
errors=0
```

10 个节点顺序正确，`FinalReportNode` 恰好一次，无任何「Fallback used.」标记。

## Slice 5: 并行化 intake 节点与可配置超时

### 动机

`resume_parser_node` 读 `raw_resume_text`，`jd_analyzer_node` 读 `raw_jd_text`，
两者都不读对方的输出。但工作流串行执行它们，在 LLM 路径上白白多花一次网络往返。
项目在 Phase 2 已经证明并行模式可行，这里只是把同一手法用到 intake 阶段。

另外 `llm_client.py` 中的 `max_retries=2` 与 `request_timeout=60` 是硬编码的。
项目文档反复记录「thinking 模式配 high reasoning effort 很慢，应谨慎使用」——
而使这一配置可用的关键旋钮却必须改源码才能调整。

### 改动

- 把原先只服务 Phase 2 的 `_run_phase_two_parallel()` 泛化为
  `_run_in_parallel(state, nodes)`，两处并行点共用。每个节点拿到状态的独立副本，
  结果按声明顺序返回而非完成顺序，以保证 trace 在多次运行间稳定。
- LangGraph 路径：从 `START` 扇出到两个 intake 节点，在 `rag_retriever` 处 join
  （它是第一个需要 `jd_analyzer` 输出的节点）。
- 顺序执行器路径：改用 `_run_in_parallel`。
- `request_timeout` 与 `max_retries` 提升为 `ProviderConfig` 字段，可由
  `DEEPSEEK_REQUEST_TIMEOUT` / `DEEPSEEK_MAX_RETRIES` 配置，默认值与原硬编码值
  相同。非法值（空、非数字、零、负数、小数）回退到默认值 —— `.env` 里的一个笔误
  不应该静默产生零超时，那会让每个请求都瞬间失败。

### 一条过度约束的测试

slice 4 写的 `test_stream_workflow_uses_the_compiled_graph` 断言
`node_names[0] == "resume_parser"`，并行化后失败，实际首个事件变成了
`jd_analyzer`。

这是**测试写得过度具体**，不是实现错误：并行节点之间本就没有确定的先后顺序，
断言具体哪个先到是在测试一个不存在的契约。已改为断言前两个事件的集合等于
`{resume_parser, jd_analyzer}`，并新增一条测试确认二者都在 `rag_retriever`
之前完成 —— 那才是真正需要保证的约束。

### 验证

```text
$ ruff check .
All checks passed!

$ pytest --basetemp=.pytest_tmp
55 passed in 1.81s

$ python eval/run_eval.py
Mode: deterministic. Pass --live to call the real LLM.
OUTPUTS IDENTICAL
```

真实 DeepSeek 耗时对比（预算闸退出码 0，余额 5.68 元）。同一进程内先后测量，
输入相同：

```text
sequential (old behaviour): 7.45s
parallel   (new behaviour): 4.23s

speedup: 1.76x, saved 3.22s

sequential traces:
   ResumeParserNode: Extracted 3 projects, 9 skills, 1 work experiences.
   JDAnalyzerNode: Identified 4 required skills, 4 preferred skills, 6 keywords.
  fell back: 0
parallel traces:
   ResumeParserNode: Extracted 3 projects, 9 skills, 1 work experiences.
   JDAnalyzerNode: Identified 5 required skills, 4 preferred skills, 4 keywords.
  fell back: 0
```

两种模式下都没有节点退回确定性路径。

必须说明的是，**这是单次测量，不是基准测试**。网络延迟波动可能达到秒级，
1.76x 这个数字不应被当作精确值引用。可以确定的只是量级：省下的时间约等于一次
LLM 往返，这与「两次串行调用变成两次并发调用」的预期一致。两次 `jd_analyzer`
调用返回的技能数不同（4 vs 5），是 LLM 本身的非确定性，与并行化无关。

