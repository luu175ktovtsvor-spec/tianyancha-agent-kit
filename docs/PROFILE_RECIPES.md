# 企业获客线索 profile 配置

profile 用来表达筛选规则，不负责查询页面。输入可以来自浏览器采集结果或已有 JSON 文件。

公开模板只是示例。真实行业的保留词、排除词、主体、风险、地区和电话标准，应由任务负责人告诉 Agent 后再在任务工作区中改造。

如果使用 `browser-collect`，浏览器选择器配置还应对应页面中的成立日期、状态、地区、电话和风险数。`browser.risk.self`、`browser.risk.related`、`browser.risk.history` 分别用于读取三类风险数量；读取到的值会进入同一套 `max_risk` 筛选规则。

以 [公开模板](../examples/industry-profile.example.yaml) 为起点：

```bash
cp examples/industry-profile.example.yaml /path/to/task-workspace/profiles/company-phone-leads.yaml
tyc-agent validate --profile /path/to/task-workspace/profiles/company-phone-leads.yaml
```

## 关键配置

| 配置 | 作用 | 默认/说明 |
| --- | --- | --- |
| `positive_terms` / `negative_terms` / `required_terms` | 行业语义边界 | 匹配名称、经营范围和类别；负向词优先排除 |
| `entity_classes` | 主体分流 | 个体工商户、企业、其他主体；按顺序首次匹配 |
| `phone_leads.min_phone_count` | 电话入库下限 | 公开模板为 `1`；有一个电话即可入库 |
| `phone_leads.target_entity_classes` | 最终交付主体类 | 默认个体工商户和企业 |
| `established_on_or_after` / `allowed_statuses` / `max_risk` | 质量规则 | 可按任务需要设置 |
| `location.allowed_cities` / `allowed_districts` | 地区边界 | 空值表示不限制 |
| `privacy.redact_fields` | 外发时需要隐藏的字段 | 仅用于经批准的外发版本 |

## 主体分类

`phone-leads` 获客线索命令按 `entity_classes` 的书写顺序匹配 `entity_type`：

```yaml
entity_classes:
  - key: individual_business
    label: 个体工商户
    markers: [个体工商户]
  - key: enterprise
    label: 企业
    markers: [公司, 企业, 合伙企业, 个人独资企业, 分公司]
  - key: other
    label: 其他主体
    fallback: true
```

`phone_leads.target_entity_classes` 决定哪些类别进入最终电话表。未选择的类别保留在任务工作区的淘汰审计文件中，原因标记为 `entity_class.<类别>`。

## 电话规则

`phone-leads` 固定要求至少一个电话，因此 `min_phone_count: 1` 是“所有有电话主体入库”的默认做法。若任务负责人提高该值，属于主动收紧交付规则，而不是工具默认行为。

同一主体的多个电话会被保留为 `phone_1`、`phone_2` 等动态列；不能只保留第一个号码。
