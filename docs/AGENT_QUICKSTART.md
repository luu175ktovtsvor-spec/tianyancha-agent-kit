# Agent 操作清单

这份清单用于把仓库交给 Agent 后，从零完成一次可验证运行。

## 1. 安装

```bash
git clone https://github.com/luu175ktovtsvor-spec/tianyancha-agent-kit.git
cd tianyancha-agent-kit
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev,browser]'
.venv/bin/python -m playwright install chromium
```

## 2. 先跑本地示例

```bash
bash scripts/run_demo.sh
```

成功条件：终端输出 JSON，其中 `captured_records` 为 `5`、`phone_leads` 为 `2`、`rejected` 为 `3`。这一步会验证依赖、Playwright、本地浏览器采集、筛选和 XLSX 获客线索导出。

## 3. 真实任务前需要向任务负责人取得的内容

- 本次使用的数据来源；
- 浏览器入口页；页面能打开时，由 Agent 检查页面并在任务工作区建立 CSS 选择器配置；
- 筛选规则：行业词、主体、风险、地区和入库条件；
- 飞书目标表与字段对应方式（如果需要同步）。
- 登录分工：Agent 打开浏览器，任务负责人扫码登录，并在结果页准备好后告诉 Agent 继续。

这些内容都保存在仓库外的任务工作区。没有入口页、筛选规则或交付目标时，Agent 应停下并向任务负责人索取；用户不需要先手写 YAML 或 CSS 选择器。

## 行业规则不是固定的

仓库中的示例只展示写法和流程，不是某个行业的推荐规则。任务负责人可以直接告诉 Agent 想要的行业、保留词、排除词、主体、风险、地区和电话要求；Agent 根据这些要求改任务工作区里的 profile 和选择器。每个行业、每个任务都可以使用不同的筛选逻辑。

给 Agent 的最简需求模板见根目录 [AGENTS.md](../AGENTS.md)。

## 本地工作流优先

README 的成本图只用于说明会员页面和官方 API 的差异，不是执行步骤。Agent 应先跑本地示例，再按任务工作区配置完成采集、筛选、导出和飞书交付。

## 4. 真实浏览器采集

```bash
tyc-agent browser-collect \
  --browser-profile /path/to/task-workspace/browser-profile.yaml \
  --output /path/to/task-workspace/captured-records.json
```

命令会打开可见浏览器。Agent 先停在这里，任务负责人在浏览器里扫码登录并进入结果页；任务负责人说“可以继续”后，Agent 再确认终端并读取结果。不要在登录前使用 `--ready`；它只适用于结果页已经准备好的情况。

## 5. 筛选并导出

```bash
tyc-agent phone-leads \
  --profile /path/to/task-workspace/company-phone-leads.yaml \
  --input /path/to/task-workspace/captured-records.json \
  --input-kind canonical \
  --format xlsx \
  --output-dir /path/to/task-workspace/output
```

完成后检查：获客电话主表、主体分表、淘汰原因文件是否都生成；获客主体是否至少有一个来源返回的电话；多个电话是否完整保留。

## 6. 飞书

使用 [lark-cli](https://github.com/larksuite/cli) 或人工导入，把确认后的 XLSX/CSV 写入飞书。尚未安装时，Agent 应按官方主页安装并验证该命令。真实对接在任务工作区配置。
