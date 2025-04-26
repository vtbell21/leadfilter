from django.test import TestCase
from django.conf import settings
import openai

class OpenAIConfigTest(TestCase):
    def test_openai_config(self):
        """Test that OpenAI API key is properly configured."""
        self.assertIsNotNone(settings.OPENAI_API_KEY)
        self.assertTrue(len(settings.OPENAI_API_KEY) > 0)
        
        # Set up the client
        client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
        
        try:
            # Try a simple API call
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": "Hello!"}],
                max_tokens=5
            )
            self.assertIsNotNone(response)
        except Exception as e:
            self.fail(f"OpenAI API call failed: {str(e)}") 