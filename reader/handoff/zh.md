`handoff` 让同一台电脑上的 Claude Code 和 Codex 互相看到可读的会话历史。后台服务发现两端的本地记录，注册 Codex 原生任务，并在每个已有的 Claude 本地账户中建立会话索引。

## 使用方式

在已安装的技能目录中运行：

```bash
python3 scripts/handoff.py sync
python3 scripts/handoff.py sync --apply
python3 scripts/handoff.py install
python3 scripts/handoff.py status
python3 scripts/handoff.py uninstall
```

`sync` 默认只预览；加上 `--apply` 才执行一次同步。`install` 备份并更新本技能在 `~/.claude/settings.json` 和 `~/.codex/hooks.json` 中的 hook，保留其他 hook，同时安装稳定运行目录。macOS 上还会安装独立后台服务。更新插件后需要重新安装，以刷新稳定运行目录；客户端仍自行管理 hook 的信任。其他平台会明确报告后台服务未安装，可在支持的环境中手动运行 `watch` 或单次同步。

## 如何保留接续内容

Codex 侧必须通过原生接口导入并回读确认，只有 rollout 文件不代表任务已注册。Claude 侧也需要桌面索引；程序按 `cliSessionId` 匹配记录并保留已有的桌面 `sessionId`，不会假设这两个 ID 相同。

未被独立接续的副本可以更新。如果你已在任一端继续聊天，程序保留该会话，把后续变化作为独立分支同步，保留原始记录。旧工作目录已删除时，程序使用指向现有父目录的托管快照，不修改原记录中的目录。

## 如何确认成功

hook 只请求后台扫描。它静默退出且返回零，不代表同步已经完成。检查后台最近一次完成报告和逐项错误，再在目标应用中打开一个新同步的会话。所有已有账户的索引都存在，与应用侧栏实际显示正常，是两种需要分别验证的结果。

大历史库扫描可能耗时，后台服务刚重启时尤其如此。同步最终会跟进，轮询间隔不等于端到端延迟保证。尚未写完整的最后一行会留到后续处理。

## 能力边界

同步的是可读上下文，不是逐字节重放原平台会话。加密推理、签名 thinking、附件和平台专有状态不保证完整转换。导入后可以作为独立任务继续。子代理与仅在云端存在的历史不在同步范围内，也不支持跨电脑搬迁。
