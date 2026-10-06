# InStock 部署镜像，构建上下文为仓库根目录（见同目录 docker-compose.yml）
# TA-Lib 使用 PyPI 预编译 wheel，不再从 GitHub 下载源码编译
FROM python:3.12-slim

ENV LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PYTHONIOENCODING=utf-8 \
    PYTHONPATH=/data/InStock \
    TZ=Asia/Shanghai \
    PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple \
    PIP_TRUSTED_HOST=mirrors.aliyun.com \
    PIP_NO_CACHE_DIR=1
EXPOSE 9988

RUN sed -i 's@deb.debian.org@mirrors.aliyun.com@g' /etc/apt/sources.list.d/debian.sources && \
    apt-get update && \
    apt-get install -y --no-install-recommends cron tzdata && \
    ln -sf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime && echo "Asia/Shanghai" > /etc/timezone && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt supervisor

WORKDIR /data
COPY . /data/InStock
COPY cron/cron.hourly /etc/cron.hourly
COPY cron/cron.workdayly /etc/cron.workdayly
COPY cron/cron.monthly /etc/cron.monthly

# Windows 检出的脚本是 CRLF 换行，转成 LF 否则无法执行
RUN find /data/InStock/instock/bin /data/InStock/supervisor /etc/cron.hourly /etc/cron.workdayly /etc/cron.monthly \
      -type f -exec sed -i 's/\r$//' {} + && \
    chmod 755 /data/InStock/instock/bin/run_*.sh /etc/cron.hourly/* /etc/cron.workdayly/* /etc/cron.monthly/* && \
    printf '%s\n' \
      'SHELL=/bin/sh' \
      'PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin' \
      '# min hour day month weekday command' \
      '*/30 9,10,11,13,14,15 * * 1-5 /bin/run-parts /etc/cron.hourly' \
      '30 17 * * 1-5 /bin/run-parts /etc/cron.workdayly' \
      '30 10 * * 3,6 /bin/run-parts /etc/cron.monthly' > /var/spool/cron/crontabs/root && \
    chmod 600 /var/spool/cron/crontabs/root

ENTRYPOINT ["supervisord","-n","-c","/data/InStock/supervisor/supervisord.conf"]
