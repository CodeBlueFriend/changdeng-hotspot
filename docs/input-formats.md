# 操作格式

以下均为结构说明，不是生产事实。用测试环境运行示例。

手工导入：

```json
{"is_fixture":true,"items":[{"id":"123456789012345678901","title":"【构造样例】古城+考古","url":null,"rank":null,"heat":"1.2万","unit":"热度指数"}],"truncated":true}
```

无来源更新时间就保持未知。手工输入的`board_type`不被当作已核验的平台榜单。正常空输入须显式`allow_empty:true`；异常空数组隔离。

证据归档：

```json
{"evidence_id":"SRC-001","version":1,"title":"材料标题","source_family_id":"原始作品或通稿编号","recorded_by":"实际记录人","url":null,"text":"实际读到并获准本地留存的正文"}
```

同编号新证据递增version，会改变依赖该来源的审核输入哈希。修改后的卡片也须保存新candidate_version。关键词检索以空格分词；不提供语义检索或来源真实性自动判断。

人工审核：先用`packet TOPIC-ID`取得当前`input_hash`和版本，记录真实核验结果：

```json
{"candidate_id":"TOPIC-ID","candidate_version":2,"input_hash":"当前审核包返回的64位哈希","reviewer_id":"独立审核者身份","reviewer_type":"human","independence_record":"与作者分离，核对了哪些原始材料","notes":"实际结论、反证处理及限制","decision":"hold","attest_checked":false,"checked_claim_ids":[]}
```

只有实际完成核查后才用`approved`和`attest_checked:true`，checked_claim_ids必须覆盖全部关键主张。程序不代填。`hold`和`rejected`都不允许导出。当前版本采取保守门槛：P0/P1/P2与事实性问题须rechecked，不实现非事实P1豁免快捷通道。

撤回：

```json
{"kind":"snapshot","id":"SNAP-ID","reason":"明确更正或撤回原因"}
```

`kind`也支持`evidence_asset`和`candidate`。撤回后保留全部原文与回执。此版本不提供撤销撤回按钮，需以新编号记录更正后素材，重新审核。

基准：gold需要human_finalized、locked、contaminated=false、reviewers、cases。每例需要唯一id、label（positive/negative/disputed）、direct、critical_claims、is_synthetic=false。预测文件为3个独立运行的数组，各有run_id、predictions；每个预测需要id、decision（recommend/hold/reject）、p0_count、supported_critical_claims。必须包含全部锁定ID，不得套用展示上限。

金标的分组拆分、隐藏答案、人工身份和真实资料取得情况须由评测执行者另行审计；本版计算器不自动证明这些条件。真实验收报告未运行。
