# 📊 宏观经济仪表盘 · 自动化版本

每天定时拉取美 / 中 / 日 / 欧 / 全球市场的宏观数据，生成可视化报告 + 资产配置参考 + 微信推送。

## ✨ 功能

- **数据采集**：FRED API（美国/欧元区/日本宏观数据）+ akshare（中国数据）+ Yahoo Finance（市场行情）
- **可视化看板**：每个指标含 12 月趋势图、信号判断、当前判断、个人参考方向
- **综合面板**：宏观环境综合评分、四大维度分项打分、资产配置建议（进取型/稳健型）
- **关键告警**：红色信号 + 月度大变动 + 较上次运行对比
- **历史相似度**：对比 2008雷曼 / 2018加息+贸易战 / 2020新冠 / 2022高通胀 / 2024软着陆

## 🚀 三种使用方式

### 1. 本地运行（开发/调试）

```bash
pip install -r requirements.txt
export FRED_API_KEY="你的Key"   # 或在交互模式下输入一次自动保存
python econ_dashboard.py
```

报告会自动在浏览器打开。

### 2. 本地定时运行（cron）

```bash
python econ_dashboard.py --setup-cron
```

按提示选择每周/每月频率即可。

### 3. GitHub Actions 自动化（每天定时运行 + 推送微信）⭐ 推荐

**步骤 A：在 GitHub 创建仓库**

1. 在 GitHub 上新建一个**私有仓库**（建议私有，避免 API Key 暴露）
2. 把本目录下所有文件 push 上去：

```bash
git init
git add .
git commit -m "init"
git remote add origin git@github.com:你的用户名/你的仓库名.git
git branch -M main
git push -u origin main
```

**步骤 B：申请 Server酱（用于推送微信）**

1. 访问 [https://sct.ftqq.com](https://sct.ftqq.com)，用微信扫码登录
2. 复制 **SendKey**（页面顶部一长串字符）
3. 微信扫码绑定接收消息的微信号
4. 免费版每天可推 5 条，足够日报使用

**步骤 C：在 GitHub 仓库配置 Secrets**

进入仓库 → `Settings` → `Secrets and variables` → `Actions` → `New repository secret`，添加：

| Secret 名称 | 值 |
|---|---|
| `FRED_API_KEY` | 你的 FRED API Key |
| `SERVERCHAN_KEY` | Server酱 SendKey |
| `WECOM_WEBHOOK` | （可选）企业微信群机器人 webhook URL |

**步骤 D：开启 GitHub Pages**

进入仓库 → `Settings` → `Pages`：
- **Source**: Deploy from a branch
- **Branch**: `gh-pages` / `(root)`
- 第一次运行后会自动创建该分支

**步骤 E：测试运行**

进入仓库 → `Actions` → 选择 `每日宏观经济日报` workflow → 点击 `Run workflow` 手动触发一次。

执行成功后：
- 微信会收到推送（标题示例：`📊 宏观日报 05-07 ⚠ 偏防御`）
- 微信中点击链接可看到完整 HTML 报告（GitHub Pages）
- 仓库会自动 commit 一份 `.dashboard_snapshot.json`（下次运行用于"较上次运行"对比）

之后每天北京时间 **08:30** 会自动运行。

## ⏰ 调整运行时间

编辑 `.github/workflows/daily.yml` 中的 `cron`：

```yaml
- cron: '30 0 * * *'   # UTC 00:30 = 北京 08:30
```

常用时间对照：
| 北京时间 | UTC cron |
|---|---|
| 早 7:00 | `0 23 * * *` |
| 早 8:30 | `30 0 * * *` |
| 晚 9:00 | `0 13 * * *` |

## 🔧 命令行参数

```bash
python econ_dashboard.py [选项]

  --no-open          不自动打开浏览器
  --ci-mode          CI模式：无交互、无浏览器、固定文件名
  --output-dir DIR   HTML输出目录（默认脚本同目录）
  --summary-md PATH  额外输出Markdown摘要文件
  --push-wechat      通过Server酱推送到微信
  --public-url URL   完整报告的公开URL（用于微信链接）
  --setup-cron       配置本地定时任务
```

## 🐛 常见问题

**Q: GitHub Actions 运行失败，akshare 部分指标拉不到**

A: GitHub 服务器在美国，访问 sina/eastmoney 偶有不稳定。脚本内置错误降级，单个指标失败不影响整体。如果中国数据全部失败，可以等下次自动重试或手动重跑。

**Q: 微信没收到推送**

A: 检查：
1. `SERVERCHAN_KEY` 是否正确配置在 Secrets 里
2. 是否已在 Server酱网站绑定接收微信
3. Server酱免费版每日 5 条限额，超限会被拒
4. 查看 Actions 运行日志，搜索 `[Server酱]` 相关输出

**Q: 想换成企业微信群推送**

A: 在企业微信群里"添加机器人 → 自定义"获取 webhook URL，配置到 `WECOM_WEBHOOK` secret。代码已支持（`push_to_wecom` 函数），但默认未启用，需修改 main 中的 `push_to_wechat(...)` 改为 `push_to_wecom(...)`。

## 📁 项目结构

```
.
├── econ_dashboard.py            # 主程序
├── requirements.txt             # Python 依赖
├── .github/workflows/daily.yml  # GitHub Actions 定时任务
├── .gitignore
├── README.md                    # 本文件
└── .dashboard_snapshot.json     # 自动生成，不要手动修改
```

## 📜 License

仅供个人学习参考。涉及任何资产配置建议均不构成投资建议，请结合自身情况谨慎决策。
