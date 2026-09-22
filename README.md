# PubMed AI 检索

输入中文研究主题，自动用 AI（DeepSeek）翻译成标准 PubMed 检索式，检索并下载文献清单、摘要和开放获取全文。

## 功能

- **中文主题 → 标准 PubMed 检索式**：用 PICO 拆解概念，MeSH 主题词 + 自由词结合，字段标签明确，检索式稳定可复现；
- **自动下载**：元数据 + 摘要 + OA 全文（仅从 PMC Open Access 合法渠道）；
- **多格式导出**：命中汇总、文献清单 CSV、参考文献（GB/T 7714 + APA）、BibTeX、RIS、HTML 汇总页；
- **去重**：已下载的文献自动跳过，可询问是否重新下载；
- **待下载清单**：从命中汇总挑 PMID，批量补下排在后面的文献；
- **配置程序**：菜单式配置、严格校验，防止配置错乱；
- **清理工具**：一键清空所有使用痕迹。

## 快速开始

### 方式一：直接使用 exe（无需 Python）

1. 到 [Releases](../../releases) 下载 `PubMedAI-Search.exe`、`ConfigTool.exe`、`CleanTool.exe` 三个文件；
2. 双击 `配置设置.exe`，填入 DeepSeek API Key 和邮箱（在 [platform.deepseek.com](https://platform.deepseek.com) 免费获取）；
3. 双击 `PubMedAI检索.exe`，输入研究主题即可。

### 方式二：源码运行

```bash
python pubmed_ai.py
```

仅依赖 Python 标准库（3.9+），无第三方依赖。

## 配置说明

- 配置保存在用户目录 `~/.pubmed-ai/config.ini`（Windows 为 `C:\Users\你\.pubmed-ai\config.ini`），**不在程序目录**，防止分享程序时泄露密钥；
- API Key 仅保存在本机用户目录，不会上传到任何服务器；
- 首次运行「配置设置.exe」会引导填写。

## 免责声明

- 本工具非 PubMed / NCBI / NLM 官方工具，与上述机构无关联；
- 文献摘要和元数据来自 NCBI E-utilities，版权归原作者及出版方所有；
- 全文仅从 PMC Open Access 等合法开放获取渠道获取；
- AI 生成的检索式可能存在偏差，使用前请人工确认；
- 本工具仅供科研参考，不构成医疗建议、诊断或治疗依据。

## NCBI 使用合规

- 请求均携带 `tool` 和 `email` 参数；
- 遵守速率限制（无 API Key 约 3 请求/秒，有 Key 约 10 请求/秒）；
- 请勿将患者隐私信息输入本工具。

## 许可证

本项目采用 [AGPL-3.0](LICENSE) 许可证。如果你修改后通过网络提供服务，必须公开修改后的源码。

## 赞助

如果这个工具帮你节省了时间，可以请我喝杯咖啡 ☕

[爱发电](https://afdian.com/a/L-line-A)
