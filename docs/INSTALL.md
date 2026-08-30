# 安装与更新

本项目以源码方式提供。

## 使用 Git 安装

```bash
git clone https://github.com/luu175ktovtsvor-spec/tianyancha-agent-kit.git
cd tianyancha-agent-kit
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev,browser]'
python -m playwright install chromium
tyc-agent --help
```

浏览器自动化依赖 [Playwright 官方项目](https://github.com/microsoft/playwright)。

更新时：

```bash
git pull
python -m pip install -e '.[dev,browser]'
python -m playwright install chromium
python -m pytest
```

## 下载源码 ZIP

1. 在 GitHub 仓库页面选择 **Code → Download ZIP**。
2. 解压后在目录内执行：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install '.[browser]'
python -m playwright install chromium
tyc-agent --help
```

## 第一次运行完整工作流

先验证本地环境：

```bash
bash scripts/run_demo.sh
```

通过后，再在仓库外建立任务工作区。把行业、地区、电话和交付要求告诉 Agent；它可以在打开页面后建立浏览器选择器配置和筛选规则。完整命令与扫码登录步骤见 [完整工作流](WORKFLOW.md) 和 [Agent 操作清单](AGENT_QUICKSTART.md)。
