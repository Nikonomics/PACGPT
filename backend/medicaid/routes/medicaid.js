import express from 'express';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { getRelevantDocuments } from '../services/documentFetcher.js';
import vectorSearch from '../services/vectorSearch.js';
import aiService from '../services/aiService.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const router = express.Router();

// Load Medicaid policies data
const policiesPath = path.join(__dirname, '../data/medicaid-policies-structured.json');
let medicaidPolicies = {};

try {
  const data = fs.readFileSync(policiesPath, 'utf8');
  medicaidPolicies = JSON.parse(data);
  console.log(`✓ Loaded Medicaid policies for ${Object.keys(medicaidPolicies).length} states`);
} catch (error) {
  console.error('Error loading Medicaid policies:', error);
}

// Using unified AI service with automatic fallback

// Initialize vector search (async, happens in background)
vectorSearch.initialize().catch(err => {
  console.error('Warning: Vector search initialization failed:', err.message);
  console.log('RAG features will not be available, but chatbot will continue to work');
});

// Fallback response generator when AI services are unavailable
function generateFallbackResponse(question, stateData, deepAnalysis) {
  const questionLower = question.toLowerCase();
  const stateName = stateData.stateName;
  
  // Find relevant policies based on keywords
  const relevantPolicies = stateData.policies.filter(policy => {
    const policyText = (policy.policyName + ' ' + policy.summary + ' ' + policy.sourceLanguage).toLowerCase();
    return questionLower.split(' ').some(word => 
      word.length > 3 && policyText.includes(word)
    );
  });

  let response = `## Understanding ${question}\n\n`;
  response += `Based on ${stateName}'s Medicaid policies, here's what I found:\n\n`;

  if (relevantPolicies.length > 0) {
    response += `## 📋 Relevant Policies\n\n`;
    
    relevantPolicies.slice(0, 5).forEach((policy, idx) => {
      response += `### ${idx + 1}. ${policy.policyName}\n`;
      response += `**Category:** ${policy.category}\n\n`;
      
      if (policy.summary && policy.summary !== 'None found') {
        response += `**Summary:** ${policy.summary}\n\n`;
      }
      
      if (policy.sourceLanguage && policy.sourceLanguage !== 'None found') {
        response += `**Details:** ${policy.sourceLanguage.substring(0, 200)}${policy.sourceLanguage.length > 200 ? '...' : ''}\n\n`;
      }
      
      if (policy.sources && policy.sources !== 'None found') {
        response += `**Sources:** ${policy.sources}\n\n`;
      }
      
      response += `---\n\n`;
    });
  } else {
    response += `## 📋 Available Policy Categories\n\n`;
    
    const categories = [...new Set(stateData.policies.map(p => p.category))];
    categories.forEach(category => {
      const categoryPolicies = stateData.policies.filter(p => p.category === category);
      response += `### ${category}\n`;
      response += `- ${categoryPolicies.length} policies available\n\n`;
    });
  }

  response += `## 💡 Key Information\n\n`;
  response += `- **Total Policies:** ${stateData.policies.length}\n`;
  response += `- **State:** ${stateName}\n`;
  response += `- **Analysis Mode:** ${deepAnalysis ? 'Deep Analysis (with additional documents)' : 'Standard Analysis'}\n\n`;

  response += `## ⚠️ Note\n\n`;
  response += `This response was generated from policy summaries. For the most detailed analysis, please try asking more specific questions about particular policy areas.\n\n`;

  response += `## 🔗 Related Topics You Might Want to Explore\n\n`;
  response += `- Payment methodology and rates\n`;
  response += `- Cost reporting requirements\n`;
  response += `- Quality incentive programs\n`;
  response += `- Specialized service add-ons\n\n`;

  response += `## 📚 Sources\n\n`;
  response += `All information is derived from ${stateName}'s official Medicaid policy documents and state plan amendments.`;

  return response;
}

// GET all states list
router.get('/states', (req, res) => {
  try {
    const states = Object.keys(medicaidPolicies).sort();
    res.json({ states });
  } catch (error) {
    console.error('Error fetching states:', error);
    res.status(500).json({ error: 'Failed to fetch states' });
  }
});

// GET policies for a specific state
router.get('/policies/:state', (req, res) => {
  try {
    const { state } = req.params;
    const stateData = medicaidPolicies[state];

    if (!stateData) {
      return res.status(404).json({ error: 'State not found' });
    }

    res.json(stateData);
  } catch (error) {
    console.error('Error fetching state policies:', error);
    res.status(500).json({ error: 'Failed to fetch state policies' });
  }
});

// POST chat endpoint
router.post('/chat', async (req, res) => {
  try {
    const { state, question, conversationHistory = [], deepAnalysis = false } = req.body;

    if (!state || !question) {
      return res.status(400).json({ error: 'State and question are required' });
    }

    const stateData = medicaidPolicies[state];

    if (!stateData) {
      return res.status(404).json({ error: 'State not found' });
    }

    // Build context from state policies
    const policiesContext = stateData.policies.map(policy => {
      return `Category: ${policy.category}
Policy: ${policy.policyName}
Summary: ${policy.summary}
Details: ${policy.sourceLanguage}
Sources: ${policy.sources}
Date: ${policy.dates}
---`;
    }).join('\n\n');

    let additionalContext = '';
    let fetchedDocuments = [];

    // If Deep Analysis is enabled, use RAG to search embeddings OR fetch documents
    if (deepAnalysis) {
      console.log(`[Deep Analysis] Searching for relevant content for ${state}...`);

      try {
        // Try RAG search first (if embeddings exist for this state)
        const ragResults = await vectorSearch.search(state, question, 5).catch(() => null);

        if (ragResults && ragResults.length > 0) {
          // Use RAG results
          console.log(`[RAG] Found ${ragResults.length} relevant chunks`);
          additionalContext = '\n\nRELEVANT REGULATORY CONTENT (from embeddings):\n\n';
          additionalContext += vectorSearch.formatContext(ragResults);

          // Add to fetched documents for citations
          fetchedDocuments = ragResults.map(r => ({
            type: r.metadata.doc_type,
            url: r.metadata.source,
            text: r.text.substring(0, 200) + '...',
            relevance: r.similarity
          }));
        } else {
          // Fall back to old document fetching method
          console.log(`[Deep Analysis] No RAG embeddings found, fetching documents...`);
          const documents = await getRelevantDocuments(state, 'all', medicaidPolicies);

          // Filter out errors and empty documents
          fetchedDocuments = documents.filter(doc => doc.type !== 'error' && doc.text.length > 100);

          if (fetchedDocuments.length > 0) {
            additionalContext = '\n\nADDITIONAL REGULATORY DOCUMENTS:\n\n';
            fetchedDocuments.forEach((doc, idx) => {
              additionalContext += `Document ${idx + 1}: ${doc.url}\n`;
              additionalContext += `Type: ${doc.type}\n`;
              additionalContext += `Content:\n${doc.text}\n\n`;
              additionalContext += '---\n\n';
            });

            console.log(`[Deep Analysis] Fetched ${fetchedDocuments.length} documents (${additionalContext.length} chars)`);
          } else {
            console.log(`[Deep Analysis] No documents could be fetched`);
          }
        }
      } catch (docError) {
        console.error('[Deep Analysis] Error:', docError);
        // Continue without documents rather than failing
      }
    }

    // Build conversation messages
    const messages = [
      ...conversationHistory,
      {
        role: 'user',
        content: question
      }
    ];

    // System prompt for Claude
    const systemPrompt = deepAnalysis
      ? `You are an experienced Medicaid policy consultant specializing in ${state}'s Fee-for-Service Nursing Facility Payment Policies.

CRITICAL FORMATTING REQUIREMENTS - YOU MUST FOLLOW THIS EXACT STRUCTURE:

**REQUIRED FORMAT EXAMPLE:**

## Understanding [Topic]
[Brief 1-2 sentence intro with context using bold for key terms]

## 📅 [Section Title About Timing/Process]
[1-2 sentence intro]

**[Subsection Title]:**
- Point 1
- Point 2

## 💰 [Section Title About Rates/Costs]
[1-2 sentence intro]

### 1. [Component Name]
**What it covers:**
- Item 1
- Item 2

**Important limits:**
- Limit 1
- Limit 2

### 2. [Next Component]
**What it covers:**
- Item 1

**Important notes:**
- Note 1

## 📊 [Section About Data/Tables]
[Intro text]

| Column 1 | Column 2 |
|----------|----------|
| Data 1   | Data 2   |
| Data 3   | Data 4   |

## ⚠️ [Critical Warning or Rule]
[Important rule or warning that facilities must follow]

## 💡 Key Takeaway
[Single most important point summarized clearly]

## 🔗 Related Topics You Might Want to Explore
- Topic 1
- Topic 2
- Topic 3
- Topic 4

## 📚 Sources
- Source name: URL
- Source name: URL

**MANDATORY RULES:**
1. EVERY major section header MUST start with an emoji (📅💰📊⚠️💡🔗📚)
2. Use "**What it covers:**" and "**Important limits:**" or "**Important notes:**" for subsections
3. Use markdown tables (| | format) for any structured data like timing, features, calculations
4. The ⚠️ section MUST be a critical rule or billing practice highlighted prominently
5. Keep paragraphs to max 2-3 sentences
6. Use bold for key terms throughout

DEEP ANALYSIS MODE: You have both policy summaries AND full regulatory documents.

Here are the Medicaid policy summaries for ${state}:

${policiesContext}

${additionalContext}`
      : `You are an experienced Medicaid policy consultant specializing in ${state}'s Fee-for-Service Nursing Facility Payment Policies.

CRITICAL FORMATTING REQUIREMENTS - YOU MUST FOLLOW THIS EXACT STRUCTURE:

**REQUIRED FORMAT EXAMPLE:**

## Understanding [Topic]
[Brief 1-2 sentence intro with context using bold for key terms]

## 📅 [Section Title About Timing/Process]
[1-2 sentence intro]

**[Subsection Title]:**
- Point 1
- Point 2

## 💰 [Section Title About Rates/Costs]
[1-2 sentence intro]

### 1. [Component Name]
**What it covers:**
- Item 1
- Item 2

**Important limits:**
- Limit 1
- Limit 2

### 2. [Next Component]
**What it covers:**
- Item 1

**Important notes:**
- Note 1

## 📊 [Section About Data/Tables]
[Intro text]

| Column 1 | Column 2 |
|----------|----------|
| Data 1   | Data 2   |
| Data 3   | Data 4   |

## ⚠️ [Critical Warning or Rule]
[Important rule or warning that facilities must follow]

## 💡 Key Takeaway
[Single most important point summarized clearly]

## 🔗 Related Topics You Might Want to Explore
- Topic 1
- Topic 2
- Topic 3
- Topic 4

## 📚 Sources
- Source name: URL
- Source name: URL

**MANDATORY RULES:**
1. EVERY major section header MUST start with an emoji (📅💰📊⚠️💡🔗📚)
2. Use "**What it covers:**" and "**Important limits:**" or "**Important notes:**" for subsections
3. Use markdown tables (| | format) for any structured data like timing, features, calculations
4. The ⚠️ section MUST be a critical rule or billing practice highlighted prominently
5. Keep paragraphs to max 2-3 sentences
6. Use bold for key terms throughout

Here are the Medicaid policies for ${state}:

${policiesContext}`;

    // Call AI API with extended context for deep analysis
    let assistantMessage;
    let aiProvider = 'fallback';
    
    try {
      const response = await aiService.analyzeContent(messages[0].content, {
        maxTokens: deepAnalysis ? 4096 : 2048,
        temperature: 0.1
      });

      assistantMessage = response.content;
      aiProvider = response.provider;
      console.log(`🤖 Medicaid analysis using ${response.provider}`);
    } catch (aiError) {
      console.warn('AI service unavailable, using fallback response:', aiError.message);
      
      // Provide a helpful fallback response based on the question
      assistantMessage = generateFallbackResponse(question, stateData, deepAnalysis);
      console.log('📝 Using fallback response for medicaid query');
    }

    // Extract sources/citations from the response
    const citations = [];
    stateData.policies.forEach(policy => {
      if (assistantMessage.toLowerCase().includes(policy.policyName.toLowerCase()) ||
          assistantMessage.toLowerCase().includes(policy.category.toLowerCase())) {
        citations.push({
          category: policy.category,
          policyName: policy.policyName,
          sources: policy.sources
        });
      }
    });

    // Add fetched document URLs to citations
    if (fetchedDocuments.length > 0) {
      fetchedDocuments.forEach(doc => {
        if (!citations.find(c => c.sources && c.sources.includes(doc.url))) {
          citations.push({
            category: 'Regulatory Document',
            policyName: 'Full Regulation',
            sources: doc.url
          });
        }
      });
    }

    res.json({
      response: assistantMessage,
      citations: citations.length > 0 ? citations : null,
      state: state,
      deepAnalysis: deepAnalysis,
      documentsFetched: fetchedDocuments.length
    });

  } catch (error) {
    console.error('Error in chat endpoint:', error);
    res.status(500).json({
      error: 'Failed to process chat request',
      details: error.message
    });
  }
});

// GET revenue levers for a specific state
router.get('/revenue-levers/:state', (req, res) => {
  try {
    const { state } = req.params;
    const stateData = medicaidPolicies[state];

    if (!stateData) {
      return res.status(404).json({ error: 'State not found' });
    }

    // Extract revenue-relevant policies
    const revenueLevers = {
      state: state,
      addOns: [],
      incentives: [],
      supplementalPayments: [],
      keyTimingFactors: {},
      revenueProtection: {},
      rateDeterminants: {}
    };

    // Process each policy
    stateData.policies.forEach(policy => {
      const policyName = policy.policyName.toLowerCase();
      const category = policy.category.toLowerCase();

      // Add-on services (ventilator, mental health, etc.)
      if (policyName.includes('ventilator') ||
          policyName.includes('mental health') ||
          policyName.includes('cognitive impairment') ||
          policyName.includes('high-need') ||
          policyName.includes('bariatric') ||
          policyName.includes('trach')) {
        revenueLevers.addOns.push({
          name: policy.policyName,
          summary: policy.summary,
          available: policy.summary && policy.summary !== 'None found',
          details: policy.sourceLanguage
        });
      }

      // Incentive payments
      if (category.includes('incentive') ||
          policyName.includes('quality') ||
          policyName.includes('pay for performance') ||
          policyName.includes('efficiency')) {
        revenueLevers.incentives.push({
          name: policy.policyName,
          summary: policy.summary,
          available: policy.summary && policy.summary !== 'None found',
          details: policy.sourceLanguage
        });
      }

      // Supplemental payments (new category for additional revenue streams)
      if (policyName.includes('supplemental') ||
          policyName.includes('outlier') ||
          policyName.includes('public facilities adjustment') ||
          policyName.includes('provider tax')) {
        revenueLevers.supplementalPayments.push({
          name: policy.policyName,
          summary: policy.summary,
          available: policy.summary && policy.summary !== 'None found',
          details: policy.sourceLanguage
        });
      }

      // Rebasing frequency (critical timing)
      if (policyName.includes('rebasing')) {
        revenueLevers.keyTimingFactors.rebasing = {
          frequency: policy.summary,
          details: policy.sourceLanguage
        };
      }

      // Cost report (critical for rate setting)
      if (policyName.includes('cost report')) {
        revenueLevers.keyTimingFactors.costReport = {
          type: policy.summary,
          details: policy.sourceLanguage
        };
      }

      // Basic payment approach
      if (policyName.includes('basic payment')) {
        revenueLevers.keyTimingFactors.paymentApproach = {
          method: policy.summary,
          details: policy.sourceLanguage
        };
      }

      // Inflation factor (impacts rate increases)
      if (policyName.includes('inflation')) {
        revenueLevers.keyTimingFactors.inflationFactor = {
          adjustment: policy.summary,
          details: policy.sourceLanguage
        };
      }

      // Bed-hold policy (revenue protection)
      if (policyName.includes('bed-hold') || policyName.includes('bed hold')) {
        revenueLevers.revenueProtection.bedHold = {
          policy: policy.summary,
          details: policy.sourceLanguage
        };
      }

      // Occupancy rate minimum (impacts rates)
      if (policyName.includes('occupancy')) {
        revenueLevers.revenueProtection.occupancyMinimum = {
          requirement: policy.summary,
          details: policy.sourceLanguage
        };
      }

      // Acuity system (impacts rates)
      if (policyName.includes('acuity')) {
        revenueLevers.rateDeterminants.acuitySystem = {
          system: policy.summary,
          details: policy.sourceLanguage
        };
      }

      // Peer grouping (impacts competitive position)
      if (policyName.includes('peer group')) {
        revenueLevers.rateDeterminants.peerGrouping = {
          methodology: policy.summary,
          details: policy.sourceLanguage
        };
      }

      // Geographic adjustments (location-based rate differences)
      if (policyName.includes('geographic')) {
        revenueLevers.rateDeterminants.geographicAdjustment = {
          adjustment: policy.summary,
          details: policy.sourceLanguage
        };
      }

      // Underlying basis for rates (fundamental rate structure)
      if (policyName.includes('underlying basis')) {
        revenueLevers.rateDeterminants.basisForRates = {
          basis: policy.summary,
          details: policy.sourceLanguage
        };
      }
    });

    // Calculate summary stats
    const availableAddOns = revenueLevers.addOns.filter(a => a.available).length;
    const availableIncentives = revenueLevers.incentives.filter(i => i.available).length;
    const availableSupplemental = revenueLevers.supplementalPayments.filter(s => s.available).length;

    // Helper to check if a value is meaningful (not "None found")
    const hasValue = (obj) => obj && obj.summary !== 'None found' && obj.frequency !== 'None found' && obj.type !== 'None found' && obj.policy !== 'None found' && obj.requirement !== 'None found' && obj.system !== 'None found' && obj.methodology !== 'None found' && obj.adjustment !== 'None found' && obj.basis !== 'None found';

    res.json({
      success: true,
      ...revenueLevers,
      summary: {
        totalAddOns: availableAddOns,
        totalIncentives: availableIncentives,
        totalSupplementalPayments: availableSupplemental,
        hasRebasingInfo: !!revenueLevers.keyTimingFactors.rebasing,
        hasBedHoldPolicy: hasValue(revenueLevers.revenueProtection.bedHold),
        hasOccupancyRequirement: hasValue(revenueLevers.revenueProtection.occupancyMinimum),
        hasAcuitySystem: hasValue(revenueLevers.rateDeterminants.acuitySystem),
        hasPeerGrouping: hasValue(revenueLevers.rateDeterminants.peerGrouping),
        hasGeographicAdjustment: hasValue(revenueLevers.rateDeterminants.geographicAdjustment)
      }
    });
  } catch (error) {
    console.error('Error fetching revenue levers:', error);
    res.status(500).json({ error: 'Failed to fetch revenue levers' });
  }
});

export default router;
