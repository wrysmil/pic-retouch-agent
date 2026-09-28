# S6 实现文档：测试清理只删测试账号

> 项目：pic-retouch-agent
> 里程碑：S6
> 日期：2026-09-24

## 1. 仓库状态变化

| 提交 | 内容 |
|---|---|
| S1–S5（已存在） | 脚手架 / 基础设施 / 账号体系 / 素材上传 / 品牌化 / 文生图链路 |
| **S6（本里程碑）** | 测试账号前缀约定 + 按前缀精准清理 |

纯测试基座改动，零业务代码、零迁移、零前端。

## 2. 变更详情

### 2.1 `backend/tests/conftest.py`

```python
TEST_USER_PREFIX = "test_"   # 测试账号统一此前缀

@pytest.fixture
def credentials() -> dict[str, str]:
    return {"username": f"{TEST_USER_PREFIX}{uuid.uuid4().hex[:10]}", "password": "secret123"}

@pytest.fixture(autouse=True)
async def cleanup_users():
    yield
    async with SessionFactory() as session:
        await session.execute(delete(User).where(User.username.startswith(TEST_USER_PREFIX)))
        await session.commit()
```

### 2.2 `backend/tests/test_assets.py`

`"otheruser"` → `"test_otheruser"`（隔离用例里跨用户读他人素材）。

## 3. 关键决策与理由

| 决策 | 理由 |
|---|---|
| 前缀常量定义在 `conftest.py` | 全测试共享夹具的天然归属；一处修改全局生效 |
| 用 `startswith` 而非 `IN (...)` | 不需要维护账号白名单，未来新增测试自动受益 |
| S5 的 `test_intruder` 天然符合前缀 | 无需改动，正好验证约定已开始覆盖 |

## 4. 验证

```bash
cd backend && ./.venv/Scripts/python.exe -m pytest -q   # 全部绿
```

## 5. 后续清理

无遗留。S7/S8 直接基于本基座。