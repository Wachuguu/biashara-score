"""
Amazon Bedrock LLM Client Wrapper
Calls Claude 3 Haiku when running in AWS, or returns mock classification locally when MOCK_AWS=true.
"""
import os
import json
from typing import Dict, Any

MOCK_MODE = os.getenv("MOCK_AWS", "true").lower() == "true"


class BedrockLLMClient:
    def __init__(self):
        self.mock = MOCK_MODE
        if not self.mock:
            import boto3
            self.bedrock = boto3.client("bedrock-runtime", region_name=os.getenv("AWS_REGION", "eu-west-1"))
            self.model_id = os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0")

    def classify_unclear_transaction(self, details: str, direction: str, amount: float) -> Dict[str, Any]:
        """
        Classifies an ambiguous transaction into a standardized category.
        """
        if self.mock:
            # Deterministic mock response for local testing
            return {
                "category": "INVENTORY" if direction == "OUT" else "SALES",
                "confidence": 0.90,
                "reason": "Mock offline classification"
            }

        prompt = f"""
        Classify this Kenyan M-Pesa transaction:
        Details: {details}
        Direction: {direction}
        Amount: KSh {amount}
        Allowed categories: [SALES, INVENTORY, UTILITIES, RENT, DEBT_RECOVERY, OWNER_DRAW, OTHER]
        Return JSON only: {{"category": "...", "confidence": 0.9, "reason": "..."}}
        """

        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 100,
            "messages": [{"role": "user", "content": prompt}]
        })

        response = self.bedrock.invoke_model(
            modelId=self.model_id,
            body=body,
            contentType="application/json"
        )
        response_body = json.loads(response["body"].read())
        return json.loads(response_body["content"][0]["text"])


llm_client = BedrockLLMClient()
