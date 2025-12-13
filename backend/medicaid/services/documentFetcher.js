import fetch from 'node-fetch';
import NodeCache from 'node-cache';
import * as cheerio from 'cheerio';

// Cache for 7 days (regulatory documents don't change often)
const documentCache = new NodeCache({ stdTTL: 604800, checkperiod: 86400 });

/**
 * Fetch and parse a document from a URL
 * Returns clean text content
 */
export async function fetchDocument(url) {
  // Check cache first
  const cached = documentCache.get(url);
  if (cached) {
    console.log(`[DocumentFetcher] Cache hit for: ${url}`);
    return cached;
  }

  try {
    console.log(`[DocumentFetcher] Fetching: ${url}`);

    const response = await fetch(url, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
      },
      timeout: 15000
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    const contentType = response.headers.get('content-type') || '';

    let documentText = '';
    let documentType = 'unknown';

    // Handle HTML pages
    if (contentType.includes('text/html')) {
      const html = await response.text();
      documentText = extractTextFromHtml(html);
      documentType = 'html';
    }
    // Handle PDF (we'll note it but not parse it - would need pdf-parse library)
    else if (contentType.includes('application/pdf')) {
      documentText = '[PDF Document - Full text parsing requires download]';
      documentType = 'pdf';
    }
    // Handle plain text
    else if (contentType.includes('text/plain')) {
      documentText = await response.text();
      documentType = 'text';
    }
    // Other formats
    else {
      documentText = `[Document type: ${contentType} - May require specialized parsing]`;
      documentType = contentType;
    }

    const result = {
      url,
      text: documentText,
      type: documentType,
      fetchedAt: new Date().toISOString(),
      size: documentText.length
    };

    // Cache the result
    documentCache.set(url, result);

    console.log(`[DocumentFetcher] Cached document (${documentType}, ${documentText.length} chars)`);

    return result;

  } catch (error) {
    console.error(`[DocumentFetcher] Error fetching ${url}:`, error.message);

    // Return error info but don't cache errors
    return {
      url,
      text: '',
      type: 'error',
      error: error.message,
      fetchedAt: new Date().toISOString()
    };
  }
}

/**
 * Fetch multiple documents in parallel
 */
export async function fetchDocuments(urls, maxConcurrent = 3) {
  const results = [];

  // Process in batches to avoid overwhelming servers
  for (let i = 0; i < urls.length; i += maxConcurrent) {
    const batch = urls.slice(i, i + maxConcurrent);
    const batchResults = await Promise.all(
      batch.map(url => fetchDocument(url))
    );
    results.push(...batchResults);
  }

  return results;
}

/**
 * Extract clean text from HTML
 */
function extractTextFromHtml(html) {
  const $ = cheerio.load(html);

  // Remove script and style elements
  $('script, style, nav, footer, header, aside, .navigation, .menu, .sidebar').remove();

  // Get main content - try common content containers first
  let contentElement = $('main, article, .content, .main-content, #content, #main').first();

  // Fallback to body if no main content found
  if (contentElement.length === 0) {
    contentElement = $('body');
  }

  // Extract text and clean it up
  let text = contentElement.text();

  // Clean up whitespace
  text = text
    .replace(/\s+/g, ' ')
    .replace(/\n\s*\n/g, '\n')
    .trim();

  // Limit to reasonable size (Claude has limits)
  const MAX_LENGTH = 100000; // 100k chars
  if (text.length > MAX_LENGTH) {
    text = text.substring(0, MAX_LENGTH) + '\n\n[Document truncated due to length]';
  }

  return text;
}

/**
 * Get documents relevant to a specific policy
 */
export async function getRelevantDocuments(state, policyCategory, medicaidPolicies) {
  const stateData = medicaidPolicies[state];
  if (!stateData) return [];

  // Find policies matching the category
  const relevantPolicies = stateData.policies.filter(p =>
    p.category === policyCategory || policyCategory === 'all'
  );

  // Extract unique URLs from these policies
  const urls = new Set();
  relevantPolicies.forEach(policy => {
    if (policy.sources && policy.sources !== 'See notes below' && policy.sources !== 'None found') {
      const urlMatches = policy.sources.match(/https?:\/\/[^\s]+/g);
      if (urlMatches) {
        urlMatches.forEach(url => {
          urls.add(url.replace(/[.,;:)]$/, ''));
        });
      }
    }
  });

  // Fetch documents (limit to 3 most relevant)
  const urlArray = Array.from(urls).slice(0, 3);
  if (urlArray.length === 0) return [];

  console.log(`[DocumentFetcher] Fetching ${urlArray.length} documents for ${state} - ${policyCategory}`);

  return await fetchDocuments(urlArray);
}

/**
 * Clear cache (for testing/debugging)
 */
export function clearCache() {
  documentCache.flushAll();
  console.log('[DocumentFetcher] Cache cleared');
}

/**
 * Get cache stats
 */
export function getCacheStats() {
  return {
    keys: documentCache.keys().length,
    stats: documentCache.getStats()
  };
}
