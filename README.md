# NextFind 企业微信助手

NotifyHub 插件：通过企业微信和 NextFind OpenAPI 交互，支持搜索、查看资源、订阅和转存。

## 功能

- 企业微信文本消息回调
- 搜索电影/电视剧
- 数字选择搜索结果查看资源
- 数字选择资源直接转存
- 订阅搜索结果
- 查看订阅列表

## 安装

把本目录放到 NotifyHub 插件目录：

```bash
/appdata/notifyhub/data/plugins/nextfind_assistant
```

然后重启 NotifyHub。

企业微信回调地址：

```text
https://你的NotifyHub域名/api/plugins/nextfind_assistant/chat
```

## 配置

所有配置都在 NotifyHub 插件页填写，仓库里不包含任何真实密钥。

| 字段 | 说明 |
| --- | --- |
| `nextfind_base_url` | NextFind OpenAPI 地址，例如 `https://nextfind.example.com/api/openapi` |
| `nextfind_api_key` | NextFind OpenAPI Key |
| `qywx_base_url` | 企业微信 API 地址，例如 `https://qyapi.weixin.qq.com` |
| `sCorpID` | 企业微信 CorpID |
| `sCorpsecret` | 企业微信 Secret |
| `sAgentid` | 企业微信 AgentID |
| `sToken` | 企业微信回调 Token |
| `sEncodingAESKey` | 企业微信回调 EncodingAESKey |

## 命令

```text
搜 阿凡达
1
订阅1
订阅列表
```

交互规则：

- 搜索结果阶段回复数字：查看该条资源
- 资源列表阶段回复数字：直接转存该资源
- 搜索结果阶段回复 `订阅1`：订阅第 1 个结果

## 说明

插件收到企业微信回调后会立即返回 `success`，处理完成后再通过企业微信主动消息发送结果。
