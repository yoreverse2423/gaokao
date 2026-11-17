# 高考备考计划网站（可开发源码）

本仓库是「高考备考计划网站」的可开发源码，供继续开发与审阅使用。它不是已上线站点，也不代表现在就要部署；若以后要公开发布，需另作授权，并按白名单打包，不得带入个人档案与凭据。

## 内容结构

- `index.html`、`app.js`、`style.css`：多文件原站入口。源站以这三份文件为准，**不要用打包生成的单文件主界面覆盖源 `index.html`**。
- `data/*.json`：课表、周计划、资源等结构化数据。
- `materials/`：学生材料，以 Markdown 为准（已有的 geo html 保留）。文件名含「无答案」的是学生页，不是教师答案，必须保留。
- 根目录补充文档：`总课表.md`、`SCHEMA.md`、`打开说明.txt`、`首周任务_学生版.md`、`首二周补充_学生版.md`、`第3周补充_学生版.md`、`第4周补充_学生版.md` 等。
- `tools/`：校验、合并与打包脚本。

## 本地打开源站

直接用浏览器打开源 `index.html`，或在本目录起一个静态服务器（例如 `python3 -m http.server`）后访问。页面依赖 `data/bundle.js` 提供数据。

## 开发流程

1. 修改 `data/*.json` 后，运行：

   ```bash
   python3 tools/build.py
   ```

   该命令只把 `data/*.json` 合并为 `data/bundle.js`，**不会覆盖源 `index.html`**。

2. 校验计划数据：

   ```bash
   python3 tools/validate_plan.py
   ```

3. 跑测试：

   ```bash
   python3 tools/test_package.py
   node tools/test_app_dates.cjs
   ```

   `test_app_dates.cjs` 内部会对 Asia/Shanghai、UTC、America/New_York 三个时区各跑一遍。

## 29 周说明

29 周只是日历与课表计划，**并不表示题库或讲义已按 29 周齐备**。后续周可能仍有范围/占位，不能当作完整题库使用。

## 完整离线包

生成完整离线包时，`tools/package_site.py` 会先跑 `validate_plan.py` 与 `build.py`，再把产物写到 `dist/备考计划网站.zip` 与 `dist/site/`。包内 `index.html` 与 `主界面-单文件.html` 是同一份内嵌后的主界面，**不是源 `index.html`**。构建建议在临时副本上执行，具体步骤与追加补充材料的机械命令见 `构建说明.md`。

## 使用约定

- 勾选状态只存在本机浏览器，不同步手表或学习 App。
- 学习日以北京时间 04:00 为界。

## 公开边界

- **不要把本仓库推送到 `yoreverse2423/English` 或 `yoreverse2423/my-agent` 等其它已有学习仓库。**
- **不要把教师答案、private-answers、secret、凭据、聊天或健康/进度档案打进本仓库。**
- 学生材料里文件名含「无答案」的是学生页，不是教师答案，必须保留。
- 打包走白名单：收 `materials` 下学生页（名称含学生、打开说明、离线、课标、来源与边界、`knowledge.html`、`recall.html`，以及课表 resources 指向的学生文件），排除 `work`、`reviews`、`backups`、`PRIVATE`、`bot-only`、提示词和凭据。本地链接对不上会失败。

## 不在本次范围

- 不鼓励现在就部署上线。本仓库是可开发源码，发布须另作授权。
- 不要改功能脚本逻辑；构建与校验以现有脚本为准。
