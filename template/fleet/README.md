# fleet — 设备清单与角色

> **Agent Packet**
> - zone: fleet
> - 维护 skill: `substrate-sync`（接入新机时更新）
> - canonical: 本文件顶部的可解析 YAML 块
> - 写前查: 这台机是否已登记
> - 写后更新: 增/改对应 device 条目
> - doctor 检查: 至多一台标 `migration_leader: true`；role 取值合法
>
> ⚠️ 引擎只给这个**通用槽位 + 机制**；**具体有哪几台机、各自角色，是你的实例数据**，填在下面。

```yaml
devices: []
# 示例（删掉，换成你自己的机器）：
#   - id: my-laptop
#     role: main-dev          # 建议词汇：main-dev / headless-dev / migration_leader / read-only
#     runtimes: [claude-code] # 这台机上跑的 agent runtime
#     migration_leader: true  # 是否专责执行跨引擎版本迁移（全 fleet 至多一台 true）
#     notes: 一句话
```

---

## 角色（建议词汇，可自定）

- `main-dev`：主力开发/读写机。
- `headless-dev`：无人值守/服务器机。
- `migration_leader`：专责执行跨引擎版本迁移的机器（全 fleet 至多一台；其它机 pull 到新版即跳过迁移）。
- `read-only`：只读消费，不写库。

## 接入一台新机

按 `../governance/bootstrap.md`：clone → 配身份 → `substrate-sync` 装 skill → 在上面 `devices:` 加本机一条 → commit/push。
