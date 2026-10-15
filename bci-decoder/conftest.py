"""让 pytest 在项目根目录直接 import bci_decoder（无需安装）。"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
