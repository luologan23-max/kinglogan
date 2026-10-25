#!/usr/bin/env bash
# 打包插件：生成 dist/aurora-core.zip，在 WP 后台 插件 → 安装插件 → 上传插件 即可
set -euo pipefail
cd "$(dirname "$0")/../plugin"
mkdir -p ../dist
rm -f ../dist/aurora-core.zip
zip -rq ../dist/aurora-core.zip aurora-core -x '*.DS_Store'
echo "✓ 已生成 $(cd ../dist && pwd)/aurora-core.zip"
