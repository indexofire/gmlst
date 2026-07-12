# bugs

1. gmlst scheme download命令使用python下载工具，默认的并发数可能会导致网站nginx返回失败，需要重设并发数，并对下载文件是否是fasta，以及完整性进行验证，如果失败需要重新下载。
2. gmlst新建命令，用于环境变量的设置。gmlst config env打印所有环境变量，gmlst config set 设置具体的值，gmlst config show 显示config配置理解信息
3. gmlst scheme search命令用来搜索scheme，用来代替list命令
4. gmlst scheme list 实现更好的高亮显示已下载scheme, 表格显示效果。
5. gmlst scheme download/update/remove/show等直接操作scheme的命令，是否直接用scheme name 而不用-s 参数

下载mlst数据库，当too many request下载失败后，重新下载的文件不会覆盖原文件。导致profile失败。要限制并发连接数，同时要删除失败文件，或用完成文件去覆盖