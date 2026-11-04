# RAG 检索质量评测报告

- 执行时间：2026-11-04T23:14:47+08:00
- Embedding：`Qwen/Qwen3-Embedding-0.6B` dim=1024
- 固定配置：top_k=5、min_score=0.3、chunk=800/120；RAG Judge：enabled=True、judge_min_score=0.6（低分带 LLM 复核）；web_search=False（评测口径固定关闭）
- 灌入路径：HTTP API `http://localhost:8000/api/v1`；检索路径：应用层 VectorRetriever（与生产同实现，含 user_id SQL 下推，不经 LLM、无裸 SQL）
- 数据集：`backend/scripts/eval/dataset.json` sha256=94fade3532166780（语料 18 篇）
- 三段准入：①维度一致 ②连续 embedding ③检索冒烟 — 全部通过
- HTTP 一致性对照：一致

## 一、准入指标（Go/No-Go）

| 指标 | 门槛 | 实测 | 结论 |
| --- | --- | --- | --- |
| 知识库 scope hit@5 | 0.85 | 1.000 | ✅ 达标 |
| 会议材料 scope hit@5 | 0.8 | 0.938 | ✅ 达标 |
| 总体 MRR | 0.5 | 0.944 | ✅ 达标 |
| 负样本拦截率 | 1.0 | 1.000 | ✅ 达标 |

## 二、分 scope 指标

| scope | n | hit@1 | hit@5 | MRR | chunk 命中@5 |
| --- | --- | --- | --- | --- | --- |
| knowledge_base | 20 | 1.000 | 1.000 | 1.000 | 1.000 |
| current_meeting | 16 | 0.812 | 0.938 | 0.875 | 0.938 |
| overall | 36 | 0.917 | 0.972 | 0.944 | 0.972 |

## 三、负样本拦截明细

| 问题 | 分类 | scope | top1 分数 | 拦截 |
| --- | --- | --- | --- | --- |
| 公司食堂下周的菜单是什么？ | domain_irrelevant | knowledge_base | — | ✅ |
| 公司食堂下周的菜单是什么？ | domain_irrelevant | current_meeting | — | ✅ |
| 年会定在几月几号举办？ | domain_irrelevant | knowledge_base | — | ✅ |
| 年会定在几月几号举办？ | domain_irrelevant | current_meeting | — | ✅ |
| 隔壁组的 HC 还招人吗？ | domain_irrelevant | knowledge_base | — | ✅ |
| 隔壁组的 HC 还招人吗？ | domain_irrelevant | current_meeting | — | ✅ |
| 上海明天的天气怎么样？ | out_of_domain | knowledge_base | — | ✅ |
| 上海明天的天气怎么样？ | out_of_domain | current_meeting | — | ✅ |
| 怎么做红烧肉比较好吃？ | out_of_domain | knowledge_base | — | ✅ |
| 怎么做红烧肉比较好吃？ | out_of_domain | current_meeting | — | ✅ |
| 2026 年世界杯冠军是谁？ | out_of_domain | knowledge_base | — | ✅ |
| 2026 年世界杯冠军是谁？ | out_of_domain | current_meeting | — | ✅ |
| asdfghjkl 一二三四五？ | noise | knowledge_base | — | ✅ |
| asdfghjkl 一二三四五？ | noise | current_meeting | — | ✅ |
| 嗯嗯啊啊那个这个…… | noise | knowledge_base | — | ✅ |
| 嗯嗯啊啊那个这个…… | noise | current_meeting | — | ✅ |

## 四、未命中分析（hit@5 miss）

| scope | 期望文档 | 问题 | 实际 top3（doc_key, score） |
| --- | --- | --- | --- |
| current_meeting | mt-sprint | 关键依赖是什么？ | [] |

## 五、chunk 级未命中（内容断言失败）

- [current_meeting] 关键依赖是什么？（期望包含：见 dataset.json expect_chunk_contains）

## 六、分数分布（阈值校准参考，不自动放宽）


**结论：Go — 全部准入指标达标**