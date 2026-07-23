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

## Slice 6: 补 parser 与 LLM 分支测试

### 动机

两处零覆盖，都在用户输入直接经过的路径上。

**上传解析。** 核实过改动前的测试目录，没有任何测试引用 `parse_pdf`、
`parse_docx`、`parse_resume_file` 或 `src.parsers`：

```text
$ for f in $(git ls-tree --name-only c35a358 tests/); do
    git show c35a358:$f | grep -qE "parse_pdf|parse_docx|parse_resume_file|src.parsers" && echo "HIT: $f"
  done
(无输出)
```

`src/parsers/` 三个模块此前一行测试都没有，而简历是用户上传的文件，这条路径要
面对各种真实产物：带 BOM 的导出、遗留编码、空文件、扩展名不符的文件。

**LLM 分支。** `tests/conftest.py` 的 autouse fixture 清除 API key，因此整个测试
套件跑的都是确定性 fallback，`can_use_llm()` 为真时的那条分支从未被执行过。这意味
着 `invoke_structured()`、`invoke_structured_list()` 与结构化输出校验在测试中完全
没有被覆盖。

这个问题在 slice 2 已经露过一次头：当时新写的一条测试之所以失败，正是因为没有
伪造凭据，`run_node()` 根本没进入 LLM 分支。

### 改动

`tests/test_parsers.py`（13 条）：用 PyMuPDF 和 python-docx 在内存中生成真实的
PDF/DOCX 文件后往返解析，覆盖 None 输入、空文件、UTF-8 / UTF-8-BOM / Latin-1 编码、
无法解码的字节、大写扩展名、不支持的扩展名，以及损坏的二进制文件。

`tests/test_llm_branches.py`（14 条）：用一个假的 chat model 替换 `common.get_llm`
并将 `can_use_llm()` 固定为真，覆盖 6 个节点各自的 LLM 分支。

其中值得单独指出的几条：

- 模型回答签证问题时，答案仍被 `SENSITIVE_NOTICE` 覆盖。这条测试保护的是安全
  边界 —— 模型有可能自作主张回答签证资格问题，那个答案绝不能到达用户。
- `{"items": [...]}` 包装能被正确拆开，而不是整体判定为解析失败。
- 四种无法解析的响应（非 JSON、截断的 JSON、类型错误、空字符串）都落到 fallback
  并记录错误。
- 响应内容不是字符串而是结构化块时也能处理。

这些测试都不是空转的：以 `test_resume_parser_uses_the_model_response` 为例，它
断言结果中的姓名为「Parsed By Model」，该值只可能来自假模型；若 LLM 分支未被执行，
拿到的会是 fallback 解析出的「Alex Chen」，测试立即失败。

### 验证

```text
$ ruff check .
All checks passed!

$ pytest --basetemp=.pytest_tmp
82 passed in 1.98s

$ python eval/run_eval.py
Mode: deterministic. Pass --live to call the real LLM.
OUTPUTS IDENTICAL
```

测试数从 55 增至 82。本 slice 只新增测试，未改动任何产品代码，评估输出因此不变。

值得记录的是：13 条 parser 测试**一次就全部通过**，没有发现缺陷。解析模块比预期
健壮 —— `parse_pdf` 已经处理空字节流，`_read_text_file` 已经有编码回退链，
`parse_resume_file` 已经对扩展名做小写归一。此前缺的不是健壮性，是证据。

本 slice 无 API 调用，不产生费用。

## Slice 7: 拆分 app.py 与清理副作用

### 动机

`app.py` 用 263 行容纳 6 个 tab 的全部渲染逻辑、缓存处理、工作流调用与运行历史。
除此之外还有两处具体缺陷：

1. **渲染 widget 会产生全局副作用。** 侧边栏在读取用户选择后直接写
   `os.environ["DEEPSEEK_MODEL"]` 等（原 `app.py:75,80,90`）。Streamlit 每次交互
   都会重跑整个脚本，因此每次交互都在修改进程级状态，且从不还原。模型输入框留空
   时旧值也不会被清除。
2. **签证/薪酬提示无条件渲染**（原 `app.py:216`）。它位于 tab 的最外层，在任何
   分析运行之前就会显示 —— 警告一段当时并不在屏幕上的内容。

### 改动

拆分为 8 个模块：`src/ui/sidebar.py`、`src/ui/analysis.py`、
`src/ui/sample_data.py`，以及 `src/ui/tabs/` 下的 6 个 tab 模块。`app.py` 缩减为
44 行，只负责装配。

副作用清理：侧边栏改为返回 `ProviderSettings` 值对象，由 `run_analysis()` 通过新增
的 `provider_overrides()` 上下文管理器在工作流运行期间应用，结束后还原原值。空值
被忽略，不会覆盖 `.env` 提供的配置。异常路径也会还原。

签证提示改为仅在确有草稿内容时渲染。

### 拆分过程中自己引入又修掉的一处回归

初版 `app.py` 在渲染 tab 之前读取 `st.session_state["last_result"]`。原实现是在
tab1 的代码块**之后**读取的 —— 顺序不同会导致分析跑完后当次看不到结果，必须再交互
一次才刷新。已改回在 `input_tab.render()` 之后读取，并加注释说明原因。

### 关于「HTTP 200」不足以验证 UI

启动 Streamlit 后 `Invoke-WebRequest` 返回 `HTTP 200 OK`，stderr 也没有报错：

```text
2026-07-23 04:40:33.176 Uvicorn server started on 127.0.0.1:8511
```

但这**证明不了 UI 正常**。Streamlit 在客户端建立 websocket 会话之前不会执行
`app.py`，HTTP 请求拿到的只是外壳 HTML。把一个文件拆成 8 个模块后，import 错误或
属性错误恰恰只在渲染时才暴露 —— 而这正是该验证方式看不到的部分。

项目此前的验证记录多次以「HTTP 200」作为 UI 可用的证据，这个判据是不充分的。

改用 Streamlit 自带的 `AppTest` 无头执行整个脚本（`tests/test_app_renders.py`，
5 条）：断言脚本未抛异常、6 个 tab 全部存在、侧边栏三个控件齐全、未运行分析时提示
文案正确、以及签证提示在分析前不出现。

### 验证

```text
$ ruff check .
All checks passed!

$ pytest --basetemp=.pytest_tmp
99 passed in 2.70s

$ python eval/run_eval.py
Mode: deterministic. Pass --live to call the real LLM.
OUTPUTS IDENTICAL

$ (Get-Content app.py | Measure-Object -Line).Lines
44
```

`app.py` 从 263 行降至 44 行。测试数从 82 增至 99，新增 12 条覆盖此前内联在渲染
函数中、无法单独测试的逻辑（问题文本切分、样例数据加载、历史表格列映射、
`provider_overrides` 的还原语义），以及 5 条 AppTest。

本 slice 无 API 调用，不产生费用。

## Slice 8: 报告导出（新功能）

### 改动

新增 `src/services/report_export.py`，把完成的工作流状态渲染为 Markdown：匹配报告、
bullet 建议、申请回答草稿、面试练习题、警告，并保留审阅提示与敏感问题声明。该模块
不依赖 Streamlit，可直接测试。Match Report tab 增加一个下载按钮。

### 我自己违反了预算规程

预览导出效果时，我在 PowerShell 里把 `DEEPSEEK_API_KEY` 设为空字符串，以为这样
就是离线运行，因此没有先跑预算闸。结果那次运行**调用了真实 API** —— 输出的分数 58
与详尽的解释文本只可能来自真实模型。

原因正是 slice 1 记录过的机制：`provider_config` 在 import 时调用 `load_dotenv()`，
从上层目录找到 `.env` 并把变量填了回来。**我记录了这个陷阱，然后自己踩了进去。**
从 shell 设置环境变量不起作用，唯一可靠的方式是在 import 之后清除，也就是
`eval/run_eval.py` 里的 `use_deterministic_agents()`。

后续预览已改用该函数。这次意外调用的费用在允许范围内，但流程是错的，记录在此。

### 预览暴露的两个缺陷

肉眼检查导出结果时发现两处问题，都不是断言能覆盖到的。

**一、bullet 标题变成整段文字。** schema 中 `context` 字段意为项目或岗位名称，
确定性路径也确实如此。但真实模型经常把整条改写后的 bullet 放进 `context`，于是
Markdown 标题变成了一整段：

```text
### 1. Built a movie recommendation system using Python, pandas, NumPy, and
scikit-learn. Compared collaborative filtering and content-based recommendations
and visualized model results with Matplotlib.
```

导出侧对超过 60 字符的 `context` 做截断，而不是信任上游数据。

**二、职位名提取的贪婪匹配 bug。** 导出的文件名是：

```text
careerpilot-ai-intern-we-are-looking-for-an-ai-intern-20260723.md
```

`jd_analyzer_agent.py` 的职位名正则用了贪婪量词：

```text
greedy -> 'AI Intern  We are looking for an AI Intern'
lazy   -> 'AI Intern'
```

`[\w\s/-]*` 会越过第一个 "Intern"，一直匹配到文档中最后一个。这不只影响导出 ——
职位名同时显示在 Match Report、Run History 表格中，还被用于拼装 RAG 检索 query。
改为非贪婪量词并补充测试。

修复后文件名为 `careerpilot-ai-intern-20260723.md`。

值得一提的是，评估指标在此修复后**没有变化**。原本预期 RAG query 改变会影响检索
结果，但知识库只有 8 个 chunk 且总是被全量返回，query 内容不起作用 —— 与 slice 1
的发现一致。

### 一条写错的测试

新增的 AppTest 用例最初调用 `app.download_button`，报 `AttributeError`。该
Streamlit 版本的 `AppTest` 没有这个访问器，需要用 `app.get("download_button")`。
应用本身渲染无异常，是测试的写法有误。

### 验证

```text
$ ruff check .
All checks passed!

$ pytest --basetemp=.pytest_tmp
117 passed in 2.20s

$ python eval/run_eval.py
Mode: deterministic. Pass --live to call the real LLM.
OUTPUTS IDENTICAL
```

测试数从 99 增至 117。除断言外，也实际生成并肉眼检查了完整报告 —— 上述两个缺陷
都是这样发现的，不是靠测试发现的。

## Slice 9: 多 JD 批量对比（新功能）

### 动机

项目定位是帮学生准备实习申请，而学生通常同时投递多个岗位。现有工作流一次只处理
一个 JD，能回答「这个岗位合不合适」，但回答不了「这几个里哪个最值得投入时间」和
「补哪一项技能能同时打开最多机会」。

### 改动

新增 `src/services/multi_jd.py`：复用现有 `run_workflow` 与缓存逐个分析，按匹配分
排序，并计算所有岗位共同缺失的技能。不新增任何 LLM 调用模式。

新增 `Compare Jobs` tab。多个 JD 用 `===` 分隔，块首写 `# 标签` 可命名。

两处设计判断值得记录：

**共同缺失取交集而非并集。** 并集只是「所有岗位提到过的技能」，信息量不大；交集
才是「每个岗位都要求、而简历里都没有」的技能 —— 那才是最该优先补的一项。结果顺序
沿用第一个岗位的列表，而不是集合的迭代顺序，以保证多次运行结果稳定。

**单个岗位不计算共同缺失。** 对单个集合求交集就是它本身，作为「这些岗位都要什么」
的答案会产生误导，因此少于两个可用岗位时返回空。

**单个岗位失败不影响其余。** 每个岗位的异常被记录在该行上，失败行排在最后，不会
占据「最佳匹配」的位置。空 JD 直接标记而不进入工作流。

### 验证

```text
$ ruff check .
All checks passed!

$ pytest --basetemp=.pytest_tmp
132 passed in 2.18s
```

测试数从 117 增至 132。除单元测试外，用样例数据实际跑了一次完整对比：

```text
Rank Job             Detected Role                Score  Matched  Missing  Status
1    Data Analyst    Data Analyst Intern          79     2        1        OK
2    SWE Intern      Software Engineering Intern  72     2        2        OK
3    AI Intern       AI Intern                    68     2        3        OK

best fit: Data Analyst (79/100)
missing from every role: (none)

Data Analyst: missing = ['Tableau']
SWE Intern:   missing = ['Java', 'REST API']
AI Intern:    missing = ['PyTorch', 'TensorFlow', 'NLP']
```

「missing from every role: (none)」是正确结果而非缺陷 —— 这三个岗位要求的技能确实
没有交集。UI 对这种情况有单独的说明文案。

顺带可以看到 slice 8 修复的职位名正则在这里生效：`Detected Role` 一列是干净的
职位名，而不是整段 JD 开头。

本 slice 无 API 调用，不产生费用。

## Slice 10: RAG 检索恢复选择性

本条在前九个 slice 合并到 `integration/2026-07-optimization` 之后追加，处理此前
被记为「超出范围」的那个问题。

### 诊断修正了此前的判断

前面几个 slice 把这个问题记录为「知识库只有 8 个 chunk，太小」。实际排查后发现，
**语料规模只是表象，分块逻辑本身是坏的**。

`split_markdown()` 按 1200 字符累积段落，完全不理会 markdown 标题。旧行为实测：

```text
total chunks: 8
[resume_bullets] 914 chars | category=software_engineering
                 | headings inside: ['# Machine Learning', '# Data Analysis', '# Software Engineering']
[skill_taxonomy] 1112 chars | category=databases
                 | headings inside: ['# Programming Languages', '# ML And AI', '# Data Tools',
                                     '# Visualization', '# Cloud And DevOps', '# Software Engineering',
                                     '# Databases']
[skill_taxonomy]  160 chars | category=databases | headings inside: []
```

三个后果：

1. **AI 岗和 SWE 岗的查询在原理上无法区分。** Machine Learning、Data Analysis、
   Software Engineering 三节的 bullet 模板挤在同一个 chunk 里，无论查询是什么，
   要么全拿到要么全拿不到。
2. **`category` 元数据是错的。** 它只记录该 chunk 吸收的最后一个标题，因此上面
   那个含三节内容的 chunk 被标为 `software_engineering`，描述错了自己三分之二的
   内容。
3. **存在孤儿 chunk。** 160 字符那一块没有任何标题，category 从上一块泄漏而来。

所以只补内容而不修分块是无效的 —— 新内容同样会被揉进跨节的大块里。

### 改动

**分块按节切分。** `split_markdown()` 改为每个 markdown 标题起一个新 chunk，
category 取自该 chunk 自己的标题。超过 `chunk_size` 的长节仍会继续切分，但每一片
都重复标题，保证自描述。

仅此一项改动：8 → 23 个 chunk，每个恰好一个标题，category 全部正确，孤儿块消失。

**扩充知识库内容。** 新增的节是实习准备的实际内容，不是填充：

- `resume_bullet_templates.md`：Deep Learning、NLP、Data Engineering、
  Backend And API、Testing And Quality。
- `interview_question_bank.md`：ML 概念、数据分析概念、软件工程概念、SQL 与数据库、
  反问面试官的问题。
- `star_method_examples.md`：学习新工具、需求不明、时间压力、API 集成、数据质量问题。
- `application_question_examples.md`：项目举例、为何选择该公司、学习与成长、团队协作、
  应对挫折、日程与出勤安排。

内容遵循项目既有约束：不编造事实，不替用户回答签证与薪酬类问题。

23 → 44 个 chunk。各 collection 与检索请求量的对比：

| collection | 请求 k | 改动前可用 | 改动后可用 |
| --- | --- | --- | --- |
| resume_bullets | 5 | 2 | 10 |
| star_examples | 3 | 2 | 10 |
| skill_taxonomy | 3 | 2 | 7 |
| application_examples | 2 | 1 | 9 |
| interview_bank | 3 | 1 | 8 |

**评分函数利用标题。** 每个 chunk 现在恰好对应一节，标题比正文任何一行都更能说明
这节讲什么 ——「Backend And API」与「Deep Learning」两节都会提到 Python，只有标题
能区分。`_score()` 现在把 category 匹配按 3 倍权重计入。

### 效果

同一份简历对三个样例 JD 的检索结果（`bullet_templates` 一列）：

```text
AI Intern    -> ['Machine Learning', 'Data Analysis', 'Deep Learning',
                 'Software Engineering', 'Natural Language Processing']
Data Analyst -> ['Data Analysis', 'Data Engineering', 'Machine Learning',
                 'Software Engineering', 'Deep Learning']
SWE Intern   -> ['Software Engineering', 'Backend And API', 'Data Engineering',
                 'Machine Learning', 'Data Analysis']
```

SWE 岗拿到 Backend And API、API Integration、Cloud And DevOps；AI 岗拿到 ML And AI、
Model Training、Deep Learning；Data Analyst 拿到 Data Engineering、Data Tools、
Data Quality Issue。改动前三者拿到的是**完全相同**的内容。

标题加权带来的增量：AI 与 Data Analyst 的 bullet 模板重合度从 5/5 降至 4/5。
剩余重合是合理的 —— 两个岗位都以 Python 和 SQL 为主。

### 指标本身也需要修

把 `rag_snippet_count` 从 8 提到 16 不能说明问题已解决：语料 44 条、请求 16 条，
这个计数从此恒为 16，依旧不衡量任何东西。「返回 8 条中的 8 条」和「返回 800 条中的
8 条」是同一个数字，却是完全不同的行为。

因此新增了一个占比指标。**但这个替代指标当时也没有真正解决问题** —— 见 slice 14 的
更正：它同样是常量，只是换了个数值。

### 验证

新增 `tests/test_rag_retrieval.py`（17 条）。为确认这些测试确实在验证行为而不是
恒真，把源码与内容临时 stash 回旧版本后重跑：

```text
FAILED test_each_chunk_covers_exactly_one_section
FAILED test_category_matches_the_heading_in_the_chunk
FAILED test_sections_are_split_even_when_they_would_fit_one_chunk
FAILED test_a_long_section_splits_but_keeps_its_heading
FAILED test_every_collection_offers_more_than_the_retriever_asks_for[resume_bullets-5]
FAILED test_every_collection_offers_more_than_the_retriever_asks_for[star_examples-3]
FAILED test_every_collection_offers_more_than_the_retriever_asks_for[skill_taxonomy-3]
FAILED test_every_collection_offers_more_than_the_retriever_asks_for[application_examples-2]
FAILED test_every_collection_offers_more_than_the_retriever_asks_for[interview_bank-3]
FAILED test_different_roles_retrieve_different_context
FAILED test_retrieval_reflects_the_role
FAILED test_retrieval_does_not_return_the_whole_corpus
FAILED test_heading_matches_outrank_incidental_body_mentions
```

13 条在旧实现下失败。其中 `test_different_roles_retrieve_different_context` 的失败
直接证明了旧代码下三个岗位拿到的上下文完全一致。

```text
$ ruff check .
All checks passed!

$ pytest --basetemp=.pytest_tmp
149 passed in 2.75s

$ python eval/run_eval.py   （连续两次）
reproducible: True
```

测试数从 132 增至 149。评估输出发生变化是**预期的** —— 这正是检索行为改变的体现，
且连续两次运行仍逐字节一致。

本条无 API 调用，不产生费用。

## Slice 11: 停止默认使用会降低质量的向量库路径

### 我在 Future Work 里写错了一条

Slice 10 结束时，我把剩余工作记为「检索用词项匹配，同义词会漏；走 Chroma 的
embedding 路径可以解决」。着手前先做验证，**这条是错的**。

`get_embeddings()` 默认返回 `LocalHashEmbeddings`（`EMBEDDING_PROVIDER=local_hash`，
项目是 DeepSeek-only，没有配置 OpenAI embedding）。它把每个 token 用 md5 映射到
64 个桶之一然后计数 —— 是哈希词袋，不是语义向量。实测：

```text
default embeddings: LocalHashEmbeddings | dims: 64

cosine similarity under local_hash:
  'pytorch'  vs 'deep learning framework'     = 0.000
  'sql'      vs 'relational database queries' = 0.000
  'rest api' vs 'http endpoint'               = 0.000
  'pytorch'  vs 'pytorch'                     = 1.000
```

三组同义词相似度全为 0.000。**零同义词能力**，所以这条路径根本无法交付我承诺的
效果。

碰撞问题同样严重：

```text
vocabulary: 839 distinct tokens into 64 buckets
average tokens per bucket: 13.1
busiest bucket holds 20 tokens, e.g. ['applied', 'causation', 'confirmed',
                                      'crud', 'debug', 'docker:', 'finding', 'hugging']
```

平均 13 个词共用一个维度，`docker` 与 `causation`、`hugging` 成为同一个特征。

### 由此发现的真实缺陷

既然哈希向量既无语义又高度碰撞，那么走 Chroma 的检索质量应当低于词项匹配。
实测对比（重建向量库后，同一份知识库、同样三个样例 JD）：

```text
===== markdown scorer =====
SWE Intern   bullets: ['Software Engineering', 'Backend And API', 'Data Engineering', ...]
             skills : ['Software Engineering', 'Programming Languages', 'Cloud And DevOps']
Data Analyst skills : ['Databases', 'Data Tools', 'Programming Languages']

===== chroma + local_hash =====
SWE Intern   bullets: ['Data Analysis', 'Backend And API', 'Machine Learning',
                       'Deep Learning', 'Software Engineering']
             skills : ['Visualization', 'Databases', 'Data Tools']
Data Analyst skills : ['Visualization', 'Databases', 'Data Tools']
```

Chroma 路径下：

- 后端岗位的首选 bullet 变成「Data Analysis」，「Software Engineering」跌到第 5 位。
- 后端岗位的技能片段里既没有 Software Engineering 也没有 Cloud And DevOps，取而代之
  的是 Visualization。
- 数据分析岗与软件工程岗拿到**完全相同**的技能片段 —— 无法区分。

而 `retrieve_snippets()` 是**优先**使用向量库的，只要 `data/vectorstore/` 存在即生效。
该目录是 gitignore 的机器本地状态，运行过应用的机器上就会有。也就是说在实际使用中，
检索走的是更差的那条路径 —— 这个缺陷此前一直存在，只是知识库过小时（每次返回全部
内容）无从暴露。

### 改动

`get_or_build_vectorstore()` 现在在嵌入不具备语义时返回 `None`，即跳过向量库。
新增 `has_semantic_embeddings()` 判断，逻辑与依据写在其 docstring 中。

向量库路径本身保留：配置 `EMBEDDING_PROVIDER=openai` 后自动启用。也可用
`CAREERPILOT_FORCE_VECTORSTORE=1` 强制启用哈希向量路径（用于演示或调试）。
`CAREERPILOT_DISABLE_VECTORSTORE` 优先级高于强制开关。

### 验证

```text
$ ruff check .
All checks passed!

$ pytest --basetemp=.pytest_tmp
155 passed in 3.00s

$ python eval/run_eval.py
(评估输出无变化 —— 评估本就强制走 markdown 路径)
```

新增 6 条测试：哈希嵌入不被判定为语义嵌入、同义词相似度为 0、默认跳过向量库、
强制开关有效、禁用优先于强制。

需要说明的是：这不能算「解决了同义词问题」。同义词检索需要真正的嵌入模型，而
DeepSeek 未提供 embedding 接口，因此在当前 provider 下无法实现。本条做的是**停止
使用一个比现有方案更差的路径**，并把判断依据写进代码，避免下一个人重新踩进去。

本条无 API 调用，不产生费用。

## Slice 12: 截图更新，以及它暴露的一个功能缺陷

### 「Load all sample JDs」此前完全不工作

刷新 README 截图时，为拍到 Compare Jobs 的结果页而驱动 UI，脚本一直超时。抓取失败
时刻的截图后看到：两个输入框都是空的，页面显示「Please provide a resume.」——
点击「Load all sample JDs」没有任何效果。

原因是 Streamlit 的 widget 语义。带 `key=` 的组件，其值保存在
`st.session_state[key]` 中，**首次渲染之后的每次 rerun 都会忽略 `value=` 参数**。
`compare_tab.py` 同时使用了两者：

```python
jd_blocks = st.text_area("Job descriptions", value=st.session_state.get("compare_jds", ""), key="compare_jd_text")
```

首次渲染时 `compare_jd_text` 被注册为空字符串，此后按钮写入 `compare_jds` 完全
不起作用。也就是说 slice 9 交付的这个功能，在真实 UI 中从一开始就是坏的 ——
用户只能手动粘贴 JD，示例加载按钮是死的。

**为什么此前的测试没有发现**：`tests/test_multi_jd.py` 直接测试 `compare_jobs()`
纯函数；`tests/test_app_renders.py` 只断言控件存在。两者都没有真正驱动这条交互
路径。

### 改动

- `compare_tab.py` 改为通过 `st.session_state` 传值，不再传 `value=`。加载按钮
  移到 columns 之上 —— 组件创建之后就不能再赋值它的 session_state key。按钮写入
  后调用 `st.rerun()`。
- 新增两条 AppTest 回归测试：点击按钮后两个输入框确实被填充；以及完整的端到端
  对比流程可以跑通并产出结果。把 `compare_tab.py` 临时 stash 回旧版本后，这两条
  测试都失败，确认它们捕捉的是真实行为。

### 截图工具的三处修复

- **虚拟环境发现**：工具硬编码 `.venv` 在仓库根目录，在 git worktree 中不存在，
  直接以 ENOENT 失败。现在会向上层查找，并支持 `PYTHON` 覆盖。
- **点击方式**：`element.click()` 对 Streamlit 的主按钮无效 —— React 处理器绑定在
  指针事件上。脚本会以为已经启动了分析，实际什么都没发生。改为通过
  `Input.dispatchMouseEvent` 在元素中心派发真实鼠标事件。
- **等待条件**：`run_analysis()` 命中缓存时会在创建 status 组件之前返回，因此
  「Analysis complete」永远不出现，任何重复运行都会挂起。现在同时接受
  「Loaded cached analysis」。

### 截图改为确定性模式

截图是提交进仓库的产物，应当可复现。工具现在默认清空 LLM 凭据与缓存后再运行，
`--live` 才使用真实模型。

这个决定另有一个具体原因。第一次带真实 API 的截图拍到了 **3/100** 的匹配分，而
模型自己的解释写的是「strong alignment with Python, SQL, scikit-learn」。排查确认
不是解析缺陷 —— 原始响应中的 `overall_score` 字段就是那个值，validated 之后一致。

当时记录为「相同输入下从 3 摆动到 65」。**这个结论后来被证明是错的**，更正见
下一条。截图使用确定性路径的决定本身仍然成立。

### 验证

```text
$ ruff check .
All checks passed!

$ pytest --basetemp=.pytest_tmp
157 passed in 3.81s

$ python eval/run_eval.py
(评估输出无变化)

$ node tools/capture_streamlit_screenshot.mjs
Mode: deterministic (pass --live for real calls)
Saved docs/assets/careerpilot-home.png
Saved docs/assets/careerpilot-sample-input.png
Saved docs/assets/careerpilot-match-report.png
Saved docs/assets/careerpilot-compare-jobs.png
```

四张截图均已逐一目视检查：首页显示全部 7 个 tab；Match Report 显示导出按钮；
Compare Jobs 显示排序表格与「Best fit: Data Analyst (79/100)」。新增的两张结果
截图填补了 README 此前没有任何实际输出图片的空白。

本条产生少量 API 消耗：截图首次运行走的是真实路径，另有一次用于诊断 3/100 的调用。
余额从 5.63 元降至 5.62 元附近（结算有延迟）。

## Slice 13: 更正打分结论，并修复量纲导致的静默失败

仓库所有者质疑了 slice 12 的结论：3 分是不是因为样例数据本身不合适？这促成了一次
正式测量，结果推翻了我此前的说法。

### 此前的结论错在哪里

slice 12 写的是「相同输入下从 3 摆动到 65」。这个说法有两个问题：

1. **输入并不相同。** 65 和 62 是 slice 10 修改 RAG 之前测得的，3 和 40 是之后。
   检索到的片段是打分节点的输入之一（`retrieved_context` 会进入 prompt），因此
   这四个数字并非来自同一条件。我把一个可能的因果关系当成了随机性。
2. **样本量为 1 的离群值被当成了范围端点。** 3 分只出现过一次。

### 正式测量

每个样例 JD 连续 4 次，代码状态一致：

```text
=== ai_intern ===
deterministic score: 68
LLM, with RAG context              [40, 50, 50, 55]  mean=48.8  spread=15
LLM, no RAG context                [40, 40, 50, 40]  mean=42.5  spread=10

=== data_analyst ===
deterministic score: 79
LLM, with RAG context              [65, 60, 60, 65]  mean=62.5  spread=5

=== swe_intern ===
deterministic score: 72
LLM, with RAG context              [50, 50, 50, 50]  mean=50.0  spread=0
```

更正后的结论：

- **运行间波动很小**，0 到 15 分，SWE 岗四次完全相同。远不是「3 到 65」。
- **真正的现象是系统性偏低**：LLM 一致地比确定性算法低 15 到 20 分，三个岗位皆然。
  这是稳定偏差，不是噪声。
- RAG 上下文使分数略微升高（48.8 对 42.5），方向合理。
- 3 分是罕见离群值，在其后 12 次采样中未再出现。

关于「是不是样例不合适」：**不是**。这份简历确实缺少 AI Intern JD 要求的
PyTorch / TensorFlow / NLP，因此中等分数是正确结果，而非缺陷。README 截图已使用
确定性路径，显示 68，本就是合理数字，无需更换样例。

### 测量过程中发现的真实缺陷

不带 RAG 上下文的那一组最初直接崩溃：

```text
pydantic_core._pydantic_core.ValidationError: 1 validation error for MatchReport
overall_score
  Input should be a valid integer, got a number with a fractional part
  [type=int_from_float, input_value=0.4, input_type=float]
```

模型返回了 `"overall_score": 0.4` —— 用 0-1 而非 0-100 的量纲。Pydantic 拒绝该值，
`run_node()` 捕获异常后改用确定性 fallback。也就是说：**模型给出了答案，系统把它
丢掉了**，用户看到的是 fallback 结果，界面上只留下一条错误记录。

这正是项目文档声称已处理的 schema drift，但 `structured_output.py` 未覆盖量纲这一类。

新增 `normalize_overall_score()`：0 到 1 之间的小数按百分比换算，字符串与百分号
形式一并处理，其余小数四舍五入。`0` 和 `1` 保持原样 —— 二者都是合法的 0-100 分数，
无从判断模型用的是哪种量纲，不应擅自放大 100 倍。

新增 9 条参数化测试覆盖上述各种形式。

### 验证

```text
$ ruff check .
All checks passed!

$ pytest --basetemp=.pytest_tmp
166 passed in 3.74s
```

修复后重跑同一组测量，不带 RAG 的那一组不再崩溃，正常返回 [40, 40, 50, 40]。

系统性偏低这一现象记入 README 已知限制与实施计划的技术债，供仓库所有者判断是否
需要处理。本条不改变打分逻辑本身。


## Slice 14: 代码评审后的修正

仓库所有者要求不再自行 review，改由我调用评审流程后直接整合。使用
`superpowers:requesting-code-review` 对 slice 10-13 的全部改动做了一次独立评审
（base `2b790e7`，head `70fea64`）。评审未发现 Critical 问题，但指出 7 项 Important，
其中数项是对我推理本身的纠正。以下是实际修复内容。

### 一、只有标题没有内容的 chunk（真实潜伏缺陷）

`split_markdown()` 的 flush 判断用的是 `current.strip()`，而 `current` 一开始就被
塞进了标题，因此恒为真。当某一节的第一个段落本身就超过 `chunk_size` 时，第一轮循环
就会产出一个**只含标题、没有任何正文**的 chunk：

```python
>>> split_markdown("# H\n\n" + "x"*300, "f", "c", "t", chunk_size=200)
[KnowledgeChunk(content='# H', ...), KnowledgeChunk(content='# H\n\nxxx…', ...)]
```

评审用 2000 组随机数据验证，其中 997 组触发。当前知识库未触发，仅因最长段落 478
字符远小于 1200。危害不只是浪费一个槽位：空 chunk 仍会因标题匹配获得高分，从而挤占
检索结果并把空内容送进 prompt。

改为显式追踪 `has_body`。同时补测试 —— 原有的
`test_a_long_section_splits_but_keeps_its_heading` 用 `startswith("# Long Section")`
断言，对只含标题的 chunk 同样成立，**捕捉不到这个缺陷**。

### 二、`has_semantic_embeddings()` 可能抛异常中断整个分析

配置 `EMBEDDING_PROVIDER=openai` 但没有 OpenAI key 时，`get_embeddings()` 会抛异常。
`rag_retriever_node` 没有 try/except，也不经过 `run_node`，异常会一路冒泡终止工作流。
而 README 与 AGENTS.md 恰恰把 `EMBEDDING_PROVIDER=openai` 作为启用向量库的推荐方式
写在文档里。这违反了项目「可选依赖缺失时应降级而非崩溃」的原则。已加保护并补测试。

### 三、我的新指标同样是常量（对推理的纠正）

评审指出：`rag_corpus_fraction` 恒为 `16/44 = 0.3636`，每一行、每一次运行都一样。
因为 `fallback_retrieve` 总是取满 k，而语料已超过请求量，这个值由构造决定。

**这正是我在 slice 10 批评 `rag_snippet_count` 时用的同一个论证** —— 我用一个新的
常量替换了旧的常量，还宣称已经解决。评审的判断是对的。

修复分两部分：

- 重命名为 `rag_corpus_headroom`，docstring 明确它是**语料规模的守卫**而非质量度量：
  1.0 表示检索没有选择余地，这是它唯一能捕捉的失效。
- 新增 `rag_context_overlap()` —— 不同岗位检索结果之间的平均 Jaccard 重合度。这是
  真正会随排序质量变化的指标：旧分块下为 1.0（三个岗位拿到完全相同的内容），当前为
  **0.3737**。它是跨案例的，因此由 `eval/run_eval.py` 输出而非放进逐案例的指标行。

```text
$ python eval/run_eval.py
Mode: deterministic. Pass --live to call the real LLM.
RAG context overlap across the 3 cases: 0.3737 (1.0 = every role got the same snippets)
```

### 四、停用词拿到了标题权重

`_query_terms` 以 `len(term) > 2` 过滤，保留了 "and"；而 category 匹配是子串判断，
因此任何含 "And" 的标题都会仅凭 "and" 拿到 4 分：

```text
query "python and sql analysis" ->
  data_analysis 7 | backend_and_api 4 | testing_and_quality 4 | machine_learning 2
```

「Backend And API」与「Testing And Quality」压过了「Machine Learning」。当前三个样例
JD 的技能都是单词，尚未触发，但 LLM 分析器经常返回多词技能。改为对标题分词后做整词
匹配，并剔除连接词。

### 五、四条无效或过弱的测试

- `test_vectorstore_can_still_be_forced` **没有任何断言** —— 即使强制开关从未被读取
  也会通过。改为断言确实绕过了嵌入门控。
- `test_retrieval_does_not_return_the_whole_corpus` 断言 `< 0.5`，但该值上限就是
  0.36，**永远不可能失败**。改为与请求量对比。
- `has_semantic_embeddings()` 的 True 分支此前无测试覆盖。
- `tests/conftest.py` 未固定 `EMBEDDING_PROVIDER`。按文档配置了
  `EMBEDDING_PROVIDER=openai` 的维护者，本地会看到检索测试失败而 CI 通过。已固定。

### 六、我自己已推翻却仍留在文档里的说法

评审指出「3 到 65」这个已被 slice 13 推翻的数字，仍然留在 `README.md` 的截图说明和
`capture_streamlit_screenshot.mjs` 的注释里 —— README 甚至在 33 行之后就写着更正后的
版本，自相矛盾。另有两处「截图待更新」的待办，而 slice 12 已经做完，README 在该条目
上方 45 行处就嵌入了新截图。四处全部清理。

评审的评语值得记下：slice 13 本身就是关于「纠正一个夸大的结论」，把那个结论留在
README 里会削弱这条分支最有价值的部分。

### 其他采纳的小项

- `load_all_knowledge_docs()` 加 `lru_cache`：此前 `retrieve_context()` 每次会把 5 个
  文件完整读取并解析 5 遍。
- `_category_of()` 折叠空白：标题后若无空行，正文会被并入标题，导致 category 含换行。
- `evaluation.py` 的函数内 import 改为顶层 —— 评审核实过不存在循环依赖，函数内 import
  只是把 `services -> rag` 这条依赖边对工具隐藏了，边本身依然存在。
- 补充 docstring：标题命中实际是 `1 + HEADING_WEIGHT = 4` 倍，而非 3 倍。
- `split_markdown()` 中一个恒为真的死条件已移除。

### 未采纳的项

评审建议截图工具改为向上逐级查找 `.venv` 而非硬编码 worktree 深度，以及把 Compare
流程里的固定 `sleep(3000)` 换成 `waitForText`。两项都合理，但属于工具健壮性而非产品
代码，当前可用，记在此处备查。

### 验证

```text
$ ruff check .
All checks passed!

$ pytest --basetemp=.pytest_tmp
174 passed in 3.63s

$ python eval/run_eval.py   （连续两次）
输出逐字节一致
```

测试数从 166 增至 174。本条无 API 调用，不产生费用。

## Slice 15: 打分对齐 —— 把 AI 分数与确定性基准并列

这是仓库所有者选定的下一步，也是唯一带产品判断的一项。她入睡前授权我自行选择方案。

### 背景

slice 13 测出 LLM 打分系统性地低于确定性算法 15-20 分，且偶发极端离群（3 分）。
用户在界面上看到的是 LLM 分数这个头号数字，因此它不可靠。三种可选方案：校准
prompt、用确定性分数做钳制、或并列展示两者。

### 选择的方案与理由

**并列展示，不偷改分数。** 具体：

- `match_scoring_node` 在 LLM 路径下**也总是**计算一次确定性分数，存为 state 顶层的
  `reference_score`。fallback 路径下模型本身就是这个打分器，两者相等，不产生任何额外
  显示。
- 两分数差距 ≥ `SCORE_GAP_THRESHOLD`（20）时加一条 warning。阈值取 20 的依据是实测
  差距 13-28：20 能捕捉大分歧（SWE 22、AI 极端 28），而让常规偏移（Data Analyst
  14-19）留给更安静的并列展示处理。
- UI 在两分数不同时并列显示「AI Score」与「Rule-based Score」两个 metric，附一句中性
  说明；相同时退回单分数布局。Markdown 导出同理。

不选钳制的理由：把 LLM 分数悄悄拉向基准，会让「模型打分不可靠」这个事实从视野里消失
—— 这正是本轮反复出现的那类隐藏问题（HTTP 200、恒定指标、CI 从未验证）。**模型的
原始分数在任何情况下都不被覆盖**，这是本方案的核心。

不选校准 prompt 的理由：需要反复真实调用去试，烧预算，且结果仍会漂移。留作 Future
Work。

### 真实验证碰巧证明了它的价值

真实 DeepSeek 端到端运行（预算闸退出码 0，余额 5.58 元）恰好又抽到了那个罕见的 3 分
离群值：

```text
AI score:        3
reference_score: 79
gap:             76
errors:          0
warnings:
  - Low match score (3/100). This JD may not be the best fit. ...
  - The AI score (3/100) and the rule-based score (79/100) disagree by 76 points.
    Treat the number as approximate and weigh the matched and missing skills, ...
```

模型给出 3 分时：它的原始分数 **3 被完整保留**（没有被改成 79），旁边并列着 79 分基准，
并弹出「相差 76 分，请把分数当作近似值」的警告。功能正好在它该起作用的极端场景里
起了作用。3 分离群值罕见但真实（本轮第二次遇到），这正是把基准并列展示、而非信任
单一分数的理由。

### 验证

```text
$ ruff check .
All checks passed!

$ pytest --basetemp=.pytest_tmp
183 passed in 3.40s

$ python eval/run_eval.py
（评估输出无变化：确定性路径下 reference_score == overall_score，不影响任何指标列）
```

测试数从 174 增至 183。新增覆盖：gap warning 的触发/不触发/对称性、低分警告独立于
gap、**模型分数被保留而非被基准覆盖**（核心断言）、fallback 路径两分数相等、导出与 UI
在分歧时的双分数呈现。

一处旧测试的断言随之更新：`test_match_scoring_uses_the_model_response` 原先断言
`warnings == []`，但它的 fixture 让确定性基准远低于 fake 的 88 分，如今会触发 gap
warning —— 这是正确的新行为，断言改为「不含低分警告」。

本条产生少量 API 消耗（一次真实端到端验证）。

## Slice 10: 修复缓存的隐私与历史重复缺陷

### 动机

2026-07-24 复审时发现两个残留缺陷，均不在原设计 spec 的 P1–P7 范围内：

1. **缓存把简历/JD 原文明文写盘。** `src/services/cache.py` 的 `save_to_cache`
   直接 `json.dump` 整个 workflow state，其中含 `raw_resume_text` 与
   `raw_jd_text`。这与 README、`docs/PROJECT_SPEC.md` 反复声明的
   「Uploaded files are processed in memory and are not saved / raw resumes and
   job descriptions are not persisted」直接矛盾。`run_history` 已小心只存摘要，
   缓存却把原文落到 `outputs/cache/*.json`。
2. **缓存命中重复写历史。** `src/ui/analysis.py` 的 `run_analysis` 在缓存命中
   分支仍调用 `save_run_history`。每次对同一输入点一次「Run」都会往 SQLite
   插一条新记录，历史被重复行灌满，而重看缓存并不是一次新的分析。

### 改动

- `src/services/cache.py`：新增 `_SENSITIVE_KEYS`/`_redact_sensitive`，在写盘前
  把 `raw_resume_text`、`raw_jd_text` 置空。这两个字段是输入，从不用于渲染缓存
  结果，redact 后 UI 各 tab 仍完整（match_report、optimized_bullets 等均保留）。
  redact 作用于副本，不改调用方内存中的 state。
- `src/ui/analysis.py`：缓存命中分支移除 `save_run_history` 调用，只做展示。
- 新增 `tests/test_cache.py`（5 例）与 `tests/test_analysis.py`（2 例），均先写
  失败测试再实现（TDD）。

### 验证

```text
$ pytest --basetemp=.pytest_tmp
190 passed in 3.34s

$ ruff check .
All checks passed!

$ python eval/run_eval.py
Mode: deterministic. Pass --live to call the real LLM.
（两个 CSV 重新生成，git status 无变化 —— 指标零回退）
```

测试数从 183 增至 190。本条走确定性路径，无 API 调用，不产生费用。

## Slice 11: 缓存写盘失败不再拖垮已完成的分析

### 动机

`run_analysis` 里 `save_to_cache(key, final_state)` 无容错。工作流已经跑完之后，
若缓存写盘异常（磁盘满、权限、并发占用），异常会一路冒泡到 `app.py` 外层的
`try/except`，UI 显示「Analysis failed」—— 而分析其实已经成功，结果（在 live 模式下
甚至是花过钱得到的）被直接丢弃。相邻的 `save_run_history` 早已用 try/except 兜住，
缓存却没有。缓存只是重复运行的加速手段，它的失败不应改变分析的成败。

### 改动

- `src/ui/analysis.py`：新增 `save_cache_safely`，与 `save_run_history` 对称，
  把 `save_to_cache` 包进 try/except，失败时只 `st.warning` 而不中断返回。
- `tests/test_analysis.py`：新增 `test_completed_analysis_survives_a_cache_write_failure`
  —— 让 `save_to_cache` 抛 `OSError`，断言 `run_analysis` 仍返回带 match_report 的
  结果、历史仍恰好记一次、并给出缓存告警。先写失败测试再实现（TDD）。

### 验证

```text
$ pytest --basetemp=.pytest_tmp
191 passed in 3.49s

$ ruff check .
All checks passed!
```

测试数从 190 增至 191。本条走确定性路径，无 API 调用，不产生费用。
