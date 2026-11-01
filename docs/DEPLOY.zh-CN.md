# 私人卡片本部署指南

[English](DEPLOY.en.md) · [项目首页](../README.md)

本项目面向单人使用，界面目前为中文。可以在本机保存 Markdown，或在 Vercel 上使用 Neon PostgreSQL。两种模式不自动同步；Markdown 下载不要求后台将每条笔记保存成磁盘文件。

## 1. 准备

- Python **3.13**、Node.js **24**、npm、Git。
- 云端部署另需自己的 GitHub、Vercel 和 Neon 账户；域名可选。
- 克隆或 Fork 本仓库。下文所有命令均从项目根目录运行。
- 仓库不含笔记或环境文件。首次本地启动创建 `data/notes`、`data/trash` 和默认分类，不带演示笔记。迁移已有库时先核对原数据，不要把意外启动的空库当成迁移成功。

本项目不包含注册、公开分享、附件、AI 或自动同步。部署文档为英文不代表界面切换为英文。

## 2. 本地部署

### Windows

安装 Python 与 Node 后运行：

```powershell
.\安装.cmd
.\启动卡片本.cmd
```

访问 `http://127.0.0.1:8765`。`停止卡片本.cmd` 停止本项目的服务；关闭浏览器不会停止后台服务。`创建桌面入口.cmd` 可创建快捷方式。重复启动复用同一项目、同一数据目录的服务；端口属于其他程序时会报错，不会结束其他服务。

移动目录或换电脑后重新安装依赖。旧 `.venv` 不可当作可移植环境；先重命名保留，再运行安装脚本。桌面快捷方式也需要重新创建。

### macOS / Linux

```sh
python3.13 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.lock.txt
npm ci
npm run build
python -m uvicorn backend.app:create_app --factory --host 127.0.0.1 --port 8765 --workers 1
```

关闭当前服务终端或按 Ctrl+C 停止。文件模式只能有一个进程写同一数据目录，不要增加 worker 数量。

### 本地数据与草稿

```text
data/
  categories.json   分类、顺序和图标
  notes/*.md        正常笔记
  trash/*.md        回收站
```

可通过 `NOTEBOOK_DATA_DIR` 指定其他目录。默认仅监听本机，不向公网开放。无密钥的本地模式健康接口会返回实际数据目录，便于核对服务归属。

未保存草稿在当前浏览器的 localStorage，按网址隔离，不在数据目录中。换浏览器、端口、域名或从 HTTP 切换 HTTPS 后，不会自动出现原网址的草稿。先保存草稿再迁移，勿通过清缓存解决异常。

## 3. Docker 本地部署

需要 Docker 和 Compose：

```sh
docker compose up -d --build
docker compose logs --tail 50
# 停止
docker compose down
```

默认仍访问 `http://127.0.0.1:8765`，`./data` 独立挂载到容器 `/data`，端口只绑定主机 loopback。不要通过修改端口映射把未鉴权的文件模式直接暴露到公网。远程使用可选择云端方案，或自己管理的 HTTPS 与私有访问通道。

## 4. Vercel + Neon 云端部署

### 4.1 创建自己的资源

1. 将本仓库 Fork 到自己的 GitHub，或使用自己的副本创建仓库。
2. 在 Vercel 中导入该仓库。使用 **Vite** 框架、`npm run build` 构建命令、`dist` 输出目录和 Node.js 24。Python 版本由 `.python-version` 固定为 3.13。
3. 在项目 Storage / Marketplace 创建 **Neon PostgreSQL** 并连接项目的 **Production** 环境。不要启用 Neon Auth；本应用已有单人密钥入口。建议数据库和函数选同一地区，默认函数地区为新加坡 `sin1`。其他地区同时修改 `vercel.json` 中的 `regions`。
4. 如果 Neon 要求确认服务条款，请由账户本人完成。免费计划额度、地区和可用性以控制台为准；不要默认升级付费计划。
5. Neon 集成通常会注入 `DATABASE_URL` 等变量。Preview / Development 使用独立数据库或分支，不要连接正式库。后文初始化前应核对所用连接串属于哪个数据库。

如果初次自动部署发生在配置之前，接口会因缺少云端配置而拒绝启动。完成下面的环境变量和数据库初始化，再重新部署即可；不要为了启动成功关闭鉴权或改用临时文件存储。

### 4.2 生成访问密钥哈希

在已安装依赖的本地终端运行：

```sh
python -m scripts.cloud key
```

按提示输入至少 16 个字符的密钥，两次输入不回显。输出形如 `NOTEBOOK_KEY_HASH=scrypt:...`；只把等号后的**完整哈希**保存到 Vercel 的 `NOTEBOOK_KEY_HASH` Secret。明文密钥自己保存在密码管理器里，不要写入前端、仓库或 `VITE_` 变量。

### 4.3 配置 Production 环境变量

参照根目录 `.env.cloud.example`，在 Vercel 项目设置中添加：

| 变量 | 值 |
| --- | --- |
| `NOTEBOOK_STORAGE` | `postgres` |
| `DATABASE_URL` | Neon 的池化连接串，包含其要求的 TLS 参数；仅后端可用 |
| `NOTEBOOK_KEY_HASH` | 上一步生成的 scrypt 哈希，设为 Secret |
| `NOTEBOOK_ALLOWED_HOSTS` | 自己的自定义域名，例如 `notes.example.com`；多个用逗号分隔，不带协议 |
| `NOTEBOOK_ALLOWED_ORIGINS` | 自己的 HTTPS 来源，例如 `https://notes.example.com`；多个用逗号分隔 |

Vercel 当前部署地址和项目主生产地址会从系统环境变量加入允许 Host；使用其他别名时也需显式添加。暂时只用 Vercel 默认地址时，可以不设置自定义域名两项。API 的同源写入检查会允许当前请求来源。

环境变量变更后需要重新部署。`DATABASE_URL`、密钥哈希和其他凭证不得使用 `VITE_` 前缀。

### 4.4 初始化数据库

先在本地安装 Python 依赖，然后将正确的 Neon 连接串设置在当前终端中。以下示例隐藏输入，不把连接串写进命令历史：

Windows PowerShell：

```powershell
$env:DATABASE_URL = [System.Net.NetworkCredential]::new('', (Read-Host 'Neon connection string' -AsSecureString)).Password
python -m scripts.cloud init
Remove-Item Env:DATABASE_URL
```

macOS / Linux（Bash）：

```bash
read -r -s -p 'Neon connection string: ' DATABASE_URL
printf '\n'
export DATABASE_URL
python -m scripts.cloud init
unset DATABASE_URL
```

`init` 只创建本应用的表和默认分类，不删除已有笔记。运行时使用池化连接；初始化、导入时也可设置 `DATABASE_URL_UNPOOLED`，脚本优先使用它。脚本**不会自动加载 `.env.local`**；若使用 `vercel env pull`，需自行安全加载相应环境，且不要把下载的文件提交。

全新使用只需 `init`。如果没有本地数据，不要运行 `import`。

### 4.5 可选：导入已有 Markdown 库

1. 保存浏览器草稿，停止原数据目录的写入，复制整个原数据目录作备份。
2. 确认原目录同时含 `notes/`、`trash/`、`categories.json`；使用上一节方式设置正确的数据库连接。
3. 从项目根目录运行（将 `path/to/notebook-data` 替换成原目录，Windows 路径有空格时保留引号）：

```sh
python -m scripts.cloud inspect --source "path/to/notebook-data"
python -m scripts.cloud import --source "path/to/notebook-data"
python -m scripts.cloud verify --source "path/to/notebook-data"
```

导入使用事务，保留 ID、文件名、日期、标签、来源、未知元信息、分类配置和回收站。它会核对文件字节哈希；已有相同数据可重复执行，已有不同笔记或分类配置则停止，不会静默覆盖。解析失败或重复 ID 会阻止导入。导入后再打开原本地版编辑，产生的是独立副本，不会同步到云端。

### 4.6 发布与验收

在 Vercel 控制台重新部署 Production。也可安装 GitHub / Vercel CLI 后，从自己的副本使用：

```sh
npx vercel link
npx vercel deploy --prod --skip-domain
# 验收准确的返回地址后，再 promote 同一个部署
npx vercel promote <tested-deployment-url>
```

核对登录的团队、项目和环境。发布前确保 `data/`、`.env*`、`.vercel/`、`.runtime/`、归档和构建缓存未提交；本仓库已有忽略规则。不要通过复制私人项目整个文件夹来代替克隆公开源码。

建议验收：

- 首页显示密钥入口，`GET /api/auth/status` 返回 `required: true`；未解锁时 `/api/meta`、`/api/notes`、导出及备份应为 401。
- 输入密钥后能保存、刷新、搜索、补录旧日期和导出 Markdown；多标签和多个关键词同时满足。
- 另一个窗口修改同一笔记后，旧版本保存应提示冲突并保留草稿。
- 退出或撤销所有设备后需重新输入密钥；会话过期后的草稿可恢复。
- 完整备份包含正常笔记、回收站和分类配置；导入已有库时核对数量及 `verify` 结果。
- 检查 Vercel 日志和手机浏览器，不以构建成功代替实际访问验证。

Vercel 自身的 Deployment Protection 与应用密钥是两层保护。默认部署地址可能额外要求 Vercel 登录，取决于账户设置。自定义域名能否公开到达也受该设置影响；按自己的访问需求在控制台管理，不要为了排错自动关闭保护。

## 5. 自定义域名与 Cloudflare DNS

1. 在 Vercel 项目 Settings → Domains 添加自己的域名，例如 `notes.example.com`。
2. 读取该项目显示的**实际 CNAME 目标**，不要照抄别人项目的目标。
3. 在 Cloudflare 增加 CNAME：名称 `notes`，目标为上一步值，TTL 自动，先选**仅 DNS（灰云）**。如果该名称已有记录，先核对用途，不要盲目覆盖。
4. 无须为了一个子域名更换整个域名的 nameserver。若 Vercel 要求 TXT 所有权验证，按平台实际返回值添加。
5. 等待解析生效并确认 Vercel 配置有效、HTTPS 证书已签发，再访问自定义域名。将域名加入允许 Host/Origin 后重新部署。

连接在 TLS 握手阶段关闭时，先检查证书状态。DNS 正确不代表证书已经签发；在 Vercel 检查证书、CAA 与验证挑战，必要时按官方流程重新签发。不要关闭浏览器证书校验，不要用清理草稿或重建数据库解决网络问题。

保持 API `Cache-Control: no-store`，不要对笔记接口设置 Cloudflare Cache Everything。

## 6. 备份、更新与密钥轮换

- 普通 ZIP 导出不含回收站；菜单中的**完整备份**包括 `notes/`、`trash/`、`categories.json`。
- 将完整备份解压到新建空数据目录，可回到本地模式。不要覆盖已有库；浏览器草稿和设备会话不在备份里。
- 本地文件模式的另一种完整备份方法：停止服务后复制实际数据目录。如果配置了 `NOTEBOOK_DATA_DIR`，备份那个目录。
- 更新代码前下载备份，检查发布说明，安装锁定依赖并重新构建。云端数据库无需随函数重新部署而重建。不要在每次部署时自动重新导入旧 data。
- 修改密钥：运行密钥工具生成新哈希，替换 Production Secret 后重新部署，撤销设备会话并停用仍含旧配置的历史部署。旧部署不可变，新部署不会改写它们。
- 一次授权保存一年，按浏览器而非硬件设备识别；无痕模式、清除 Cookie、换浏览器都需要重新输入。退出不删除本机未加密草稿。

## 7. 开发与测试

```sh
python -m pytest tests -q
node --test tests/dates.test.mjs
npm run build
```

真实 PostgreSQL 回归需一个**可丢弃的本机数据库**，必须名为 `notebook_qa`。设置 `TEST_DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:5432/notebook_qa` 后运行测试；测试会清空该库的应用表。未设置时数据库测试明确跳过，不等于已验证数据库。GitHub Actions 使用独立 PostgreSQL 服务完成这一组测试。

开发前端运行 `npm run dev`，后端运行前设置 `NOTEBOOK_ALLOWED_ORIGINS=http://127.0.0.1:5173,http://localhost:5173`；使用独立数据目录，防止测试笔记混入正式库。

## 8. 已知边界

当前面向单人小型文字库。查询与批量导出仍可能一次读取全部匹配内容，数据量很大时应增加 SQL 分页与流式备份。全站登录限速为每 15 分钟 30 次，恶意请求可能暂时消耗本人的登录额度。前端草稿未加密；端到端加密、公开分享、离线云端写入及多库自动同步不在当前范围。
