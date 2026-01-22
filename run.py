"""
快速启动脚本
"""
import sys
import os

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from init_dirs import init_directories
from generate_data import main as generate_data_main
from main import main as main_main

if __name__ == '__main__':
    print("初始化目录...")
    init_directories()
    
    print("\n生成数据...")
    generate_data_main()
    
    print("\n运行主程序...")
    main_main()

