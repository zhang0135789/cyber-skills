# 公网访问（Cloudflare Tunnel + Access）

## 架构

```
[你的设备/指定的人] --https--> [Cloudflare 边缘]
   |                              |  (Access 邮箱白名单认证)
   |                              v
   |                          [Cloudflare Tunnel]
   |                              |
   v                              v
公网用户验明身份后  ------>  本机 cloudflared  ------>  DeepTutor:3782  ------>  Obsidian vault
   (浏览器)                  (宿主机常驻)            (Docker 容器)         (就地读写)
```

- **Cloudflare Tunnel**：本机 cloudflared 主动出站连 CF，无需公网 IP、无需开端口，自带 HTTPS。
- **Cloudflare Access**：在 CF 边缘做身份认证（邮箱一次性验证码），只有白名单内的人能进。DeepTutor 自身保持免 AUTH，本地/局域网仍方便。
- **DeepTutor**：仍跑在本地 Docker，读写 Obsidian vault 不变。

## 前置条件

1. Cloudflare 账号（免费即可）：https://dash.cloudflare.com/sign-up
2. 一个域名托管到 Cloudflare（在 CF 添加域名，把 NS 改到 CF）。没有域名可用 trycloudflare 临时域名（见末尾"无域名临时方案"），但临时域名**不能配 Access**，仅适合快速测试。
3. cloudflared 已安装：`winget install --id Cloudflare.cloudflared`
4. DeepTutor 容器在跑：`docker ps` 应见 deeptutor healthy。

## 部署步骤

运行引导脚本（一条命令搞定可自动化的部分）：

```powershell
powershell -ExecutionPolicy Bypass -File "C:\Users\Administrator\.workbuddy\skills\knowledge-vault\scripts\setup_cloudflare_tunnel.ps1"
```

脚本会依次引导：
1. 检查 DeepTutor 可达
2. `cloudflared tunnel login` —— **会开浏览器**，选择你的域名授权（生成 cert.pem）
3. 创建隧道（默认名 deeptutor）
4. 绑定公网域名（如 `kb.yourdomain.com`），自动写 DNS CNAME
5. 生成 `~/.cloudflared/config.yml`（ingress 规则指向 localhost:3782）
6. **手动**：去 Zero Trust Dashboard 配 Access 邮箱白名单（脚本会打印直达链接与步骤）
7. 启动隧道（前台测试 or 注册为开机自启服务，后者需管理员）

## 配置 Cloudflare Access（指定几人）

1. 打开 https://one.dash.cloudflare.com/
2. Access → Applications → Add an application → **Self-hosted**
3. Application domain 填你的公网域名（如 `kb.yourdomain.com`）
4. Identity providers 勾 **One-time PIN**（邮箱收验证码，无需第三方登录）
5. Policy：Include → Emails → 填指定几人的邮箱（如 `you@example.com`, `friend@example.com`）
6. 保存

效果：任何人访问 `https://kb.yourdomain.com` 都先被 Access 拦下要求邮箱，只有白名单邮箱收到验证码才能进 DeepTutor。

## 安全模型

| 访问路径 | 认证 | 说明 |
|---------|------|------|
| `http://127.0.0.1:3782` | 无 | 本机，仅自己 |
| `http://192.168.0.4:3782` | 无 | 局域网，家庭/办公内网 |
| `https://kb.yourdomain.com` | Cloudflare Access 邮箱白名单 | 公网，仅指定几人 |

- **不开 DeepTutor AUTH**：Access 已在网关层挡住公网，DeepTutor 保持免 AUTH 让本地/局域网/MCP 桥接零摩擦。
- 纵深防御：若需更强，可在 DeepTutor 也开 AUTH（`data/user/settings/auth.json` → `enabled: true`），但 MCP 桥需同步带 token。
- vault 文件本身不暴露：公网用户通过 DeepTutor 间接读，拿不到原始 .md 文件路径。

## 运维命令

```powershell
# 前台跑（测试）
cloudflared tunnel run deeptutor

# 注册/卸载服务（开机自启）
cloudflared service install
cloudflared service uninstall

# 查隧道状态
cloudflared tunnel list
cloudflared tunnel info deeptutor

# 改白名单/域名：直接去 Zero Trust Dashboard
```

## 故障排查

| 现象 | 排查 |
|------|------|
| 公网域名 1033 错误 | cloudflared 没跑，`cloudflared tunnel run deeptutor` 或 `service start` |
| 公网域名 502 | DeepTutor 容器挂了，`docker ps` / `docker start deeptutor` |
| Access 不拦、直接进 | Access 应用未配或域名不匹配，检查 Application domain |
| `tunnel login` 卡住 | 浏览器没开，手动复制终端里的 URL 到浏览器 |
| DNS 绑不上 | 域名 NS 未指向 Cloudflare，去域名注册商改 NS |

## 无域名临时方案（仅测试）

```powershell
cloudflared tunnel --url http://localhost:3782
```
会分配一个 `https://xxx-yyy.trycloudflare.com` 随机域名，**重启就变、不能配 Access、任何人可访问**。仅用于快速验证链路，正式使用务必走上面的正式隧道 + Access。

## 与 skill 的关系

公网域名配好后，建议设到环境变量供 skill 引用：
```
setx KB_PUBLIC_URL "https://kb.yourdomain.com"
```
skill 在入库反馈时会同时给出本地/局域网/公网三个访问入口。
