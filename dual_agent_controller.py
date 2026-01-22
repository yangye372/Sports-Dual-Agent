"""
双智能体调控器
"""
import json
from typing import Dict, List, Optional, Tuple
from neo4j import GraphDatabase
import config
from utils.api_client import QwenAPIClient


class DualAgentController:
    """双智能体调控器"""
    
    def __init__(self):
        self.driver = GraphDatabase.driver(
            config.NEO4J_URI,
            auth=(config.NEO4J_USER, config.NEO4J_PASSWORD)
        )
        self.api_client = QwenAPIClient()
        self.guiding_prompt = self._get_guiding_prompt()
        self.structural_prompt = self._get_structural_prompt()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.driver.close()
    
    def _get_guiding_prompt(self) -> str:
        """Guiding Agent的system prompt"""
        return """你是一个Guiding Agent，专注于帮助学习者理解知识。

当学习者出现误解或跳任务时，你的策略是：
1. 插入"补桥节点"来填补知识缺口
2. 解释转场因果，帮助学习者理解为什么需要这些先修知识
3. 恢复可学性，确保学习者能够跟上学习路径

可用动作：
- INSERT_BRIDGE(node_id, reason): 插入必要补桥节点
- BACKTRACK(to_node_id, reason): 回退到先修节点
- CONTINUE(next_node_id): 维持主路径推进

你的目标是帮助学习者建立完整的知识理解链。"""
    
    def _get_structural_prompt(self) -> str:
        """Structural Agent的system prompt"""
        return """你是一个Structural Agent，专注于维持学习路径的结构性和可控性。

当目标含糊或对话漂移时，你的策略是：
1. 回退到主路径，确保学习目标清晰
2. 简化提示，减少分支和复杂度
3. 维持路线可控性，防止学习偏离

可用动作：
- BACKTRACK(to_node_id, reason): 回退到先修节点
- SIMPLIFY_PROMPT(level): 压缩提问/减少分支
- LOCAL_REORDER(window): 在依赖允许范围内局部重排
- CONTINUE(next_node_id): 维持主路径推进

你的目标是确保学习路径清晰、可控、高效。"""
    
    def detect_scenario(
        self,
        user_input: str,
        current_node: str,
        goal: str
    ) -> Tuple[str, str]:
        """场景识别：规则优先 + LLM判别"""
        # 规则优先检测
        scenario, issue = self._rule_based_detection(user_input, current_node, goal)
        
        if scenario == 'unknown':
            # LLM判别兜底
            scenario, issue = self._llm_based_detection(user_input, current_node, goal)
        
        return scenario, issue
    
    def _rule_based_detection(
        self,
        user_input: str,
        current_node: str,
        goal: str
    ) -> Tuple[str, str]:
        """基于规则的场景检测"""
        input_lower = user_input.lower()
        
        # 检测ambiguous goals
        ambiguous_keywords = ['不知道', '不清楚', '不明白', '什么意思', '哪个', '什么']
        if any(kw in input_lower for kw in ambiguous_keywords):
            return 'ambiguous', '用户目标不明确'
        
        # 检测misunderstanding
        misunderstanding_keywords = ['不对', '错了', '不是', '应该是', '理解错了']
        if any(kw in input_lower for kw in misunderstanding_keywords):
            return 'misunderstanding', '知识理解错误'
        
        # 检测cross-task jumping
        # 检查是否提到其他模块或任务
        with self.driver.session() as session:
            result = session.run("""
                MATCH (n:TeachingTask)
                WHERE n.name <> $current
                RETURN n.name as name
                LIMIT 10
            """, current=current_node)
            
            other_tasks = [record['name'] for record in result]
            if any(task in user_input for task in other_tasks):
                return 'cross-task', '跨任务跳跃'
        
        return 'unknown', ''
    
    def _llm_based_detection(
        self,
        user_input: str,
        current_node: str,
        goal: str
    ) -> Tuple[str, str]:
        """基于LLM的场景检测"""
        prompt = f"""分析以下学习交互，判断属于哪种偏离场景：

用户输入：{user_input}
当前节点：{current_node}
学习目标：{goal}

场景类型：
1. ambiguous: 用户目标无法映射到图中具体task/skill或多目标冲突
2. misunderstanding: 反馈阶段出现关键概念错误、机制链断裂或定义混淆
3. cross-task: 输入显示明显跳到非相邻节点或跨模块task
4. normal: 正常学习交互

输出JSON格式：
{{
  "scenario": "场景类型",
  "issue": "问题描述"
}}
"""
        
        messages = [
            {"role": "system", "content": "你是一个学习场景分析专家。"},
            {"role": "user", "content": prompt}
        ]
        
        try:
            response = self.api_client.chat_completion(
                messages,
                response_format={"type": "json_object"}
            )
            content = response['choices'][0]['message']['content']
            result = self.api_client.extract_json(content)
            return result.get('scenario', 'normal'), result.get('issue', '')
        except:
            return 'normal', ''
    
    def control(
        self,
        agent_type: str,
        scenario: str,
        issue: str,
        current_node: str,
        goal: str,
        path_history: List[str],
        user_input: str
    ) -> Dict:
        """智能体调控"""
        if agent_type == 'guiding':
            return self._guiding_control(scenario, issue, current_node, goal, path_history, user_input)
        elif agent_type == 'structural':
            return self._structural_control(scenario, issue, current_node, goal, path_history, user_input)
        else:
            raise ValueError(f"未知智能体类型: {agent_type}")
    
    def _guiding_control(
        self,
        scenario: str,
        issue: str,
        current_node: str,
        goal: str,
        path_history: List[str],
        user_input: str
    ) -> Dict:
        """Guiding Agent调控"""
        prompt = f"""{self.guiding_prompt}

当前场景：{scenario}
问题描述：{issue}
当前节点：{current_node}
学习目标：{goal}
路径历史：{' -> '.join(path_history[-5:])}
用户输入：{user_input}

请分析情况并决定采取什么动作。输出JSON格式：
{{
  "action_type": "INSERT_BRIDGE|BACKTRACK|CONTINUE",
  "action_params": {{
    "node_id": "节点ID或名称",
    "reason": "动作理由"
  }},
  "teaching_discourse": "教学话语内容"
}}
"""
        
        messages = [
            {"role": "system", "content": self.guiding_prompt},
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
                'action_type': result.get('action_type', 'CONTINUE'),
                'action_params': result.get('action_params', {}),
                'teaching_discourse': result.get('teaching_discourse', '')
            }
        except:
            return {
                'action_type': 'CONTINUE',
                'action_params': {'node_id': current_node, 'reason': '默认继续'},
                'teaching_discourse': '让我们继续学习。'
            }
    
    def _structural_control(
        self,
        scenario: str,
        issue: str,
        current_node: str,
        goal: str,
        path_history: List[str],
        user_input: str
    ) -> Dict:
        """Structural Agent调控"""
        prompt = f"""{self.structural_prompt}

当前场景：{scenario}
问题描述：{issue}
当前节点：{current_node}
学习目标：{goal}
路径历史：{' -> '.join(path_history[-5:])}
用户输入：{user_input}

请分析情况并决定采取什么动作。输出JSON格式：
{{
  "action_type": "BACKTRACK|SIMPLIFY_PROMPT|LOCAL_REORDER|CONTINUE",
  "action_params": {{
    "node_id": "节点ID或名称（如适用）",
    "level": "简化级别（如适用）",
    "reason": "动作理由"
  }},
  "teaching_discourse": "教学话语内容"
}}
"""
        
        messages = [
            {"role": "system", "content": self.structural_prompt},
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
                'action_type': result.get('action_type', 'CONTINUE'),
                'action_params': result.get('action_params', {}),
                'teaching_discourse': result.get('teaching_discourse', '')
            }
        except:
            return {
                'action_type': 'CONTINUE',
                'action_params': {'node_id': current_node, 'reason': '默认继续'},
                'teaching_discourse': '让我们继续学习。'
            }

