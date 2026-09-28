# S6 需求文档：测试清理只删测试账号

> 项目：pic-retouch-agent（AI 修图智能体）
> 里程碑：S6 — 测试隔离清理加固
> 日期：2026-09-24
> 前置里程碑：S5（已完成）
> 后续里程碑：S7+（启动端口配置化、品牌 favicon）

## 1. 背景与目标

S1–S5 的测试在 `conftest.py` 里用一个 `autouse` fixture 在每个测试后执行 `delete(User)` —— **清空整张 users 表**。这在只跑测试、库里只有测试账号时没问题，可一旦开发者在本机同时用自己的账号登录了开发环境，跑一次测试就会把真实用户连带删掉。

S6 的改动很小但意义明确：

1. **约定前缀**：所有测试创建的账号统一以 `test_` 开头。
2. **精准清理**：清理逻辑只删除用户名带 `test_` 前缀的行，不再碰真实账号。
3. **修正遗留**：`test_assets.py` 里硬编码的 `otheruser` 改为 `test_otheruser`，落入前缀约定。

## 2. 用户与场景

| 角色 | 场景 |
|---|---|
| 后端开发者 | 本机开发库里既有自己手工注册的账号，也有测试账号；跑 `pytest` 后真实账号完好 |
| CI | 全量测试后无需担心残留测试数据影响下一次运行（前缀账号会被自动清掉） |

## 3. 功能需求

### 3.1 测试账号前缀约定 F1

- **F1.1** `conftest.py` 定义常量 `TEST_USER_PREFIX = "test_"`。
- **F1.2** `credentials` fixture 生成 `f"{TEST_USER_PREFIX}{uuid.uuid4().hex[:10]}"` 形式的随机用户名。

### 3.2 按前缀清理 F2

- **F2.1** `cleanup_users` 由 `delete(User)` 改为 `delete(User).where(User.username.startswith(TEST_USER_PREFIX))`。
- **F2.2** 其余测试文件里所有硬编码测试用户名统一加 `test_` 前缀（`otheruser` → `test_otheruser`）。

## 4. 非功能需求

| 编号 | 类别 | 描述 |
|---|---|---|
| NFR1 | 安全 | 开发/生产库中的真实用户不会因跑测试被误删 |
| NFR2 | 可维护 | 前缀集中在 `conftest.py` 一处定义，其它测试引用即可 |

## 5. 验收标准

| 编号 | 描述 |
|---|---|
| AC1 | `pytest` 全绿（含 S5 新增的文生图用例） |
| AC2 | 手工在开发库注册 `alice`（非 `test_` 前缀）后跑测试，`alice` 仍存在 |
| AC3 | 测试产生的 `test_*` 账号在测试结束后被清空 |

## 6. 范围与非范围

**本里程碑范围**：

- `backend/tests/conftest.py`：前缀常量 + 条件清理
- `backend/tests/test_assets.py`：`otheruser` → `test_otheruser`

**本里程碑非范围**：

- 其它测试文件（S5 的 `test_generation.py` 已用 `test_intruder`，天然符合）
- 任何业务代码 / 迁移改动

## 7. 后续依赖

- S7 / S8 继续沿用本测试基座。