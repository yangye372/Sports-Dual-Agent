"""
知识图谱构建模块
"""
import json
import os
from typing import List, Dict, Set, Tuple
from neo4j import GraphDatabase
from collections import defaultdict
import config
from utils.api_client import QwenAPIClient


class KGBuilder:
    """知识图谱构建器"""
    
    def __init__(self):
        self.driver = GraphDatabase.driver(
            config.NEO4J_URI,
            auth=(config.NEO4J_USER, config.NEO4J_PASSWORD)
        )
        self.api_client = QwenAPIClient()
        self.entities = []
        self.relations = []
        self.entity_map = {}  # temp_name -> canonical_name
        self.synonym_map = {}  # 同义词映射
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.driver.close()
    
    def extract_triples(self, chunk: Dict) -> Tuple[List[Dict], List[Dict]]:
        """从chunk中抽取三元组"""
        prompt = f"""你是一个知识图谱构建专家。请从以下教学文本中抽取实体和关系。

文本内容：
{chunk['text']}

模块提示：{chunk.get('module_hint', '')}
目标提示：{chunk.get('objective_hint', '')}

请按照以下JSON格式输出：

{{
  "entities": [
    {{
      "id": "实体唯一ID",
      "temp_name": "文本中的名称",
      "type": "Module|KnowledgePoint|CognitiveSkill|TeachingTask|TeachingActivity",
      "canonical_name": "规范化名称",
      "definition": "定义或描述",
      "source_chunk": "{chunk['chunk_id']}"
    }}
  ],
  "relations": [
    {{
      "head": "头实体规范化名称",
      "rel": "BELONGS_TO_MODULE|SUPPORTS_UNDERSTANDING|CONSTITUTES_SKILL|PREDECESSOR_TASK|DEPENDENT_TASK",
      "tail": "尾实体规范化名称",
      "confidence": 0.0-1.0,
      "justification": "关系理由",
      "source_chunk": "{chunk['chunk_id']}"
    }}
  ]
}}

要求：
1. 实体类型必须是指定的5种之一
2. 关系类型必须是指定的5种之一
3. 确保规范化名称一致
4. 抽取所有重要的概念、技能和任务关系
5. 如果模块提示不为空，请为所有实体添加"module"字段，值为模块提示的内容
6. 如果模块提示不为空，请创建一个Module类型的实体，名称为模块提示的内容
7. 使用BELONGS_TO_MODULE关系将其他实体关联到Module实体
"""
        
        messages = [
            {"role": "system", "content": "你是一个专业的知识图谱构建助手，擅长从教学文本中提取结构化知识。"},
            {"role": "user", "content": prompt}
        ]
        
        try:
            print(f"      调用API进行三元组抽取...")
            response = self.api_client.chat_completion(
                messages,
                response_format={"type": "json_object"}
            )
            
            content = response['choices'][0]['message']['content']
            result = self.api_client.extract_json(content)
            
            entities = result.get('entities', [])
            relations = result.get('relations', [])
            
            # 自检补全（可选，如果太慢可以跳过）
            # 注释掉自检补全以加快速度，如果需要可以取消注释
            # try:
            #     print(f"      进行自检补全...")
            #     entities, relations = self._self_check(chunk, entities, relations)
            # except Exception as e:
            #     print(f"      自检补全跳过: {str(e)}")
            #     # 继续使用主抽取的结果
            
            return entities, relations
        except Exception as e:
            print(f"      抽取失败: {str(e)}")
            import traceback
            traceback.print_exc()
            return [], []
    
    def _self_check(
        self,
        chunk: Dict,
        entities: List[Dict],
        relations: List[Dict]
    ) -> Tuple[List[Dict], List[Dict]]:
        """自检补全：补全缺失的先修/依赖关系"""
        if not entities:
            return entities, relations
        
        # 简化自检：只对重要实体进行补全，避免API调用过多
        if len(entities) > 10:  # 如果实体太多，跳过自检
            return entities, relations
        
        prompt = f"""基于已抽取的实体和关系，检查并补全缺失的先修关系、依赖关系和关键概念定义。

已抽取实体：
{json.dumps(entities[:5], ensure_ascii=False, indent=2)}  # 只显示前5个

已抽取关系：
{json.dumps(relations[:5], ensure_ascii=False, indent=2)}  # 只显示前5个

请补全：
1. 缺失的PREDECESSOR_TASK关系（先修任务）
2. 缺失的DEPENDENT_TASK关系（依赖任务）
3. 缺失的SUPPORTS_UNDERSTANDING关系（概念支撑）
4. 缺失的关键概念定义

输出格式同上，只输出需要补全的部分。如果没有需要补全的，返回空的entities和relations。
"""
        
        messages = [
            {"role": "system", "content": "你是一个知识图谱质量检查助手。"},
            {"role": "user", "content": prompt}
        ]
        
        try:
            response = self.api_client.chat_completion(messages)
            content = response['choices'][0]['message']['content']
            result = self.api_client.extract_json(content)
            
            # 合并补全的实体和关系
            additional_entities = result.get('entities', [])
            additional_relations = result.get('relations', [])
            
            if additional_entities or additional_relations:
                entities.extend(additional_entities)
                relations.extend(additional_relations)
        except Exception as e:
            # 自检失败不影响主抽取
            pass
        
        return entities, relations
    
    def normalize_and_deduplicate(self):
        """规范化、去重、语义校验"""
        # 1. 同义词归并
        self._merge_synonyms()
        
        # 2. 去重
        self._deduplicate_entities()
        self._deduplicate_relations()
        
        # 3. 校验
        self._validate_graph()
    
    def _merge_synonyms(self):
        """同义词归并"""
        # 构建同义词映射（简化版，实际可用更复杂的语义相似度）
        name_to_canonical = {}
        
        for entity in self.entities:
            canonical = entity['canonical_name']
            temp = entity['temp_name']
            
            # 如果temp_name和canonical_name不同，建立映射
            if temp != canonical:
                name_to_canonical[temp] = canonical
            
            # 检查是否有别名（简化处理）
            if 'alias' in entity:
                for alias in entity['alias']:
                    name_to_canonical[alias] = canonical
        
        self.synonym_map = name_to_canonical
        
        # 更新关系中的实体名称
        for rel in self.relations:
            rel['head'] = name_to_canonical.get(rel['head'], rel['head'])
            rel['tail'] = name_to_canonical.get(rel['tail'], rel['tail'])
    
    def _deduplicate_entities(self):
        """实体去重"""
        seen = {}
        unique_entities = []
        
        for entity in self.entities:
            key = (entity['canonical_name'], entity['type'])
            if key not in seen:
                seen[key] = entity
                unique_entities.append(entity)
            else:
                # 合并定义
                existing = seen[key]
                if entity.get('definition') and not existing.get('definition'):
                    existing['definition'] = entity['definition']
        
        self.entities = unique_entities
    
    def _deduplicate_relations(self):
        """关系去重"""
        seen = set()
        unique_relations = []
        
        for rel in self.relations:
            key = (rel['head'], rel['rel'], rel['tail'])
            if key not in seen:
                seen.add(key)
                unique_relations.append(rel)
        
        self.relations = unique_relations
    
    def _validate_graph(self):
        """校验图谱：禁止环形先修等"""
        # 构建先修关系图
        predecessor_graph = defaultdict(set)
        for rel in self.relations:
            if rel['rel'] == 'PREDECESSOR_TASK':
                predecessor_graph[rel['tail']].add(rel['head'])
        
        # 检测环（简化版DFS）
        def has_cycle(node, visited, rec_stack):
            visited.add(node)
            rec_stack.add(node)
            
            for neighbor in predecessor_graph.get(node, []):
                if neighbor not in visited:
                    if has_cycle(neighbor, visited, rec_stack):
                        return True
                elif neighbor in rec_stack:
                    return True
            
            rec_stack.remove(node)
            return False
        
        # 移除导致环的关系
        valid_relations = []
        for rel in self.relations:
            if rel['rel'] == 'PREDECESSOR_TASK':
                # 临时添加，检查是否形成环
                predecessor_graph[rel['tail']].add(rel['head'])
                visited = set()
                rec_stack = set()
                if has_cycle(rel['head'], visited, rec_stack):
                    predecessor_graph[rel['tail']].discard(rel['head'])
                    continue
            valid_relations.append(rel)
        
        self.relations = valid_relations
    
    def build_from_chunks(self, chunks: List[Dict], skip_existing: bool = True):
        """从chunks构建知识图谱"""
        print(f"开始从 {len(chunks)} 个chunks构建知识图谱...")
        
        # 检查是否已有数据
        if skip_existing:
            with self.driver.session() as session:
                result = session.run("MATCH (n) RETURN count(n) as count")
                existing_count = result.single()['count']
                if existing_count > 0:
                    print(f"检测到知识图谱中已有 {existing_count} 个节点，跳过抽取步骤")
                    print("如需重新构建，请先清空Neo4j数据库或设置 skip_existing=False")
                    return
        
        # 阶段B：三元组抽取
        print("\n阶段B: 三元组抽取")
        for idx, chunk in enumerate(chunks, 1):
            print(f"  处理chunk {idx}/{len(chunks)}: {chunk.get('chunk_id', 'unknown')[:50]}...")
            try:
                entities, relations = self.extract_triples(chunk)
                self.entities.extend(entities)
                self.relations.extend(relations)
                print(f"    ✓ 抽取到 {len(entities)} 个实体，{len(relations)} 个关系")
            except Exception as e:
                print(f"    ✗ 抽取失败: {str(e)}")
                continue
        
        print(f"\n抽取完成：{len(self.entities)} 个实体，{len(self.relations)} 个关系")
        
        # 阶段C：规范化、去重、校验
        print("\n阶段C: 规范化、去重、校验...")
        self.normalize_and_deduplicate()
        print(f"规范化后：{len(self.entities)} 个实体，{len(self.relations)} 个关系")
        
        # 入库
        print("\n阶段D: 导入到Neo4j...")
        self._import_to_neo4j()
    
    def _import_to_neo4j(self):
        """导入到Neo4j"""
        print(f"  连接Neo4j...")
        try:
            with self.driver.session() as session:
                # 创建唯一约束
                print(f"  创建唯一约束...")
                for node_type in config.NODE_TYPES:
                    session.run(f"""
                        CREATE CONSTRAINT IF NOT EXISTS FOR (n:{node_type})
                        REQUIRE n.id IS UNIQUE
                    """)
                
                # 创建索引
                print(f"  创建索引...")
                for node_type in config.NODE_TYPES:
                    session.run(f"""
                        CREATE INDEX IF NOT EXISTS FOR (n:{node_type})
                        ON (n.name)
                    """)
                
                # 导入实体
                print(f"  导入 {len(self.entities)} 个实体...")
                for entity in self.entities:
                    session.run(f"""
                        MERGE (n:{entity['type']} {{id: $id}})
                        SET n.name = $name,
                            n.definition = $definition,
                            n.module = $module,
                            n.difficulty = $difficulty,
                            n.source_ref = $source_ref
                    """, {
                        'id': entity['id'],
                        'name': entity['canonical_name'],
                        'definition': entity.get('definition', ''),
                        'module': entity.get('module', ''),
                        'difficulty': entity.get('difficulty', 'medium'),
                        'source_ref': entity.get('source_chunk', '')
                    })
                
                # 导入关系
                print(f"  导入 {len(self.relations)} 个关系...")
                for rel in self.relations:
                    session.run(f"""
                        MATCH (h), (t)
                        WHERE h.name = $head AND t.name = $tail
                        MERGE (h)-[r:{rel['rel']}]->(t)
                        SET r.confidence = $confidence,
                            r.justification = $justification,
                            r.source_chunk = $source_chunk
                    """, {
                        'head': rel['head'],
                        'tail': rel['tail'],
                        'confidence': rel.get('confidence', 1.0),
                        'justification': rel.get('justification', ''),
                        'source_chunk': rel.get('source_chunk', '')
                    })
            
            print("  ✓ 知识图谱已导入Neo4j")
        except Exception as e:
            print(f"  ✗ Neo4j导入失败: {str(e)}")
            import traceback
            traceback.print_exc()
            raise
    
    def export_graph(self, output_dir: str = None):
        """导出图谱"""
        output_dir = output_dir or config.KG_EXPORT_DIR
        os.makedirs(output_dir, exist_ok=True)
        
        # 导出节点
        nodes_file = os.path.join(output_dir, "nodes.csv")
        with open(nodes_file, 'w', encoding='utf-8') as f:
            f.write("id,name,type,definition,module,difficulty,source_ref\n")
            for entity in self.entities:
                f.write(f"{entity['id']},{entity['canonical_name']},{entity['type']},"
                       f"{entity.get('definition', '')},{entity.get('module', '')},"
                       f"{entity.get('difficulty', 'medium')},{entity.get('source_chunk', '')}\n")
        
        # 导出边
        edges_file = os.path.join(output_dir, "edges.csv")
        with open(edges_file, 'w', encoding='utf-8') as f:
            f.write("head,relation,tail,confidence,justification,source_chunk\n")
            for rel in self.relations:
                f.write(f"{rel['head']},{rel['rel']},{rel['tail']},"
                       f"{rel.get('confidence', 1.0)},{rel.get('justification', '')},"
                       f"{rel.get('source_chunk', '')}\n")
        
        print(f"图谱已导出到 {output_dir}")

