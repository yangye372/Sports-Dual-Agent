"""
系统配置文件
"""
import os

# Neo4j配置
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "yyj2002222"

# Qwen API配置
DASHSCOPE_API_KEY = 'sk-71bd8c3a6e5749598d506ba2689da0a6'
BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
CHAT_COMPLETIONS_ENDPOINT = f"{BASE_URL}/chat/completions"

# Qwen模型配置
MODEL_NAME_CANDIDATES = [
    "qwen-plus-1127",
    # "qwen-plus-1220",
    # "qwen-plus-0723",
    # "qwen-plus-0806"
]
MODEL_NAME = MODEL_NAME_CANDIDATES[0]
TEMPERATURE = 0.1
MAX_RETRY = 3
SLEEP_BETWEEN = 1.0
TIMEOUT_SEC = 300

# 数据路径
DATA_DIR = "data"
CHUNKS_FILE = os.path.join(DATA_DIR, "chunks.jsonl")
KG_EXPORT_DIR = os.path.join(DATA_DIR, "kg_export")
TASK_CHAIN_DIR = os.path.join(DATA_DIR, "task_chains")
LOG_DIR = os.path.join(DATA_DIR, "logs")
SIM_DATA_DIR = os.path.join(DATA_DIR, "simulation")

# 节点类型
NODE_TYPES = [
    "Module",
    "KnowledgePoint",
    "CognitiveSkill",
    "TeachingTask",
    "TeachingActivity"
]

# 关系类型
RELATION_TYPES = [
    "BELONGS_TO_MODULE",
    "SUPPORTS_UNDERSTANDING",
    "CONSTITUTES_SKILL",
    "PREDECESSOR_TASK",
    "DEPENDENT_TASK"
]

# 动作类型
ACTION_TYPES = [
    "INSERT_BRIDGE",
    "BACKTRACK",
    "SIMPLIFY_PROMPT",
    "LOCAL_REORDER",
    "CONTINUE"
]

# 场景类型
SCENARIO_TYPES = [
    "ambiguous",
    "misunderstanding",
    "cross-task"
]

# 智能体类型
AGENT_TYPES = [
    "guiding",
    "structural"
]

# 模块列表
MODULES = [
    "Movement Systems",
    "Health and Aerobic Training Design"
]

# 实验配置
SIMULATION_CONFIG = {
    "modules": MODULES,
    "scenarios": SCENARIO_TYPES,
    "agents": AGENT_TYPES,
    "sessions_per_agent": 50
}

