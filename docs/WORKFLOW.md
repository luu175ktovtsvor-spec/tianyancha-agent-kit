# 完整工作流：浏览器自动化到获客线索

完整链路是：Playwright 可见浏览器或已有数据 → 任务选择器与筛选规则 → 获客电话主表、主体分表、淘汰审计 → 飞书或其他交付。

## 1. 浏览器自动化

`browser-collect` 使用 [Playwright 官方项目](https://github.com/microsoft/playwright) 打开可见浏览器。Agent 先按任务工作区配置打开入口页；任务负责人在浏览器里扫码登录，进入结果页后告诉 Agent 继续，命令才按任务配置的 CSS 选择器读取结果。

```bash
tyc-agent browser-collect \
  --browser-profile /path/to/task-workspace/browser-profile.yaml \
  --output /path/to/task-workspace/captured-records.json
```

浏览器配置中包含目标页面、结果卡片、字段、风险数和翻页选择器。成立日期会整理成 `YYYY-MM-DD`；风险数会进入后续的风险筛选。配置保存在任务工作区。

任务负责人只需要说清目标行业、地区、电话和交付要求。Agent 可以检查已打开页面，并在任务工作区改选择器与筛选配置；公开仓库的示例不限制具体行业。

README 的成本图只用于说明会员页面和官方 API 的差异，不是本地执行步骤。按任务工作区配置完成浏览器采集和后续交付即可。

## 2. 筛选与电话分表

浏览器采集结果输出为 canonical JSON。随后用任务的筛选规则生成获客名单：

```bash
tyc-agent phone-leads \
  --profile /path/to/task-workspace/company-phone-leads.yaml \
  --input /path/to/task-workspace/captured-records.json \
  --input-kind canonical \
  --output-dir /path/to/task-workspace/output \
  --format xlsx
```

满足前面筛选条件后，只要一个来源实际返回的电话即可入库；多个电话会完整保留。筛选顺序和淘汰原因见 [筛选说明](METHODOLOGY.md)。

## 3. 飞书交付

输出的 JSONL、CSV、XLSX 可导入飞书。需要通过命令行操作飞书时，使用飞书官方开源工具 [lark-cli](https://github.com/larksuite/cli)。字段映射说明见 [飞书对接说明](FEISHU_INTEGRATION.md)。

## 4. 已有数据时

如果已有 JSON 数据，可跳过浏览器自动化，直接把 JSON 输入 `phone-leads`。
