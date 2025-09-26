# -------------------------------
# 1. 更新系统
# -------------------------------
sudo apt update && sudo apt upgrade -y

# 安装 Python3 全功能包（确保 venv 可用）
sudo apt install python3-full python3-venv python3-pip -y

# -------------------------------
# 2. 创建虚拟环境
# -------------------------------
# 可以把虚拟环境放在 home 目录，例如 ~/venv_ccxt
python3 -m venv ~/venv_ccxt

# -------------------------------
# 3. 激活虚拟环境
# -------------------------------
source ~/venv_ccxt/bin/activate

# -------------------------------
# 4. 升级 pip
# -------------------------------
pip install --upgrade pip

# -------------------------------
# 5. 安装依赖
# -------------------------------
pip install ccxt pandas psycopg2-binary numpy

# -------------------------------
# 6. 运行你的脚本
# -------------------------------
# 例如你的脚本在 ~/fetch-klines-data
cd ~/fetch-klines-data
python init_symbols.py
