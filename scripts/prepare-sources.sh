#!/usr/bin/env bash
set -euo pipefail

project_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
work_dir="$project_dir/work"
bsp_edk=${1:-"$project_dir/../Board_Support_Package_Sources_for_Intel_Quark_v1.1.0/Quark_EDKII_v1.1.0"}
udk_dir="$work_dir/udk2014-sp1-r16182"
tools_dir="$work_dir/edk2"
fat_dir="$work_dir/edk2-FatPkg"
grub_dir="$work_dir/grub-2.14"

udk_commit=160b825f67cf77d2b85eaae3915fa1ecced82df0
tools_commit=b03a21a63e3bd001f52c527e5a57feddb53a690b
fat_commit=278d45c7f6c05cc3443126964677d21bf9e2ee30

if [[ ! -d "$bsp_edk/QuarkPlatformPkg" ]]; then
  echo "BSP EDK source not found: $bsp_edk" >&2
  echo "Pass Quark_EDKII_v1.1.0 as the first argument." >&2
  exit 1
fi

mkdir -p "$work_dir"

clone_at_commit() {
  local destination=$1
  local commit=$2
  if [[ ! -d "$destination/.git" ]]; then
    git clone --filter=blob:none --no-checkout \
      https://github.com/tianocore/edk2.git "$destination"
    git -C "$destination" checkout "$commit"
  fi
}

apply_once() {
  local tree=$1
  local patch_file=$2
  if git -C "$tree" apply --check "$patch_file"; then
    git -C "$tree" apply "$patch_file"
  elif git -C "$tree" apply --reverse --check "$patch_file"; then
    echo "Already applied: ${patch_file##*/}"
  else
    echo "Cannot apply cleanly: $patch_file" >&2
    exit 1
  fi
}

clone_at_commit "$udk_dir" "$udk_commit"
clone_at_commit "$tools_dir" "$tools_commit"
clone_at_commit "$fat_dir" "$fat_commit"

cp -a "$bsp_edk/IA32FamilyCpuBasePkg" \
      "$bsp_edk/QuarkPlatformPkg" \
      "$bsp_edk/QuarkSocPkg" \
      "$bsp_edk/buildallconfigs.sh" \
      "$bsp_edk/quarkbuild.sh" \
      "$udk_dir/"
cp -a "$fat_dir/FatPkg" "$udk_dir/"

# The BSP mixes LF and CRLF. Normalize the copied source before applying the
# repository patch so its context is deterministic on modern patch tools.
find "$udk_dir/IA32FamilyCpuBasePkg" \
     "$udk_dir/QuarkPlatformPkg" \
     "$udk_dir/QuarkSocPkg" \
     -type f \( -name '*.c' -o -name '*.h' -o -name '*.inf' \
     -o -name '*.dec' -o -name '*.dsc' -o -name '*.fdf' \
     -o -name '*.asl' -o -name '*.py' -o -name '*.sh' \) \
     -exec perl -pi -e 's/\r?\n/\n/g' {} +

apply_once "$udk_dir" "$project_dir/patches/udk2014-compat-terminal.patch"
apply_once "$udk_dir" "$project_dir/patches/quark-bsp-fastboot.patch"
cp -a "$project_dir/overlays/MdeModulePkg/Include/Protocol/VarCheck.h" \
      "$udk_dir/MdeModulePkg/Include/Protocol/VarCheck.h"

apply_once "$tools_dir" "$project_dir/patches/basetools-quark-stage1.patch"
make -C "$tools_dir/BaseTools"

if [[ ! -d "$grub_dir" ]]; then
  archive="$work_dir/grub-2.14.tar.xz"
  if [[ ! -f "$archive" ]]; then
    curl -fL https://ftp.gnu.org/gnu/grub/grub-2.14.tar.xz -o "$archive"
  fi
  tar -C "$work_dir" -xf "$archive"
fi

echo "Sources prepared in $work_dir"
