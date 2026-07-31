# 团队工具

按场景分类整理当下热门、可私有化部署的团队协作工具。

## 分类与索引

| 分类 | 文档 |
| --- | --- |
| **云盘 / 文件协作** | [云盘工具.md](云盘工具.md) |
| **即时通讯 / 团队聊天** | [及时通讯.md](及时通讯.md) |
| **知识库 / 文档 / Wiki** | [知识库.md](知识库.md) |
| **项目管理 / 任务协作** | [项目管理.md](项目管理.md) |

## 选型速查

| 场景 | 建议 |
| --- | --- |
| 企业盘、文件同步 + 在线协作 | Nextcloud |
| 音视频文件分享 + 协作 | Seafile |
| 对象存储 / S3 替代 | MinIO |
| 团队聊天、Slack 替代 | Mattermost / Rocket.Chat |
| 安全/端到端加密 IM | Element (Matrix) |
| 公司内部 Wiki / 文档库 | Confluence（付费）或 Outline / Wiki.js |
| 替代 Notion、本地化笔记本 | AppFlowy / SiYuan / AFFiNE |
| 轻量化任务 + 看板 | Focalboard / Plane |
| Jira 替代 + 全面项目管理 | Redmine / OpenProject |
| Scrum + 看板 + 路线图 | Taiga |

## 选型维度

- **协议 / 标准**：OIDC / SAML / ActivityPub / S3 / WebDAV，方便联动
- **客户端生态**：Web / Desktop / iOS / Android / Linux 客户端是否齐全
- **插件 / 扩展**：应用 + 集成 + API 丰富度
- **运维成本**：单体 / 微服务、内存 / 磁盘、升级是否平滑
- **数据库 / 依赖**：PG、MySQL、Redis、MinIO
- **许可证**：AGPL / MIT / Apache 2.0 / 商业版权
- **中文支持**：界面 / 文档 / 搜索 / OCR
- **审计 / 合规**：等保 / SOC2 / GDPR / HIPAA

## 总体趋势

- **本地优先 / Local-first**：AppFlowy / Logseq / SiYuan 都强调"数据在自己本地"
- **AI 加持**：内置 AI 助手、RAG 集成、自动化
- **协作协议标准化**：Element（Matrix）、Joplin Sync、AFFiNE Cloud 走向开放生态
- **All-in-One vs 专精**：Nextcloud、AppFlowy 向 ALL-in-One 走，但单一场景专精工具仍然有优势
- **可观测性集成**：任务 / 文档与日历 / 邮件 / AI / 监控打通
