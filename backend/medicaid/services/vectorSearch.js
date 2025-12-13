import fs from 'fs';
import path from 'path';
import { pipeline } from '@xenova/transformers';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

/**
 * Vector Search Service for RAG
 * Loads embeddings and performs semantic search
 */
class VectorSearch {
  constructor() {
    this.embeddings = {}; // Will store: { state: { chunks: [], embedder: null } }
    this.initialized = false;
  }

  /**
   * Load embeddings for a specific state
   */
  async loadStateEmbeddings(state) {
    const stateLower = state.toLowerCase();

    if (this.embeddings[stateLower]) {
      return; // Already loaded
    }

    const embeddingsPath = path.join(__dirname, '../data/embeddings', `${stateLower}.json`);

    if (!fs.existsSync(embeddingsPath)) {
      console.log(`⚠️  No embeddings found for ${state} at ${embeddingsPath}`);
      return null;
    }

    console.log(`📦 Loading embeddings for ${state}...`);
    const data = JSON.parse(fs.readFileSync(embeddingsPath, 'utf8'));

    // Initialize embedder if not already done
    if (!this.embeddings.embedder) {
      console.log('🔄 Loading embedding model...');
      this.embeddings.embedder = await pipeline('feature-extraction', 'Xenova/all-MiniLM-L6-v2');
      console.log('✓ Model loaded');
    }

    this.embeddings[stateLower] = {
      chunks: data,
      count: data.length
    };

    console.log(`✓ Loaded ${data.length} embeddings for ${state}\n`);
    return data.length;
  }

  /**
   * Load embeddings for all available states
   */
  async initialize() {
    if (this.initialized) return;

    console.log('🚀 Initializing Vector Search...\n');

    const embeddingsDir = path.join(__dirname, '../data/embeddings');

    // Create directory if it doesn't exist
    if (!fs.existsSync(embeddingsDir)) {
      fs.mkdirSync(embeddingsDir, { recursive: true});
      console.log('⚠️  No embeddings found. Run processing scripts first.\n');
      this.initialized = true;
      return;
    }

    // Load all available state embeddings
    const files = fs.readdirSync(embeddingsDir).filter(f => f.endsWith('.json'));

    if (files.length === 0) {
      console.log('⚠️  No embeddings found. Run processing scripts first.\n');
      this.initialized = true;
      return;
    }

    // Initialize embedder once
    console.log('🔄 Loading embedding model...');
    this.embeddings.embedder = await pipeline('feature-extraction', 'Xenova/all-MiniLM-L6-v2');
    console.log('✓ Model loaded\n');

    // Load each state's embeddings
    for (const file of files) {
      const state = path.basename(file, '.json');
      const data = JSON.parse(fs.readFileSync(path.join(embeddingsDir, file), 'utf8'));

      this.embeddings[state] = {
        chunks: data,
        count: data.length
      };

      console.log(`✓ Loaded ${data.length} embeddings for ${state}`);
    }

    console.log(`\n✅ Vector Search initialized with ${files.length} states\n`);
    this.initialized = true;
  }

  /**
   * Calculate cosine similarity between two vectors
   */
  cosineSimilarity(a, b) {
    if (a.length !== b.length) {
      throw new Error('Vectors must have same length');
    }

    let dotProduct = 0;
    let normA = 0;
    let normB = 0;

    for (let i = 0; i < a.length; i++) {
      dotProduct += a[i] * b[i];
      normA += a[i] * a[i];
      normB += b[i] * b[i];
    }

    return dotProduct / (Math.sqrt(normA) * Math.sqrt(normB));
  }

  /**
   * Generate embedding for a query
   */
  async embedQuery(query) {
    if (!this.embeddings.embedder) {
      throw new Error('Embedding model not initialized');
    }

    const output = await this.embeddings.embedder(query, { pooling: 'mean', normalize: true });
    return Array.from(output.data);
  }

  /**
   * Search for most relevant documents
   * @param {string} state - State abbreviation (e.g., 'idaho')
   * @param {string} query - User's question
   * @param {number} topK - Number of results to return
   * @returns {Array} Top K most similar documents with scores
   */
  async search(state, query, topK = 5) {
    const stateLower = state.toLowerCase();

    // Ensure state embeddings are loaded
    if (!this.embeddings[stateLower]) {
      await this.loadStateEmbeddings(stateLower);
    }

    if (!this.embeddings[stateLower]) {
      throw new Error(`No embeddings available for ${state}`);
    }

    // Generate query embedding
    const queryEmbedding = await this.embedQuery(query);

    // Calculate similarities
    const results = [];
    for (const doc of this.embeddings[stateLower].chunks) {
      const similarity = this.cosineSimilarity(queryEmbedding, doc.embedding);

      results.push({
        ...doc,
        similarity: similarity,
        // Remove embedding from result to reduce size
        embedding: undefined
      });
    }

    // Sort by similarity and return top K
    results.sort((a, b) => b.similarity - a.similarity);

    return results.slice(0, topK);
  }

  /**
   * Format search results into context string for Claude
   */
  formatContext(searchResults) {
    return searchResults.map((result, index) => {
      const { text, metadata, similarity } = result;
      return `
[Document ${index + 1}]
Source: ${metadata.source}
Type: ${metadata.doc_type}
Relevance: ${(similarity * 100).toFixed(1)}%

${text}

---`;
    }).join('\n\n');
  }

  /**
   * Get available states
   */
  getAvailableStates() {
    return Object.keys(this.embeddings).filter(key => key !== 'embedder');
  }

  /**
   * Get stats for a state
   */
  getStateStats(state) {
    const stateLower = state.toLowerCase();
    if (!this.embeddings[stateLower]) {
      return null;
    }

    const chunks = this.embeddings[stateLower].chunks;
    const docTypes = {};

    chunks.forEach(chunk => {
      const type = chunk.metadata.doc_type;
      docTypes[type] = (docTypes[type] || 0) + 1;
    });

    return {
      state: state,
      totalChunks: chunks.length,
      documentTypes: docTypes,
      sources: [...new Set(chunks.map(c => c.metadata.source))]
    };
  }
}

// Create singleton instance
const vectorSearch = new VectorSearch();

export default vectorSearch;
