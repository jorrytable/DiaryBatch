import os
import sys

# Lambdaランタイムでは CodeUri (src/backend/) がsys.pathのルートになり、
# batch.xxx / common.xxx のようなbareインポートが解決される。
# ローカルのpytest実行でも同じ解決ができるようにパスを追加する。
_SRC_BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src', 'backend'))
if _SRC_BACKEND not in sys.path:
    sys.path.insert(0, _SRC_BACKEND)
