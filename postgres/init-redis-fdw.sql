CREATE EXTENSION redis_fdw;

CREATE SERVER redis_server 
    FOREIGN DATA WRAPPER redis_fdw 
    OPTIONS (address 'test_redis', port '6379');

GRANT USAGE ON FOREIGN SERVER redis_server TO test_user;
CREATE USER MAPPING FOR CURRENT_USER
    SERVER redis_server;

CREATE FOREIGN TABLE swarm_tasks (
    description text,
    callback_url text,
    fields jsonb,
    type text,
    external bool,
    starter bool
) SERVER redis_server
OPTIONS (tabletype 'list', tablekeyprefix 'swarm_tasks');