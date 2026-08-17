#!/usr/bin/env bash
set -euo pipefail

project_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
grub_src="$project_dir/work/grub-2.14"
grub_build="$project_dir/work/grub-build-i386-efi-local"

mkdir -p "$grub_build"

if [[ ! -x "$grub_build/grub-mkimage" ]]; then
  cd "$grub_build"
  TARGET_CFLAGS="-Os -ffile-prefix-map=$grub_src/=" \
    "$grub_src/configure" \
      --target=i386 \
      --with-platform=efi \
      --disable-werror
fi

make -C "$grub_build" -j"$(nproc)"
