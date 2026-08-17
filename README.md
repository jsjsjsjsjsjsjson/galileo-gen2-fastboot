# Galileo Gen 2 Fastboot

面向 Intel Galileo Gen 2 的 UEFI 固件构建项目，基于 Intel Quark BSP 1.1.0 和
UDK2014.SP1，使用 GRUB 2.14 从 USB 或 microSD 启动 Linux。

项目缩短固件和引导器的启动等待，改善串口终端兼容性，并提供适配现代构建工具的补丁。
适用于配备 8 MiB SPI flash 的 Galileo Gen 2 PLAIN（非安全）开发板。

## 功能

- 将 SPI flash 内的 GRUB 更新到 2.14，支持 Linux、Multiboot 和 UEFI chainloading。
- 移除 SPI 内置的 Linux kernel、ramdisk 和旧版 `grub.conf`，从外部介质加载系统。
- 将 UEFI 启动倒计时设为零，默认 Linux 配置也使用零秒等待。
- 改善 UTF-8 串口输出及 xterm 功能键兼容性，缩短单独按下 Esc 时的等待。
- 适配现代 GCC、Python 3、OpenSSL 3 和 EDK II BaseTools。

## 构建

### 环境准备

使用支持 IA32 交叉构建的 Linux 主机。如果你是 Debian，可以参考下面的命令：

```sh
sudo apt install git curl perl xz-utils build-essential gcc-multilib \
  uuid-dev acpica-tools nasm autoconf automake autopoint bison flex \
  gettext libssl-dev python3
```

另需准备 Intel Quark BSP 1.1.0 中的 `Quark_EDKII_v1.1.0` 源码目录，包含
`QuarkPlatformPkg`、`QuarkSocPkg` 和 `IA32FamilyCpuBasePkg`。这些 BSP 源码不随本仓库提供。
你需要自行下载 EDK II 和 GRUB。

### 执行构建

```sh
git https://github.com/jsjsjsjsjsjsjson/galileo-gen2-fastboot.git
cd galileo-gen2-fastboot

./scripts/prepare-sources.sh /path/to/Quark_EDKII_v1.1.0
./scripts/build-grub.sh
./scripts/build-release.sh
```

如果 BSP 位于以下相邻目录，可省略 `prepare-sources.sh` 的参数：

```text
../Board_Support_Package_Sources_for_Intel_Quark_v1.1.0/Quark_EDKII_v1.1.0
```

脚本会准备固定版本的 UDK2014、BaseTools、FatPkg 和 GRUB，应用补丁，然后生成固件和
更新介质。源码及构建目录位于 `work/`，UEFI 构建日志位于 `logs/`。

### 构建产物

| 路径（相对于 `artifacts/`） | 用途 |
| --- | --- |
| `galileo-gen2-grub-2.14-fastboot-plain.cap` | UEFI 固件更新 capsule |
| `update-media/` | 可复制到 FAT32 介质的 UEFI Shell、更新工具、菜单和 capsule |
| `grub-2.14-galileo-gen2.efi` | IA32 UEFI GRUB 镜像 |
| `galileo-gen2-grub-2.14-fastboot-missing-pdat.bin` | 8 MiB SPI 布局验证镜像，缺少板级 PDAT |
| `CapsuleComponents.ini`、`image_info.txt` | Capsule 组件及镜像布局信息 |
| `SHA256SUMS` | 构建产物校验和 |

验证包括 IA32 PE 格式、capsule 组件及地址、SPI 镜像大小，以及内置 kernel、ramdisk 和
旧配置的移除情况。Capsule 签名使用随机 salt，重复构建的哈希可能不同。

## 更新固件

**刷写前务必备份整个 SPI flash，并准备外置编程器用于恢复。**

此构建使用 BSP 的开发样例密钥，面向 PLAIN／非安全开发板。已启用安全 SKU 或 fuse 的
板子不适用。`missing-pdat.bin` 缺少板级参数，**不可直接用于整片编程**。

1. 将 `artifacts/update-media/` 下的全部内容复制到 FAT32 USB 或 microSD 的根目录。
2. 进入 UEFI Shell。已运行本项目固件时，可通过介质上的 GRUB 更新菜单选择
   `Start UEFI shell for Galileo firmware update`；首次安装需从现有固件启动该介质的
   `EFI/BOOT/BOOTIA32.EFI`。
3. 在 Shell 中刷新设备映射，切换到更新介质所在的文件系统，再执行更新：

   ```text
   map -r
   fs0:
   CapsuleApp.efi Flash.cap
   ```

   `fs0:` 仅为示例，请根据映射结果选择实际包含 `Flash.cap` 的文件系统。

4. 等待更新完成并自动重启，期间保持供电。

Capsule 不覆盖 PDAT、signed-key-module 和 SVN area，保留板上原有的 MRC 参数、MAC
地址和安全状态；NVRAM 会更新为本构建的默认值。

## 配置 Linux 启动介质

内嵌 GRUB 将搜索外部介质上的 `/boot/grub/grub.cfg`。将
[`config/removable-grub.cfg.example`](config/removable-grub.cfg.example) 复制到该路径，
并按实际系统修改内核、initramfs 路径及根文件系统参数。

示例目录布局：

```text
boot/
├── grub/
│   └── grub.cfg
├── vmlinuz
└── initramfs.img
```

默认配置直接启动第一项。找不到配置时，GRUB 会进入命令行；可执行 `help` 查看命令，
或用 `fwsetup` 进入 UEFI 设置。UEFI 的 F7 按键窗口较短，需要提前按住。

更新介质使用交互式菜单。完成固件更新后，将介质上的 `/boot/grub/grub.cfg` 替换为
Linux 启动配置，再放入内核及 initramfs。

## 许可

本仓库包含 Intel BSP 相关工具和补丁，请保留各文件的版权及许可声明。
Flash 工具的许可见 [`flash/LICENSE`](flash/LICENSE)；EDK II、GRUB 和外部 BSP 源码
分别遵循其上游许可。
