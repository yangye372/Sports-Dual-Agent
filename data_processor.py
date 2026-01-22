"""
数据接入与语义切分模块
"""
import json
import os
from typing import List, Dict
from langchain.text_splitter import RecursiveCharacterTextSplitter
import config


class DataProcessor:
    """数据处理器：将原始材料切分为语义chunks"""
    
    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50):
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", "。", "，", " ", ""]
        )
        self.chunks = []
    
    def process_text(
        self,
        text: str,
        source: str,
        module_hint: str = "",
        objective_hint: str = ""
    ) -> List[Dict]:
        """处理文本，生成chunks"""
        chunks = self.splitter.split_text(text)
        
        result = []
        for idx, chunk_text in enumerate(chunks):
            chunk = {
                "chunk_id": f"{source}_{idx}",
                "text": chunk_text,
                "module_hint": module_hint,
                "objective_hint": objective_hint,
                "source": source
            }
            result.append(chunk)
            self.chunks.append(chunk)
        
        return result
    
    def save_chunks(self, output_file: str = None):
        """保存chunks到JSONL文件"""
        output_file = output_file or config.CHUNKS_FILE
        
        # 确保目录存在
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            for chunk in self.chunks:
                f.write(json.dumps(chunk, ensure_ascii=False) + '\n')
        
        print(f"已保存 {len(self.chunks)} 个chunks到 {output_file}")
    
    def load_chunks(self, input_file: str = None) -> List[Dict]:
        """从JSONL文件加载chunks"""
        input_file = input_file or config.CHUNKS_FILE
        
        if not os.path.exists(input_file):
            return []
        
        chunks = []
        with open(input_file, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    chunks.append(json.loads(line))
        
        self.chunks = chunks
        return chunks

