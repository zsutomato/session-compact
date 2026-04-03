#!/bin/bash
# release.sh — 打包并生成新版本的 manifest
# 用法：./scripts/release.sh 1.1.0
# 前提：已安装 gh CLI，且已 push 到 GitHub

set -e

VERSION="${1:-}"
if [ -z "$VERSION" ]; then
  echo "用法: $0 <版本号>  例如: $0 1.1.0"
  exit 1
fi

SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SKILL_NAME="session-compact"
ZIP_NAME="${SKILL_NAME}.zip"
ZIP_PATH="/tmp/${ZIP_NAME}"
GITHUB_REPO="zsutomato/session-compact"

echo "==> 打包 skill v${VERSION}..."

# 打包（排除 manifest.json / release 脚本 / .DS_Store）
cd "$(dirname "$SKILL_DIR")"
zip -r "${ZIP_PATH}" "${SKILL_NAME}/" \
  --exclude "*.DS_Store" \
  --exclude "*/__pycache__/*" \
  --exclude "*/.git/*"

# 计算 sha256
SHA256=$(shasum -a 256 "${ZIP_PATH}" | awk '{print $1}')
echo "==> SHA256: ${SHA256}"

# 更新 manifest.json
cat > "${SKILL_DIR}/manifest.json" << EOF
{
  "version": "${VERSION}",
  "zip_url": "https://github.com/${GITHUB_REPO}/releases/download/v${VERSION}/${ZIP_NAME}",
  "sha256": "${SHA256}"
}
EOF

# 更新 config.json 里的版本号
python3 -c "
import json, pathlib
p = pathlib.Path('${SKILL_DIR}/config.json')
cfg = json.loads(p.read_text())
cfg['version'] = '${VERSION}'
p.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + '\n')
print('config.json 已更新')
"

echo "==> manifest.json 已更新"
echo ""
echo "接下来手动执行（或取消注释自动执行）："
echo ""
echo "  git add -A && git commit -m 'release: v${VERSION}' && git push"
echo "  gh release create v${VERSION} '${ZIP_PATH}' --title 'v${VERSION}' --notes ''"
echo ""
echo "发布后，用户运行以下命令即可更新："
echo "  skillhub upgrade session-compact"
