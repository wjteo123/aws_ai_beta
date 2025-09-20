# aws_embedder.py
"""
AWS Bedrock Embedder implementation for Agno framework.
This provides a custom embedder that uses AWS Bedrock Titan Text Embeddings V2.
"""

import json
import boto3
from typing import List, Union
from agno.embedder.base import Embedder


class BedrockEmbedder(Embedder):
    """AWS Bedrock Titan Text Embeddings V2 embedder for Agno."""
    
    def __init__(
        self,
        model_id: str = "amazon.titan-embed-text-v2:0",
        region: str = "us-east-1",
        dimensions: int = 1024,
        normalize: bool = True,
        **kwargs
    ):
        """
        Initialize Bedrock embedder.
        
        Args:
            model_id: Bedrock model ID for embeddings
            region: AWS region
            dimensions: Output embedding dimensions (256, 512, or 1024)
            normalize: Whether to normalize embeddings
        """
        super().__init__(**kwargs)
        self.model_id = model_id
        self.region = region
        self.dimensions = dimensions
        self.normalize = normalize
        
        # Initialize Bedrock client
        self.bedrock_client = boto3.client(
            'bedrock-runtime',
            region_name=region
        )
    
    def get_embedding(self, text: Union[str, List[str]]) -> Union[List[float], List[List[float]]]:
        """
        Generate embeddings for text(s) using AWS Bedrock.
        
        Args:
            text: Single text string or list of text strings
            
        Returns:
            Single embedding vector or list of embedding vectors
        """
        if isinstance(text, str):
            return self._get_single_embedding(text)
        else:
            return [self._get_single_embedding(t) for t in text]
    
    def _get_single_embedding(self, text: str) -> List[float]:
        """Generate embedding for a single text."""
        body = json.dumps({
            "inputText": text,
            "dimensions": self.dimensions,
            "normalize": self.normalize
        })
        
        try:
            response = self.bedrock_client.invoke_model(
                body=body,
                modelId=self.model_id,
                accept="application/json",
                contentType="application/json"
            )
            
            response_body = json.loads(response.get('body').read())
            return response_body['embedding']
            
        except Exception as e:
            raise RuntimeError(f"Failed to generate embedding: {e}")
    
    async def aget_embedding(self, text: Union[str, List[str]]) -> Union[List[float], List[List[float]]]:
        """Async version of get_embedding."""
        # For now, we'll use the sync version
        # In a production environment, you might want to use aioboto3
        return self.get_embedding(text)