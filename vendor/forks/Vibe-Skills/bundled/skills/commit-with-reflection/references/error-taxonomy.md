# 错误分类体系 (Error Taxonomy)

本文档定义了反思报告中使用的错误分类标准、严重程度评级和常见错误模式库。

## 错误类型分类

### 1. 语法错误 (Syntax Errors)

**定义**: 代码不符合编程语言的语法规则,导致无法编译或解析。

**特征**:
- 编译器/解释器直接报错
- 代码无法运行
- 错误位置明确

**常见示例**:
```javascript
// 缺少括号
if (condition {
  doSomething();
}

// 缺少分号(在严格模式下)
const x = 5
const y = 10

// 拼写错误
functoin myFunc() {}
```

**根本原因**:
- 打字错误
- 对语法规则不熟悉
- IDE/编辑器未配置语法检查

**预防策略**:
- 使用支持语法高亮的编辑器
- 启用实时语法检查(ESLint, TSLint)
- 配置自动格式化工具(Prettier)

---

### 2. 类型错误 (Type Errors)

**定义**: 在静态类型语言中,类型不匹配或类型定义不完整导致的错误。

**特征**:
- TypeScript/Flow等类型检查器报错
- 运行时可能出现undefined/null错误
- 接口定义与实际使用不一致

**常见示例**:
```typescript
// 类型不匹配
const age: number = "25"; // Error

// 属性不存在
interface User {
  name: string;
}
const user: User = { name: "Alice" };
console.log(user.age); // Error: Property 'age' does not exist

// 函数参数类型错误
function add(a: number, b: number): number {
  return a + b;
}
add("1", "2"); // Error
```

**根本原因**:
- 接口定义不完整
- 类型断言使用不当
- 数据库schema与类型定义不同步
- 第三方库类型定义缺失

**预防策略**:
- 使用严格的TypeScript配置(`strict: true`)
- 从schema自动生成类型定义
- 定期同步类型定义与数据源
- 避免使用`any`类型
- 为第三方库添加类型声明

---

### 3. 逻辑错误 (Logic Errors)

**定义**: 代码可以运行,但产生的结果不符合预期,通常是算法或业务逻辑错误。

**特征**:
- 无编译错误
- 程序可以运行
- 输出结果错误
- 难以定位

**常见示例**:
```javascript
// 错误的条件判断
if (age > 18) { // 应该是 >=
  allowAccess();
}

// 循环边界错误(off-by-one)
for (let i = 0; i <= arr.length; i++) { // 应该是 <
  console.log(arr[i]);
}

// 错误的计算逻辑
const total = price + tax; // 应该是 price * (1 + tax)

// 异步逻辑错误
async function fetchData() {
  const data = await fetch(url);
  return data; // 忘记解析JSON
}
```

**根本原因**:
- 对业务需求理解不准确
- 边界条件考虑不周
- 异步流程处理不当
- 状态管理混乱

**预防策略**:
- 编写详细的单元测试
- 使用边界值测试
- 代码审查(Code Review)
- 添加断言(assertions)
- 使用调试工具逐步执行

---

### 4. 架构问题 (Architectural Issues)

**定义**: 代码结构、模块划分、依赖关系等架构层面的问题。

**特征**:
- 代码可以运行
- 难以维护和扩展
- 模块耦合度高
- 职责划分不清

**常见示例**:
```javascript
// 循环依赖
// moduleA.js
import { funcB } from './moduleB';
export function funcA() { funcB(); }

// moduleB.js
import { funcA } from './moduleA';
export function funcB() { funcA(); }

// 职责不清
class UserController {
  createUser(data) {
    // 直接操作数据库(应该通过Service层)
    db.insert('users', data);
    // 直接发送邮件(应该通过EmailService)
    sendEmail(data.email);
  }
}

// 过度耦合
function processOrder(order) {
  // 直接依赖具体实现而非接口
  const payment = new StripePayment();
  payment.charge(order.amount);
}
```

**根本原因**:
- 缺乏架构设计
- 不了解设计模式
- 快速开发忽略架构
- 技术债务积累

**预防策略**:
- 遵循SOLID原则
- 使用分层架构(Controller-Service-Repository)
- 依赖注入(Dependency Injection)
- 定期重构
- 架构评审

---

### 5. 集成问题 (Integration Issues)

**定义**: 与外部系统、API、数据库等集成时出现的问题。

**特征**:
- 本地测试正常,集成环境出错
- 网络相关错误
- 数据格式不匹配
- 认证/授权失败

**常见示例**:
```javascript
// CORS跨域问题
fetch('https://api.example.com/data')
  .then(res => res.json())
  .catch(err => console.error('CORS error'));

// API版本不兼容
const response = await api.getUser(userId);
// API返回格式变更,导致解析失败
const name = response.data.user.name; // Error: Cannot read property 'name'

// 数据库连接问题
const db = await connectDB({
  host: 'localhost', // 生产环境应该是远程地址
  port: 5432
});

// 认证token过期
const data = await fetch(url, {
  headers: {
    'Authorization': `Bearer ${oldToken}` // token已过期
  }
});
```

**根本原因**:
- 环境配置不一致
- API文档过时
- 缺少错误处理
- 未考虑网络延迟/失败

**预防策略**:
- 使用环境变量管理配置
- API版本控制
- 添加重试机制
- 完善错误处理
- 集成测试
- 使用API mock进行本地测试

---

### 6. 性能问题 (Performance Issues)

**定义**: 代码功能正确但性能不佳,响应慢、内存占用高等。

**特征**:
- 响应时间过长
- 内存泄漏
- CPU占用率高
- 用户体验差

**常见示例**:
```javascript
// N+1查询问题
for (const user of users) {
  const posts = await db.query('SELECT * FROM posts WHERE user_id = ?', user.id);
  // 应该使用JOIN或批量查询
}

// 未优化的循环
for (let i = 0; i < arr.length; i++) {
  for (let j = 0; j < arr.length; j++) {
    // O(n²)复杂度
  }
}

// 内存泄漏
const cache = {};
function addToCache(key, value) {
  cache[key] = value; // 永不清理,导致内存泄漏
}

// 未使用索引
SELECT * FROM users WHERE email = 'test@example.com';
// email字段未建立索引
```

**根本原因**:
- 算法复杂度过高
- 数据库查询未优化
- 缺少缓存机制
- 资源未释放

**预防策略**:
- 使用性能分析工具(Chrome DevTools, Node.js Profiler)
- 数据库查询优化(索引、JOIN)
- 实现缓存策略
- 代码复杂度分析
- 性能测试

---

### 7. 安全问题 (Security Issues)

**定义**: 可能导致安全漏洞的代码问题。

**特征**:
- SQL注入风险
- XSS攻击风险
- 敏感信息泄露
- 认证/授权绕过

**常见示例**:
```javascript
// SQL注入
const query = `SELECT * FROM users WHERE username = '${username}'`;
// 应该使用参数化查询

// XSS攻击
element.innerHTML = userInput;
// 应该使用textContent或sanitize

// 敏感信息泄露
console.log('User password:', password);
// 不应该记录敏感信息

// 弱密码验证
if (password.length >= 6) {
  // 太弱,应该要求更复杂的密码
}
```

**根本原因**:
- 安全意识不足
- 未进行输入验证
- 缺少安全审计

**预防策略**:
- 使用参数化查询
- 输入验证和sanitization
- 使用安全库(helmet, bcrypt)
- 定期安全审计
- 遵循OWASP Top 10

---

## 严重程度评级

### 严重 (Critical)

**定义**: 导致系统崩溃、数据丢失或严重安全漏洞的错误。

**特征**:
- 系统无法启动或运行
- 数据损坏或丢失
- 严重的安全漏洞
- 影响所有用户

**示例**:
- 数据库连接失败导致服务不可用
- SQL注入漏洞
- 内存泄漏导致服务器崩溃
- 认证绕过漏洞

**处理优先级**: 最高,立即修复

---

### 重要 (Major)

**定义**: 影响核心功能但不导致系统崩溃的错误。

**特征**:
- 核心功能无法使用
- 影响部分用户
- 有workaround但不理想
- 性能严重下降

**示例**:
- 用户无法登录
- 支付功能失败
- 关键API返回错误
- 页面加载时间过长(>5秒)

**处理优先级**: 高,尽快修复

---

### 次要 (Minor)

**定义**: 影响用户体验但不影响核心功能的错误。

**特征**:
- 非核心功能异常
- UI显示问题
- 轻微的性能问题
- 有简单的workaround

**示例**:
- 按钮样式错误
- 提示信息拼写错误
- 非关键功能的小bug
- 轻微的响应延迟

**处理优先级**: 中,计划修复

---

## 常见错误模式库

### 模式 1: 未处理的Promise拒绝

**错误代码**:
```javascript
async function fetchData() {
  const response = await fetch(url);
  return response.json();
}

fetchData(); // 未处理可能的错误
```

**正确做法**:
```javascript
async function fetchData() {
  try {
    const response = await fetch(url);
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    return await response.json();
  } catch (error) {
    console.error('Failed to fetch data:', error);
    throw error;
  }
}

fetchData().catch(err => {
  // 处理错误
});
```

---

### 模式 2: 状态更新时机错误

**错误代码**:
```javascript
function updateUser() {
  setLoading(true);
  fetchUser().then(user => {
    setUser(user);
  });
  setLoading(false); // 错误:立即设置为false
}
```

**正确做法**:
```javascript
async function updateUser() {
  setLoading(true);
  try {
    const user = await fetchUser();
    setUser(user);
  } finally {
    setLoading(false); // 正确:在完成后设置
  }
}
```

---

### 模式 3: 闭包陷阱

**错误代码**:
```javascript
for (var i = 0; i < 5; i++) {
  setTimeout(() => {
    console.log(i); // 输出5次5
  }, 1000);
}
```

**正确做法**:
```javascript
for (let i = 0; i < 5; i++) {
  setTimeout(() => {
    console.log(i); // 输出0,1,2,3,4
  }, 1000);
}
```

---

### 模式 4: 对象引用问题

**错误代码**:
```javascript
const original = { name: 'Alice', age: 25 };
const copy = original;
copy.age = 26;
console.log(original.age); // 26,原对象被修改
```

**正确做法**:
```javascript
const original = { name: 'Alice', age: 25 };
const copy = { ...original }; // 浅拷贝
copy.age = 26;
console.log(original.age); // 25,原对象未被修改
```

---

### 模式 5: 竞态条件

**错误代码**:
```javascript
let latestRequestId = 0;

function searchUsers(query) {
  const requestId = ++latestRequestId;
  fetch(`/api/users?q=${query}`)
    .then(res => res.json())
    .then(users => {
      setUsers(users); // 可能显示旧请求的结果
    });
}
```

**正确做法**:
```javascript
let latestRequestId = 0;

function searchUsers(query) {
  const requestId = ++latestRequestId;
  fetch(`/api/users?q=${query}`)
    .then(res => res.json())
    .then(users => {
      if (requestId === latestRequestId) {
        setUsers(users); // 只使用最新请求的结果
      }
    });
}
```

---

## 错误分类决策树

```
开始
  |
  ├─ 代码无法编译/解析? ─ 是 ─> 语法错误
  |                      否
  |                       |
  ├─ TypeScript类型检查失败? ─ 是 ─> 类型错误
  |                          否
  |                           |
  ├─ 与外部系统交互失败? ─ 是 ─> 集成问题
  |                      否
  |                       |
  ├─ 性能不符合要求? ─ 是 ─> 性能问题
  |                  否
  |                   |
  ├─ 存在安全风险? ─ 是 ─> 安全问题
  |                否
  |                 |
  ├─ 代码结构/设计问题? ─ 是 ─> 架构问题
  |                      否
  |                       |
  └─ 功能结果不正确? ─ 是 ─> 逻辑错误
                      否
                       |
                      未知错误类型
```

---

## 使用指南

### 如何分类错误

1. **阅读错误消息**: 确定错误的直接原因
2. **分析错误上下文**: 理解错误发生的场景
3. **使用决策树**: 按照决策树逐步判断
4. **评估严重程度**: 根据影响范围和后果评级
5. **记录到报告**: 在反思报告中详细记录

### 如何评估严重程度

考虑以下因素:
- **影响范围**: 影响多少用户?
- **功能重要性**: 是核心功能还是辅助功能?
- **数据风险**: 是否可能导致数据丢失或损坏?
- **安全风险**: 是否存在安全漏洞?
- **可恢复性**: 是否容易恢复?

### 如何使用模式库

1. **识别模式**: 将遇到的错误与模式库对比
2. **学习正确做法**: 参考模式库中的解决方案
3. **更新模式库**: 发现新模式时添加到库中
4. **分享经验**: 将有价值的模式分享给团队

---

## 扩展和维护

### 添加新的错误类型

当发现新的错误类型时:
1. 定义错误类型的特征
2. 提供典型示例
3. 分析根本原因
4. 制定预防策略
5. 更新决策树

### 更新模式库

定期审查和更新:
- 添加新发现的常见模式
- 更新解决方案
- 删除过时的模式
- 补充更多示例

---

**最后更新**: 2026-02-15
**版本**: v1.0
