import json
import logging
from typing import Dict, Any
from django.conf import settings
from openai import OpenAI

logger = logging.getLogger(__name__)

def score_lead_with_gpt(field_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Score a lead for spam likelihood using GPT.
    
    Args:
        field_dict: Dictionary containing lead fields (name, email, phone, etc.)
        
    Returns:
        Dict containing score (0-1) and reason
        
    Raises:
        ValueError: If GPT response is malformed
        Exception: For API or other errors
    """
    try:
        # Initialize OpenAI client
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        
        # Format fields for prompt
        field_text = "\n".join([
            f"{key}: {value}" 
            for key, value in field_dict.items() 
            if value and str(value).strip()
        ])
        
        # Construct the analysis prompt
        prompt = f"""Analyze this lead information for spam likelihood. Consider:
1. Name authenticity and formatting
2. Email validity and domain reputation
3. Phone number format and validity
4. Message quality and coherence
5. Overall data consistency
6. Any suspicious patterns

Lead Information:
{field_text}

Return a JSON object with:
- score: Number between 0 and 1 (higher = more likely spam). Strongly penalize leads with fake names, disposable email domains, VOIP numbers, missing fields, or vague/empty messages.
- reason: Explain the score briefly and clearly.

Example response format:
{{"score": 0.82, "reason": "Message was nonsensical and phone/email look suspicious"}}

Provide only the JSON response, no additional text."""

        # Call GPT API
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",  # Can be upgraded to "gpt-4" if needed
            messages=[
                {"role": "system", "content": "You are a lead quality analyzer that returns JSON responses."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,  # Lower temperature for more consistent scoring
            max_tokens=150,
            response_format={ "type": "json_object" }  # Ensure JSON response
        )
        
        # Extract response content
        response_text = response.choices[0].message.content
        
        try:
            # Parse and validate JSON response
            result = json.loads(response_text)
            
            # Validate required fields
            if not isinstance(result.get('score'), (int, float)):
                raise ValueError("Score must be a number")
            if not isinstance(result.get('reason'), str):
                raise ValueError("Reason must be a string")
            if not 0 <= float(result['score']) <= 1:
                raise ValueError("Score must be between 0 and 1")
            
            # Return validated result
            return {
                'score': float(result['score']),
                'reason': result['reason']
            }
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse GPT response: {response_text}")
            raise ValueError(f"Invalid JSON in GPT response: {str(e)}")
        except KeyError as e:
            logger.error(f"Missing required field in GPT response: {response_text}")
            raise ValueError(f"Missing field in GPT response: {str(e)}")
            
    except Exception as e:
        logger.error(f"Error in score_lead_with_gpt: {str(e)}")
        raise 