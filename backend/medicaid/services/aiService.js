/**
 * Unified AI Service with Anthropic and OpenAI Support
 * Automatic fallback between providers
 */

import Anthropic from '@anthropic-ai/sdk'
import OpenAI from 'openai'

class AIService {
  constructor() {
    this.providers = {
      openai: {
        client: null,
        available: false,
        priority: 1
      },
      anthropic: {
        client: null,
        available: false,
        priority: 2
      }
    }
    
    // Initialize providers only if API keys are available
    if (process.env.OPENAI_API_KEY) {
      try {
        this.providers.openai.client = new OpenAI({
          apiKey: process.env.OPENAI_API_KEY
        })
        this.providers.openai.available = true
        console.log('✓ OpenAI client initialized')
      } catch (error) {
        console.error('Failed to initialize OpenAI client:', error.message)
      }
    }
    
    if (process.env.ANTHROPIC_API_KEY) {
      try {
        this.providers.anthropic.client = new Anthropic({
          apiKey: process.env.ANTHROPIC_API_KEY
        })
        this.providers.anthropic.available = true
        console.log('✓ Anthropic client initialized')
      } catch (error) {
        console.error('Failed to initialize Anthropic client:', error.message)
      }
    }
    
    this.currentProvider = null
    this.failedProviders = new Set()
    this.requestCounts = new Map()
    this.lastReset = Date.now()
    
    // Reset counters every hour
    setInterval(() => {
      this.requestCounts.clear()
      this.lastReset = Date.now()
    }, 60 * 60 * 1000)
  }

  getCurrentProvider() {
    if (this.currentProvider && this.providers[this.currentProvider].available && !this.failedProviders.has(this.currentProvider)) {
      return this.currentProvider
    }
    return this.getNextAvailableProvider()
  }

  getNextAvailableProvider() {
    // Sort providers by priority
    const sortedProviders = Object.entries(this.providers)
      .filter(([name, config]) => config.available && !this.failedProviders.has(name))
      .sort((a, b) => a[1].priority - b[1].priority)

    if (sortedProviders.length === 0) {
      console.error('❌ No AI providers available. Please check your API keys.')
      throw new Error('No AI providers available. Please check your API keys.')
    }

    this.currentProvider = sortedProviders[0][0]
    console.log(`🔄 Using AI provider: ${this.currentProvider}`)
    return this.currentProvider
  }

  markProviderFailed(provider) {
    this.failedProviders.add(provider)
    console.warn(`🚨 AI provider ${provider} marked as failed`)
  }

  markProviderSuccess(provider) {
    this.failedProviders.delete(provider)
    // Reset to primary provider if it's working again
    if (provider === 'openai') {
      this.currentProvider = 'openai'
    }
  }

  incrementRequestCount(provider) {
    const count = this.requestCounts.get(provider) || 0
    this.requestCounts.set(provider, count + 1)
  }

  getRequestCount(provider) {
    return this.requestCounts.get(provider) || 0
  }

  getStats() {
    return {
      providers: Object.keys(this.providers).map(name => ({
        name,
        available: this.providers[name].available,
        failed: this.failedProviders.has(name),
        requestCount: this.getRequestCount(name)
      })),
      currentProvider: this.currentProvider,
      failedProviders: Array.from(this.failedProviders),
      lastReset: this.lastReset
    }
  }

  async analyzeContent(prompt, options = {}) {
    const maxRetries = 3
    let lastError

    for (let attempt = 0; attempt < maxRetries; attempt++) {
      try {
        const provider = this.getCurrentProvider()
        const result = await this.callProvider(provider, prompt, options)
        
        this.markProviderSuccess(provider)
        this.incrementRequestCount(provider)
        
        return {
          ...result,
          provider,
          attempt: attempt + 1
        }
      } catch (error) {
        lastError = error
        console.warn(`AI attempt ${attempt + 1} failed:`, error.message)
        
        if (error.message.includes('rate limit') || error.message.includes('quota')) {
          this.markProviderFailed(this.currentProvider)
        }
        
        if (attempt === maxRetries - 1) {
          throw lastError
        }
      }
    }
  }

  async callProvider(provider, prompt, options) {
    const config = this.providers[provider]
    
    if (!config.available) {
      throw new Error(`Provider ${provider} is not available`)
    }

    switch (provider) {
      case 'anthropic':
        return await this.callAnthropic(prompt, options)
      case 'openai':
        return await this.callOpenAI(prompt, options)
      default:
        throw new Error(`Unknown provider: ${provider}`)
    }
  }

  async callAnthropic(prompt, options) {
    const response = await this.providers.anthropic.client.messages.create({
      model: options.model || 'claude-3-5-sonnet-20241022',
      max_tokens: options.maxTokens || 1000,
      temperature: options.temperature || 0.1,
      messages: [{
        role: 'user',
        content: prompt
      }]
    })

    return {
      content: response.content[0].text,
      usage: response.usage,
      model: response.model
    }
  }

  async callOpenAI(prompt, options) {
    const response = await this.providers.openai.client.chat.completions.create({
      model: options.model || 'gpt-4o',
      max_tokens: options.maxTokens || 1000,
      temperature: options.temperature || 0.1,
      messages: [{
        role: 'user',
        content: prompt
      }]
    })

    return {
      content: response.choices[0].message.content,
      usage: response.usage,
      model: response.model
    }
  }
}

export default new AIService()
