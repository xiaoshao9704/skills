---
name: go-openapi-bidirectional-sync
description: 面向 Go 项目的 OpenAPI 双向生成与同步技能。用于 Spec First（从 openapi.yaml 生成/更新代码与协议）和 Code First（从 router/handler 反推 OpenAPI），优先 chi，兼容 gin/echo/net/http。适用于 Claude Code 与 Codex 场景。
---

# Go 项目 OpenAPI 双向生成与同步（中文友好版）

## 概览

使用本技能在 `openapi.yaml` 与 Go 服务端代码之间做双向推导、生成与增量同步。

优先直接执行，尽量减少追问；仅在缺少关键参数时提问。

支持 **Claude Code** 与 **Codex** 两类代理使用。

## 工作流总览

1. 判定模式：
   - **Spec First**：用户先有 OpenAPI，或希望先组装/更新 `openapi.yaml`。
   - **Code First**：用户先有 Go 代码，要求从 router/handler 反推 OpenAPI。
2. 判定路径：
   - OpenAPI 路径：用户指定优先；未指定默认 `api/openapi.yaml`。
   - 生成目录：用户指定优先；未指定默认 `internal/generated`。
3. 判定范围：
   - 全量路由反推。
   - 单接口定向反推（例如 `/api/v1/orders/{id}`）。
4. 输出结果：
   - OpenAPI 文档（完整、单 path 片段、或增量补丁）。
   - 代码生成结果（models/interface/stub/路径建议）。
   - 分析报告（证据链、不确定项、待补充信息）。

## 交互策略（少问、多做）

仅在以下情况追问最少必要信息：

- Spec First 缺关键项：`path`、`method`、请求结构、响应结构。
- Code First 缺入口：router 文件未知、handler 目录未知、项目入口不清晰。
- 用户未说明是全量反推还是单接口反推。
- 项目中存在多个候选 OpenAPI 文件或多个生成目录，且用户未指定。

如果可合理推断，直接推断并明确标注“推断项”。

## Spec First 模式

### 1) 仅提供必要参数时，自动组装 OpenAPI

组织以下信息：

1. 服务基础信息：
   - `info.title`、`info.version`、`info.description`
   - `servers[].url`
2. 接口基础信息：
   - `path`、`method`、`summary`、`description`、`tags`
3. 请求信息：
   - path/query/header 参数
   - requestBody 与 content-type
4. 响应信息：
   - status code
   - success/error body schema
   - 通用错误码与错误响应结构
5. 组件信息：
   - 可复用 `components.schemas`
   - 通用响应包装结构
   - `securitySchemes`（Bearer Token/API Key）

缺失但可推断时，补默认值并标注推断依据。

### 2) 增量更新优先

若项目已存在 OpenAPI，优先复用并增量更新，不默认整体重写。

重点复用：

- `paths`
- `components`
- `components.schemas`
- `components.securitySchemes`
- `tags`
- 现有命名风格与字段风格

可输出：

- 完整更新后的 `openapi.yaml`
- 单独的 `paths/components` 增量片段

### 3) 根据 OpenAPI 生成 Go 代码（固定优先 oapi-codegen）

生成代码时默认优先 **oapi-codegen**。

执行规则：

1. 若项目已有 oapi-codegen 配置，优先复用。
2. 若无配置，提供默认配置示例并解释关键字段。
3. 默认推荐（chi 场景）至少包含：
   - `models: true`
   - `chi-server: true`
   - `strict-server: true`

默认示例：

```yaml
package: generated
output: internal/generated/server.gen.go
generate:
  models: true
  chi-server: true
  strict-server: true
output-options:
  skip-prune: true
```

说明要点：

- `strict-server` 必须搭配具体 server 选项（如 `chi-server` / `gin-server`）。
- `strict-server` 不等于完整请求校验；必要时补充校验中间件。

自定义输出目录/package 时，同步调整：

- `output`
- `package`

建议命令：

```go
//go:generate go tool oapi-codegen -config cfg.yaml api/openapi.yaml
```

工具安装建议：

```bash
go get -tool github.com/oapi-codegen/oapi-codegen/v2/cmd/oapi-codegen@latest
```

## Code First / Reverse Generate 模式

必须基于代码证据推导，不臆造接口/字段/状态码。

### 1) 基于 router 全量反推

当用户提供 router/route register 文件时：

1. 枚举所有注册路由。
2. 提取每条路由：
   - HTTP method
   - path
   - handler/controller 引用
3. 反查对应 handler/controller 实现。
4. 分析请求/响应结构。
5. 递归解析跨文件类型依赖。
6. 产出 OpenAPI 的：
   - `paths`
   - `parameters`
   - `requestBody`
   - `responses`
   - `components.schemas`
7. 输出完整文档或增量更新结果。

### 2) 基于指定接口定向反推

当用户只指定某个接口地址时：

1. 在 router 中匹配该地址。
2. 定位对应 handler/controller。
3. 仅分析该接口请求与响应。
4. 输出该接口对应 OpenAPI 片段。
5. 自动补齐该接口依赖的 schema。
6. 不扫描整个项目。

## Go 代码推断规则

优先证据来源：

- `json` tag
- `form` tag
- `uri`/`param` tag
- 注释
- bind/decode 调用方式
- path/query/header 读取逻辑

请求来源映射：

- URL 路径变量 -> path parameters
- query 读取 -> query parameters
- header 读取 -> header parameters
- JSON bind/decode -> requestBody

响应推断：

- 状态码写入逻辑
- JSON 输出逻辑
- 统一响应封装
- 返回对象结构

递归类型解析应支持：

- 基础类型
- 指针
- slice/array
- map
- 匿名结构体
- 嵌套结构体
- type alias
- 跨文件引用

尽量保留 required/optional 语义：

- 指针 vs 非指针
- `omitempty`
- 默认值/校验痕迹

识别统一响应包装并抽离业务 data：

- `code/message/data`
- `errNo/errMsg/data`
- `BaseResponse[T]`
- `Response[T]`
- `CommonResult`

若无法完全确定语义：

- 输出保守推断
- 标注不确定项
- 给出推断依据（代码证据）

## 输出格式约定

至少输出以下之一：

### A. OpenAPI 输出

- 完整 `openapi.yaml`
- 单个 path 的 YAML 片段
- `components/schemas` 增量补丁

### B. 代码生成输出

- 生成的 Go struct
- 接口定义 / handler stub
- 生成文件路径建议
- oapi-codegen 配置建议

### C. 分析报告

- 识别到的路由清单
- 路由到 handler/controller 的映射
- 推断的 request/response 类型
- 依赖 schema
- 不确定项与原因
- 需要用户补充的信息

## 执行前检查清单

1. 使用用户路径；未指定则默认：`api/openapi.yaml`、`internal/generated`。
2. 发现已有 OpenAPI 时优先增量更新与复用。
3. Spec First 生成代码时固定优先 `oapi-codegen`。
4. 单接口场景严格限制分析范围，避免全项目扫描。
5. 区分“已确认项”与“推断项”。
6. 禁止臆造不存在的接口、字段、状态码。

## 脚本支持（建议优先使用）

本技能已提供可复用扫描脚本，适用于 Claude Code 与 Codex 的自动化执行链路。

### 1) 路由扫描脚本

文件：`scripts/scan_routes.py`

用途：扫描 Go 项目中的路由注册，输出 `method/path/handler/file/line/evidence` 映射。

示例：

```bash
python scripts/scan_routes.py --project-root /path/to/project
python scripts/scan_routes.py --project-root /path/to/project --endpoint /api/v1/orders/{id} --method GET
```

### 2) 单接口推断脚本

文件：`scripts/infer_endpoint_schema.py`

用途：基于 handler 函数名做保守推断，输出请求来源与响应证据（path/query/header/json/status）。

示例：

```bash
python scripts/infer_endpoint_schema.py \
  --project-root /path/to/project \
  --handler GetOrder \
  --path /api/v1/orders/{id} \
  --method GET
```

### 3) OpenAPI 增量合并脚本（JSON v1）

文件：`scripts/merge_openapi_patch.py`

用途：将 OpenAPI patch 合并到 base 文档（当前脚本使用 JSON 输入输出，保证无额外依赖）。

示例：

```bash
python scripts/merge_openapi_patch.py \
  --base api/openapi.json \
  --patch api/openapi.patch.json \
  --out api/openapi.merged.json
```

说明：如项目主文档是 YAML，可在外层流程先做 YAML/JSON 转换后再调用该脚本。
