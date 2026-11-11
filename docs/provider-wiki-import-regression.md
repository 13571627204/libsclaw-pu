# 模型配置与 Wiki 重复导入修复验收

日期：2026-11-02。

## 修复范围与原因

- 模型加载直接读取 `type`。本机 `imget/gemini-3-pro-image-preview` 引用的
  `imget` 来源已不存在，无法继承适配器类型，导致 `KeyError: 'type'`。
  现在加载前校验并给出可操作的警告，跳过无效模型、继续加载其他模型。
  空类型可以继承有效来源；新增、更新、重载前也校验，避免再次保存这类无效配置。
  校验失败的重载不会先终止正常运行的模型。
- Wiki 默认不覆盖时，将同名文件作为异常抛出。本机蓝皮书错误发生于后台导入任务，
  并非服务启动失败。现在后台默认跳过已有同路径页面并返回 `reason: exists`；
  混合批次继续导入新页面，全跳过也正常完成且不重建索引。
  显式勾选覆盖时才替换内容，保持文档 ID。
- 图片识别模块的 `PharmaTranslatorError` 中状态码赋值不完整，导致校验错误
  变成 `AttributeError`。恢复 `self.status_code = status_code`，保留原有校验边界。

本次未修改本机提供商配置、密钥或默认模型，未覆盖或删除已有蓝皮书。
底层 Wiki 接口仍默认严格拒绝重名；只有显式传入 `skip_existing=True` 的调用启用跳过。
路径穿越、符号链接、大小写冲突及批次内重复路径仍不能绕过验证。

## 生效与操作步骤

1. 完成正在进行的任务，在当前开发服务窗口按 `Ctrl+C` 停止服务。
2. 在仓库根目录运行 `.\dev.cmd`，只启动一份开发服务，再刷新浏览器。
   本次代码修改未自动重启正在运行的服务。
3. 在模型配置页检查 `imget/gemini-3-pro-image-preview`：重新选择实际可用的
   提供商来源，或禁用不用的模型。不要随意填入猜测的适配器类型。
   当前默认模型 ID `kimi-code/kimi-k2.6` 也不在已配置模型列表中，
   请按实际业务需要重新选择；本次未擅自替换。
4. 在知识库 Wiki 导入界面重新选择蓝皮书，保持“覆盖”不勾选。
   应显示“导入 0 个页面，跳过 1 个文件”，展开可见“同路径页面已存在，保留原内容”。
5. 如确实需要更新蓝皮书，先核对上传内容，再勾选覆盖重新导入。

## 验收场景

| 场景 | 预期 |
| --- | --- |
| 启动时模型来源缺失或类型缺失 | 清楚警告并跳过该模型，不再出现此 `KeyError`，其他模型继续加载 |
| 有效来源 + 空白模型类型 | 从来源继承类型，输入配置不被修改 |
| 保存或重载无效配置 | 拒绝保存；不终止原有正常实例 |
| 单独重复导入蓝皮书 | 正常完成；原文件字节、文档 ID 和索引保持不变 |
| 同批已有页面 + 新页面 | 分别显示跳过和导入数量；仅写入新页面 |
| 同时提交两次相同导入 | 一次导入、另一次跳过，不重复创建页面 |
| 显式覆盖 | 内容更新，文档 ID 不变 |
| 路径大小写冲突或恶意路径 | 仍拒绝，不因跳过策略放宽安全检查 |
| 图片格式错误或关键字段未确认 | 返回原有业务校验错误，不再抛出状态码属性异常 |

## 自动回归命令

在仓库根目录执行（Provider 测试先加载 API，兼容项目现有导入顺序）：

```powershell
.venv\Scripts\python.exe -m pytest tests/test_provider_config_validation.py tests/unit/test_wiki_store.py tests/unit/test_knowledge_base_service_contract.py tests/test_pharma_translator.py -q
.venv\Scripts\python.exe -m ruff check astrbot/core/provider/manager.py astrbot/core/knowledge_base/wiki.py astrbot/core/knowledge_base/kb_helper.py astrbot/dashboard/services/knowledge_base_service.py astrbot/dashboard/services/pharma_translator_service.py
git diff --check
```

在 `dashboard` 目录执行：

```powershell
node --test tests/wikiImportResult.test.mjs
node_modules\.bin\vue-tsc.cmd --noEmit
```

测试使用隔离临时目录和本地替身，不向真实提供商发请求，不覆盖实际知识库。

## 本次验证结果

- 上述后端定向回归：121 项通过。
- Wiki 导入前端回归：5 项通过；Vue TypeScript 类型检查通过。
- 修改涉及的 Python 文件 Ruff 检查、格式检查和 Git diff 空白检查通过。
- 实际本机配置只读校验：4 个模型有效、1 个模型来源缺失；未启动提供商或保存配置。
- 额外全前端测试运行：68 项通过、2 项 PersonaForm 可见性测试失败。
  该模块未在本次修改，不能将全量前端测试报告为全部通过。
- 未重启运行中的服务，也未使用真实蓝皮书执行覆盖导入；人工界面验收需重启后按上表完成。
