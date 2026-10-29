# 使用说明

## 启动与数据目录

在仓库根目录安装requirements.txt后运行`python -m hotspot serve`（使用虚拟环境的python）。默认网址为http://127.0.0.1:8776，Ctrl+C停止。端口被占用时使用`serve --port 8778`。

默认项目目录为仓库内`.runtime`。`--project /absolute/project`可指定其他位置，该目录下会创建`01_选题库/热点中心`；不会移动原有资料。测试使用`--environment test`，在界面保留明显标记。

macOS启动脚本使用自身所在目录定位程序，不依赖终端当前目录。若要采用其他数据根：`./启动热点中心.command --project /absolute/project`。

## 线索到候选

网页“热点池”支持每行一个标题；单条可附HTTPS来源链接。来源链接只保存，不会访问网页或执行其中指令。多条不同链接使用JSON导入。

```sh
.venv/bin/python -m hotspot --environment test manual examples/manual.fixture.json
.venv/bin/python -m hotspot --environment test status
.venv/bin/python -m hotspot --environment test replay SNAP-ID
```

命令返回实际snapshot_id与record_id。`SNAP-ID`等占位符须替换成真实返回值。fixture导入生产会失败；不要为了通过检查改掉样例标记。

点击“建候选”，填写实际作者身份。候选初始均为待查。通过“修订候选”补充实体、主张、证据引用和建议时长。修订按钮会递增版本；JSON导入时也须明确提供递增版本。必要字段见[候选契约](../schemas/topic_candidate.schema.json)。

CLI候选输入是`{"author":"作者","candidate":{...}}`，可用以下命令保存：

```sh
.venv/bin/python -m hotspot candidate candidate-submission.json
```

`examples/candidate.template.json`只展示结构，其引用是虚构的，不能直接作为已入库候选提交。

## 证据与审核

先归档实际正文，再在候选evidence中填写与归档一致的ID、标题、家族和URL。access_status如实记录是否读到原文。每个关键主张都须建立evidence_links，填写实际核对的片段、位置、判断及核对人。

```sh
.venv/bin/python -m hotspot evidence evidence.json
.venv/bin/python -m hotspot search '古城 考古'
.venv/bin/python -m hotspot packet TOPIC-ID
.venv/bin/python -m hotspot review review.json
.venv/bin/python -m hotspot gate TOPIC-ID
```

搜索为空格分隔的关键词交集，不是语义检索。packet输出当前版本、输入哈希、事实输入和结构阻断项。应由实际独立审核者阅读原文、反证和限定语，再提交审核记录；作者不能仅换一个身份字符串就视为完成独立审核。

证据文件存在、摘录匹配、审核者勾选都不能自动证明历史真实性。原文不支持时应hold/rejected，不能依靠提高编辑评分放行。

问题修复后更新候选版本及问题状态，重做审核。已存在的候选、快照、证据历史不会覆盖。

## 导出与既有项目集成

```sh
.venv/bin/python -m hotspot export TOPIC-ID --actor 选择人 --authorize
```

仅允许history_long_video目标。`--authorize`表示选择当前版本并授权导入待立项库，既不代表同意发布，也不代表新集全部资料审核完成。

回执中包含bundle、inbox和receipt_id；episode_id为空。包内有候选、审核、输入清单、授权范围、原始快照、证据副本、Markdown关联卡和文件哈希清单。相同ID、版本、目标重复执行返回原回执。

对接其他工作台时，将`--project`指向其数据根，读取`01_选题库/热点导入库`。本仓库不依赖任何私人工作台源码，也不会自动重写其CLI。下游应核验bundle-manifest.json并保留采用副本，继续执行故事线查重、用户选题、稿件审核等原有规则。

输入依赖变更后，先保存候选新版本并复核，再重新导出。已经导出的同一版本不会被新证据静默覆盖。

## 完整性、撤回与恢复

```sh
.venv/bin/python -m hotspot audit
.venv/bin/python -m hotspot invalidate correction.json
.venv/bin/python -m hotspot backup /absolute/path/new-backup
.venv/bin/python -m hotspot restore /absolute/path/new-backup /absolute/path/new-environment
```

撤回输入格式见[input-formats.md](input-formats.md)。撤回保留旧文件和回执，当前没有取消撤回操作；更正后使用新编号重新核验。

备份目标不得在运行数据目录内部，也不能已经存在。恢复目标是**整个环境目录**，例如`/new-project/01_选题库/热点中心/production`，并不是项目根。恢复后用`--project /new-project`启动。同一目标恢复前应停止服务；程序不自动切换正在使用的目录。

文件被修改时保留异常，不重新计算哈希掩盖变更。audit在导出目录的“复审通知”保存影响记录；下游需要自行处理这些通知。

## 评测

```sh
.venv/bin/python -m hotspot benchmark gold.json runs.json --output evaluation.json
```

输入为人工定稿的完整锁定集和三次预测。不得使用示例作为真实金标，不得把展示5条上限用于评测分母。程序报告TP、FP、FN、待裁决数、精度、召回、直接关联召回、关键证据覆盖、P0和Wilson区间；零分母为null，样本不足不会记PASS。

当前没有真实金标成绩。数据获得方式、分组拆分、防答案泄露和人工身份须另行核验，计算器不会证明这些条件成立。

## 常见问题

- **没有自动热点**：当前版本只有手工适配器。collect返回NOT_CONFIGURED且不发网络请求，修改文案不会开通来源。
- **JSON字段错误**：按schemas中的类型和必填字段修正；导入异常会隔离，不冒充空榜成功。
- **审核输入变化**：重新读取packet，核对新证据/配置，再提交当前版本审核。
- **数据库被锁**：等待当前写入结束，不要同时手工编辑SQLite；备份和服务操作使用同一写锁。
- **Windows报fcntl错误**：使用WSL；本版尚未实现Windows原生文件锁。
- **恢复后看不到数据**：核对环境目录层级和--environment参数，测试与生产分别存放。
