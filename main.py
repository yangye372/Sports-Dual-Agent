"""
主程序：完整的系统流程
"""
import os
import sys
from data_processor import DataProcessor
from kg_builder import KGBuilder
from task_chain_generator import TaskChainGenerator
from simulation import Simulation
import config


def build_knowledge_graph():
    """构建知识图谱"""
    print("=" * 50)
    print("阶段1: 构建知识图谱")
    print("=" * 50)
    
    # 加载chunks
    processor = DataProcessor()
    chunks = processor.load_chunks()
    
    if not chunks:
        print("错误：未找到chunks数据，请先运行 generate_data.py")
        return False
    
    print(f"加载了 {len(chunks)} 个chunks")
    
    # 构建知识图谱（如果已有数据则跳过抽取）
    with KGBuilder() as kg_builder:
        kg_builder.build_from_chunks(chunks, skip_existing=True)
        kg_builder.export_graph()
    
    print("知识图谱构建完成！")
    return True


def generate_task_chains():
    """生成任务链"""
    print("=" * 50)
    print("阶段2: 生成任务链")
    print("=" * 50)
    
    with TaskChainGenerator() as chain_gen:
        for module in config.MODULES:
            target_objective = f"掌握{module}的核心内容"
            print(f"\n生成任务链: {target_objective}")
            
            try:
                chain = chain_gen.generate_chain(target_objective)
                
                if not chain.get('nodes'):
                    print(f"  警告: 生成的任务链为空，尝试使用模块下的所有节点")
                    # 如果任务链为空，尝试直接获取模块下的节点
                    from neo4j import GraphDatabase
                    driver = GraphDatabase.driver(
                        config.NEO4J_URI,
                        auth=(config.NEO4J_USER, config.NEO4J_PASSWORD)
                    )
                    with driver.session() as session:
                        result = session.run("""
                            MATCH (n)
                            WHERE n.module CONTAINS $module
                            RETURN DISTINCT n.name as name, n.id as id, n.type as type,
                                   n.definition as definition, n.module as module
                            LIMIT 20
                        """, module=module)
                        
                        nodes = []
                        for record in result:
                            nodes.append({
                                'id': record['id'],
                                'name': record['name'],
                                'type': record['type'],
                                'definition': record.get('definition', ''),
                                'module': record.get('module', '')
                            })
                        
                        if nodes:
                            chain = chain_gen._instantiate_chain(nodes, target_objective, {})
                            print(f"  找到 {len(nodes)} 个节点")
                    driver.close()
                
                if chain.get('nodes'):
                    output_file = os.path.join(
                        config.TASK_CHAIN_DIR,
                        f"{module.replace(' ', '_')}_chain.json"
                    )
                    chain_gen.save_chain(chain, output_file)
                    print(f"  ✓ 任务链已保存: {output_file} (包含 {len(chain.get('nodes', []))} 个节点)")
                else:
                    print(f"  ✗ 无法生成任务链：知识图谱中未找到相关节点")
            except Exception as e:
                print(f"  ✗ 生成任务链失败: {str(e)}")
                import traceback
                traceback.print_exc()
    
    print("\n任务链生成完成！")


def run_simulation():
    """运行仿真实验"""
    print("=" * 50)
    print("阶段3: 运行仿真实验")
    print("=" * 50)
    
    sim = Simulation()
    results = sim.run_batch_simulation()
    
    print(f"仿真实验完成！共运行 {len(results)} 个会话")
    return results


def evaluate_results():
    """评估结果"""
    print("=" * 50)
    print("阶段4: 评估结果")
    print("=" * 50)
    
    evaluator = Evaluator()
    
    # 构建预设节点映射和目标文本映射（简化版）
    preset_nodes_map = {
        'Movement Systems': ['骨骼系统', '肌肉系统', '神经系统', '运动技能学习'],
        'Health and Aerobic Training Design': ['有氧代谢', '最大摄氧量', '有氧训练设计', '训练计划']
    }
    
    target_texts_map = {
        'Movement Systems': [
            '运动系统是人体进行各种运动的基础',
            '骨骼系统支撑身体、保护内脏器官',
            '肌肉通过收缩产生力量',
            '神经系统控制肌肉的收缩'
        ],
        'Health and Aerobic Training Design': [
            '有氧训练是提高心肺功能的重要方法',
            '最大摄氧量是评价有氧能力的重要指标',
            '有氧训练的设计需要考虑训练强度、频率、时间和类型',
            '规律的有氧训练可以降低慢性病风险'
        ]
    }
    
    # 评估所有会话
    results = evaluator.evaluate_all_sessions(preset_nodes_map, target_texts_map)
    
    # 导出结果
    output_file = os.path.join(config.DATA_DIR, "evaluation_results.json")
    evaluator.export_results(results, output_file)
    
    # 打印摘要
    summary = results['summary']
    print("\n评估摘要:")
    print(f"总会话数: {summary.get('total_sessions', 0)}")
    print(f"平均结构匹配度 (SMD): {summary.get('avg_smd', 0):.3f}")
    print(f"平均策略标签频率 (STF): {summary.get('avg_stf', 0):.3f}")
    print(f"平均目标一致性 (GA): {summary.get('avg_ga', 0):.3f}")
    
    print("\n按智能体类型:")
    for agent_type, stats in summary.get('by_agent', {}).items():
        print(f"  {agent_type}: SMD={stats['avg_smd']:.3f}, STF={stats['avg_stf']:.3f}, GA={stats['avg_ga']:.3f}")
    
    print("\n按场景类型:")
    for scenario, stats in summary.get('by_scenario', {}).items():
        print(f"  {scenario}: SMD={stats['avg_smd']:.3f}, STF={stats['avg_stf']:.3f}, GA={stats['avg_ga']:.3f}")
    
    print(f"\n详细结果已保存到: {output_file}")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='体育通识教学系统')
    parser.add_argument('--step', type=str, choices=['all', 'kg', 'chain', 'sim', 'eval'],
                       default='all', help='执行步骤')
    parser.add_argument('--skip-kg', action='store_true', help='跳过知识图谱构建')
    
    args = parser.parse_args()
    
    try:
        if args.step == 'all':
            if not args.skip_kg:
                if not build_knowledge_graph():
                    return
            generate_task_chains()
            run_simulation()
        elif args.step == 'kg':
            build_knowledge_graph()
        elif args.step == 'chain':
            generate_task_chains()
        elif args.step == 'sim':
            run_simulation()
        
        print("\n" + "=" * 50)
        print("所有步骤完成！")
        print("=" * 50)
        
    except Exception as e:
        print(f"错误: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()

