# 使用指南

## 快速开始

### 1. 环境准备

```bash
# 安装依赖
pip install -r requirements.txt

# 初始化目录
python init_dirs.py

# 确保Neo4j服务运行
# 默认连接: bolt://localhost:7687
# 用户名: neo4j
# 密码: yyj2002222 (在config.py中配置)
```

### 2. 生成数据

```bash
python generate_data.py
```

这将生成示例教学材料并切分为chunks。

### 3. 构建知识图谱

```bash
python main.py --step kg
```

**注意**: 这一步会调用Qwen API进行三元组抽取，需要：
- 有效的API密钥（已在config.py中配置）
- 网络连接
- 可能需要一些时间（取决于chunks数量）

### 4. 生成任务链

```bash
python main.py --step chain
```

为每个模块生成G-P-F三阶段任务链。

### 5. 运行仿真实验

```bash
python main.py --step sim
```

**注意**: 这一步会运行100个会话，需要较长时间。

### 6. 评估结果

```bash
python main.py --step eval
```

计算并输出评估指标。

## 完整流程

```bash
# 一键运行（推荐）
python run.py

# 或分步运行
python main.py
```

## 输出文件说明

### 知识图谱
- `data/kg_export/nodes.csv`: 所有节点（实体）
- `data/kg_export/edges.csv`: 所有关系（边）

### 任务链
- `data/task_chains/Movement_Systems_chain.json`: 运动系统模块任务链
- `data/task_chains/Health_and_Aerobic_Training_Design_chain.json`: 有氧训练模块任务链

### 仿真数据
- `data/simulation/*.json`: 每个会话的对话记录
- `data/simulation/summary.json`: 会话汇总

### 日志
- `data/logs/path_log.jsonl`: 所有交互的详细日志

### 评估结果
- `data/evaluation_results.json`: 评估指标和统计

## 自定义配置

编辑 `config.py` 可以修改：
- Neo4j连接信息
- API配置
- 模型参数
- 数据路径

## 故障排除

### Neo4j连接失败
- 检查Neo4j服务是否运行
- 检查连接URI、用户名、密码是否正确

### API调用失败
- 检查网络连接
- 检查API密钥是否有效
- 检查API配额是否充足

### 内存不足
- 减少chunks数量
- 减少仿真会话数（修改config.py中的sessions_per_agent）

### 模型下载慢
- sentence-transformers模型首次使用会自动下载
- 可以手动下载并缓存到本地

## 扩展开发

### 添加新的节点类型
1. 在 `config.py` 的 `NODE_TYPES` 中添加
2. 更新 `kg_builder.py` 中的抽取逻辑

### 添加新的关系类型
1. 在 `config.py` 的 `RELATION_TYPES` 中添加
2. 更新抽取和验证逻辑

### 自定义智能体策略
编辑 `dual_agent_controller.py` 中的prompt和逻辑。

### 自定义评估指标
在 `evaluator.py` 中添加新的计算方法。

