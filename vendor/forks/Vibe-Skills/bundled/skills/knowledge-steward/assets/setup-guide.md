# Knowledge Steward - GitHub 同步设置指南

本指南将帮助您设置 Knowledge Steward 技能的 GitHub 自动同步功能。

## 概述

Knowledge Steward 现在支持将您的知识笔记自动同步到 GitHub，实现：
- 自动备份所有笔记
- 多设备访问
- 版本历史追踪
- 安全的云端存储

## 前置要求

1. **Git for Windows**
   - 下载：https://git-scm.com/download/win
   - 安装时选择默认选项即可
   - 验证安装：打开命令行运行 `git --version`

2. **GitHub 账号**
   - 注册：https://github.com/signup
   - 免费账号即可

3. **Python 3.7+**
   - 通常已随 Claude Code 安装

## 设置步骤

### 步骤 1: 运行设置向导

打开命令行，进入技能目录：

```bash
cd C:\Users\羽裳\.claude\skills\knowledge-steward
python scripts\setup_github.py
```

设置向导将引导您完成：
1. 检查系统环境（Git 是否安装）
2. 输入 GitHub 用户名
3. 选择认证方式（推荐 HTTPS）
4. 创建两个 GitHub 仓库：
   - `knowledge-base` - 存储知识笔记
   - `claude-skill-knowledge-steward` - 存储技能代码

### 步骤 2: 创建 GitHub 仓库

如果没有安装 GitHub CLI，需要手动创建仓库：

1. 访问 https://github.com/new
2. 创建第一个仓库：
   - Repository name: `knowledge-base`
   - 设置为 **Private** (私有)
   - **不要**勾选 "Add a README file"
   - **不要**勾选 "Add .gitignore"
   - 点击 "Create repository"

3. 创建第二个仓库：
   - Repository name: `claude-skill-knowledge-steward`
   - 设置为 **Private** (私有)
   - 同样不要添加 README 和 .gitignore
   - 点击 "Create repository"

### 步骤 3: 初始化 Git 仓库

运行初始化脚本：

```bash
python scripts\init_git_repos.py
```

这个脚本会：
1. 在两个目录中初始化 Git
2. 创建 .gitignore 文件
3. 创建 README.md 文件
4. 进行初始提交
5. 推送到 GitHub

**首次推送时的认证：**
- 如果选择了 HTTPS，会弹出 Windows 凭据管理器窗口
- 输入您的 GitHub 用户名和密码（或 Personal Access Token）
- 凭据会被安全保存，以后不需要再次输入

### 步骤 4: 测试同步

保存一条测试笔记：

```bash
python scripts\save_to_obsidian.py --title "测试同步" --type "想法" --content "这是一条测试笔记，用于验证 GitHub 同步功能。"
```

如果一切正常，您会看到：
```
✓ 已保存到 Obsidian
文件：D:\Documents\ai技能外置大脑\Claude_Insights\想法\2026-02-14_测试同步.md
类型：想法
标签：#想法 #测试 #同步 #功能 #笔记
✓ 已同步到 GitHub
```

### 步骤 5: 验证 GitHub

访问您的 GitHub 仓库确认文件已上传：
- https://github.com/你的用户名/knowledge-base

您应该能看到：
- README.md
- .gitignore
- 想法/2026-02-14_测试同步.md

## 认证方式

### 方式 1: HTTPS + Git Credential Manager (推荐)

**优点：**
- 设置简单
- Windows 原生支持
- 凭据安全存储

**设置：**
1. 首次 push 时会弹出认证窗口
2. 输入 GitHub 用户名和密码
3. 凭据自动保存到 Windows 凭据管理器

**Personal Access Token (如果需要)：**
如果 GitHub 要求使用 Token 而不是密码：
1. 访问 https://github.com/settings/tokens
2. 点击 "Generate new token (classic)"
3. 勾选 `repo` 权限
4. 生成并复制 token
5. 在认证窗口中使用 token 代替密码

### 方式 2: SSH 密钥

**优点：**
- 无需每次输入密码
- 更安全

**设置：**
1. 生成 SSH 密钥：
   ```bash
   ssh-keygen -t ed25519 -C "your_email@example.com"
   ```
2. 添加到 SSH agent：
   ```bash
   ssh-add ~/.ssh/id_ed25519
   ```
3. 复制公钥：
   ```bash
   cat ~/.ssh/id_ed25519.pub
   ```
4. 添加到 GitHub：
   - 访问 https://github.com/settings/keys
   - 点击 "New SSH key"
   - 粘贴公钥
5. 测试连接：
   ```bash
   ssh -T git@github.com
   ```

## 配置文件

配置文件位于：`C:\Users\羽裳\.claude\skills\knowledge-steward\config.yaml`

### 关键配置项

```yaml
# 启用/禁用 Git 同步
git:
  enabled: true
  auto_sync: true

# 仓库配置
repositories:
  knowledge_base:
    url: "https://github.com/username/knowledge-base.git"
    enabled: true
    auto_pull: true  # 推送前自动拉取（多设备同步）

# 同步行为
sync:
  auto_pull_before_push: true  # 避免冲突
  retry_on_failure: true
  max_retries: 3
```

### 临时禁用同步

如果需要临时禁用同步，有两种方式：

1. **使用 --no-sync 标志：**
   ```bash
   python scripts\save_to_obsidian.py --title "..." --type "..." --content "..." --no-sync
   ```

2. **修改配置文件：**
   ```yaml
   git:
     enabled: false  # 或 auto_sync: false
   ```

## 多设备使用

如果您在多台设备上使用 Knowledge Steward：

### 在新设备上设置

1. 克隆知识库：
   ```bash
   git clone https://github.com/username/knowledge-base.git "D:\Documents\ai技能外置大脑\Claude_Insights"
   ```

2. 克隆技能代码：
   ```bash
   git clone https://github.com/username/claude-skill-knowledge-steward.git "C:\Users\羽裳\.claude\skills\knowledge-steward"
   ```

3. 复制并修改配置文件：
   ```bash
   cd C:\Users\羽裳\.claude\skills\knowledge-steward
   copy config.example.yaml config.yaml
   # 编辑 config.yaml 填入您的信息
   ```

### 自动同步

配置中的 `auto_pull: true` 确保：
- 每次保存前自动拉取远程更改
- 避免冲突
- 保持多设备同步

## 常见问题

### Q: 推送失败，提示认证错误

**A:** 检查认证设置：
1. HTTPS: 重新输入凭据
   ```bash
   git credential-manager erase https://github.com
   ```
2. SSH: 测试 SSH 连接
   ```bash
   ssh -T git@github.com
   ```

### Q: 推送失败，提示 "rejected"

**A:** 远程有新的更改，需要先拉取：
```bash
cd "D:\Documents\ai技能外置大脑\Claude_Insights"
git pull --rebase origin main
git push origin main
```

### Q: 如何查看同步日志？

**A:** 日志文件位于：
```
C:\Users\羽裳\.claude\skills\knowledge-steward\logs\git_sync.log
```

### Q: 如何手动同步技能代码？

**A:** 运行：
```bash
python scripts\sync_skill_code.py
```

### Q: 同步很慢怎么办？

**A:**
1. 检查网络连接
2. 考虑使用 SSH 而不是 HTTPS
3. 如果仓库很大，考虑使用 Git LFS

### Q: 如何恢复到之前的版本？

**A:** 使用 Git 命令：
```bash
cd "D:\Documents\ai技能外置大脑\Claude_Insights"
git log  # 查看历史
git checkout <commit-hash> -- <file-path>  # 恢复特定文件
```

## 安全建议

1. **使用私有仓库**
   - 知识笔记可能包含敏感信息
   - 确保两个仓库都设置为 Private

2. **不要提交敏感信息**
   - .gitignore 已配置排除 config.yaml
   - 不要在笔记中包含密码、API 密钥等

3. **定期备份**
   - GitHub 是备份，但不是唯一备份
   - 考虑定期导出重要笔记

4. **审查提交内容**
   - 偶尔检查 GitHub 上的提交
   - 确保没有意外提交敏感文件

## 高级功能

### 自定义提交信息模板

编辑 config.yaml：
```yaml
git:
  commit_message_template: "Add: {type} - {title} [{date}]"
```

### 冲突解决策略

```yaml
sync:
  conflict_resolution: "prefer-remote"  # 或 "prefer-local"
```

### 日志级别

```yaml
logging:
  level: "DEBUG"  # INFO, WARNING, ERROR
```

## 故障排除

### 完全重置

如果遇到无法解决的问题，可以完全重置：

1. 备份重要笔记
2. 删除本地 .git 目录：
   ```bash
   rmdir /s "D:\Documents\ai技能外置大脑\Claude_Insights\.git"
   rmdir /s "C:\Users\羽裳\.claude\skills\knowledge-steward\.git"
   ```
3. 重新运行 `init_git_repos.py`

### 获取帮助

如果遇到问题：
1. 查看日志文件：`logs/git_sync.log`
2. 运行诊断：
   ```bash
   python scripts\git_sync.py --check-git
   python scripts\git_sync.py --test-config
   ```
3. 在 GitHub 上提交 Issue

## 总结

设置完成后，Knowledge Steward 将：
- ✓ 自动保存每条笔记到本地 Obsidian
- ✓ 自动提交到 Git
- ✓ 自动推送到 GitHub
- ✓ 支持多设备同步
- ✓ 保留完整的版本历史

享受无缝的知识管理体验！
