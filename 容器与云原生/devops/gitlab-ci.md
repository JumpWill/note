
## CI/CD 概览

### 持续集成

考虑一个应用程序，它的代码存储在极狐GitLab 的 Git 存储库中。开发人员每天多次推送代码更改。对于每次推送到仓库，您可以创建一组脚本来自动构建和测试您的应用程序。这些脚本有助于减少您在应用程序中引入错误的机会。

这种做法称为持续集成。提交给应用程序的每个更改，甚至是开发分支，都会自动且连续地构建和测试。这些测试可确保更改通过您为应用程序建立的所有测试、指南和代码合规性标准。

### 持续交付

持续交付 是超越持续集成的一步。每次将代码更改推送到代码库时，不仅会构建和测试您的应用程序，还会持续部署应用程序。但是，对于持续交付，您需要手动触发部署。
持续交付会自动检查代码，但需要人工干预以手动和战略性地触发更改的部署

### 持续部署

持续部署是超越持续集成的又一步，类似于持续交付。不同之处在于，不是手动部署应用程序，而是将其设置为自动部署。不需要人工干预。

## Gitlab

### GitLab CI/CD 工作流

GitLab 中的远端仓库中的功能分支。 推送会触发项目的 CI/CD 流水线。然后，GitLab CI/CD：

- 运行自动化脚本（顺序或并行）：
  - 构建和测试您的应用程序。
  - 在 Review App 中预览更改，就像您在 localhost 上看到的一样。
- 实施后按预期工作：
  - 审核并批准您的代码。
  - 将功能分支合并到默认分支中。
    - GitLab CI/CD 将您的更改自动部署到生产环境。
如果出现问题，您可以回滚您的更改。
![工作流](./images/gitlab_workflow_example.png)

## gitlab-ci.yml 文件

要使用 GitLab CI/CD，您需要：

- 托管在 Git 仓库中的应用程序代码。
- 仓库根目录中名为 .gitlab-ci.yml 的文件，其中包含 CI/CD 配置。
  
在.gitlab-ci.yml文件中，您可以定义：

- 要运行的脚本。
- 要包含的其他配置文件和模板。
- 依赖项和缓存。
- 要按顺序运行的命令和要并行运行的命令。
- 将应用程序部署到的位置。
- 无论您是想自动运行脚本还是手动触发它们中的任何一个

可以定义不同的job执行不同的脚本，并且定义各个job之间执行逻辑和数据共享和存储。
举个例子

```yaml
# 定义各个阶段的名称
stages:
  - build
  - test
  - make_image
  - deploy
# 定义(stage)段的job以及执行的脚本内容
build-code-job:
  stage: build
  script:
    - echo "Check the ruby version, then build some Ruby project files:"
    - ruby -v
    - rake

test-code-job1:
  stage: test
  script:
    - echo "If the files are built successfully, test some files with one command:"
    - rake test1

test-code-job2:
  stage: test
  script:
    - echo "If the files are built successfully, test other files with a different command:"
```

### 关键字

#### 全局

| 名称 | 作用 |
| ------ | --------------- |
| default | 作业关键字的自定义默认值。 |
| stages |  流水线阶段的名称和顺序。|
| workflow | 控制运行的流水线类型。 |
| include | 从其他 YAML 文件导入配置 |

##### stages

通过stage定义不同的阶段，在job里指定stage为各个阶段添加任务，且阶段任务的执行顺序是从上而下的。
使用 stages 来定义包含作业组的阶段。stages 是为流水线全局定义的。在作业中使用 stage 来定义作业属于哪个阶段。
如果 .gitlab-ci.yml 文件中没有定义 stages，那么默认的流水线阶段是：

- .pre
- build
- test
- deploy
- .post
stages 项的顺序定义了作业的执行顺序：
- 同一阶段的作业并行运行。
- 下一阶段的作业在上一阶段的作业成功完成后运行

##### default

设置全局的一些配置，例如超时时间，任务执行前需要执行的脚本等。例如after_script
artifacts,before_script,cache,image,interruptible,retry,services,tags,timeout

##### include

使用 include 在 CI/CD 配置中包含外部 YAML 文件。 您可以将一个长的 .gitlab-ci.yml 文件拆分为多个文件以提高可读性，或减少同一配置在多个位置的重复。

您还可以将模板文件存储在中央仓库中并将它们包含在项目中。

include 文件：

- 与 .gitlab-ci.yml 文件中的那些合并。
- 无论 include 关键字的位置如何，始终先求值，然后与 .gitlab-ci.yml 文件的内容合并。

可以包含一个本仓库的文件，也可以包含其他仓库以及远端的文件.

###### local

使用 include:local 包含与 .gitlab-ci.yml 文件位于同一仓库中的文件。 使用 include:local 代替符号链接。
配置该文件需要是绝对路径。
details:

- .gitlab-ci.yml 文件和本地文件必须在同一个分支上。
- 不能通过 Git 子模块路径包含本地文件。

```yaml
include: 
  - local: '/templates/.gitlab-ci-template.yml'

```

###### file

要在同一个实例上包含来自另一个私有项目的文件，请使用 include:file。 您只能将 include:file 与 include:project 结合使用。

details:

- 包含来自另一个私有项目的 YAML 文件时，运行流水线的用户必须是这两个项目的成员并且具有运行流水线的适当权限。如果用户无权访问任何包含的文件，则可能会显示 not found or access denied 错误。

```yaml
include:
  - project: 'my-group/my-project'
    ref: main
    file:
      - '/templates/.builds.yml'
      - '/templates/.tests.yml'
```

###### remote

使用带有完整 URL 的 include:remote 来包含来自不同位置的文件。

details：

- 包含远端 CI/CD 配置文件时要小心。当外部 CI/CD 配置文件更改时，不会触发任何流水线或通知。从安全角度来看，这类似于拉取第三方依赖项。

```yaml
include:
  - remote: 'https://gitlab.com/example-project/-/raw/main/.gitlab-ci.yml'
```

###### template

导入模版文件

```yaml
include:
  - template: Android-Fastlane.gitlab-ci.yml
  - template: Auto-DevOps.gitlab-ci.yml
```

##### default

设置全局默认值。 未定义一个或多个所列关键字的作业使用在 default: 部分中定义的值。

| 关键字 | 描述  |
|-------|-------|
| artifacts| 成功时附加到作业的文件和目录列表。|
| before_script/after_script | 执行前后的脚本(已废弃)｜
| cache | 应在后续运行之间缓存的文件列表(已废弃)。 |
| image | 任务执行的镜像(已废弃) |
| interruptible |定义当新运行使作业变得多余时，是否可以取消作业。 |
| retry | 在失败的情况下可以自动重试作业的时间和次数。|
| services| 使用 Docker 服务镜像(已废弃)。 |
| tags| 用于选择 runner 的标签列表。|
| timeout| 定义优先于项目范围设置的自定义作业级别超时。|

```yaml
default:
  # 作业前后需要执行的shell
  before_script:
    - echo "this is before."
  after_script:
    - echo "this is after."
  # 执行作业的镜像
  image: bitnami/python:latest
  # runner的tag需要为dev-k8s
  tags: dev-k8s
  # 超时时间为3600
  timeout: 3600
  retry: 2

  # 禁止中止
  interruptible: true
  # todo 不是太懂
  services:
  - name: my-postgres:11.7
    alias: db-postgres
    entrypoint: ["/usr/local/bin/db-postgres"]
    command: ["start"]

  # 收集产物,收集binaries下的产物,但是排除**/*.o
  artifacts:
    paths:
      - binaries/
    exclude:
      - binaries/**/*.o
```

##### workflow

workflow用于限制流水线触发的条件。例如提交了代码不执行而是合并代码。
与rules/if/when同时使用.

```yaml
# 如果commit message中含有里draft就不执行,push操作就会执行。
workflow:
  rules:
    - if: $CI_COMMIT_MESSAGE =~ /draft$/
      when: never
    - if: $CI_PIPELINE_SOURCE == "push"
```

#### 作业关键字

##### image

使用 image 指定运行作业的 Docker 镜像。

##### pull_policy

拉取策略

details:

- 如果 runner 不支持定义的拉取策略，则作业将失败并出现类似以下错误：ERROR: Job failed (system failure): the configured PullPolicies ([always]) are not allowed by AllowedPullPolicies ([never])。

##### entrypoint

作为容器入口点执行的命令或脚本。

##### script

使用 script 指定 runner 要执行的命令。

##### stage

使用 stage 定义作业在哪个 stage 中运行。同一个 stage 中的作业可以并行执行（参见 额外细节）。
如果没有定义 stage，则作业默认使用 test 阶段。

##### extends

继承,则是可以继承其他的job的东西.

##### tags

指定runner。

##### allow_failure

使用 allow_failure 来确定当作业失败时，流水线是否应该继续运行。

- 要让流水线继续运行后续作业，请使用 allow_failure: true。
- 要停止流水线运行后续作业，请使用 allow_failure: false。

allow_failure 的默认值为：

- 手动作业为 true。
- 对于在 rules 中使用 when:manual 的作业为 false。
- 在所有其它情况下为 false

##### when

使用 when 配置作业运行的条件。如果未在作业中定义，则默认值为 when: on_success。

可能的输入：

- on_success（默认）：仅当早期阶段的所有作业都成功或具有 allow_failure: true 时才运行作业。
- manual：仅在手动触发时运行作业。
- always：无论早期阶段的作业状态如何，都运行作业。也可以在 workflow:rules 中使用。
- on_failure：只有在早期阶段至少有一个作业失败时才运行作业。
- delayed：作业的执行延迟指定的持续时间。
- never：不要运行作业。只能在 rules 部分或 workflow: rules 中使用。

details:

- 在 13.5 及更高版本中，您可以在与 trigger 相同的作业中使用 when:manual。在 13.4 及更早版本中，将它们一起使用会导致错误 jobs:#{job-name} when should be on_success, on_failure or always。
- allow_failure 的默认行为通过 when: manual 更改为 true。但是，如果您将 when: manual 与 rules 一起使用，allow_failure 默认为 false。

```yaml
stages:
  - build
  - cleanup_build
  - test
  - deploy
  - cleanup

build_job:
  stage: build
  script:
    - make build

# 失败的时候执行
cleanup_build_job:
  stage: cleanup_build
  script:
    - cleanup build when failed
  when: on_failure

test_job:
  stage: test
  script:
    - make test

# 手动部署
deploy_job:
  stage: deploy
  script:
    - make deploy
  when: manual
  environment: production

# 总是清除
cleanup_job:
  stage: cleanup
  script:
    - cleanup after jobs
  when: always
```

##### rules

使用 rules 来包含或排除流水线中的作业。
创建流水线时会评估规则，并按顺序评估，直到第一次匹配。找到匹配项后，该作业将包含在流水线中或从流水线中排除，具体取决于配置。
rules 替换了 only/except，并且它们不能在同一个作业中一起使用。如果您将一个作业配置为使用两个关键字，则系统会返回一个 key may not used with rules 错误。
rules 不能与only/except 同时使用。

rules 会与下面关键字一同使用：

- if
- changes
- exists
- allow_failure
- variables
- when

作业不会被添加:

- 如果没有规则匹配。
- 如果规则匹配并且有 when: never

作业被添加到流水线中：

- 如果 if、changes 或 exists 规则匹配并且还具有 when: on_success（默认）、when: delay 或 when: always。
- 如果达到的规则只有 when: on_success、when: delay 或 when: always。

###### if

使用 rules:if 子句指定何时向流水线添加作业：

- 如果 if 语句为 true，则将作业添加到管流水线中
- 如果 if 语句为 true，但它与 when: never 结合使用，则不要将作业添加到流水线中。
- 如果没有 if 语句为 true，则不要将作业添加到流水线中。

details:

- 如果规则匹配并且没有定义 when，则规则使用为作业定义的 when，如果未定义，则默认为 on_success。
- =~ 和 !~ 表达式右侧的变量被认为是正则表达式。

```yaml
job:
  script: echo "Hello, Rules!"
  rules:
    # 如果源分支有feature且合并的目标分支不为 $CI_DEFAULT_BRANCH 不执行
    - if: $CI_MERGE_REQUEST_SOURCE_BRANCH_NAME =~ /^feature/ && $CI_MERGE_REQUEST_TARGET_BRANCH_NAME != $CI_DEFAULT_BRANCH
      when: never
    # 如果源分支有feature 手动执行允许失败
    - if: $CI_MERGE_REQUEST_SOURCE_BRANCH_NAME =~ /^feature/
      when: manual
      allow_failure: true
    # 默认成功
    - if: $CI_MERGE_REQUEST_SOURCE_BRANCH_NAME
```

###### exists

当仓库中存在某些文件时，使用 exists 来运行作业.

details:

- 如果找到任何列出的文件，exists 解析为 true（OR 操作）

```yaml
job:
  script: docker build -t my-image:$CI_COMMIT_REF_SLUG .
  rules:
    - exists:
        - Dockerfile
        - xxxx
```

###### allow_failure

使用 allow_failure: true 允许作业在不停止流水线的情况下失败。

###### changes

使用 rules:changes 通过检查对特定文件的更改来指定何时将作业添加到流水线。

```yaml
docker build:
  script: docker build -t my-image:$CI_COMMIT_REF_SLUG .
  rules:
    - if: '$CI_PIPELINE_SOURCE == "merge_request_event"'
      changes:
        - Dockerfile
        - xxx
      when: manual
      allow_failure: true
```

##### cache

用于不同jod之间的文件共享,比如在前面的任务出了产物，让后续的job进行使用.
且由于不同的job 可能都会产生缓存，所以可以为不同的缓存生成不同的key,避免缓存被覆盖.

指定files可以是当该文件的发生变化(md5值发生变化)，
那么就会触发缓存，将paths中定义路径下的内容进行缓存,且可以为生成的缓存加上prefix以区分不同的缓存.

```yaml
build:
  script:
    - echo "This job uses a cache."
  cache:
    key: build-cache
     files:
       - package.json
      prefix: build
    paths:
      - tar/*.apk
      - .config
```
