安装说明

1️⃣ 将脚本保存为文件：
nano install_timescaledb.sh
粘贴上述内容后保存退出（Ctrl + O, Enter, Ctrl + X）。

2️⃣ 给脚本执行权限：
chmod +x install_timescaledb.sh

3️⃣ 运行脚本：
./install_timescaledb.sh




卸载说明

1️⃣ 创建脚本：
nano remove_timescaledb.sh

2️⃣ 粘贴以上内容并保存退出
（Ctrl + O → Enter → Ctrl + X）

3️⃣ 赋予执行权限：
chmod +x remove_timescaledb.sh

4️⃣ 执行卸载脚本：
./remove_timescaledb.sh



定期备份说明

1)赋权并试跑：

sudo install -m 750 -o root -g root pg_timescale_backup.sh /usr/local/bin/pg_timescale_backup.sh
sudo /usr/local/bin/pg_timescale_backup.sh


2) 设置 cron 定时任务
举例：每天 03:30（新加坡时间，UTC+8） 备份一次。
sudo crontab -e
加入一行（确保脚本是可执行路径）：
30 3 * * * /usr/local/bin/pg_timescale_backup.sh >/dev/null 2>&1
想每 6 小时一次：0 */6 * * * /usr/local/bin/pg_timescale_backup.sh >/dev/null 2>&1

3) 恢复（单库还原）速查
适用于 TimescaleDB：扩展与对象定义都在 dump 文件里，会随着还原一起恢复（如遇版本差异，先 CREATE EXTENSION timescaledb; 再还原）。
新建数据库（如果不存在）：
createdb -h 127.0.0.1 -p 5432 -U postgres mydb
并行还原（根据备份时的 PARALLEL_JOBS 调整）：
pg_restore -h 127.0.0.1 -p 5432 -U postgres \
  -d mydb --jobs=4 --no-owner --no-privileges /var/backups/postgres/20250101_033001/mydb.dump

全局角色/权限（可在全库恢复前执行）：
gzip -dc /var/backups/postgres/20250101_033001/globals.sql.gz | psql -h 127.0.0.1 -p 5432 -U postgres

只想还原某些 schema/table，可先看清单：
pg_restore -l mydb.dump | less
然后用 -L 过滤清单 或用 -t schema.table 精选恢复。

4) 额外建议（可选）

WAL/物理备份：若追求点时间恢复（PITR），配合归档 pg_wal 或使用 pg_basebackup + WAL 归档。当前脚本属于逻辑备份，适合日常冷备/迁移。
异地容灾：备份后可 rclone/aws s3 cp/rsync 到远端（在脚本末尾追加上传命令）。
监控失败：在 cron 中把日志留存，或用 mailx/Webhook 发送失败告警。
压缩率/速度：已自动优先 pigz（多核），无则用 gzip。

需要的话，我可以再给你一个 带 S3 上传版 的脚本（含 aws s3 cp、多区域 bucket、断点续传与清单同步），或者 systemd 定时器版（比 cron 更好管控日志与权限）。