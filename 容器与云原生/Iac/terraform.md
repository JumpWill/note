# Terraform 笔记

## 认识

HashiCorp 出品的 **基础设施即代码（IaC）** 工具，使用声明式 HCL 语言（HashiCorp Configuration Language）描述期望的资源终态，由 Terraform 自行计算与当前状态的差异并执行变更。

核心特征：

- **声明式**：只描述"要什么"，不写"怎么做"
- **状态驱动**：通过 state 文件对比期望与现实
- **Provider 生态**：几乎所有公有云、Saas 服务、Kubernetes 都有官方/社区 provider
- **执行图（plan/apply graph）**：先 `plan` 再 `apply`，变更可预览
- **不可变基础设施**：鼓励替换而非修改（如 `terraform taint` → `terraform replace`）

与同类工具对比：

| 工具 | 形态 | 语言 | 状态管理 | 适用 |
|---|---|---|---|---|
| Terraform | 客户端 | HCL | 显式 state 文件 | 多云、SaaS、K8s |
| Pulumi | 客户端 | TypeScript/Go/Python | 显式 state 文件 | 程序员友好、需要复杂逻辑 |
| Ansible | 客户端 | YAML | 无状态 | 配置管理、应用部署 |
| CloudFormation | 服务端 | YAML/JSON | 由 AWS 管理 | 纯 AWS 场景 |
| CDK | 服务端 | TypeScript/Python | 由 AWS 管理 | AWS + 程序员友好 |

---

## 核心概念

### Provider

声明使用哪个云/服务的插件，例如 `aws`、`kubernetes`、`helm`。

```hcl
terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = "us-east-1"
}
```

注意点：

- **版本约束一定要写**（`~>` 锁定次版本，`>=` 只锁下限），否则 provider 升级可能带来 breaking change
- 多 region/多账号用 `provider` 的 `alias` 机制：先定义 `provider "aws" { alias = "us_west" }`，再在 `resource` 里用 `provider = aws.us_west`
- 敏感凭证**不要**写进 provider 块，应该用环境变量、`~/.aws/credentials`、OIDC、Vault 等

### Resource

最小声明单位，对应一个云上实体。

```hcl
resource "aws_instance" "web" {
  ami           = "ami-0c55b159cbfafe1f0"
  instance_type = "t3.micro"
  tags = {
    Name = "web-server"
  }
}
```

引用其他 resource 的属性：`<resource_type>.<name>.<attribute>`，例如 `aws_instance.web.id`。

### State

State 是 Terraform 的"记忆"，记录每个资源当前真实状态、属性、依赖关系。

文件格式：本地是 `terraform.tfstate`，远程通常是 `.tfstate` 存储在 S3/OSS/Terraform Cloud/GCS 等。

⚠️ **状态文件包含敏感信息（密码、密钥、ID），必须加密 + 权限控制**。

#### 后端（Backend）

```hcl
terraform {
  backend "s3" {
    bucket         = "my-tf-state"
    key            = "prod/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "tf-lock"   # 配合 DynamoDB 做 state 锁
    encrypt        = true
  }
}
```

常见后端：

| Backend | 锁 | 适用 |
|---|---|---|
| local | ❌ | 个人本地玩 |
| s3 + dynamodb | ✅ | AWS 生产推荐 |
| oss + aliyun | ✅ | 阿里云生产推荐 |
| cos + 自行实现 | ✅ | 腾讯云 |
| gcs | ✅ | GCP |
| terraform cloud | ✅ | 不自建、SaaS |
| remote (HCP) | ✅ | 团队托管 |
| http | 自行实现 | 自定义存储 |

### Module

把一组 resource 封装成可复用单元。**所有生产代码都应该模块化**，而不是一个大 `main.tf`。

```hcl
module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "5.0.0"

  name = "my-vpc"
  cidr = "10.0.0.0/16"
  azs  = ["us-east-1a", "us-east-1b"]
  public_subnets  = ["10.0.1.0/24", "10.0.2.0/24"]
  private_subnets = ["10.0.10.0/24", "10.0.11.0/24"]
}
```

Module 来源：

- 本地路径：`source = "./modules/network"`
- Git：`source = "git::https://github.com/foo/bar.git?ref=v1.0"`
- Terraform Registry：`source = "hashicorp/consul/aws"`（默认仓库）
- 私有 Registry：自建或用 Terraform Cloud

### Variable & Output

Variable：输入参数化，便于跨环境复用

```hcl
variable "instance_type" {
  type        = string
  default     = "t3.micro"
  description = "EC2 instance type"
  sensitive   = false       # true 时 plan/apply 输出会打码
  validation {
    condition     = contains(["t3.micro", "t3.small", "t3.medium"], var.instance_type)
    error_message = "Only t3 family supported."
  }
}
```

变量赋值优先级：CLI `-var` → `*.auto.tfvars` → 环境变量 `TF_VAR_<name>` → `terraform.tfvars` → `default`。

Output：把资源属性"导出"，常用于跨 stack 传递或调试。

```hcl
output "db_endpoint" {
  value     = aws_db_instance.main.endpoint
  sensitive = true
}
```

### Data Source

只读查询，不创建资源。常用于获取已有数据。

```hcl
data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"]

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }
}
```

### Lifecycle

控制资源的特殊行为：

```hcl
resource "aws_instance" "web" {
  ami           = data.aws_ami.ubuntu.id
  instance_type = "t3.micro"

  lifecycle {
    create_before_destroy = true   # 先创建新再销毁旧，零停机
    prevent_destroy       = true   # 防止误删（数据库常用）
    ignore_changes        = [tags, ami]   # 外部修改不感知
  }
}
```

### Provisioner

在资源创建后跑本地/远程命令。**能不用就不用**，IaC 的精神是声明而非命令。

```hcl
provisioner "remote-exec" {
  inline = ["sudo apt update", "sudo apt install -y nginx"]
}
```

替代方案：

- 用 `user_data` / cloud-init
- 用 Ansible / Chef / Puppet 做配置管理
- 用 Packer 烘焙镜像

---

## 工作流

```
terraform init       # 初始化：下载 provider、初始化 backend
  ↓
terraform validate   # 语法/类型检查
  ↓
terraform fmt        # 格式化（HCL 官方风格）
  ↓
terraform plan       # 预览：对比 state 与配置，输出 diff
  ↓
terraform apply      # 执行：plan 通过后实际变更
  ↓
terraform destroy    # 销毁：慎用！生产几乎不用，全部走一个个 resource 删
```

辅助命令：

- `terraform output` - 查看 output 值
- `terraform state list` / `show` / `mv` / `rm` - 操作 state
- `terraform import` - 把已有资源导入 state
- `terraform refresh` - 把真实状态重新写入 state（已废弃，推荐用 `apply -refresh-only`）
- `terraform graph` - 输出依赖图（dot 格式）

---

## 各环境最佳实践

### 本地开发

- 用 `local` backend 或 `s3` 后端 + 单独 key
- 推荐目录布局：

```
.
├── modules/                # 自定义 module
│   └── network/
│       ├── main.tf
│       ├── variables.tf
│       ├── outputs.tf
│       └── README.md
├── envs/                   # 每个环境一个目录
│   ├── dev/
│   │   ├── main.tf         # 引用 module
│   │   ├── variables.tf
│   │   ├── backend.tf      # 不同环境不同 key
│   │   └── terraform.tfvars
│   ├── staging/
│   └── prod/
└── README.md
```

- `terraform console` 交互式测试表达式
- 用 `pre-commit` 配合 `terraform fmt -check` / `tflint` / `tfsec` / `checkov`
- 单人操作时，可以靠 `terraform.lock.hcl` 锁定 provider 版本：

```hcl
terraform {
  required_providers {
    aws = {
      version = "5.31.0"
      source  = "hashicorp/aws"
    }
  }
}
```

### 开发环境（Dev）

特点：可以乱搞，资源成本敏感，团队多人共用但容易污染。

最佳实践：

- **自动 TTL**：用 `null_resource` + `time_rotating` 配合 lambda，定时销毁
- **命名加前缀**：`dev-` 开头，方便审计与清理
- **state 加锁**，否则同事一 apply 你的就没了
- 使用 `workspaces` 隔离不同开发者的 dev 环境：

```bash
terraform workspace new alice
terraform workspace select alice
```

但 workspace 共享一个 state 文件（用 key 前缀区分），有性能/权限粒度问题，**复杂场景推荐用 Terragrunt 的文件夹布局**。

### 预发布 / Staging

与生产架构一致，但规模小、生命周期短。

最佳实践：

- **数据用脱敏数据**，不要直接复制生产
- state 与生产完全独立（不同 bucket、不同 key）
- 跑完整的 `plan` + 自动化测试 + 真实 apply，做变更演练
- 用 **Atlantis** 或 **Terraform Cloud** 跑 PR 自动化：开发者提 PR 时自动 plan，并把 plan 结果回写到 PR 评论

### 生产环境（Prod）

这是重点中的重点。

#### 1. State 管理

- **远端 backend + 加密 + 锁**，S3/DynamoDB 是黄金组合
- **开启版本控制**（S3 versioning），state 文件可以回滚
- **强制 MFA 删除**：S3 桶删除时需要 MFA
- 定期快照 state 到独立位置

```hcl
terraform {
  backend "s3" {
    bucket         = "company-tfstate-prod"
    key            = "vpc/terraform.tfstate"
    region         = "ap-southeast-1"
    dynamodb_table = "tf-lock-prod"
    encrypt        = true
    kms_key_id     = "arn:aws:kms:ap-southeast-1:111:key/xxx"
  }
}
```

#### 2. 代码组织

- **每个环境一个目录**（不是 workspace），state 完全独立
- 公共配置抽到 module
- 用 Terragrunt 处理多环境的 DRY 问题：

```hcl
# terragrunt.hcl
include "root" {
  path = find_in_parent_folders()
}

terraform {
  source = "../../modules//network"
}

inputs = {
  env         = "prod"
  cidr_block  = "10.0.0.0/16"
  environment = local.environment_vars
}
```

#### 3. 变更流程

```
PR → 自动化 plan（Atlantis / GitHub Actions）→ Code Review → 人工审批 → 自动/手动 apply
```

- **永远不要在本地直接 `terraform apply`** 到生产
- 生产 apply 应走 CI/CD 或 Terraform Cloud，加审批人
- 启用 policy as code：Sentinel / OPA / Conftest

#### 4. 安全与合规

- 敏感变量标 `sensitive = true`
- 凭据走 **OIDC 联邦**（CI runner → 云），不要存 long-lived AK/SK

```hcl
# GitHub Actions OIDC 登录 AWS 示例
provider "aws" {
  region = "ap-southeast-1"
  # AK/SK 通过环境变量 + STS AssumeRoleWithWebIdentity
}
```

- 用 `tfsec` / `checkov` / `terrascan` 扫描安全违规
- 启用审计日志：CloudTrail / ActionTrail，记录所有 API 调用
- 生产资源打 tag（环境、所有者、成本中心）

#### 5. 零停机变更

- ASG / 多副本：先扩后缩
- 数据库：`create_before_destroy = true`，加 `prevent_destroy`
- ELB / ALB：滚动替换
- 用蓝绿或金丝雀发布，Terraform 只负责基础设施，应用层用 Argo Rollouts / Flagger

#### 6. 灾备

- state 文件异地备份
- 配置走 Git，单一可信源（GitOps 思想）
- module 内部资源尽量幂等、可重建

### 多云环境

Terraform 的一大优势是同一个工具管理多家云。

最佳实践：

- 每个云一套目录，互不干扰：

```
.
├── aws-prod/
├── aws-staging/
├── gcp-prod/
├── azure-shared/
```

- 跨云数据传递用 **remote state**：

```hcl
data "terraform_remote_state" "aws_vpc" {
  backend = "s3"
  config = {
    bucket = "shared-tfstate"
    key    = "aws-vpc/terraform.tfstate"
    region = "ap-southeast-1"
  }
}
```

- 跨云通信一般靠专线或 VPN
- 不要在配置里混用多个 provider 干同一件事（容易出错），明确职责划分

### CI/CD 集成

#### GitHub Actions 范例

```yaml
name: Terraform
on:
  pull_request:
    paths: ['**.tf']
  push:
    branches: [main]

jobs:
  terraform:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: hashicorp/setup-terraform@v3
        with:
          terraform_version: 1.7.0

      - name: Format
        run: terraform fmt -check -recursive

      - name: Init
        run: terraform init -backend-config=environments/prod/backend.hcl

      - name: Validate
        run: terraform validate

      - name: Plan
        if: github.event_name == 'pull_request'
        run: terraform plan -no-color
        env:
          AWS_ROLE_ARN: ${{ secrets.AWS_ROLE_ARN }}

      - name: Apply
        if: github.ref == 'refs/heads/main' && github.event_name == 'push'
        run: terraform apply -auto-approve
```

#### Atlantis（PR 自动化）

- 自托管服务
- 监听 PR，自动跑 plan，评论结果
- 加 `atlantis apply` 触发 apply

#### Terraform Cloud / HCP

- 官方 SaaS
- 状态管理、远程执行、policy、sentinel 一体化
- 适合不想自建 CI 的中小团队

---

## 常见坑与反模式

### 1. State 漂移（Drift）

有人绕过 Terraform 在控制台改了资源，导致 state 与现实不一致。

检测：`terraform plan` 会报 drift。

解决：

- 制度上禁止手动改（写文档、加 IAM 限制）
- 定期 `terraform plan -detailed-exitcode` 跑 CI 监控
- 实在有合法需求，用 `terraform import` 把外部修改纳入管理

### 2. State 锁竞争

两个 apply 同时跑，互相锁住。

解决：

- 后端带锁（S3+DynamoDB、OSS+Table）
- CI 加并发限制（`concurrency`）
- 不要在本地跑生产 apply

### 3. 销毁整个 stack

`terraform destroy` 误操作清空生产数据库的故事听过很多。

解决：

- 关键资源加 `lifecycle.prevent_destroy = true`
- 后端 bucket 开启 MFA delete
- IAM 权限收紧，生产环境 apply/destroy 走审批

### 4. Module 升级踩坑

`version = ">= 1.0"` 这种写法会一直拉到最新。

解决：用 `~>` 锁次版本或精确锁版本，每次升级走 PR 评估。

### 5. 变量过多导致维护困难

`variables.tf` 几十个变量，没人记得清。

解决：用 `object` 类型聚合：

```hcl
variable "network" {
  type = object({
    cidr_block = string
    subnets    = list(string)
    azs        = list(string)
  })
}
```

### 6. Provider 凭据硬编码

```hcl
provider "aws" {
  access_key = "AKIA..."   # 严禁！
  secret_key = "..."
}
```

解决：环境变量、profile、OIDC、Vault。

### 7. 巨型 stack

一个 state 文件管上万资源，`plan` 跑半小时。

解决：

- 按生命周期/团队拆分 stack（`infra-state` / `app-state`）
- 用 `terraform workspace` 或 Terragrunt 子目录

---

## 进阶主题

### 1. 动态块（Dynamic Blocks）

生成重复嵌套块：

```hcl
resource "aws_security_group" "main" {
  name = "main"

  dynamic "ingress" {
    for_each = var.ingress_rules
    content {
      from_port   = ingress.value.port
      to_port     = ingress.value.port
      protocol    = "tcp"
      cidr_blocks = ingress.value.cidr_blocks
    }
  }
}
```

### 2. for_each 与 count

- `count = N`：用索引 `[0]`，删中间元素会触发重建（**避免用在生产资源上**）
- `for_each = { ... }`：用 key，删中间不影响其他资源（**推荐**）

```hcl
resource "aws_instance" "web" {
  for_each = {
    alice = "t3.micro"
    bob   = "t3.small"
  }
  ami           = data.aws_ami.ubuntu.id
  instance_type = each.value
  tags = {
    Name = each.key
  }
}
```

### 3. 表达式与函数

常用：

- `merge(a, b)` - 合并 map
- `concat(list1, list2)` - 拼接 list
- `jsonencode(...)` / `jsondecode(...)` - 序列化
- `lookup(map, key, default)` - 安全取值
- `try(expr, default)` - 错误兜底
- `file("path")` - 读文件内容
- `templatefile("path", vars)` - 模板渲染

### 4. 远程执行

```hcl
resource "null_resource" "run" {
  triggers = {
    always_run = timestamp()
  }
  provisioner "local-exec" {
    command = "echo triggered at ${timestamp()}"
  }
}
```

### 5. Terraform Cloud 特性

- Remote execution（terraform 在 TFC 端跑，不在 CI）
- Sentinel policy（强制约束，例如禁止 `t3.micro` 出现在 prod）
- Cost estimation
- 团队协作 + RBAC
- Private module registry

### 6. Terraform 1.x 新特性

- `moved` 块：重构资源不删重建

  ```hcl
  moved {
    from = aws_instance.web
    to   = aws_instance.app_server
  }
  ```

- `import` 块（1.5+）：声明式导入

  ```hcl
  import {
    to = aws_instance.example
    id = "i-1234567890abcdef0"
  }
  ```

- `removed` 块（1.7+）：声明式删除

  ```hcl
  removed {
    from = aws_instance.old
  }
  ```

- `check` 块（1.5+）：声明断言

  ```hcl
  check "health" {
    data "http" "example" {
      url = "https://example.com"
    }
    assert {
      condition     = data.http.example.status_code == 200
      error_message = "Service unhealthy"
    }
  }
  ```

---

## 配套工具生态

| 工具 | 用途 |
|---|---|
| **Terragrunt** | 多环境 DRY、跨 stack 依赖管理 |
| **Atlantis** | PR 自动化 plan/apply |
| **Terraform Cloud / HCP** | 官方托管服务 |
| **tfsec / checkov / terrascan** | 静态安全扫描 |
| **tflint** | Linter |
| **terraform-docs** | 自动生成 module README |
| **pre-commit-terraform** | 提交前 fmt/validate/scan |
| **Pulumi** | 程序员友好的替代 |
| **Crossplane** | K8s 风格的 IaC |
| **Ansible** | Terraform 管基础设施，Ansible 管应用配置 |
| **Packer** | 镜像烘焙，常与 Terraform 配合 |

---

## 推荐学习路径

1. **入门**：跟着官方教程 `terraform.io` 跑一遍 AWS/GCP 基础
2. **进阶**：理解 state、依赖图、模块化、生命周期
3. **生产化**：Terragrunt / Atlantis / TFC / Sentinel / OIDC
4. **安全**：tfsec / checkov + IAM 最小权限 + OIDC 联邦
5. **扩展**：跨云、Kubernetes operator、Spectro Cloud / Cluster API

官方资源：

- <https://developer.hashicorp.com/terraform>
- <https://registry.terraform.io>
- <https://github.com/hashicorp/learn-terraform-fundamentals>
