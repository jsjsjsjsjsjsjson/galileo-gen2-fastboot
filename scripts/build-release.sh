#!/usr/bin/env bash
set -euo pipefail

project_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
edk_dir="$project_dir/work/udk2014-sp1-r16182"
edk_tools="$project_dir/work/edk2/BaseTools"
grub_build="$project_dir/work/grub-build-i386-efi-local"
fv_dir="$edk_dir/Build/QuarkPlatform/RELEASE_GCCNOLTO/FV"

mkdir -p "$project_dir/logs" \
  "$project_dir/artifacts/update-media/EFI/BOOT" \
  "$project_dir/artifacts/update-media/boot/grub"

export WORKSPACE="$edk_dir"
export EDK_TOOLS_PATH="$edk_tools"
export PYTHON_COMMAND=python3
export PYTHONPATH="$edk_tools/Source/Python"
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:$edk_tools/BinWrappers/PosixLike:$edk_tools/Source/C/bin"

edk_build=(
  build -p QuarkPlatformPkg/QuarkPlatformPkg.dsc
  -b RELEASE -a IA32 -t GCCNOLTO -n "$(nproc)"
  -DDEBUG_PRINT_ERROR_LEVEL=0x80000000
  -DDEBUG_PROPERTY_MASK=0x23
)

cd "$edk_dir"
"${edk_build[@]}" > "$project_dir/logs/edk-release-pass1.log" 2>&1
python3 QuarkPlatformPkg/Tools/QuarkSpiFixup/QuarkSpiFixup.py \
  QuarkPlatform RELEASE GCCNOLTO
"${edk_build[@]}" > "$project_dir/logs/edk-release-pass2.log" 2>&1

rm -rf "$project_dir/firmware/FV/FlashModules"
mkdir -p "$project_dir/firmware/FV/FlashModules" "$project_dir/firmware/FV/Tools"
cp -a "$fv_dir/FlashModules/." "$project_dir/firmware/FV/FlashModules/"

make -C QuarkPlatformPkg/Tools/CapsuleCreate -f GNUmakefile
cp -a QuarkPlatformPkg/Tools/CapsuleCreate/CapsuleCreate \
  "$project_dir/firmware/FV/Tools/CapsuleCreate"

grub_modules=(
  normal configfile linux multiboot search search_fs_file part_gpt part_msdos fat ext2
  efifwsetup reboot halt echo test loadenv regexp probe ls cat sleep help chain
)
"$grub_build/grub-mkimage" -O i386-efi \
  -d "$grub_build/grub-core" -p /boot/grub \
  -c "$project_dir/grub/embedded.cfg" \
  -o "$project_dir/artifacts/grub-2.14-galileo-gen2.efi" \
  "${grub_modules[@]}"
cp -a "$project_dir/artifacts/grub-2.14-galileo-gen2.efi" \
  "$project_dir/firmware/grub-2.14-galileo-gen2.efi"

make -C "$project_dir/flash" clean \
  BASETOOLS="$edk_tools/Source/C/bin"
make -C "$project_dir/flash" raw capsule \
  BASETOOLS="$edk_tools/Source/C/bin"

cp -a "$project_dir/flash/Flash.cap" \
  "$project_dir/artifacts/galileo-gen2-grub-2.14-fastboot-plain.cap"
cp -a "$project_dir/flash/Flash-missingPDAT.bin" \
  "$project_dir/artifacts/galileo-gen2-grub-2.14-fastboot-missing-pdat.bin"
cp -a "$project_dir/flash/image_info.txt" \
  "$project_dir/flash/CapsuleComponents.ini" "$project_dir/artifacts/"
cp -a "$edk_dir/Build/QuarkPlatform/RELEASE_GCCNOLTO/IA32/CapsuleApp.efi" \
  "$project_dir/artifacts/update-media/"
cp -a "$edk_dir/EdkShellBinPkg/FullShell/Ia32/Shell_Full.efi" \
  "$project_dir/artifacts/update-media/EFI/BOOT/BOOTIA32.EFI"
cp -a "$project_dir/config/update-grub.cfg" \
  "$project_dir/artifacts/update-media/EFI/BOOT/grub.cfg"
cp -a "$project_dir/config/update-grub.cfg" \
  "$project_dir/artifacts/update-media/boot/grub/grub.cfg"
cp -a "$project_dir/artifacts/galileo-gen2-grub-2.14-fastboot-plain.cap" \
  "$project_dir/artifacts/update-media/Flash.cap"

python3 "$project_dir/scripts/validate-release.py"

cd "$project_dir"
sha256sum \
  artifacts/galileo-gen2-grub-2.14-fastboot-plain.cap \
  artifacts/galileo-gen2-grub-2.14-fastboot-missing-pdat.bin \
  artifacts/grub-2.14-galileo-gen2.efi > artifacts/SHA256SUMS
cd "$project_dir/artifacts/update-media"
sha256sum CapsuleApp.efi EFI/BOOT/BOOTIA32.EFI EFI/BOOT/grub.cfg \
  boot/grub/grub.cfg Flash.cap \
  > SHA256SUMS
