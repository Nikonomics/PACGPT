import express from 'express';
import cors from 'cors';
import dotenv from 'dotenv';
import medicaidRoutes from './routes/medicaid.js';
import vectorSearch from './services/vectorSearch.js';

// Load from .env file in development, or use environment variables in production
dotenv.config({ path: '../../.env' });
dotenv.config(); // Also check local .env for Render deployment

const app = express();
const PORT = process.env.PORT || process.env.MEDICAID_PORT || 3001;

// Middleware
app.use(cors());
app.use(express.json());

// Initialize vector search (async, happens in background)
vectorSearch.initialize().catch(err => {
  console.error('Failed to initialize vector search:', err.message);
  console.log('RAG features will not be available, but chatbot will continue to work');
});

// Routes
app.use('/api/medicaid', medicaidRoutes);

// Health check
app.get('/health', (req, res) => {
  res.json({ status: 'ok', service: 'medicaid-chatbot' });
});

app.listen(PORT, () => {
  console.log(`Medicaid Chatbot backend running on port ${PORT}`);
});
