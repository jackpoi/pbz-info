# 第三方组件

## native/pbz_codec.dll

- 名称：oozextract（Oodle Kraken 解码器）
- 版本：0.5.7（见 `native/manifest.json`）
- 来源：https://github.com/qry6868/PBZ-Editor 的构建产物
- 许可：MIT
- 用途：解压游戏存档里的 Oodle Kraken 压缩块

本程序不包含 Epic 的 `oo2core_*.dll`，也不依赖任何游戏资源文件。

运行时会对该 DLL 做 sha256 校验（`native/manifest.json`），校验失败即拒绝加载。

## Python 依赖

- `cryptography`（AES-256-GCM 解密）— Apache-2.0 / BSD
- `pywebview`（窗口与 JS 桥）— BSD-3-Clause（待 M2 引入）
- `PyInstaller`（打包，仅构建期）— GPL with exception

## 游戏数据

本程序不打包、不修改、不上传任何游戏资源或存档内容；所有数值均在用户本机实时读取。
