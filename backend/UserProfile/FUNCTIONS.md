# 用户账号与 Watchlist：文件和函数说明

登录成功后，前端读取该账号在数据库中的收藏。登录不会重新插入收藏，
因此添加时间和添加时价格保持不变。Profile、Watchlist 和物品详情页共用一份状态。

## 后端

### `watchlist.py`（新增）

| 函数 / 数据模型 | 用处 |
| --- | --- |
| `ItemKey` | 校验游戏和完整物品名；拒绝额外字段，例如客户端伪造的 `user_id`。 |
| `NewItem` | 在物品标识上增加添加时价格，只接受非负整数美分或空值。 |
| `install_watchlist(app, db_path, current_user)` | 把收藏接口挂到现有服务，并复用登录验证。 |
| `write_user(request, user)` | 检查前端显示的账号是否仍与登录会话一致，避免旧标签页改到另一个账号。请求头只做一致性检查，不授予权限。 |
| `get_watchlist(user)` | 查询当前用户的全部收藏，返回账号和列表；没有市场价格数据也能读取收藏。 |
| `add_watchlist_item(item, user)` | 将收藏写入该用户账号，由服务器生成添加时间；重复请求不会覆盖原记录。 |
| `remove_watchlist_item(item, user)` | 仅删除该用户的指定收藏；重复删除不会影响其他用户。 |

### `accounts.py`（复用并接入收藏路由）

| 函数 | 用处 |
| --- | --- |
| `connection(path)` | 打开数据库，开启外键检查，成功提交、异常回滚，最后关闭连接。 |
| `install_accounts(app, db_path)` | 检查现有用户表、执行 schema，安装账号及收藏接口。 |
| `csrf_guard(request, call_next)` | 写请求要求自定义请求头；API 响应禁止缓存。 |
| `digest(token)` | 将登录令牌转成哈希，数据库不直接保存原始令牌。 |
| `password_hash(password, salt)` | 用 scrypt 和随机盐计算密码哈希。 |
| `email_key(value)` | 统一邮箱大小写和首尾空格，检查邮箱格式。 |
| `current_user(request)` | 从 Cookie 查找未过期的登录会话，确定真实用户；未登录返回 401。 |
| `register(data)` | 校验账号资料，保存邮箱与密码哈希；拒绝重复邮箱。 |
| `login(data, request, response)` | 验证密码和失败次数限制，建立会话并设置 Cookie。 |
| `logout(request, response)` | 删除会话并清除 Cookie；不会删除收藏。 |
| `profile(user)` | 返回用户 ID、邮箱和创建时间，不返回密码或令牌。 |

`app.py` 的 `create_app(db_path)` 创建服务；`account_page()` 提供原来的独立账号测试页。
实际网站使用 React 的 Profile 页面。`schema.sql` 定义用户、收藏、会话和登录尝试表。

## 前端

### `frontend/src/lib/accountApi.ts`（新增）

| 函数 / 类 | 用处 |
| --- | --- |
| `AccountApiError` / `constructor(status, message)` | 保存请求错误的状态码和提示，区分登录过期、账号变化等情况。 |
| `accountRequest<T>(path, method, body, userId)` | 统一发送账号请求、Cookie 和写请求头，读取 JSON，并把请求失败交给页面处理。 |

### `frontend/src/components/AccountProvider.tsx`（新增）

| 函数 | 用处 |
| --- | --- |
| `same(item, name, game)` | 用游戏和完整名称判断是否为同一个物品。 |
| `AccountProvider({children})` | 为整个网站提供共享账号、收藏、加载和错误状态。 |
| `clearAccount()` | 清除页面内存里的账号和收藏，不删除数据库记录。 |
| `loadAccount()` | 从服务器读取当前账号及其收藏，更新共享状态。 |
| `run(action, sessionCheck)` | 串行执行操作，防止重复提交；统一处理加载、错误和登录过期。返回是否成功。 |
| `refresh()` | 首次打开页面、返回标签页或其他标签页有变化时重新读取账号；失败时不保留旧账号列表。 |
| `signIn(email, password, register)` | 可先注册，再登录，最后读取已有收藏；通知其他标签页刷新。 |
| `signOut()` | 请求退出登录，成功后清除页面状态；收藏留在数据库。 |
| `add(name, game, price)` | 请求添加收藏，服务器确认后更新各页面的列表。 |
| `remove(name, game)` | 请求删除收藏，成功后更新列表；失败不会假装删除成功。 |
| `has(name, game)` | 判断是否已收藏，控制物品页按钮及重复添加提示。 |
| `onFocus()`（effect 内） | 页面重新获得焦点或接到其他标签页通知时触发刷新；清理函数移除监听并关闭通知通道。 |

### 页面和共享组件

| 文件 / 函数 | 用处 |
| --- | --- |
| `lib/watchlist.ts` → `useWatchlist()` | 读取 Provider 的共享状态和操作，替换旧的浏览器本地存储逻辑。 |
| `components/AccountStatus.tsx` → `AccountStatus()` | 显示同步状态、错误信息和重新读取账号按钮。 |
| `pages/Profile.tsx` → `Profile()` | 未登录显示注册/登录表单，已登录显示账号、退出按钮和同一份 Watchlist。 |
| `Profile.tsx` → `onSubmit(event)` | 检查两次密码是否一致，调用注册/登录，成功后清空密码输入。 |
| `pages/Watchlist.tsx` → `Watchlist()` | 展示当前用户收藏及最新价格；未登录则提示登录。 |
| `Watchlist.tsx` → `onAdd(event)` | 提交选中的物品，只有保存成功才清空输入框。 |
| `Watchlist.tsx` → `keyOf(game, name)`（已有） | 生成查找市场报价的物品键。 |
| `Watchlist.tsx` → `loadQuotes(signal)`（已有） | 读取最新市场报价；报价与用户收藏记录分开保存。 |
| `pages/Item.tsx` → `Item()`（调整） | 使用同一收藏状态；未登录时提供登录入口，操作中禁用按钮。 |
| `components/Layout.tsx` → `Layout()`（调整） | 在页面公共区域显示账号同步与错误状态。 |

`main.tsx` 把网站放入 Provider；`vite.config.ts` 将本地账号请求转发到 8001 端口；
`index.css` 增加表单样式；`config.ts` 更新 Profile 的页面描述。

## 测试

以下测试脚本按要求保留在本地，不包含在本次 GitHub 上传中。

`tests/test_watchlist.py` 使用临时数据库，不修改真实账号：

| 函数 | 检查内容 |
| --- | --- |
| `setUp()` | 每次测试建立独立数据库和两个测试账号。 |
| `client()` | 创建连接同一测试数据库的服务客户端，也用于模拟服务重启。 |
| `test_restore_duplicate_and_account_isolation()` | 重复添加保留原数据、账号隔离、退出重登恢复、服务重启恢复、删除及重复删除。 |
| `test_validation_and_session_protection()` | 非法输入、伪造归属、旧标签页账号不一致、缺少写请求头、会话过期。 |

原有 `test_accounts.py` 继续检查注册登录、会话持久化及旧 schema 保护，
并将原来的“收藏接口不存在”断言更新为“新账号收藏为空”。

## 范围与运行方式

- 本次已连接本地前后端，尚未部署 AWS。
- 浏览器旧的 `vm-watchlist-v1` 数据不删除、不自动导入，避免误归到其他账号。
- 后端按 [README](README.md) 启动到 8001，前端运行 `npm run dev`，进入 `/#/profile`。
- 生产环境需把账号接口通过同站点 HTTPS 反向代理连接后端；只上传静态网页不能保存账号收藏。
