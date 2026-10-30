# 错误信息与退出码

退出码语义，以及常见后端、数据源、下载与参数错误的修复方法。

## 常见错误信息

### 退出码分别是什么含义？

自 0.2.0 起，退出码语义是稳定的，可以据此编写脚本判断：

| 退出码 | 含义 |
| --- | --- |
| `0` | 成功（包括未加 `--fail-on-error` 的 tgmlst 部分样本失败） |
| `1` | 运行时失败（包括 `scheme update` 中任一 provider 或方案失败） |
| `2` | 用法错误，例如非法参数，或 `scheme list --name` 传入非法正则 |
| `3` | tgmlst 输入阶段失败 |
| `4` | tgmlst 组装阶段失败 |
| `5` | tgmlst 预测阶段失败 |
| `6` | tgmlst 未知阶段失败 |

tgmlst 的阶段码从 3 开始编号，避免与 shell 标准的用法错误退出码 2 冲突。当多个样本在不同阶段失败时，退出码反映占多数的失败阶段。要使 tgmlst 的部分样本失败也返回非零，请加 `--fail-on-error`。

### `Unknown backend 'X'`

说明你请求的 backend 没有注册到 `gmlst/aligners/__init__.py`。可以先查看支持的后端名称：

```bash
gmlst typing mlst --help
gmlst utils check -b blastn
```

### `Unknown provider 'X'`

说明 provider 没有注册到 `gmlst/database/providers/__init__.py`。

可以先用下面的命令查看可用 provider：

```bash
gmlst scheme list
```

### `No typing result produced for input sample`

通常表示在组装出有效结果前就失败了。请重点检查输入格式、后端兼容性、方案是否可用，以及失败前的命令输出。

### `Failed to download` 相关错误

这类错误通常指向网络问题，或 provider 端问题。可以先换一个 `--download-tool` 重试，再确认远端地址是否能访问。

自 0.2.0 起，网络失败会先在 stderr 打印简洁的重试行（例如 `retry 1/3 [connection timeout] bigsdb.pasteur.fr — adk`），最终失败时错误信息带 `[network:<reason>]` 前缀，方便脚本按原因归类。

### `--verbose and --quiet cannot be used together`

这两个参数互斥，只能选一个：

```bash
gmlst --verbose scheme list
gmlst --quiet scheme list
```

## 在脚本中使用退出码

```bash
gmlst typing tgmlst sample.fna --fail-on-error
case $? in
  0) echo "ok" ;;
  2) echo "参数错误" ;;
  3|4|5|6) echo "tgmlst 阶段失败" ;;
  *) echo "运行时失败" ;;
esac
```

## 错误与修复对照

| 报错 | 修复 |
| --- | --- |
| `Unknown backend 'X'` | `gmlst typing mlst --help`，再用 `gmlst utils check -b <name>` |
| `Unknown provider 'X'` | `gmlst scheme list`；检查 `-p` 拼写 |
| `Scheme 'X' not found in catalog` | `gmlst scheme search <organism>` |
| `No typing result produced` | 用 `--format json --verbose` 重跑 |
| `Failed to download` | 换 `--download-tool curl` 重试，检查代理与限流 |
| `--verbose and --quiet` | 只保留其中一个参数 |

如果批处理中出现相同失败，单独对一条样本加 `--verbose` 重跑，避免警告相互穿插。
