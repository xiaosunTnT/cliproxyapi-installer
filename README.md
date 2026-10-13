# CLIProxyAPI Linux 安装脚本

用于在 Linux 上安装、升级和管理 [CLIProxyAPI](https://github.com/router-for-me/CLIProxyAPI)。支持 AMD64 和 ARM64，保留已有配置，并通过系统级 systemd 服务持续运行。

## 功能

- **自动安装**：识别 Linux 架构，下载上游最新发布版本。
- **ARM64 兼容**：支持当前的 `linux_aarch64` 和旧版本的 `linux_arm64` 安装包。
- **系统级服务**：安装到 `/etc/systemd/system/cliproxyapi.service`，退出 SSH 后仍由系统管理服务。
- **旧服务迁移**：将原来的用户级服务迁移为系统级服务，无需重新下载程序。
- **配置保留**：升级前备份配置，优先保留用户修改过的 `config.yaml`。
- **服务管理**：升级时先下载并解压，再停止运行中的服务；更新后恢复运行。
- **API 密钥管理**：首次配置时生成 API 密钥，也可单独生成新密钥。
- **版本清理**：保留最近两个版本目录。
- **错误提示**：显示网络、发布信息和安装包匹配错误，下载请求具有超时和重试机制。

## 环境要求

- Linux，支持 `amd64` / `x86_64` 和 `arm64` / `aarch64`；不支持 32 位 ARM。
- Bash。
- `curl` 或 `wget`，以及 `tar`。
- 已启动的 systemd 系统管理器。
- root 权限，或具有 `sudo` 权限的安装用户，用于安装和管理系统级服务。

安装依赖：

```bash
# Ubuntu / Debian
sudo apt-get install curl wget tar

# CentOS / RHEL
sudo yum install curl wget tar

# Fedora
sudo dnf install curl wget tar
```

## 快速开始

### 安装

以拥有 `~/cliproxyapi/` 的用户身份运行安装脚本。脚本只在安装和管理系统服务时通过 `sudo` 提权，程序、配置和认证数据仍保存在该用户的主目录中。

```bash
# 下载并运行
curl -fsSL https://raw.githubusercontent.com/xiaosunTnT/cliproxyapi-installer/refs/heads/master/cliproxyapi-installer | bash

# 或克隆仓库后运行
git clone https://github.com/xiaosunTnT/cliproxyapi-installer.git
cd cliproxyapi-installer
./cliproxyapi-installer
```

### 配置与认证

查看或修改配置：

```bash
cd ~/cliproxyapi
nano config.yaml
```

按需要选择提供方进行认证：

```bash
./cli-proxy-api --login           # Gemini / Google
./cli-proxy-api --codex-login     # OpenAI / Codex
./cli-proxy-api --claude-login    # Claude / Anthropic
./cli-proxy-api --qwen-login      # Qwen
./cli-proxy-api --iflow-login     # iFlow
```

在没有浏览器的服务器上，可添加 `--no-browser`，让程序输出登录地址：

```bash
./cli-proxy-api --codex-login --no-browser
```

配置中的 `api-keys` 用于验证客户端对代理服务的请求；提供方认证使用上述登录命令完成。

### 启动并设置开机自启

```bash
sudo systemctl enable --now cliproxyapi.service
sudo systemctl status cliproxyapi.service
```

首次安装只创建服务文件，完成配置和认证后再执行上述命令启动服务。直接执行 `./cli-proxy-api` 可用于前台调试，长期运行使用系统级服务。

## 命令说明

```bash
./cliproxyapi-installer [命令]
```

| 命令 | 说明 |
| --- | --- |
| `install` / `upgrade` | 安装或升级 CLIProxyAPI，默认行为 |
| `status` | 查看版本、配置和系统服务状态 |
| `setup-service` | 安装、修复或迁移系统级服务，不下载新版本 |
| `auth` | 显示提供方认证说明 |
| `check-config` | 检查配置和 API 密钥 |
| `generate-key` | 生成一个新 API 密钥，不自动修改配置 |
| `manage-docs` | 检查文档及其一致性 |
| `uninstall` | 确认后移除服务及安装目录 |
| `-h` / `--help` | 显示帮助 |

常用操作：

```bash
# 安装或升级到最新版本
./cliproxyapi-installer

# 迁移旧用户服务，或修复系统服务
./cliproxyapi-installer setup-service

# 查看状态、检查配置
./cliproxyapi-installer status
./cliproxyapi-installer check-config

# 生成新密钥、查看认证说明
./cliproxyapi-installer generate-key
./cliproxyapi-installer auth

# 卸载
./cliproxyapi-installer uninstall
```

## 安装目录与配置

```text
~/cliproxyapi/
├── cli-proxy-api          # 主程序
├── config.yaml           # 用户配置
├── cliproxyapi.service   # 系统服务文件的本地副本
├── version.txt           # 当前版本
├── x.x.x/                # 对应版本的解压目录
└── config_backup/        # 升级前的配置备份
```

系统管理器实际加载的服务文件位于：

```text
/etc/systemd/system/cliproxyapi.service
```

首次安装时，脚本从 `config.example.yaml` 创建配置，并替换示例 API 密钥。升级时按以下顺序选择配置：

1. 本次升级创建的备份。
2. 主安装目录中已有的 `config.yaml`。
3. 旧版本目录中已有的 `config.yaml`。
4. 新版本提供的示例配置。

已有配置优先于示例配置。`generate-key` 只输出新密钥，需要自行添加到 `config.yaml`。

## 系统级 systemd 服务

服务使用系统管理器，管理命令为 `sudo systemctl`，不带 `--user`。服务文件使用 `WantedBy=multi-user.target`，启用后可在系统启动时运行，无需等待用户登录。

服务中的 `User=` 和 `Group=` 指向安装用户，`HOME` 和 `WorkingDirectory` 也保持该用户的路径。因此，服务仍以原安装用户身份运行，继续使用原来的配置和认证数据，但生命周期由系统管理器管理。每台主机安装一个 `cliproxyapi.service`。

### 为什么旧服务可能在退出 SSH 后停止

旧脚本将服务安装在 `~/.config/systemd/user/`，并通过 `systemctl --user` 管理。它属于用户的 systemd 管理器；未启用 lingering 时，最后一个登录会话结束后，用户管理器可能停止，从而停止服务。

会话进程是否被清理还取决于主机的 logind 配置，不能理解为退出 SSH 必然终止该用户的所有进程。相关行为可查看 [systemd 的 loginctl 文档](https://github.com/systemd/systemd/blob/main/man/loginctl.xml)。

新版脚本安装系统级服务，不依赖 SSH 会话，也无需通过 `loginctl enable-linger` 维持用户管理器。

### 迁移已有安装

使用新版脚本，并以**最初安装 CLIProxyAPI 的同一个用户**执行，确保脚本能找到原来的主目录、配置和用户服务：

```bash
# 仅迁移服务，不检查或下载 CLIProxyAPI 新版本
./cliproxyapi-installer setup-service

# 设置开机自启并立即启动
sudo systemctl enable --now cliproxyapi.service

# 检查服务文件路径、运行用户和进程
sudo systemctl status cliproxyapi.service
sudo systemctl show cliproxyapi.service -p FragmentPath -p User -p MainPID
```

迁移会停止并禁用旧用户服务、删除旧服务文件、重新加载用户管理器，然后按原来的启用和运行状态处理系统服务，避免两个实例同时占用端口。若无法连接旧用户管理器，脚本会报错并停止迁移；请在原安装用户的登录会话中重新执行。

`install` 和 `upgrade` 也会执行迁移，即使程序版本已经是最新版本。配置和认证数据继续保留。

对于已有的普通用户安装，请直接以该用户运行脚本，让脚本按需请求 `sudo` 权限。将整个安装脚本用 `sudo` 运行会使用 root 的主目录和安装身份，无法按原普通用户的路径找到已有数据。

### 日常管理

```bash
# 设置开机自启并立即启动
sudo systemctl enable --now cliproxyapi.service

# 查看服务状态和实时日志
sudo systemctl status cliproxyapi.service
sudo journalctl -u cliproxyapi.service -f

# 停止、重启
sudo systemctl stop cliproxyapi.service
sudo systemctl restart cliproxyapi.service

# 分别检查开机自启状态与当前运行状态
sudo systemctl is-enabled cliproxyapi.service
sudo systemctl is-active cliproxyapi.service

# 禁用开机自启并立即停止
sudo systemctl disable --now cliproxyapi.service
```

卸载时，脚本会先停止并禁用服务，移除系统服务文件并重新加载 systemd，再删除安装目录。

### 验证退出 SSH 后持续运行

```bash
sudo systemctl enable --now cliproxyapi.service
exit

# 重新连接 SSH 后执行，正常应输出 active
sudo systemctl is-active cliproxyapi.service
sudo journalctl -u cliproxyapi.service -n 50
```

## 升级行为

```bash
./cliproxyapi-installer upgrade
```

升级时，脚本先备份已有配置，下载并解压新版本，再停止服务和相关进程、替换主程序、更新系统服务文件，最后恢复原来运行中的服务。更新主程序期间会有短暂中断。

| 原有状态 | 升级后的行为 | 配置处理 |
| --- | --- | --- |
| 服务正在运行 | 更新后自动重新启动 | 备份并保留 |
| 服务已停止 | 更新后保持停止 | 备份并保留 |
| 使用旧用户服务 | 迁移为系统服务，保留启用和运行状态 | 保留 |
| 程序已经是最新版本 | 仍安装、修复或迁移服务 | 保留 |
| 首次安装 | 创建服务文件，配置完成后手动启动 | 从示例生成 |

## 常见问题

### 检测到 ARM64 后直接退出

如果旧脚本只显示 `Detected platform: linux_arm64` 后就结束，请使用新版脚本。上游 ARM64 安装包现在使用 `linux_aarch64` 命名，新版会优先匹配该名称，并兼容旧的 `linux_arm64`。

安装包使用完整文件名匹配，避免误选 `no-plugin` 构建。找不到兼容包时，会显示架构、版本和可用安装包列表。

### 网络请求或下载失败

新版将进度和错误写入标准错误流（stderr），不会因命令替换而隐藏错误。检查网络、代理设置和 GitHub API 请求限额。HTTP 错误会导致下载失败，而不会被当作有效安装包继续解压。

### 脚本无法执行

```bash
chmod +x cliproxyapi-installer
```

### 缺少依赖或权限

按照“环境要求”安装 `curl` 或 `wget`、`tar`，并确认主机使用 systemd 启动。安装或管理系统服务需要 root 或 `sudo` 权限。

### 服务无法启动

```bash
sudo systemctl status cliproxyapi.service
sudo journalctl -u cliproxyapi.service -n 50
sudo systemctl cat cliproxyapi.service
./cliproxyapi-installer check-config
```

如需修复服务文件：

```bash
./cliproxyapi-installer setup-service
sudo systemctl enable --now cliproxyapi.service
```

### 端口被占用

默认端口为 `8317`。先确认占用端口的进程：

```bash
sudo ss -ltnp | grep ':8317'
```

若占用来自旧用户服务，运行 `setup-service` 完成迁移；其他进程则按实际用途处理，然后重启服务：

```bash
sudo systemctl restart cliproxyapi.service
```

### 升级后服务未恢复

```bash
sudo systemctl status cliproxyapi.service
sudo journalctl -u cliproxyapi.service -n 50
sudo systemctl restart cliproxyapi.service
```

### 从备份恢复配置

```bash
ls -la ~/cliproxyapi/config_backup/

# 将下面的文件名替换为实际需要恢复的备份
cp ~/cliproxyapi/config_backup/config_YYYYMMDD_HHMMSS.yaml ~/cliproxyapi/config.yaml
sudo systemctl restart cliproxyapi.service
```

## 回归测试

开发时使用 Python 3 运行离线回归测试；日常安装无需 Python：

```bash
bash -n cliproxyapi-installer
python3 -m unittest discover -s tests -v
```

测试覆盖新旧 ARM64 安装包名称、AMD64 兼容、错误提示、下载失败、配置保留、临时文件清理、系统服务生成、旧用户服务迁移、升级与卸载流程。

网络和 systemd 操作使用模拟实现，测试不会在本机安装或启动服务。真实 Linux 主机上的 SSH 退出和开机自启行为，需要按文档中的命令验证。

## 权限与数据

- 程序、配置和认证数据保留在安装用户的主目录中。
- 系统级服务以安装用户身份运行；服务文件安装和服务管理通过 root 或 `sudo` 完成。
- 升级前自动备份配置，已有用户配置优先于示例配置。
- 退出时只清理本次安装产生的下载临时文件。

## 参与贡献

1. Fork 仓库并创建开发分支。
2. 修改代码或文档。
3. 运行语法检查和回归测试。
4. 提交 Pull Request，说明改动和验证结果。

## 许可证

本安装脚本沿用 CLIProxyAPI 项目的许可证，具体条款请参阅上游项目。

## 文档与支持

- [CLIProxyAPI 上游项目](https://github.com/router-for-me/CLIProxyAPI)
- [安装脚本仓库](https://github.com/xiaosunTnT/cliproxyapi-installer)
- [问题反馈](https://github.com/xiaosunTnT/cliproxyapi-installer/issues)
- 命令行帮助：`./cliproxyapi-installer --help`

## 最近更新

- 兼容上游 `linux_aarch64` 与旧版 `linux_arm64` 安装包。
- 修复架构检测后因日志被捕获而静默退出的问题。
- 下载增加 HTTP 错误检查、超时和重试。
- 将服务改为系统级 systemd 服务，支持退出 SSH 后持续运行和开机自启。
- 新增 `setup-service` 命令，迁移已有用户服务而无需下载新版本。
- 升级时先准备安装包，再停止服务；保留已有配置和服务运行状态。
- 卸载时同时停用并清理服务文件。
- 临时文件清理限定为本次安装的下载文件。

本脚本仅面向 Linux；其他操作系统请参阅 CLIProxyAPI 上游项目。
