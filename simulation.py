"""
对话仿真实验
"""
import json
import os
import uuid
from typing import Dict, List
from task_chain_generator import TaskChainGenerator
from rag_generator import RAGGenerator
from dual_agent_controller import DualAgentController
from logger import PathLogger
import config


class Simulation:
    """对话仿真实验"""
    
    def __init__(self):
        self.task_chain_gen = TaskChainGenerator()
        self.rag_gen = RAGGenerator()
        self.agent_controller = DualAgentController()
        self.logger = PathLogger()
    
    def simulate_session(
        self,
        module: str,
        target_task: str,
        scenario_trigger: str,
        agent_type: str,
        max_turns: int = 10
    ) -> Dict:
        """仿真单个会话"""
        session_id = str(uuid.uuid4())
        
        # 初始化日志
        self.logger.start_session(session_id, module, scenario_trigger, agent_type)
        
        # 生成任务链
        try:
            task_chain = self.task_chain_gen.generate_chain(target_task)
            preset_nodes = [node['name'] for node in task_chain['nodes']]
        except:
            preset_nodes = []
            task_chain = {'nodes': []}
        
        # 仿真对话
        current_node_idx = 0
        path_history = []
        conversation = []
        
        for turn in range(max_turns):
            if current_node_idx >= len(task_chain['nodes']):
                break
            
            current_node = task_chain['nodes'][current_node_idx]
            current_node_name = current_node['name']
            path_history.append(current_node_name)
            
            # 生成用户输入（模拟）
            user_input = self._generate_user_input(
                scenario_trigger,
                current_node_name,
                turn
            )
            
            # 场景检测
            scenario, issue = self.agent_controller.detect_scenario(
                user_input,
                current_node_name,
                target_task
            )
            
            # 智能体调控
            control_result = self.agent_controller.control(
                agent_type,
                scenario,
                issue,
                current_node_name,
                target_task,
                path_history,
                user_input
            )
            
            # RAG生成
            evidence = self.rag_gen.retrieve(
                current_node_name,
                target_task,
                user_input
            )
            
            generation_result = self.rag_gen.generate(
                evidence,
                control_result['action_type']
            )
            
            # 记录日志
            self.logger.log_turn(
                current_node_name,
                user_input,
                issue,
                control_result['action_type'],
                control_result['action_params'],
                generation_result['covered_nodes']
            )
            
            # 记录对话
            conversation.append({
                'turn': turn + 1,
                'user_input': user_input,
                'system_output': generation_result['output_text'],
                'action': control_result['action_type'],
                'current_node': current_node_name
            })
            
            # 根据动作更新路径
            if control_result['action_type'] == 'BACKTRACK':
                # 回退
                backtrack_node = control_result['action_params'].get('node_id')
                if backtrack_node:
                    # 找到回退位置
                    for i, node in enumerate(task_chain['nodes']):
                        if node['name'] == backtrack_node:
                            current_node_idx = i
                            break
            elif control_result['action_type'] == 'INSERT_BRIDGE':
                # 插入桥接节点（简化处理：继续当前节点）
                pass
            else:
                # CONTINUE或其他：推进到下一个节点
                current_node_idx += 1
        
        return {
            'session_id': session_id,
            'module': module,
            'target_task': target_task,
            'scenario': scenario_trigger,
            'agent_type': agent_type,
            'conversation': conversation,
            'path_history': path_history,
            'preset_nodes': preset_nodes
        }
    
    def _generate_user_input(
        self,
        scenario: str,
        current_node: str,
        turn: int
    ) -> str:
        """生成模拟用户输入"""
        if scenario == 'ambiguous':
            inputs = [
                "我不太明白这个是什么意思",
                "这个和之前学的有什么关系？",
                "我应该学什么？"
            ]
        elif scenario == 'misunderstanding':
            inputs = [
                "我觉得这个不对，应该是...",
                "我理解错了，重新解释一下",
                "这个概念我搞混了"
            ]
        elif scenario == 'cross-task':
            inputs = [
                "我想学另一个模块的内容",
                "能不能跳过这个直接学后面的？",
                "这个和运动系统有什么关系？"
            ]
        else:
            inputs = [
                "我理解了",
                "继续",
                "好的"
            ]
        
        return inputs[turn % len(inputs)]
    
    def run_batch_simulation(self) -> List[Dict]:
        """批量运行仿真实验"""
        results = []
        
        for module in config.SIMULATION_CONFIG['modules']:
            for scenario in config.SIMULATION_CONFIG['scenarios']:
                for agent_type in config.SIMULATION_CONFIG['agents']:
                    for i in range(config.SIMULATION_CONFIG['sessions_per_agent']):
                        # 生成目标任务（简化：使用模块名）
                        target_task = f"{module}的核心概念"
                        
                        print(f"运行仿真: {module} - {scenario} - {agent_type} - {i+1}")
                        
                        result = self.simulate_session(
                            module,
                            target_task,
                            scenario,
                            agent_type
                        )
                        
                        results.append(result)
                        
                        # 保存单个会话结果
                        output_file = os.path.join(
                            config.SIM_DATA_DIR,
                            f"{result['session_id']}.json"
                        )
                        os.makedirs(os.path.dirname(output_file), exist_ok=True)
                        with open(output_file, 'w', encoding='utf-8') as f:
                            json.dump(result, f, ensure_ascii=False, indent=2)
        
        # 保存汇总结果
        summary_file = os.path.join(config.SIM_DATA_DIR, "summary.json")
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump({
                'total_sessions': len(results),
                'sessions': [r['session_id'] for r in results]
            }, f, ensure_ascii=False, indent=2)
        
        return results

