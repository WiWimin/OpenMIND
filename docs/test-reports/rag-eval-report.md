# RAG 检索质量评测报告

- 执行时间：2026-11-03T21:21:10+08:00
- Embedding：`Qwen/Qwen3-Embedding-0.6B` dim=1024
- 固定配置：top_k=5、min_score=0.3、chunk=800/120
- 灌入路径：HTTP API `http://localhost:8000/api/v1`；检索路径：应用层 VectorRetriever（与生产同实现，含 user_id SQL 下推，不经 LLM、无裸 SQL）
- 数据集：`backend/scripts/eval/dataset.json` sha256=94fade3532166780（语料 18 篇）
- 三段准入：①维度一致 ②连续 embedding ③检索冒烟 — 全部通过
- HTTP 一致性对照：一致

## 一、准入指标（Go/No-Go）

| 指标 | 门槛 | 实测 | 结论 |
| --- | --- | --- | --- |
| 知识库 scope hit@5 | 0.85 | 1.000 | ✅ 达标 |
| 会议材料 scope hit@5 | 0.8 | 1.000 | ✅ 达标 |
| 总体 MRR | 0.5 | 0.951 | ✅ 达标 |
| 负样本拦截率 | 1.0 | 0.500 | ❌ 未达标 |

## 二、分 scope 指标

| scope | n | hit@1 | hit@5 | MRR | chunk 命中@5 |
| --- | --- | --- | --- | --- | --- |
| knowledge_base | 20 | 1.000 | 1.000 | 1.000 | 1.000 |
| current_meeting | 16 | 0.812 | 1.000 | 0.891 | 1.000 |
| overall | 36 | 0.917 | 1.000 | 0.951 | 1.000 |

## 三、负样本拦截明细

| 问题 | 分类 | scope | top1 分数 | 拦截 |
| --- | --- | --- | --- | --- |
| 公司食堂下周的菜单是什么？ | domain_irrelevant | knowledge_base | 0.3268 | ❌ 放行 |
| 公司食堂下周的菜单是什么？ | domain_irrelevant | current_meeting | 0.3831 | ❌ 放行 |
| 年会定在几月几号举办？ | domain_irrelevant | knowledge_base | 0.3689 | ❌ 放行 |
| 年会定在几月几号举办？ | domain_irrelevant | current_meeting | 0.4432 | ❌ 放行 |
| 隔壁组的 HC 还招人吗？ | domain_irrelevant | knowledge_base | 0.3767 | ❌ 放行 |
| 隔壁组的 HC 还招人吗？ | domain_irrelevant | current_meeting | 0.4786 | ❌ 放行 |
| 上海明天的天气怎么样？ | out_of_domain | knowledge_base | — | ✅ |
| 上海明天的天气怎么样？ | out_of_domain | current_meeting | — | ✅ |
| 怎么做红烧肉比较好吃？ | out_of_domain | knowledge_base | — | ✅ |
| 怎么做红烧肉比较好吃？ | out_of_domain | current_meeting | — | ✅ |
| 2026 年世界杯冠军是谁？ | out_of_domain | knowledge_base | — | ✅ |
| 2026 年世界杯冠军是谁？ | out_of_domain | current_meeting | — | ✅ |
| asdfghjkl 一二三四五？ | noise | knowledge_base | 0.3123 | ❌ 放行 |
| asdfghjkl 一二三四五？ | noise | current_meeting | 0.3885 | ❌ 放行 |
| 嗯嗯啊啊那个这个…… | noise | knowledge_base | — | ✅ |
| 嗯嗯啊啊那个这个…… | noise | current_meeting | — | ✅ |

## 四、未命中分析（hit@5 miss）

无未命中查询。

## 五、chunk 级未命中（内容断言失败）

全部查询的 top5 中均包含期望内容片段。

## 六、分数分布（阈值校准参考，不自动放宽）

- 正样本 top1：min=0.4484 / median=0.6082 / max=0.7938（n=36）
- 负样本 top1（未拦截者）：min=0.3123 / max=0.4786（n=8）
- 无干净分界（正样本 min 0.4484 ≤ 负样本 max 0.4786）：单靠阈值无法分离，需引入重排序、答案相关性校验或负样本拒答策略，属产品级改进项。

**结论：No-Go — 存在未达标指标，见上表**