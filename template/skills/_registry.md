# _registry — 第三方 skill 清单

> 每个第三方 skill 一条记录：顶部一个**可解析 YAML 块**（`substrate-sync` 解析它），后面人话。
> **代码不进库，这里只有指针**（URL + 钉的版本）。字段契约见 Substrate 引擎 `schemas/registry.schema.yaml`。

```yaml
registry: []
# 两种来源形态（kind）——删掉示例，换成你真正要装的：
#
# ① kind: git（默认）—— 可 git-clone 的裸仓库，substrate-sync 按 pin 从上游 clone：
#   - name: example-skill
#     kind: git
#     upstream_git_url: https://github.com/example/example-skill
#     pin: v1.2.0            # tag/commit/branch；裸追 main 需把 trusted_floating 设 true
#     trusted_floating: false
#     target_runtimes: [claude-code]
#     install_paths:        # 可选；缺省由对应 runtime 的 adapter 推断
#       claude-code: ~/.claude/skills/example-skill
#     notes: 一句话说明为什么装它
#
# ② kind: plugin —— 由宿主插件机制分发（如 Claude Code plugin marketplace），
#    没有可 clone 的裸 git 仓库。只登记，sync 不 clone/不更新，更新交回插件机制。
#   - name: superpowers
#     kind: plugin
#     source: claude-plugins-official/superpowers   # marketplace/插件名
#     target_runtimes: [claude-code]
#     notes: 用 Claude Code 插件机制安装/更新；此处只做清单登记，不由 sync 装
```

---

## 怎么加一条

1. 在上面 `registry:` 列表加一个条目，先定 `kind`：
   - **git**：能 `git clone` 的（多数 GitHub skill）。填 `upstream_git_url` + `pin`（钉死版本；确需追 `main` 才把 `trusted_floating` 设 `true`）。
   - **plugin**：插件机制分发的（如 superpowers 这类 Claude Code 插件）。填 `source`（marketplace/插件名），**不填 url/pin**。
2. 跑 `substrate-sync`：对 `kind: git` 按 pin 从上游 clone 装；对 `kind: plugin` **只列出、不安装**（提示你用插件机制管）。两者都只处理 `target_runtimes` 含本机 runtime 的。
3. 同步 `README.md` 的 skill 清单。

> 自己写的 skill **不在这里**——它是 `skills/<name>/` 里的真文件。
> 不知道某 skill 的 git 地址、它又是插件装的 → 用 `kind: plugin` 登记，别硬塞 git 形态。
