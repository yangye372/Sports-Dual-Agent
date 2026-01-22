"""
任务链生成器
"""
import json
import os
from typing import List, Dict, Set, Optional
from neo4j import GraphDatabase
import networkx as nx
import config
from utils.api_client import QwenAPIClient


class TaskChainGenerator:
    """任务链生成器：生成G-P-F三阶段任务链"""
    
    def __init__(self):
        self.driver = GraphDatabase.driver(
            config.NEO4J_URI,
            auth=(config.NEO4J_USER, config.NEO4J_PASSWORD)
        )
        self.api_client = QwenAPIClient()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.driver.close()
    
    def generate_chain(
        self,
        target_objective: str,
        learner_state: Optional[Dict] = None
    ) -> Dict:
        """生成任务链"""
        learner_state = learner_state or {}
        
        # 1. 目标锚定
        target_nodes = self._anchor_target(target_objective)
        if not target_nodes:
            raise ValueError(f"无法找到目标节点: {target_objective}")
        
        # 2. 图遍历检索
        subgraph = self._retrieve_subgraph(target_nodes)
        
        # 3. 拓扑排序
        ordered_nodes = self._topological_sort(subgraph)
        
        # 4. 模板化实例化
        task_chain = self._instantiate_chain(ordered_nodes, target_objective, learner_state)
        
        return task_chain
    
    def _anchor_target(self, target_objective: str) -> List[str]:
        """在图中定位目标节点"""
        with self.driver.session() as session:
            # 提取关键词：从目标文本中提取模块名或关键概念
            keywords = self._extract_keywords(target_objective)
            
            nodes = []
            
            # 策略1: 尝试精确匹配TeachingTask或CognitiveSkill
            for keyword in keywords:
                result = session.run("""
                    MATCH (n)
                    WHERE (n:TeachingTask OR n:CognitiveSkill OR n:KnowledgePoint)
                    AND (n.name CONTAINS $keyword OR n.definition CONTAINS $keyword)
                    RETURN DISTINCT n.name as name, n.id as id
                    LIMIT 10
                """, keyword=keyword)
                nodes.extend([record['name'] for record in result])
            
            # 策略2: 如果找不到，尝试通过模块匹配
            if not nodes:
                for keyword in keywords:
                    result = session.run("""
                        MATCH (n)
                        WHERE n.module CONTAINS $keyword
                        RETURN DISTINCT n.name as name, n.id as id, n.type as type
                        LIMIT 20
                    """, keyword=keyword)
                    nodes.extend([record['name'] for record in result])
            
            # 策略3: 如果还是找不到，返回所有节点（作为fallback）
            if not nodes:
                result = session.run("""
                    MATCH (n)
                    WHERE n:TeachingTask OR n:CognitiveSkill OR n:KnowledgePoint
                    RETURN DISTINCT n.name as name, n.id as id
                    LIMIT 10
                """)
                nodes = [record['name'] for record in result]
                print(f"  警告: 未找到匹配节点，使用所有可用节点 ({len(nodes)} 个)")
            
            return list(set(nodes))  # 去重
    
    def _extract_keywords(self, target_objective: str) -> List[str]:
        """从目标文本中提取关键词"""
        # 模块名称映射
        module_mapping = {
            "Movement Systems": ["运动系统", "Movement Systems", "运动", "骨骼", "肌肉", "神经"],
            "Health and Aerobic Training Design": ["有氧训练", "Aerobic Training", "有氧", "最大摄氧量", "VO2max", "训练设计"],
            "掌握": [],
            "的核心内容": [],
            "核心内容": []
        }
        
        keywords = []
        
        # 检查是否包含已知模块名
        for module_name, related_terms in module_mapping.items():
            if module_name in target_objective:
                keywords.extend(related_terms)
                keywords.append(module_name)
        
        # 提取中文关键词（去除常见停用词）
        import re
        chinese_words = re.findall(r'[\u4e00-\u9fff]+', target_objective)
        for word in chinese_words:
            if len(word) >= 2 and word not in ["掌握", "的", "核心", "内容"]:
                keywords.append(word)
        
        # 提取英文单词
        english_words = re.findall(r'[A-Za-z]+', target_objective)
        keywords.extend([w for w in english_words if len(w) > 3])
        
        return list(set(keywords))  # 去重
    
    def _retrieve_subgraph(self, target_nodes: List[str]) -> Dict:
        """检索子图：先修概念、支撑技能、关联任务"""
        subgraph = {
            'nodes': set(),
            'edges': []
        }
        
        with self.driver.session() as session:
            for target in target_nodes:
                # 检索1-2跳邻域
                result = session.run("""
                    MATCH path = (start)-[*1..2]-(related)
                    WHERE start.name = $target
                    AND (related:KnowledgePoint OR related:CognitiveSkill 
                         OR related:TeachingTask OR related:TeachingActivity)
                    RETURN DISTINCT related.name as name, 
                           related.id as id,
                           related.type as type,
                           relationships(path) as rels
                """, target=target)
                
                for record in result:
                    node_name = record.get('name')
                    if node_name:  # 确保节点名称不为None
                        subgraph['nodes'].add(node_name)
                    # 提取关系
                    for rel in record.get('rels', []):
                        if rel:
                            head = rel.start_node.get('name') if rel.start_node else None
                            tail = rel.end_node.get('name') if rel.end_node else None
                            if head and tail:  # 确保头尾节点都不为None
                                subgraph['edges'].append({
                                    'head': head,
                                    'rel': rel.type,
                                    'tail': tail
                                })
                                # 确保头尾节点都在节点集合中
                                subgraph['nodes'].add(head)
                                subgraph['nodes'].add(tail)
        
        return subgraph
    
    def _topological_sort(self, subgraph: Dict) -> List[Dict]:
        """拓扑排序"""
        # 构建有向图
        G = nx.DiGraph()
        
        # 添加节点（过滤掉None值）
        for node_name in subgraph['nodes']:
            if node_name:  # 确保节点名称不为None
                G.add_node(node_name)
        
        # 添加边（只考虑先修和依赖关系）
        for edge in subgraph['edges']:
            if edge['rel'] in ['PREDECESSOR_TASK', 'DEPENDENT_TASK']:
                head = edge.get('head')
                tail = edge.get('tail')
                # 确保头尾节点都不为None且都在图中
                if head and tail and head in G.nodes() and tail in G.nodes():
                    G.add_edge(head, tail)
        
        # 拓扑排序
        try:
            ordered = list(nx.topological_sort(G))
        except nx.NetworkXError:
            # 如果有环，使用简单排序
            ordered = list(subgraph['nodes'])
        
        # 获取节点详细信息
        ordered_nodes = []
        with self.driver.session() as session:
            for node_name in ordered:
                if not node_name:  # 跳过None节点
                    continue
                result = session.run("""
                    MATCH (n)
                    WHERE n.name = $name
                    RETURN n.id as id, n.name as name, n.type as type,
                           n.definition as definition, n.module as module
                """, name=node_name)
                
                record = result.single()
                if record and record.get('name'):  # 确保记录和名称都不为None
                    ordered_nodes.append({
                        'id': record.get('id', ''),
                        'name': record['name'],
                        'type': record.get('type', ''),
                        'definition': record.get('definition', ''),
                        'module': record.get('module', '')
                    })
        
        return ordered_nodes
    
    def _instantiate_chain(
        self,
        nodes: List[Dict],
        target_objective: str,
        learner_state: Dict
    ) -> Dict:
        """模板化实例化：生成G-P-F三段脚本"""
        chain = {
            'target_objective': target_objective,
            'learner_state': learner_state,
            'nodes': []
        }
        
        for node in nodes:
            # 生成G-P-F脚本
            gpf_script = self._generate_gpf_script(node, target_objective, learner_state)
            
            chain['nodes'].append({
                **node,
                'guidance': gpf_script['guidance'],
                'presentation': gpf_script['presentation'],
                'feedback': gpf_script['feedback']
            })
        
        return chain
    
    def _generate_gpf_script(
        self,
        node: Dict,
        target_objective: str,
        learner_state: Dict
    ) -> Dict:
        """生成G-P-F三段脚本"""
        prompt = f"""为以下教学节点生成三段式教学脚本（Guidance-Presentation-Feedback）。

节点信息：
- 名称：{node['name']}
- 类型：{node['type']}
- 定义：{node.get('definition', '')}
- 模块：{node.get('module', '')}

目标：{target_objective}
学习者状态：{json.dumps(learner_state, ensure_ascii=False)}

请生成三段内容：

1. Guidance（引导阶段）：
   - 澄清学习目标
   - 激活先备知识
   - 建立学习动机

2. Presentation（讲解阶段）：
   - 讲解关键概念/技能点
   - 提供示例支撑
   - 解释机制和原理

3. Feedback（反馈阶段）：
   - 设计检查点问题
   - 识别可能的误解
   - 准备偏差信号检测

输出JSON格式：
{{
  "guidance": "引导内容",
  "presentation": "讲解内容",
  "feedback": "反馈检查内容"
}}
"""
        
        messages = [
            {"role": "system", "content": "你是一个专业的教学设计师，擅长设计结构化的教学脚本。"},
            {"role": "user", "content": prompt}
        ]
        
        try:
            response = self.api_client.chat_completion(
                messages,
                response_format={"type": "json_object"}
            )
            content = response['choices'][0]['message']['content']
            return self.api_client.extract_json(content)
        except:
            # 默认模板
            return {
                "guidance": f"让我们学习{node['name']}。这是{target_objective}的重要组成部分。",
                "presentation": f"{node['name']}的定义是：{node.get('definition', '暂无定义')}",
                "feedback": f"请回答：你理解{node['name']}了吗？有什么疑问？"
            }
    
    def save_chain(self, chain: Dict, output_file: str):
        """保存任务链"""
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(chain, f, ensure_ascii=False, indent=2)
    
    def load_chain(self, input_file: str) -> Dict:
        """加载任务链"""
        with open(input_file, 'r', encoding='utf-8') as f:
            return json.load(f)

