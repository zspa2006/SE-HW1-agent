# 代码解释 Agent

作者：潘彦博（学号：2404080334）

本项目为软件项目管理课程 Homework 1 的代码解释 Agent。用户提出与代码文件有关的问题后，Agent 调用 `read_file` 读取项目内的文件，再根据文件内容生成带行号的中文解释。程序通过命令行交互，支持连续追问。

## 功能

- 解释文件的整体作用、函数逻辑和指定代码行。
- 通过 Function Calling 调用本地文件读取工具，并显示调用过程。
- 保存最近 6 轮问答和上次读取的文件路径，支持连续追问。
- 拒绝读取项目目录外的路径、二进制文件及超过 32,000 字节的文件。
- 对文件错误和模型请求失败给出提示；API 客户端最多重试 2 次。

## 1. 安装

需要 Python 3.10 或更新版本，以及一个支持 Chat Completions 工具调用的模型 API。在项目根目录打开 PowerShell 并安装依赖：

```powershell
python -m pip install -r requirements.txt
```

## 2. 配置模型

密钥、接口地址和模型名均通过环境变量配置。切换服务商时，应同时更换这三项配置。

### DeepSeek

推荐先用 `deepseek-flash`。也可将模型名改为 `deepseek-v4-pro`。程序连接 DeepSeek 官方接口时会使用非思考模式，以适配当前的对话记录方式。

```powershell
$secureKey = Read-Host "请输入 DeepSeek API Key" -AsSecureString
$env:CODE_AGENT_API_KEY = [System.Net.NetworkCredential]::new("", $secureKey).Password
$env:CODE_AGENT_BASE_URL = "https://api.deepseek.com"
$env:CODE_AGENT_MODEL = "deepseek-flash"
```

DeepSeek 当前的模型名和工具调用方式见[聊天接口文档](https://api-docs.deepseek.com/api/create-chat-completion/)和[工具调用说明](https://api-docs.deepseek.com/guides/tool_calls/)。请使用当前文档中的模型名；`deepseek-chat` 和 `deepseek-reasoner` 已被列为旧名称。

### 阿里云百炼（通义千问）

下面以北京地域为例。API Key 和接口地址必须属于同一地域；其他地域请使用控制台给出的地址。

```powershell
$secureKey = Read-Host "请输入百炼 API Key" -AsSecureString
$env:CODE_AGENT_API_KEY = [System.Net.NetworkCredential]::new("", $secureKey).Password
$env:CODE_AGENT_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
$env:CODE_AGENT_MODEL = "qwen-plus"
```

可选的工具调用模型包括 `qwen-flash` 和 `qwen3-coder-plus`；以[百炼模型列表](https://help.aliyun.com/zh/model-studio/text-generation-model)及账号可用模型为准。

### OpenAI API

不设置自定义接口地址时，SDK 使用 OpenAI 官方接口。若之前设置过其他服务商地址，先清除它：

```powershell
$secureKey = Read-Host "请输入 OpenAI API Key" -AsSecureString
$env:CODE_AGENT_API_KEY = [System.Net.NetworkCredential]::new("", $secureKey).Password
Remove-Item Env:CODE_AGENT_BASE_URL -ErrorAction SilentlyContinue
$env:CODE_AGENT_MODEL = "gpt-4.1-mini"
```

也可选用支持 Chat Completions 工具调用的其他 OpenAI API 模型。API Key 不应写入项目文件、提交到仓库或公开展示；模型服务的使用费用以各服务商规则为准。

## 3. 运行

进入可连续提问的交互模式：

```powershell
python -m code_explain_agent --root .
```

看到 `你>` 后，可以依次输入：

```text
解释 examples/sample.py 的整体逻辑
total_price 函数如何计算折扣？
第 4 行有什么作用？
解释 examples/index.html 的页面结构
examples/style.css 如何设置表单布局？
```

输入 `/clear` 清除会话，输入 `/exit` 退出。只回答一个问题时，把问题写在同一行：

```powershell
python -m code_explain_agent --root . --question "解释 examples/sample.py 的整体逻辑"
```

`--root` 可指向其他代码项目。`--quiet` 可隐藏工具调用提示。

## 工作流程

1. 命令行接收问题，把最近的问答发送给模型。
2. 模型判断是否需要调用 `read_file`；涉及具体文件时，系统提示要求先读取。
3. 程序验证工具参数，只读取 `--root` 目录内的 UTF-8 文本，并返回带行号的内容。
4. 模型根据工具结果生成解释。更详细的架构与设计取舍见 [Design.md](Design.md)。

## 验证

运行单元测试无需 API Key。测试使用模拟模型和本地模拟接口，覆盖工具调用、请求格式、文件读取边界及 DeepSeek 配置：

```powershell
python -m unittest discover -s tests -v
```

`examples/` 包含 Python 示例和注册页面的 HTML/CSS，均作为代码解释功能的测试素材。Agent 仍通过命令行交互。文件不存在等错误情况会返回明确提示。

## 使用限制

- 程序只读取单个 UTF-8 文本文件，不执行或修改代码。
- 模型可能解释错误；重要结论应根据显示的文件内容和行号核对。
- DeepSeek 适配使用非思考模式，当前版本未传递思考模式所需的完整推理历史。
- 没有 API Key 或无法访问模型服务时，程序无法生成解释，但本地测试仍可运行。
