`star-lists` 用在这种时候：打开 GitHub 的 **Starred** 下拉菜单，发现收藏夹已经乱了，名字有三四种风格，有个拼写错误一直没改，好几个收藏夹只有一个仓库，一半的 star 不在任何收藏夹里。它读出你 star 过的每一个仓库，让 agent 按实际收藏的内容设计一套收藏夹，再把每个 star 放进对的那个；确实两边都沾的，就放进两个。

## 改之前你会先看到什么

你没看过改动、没点头之前，什么都不会写。agent 会先给你看这样一份差异：

```
Lists: 1 to create, 20 to update, 0 to delete. Repositories: 155 to move.
  update  Tools - Cluade Code: rename to 'AI · Claude Code'
  update  Study - CI/CD: rename to 'Study · Interview & Algorithms'
  create  AI · Design Skills
  move    obra/superpowers: Tools - Cluade Code -> AI · Claude Code
  move    vercel/geist-font: Fonts -> Design · Fonts & Icons
  ...
```

不想读文字的话，它可以生成一个审核页面：每个仓库一行，每个收藏夹一个开关，一个仓库可以同时放进几个收藏夹。在页面上保存修改后的方案，agent 就按你改过的那份写入。

## 怎么保证不出事

所有改动都经过同一份方案文件。下面几种情况 `check` 都会直接拒绝：还有 star 不在任何收藏夹里；方案里出现你没 star 的仓库；超出 GitHub 的上限（最多 32 个收藏夹，名称 32 个字符，描述 160 个字符）；收藏夹名里混进了非英文文字。`apply` 在第一次写入前先备份当前的收藏夹，写完再读回账号核对是否一致。备份本身就是一份方案，想撤销一次整理，把备份再应用一次就行。删除收藏夹不会取消任何 star。

一台什么都没装的机器也能跑。`run.sh doctor` 会列出缺了什么；`doctor --install` 从 GitHub 发布页下载 GitHub CLI 和 uv，逐个核对官方公布的 SHA-256，装进你的用户目录，不用 `sudo`。登录走 gh 的浏览器验证码流程，密码和 token 都不会经过对话。

## 它不做什么

它不 star 也不取消 star，不整理你自己名下的仓库，不碰 GitHub Projects，也不整理浏览器书签。它生成的所有内容，包括收藏夹名、描述和文件，一律是英文，不管你用什么语言提要求。GitHub 只通过 GraphQL API 提供收藏夹功能，而且至今仍标为预览，所以 GitHub 那边一改，它就可能失效；真遇到这种情况，报错里会写明是哪个调用失败了。
