"""
Qwen API客户端
"""
import json
import time
import requests
from typing import Dict, List, Optional
import config


class QwenAPIClient:
    """Qwen API客户端封装"""
    
    def __init__(self):
        self.api_key = config.DASHSCOPE_API_KEY
        self.base_url = config.CHAT_COMPLETIONS_ENDPOINT
        self.model_name = config.MODEL_NAME
        self.temperature = config.TEMPERATURE
        self.max_retry = config.MAX_RETRY
        self.sleep_between = config.SLEEP_BETWEEN
        self.timeout = config.TIMEOUT_SEC
    
    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        response_format: Optional[Dict] = None
    ) -> Dict:
        """调用聊天完成API"""
        temperature = temperature or self.temperature
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": temperature
        }
        
        if response_format:
            payload["response_format"] = response_format
        
        for attempt in range(self.max_retry):
            try:
                response = requests.post(
                    self.base_url,
                    headers=headers,
                    json=payload,
                    timeout=self.timeout
                )
                response.raise_for_status()
                result = response.json()
                return result
            except requests.exceptions.Timeout as e:
                print(f"  API调用超时 (尝试 {attempt + 1}/{self.max_retry})")
                if attempt < self.max_retry - 1:
                    time.sleep(self.sleep_between * (attempt + 1))
                    continue
                raise Exception(f"API调用超时: {str(e)}")
            except requests.exceptions.RequestException as e:
                print(f"  API调用错误 (尝试 {attempt + 1}/{self.max_retry}): {str(e)}")
                if attempt < self.max_retry - 1:
                    time.sleep(self.sleep_between * (attempt + 1))
                    continue
                raise Exception(f"API调用失败: {str(e)}")
    
    def extract_json(self, text: str) -> Dict:
        """从文本中提取JSON"""
        try:
            # 尝试直接解析
            return json.loads(text)
        except:
            # 尝试提取JSON代码块
            import re
            json_match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(1))
            # 尝试提取大括号内容
            json_match = re.search(r'\{.*\}', text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(0))
            raise ValueError(f"无法从文本中提取JSON: {text[:200]}")

