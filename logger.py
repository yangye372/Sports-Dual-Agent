"""
证据化日志系统
"""
import json
import os
from datetime import datetime
from typing import Dict, Optional, List
import config


class PathLogger:
    """路径调控日志记录器"""
    
    def __init__(self, log_file: str = None):
        self.log_file = log_file or os.path.join(config.LOG_DIR, "path_log.jsonl")
        os.makedirs(os.path.dirname(self.log_file), exist_ok=True)
        self.session_id = None
        self.turn_id = 0
    
    def start_session(
        self,
        session_id: str,
        module: str,
        scenario_type: str,
        agent_type: str
    ):
        """开始新会话"""
        self.session_id = session_id
        self.turn_id = 0
        self.module = module
        self.scenario_type = scenario_type
        self.agent_type = agent_type
    
    def log_turn(
        self,
        current_node: str,
        user_input: str,
        detected_issue: str,
        action_type: str,
        action_params: Dict,
        covered_nodes: List[str],
        model_version: str = None,
        temperature: float = None
    ):
        """记录一轮交互"""
        self.turn_id += 1
        
        log_entry = {
            'session_id': self.session_id,
            'module': self.module,
            'scenario_type': self.scenario_type,
            'agent_type': self.agent_type,
            'turn_id': self.turn_id,
            'current_node': current_node,
            'user_input': user_input,
            'detected_issue': detected_issue,
            'action_type': action_type,
            'inserted_nodes': action_params.get('node_id', []),
            'backtrack_to': action_params.get('node_id') if action_type == 'BACKTRACK' else None,
            'simplify_level': action_params.get('level') if action_type == 'SIMPLIFY_PROMPT' else None,
            'covered_nodes_in_output': covered_nodes,
            'timestamp': datetime.now().isoformat(),
            'model_version': model_version or config.MODEL_NAME,
            'temperature': temperature or config.TEMPERATURE
        }
        
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
    
    def load_logs(self) -> list:
        """加载所有日志"""
        if not os.path.exists(self.log_file):
            return []
        
        logs = []
        with open(self.log_file, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    logs.append(json.loads(line))
        
        return logs
    
    def get_session_logs(self, session_id: str) -> list:
        """获取特定会话的日志"""
        all_logs = self.load_logs()
        return [log for log in all_logs if log.get('session_id') == session_id]

