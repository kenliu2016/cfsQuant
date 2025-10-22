#!/usr/bin/env bash
set -Eeuo pipefail

############################
# 可配置变量
############################
PG_USER="postgres"                # 备份用户（建议配好 .pgpass）
PG_HOST="127.0.0.1"
PG_PORT="5432"
BACKUP_DIR="/var/backups/postgres" # 备份根目录
RETENTION_DAYS="14"               # 保留天数（按备份目录日期清理）
PARALLEL_JOBS="$(nproc)"          # pg_restore 用（可改小）
LOG_FILE="${BACKUP_DIR}/backup.log"

############################
# 环境准备
############################
TS="$(date +'%Y%m%d_%H%M%S')"
RUN_DIR="${BACKUP_DIR}/${TS}"
mkdir -p "${RUN_DIR}" "$(dirname "${LOG_FILE}")"

# 压缩工具选择
if command -v pigz >/dev/null 2>&1; then
  COMPRESS="pigz -c"
  EXT="gz"
else
  COMPRESS="gzip -c"
  EXT="gz"
fi

# 轻量资源亲和：降低 IO/CPU 抢占
IONICE="ionice -c2 -n7"
NICE="nice -n 10"

# 将输出同时写到日志与终端
exec > >(tee -a "${LOG_FILE}") 2>&1

echo "=============================="
echo "⏱ 备份开始: ${TS}"
echo "📁 目标目录: ${RUN_DIR}"
echo "🧹 保留天数: ${RETENTION_DAYS}"
echo "=============================="

############################
# 凭证建议：使用 ~/.pgpass
#   格式：host:port:database:username:password
#   权限：chmod 600 ~/.pgpass
############################

PSQL="psql -h ${PG_HOST} -p ${PG_PORT} -U ${PG_USER} -v ON_ERROR_STOP=1"

# 1) 备份全局对象（角色/权限、tablespaces）
echo "① 备份全局对象（roles/grants/tablespaces）..."
${NICE} ${IONICE} pg_dumpall -h "${PG_HOST}" -p "${PG_PORT}" -U "${PG_USER}" --globals-only \
  | ${COMPRESS} > "${RUN_DIR}/globals.sql.${EXT}"

# 2) 获取数据库清单（排除模板库）
echo "② 获取数据库列表..."
DBS=$(${PSQL} -Atc "SELECT datname FROM pg_database WHERE datistemplate = false ORDER BY 1;")

# 3) 逐库备份（-Fc 自定义格式，适合并行恢复）
for DB in ${DBS}; do
  echo "③ 备份数据库: ${DB}"
  # 说明：TimescaleDB 是扩展对象，随库一并备份，之后用 pg_restore 恢复即可
  ${NICE} ${IONICE} pg_dump -h "${PG_HOST}" -p "${PG_PORT}" -U "${PG_USER}" \
    -d "${DB}" --format=custom --no-owner --no-privileges \
    --jobs="${PARALLEL_JOBS}" \
    -f "${RUN_DIR}/${DB}.dump"

  # 可选：清单文件（便于核验/筛选恢复）
  echo "   生成对象清单: ${DB}.list"
  pg_restore -l "${RUN_DIR}/${DB}.dump" > "${RUN_DIR}/${DB}.list"
done

# 4) 生成一个清单索引与校验摘要
echo "④ 生成索引与校验摘要..."
(
  echo "# Backup Index for ${TS}"
  echo "Date: $(date -Is)"
  echo "Host: ${PG_HOST}:${PG_PORT}"
  echo "User: ${PG_USER}"
  echo "Databases:"
  for DB in ${DBS}; do
    echo "  - ${DB}"
  done
) > "${RUN_DIR}/INDEX.txt"

# 生成 sha256 校验，便于传输后完整性验证
if command -v sha256sum >/dev/null 2>&1; then
  (cd "${RUN_DIR}" && sha256sum * > SHA256SUMS.txt)
fi

# 5) 清理过期备份（仅删除日期目录）
echo "⑤ 清理超过 ${RETENTION_DAYS} 天的旧备份..."
find "${BACKUP_DIR}" -mindepth 1 -maxdepth 1 -type d -name "20*" -mtime +${RETENTION_DAYS} -print -exec rm -rf {} \;

echo "✅ 备份完成: ${TS}"
echo "📄 日志: ${LOG_FILE}"