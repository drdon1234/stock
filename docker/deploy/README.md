# Docker 部署

数据卷都放在 `/vol1/1000/docker/instock` 下：

| 路径 | 用途 |
|---|---|
| `data/mariadb` | 数据库数据 |
| `data/cache` | K 线缓存 |
| `data/log` | 运行日志 |
| `config/proxy.txt` | 代理列表，每行一个，可为空 |
| `.env` | `DB_PASSWORD=...`，数据库密码 |

## 首次部署

```bash
mkdir -p /vol1/1000/docker/instock/{data/mariadb,data/cache,data/log,config}
cd /vol1/1000/docker/instock
git clone https://github.com/drdon1234/stock.git src
touch config/proxy.txt
umask 077; printf "DB_PASSWORD=%s\n" "$(head -c 24 /dev/urandom | base64 | tr -dc A-Za-z0-9 | head -c 24)" > .env
docker compose -f src/docker/deploy/docker-compose.yml --env-file .env up -d --build
```

## 更新

```bash
cd /vol1/1000/docker/instock
git -C src pull
docker compose -f src/docker/deploy/docker-compose.yml --env-file .env up -d --build
```

容器启动时会对最近交易日跑一次完整作业（约 5 分钟），之后按 cron 定时运行。
网页地址：`http://<主机IP>:9988/`
