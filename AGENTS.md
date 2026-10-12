# AGENTS.md — AI 开发交接文档 · 易经灵占 YI JING INSIGHT

> **本文件的用途**：把项目全貌交给任何大模型/编码代理（新会话、零上下文），读完即可无缝接手继续开发。
> 给 AI 的第一步指令示例：*「读 AGENTS.md，然后按第 4 节待办第 N 项开工」*。

---

## 0. 你正在接手什么

- **项目**：易经灵占 · YI JING INSIGHT —— 单文件易经占卜网页应用（起卦 → 卦象可视化 → 断卦解读）
- **仓库**：<https://github.com/WAY227/yijing-insight>（public，`main` 分支即部署源）
- **线上**：<https://way227.github.io/yijing-insight/>（GitHub Pages，push 到 main 后约 1 分钟自动重建）
- **技术栈**：原生 JS + Tailwind Play CDN + marked + html2canvas + jsPDF；服务端纯 Python 标准库，零依赖
- `README.md` 是面向访客的门面（结构已按涨星优化），**不要动它**；本文件才是给开发者/代理看的

## 1. 铁律（违反 = 白干或出事故）

1. **`index.html` 是构建产物，不是源码！** 前端的源 = `build.py` 里的 `TEMPLATE` 原始字符串。改界面/逻辑必须改 `build.py` → 跑 `python build.py` 重新生成 → **两个文件一起提交**。直接改 index.html 会在下次构建时被覆盖丢失。
2. **数据注入**：`build.py` 读 `hexagrams2.min.json` 注入模板。64 卦字段：`n`卦序、`z`卦名、`p`拼音、`en`英译、`j`今译、`b`二进制爻位、`up`/`low`上下卦、`g`古文卦辞、`y`爻辞（`l1`–`l6` + 用九/用六）。
3. **永远不要提交**：`_ref/`（原站整站抓取素材，**版权风险**）、`divine_t*.json`（调试产物+用户解读记录）、`*.pem`（私钥）、`docs/_*.png`（临时截图）。`.gitignore` 已配好，别删规则。
4. **API Key 安全**：`GEMINI_API_KEY` 只存浏览器 localStorage、随请求体传输。任何改动不得把 Key 硬编码进代码/构建产物/日志。
5. **jsPDF 必须用动态 `<script>` 标签加载 UMD 包**（`savePDF`/`loadJsPDF` 已修好，勿回退）：cdnjs 的 `jspdf.umd.min.js` 用 `import()` 拿不到导出（UMD 无 ESM 具名导出，拿到空命名空间必报错）；`jspdf.es.min.js` 含裸模块引用（`@babel/runtime/...`）浏览器无法解析。现有兜底：jsPDF 加载失败 → 自动改下载 PNG 长图。

## 2. 架构速览

```
build.py             # ★ 源头：TEMPLATE = 整个前端（HTML/CSS/JS），构建时注入卦数据 → index.html
index.html           # 构建产物（单文件应用，双击即玩 / 可静态托管）
server.py            # 本地中转服务器：静态托管 + POST /api/divine 转发 Gemini
                     #   自动探测 Windows 系统代理/HTTPS_PROXY；PORT 环境变量默认 8763；GET /healthz 探活
hexagrams2.min.json  # 64 卦数据（build.py 的输入）
jing_full.json       # 周易经文全文（参考数据）
bin64.json           # 卦序↔二进制映射（参考数据）
docs/                # README 用截图（home.png / result.png）
```

前端要点：

- **双 AI 通道**：优先 `fetch("/api/divine")`（需 server.py）；无服务器时浏览器直连 `generativelanguage.googleapis.com`。有 `/healthz` 探测 + 优雅降级逻辑，改动时保持
- **本地断卦引擎**（无 Key 离线可用）：三枚铜钱 → 爻值 6/7/8/9（6老阴/7少阳/8少阴/9老阳）→ 本卦+动爻+之卦；**朱熹变占规则**（动爻数 0–6 各有取断规则，代码内已有完整映射表）；纯本地生成 markdown 解读（卦象总览/动爻详解/行动建议）
- **视觉规范**：底色 `#0C0C0E`、主金 `#C5A059`、字体 Noto Serif SC + Cormorant Garamond；改动不得破坏这套深底金字的调性
- Tailwind Play CDN 的 production 警告是已知的、接受的（单文件零构建是卖点）
- localStorage key：`GEMINI_API_KEY`（新增存储前先 grep 现有 key 避免冲突）

## 3. 开发工作流（Windows + Git Bash 环境）

```bash
# 1) 改代码 —— 改 build.py 的 TEMPLATE，然后：
python build.py                     # 重新生成 index.html（打印字符数即成功）

# 2) 本地验证
python server.py                    # http://127.0.0.1:8763（手机连同一 WiFi 也能开）
#   或直接双击 index.html（file:// 下直连通道可用）

# 3) 自动化测试（Playwright 已装，Python 3.8 sync API，无头 chromium 可用）
#   完整流程：goto → 点 "START NEW DIVINATION" → 等 4s → 断言/截图
#   PDF 导出：new_context(accept_downloads=True) + expect_download，验证文件头 b'%PDF'
#   坑：screenshot 要给 timeout=60000 等 Google Fonts；console 可看 html2canvas 日志

# 4) 提交部署
git add -A && git commit -m "..." && git push      # push 到 main → Pages 自动重建
gh api repos/WAY227/yijing-insight/pages/builds/latest --jq '{status, commit}'
#   status=built 且 commit 与本地一致 → 部署完成；再用无头浏览器线上复测一遍
```

## 4. 待办 / 建议方向（按优先级，接手后从这里挑活）

1. **去掉页脚 "· CLONE" 字样**（build.py 模板内搜 `CLONE`），换成正式版本号如 `v1.1.0`
2. **占卜历史记录**：localStorage 存最近 N 卦（问题+卦象+时间），首页底部加「命录 · History」回看列表
3. **更多起卦方式**：梅花易数（时间卦/数字卦）、六爻纳甲装卦 —— 扩展本地引擎，规则需写清
4. **每日一卦**：日期 + 用户盐做确定性起卦，同一天所有人/同一人结果稳定
5. **server.py 云部署**：Render/Railway 免费档部署指南，或改写成 Cloudflare Worker，让 Pages 用户也能走中转
6. **国际化**：README 拆分中英双版；界面加中/EN 切换（卦辞古文保留繁体）
7. **测试**：断卦规则用 pytest 覆盖（6/7/8/9 组合 → 期望卦例）

## 5. 环境速览

- Windows 10+ / Git Bash；**Python 3.8**（注意语法兼容，别用 3.9+ 特性）
- `gh` CLI 已登录 **WAY227**（repo scope）；git user: ling-cc；CRLF 警告无害
- 控制台打印中文 JSON 可能 GBK 乱码 —— 检查数据用 `python -c "import json;..."` 而非 cat/head
- 仓库简介 + 15 个 topics 已按 SEO 优化过，别乱动；About 网站字段指向 Pages demo

## 6. 验收标准（任何改动的「完成」定义）

- [ ] `python build.py` 无报错，index.html 同步更新
- [ ] 本地 file:// 打开：起卦 → 结果页 → 本地断卦解读，全流程可走
- [ ] Save Result 导出合法 PDF（`%PDF` 文件头）或 PNG 兜底，无报错弹窗
- [ ] push 后 Pages 构建成功（commit 对得上），**线上**复测同样流程
- [ ] 深底金字视觉未破坏；375px 手机宽度不塌
