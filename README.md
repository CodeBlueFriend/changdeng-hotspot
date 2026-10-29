# 长灯说史 · 热点中心

[![Tests](https://github.com/CodeBlueFriend/changdeng-hotspot/actions/workflows/tests.yml/badge.svg)](https://github.com/CodeBlueFriend/changdeng-hotspot/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

一个本地运行的历史选题研究工具：将热点线索整理成带证据、版本和独立审核记录的选题卡，再交给制作流程。

**当前为0.1.0手工与人工审核版。尚未接入抖音自动采集、生成模型和联网检索，未完成真实历史准确率验收。** 程序不会填充虚构实时热榜，不执行平台发布。

## 能做什么

- 手工录入标题或批量JSON；保存去敏原始快照、字段定位、长ID、热度原值和单位。
- 隔离异常输入，保留未知来源时间、截断范围和回放记录。
- 按规则多标签归档；管理实体歧义、历史主张、来源家族及逐命题支持/反证。
- 归档实际阅读的证据文本，通过本地关键词检索。
- 版本化候选、人工独立审核、问题阻断和依赖哈希检查。
- 用户选定后生成自包含证据包，幂等导入待立项库；支持完整性检查和备份恢复。
- 对人工金标准计算推荐精度、召回、证据覆盖和Wilson区间，完整评价三次运行。

## 快速开始

需要macOS或Linux、Python 3.12及以上。当前使用POSIX文件锁，不支持原生Windows，可使用WSL。无需平台账号或模型密钥。

```sh
git clone https://github.com/CodeBlueFriend/changdeng-hotspot.git
cd changdeng-hotspot
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m hotspot serve
```

打开 http://127.0.0.1:8776 。服务只监听本机，按Ctrl+C停止。macOS也可双击`启动热点中心.command`；它默认使用本仓库的数据目录。

默认数据存放在`.runtime/01_选题库/热点中心/production`，不进入Git。需要独立数据目录或接入既有项目时：

```sh
.venv/bin/python -m hotspot --project /absolute/path/to/project serve --port 8778
```

`--project`、`--environment`是全局参数，应放在子命令前。测试和生产分别建库。示例数据只导入测试环境：

```sh
.venv/bin/python -m hotspot --environment test manual examples/manual.fixture.json
.venv/bin/python -m hotspot --environment test serve --port 8777
```

## 使用顺序

1. **热点池**：粘贴原始标题和来源链接，或导入JSON。查看快照、字段映射、范围与来源更新时间；保存不表示已确认上榜。
2. **关联候选**：从线索建立候选，人工补充实体、历史切口、主张和故事依据。候选修订递增版本；当前高级编辑采用JSON。
3. **证据审核**：归档真实阅读的正文、来源家族、版本和记录人。将每个关键主张连接到核对片段，并记录反证及措辞限制。
4. **独立审核**：不同于作者的审核身份读取审核包，提交实际核对结果。缺证据、实体歧义或旧版本审核不能放行。
5. **选定并导出**：用户选择已审核卡片并授权导入；程序重算资格，生成文件包和回执。后续故事线查重、选题立项和写稿仍由原工作流执行。
6. **质量与运行**：查看事件日志、核验文件完整性。依赖变化使旧审核失效；执行完整性检查可为已导出包生成复审通知。

默认目标时长15–60分钟。若指定项目存在`00_项目配置/内容选题偏好.json`，读取其`duration_minutes`，配置哈希进入审核依赖。配图、配音、剪辑和发布规则由制作工作流管理。

## 文档

- [项目设计与实现边界](docs/architecture.md)
- [完整使用说明](docs/usage.md)
- [JSON输入格式](docs/input-formats.md)
- [版本验证与交付范围](docs/delivery-report.md)
- [更新记录](CHANGELOG.md)、[贡献指南](CONTRIBUTING.md)、[安全边界](SECURITY.md)

## 开发与验证

从仓库根目录运行：

```sh
.venv/bin/python -m unittest discover -s tests -v
```

测试使用临时目录与构造数据，验证程序门禁、持久化、HTTP边界、导出恢复和指标计算；不证明史实、来源权限或线上准确率。CI在Linux的Python 3.12/3.14上运行同一套检查。

项目采用源码运行方式，目前没有发布PyPI包或容器镜像。核心依赖是jsonschema；界面使用原生HTML/CSS/JavaScript，无Node构建步骤。

## 开源范围

代码、公开设计文档、数据契约和构造示例按[MIT许可证](LICENSE)发布。用户导入的材料及其权利不因此获得许可；第三方依赖遵循各自许可证，见[依赖说明](THIRD_PARTY_NOTICES.md)。

原始私人交接包、本地项目资料、数据库、证据正文、运行报告、备份和凭据不随仓库公开。仓库可以独立运行，不依赖这些私有文件。
