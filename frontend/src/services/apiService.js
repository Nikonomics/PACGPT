// API Base URLs for different backends
const MEDICAID_API_URL = import.meta.env.VITE_MEDICAID_API_URL || 'http://localhost:3001'
const ALF_API_URL = import.meta.env.VITE_ALF_API_URL || 'http://localhost:8000'

// ============================================
// Medicaid Chatbot API Functions
// ============================================

export async function getMedicaidStates() {
  try {
    const response = await fetch(`${MEDICAID_API_URL}/api/medicaid/states`)

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }

    const data = await response.json()
    return data
  } catch (error) {
    console.error('Error fetching Medicaid states:', error)
    throw error
  }
}

export async function askMedicaidQuestion(state, question, conversationHistory = [], deepAnalysis = false) {
  try {
    const response = await fetch(`${MEDICAID_API_URL}/api/medicaid/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        state,
        question,
        conversationHistory,
        deepAnalysis
      })
    })

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }

    const data = await response.json()
    return data
  } catch (error) {
    console.error('Error asking Medicaid question:', error)
    throw error
  }
}

export async function getRevenueLevers(state) {
  try {
    const response = await fetch(`${MEDICAID_API_URL}/api/medicaid/revenue-levers/${encodeURIComponent(state)}`)

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }

    const data = await response.json()
    return data
  } catch (error) {
    console.error('Error fetching revenue levers:', error)
    throw error
  }
}

// ============================================
// Idaho ALF Chatbot API Functions
// ============================================

export async function askALFQuestion(question, conversationHistory = [], topK = 5, temperature = 0.3) {
  try {
    const response = await fetch(`${ALF_API_URL}/query`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        question,
        conversation_history: conversationHistory,
        top_k: topK,
        temperature
      })
    })

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }

    const data = await response.json()
    return data
  } catch (error) {
    console.error('Error asking ALF question:', error)
    throw error
  }
}

export async function getALFChunks() {
  try {
    const response = await fetch(`${ALF_API_URL}/chunks`)

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }

    const data = await response.json()
    return data
  } catch (error) {
    console.error('Error fetching ALF chunks:', error)
    throw error
  }
}

export async function getALFCategories() {
  try {
    const response = await fetch(`${ALF_API_URL}/categories`)

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }

    const data = await response.json()
    return data
  } catch (error) {
    console.error('Error fetching ALF categories:', error)
    throw error
  }
}

export async function checkALFHealth() {
  try {
    const response = await fetch(`${ALF_API_URL}/health`)

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }

    const data = await response.json()
    return data
  } catch (error) {
    console.error('Error checking ALF health:', error)
    throw error
  }
}
