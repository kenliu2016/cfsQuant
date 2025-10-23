# 0) 让 CLT 指向正确位置 + 接受许可
sudo xcode-select -switch /Library/Developer/CommandLineTools || true
sudo xcodebuild -license accept || true

# 1) 确认 SDK 可用（应该是 /Library/Developer/.../MacOSX.sdk）
export SDKROOT="$(xcrun --sdk macosx --show-sdk-path)"
echo "SDKROOT=$SDKROOT"
test -f "$SDKROOT/usr/lib/libSystem.tbd" || { echo "❌ CLT/SDK 异常"; exit 1; }

# 2) 强制从源码重建 postgresql@17（避免装到旧 bottle）
brew update
export HOMEBREW_NO_INSTALL_FROM_API=1
export HOMEBREW_NO_BOTTLE=1
brew uninstall postgresql@17
brew install --build-from-source postgresql@17

# 3) 验证 pg_config 不再包含 MacOSX14.sdk
PG_PREFIX="$(brew --prefix postgresql@17)"
for f in cflags cppflags ldflags; do
  echo ">>> pg_config --$f"
  "$PG_PREFIX/bin/pg_config" --$f
done
"$PG_PREFIX/bin/pg_config" --ldflags | grep -q "MacOSX14.sdk" && { echo "❌ 仍有 14 SDK，先别往下，回我这段输出"; exit 2; }
echo "✅ pg_config 已干净"

# 4) 编译安装 TimescaleDB（PG17）
brew install cmake openssl@3 pkg-config git || true

# 干净构建目录
rm -rf /tmp/ts_build && mkdir -p /tmp/ts_build && cd /tmp/ts_build
TS_VER="2.22.1"
curl -L -o ts.tar.gz "https://github.com/timescaledb/timescaledb/archive/refs/tags/${TS_VER}.tar.gz"
tar xf ts.tar.gz && cd "timescaledb-${TS_VER}"

# 一些机型/编译器需要 SSE4.2/CRC32 才能过 TSL 的 hash 路
export MACOSX_DEPLOYMENT_TARGET=15.0
OPENSSL_ROOT_DIR="$(brew --prefix openssl@3)"
CFLAGS="-isysroot $SDKROOT -mmacosx-version-min=$MACOSX_DEPLOYMENT_TARGET -msse4.2 -mcrc32"
LDFLAGS="-isysroot $SDKROOT -Wl,-syslibroot,$SDKROOT -L$(brew --prefix openssl@3)/lib"

./bootstrap \
  -DPOSTGRES_PG_CONFIG="$PG_PREFIX/bin/pg_config" \
  -DPROJECT_INSTALL_METHOD="manual" \
  -DCMAKE_BUILD_TYPE=RelWithDebInfo \
  -DOPENSSL_ROOT_DIR="$OPENSSL_ROOT_DIR" \
  -DCMAKE_OSX_SYSROOT="$SDKROOT" \
  -DCMAKE_OSX_DEPLOYMENT_TARGET="$MACOSX_DEPLOYMENT_TARGET" \
  -DCMAKE_C_FLAGS="$CFLAGS" \
  -DCMAKE_CXX_FLAGS="$CFLAGS" \
  -DCMAKE_SHARED_LINKER_FLAGS="-Wl,-syslibroot,$SDKROOT" \
  -DCMAKE_EXE_LINKER_FLAGS="-Wl,-syslibroot,$SDKROOT" \
  -DWARNINGS_AS_ERRORS=OFF -DTAP_CHECKS=OFF -DREGRESS_CHECKS=OFF

make -C build -j"$(sysctl -n hw.ncpu 2>/dev/null || echo 4)"
sudo make -C build install

# 5) 启用扩展并验收
PG_BIN="$PG_PREFIX/bin"
PG_CONF="$("$PG_BIN/psql" -At -c "SHOW config_file;")"
if ! grep -q "^shared_preload_libraries" "$PG_CONF"; then
  echo "shared_preload_libraries = 'timescaledb'" | sudo tee -a "$PG_CONF" >/dev/null
else
  sudo sed -i '' "s/^shared_preload_libraries.*/shared_preload_libraries = 'timescaledb'/" "$PG_CONF"
fi
brew services restart postgresql@17

"$PG_BIN/createdb" ts_test 2>/dev/null || true
"$PG_BIN/psql" -d ts_test -v ON_ERROR_STOP=1 -c "CREATE EXTENSION IF NOT EXISTS timescaledb;"
"$PG_BIN/psql" -d ts_test -c "\dx" | sed -n '1,120p'
