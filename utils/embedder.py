"""
Qwen向量模型封装
"""
import os
from typing import List, Union
from openai import OpenAI
import numpy as np
import config


class QwenEmbedder:
    """Qwen向量模型封装类"""
    
    def __init__(self, model_name: str = "text-embedding-v4"):
        self.model_name = model_name
        self.client = OpenAI(
            api_key=config.DASHSCOPE_API_KEY,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
        )
    
    def encode(
        self,
        texts: Union[str, List[str]],
        batch_size: int = 10
    ) -> np.ndarray:
        """
        将文本编码为向量
        
        Args:
            texts: 单个文本或文本列表
            batch_size: 批处理大小
        
        Returns:
            numpy数组，形状为 (n, dim) 或 (dim,)
        """
        # 确保是列表
        if isinstance(texts, str):
            texts = [texts]
            single_text = True
        else:
            single_text = False
        
        all_embeddings = []
        
        # 批量处理
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i + batch_size]
            
            try:
                response = self.client.embeddings.create(
                    model=self.model_name,
                    input=batch_texts
                )
                
                # 提取向量
                batch_embeddings = [item.embedding for item in response.data]
                all_embeddings.extend(batch_embeddings)
                
            except Exception as e:
                print(f"向量编码失败: {str(e)}")
                # 返回零向量作为fallback
                # text-embedding-v4的维度是1536
                dim = 1536
                all_embeddings.extend([np.zeros(dim) for _ in batch_texts])
        
        embeddings_array = np.array(all_embeddings)
        
        # 如果是单个文本，返回一维数组
        if single_text:
            return embeddings_array[0]
        
        return embeddings_array

