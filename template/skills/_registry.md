# _registry — 第三方 skill 清单

> 每个第三方 skill 一条记录：顶部一个**可解析 YAML 块**（`substrate-sync` 解析它），后面人话。
> **代码不进库，这里只有指针**（URL + 钉的版本）。字段契约见 Substrate 引擎 `schemas/registry.schema.yaml`。

```yaml
registry: []
# 示例条目（删掉这个示例，换成你真正要装的）：
#   - name: example-skill
#     upstream_git_url: https://github.com/example/example-skill
#     pin: v1.2.0            # tag/commit/branch；裸追 main 需把 trusted_floating 设 true
#     trusted_floating: false
#     target_runtimes: [claude-code]
#     install_paths:        # 可选；缺省由对应 runtime 的 adapter 推断
#       claude-code: ~/.claude/skills/example-skill
#     notes: 一句话说明为什么装它
```

---

## 怎么加一条

1. 在上面 `registry:` 列表加一个条目（参照示例字段）。
2. `pin` 钉死版本（tag/commit）；确需追 `main` 才把 `trusted_floating` 设 `true`，并在 `notes` 说明风险。
3. 跑 `substrate-sync`：按 pin 从上游 clone，只装 `target_runtimes` 含本机 runtime 且符合本机角色的。
4. 同步 `README.md` 的 skill 清单。

> 自己写的 skill **不在这里**——它是 `skills/<name>/` 里的真文件。
