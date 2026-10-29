#!/usr/bin/env bash
# 离线还原线上页面（tests/render_audit.js）要用的前端库：jQuery、jQuery Migrate、Tabler 图标字体。
# 用法：bash tests/fetch_vendor.sh <放库的目录>   （已经下载过的会跳过）
set -euo pipefail
DIR="${1:?用法：bash tests/fetch_vendor.sh <目录>}"
mkdir -p "$DIR"
cd "$DIR"
for spec in jquery@3.7.1:jquery-3.7.1 jquery-migrate@3.4.1:jquery-migrate-3.4.1 @tabler/icons-webfont@3.19.0:tabler-icons-webfont-3.19.0; do
	pkg="${spec%%:*}" name="${spec##*:}"
	[ -d "$name/package" ] && continue
	tgz="$(npm pack "$pkg" --silent 2>/dev/null | tail -1)"
	mkdir -p "$name" && tar -xzf "$tgz" -C "$name" && rm -f "$tgz"
done
echo "$DIR"
