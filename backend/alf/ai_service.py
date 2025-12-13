"""
Unified AI Service for Idaho ALF RegNavigator
Provides fallback between Anthropic and OpenAI with automatic switching.
"""
import os
from dotenv import load_dotenv
load_dotenv()

import anthropic
import openai
from typing import Dict, Any, Optional


class AIService:
    """Unified AI service with automatic fallback between providers."""
    
    def __init__(self):
        self.providers = {
            'openai': {
                'client': openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY')),
                'available': bool(os.getenv('OPENAI_API_KEY')),
                'priority': 1
            },
            'anthropic': {
                'client': anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY')),
                'available': bool(os.getenv('ANTHROPIC_API_KEY')),
                'priority': 2
            }
        }
        
        self.current_provider = None
        self.failed_providers = set()
        self.request_counts = {}
        self.last_reset = 0
        
        # Initialize with primary provider
        for provider_name, provider_info in sorted(
            self.providers.items(), 
            key=lambda x: x[1]['priority']
        ):
            if provider_info['available']:
                self.current_provider = provider_name
                break
    
    def _get_next_provider(self) -> Optional[str]:
        """Get the next available provider."""
        available_providers = [
            (name, info) for name, info in self.providers.items()
            if info['available'] and name not in self.failed_providers
        ]
        
        if not available_providers:
            return None
            
        # Return the highest priority available provider
        return sorted(available_providers, key=lambda x: x[1]['priority'])[0][0]
    
    def _mark_provider_failed(self, provider: str):
        """Mark a provider as failed."""
        self.failed_providers.add(provider)
        print(f"🚨 AI provider {provider} marked as failed")
    
    def _mark_provider_success(self, provider: str):
        """Mark a provider as successful."""
        self.failed_providers.discard(provider)
        if provider == 'openai':
            self.current_provider = 'openai'
    
    def analyze_content(self, prompt: str, options: Dict[str, Any] = None) -> Dict[str, Any]:
        """Analyze content using available AI providers with automatic fallback."""
        if options is None:
            options = {}
            
        max_tokens = options.get('maxTokens', 1024)
        temperature = options.get('temperature', 0.7)
        model = options.get('model', None)
        
        last_error = None
        
        # Try current provider first
        if self.current_provider and self.current_provider not in self.failed_providers:
            try:
                return self._call_provider(
                    self.current_provider, 
                    prompt, 
                    max_tokens, 
                    temperature, 
                    model
                )
            except Exception as error:
                last_error = error
                self._mark_provider_failed(self.current_provider)
                print(f"Primary provider {self.current_provider} failed: {error}")
        
        # Try other available providers
        for provider_name, provider_info in self.providers.items():
            if (provider_info['available'] and 
                provider_name not in self.failed_providers and 
                provider_name != self.current_provider):
                try:
                    result = self._call_provider(
                        provider_name, 
                        prompt, 
                        max_tokens, 
                        temperature, 
                        model
                    )
                    self._mark_provider_success(provider_name)
                    return result
                except Exception as error:
                    last_error = error
                    self._mark_provider_failed(provider_name)
                    print(f"Provider {provider_name} failed: {error}")
        
        # All providers failed
        raise Exception(f"All AI providers failed: {last_error}")
    
    def _call_provider(self, provider: str, prompt: str, max_tokens: int, temperature: float, model: Optional[str]) -> Dict[str, Any]:
        """Call a specific AI provider."""
        if provider == 'openai':
            return self._call_openai(prompt, max_tokens, temperature, model)
        elif provider == 'anthropic':
            return self._call_anthropic(prompt, max_tokens, temperature, model)
        else:
            raise ValueError(f"Unknown provider: {provider}")
    
    def _call_openai(self, prompt: str, max_tokens: int, temperature: float, model: Optional[str]) -> Dict[str, Any]:
        """Call OpenAI API."""
        client = self.providers['openai']['client']
        
        response = client.chat.completions.create(
            model=model or 'gpt-4o',
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[{'role': 'user', 'content': prompt}]
        )
        
        return {
            'content': response.choices[0].message.content,
            'provider': 'openai'
        }
    
    def _call_anthropic(self, prompt: str, max_tokens: int, temperature: float, model: Optional[str]) -> Dict[str, Any]:
        """Call Anthropic API."""
        client = self.providers['anthropic']['client']
        
        response = client.messages.create(
            model=model or 'claude-sonnet-4-20250514',
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[{'role': 'user', 'content': prompt}]
        )
        
        return {
            'content': response.content[0].text,
            'provider': 'anthropic'
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get service statistics."""
        return {
            'current_provider': self.current_provider,
            'failed_providers': list(self.failed_providers),
            'available_providers': [
                name for name, info in self.providers.items() 
                if info['available'] and name not in self.failed_providers
            ]
        }


# Global instance
ai_service = AIService()