# 第三方组件

本程序自身以 MIT 许可发布，见 [`LICENSE`](LICENSE)。下列组件按各自许可分发。

## native/pbz_codec.dll

`native/pbz_codec.dll` 是随程序分发的二进制解码器，包含：

| 组件 | 上游 | 许可 |
|---|---|---|
| oozextract 0.5.7 | https://github.com/lvlvllvlvllvlvl/oozextract | MIT |
| C ABI 封装 | https://github.com/qry6868/PBZ-Editor | MIT，Copyright (c) 2026 PBZ Editor contributors |

- 该 DLL 与 PBZ-Editor v0.3.0 发布包中的 `pbz_codec.dll` 字节一致，SHA-256 为 `cc98ce6cfe62d23cdaeaa350a5a011984e03582fb54ad466b970e741b721e179`（见 [`native/manifest.json`](native/manifest.json)）。
- DLL 静态链接的 Rust 依赖（bytemuck、bytes、futures、log、memchr、safe_arch、wide 等）多为 MIT / Apache-2.0 / Zlib 许可；各 crate 的版本与许可可从 PBZ-Editor v0.3.0 发布包中的 `LICENSES/native/` 取得。
- oozextract 上游只在 `Cargo.toml` 中声明 `license = "MIT"`，仓库没有单独发布 `LICENSE` 文件或版权行；此处保留上游链接作为归属说明。

本程序不包含 Epic 的 `oo2core_*.dll`，也不依赖任何游戏资源文件。运行时会对该 DLL 做 SHA-256 校验（`native/manifest.json`），校验失败即拒绝加载。

## Python / 运行时依赖

| 组件 | 许可 |
|---|---|
| Python | PSF-2.0 |
| cryptography | Apache-2.0 OR BSD-3-Clause |
| cffi | MIT-0 |
| pycparser | BSD-3-Clause |
| pywebview | BSD-3-Clause，Copyright (c) 2014-2017 Roman Sirokov |
| pythonnet | MIT |
| clr-loader | MIT，Copyright (c) 2019-2026 Benedikt Reinartz |
| bottle | MIT |
| proxy_tools | MIT |
| typing_extensions | PSF-2.0 |

pywebview、pythonnet、clr-loader 是 Windows 上创建窗口与 JS 桥所必需的运行时依赖；bottle、proxy_tools 由 pywebview 间接引入。

## 构建期依赖（不随程序分发）

| 组件 | 许可 |
|---|---|
| PyInstaller | GPL-2.0-or-later，含允许分发非自由程序的 bootloader 例外 |
| pytest | MIT |
| Pillow | MIT-CMU |

## 游戏数据

本程序不打包、不修改、不上传任何游戏资源或存档内容；所有数值均在用户本机实时读取。
