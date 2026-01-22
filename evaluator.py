"""
评估指标计算模块
"""
import json
import os
from typing import List, Dict
import numpy as np
from logger import PathLogger
from utils.embedder import QwenEmbedder
import config


class Evaluator:
    """评估器：计算SMD、STF、GA指标"""
    
    def __init__(self):
        self.embedder = QwenEmbedder(model_name="text-embedding-v4")
        self.logger = PathLogger()
    
    def calculate_smd(
        self,
        covered_nodes: List[str],
        preset_nodes: List[str]
    ) -> float:
        """计算结构匹配度（Structural Match Degree）"""
        if not preset_nodes:
            return 0.0
        
        covered_set = set(covered_nodes)
        preset_set = set(preset_nodes)
        
        return len(covered_set & preset_set) / len(preset_set)
    
    def calculate_stf(self, logs: List[Dict]) -> float:
        """计算策略标签频率（Strategy Tagging Frequency）"""
        if not logs:
            return 0.0
        
        n_insert = sum(1 for log in logs if log.get('action_type') in [
            'INSERT_BRIDGE', 'BACKTRACK', 'SIMPLIFY_PROMPT', 'LOCAL_REORDER'
        ])
        n_turn = len(logs)
        
        return n_insert / n_turn if n_turn > 0 else 0.0
    
    def calculate_ga(
        self,
        output_texts: List[str],
        target_texts: List[str]
    ) -> float:
        """计算目标一致性（Goal Alignment）"""
        if not output_texts or not target_texts:
            return 0.0
        
        # 确保长度一致
        min_len = min(len(output_texts), len(target_texts))
        output_texts = output_texts[:min_len]
        target_texts = target_texts[:min_len]
        
        # 计算嵌入
        output_embeddings = self.embedder.encode(output_texts)
        target_embeddings = self.embedder.encode(target_texts)
        
        # 计算余弦相似度
        similarities = []
        for i in range(min_len):
            cos_sim = np.dot(output_embeddings[i], target_embeddings[i]) / (
                np.linalg.norm(output_embeddings[i]) * np.linalg.norm(target_embeddings[i])
            )
            similarities.append(cos_sim)
        
        return np.mean(similarities)
    
    def evaluate_session(
        self,
        session_id: str,
        preset_nodes: List[str],
        target_texts: List[str]
    ) -> Dict:
        """评估单个会话"""
        logs = self.logger.get_session_logs(session_id)
        
        if not logs:
            return {
                'session_id': session_id,
                'smd': 0.0,
                'stf': 0.0,
                'ga': 0.0
            }
        
        # 收集覆盖节点和输出文本
        covered_nodes = []
        output_texts = []
        
        for log in logs:
            covered_nodes.extend(log.get('covered_nodes_in_output', []))
            # 从日志中提取输出文本（如果有）
            if 'output_text' in log:
                output_texts.append(log['output_text'])
        
        smd = self.calculate_smd(covered_nodes, preset_nodes)
        stf = self.calculate_stf(logs)
        ga = self.calculate_ga(output_texts, target_texts) if output_texts else 0.0
        
        return {
            'session_id': session_id,
            'smd': float(smd),
            'stf': float(stf),
            'ga': float(ga),
            'n_turns': len(logs)
        }
    
    def evaluate_all_sessions(
        self,
        preset_nodes_map: Dict[str, List[str]],
        target_texts_map: Dict[str, List[str]]
    ) -> Dict:
        """评估所有会话"""
        all_logs = self.logger.load_logs()
        session_ids = set(log.get('session_id') for log in all_logs)
        
        results = []
        for session_id in session_ids:
            # 获取会话的模块信息
            session_logs = self.logger.get_session_logs(session_id)
            if not session_logs:
                continue
            
            module = session_logs[0].get('module', '')
            preset_nodes = preset_nodes_map.get(module, [])
            target_texts = target_texts_map.get(module, [])
            
            result = self.evaluate_session(session_id, preset_nodes, target_texts)
            result['module'] = module
            result['agent_type'] = session_logs[0].get('agent_type', '')
            result['scenario_type'] = session_logs[0].get('scenario_type', '')
            results.append(result)
        
        # 统计汇总
        summary = self._summarize_results(results)
        
        return {
            'individual_results': results,
            'summary': summary
        }
    
    def _summarize_results(self, results: List[Dict]) -> Dict:
        """汇总结果"""
        if not results:
            return {}
        
        summary = {
            'total_sessions': len(results),
            'avg_smd': np.mean([r['smd'] for r in results]),
            'avg_stf': np.mean([r['stf'] for r in results]),
            'avg_ga': np.mean([r['ga'] for r in results]),
            'by_agent': {},
            'by_scenario': {},
            'by_module': {}
        }
        
        # 按智能体类型统计
        for agent_type in config.AGENT_TYPES:
            agent_results = [r for r in results if r.get('agent_type') == agent_type]
            if agent_results:
                summary['by_agent'][agent_type] = {
                    'count': len(agent_results),
                    'avg_smd': np.mean([r['smd'] for r in agent_results]),
                    'avg_stf': np.mean([r['stf'] for r in agent_results]),
                    'avg_ga': np.mean([r['ga'] for r in agent_results])
                }
        
        # 按场景类型统计
        for scenario in config.SCENARIO_TYPES:
            scenario_results = [r for r in results if r.get('scenario_type') == scenario]
            if scenario_results:
                summary['by_scenario'][scenario] = {
                    'count': len(scenario_results),
                    'avg_smd': np.mean([r['smd'] for r in scenario_results]),
                    'avg_stf': np.mean([r['stf'] for r in scenario_results]),
                    'avg_ga': np.mean([r['ga'] for r in scenario_results])
                }
        
        # 按模块统计
        for module in config.MODULES:
            module_results = [r for r in results if r.get('module') == module]
            if module_results:
                summary['by_module'][module] = {
                    'count': len(module_results),
                    'avg_smd': np.mean([r['smd'] for r in module_results]),
                    'avg_stf': np.mean([r['stf'] for r in module_results]),
                    'avg_ga': np.mean([r['ga'] for r in module_results])
                }
        
        return summary
    
    def export_results(self, results: Dict, output_file: str):
        """导出评估结果"""
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

