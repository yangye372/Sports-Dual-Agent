"""
初始化目录结构
"""
import os
import config


def init_directories():
    """创建必要的目录"""
    directories = [
        config.DATA_DIR,
        config.KG_EXPORT_DIR,
        config.TASK_CHAIN_DIR,
        config.LOG_DIR,
        config.SIM_DATA_DIR
    ]
    
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        print(f"创建目录: {directory}")


if __name__ == '__main__':
    init_directories()
    print("目录初始化完成！")

