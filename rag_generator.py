"""
图增强RAG内容生成器
"""
import json
from typing import List, Dict, Optional
from neo4j import GraphDatabase
import numpy as np
import config
from utils.api_client import QwenAPIClient
from utils.embedder import QwenEmbedder
from data_processor import DataProcessor


class RAGGenerator:
    """图增强RAG生成器"""
    
    def __init__(self):
        self.driver = GraphDatabase.driver(
            config.NEO4J_URI,
            auth=(config.NEO4J_USER, config.NEO4J_PASSWORD)
        )
        self.api_client = QwenAPIClient()
        self.data_processor = DataProcessor()
        self.embedder = None  # 延迟加载
        self.chunks = []
        self.chunk_embeddings = None
        self._chunks_loaded = False
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.driver.close()
    
    def _load_chunks(self):
        """加载chunks并计算嵌入"""
        if self._chunks_loaded:
            return
        
        if self.embedder is None:
            self.embedder = QwenEmbedder(model_name="text-embedding-v4")
        
        self.chunks = self.data_processor.load_chunks()
        if self.chunks:
            texts = [chunk['text'] for chunk in self.chunks]
            self.chunk_embeddings = self.embedder.encode(texts)
        
        self._chunks_loaded = True
    
    def retrieve(
        self,
        current_node: str,
        goal: str,
        last_feedback: Optional[str] = None
    ) -> Dict:
        """检索：图检索 + 文本检索"""
        # 图检索
        graph_context = self._graph_retrieve(current_node)
        
        # 文本检索
        text_context = self._text_retrieve(current_node, goal)
        
        return {
            'graph_context': graph_context,
            'text_context': text_context,
            'current_node': current_node,
            'goal': goal,
            'last_feedback': last_feedback
        }
    
    def _graph_retrieve(self, current_node: str, hops: int = 2) -> Dict:
        """图检索：1-2跳邻域"""
        with self.driver.session() as session:
            result = session.run("""
                MATCH path = (start)-[*1..2]-(related)
                WHERE start.name = $current
                RETURN DISTINCT related.name as name,
                       related.type as type,
                       related.definition as definition,
                       related.module as module,
                       relationships(path) as rels
                LIMIT 20
            """, current=current_node)
            
            nodes = []
            edges = []
            
            for record in result:
                nodes.append({
                    'name': record['name'],
                    'type': record['type'],
                    'definition': record.get('definition', ''),
                    'module': record.get('module', '')
                })
                
                for rel in record['rels']:
                    if rel:
                        edges.append({
                            'head': rel.start_node['name'],
                            'rel': rel.type,
                            'tail': rel.end_node['name']
                        })
            
            # 提取先修和允许的下一步
            prereqs = []
            allowed_next = []
            
            for edge in edges:
                if edge['rel'] == 'PREDECESSOR_TASK' and edge['tail'] == current_node:
                    prereqs.append(edge['head'])
                elif edge['rel'] == 'DEPENDENT_TASK' and edge['head'] == current_node:
                    allowed_next.append(edge['tail'])
            
            return {
                'nodes': nodes,
                'edges': edges,
                'prereqs': list(set(prereqs)),
                'allowed_next': list(set(allowed_next))
            }
    
    def _text_retrieve(self, current_node: str, goal: str, top_k: int = 5) -> List[Dict]:
        """文本检索：向量相似度"""
        self._load_chunks()  # 确保已加载
        
        if not self.chunks or self.chunk_embeddings is None:
            return []
        
        # 构建查询向量
        query_text = f"{current_node} {goal}"
        query_embedding = self.embedder.encode(query_text)
        
        # 计算余弦相似度
        # 归一化查询向量
        query_norm = query_embedding / (np.linalg.norm(query_embedding) + 1e-8)
        # 归一化chunk向量
        chunk_norms = self.chunk_embeddings / (np.linalg.norm(self.chunk_embeddings, axis=1, keepdims=True) + 1e-8)
        # 计算余弦相似度
        similarities = np.dot(chunk_norms, query_norm)
        
        # 获取top-k
        top_indices = np.argsort(similarities)[-top_k:][::-1]
        
        retrieved = []
        for idx in top_indices:
            chunk = self.chunks[idx]
            # 二次过滤：检查module_hint和objective_hint
            if self._filter_chunk(chunk, current_node, goal):
                retrieved.append({
                    'text': chunk['text'],
                    'source': chunk.get('source', ''),
                    'similarity': float(similarities[idx])
                })
        
        return retrieved
    
    def _filter_chunk(self, chunk: Dict, current_node: str, goal: str) -> bool:
        """二次过滤chunk"""
        # 简化版：检查文本是否包含相关关键词
        text = chunk.get('text', '').lower()
        node_lower = current_node.lower()
        goal_lower = goal.lower()
        
        return node_lower in text or goal_lower in text
    
    def generate(
        self,
        evidence_package: Dict,
        chosen_action: Optional[str] = None
    ) -> Dict:
        """生成教学输出"""
        prompt = f"""基于检索到的知识图谱和文本内容，生成教学输出。

目标：{evidence_package['goal']}
当前节点：{evidence_package['current_node']}
先修节点：{', '.join(evidence_package['graph_context']['prereqs'])}
允许下一步：{', '.join(evidence_package['graph_context']['allowed_next'])}
上次反馈：{evidence_package.get('last_feedback', '无')}
选择动作：{chosen_action or 'CONTINUE'}

图谱上下文：
{json.dumps(evidence_package['graph_context'], ensure_ascii=False, indent=2)}

文本片段：
{json.dumps(evidence_package['text_context'], ensure_ascii=False, indent=2)}

请生成：
1. 教学输出文本（G-P-F对应段落）
2. 覆盖的节点列表
3. 动作记录和理由

输出JSON格式：
{{
  "output_text": "完整的教学输出文本",
  "covered_nodes": ["节点1", "节点2"],
  "chosen_action": "{chosen_action or 'CONTINUE'}",
  "action_reason": "选择该动作的理由"
}}
"""
        
        messages = [
            {"role": "system", "content": "你是一个专业的教学助手，擅长基于知识图谱生成结构化教学内容。"},
            {"role": "user", "content": prompt}
        ]
        
        try:
            response = self.api_client.chat_completion(
                messages,
                response_format={"type": "json_object"}
            )
            content = response['choices'][0]['message']['content']
            result = self.api_client.extract_json(content)
            
            return {
                'output_text': result.get('output_text', ''),
                'covered_nodes': result.get('covered_nodes', []),
                'chosen_action': result.get('chosen_action', chosen_action or 'CONTINUE'),
                'action_reason': result.get('action_reason', '')
            }
        except Exception as e:
            return {
                'output_text': f"基于{evidence_package['current_node']}的教学内容",
                'covered_nodes': [evidence_package['current_node']],
                'chosen_action': chosen_action or 'CONTINUE',
                'action_reason': f'生成失败: {str(e)}'
            }

