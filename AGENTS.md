# ha-uhomecp 项目指南

> Home Assistant 集成：U管家（uhomecp.com）社区门禁系统

## 项目结构

```
/home/linooy/OxShrimp/ha-uhomecp/
├── custom_components/uhomecp/
│   ├── __init__.py        # 集成入口，DataUpdateCoordinator
│   ├── api.py             # API 客户端（核心）
│   ├── config_flow.py     # 三步配置流程
│   ├── const.py           # 常量（URL、密钥）
│   ├── manifest.json      # HA 元数据
│   ├── sensor.py          # 小区名称+门禁数量传感器
│   ├── switch.py          # 门禁开关实体
│   ├── strings.json       # HA 字符串
│   └── translations/      # 中英文翻译
├── docs/
│   └── TECHNICAL_DESIGN.md # 技术设计文档
├── hacs.json              # HACS 集成
├── README.md
└── LICENSE (MIT)
```

## 核心架构

### API 客户端（api.py）

- `UHomeCPClient` 类：管理 session、登录状态、小区、门禁
- RSA 加密：`password → base64 → RSA(PKCS1v15) → base64`
- 验证码流程：登录返回 `code:20010` → 获取验证码图片 → 用户输入 → 二次登录
- 所有方法都有 sync/async 两套（`asyncio.to_thread` 包装）

### 配置流程（config_flow.py）

```
Step 1: 手机号 + 密码
  → 尝试登录
  → code="0" → 跳到 Step 3
  → code="20010" → 跳到 Step 2

Step 2: 显示验证码图片 + 输入验证码
  → 带验证码登录
  → 成功 → 跳到 Step 3

Step 3: 选择小区（如果有多个活跃小区）
  → 只有一个则自动选择
  → 保存配置
```

**唯一ID格式**：`{手机号}_{小区ID}`（支持同一账号添加多个小区）

### 实体设计

| 平台 | 实体 | 说明 |
|------|------|------|
| switch | 门禁开关 | turn_on=开门，1秒后自动复位 |
| sensor | 小区名称 | 当前选中的小区名 |
| sensor | 门禁数量 | 可用门禁总数 |

## 开发注意事项

### 本地测试

```bash
# 复制到 HA 配置目录
cp -r custom_components/uhomecp /path/to/homeassistant/custom_components/

# 重启 HA 后添加集成
# 设置 → 设备与服务 → 添加集成 → U管家门禁
```

### 调试技巧

```bash
# 查看 HA 日志
tail -f /config/home-assistant.log | grep uhomecp

# 启用调试日志（在 configuration.yaml）
logger:
  logs:
    custom_components.uhomecp: debug
```

## 关键发现（踩坑记录）

### 1. 登录需要验证码 ⚠️

**现象**：加密格式正确（172字符 base64），但登录返回各种错误

**原因**：服务器可能要求验证码（`code:20010`），尤其是多次失败后

**解决**：实现两步登录流程，HA 配置时让用户手动输入验证码

### 2. 开门 API 用 JSON，不是 form-urlencoded ⚠️

**现象**：`POST /uhomecp-app/v1/userapp/opendoor/submit.json` 返回 `415 Unsupported Media Type`

**原因**：开门接口要求 `Content-Type: application/json`

**错误写法**：
```python
resp = session.post(url, data=dict_data, headers={"Content-Type": "application/x-www-form-urlencoded"})
```

**正确写法**：
```python
resp = session.post(url, json=dict_data)  # 自动设为 application/json
```

### 3. 微信小程序不可调试 ⚠️

**现象**：`chrome://inspect` 看不到小程序的 WebView

**原因**：小程序使用独立渲染引擎，不暴露 DevTools 接口

**解决**：必须用 H5 页面（`/h5/wechat-platform-h5/`）而不是小程序

### 4. 手机代理设置残留 ⚠️

**现象**：`ERR_PROXY_CONNECTION_FAILED`，无法访问网页

**原因**：之前设置的 mitmproxy 代理没清除

**解决**：
```bash
adb shell settings put global global_http_proxy_host ""
adb shell settings put global global_http_proxy_port 0
```

### 5. ADB 无线调试端口变化 ⚠️

**现象**：`adb connect` 失败

**原因**：每次重新开启无线调试，端口号会变

**解决**：先截图看手机上显示的端口号，再连接

### 6. 小米手机 ADB 配对 ⚠️

**现象**：配对成功但连接失败

**原因**：配对码端口和连接端口是两个不同的端口

**解决**：
1. 先用配对码端口配对：`adb pair IP:配对端口 配对码`
2. 再用连接端口连接：`adb connect IP:连接端口`

### 7. 账号锁定 ⚠️

**现象**：登录返回"密码输入错误次数过多，账号已锁定"

**原因**：连续失败触发安全机制

**解决**：等待解锁（可能30分钟到数小时），或换账号测试

### 8. Session 快速过期 ⚠️

**现象**：登录成功后几分钟就返回"未登录或已过期"

**原因**：JSESSIONID Cookie 有效期短

**解决**：每次 API 调用前检查状态，过期自动重新登录

### 9. PCAPdroid MITM 未生效 ⚠️

**现象**：抓包文件中 HTTPS 流量仍然是加密的

**原因**：PCAPdroid MITM 插件需要单独安装并启用 TLS 解密

**解决**：安装 PCAPdroid MITM Addon，在设置中启用 TLS 解密

### 10. WebView 页面白屏 ⚠️

**现象**：登录成功后页面白屏

**原因**：登录后跳转到门禁页面，但浏览器环境不支持（需要微信）

**解决**：这不影响 API 调用，登录成功即可用 Cookie 访问其他接口

## API 接口清单

### 认证相关

| 接口 | 方法 | 路径 | Content-Type |
|------|------|------|--------------|
| 登录 | POST | `/authc-restapi/v1/user/auth/login` | form-urlencoded |
| 获取验证码 | GET | `/authc-restapi/v1/auth/code/getImgCode` | - |
| 登出 | POST | `/authc-restapi/v1/user/auth/logout` | - |

### 数据查询

| 接口 | 方法 | 路径 | Content-Type |
|------|------|------|--------------|
| 小区列表 | GET | `/uhomecp-sso/v1/community/findMyCommunity` | - |
| 门列表 | GET | `/door-restapi/v1/userapp/doorList` | - |
| 用户信息 | GET | `/enterprise-app/user/selectByDetails` | - |

### 控制操作

| 接口 | 方法 | 路径 | Content-Type |
|------|------|------|--------------|
| 开门 | POST | `/uhomecp-app/v1/userapp/opendoor/submit.json` | **JSON** |

### 请求示例

**登录**：
```bash
curl -X POST 'https://www.uhomecp.com/authc-restapi/v1/user/auth/login' \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'tel=18680688513&password=<RSA加密>&loginType=1&clientId=wx&md5Flag=true'
```

**开门**：
```bash
curl -X POST 'https://www.uhomecp-app/v1/userapp/opendoor/submit.json' \
  -H 'Content-Type: application/json' \
  -d '{"custId":"200387316","userId":"200387316","doorId":"271128","communityId":"1013453","doorIdStr":"10.11.99.250|01|$t","appVersion":"2.3","appType":"2"}'
```

## 待办事项

- [ ] 实现会话过期自动重新登录
- [ ] 添加开门历史记录传感器
- [ ] 支持扫码开门（QR Code）
- [ ] 添加 HACS 自动化发布
- [ ] 编写单元测试

## 相关资源

- GitHub：https://github.com/linooy/ha-uhomecp
- V2EX 帖子：https://www.v2ex.com/t/1228153
- HA 开发文档：https://developers.home-assistant.io/
- 四格互联官网：https://www.uhomecp.com

## 账号信息（测试用）

- 账号1：18680688513 / 729830（已锁定，等待解锁）
- 账号2：18680688517 / 543978239zjr（备用）
- 小区：豪方天际花园（communityId: 1013453）
- 用户ID：200387316

---

_最后更新：2026-07-18_
