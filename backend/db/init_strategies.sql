-- Insert demo strategy mapping to demo.py
TRUNCATE TABLE strategies RESTART IDENTITY CASCADE;
INSERT INTO strategies (name, description, params) VALUES ('demo','示例均线策略','[{"name":"short","type":"number","default":5},{"name":"long","type":"number","default":20}]');