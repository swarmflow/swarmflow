# Use PostgreSQL 17 as base
FROM postgres:17

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    postgresql-server-dev-17 \
    libhiredis-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Clone and build redis_fdw
RUN git clone https://github.com/pg-redis-fdw/redis_fdw.git \
    && cd redis_fdw \
    && git checkout REL_17_STABLE \
    && make \
    && make install

# Create extension creation script
COPY postgres/init-redis-fdw.sql /docker-entrypoint-initdb.d/
