# Buckshot Rouletter

这是一个独立的蟒蛇工具（外设）。工具会生成一份临时派生 Godot PCK，在《Buckshot Roulette》脚本内启动仅绑定 `127.0.0.1` 的状态读取桥接，再由蟒蛇求解器（决策树（if:if:if:if:if:if:if:if:if:if:if:if:if:if:if:if:if:if:if:if:if:if:if:if:if:if:if:if:if:if:if:if:if:if:if:if:if:if:if:if:if:if:if:if:if:if:if:if:if:if:if:if:if:if:if:if:if:if:if:if:if:if:if:if:if:if:if:if:if:if:if:if:if:if:if:if:if:if:if:if:if:if:if:if:if:if:if:if:if:if:if:if:if:if:if:if:））读取真实运行时数据并计算建议，将下一步建议显示在游戏左上角的 HUD 中。HUD 使用白色直角边框，可拖动右下角手柄调整大小。

桥接只传剩余实弹数、空弹数，以及玩家是否已用放大镜确认当前弹；不传弹膛排列。求解器把未知弹序视为随机洗牌，按剩余数量不放回抽样，并按双方最优应对最大化玩家期望胜率。支持手锯、香烟、啤酒、手铐、反转器、放大镜、过期药和肾上腺素偷取；未知当前弹被反转时，按实弹/空弹数量计算后续概率，不窥视实际弹序。burner phone 等未建模道具会列出提示。弹膛耗尽仍未分胜负时，以双方剩余生命占比估算续局。

## 使用

需要 Python、Steam 客户端，以及默认路径下的游戏：

`C:\Program Files (x86)\Steam\steamapps\common\Buckshot Roulette\Buckshot Roulette_windows\Buckshot Roulette.exe`

先正常退出当前运行中的游戏，再双击 `run.bat`。首次启动会在 `%TEMP%\BuckshotRouletteAssistant` 生成约 740 MB 的临时资源包并通过 Steam 启动游戏；原始 Steam EXE/PCK 不会被修改。之后运行会复用缓存包。

也可以在 PowerShell 中运行：

```powershell
python assistant.py
```

其他 Steam 库可传入完整 EXE 路径：

```powershell
python assistant.py --game-exe 'D:\SteamLibrary\steamapps\common\Buckshot Roulette\Buckshot Roulette_windows\Buckshot Roulette.exe'
```

若当前已有未插桩的游戏进程，工具会提示先正常退出，不会关闭该进程。工具只给出建议，不会自动点击或操作游戏。

## 校验

```powershell
python -m unittest discover -s tests -v
```

清理临时派生包可删除 `%TEMP%\BuckshotRouletteAssistant`。
