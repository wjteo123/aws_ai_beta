import React, { useState, useEffect, useRef } from 'react';
import { Send, Bot, User, FileText, Search, Shield, Edit, Scale, MessageSquare, History, Brain, Upload, Database, BarChart3, Trash2, RefreshCw, File, FolderOpen, X, Cloud, CheckCircle, AlertCircle } from 'lucide-react';

const LegalMultiAgentSystem = () => {
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  const [selectedAgent, setSelectedAgent] = useState('team');
  const [isConnected, setIsConnected] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [sessionId, setSessionId] = useState(() => `session-${Date.now()}`);
  const [showHistory, setShowHistory] = useState(false);
  const [sessionHistory, setSessionHistory] = useState([]);
  const [userMemories, setUserMemories] = useState([]);
  
  // Knowledge Base States
  const [showKnowledgePanel, setShowKnowledgePanel] = useState(false);
  const [knowledgeDocuments, setKnowledgeDocuments] = useState([]);
  const [knowledgeStats, setKnowledgeStats] = useState(null);
  const [uploadFile, setUploadFile] = useState(null);
  const [uploadDocType, setUploadDocType] = useState('pdf');
  const [uploadCategory, setUploadCategory] = useState('general');
  const [isUploading, setIsUploading] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [isSearching, setIsSearching] = useState(false);
  const [isReindexing, setIsReindexing] = useState(false);
  
  // AWS Services Status
  const [awsStatus, setAwsStatus] = useState(null);
  const [showAwsStatus, setShowAwsStatus] = useState(false);
  
  const wsRef = useRef(null);
  const messagesEndRef = useRef(null);
  const fileInputRef = useRef(null);
  
  // Agent configurations
  const agents = {
    team: { name: 'Legal Team', icon: Scale, color: 'bg-purple-500', description: 'Complete collaborative legal assistance powered by AWS Bedrock' },
    researcher: { name: 'Legal Researcher', icon: Search, color: 'bg-blue-500', description: 'Legal research with AWS OpenSearch vector database' },
    contract_analyzer: { name: 'Contract Analyzer', icon: FileText, color: 'bg-green-500', description: 'Contract analysis with Bedrock AI and knowledge base' },
    compliance_advisor: { name: 'Compliance Advisor', icon: Shield, color: 'bg-orange-500', description: 'Regulatory compliance using AWS DocumentDB records' },
    document_drafter: { name: 'Document Drafter', icon: Edit, color: 'bg-red-500', description: 'Legal document drafting with Bedrock language models' },
    legal_advisor: { name: 'Legal Advisor', icon: Bot, color: 'bg-indigo-500', description: 'General legal consultation with multi-region AWS integration' }
  };

  // WebSocket connection
  useEffect(() => {
    const connectWebSocket = () => {
      const ws = new WebSocket(`ws://localhost:8000/ws/${sessionId}`);
      
      ws.onopen = () => {
        setIsConnected(true);
        console.log('Connected to WebSocket with AWS-powered backend');
      };
      
      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        
        if (data.done) {
          setIsLoading(false);
          return;
        }
        
        if (data.error) {
          setMessages(prev => [...prev, {
            id: Date.now(),
            content: `Error: ${data.error}`,
            isBot: true,
            agent: 'System',
            timestamp: new Date().toISOString(),
            isError: true
          }]);
          setIsLoading(false);
          return;
        }
        
        if (data.content) {
          setMessages(prev => {
            const lastMessage = prev[prev.length - 1];
            if (lastMessage && lastMessage.isBot && lastMessage.isStreaming) {
              return prev.map((msg, index) => 
                index === prev.length - 1 
                  ? { ...msg, content: msg.content + data.content }
                  : msg
              );
            } else {
              return [...prev, {
                id: Date.now(),
                content: data.content,
                isBot: true,
                agent: data.agent || 'Legal Assistant',
                timestamp: data.timestamp || new Date().toISOString(),
                isStreaming: true,
                awsPowered: data.aws_powered || false
              }];
            }
          });
        }
      };
      
      ws.onclose = () => {
        setIsConnected(false);
        console.log('WebSocket disconnected');
      };
      
      ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        setIsConnected(false);
      };
      
      wsRef.current = ws;
    };

    connectWebSocket();
    
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [sessionId]);

  // Auto scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Load data on mount
  useEffect(() => {
    loadKnowledgeDocuments();
    loadKnowledgeStats();
    loadAwsStatus();
  }, []);

  const sendMessage = async () => {
    if (!inputMessage.trim() || !isConnected || isLoading) return;
    
    const userMessage = {
      id: Date.now(),
      content: inputMessage,
      isBot: false,
      timestamp: new Date().toISOString()
    };
    
    setMessages(prev => [...prev, userMessage]);
    setIsLoading(true);
    
    // Send message via WebSocket
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        message: inputMessage,
        agent_type: selectedAgent,
        session_id: sessionId,
        user_id: 'user-1' // In real app, get from auth
      }));
    }
    
    setInputMessage('');
  };

  const loadSessionHistory = async () => {
    try {
      const response = await fetch(`http://localhost:8000/sessions/${sessionId}/history`);
      const data = await response.json();
      setSessionHistory(data.messages || []);
      setShowHistory(true);
    } catch (error) {
      console.error('Error loading session history from DocumentDB:', error);
    }
  };

  const loadUserMemories = async () => {
    try {
      const userId = 'user-1'; // In real app, get from auth
      const response = await fetch(`http://localhost:8000/users/${userId}/memories`);
      const data = await response.json();
      setUserMemories(data.memories || []);
    } catch (error) {
      console.error('Error loading user memories from DocumentDB:', error);
    }
  };

  // Knowledge Base Functions
  const loadKnowledgeDocuments = async () => {
    try {
      const response = await fetch('http://localhost:8000/knowledge/documents');
      const data = await response.json();
      setKnowledgeDocuments(data.documents || []);
    } catch (error) {
      console.error('Error loading documents from OpenSearch:', error);
    }
  };

  const loadKnowledgeStats = async () => {
    try {
      const response = await fetch('http://localhost:8000/knowledge/stats');
      const data = await response.json();
      setKnowledgeStats(data);
    } catch (error) {
      console.error('Error loading knowledge stats:', error);
    }
  };

  const loadAwsStatus = async () => {
    try {
      const response = await fetch('http://localhost:8000/aws/status');
      const data = await response.json();
      setAwsStatus(data);
    } catch (error) {
      console.error('Error loading AWS status:', error);
    }
  };

  const handleFileUpload = async () => {
    if (!uploadFile) return;
    
    setIsUploading(true);
    try {
      const formData = new FormData();
      formData.append('file', uploadFile);
      formData.append('document_type', uploadDocType);
      formData.append('category', uploadCategory);
      
      const response = await fetch('http://localhost:8000/knowledge/upload', {
        method: 'POST',
        body: formData
      });
      
      if (!response.ok) {
        throw new Error('Upload failed');
      }
      
      const result = await response.json();
      console.log('Upload successful with AWS Bedrock embeddings:', result);
      
      // Show success message
      setMessages(prev => [...prev, {
        id: Date.now(),
        content: `✅ Document "${uploadFile.name}" uploaded successfully!\n• Processing: ${result.chunks_created} chunks created\n• Vector embeddings: AWS Bedrock Titan Text Embeddings V2\n• Storage: Amazon OpenSearch Service + DocumentDB\n• Document ID: ${result.document_id}`,
        isBot: true,
        agent: 'Knowledge System',
        timestamp: new Date().toISOString()
      }]);
      
      // Refresh documents and stats
      await loadKnowledgeDocuments();
      await loadKnowledgeStats();
      
      // Reset form
      setUploadFile(null);
      setUploadDocType('pdf');
      setUploadCategory('general');
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
      
    } catch (error) {
      console.error('Error uploading file:', error);
      setMessages(prev => [...prev, {
        id: Date.now(),
        content: `❌ Upload failed: ${error.message}`,
        isBot: true,
        agent: 'Knowledge System',
        timestamp: new Date().toISOString(),
        isError: true
      }]);
    } finally {
      setIsUploading(false);
    }
  };

  const deleteDocument = async (documentId) => {
    if (!confirm('Are you sure you want to delete this document from the AWS knowledge base?')) return;
    
    try {
      const response = await fetch(`http://localhost:8000/knowledge/documents/${documentId}`, {
        method: 'DELETE'
      });
      
      if (!response.ok) {
        throw new Error('Delete failed');
      }
      
      const result = await response.json();
      
      // Show success message
      setMessages(prev => [...prev, {
        id: Date.now(),
        content: `🗑️ Document deleted successfully!\n• Chunks removed: ${result.chunks_deleted}\n• Updated services: OpenSearch + DocumentDB`,
        isBot: true,
        agent: 'Knowledge System',
        timestamp: new Date().toISOString()
      }]);
      
      // Refresh documents and stats
      await loadKnowledgeDocuments();
      await loadKnowledgeStats();
      
    } catch (error) {
      console.error('Error deleting document:', error);
    }
  };

  const searchKnowledge = async () => {
    if (!searchQuery.trim()) return;
    
    setIsSearching(true);
    try {
      const response = await fetch(`http://localhost:8000/knowledge/search?query=${encodeURIComponent(searchQuery)}&limit=10&similarity_threshold=0.7`);
      const data = await response.json();
      setSearchResults(data.results || []);
      
      // Show search results in chat
      const resultsSummary = data.results.length > 0 
        ? `🔍 Found ${data.results.length} relevant documents:\n${data.results.slice(0,3).map((r, i) => `${i+1}. ${r.file_name} (similarity: ${(r.similarity_score || 0).toFixed(3)})`).join('\n')}${data.results.length > 3 ? `\n... and ${data.results.length - 3} more` : ''}\n\n📊 Search powered by: ${data.search_info?.embedding_model}\n🔧 Vector database: ${data.search_info?.vector_database}`
        : `❌ No documents found matching "${searchQuery}"\nTry different keywords or check if documents are uploaded.`;
      
      setMessages(prev => [...prev, {
        id: Date.now(),
        content: resultsSummary,
        isBot: true,
        agent: 'Knowledge Search',
        timestamp: new Date().toISOString()
      }]);
      
    } catch (error) {
      console.error('Error searching knowledge:', error);
    } finally {
      setIsSearching(false);
    }
  };

  const reindexKnowledge = async () => {
    if (!confirm('This will reindex the entire knowledge base with fresh AWS Bedrock embeddings. Continue?')) return;
    
    setIsReindexing(true);
    try {
      setMessages(prev => [...prev, {
        id: Date.now(),
        content: `🔄 Starting knowledge base reindexing...\nThis may take a few minutes for large collections.`,
        isBot: true,
        agent: 'Knowledge System',
        timestamp: new Date().toISOString()
      }]);

      const response = await fetch('http://localhost:8000/knowledge/reindex', {
        method: 'POST'
      });
      
      if (!response.ok) {
        throw new Error('Reindex failed');
      }
      
      const result = await response.json();
      console.log('Reindex successful:', result);
      
      setMessages(prev => [...prev, {
        id: Date.now(),
        content: `✅ Knowledge base reindexed successfully!\n• Documents processed: ${result.documents_processed}\n• Fresh chunks created: ${result.chunks_created}\n• Embedding model: ${result.embedding_model}\n• Services updated: ${result.services_updated.join(', ')}`,
        isBot: true,
        agent: 'Knowledge System',
        timestamp: new Date().toISOString()
      }]);
      
      // Refresh stats
      await loadKnowledgeStats();
      await loadKnowledgeDocuments();
      
    } catch (error) {
      console.error('Error reindexing knowledge:', error);
      setMessages(prev => [...prev, {
        id: Date.now(),
        content: `❌ Reindexing failed: ${error.message}`,
        isBot: true,
        agent: 'Knowledge System',
        timestamp: new Date().toISOString(),
        isError: true
      }]);
    } finally {
      setIsReindexing(false);
    }
  };

  const createNewSession = () => {
    const newSessionId = `session-${Date.now()}`;
    setSessionId(newSessionId);
    setMessages([]);
    setSearchResults([]);
    if (wsRef.current) {
      wsRef.current.close();
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const AgentIcon = agents[selectedAgent]?.icon || Bot;

  const getStatusIcon = (status) => {
    switch(status) {
      case 'connected': 
      case 'healthy': 
        return <CheckCircle size={16} className="text-green-400" />;
      case 'error':
      case 'degraded':
        return <AlertCircle size={16} className="text-red-400" />;
      default:
        return <AlertCircle size={16} className="text-yellow-400" />;
    }
  };

  return (
    <div className="flex h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900">
      {/* Sidebar */}
      <div className="w-80 bg-slate-800/50 backdrop-blur-sm border-r border-slate-700 p-6 overflow-y-auto">
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-white mb-2 flex items-center">
            <Scale className="mr-3 text-purple-400" />
            Legal AI System
          </h1>
          <p className="text-slate-400 text-sm">Multi-Agent Legal Intelligence</p>
          <div className="flex items-center mt-2 text-xs text-slate-500">
            <Cloud size={12} className="mr-1" />
            Powered by AWS Multi-Region
          </div>
        </div>

        {/* AWS Status */}
        <div className="mb-6">
          <button
            onClick={() => setShowAwsStatus(!showAwsStatus)}
            className="w-full flex items-center justify-between p-3 bg-slate-700/30 rounded-lg hover:bg-slate-700/50 transition-colors"
          >
            <div className="flex items-center">
              <Cloud size={16} className="mr-2 text-blue-400" />
              <span className="text-white font-medium text-sm">AWS Services</span>
            </div>
            <div className="flex space-x-1">
              {awsStatus && (
                <>
                  {getStatusIcon(awsStatus.bedrock)}
                  {getStatusIcon(awsStatus.opensearch)}
                  {getStatusIcon(awsStatus.documentdb)}
                </>
              )}
            </div>
          </button>
          
          {showAwsStatus && awsStatus && (
            <div className="mt-2 p-3 bg-slate-700/20 rounded-lg text-xs">
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-slate-300">Bedrock (us-west-2):</span>
                  <div className="flex items-center">
                    {getStatusIcon(awsStatus.bedrock)}
                    <span className="ml-1 text-slate-400">{awsStatus.llm}</span>
                  </div>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-slate-300">OpenSearch (ap-southeast-5):</span>
                  <div className="flex items-center">
                    {getStatusIcon(awsStatus.opensearch)}
                    <span className="ml-1 text-slate-400">{awsStatus.opensearch_docs || 0} docs</span>
                  </div>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-slate-300">DocumentDB (ap-southeast-1):</span>
                  <div className="flex items-center">
                    {getStatusIcon(awsStatus.documentdb)}
                    <span className="ml-1 text-slate-400">{awsStatus.documentdb_collections?.length || 0} collections</span>
                  </div>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-slate-300">Embeddings:</span>
                  <span className="text-slate-400">{awsStatus.embeddings}</span>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Session Controls */}
        <div className="mb-6">
          <div className="flex items-center justify-between mb-3">
            <span className="text-white font-medium">Session Controls</span>
            <div className="flex space-x-2">
              <button
                onClick={loadSessionHistory}
                className="p-2 text-slate-400 hover:text-white hover:bg-slate-700 rounded-lg transition-colors"
                title="Load History (DocumentDB)"
              >
                <History size={16} />
              </button>
              <button
                onClick={loadUserMemories}
                className="p-2 text-slate-400 hover:text-white hover:bg-slate-700 rounded-lg transition-colors"
                title="Load Memories (DocumentDB)"
              >
                <Brain size={16} />
              </button>
              <button
                onClick={() => setShowKnowledgePanel(!showKnowledgePanel)}
                className="p-2 text-slate-400 hover:text-white hover:bg-slate-700 rounded-lg transition-colors"
                title="Knowledge Base (OpenSearch)"
              >
                <Database size={16} />
              </button>
            </div>
          </div>
          <button
            onClick={createNewSession}
            className="w-full px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg transition-colors mb-2"
          >
            New Session
          </button>
          <p className="text-xs text-slate-500">Session: {sessionId.split('-')[1]}</p>
        </div>

        {/* Knowledge Base Stats */}
        {knowledgeStats && (
          <div className="mb-6 p-3 bg-slate-700/30 rounded-lg">
            <div className="flex items-center mb-2">
              <Database size={16} className="mr-2 text-blue-400" />
              <span className="text-white font-medium text-sm">Knowledge Base</span>
            </div>
            <div className="text-xs text-slate-400 space-y-1">
              <div>Documents: {knowledgeStats.total_documents}</div>
              <div>Chunks: {knowledgeStats.total_chunks}</div>
              <div>OpenSearch Docs: {knowledgeStats.opensearch_docs}</div>
              {knowledgeStats.aws_services && (
                <div className="mt-2 pt-2 border-t border-slate-600">
                  <div className="text-slate-500 text-xs">
                    Vector DB: {knowledgeStats.aws_services.vector_database}
                  </div>
                  <div className="text-slate-500 text-xs">
                    Doc DB: {knowledgeStats.aws_services.document_database}
                  </div>
                  <div className="text-slate-500 text-xs">
                    Embeddings: {knowledgeStats.aws_services.embedding_service}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Agent Selection */}
        <div className="mb-6">
          <h3 className="text-white font-medium mb-3">Select Agent</h3>
          <div className="space-y-2">
            {Object.entries(agents).map(([key, agent]) => {
              const Icon = agent.icon;
              return (
                <button
                  key={key}
                  onClick={() => setSelectedAgent(key)}
                  className={`w-full p-3 rounded-lg transition-all text-left ${
                    selectedAgent === key 
                      ? `${agent.color} text-white shadow-lg` 
                      : 'bg-slate-700/50 text-slate-300 hover:bg-slate-700'
                  }`}
                >
                  <div className="flex items-center">
                    <Icon size={20} className="mr-3" />
                    <div>
                      <div className="font-medium">{agent.name}</div>
                      <div className="text-xs opacity-75">{agent.description}</div>
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        {/* Connection Status */}
        <div className="mb-6">
          <div className={`flex items-center p-3 rounded-lg ${
            isConnected ? 'bg-green-900/30 text-green-400' : 'bg-red-900/30 text-red-400'
          }`}>
            <div className={`w-3 h-3 rounded-full mr-3 ${
              isConnected ? 'bg-green-400' : 'bg-red-400'
            }`} />
            {isConnected ? 'Connected to AWS Backend' : 'Disconnected'}
          </div>
        </div>
      </div>

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col">
        {/* Header */}
        <div className="bg-slate-800/50 backdrop-blur-sm border-b border-slate-700 p-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center">
              <AgentIcon className={`mr-3 p-2 rounded-lg ${agents[selectedAgent]?.color} text-white`} size={40} />
              <div>
                <h2 className="text-xl font-bold text-white">{agents[selectedAgent]?.name}</h2>
                <p className="text-slate-400 text-sm">{agents[selectedAgent]?.description}</p>
              </div>
            </div>
            <div className="flex items-center space-x-4">
              {isLoading && (
                <div className="flex items-center text-purple-400">
                  <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-purple-400 mr-2"></div>
                  Processing with AWS...
                </div>
              )}
              <div className="text-xs text-slate-500 flex items-center">
                <Cloud size={12} className="mr-1" />
                Multi-Region AWS
              </div>
            </div>
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {messages.length === 0 && (
            <div className="text-center text-slate-400 py-12">
              <MessageSquare size={48} className="mx-auto mb-4 opacity-50" />
              <p className="text-lg mb-2">Welcome to the Legal AI System</p>
              <p className="text-sm mb-4">Powered by AWS Bedrock, OpenSearch, and DocumentDB</p>
              <div className="text-xs text-slate-500 space-y-1">
                <div>🧠 LLM: AWS Bedrock (us-west-2)</div>
                <div>🔍 Vector Search: OpenSearch (ap-southeast-5)</div>
                <div>💾 Session Storage: DocumentDB (ap-southeast-1)</div>
              </div>
            </div>
          )}
          
          {messages.map((message) => (
            <div
              key={message.id}
              className={`flex ${message.isBot ? 'justify-start' : 'justify-end'}`}
            >
              <div
                className={`max-w-3xl p-4 rounded-lg ${
                  message.isBot
                    ? message.isError 
                      ? 'bg-red-900/30 text-red-200'
                      : 'bg-slate-700/50 text-white'
                    : 'bg-purple-600 text-white'
                } shadow-lg`}
              >
                {message.isBot && (
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center">
                      <Bot size={16} className="mr-2" />
                      <span className="text-xs font-medium opacity-75">
                        {message.agent}
                      </span>
                    </div>
                    {message.awsPowered && (
                      <div className="flex items-center text-xs text-blue-300">
                        <Cloud size={12} className="mr-1" />
                        AWS
                      </div>
                    )}
                  </div>
                )}
                <div className="prose prose-invert max-w-none">
                  {message.content.split('\n').map((line, i) => (
                    <p key={i} className="mb-2 last:mb-0">{line}</p>
                  ))}
                </div>
                <div className="text-xs opacity-50 mt-2">
                  {new Date(message.timestamp).toLocaleTimeString()}
                </div>
              </div>
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <div className="bg-slate-800/50 backdrop-blur-sm border-t border-slate-700 p-6">
          <div className="flex space-x-4">
            <textarea
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="Ask your legal question... (powered by AWS Bedrock)"
              className="flex-1 p-4 bg-slate-700 text-white rounded-lg border border-slate-600 focus:border-purple-500 focus:outline-none resize-none"
              rows="3"
              disabled={!isConnected || isLoading}
            />
            <button
              onClick={sendMessage}
              disabled={!isConnected || isLoading || !inputMessage.trim()}
              className="px-6 py-4 bg-purple-600 hover:bg-purple-700 disabled:bg-slate-600 text-white rounded-lg transition-colors flex items-center justify-center"
            >
              <Send size={20} />
            </button>
          </div>
        </div>
      </div>

      {/* Knowledge Base Panel */}
      {showKnowledgePanel && (
        <div className="w-96 bg-slate-800/50 backdrop-blur-sm border-l border-slate-700 p-6 overflow-y-auto">
          <div className="flex items-center justify-between mb-6">
            <h3 className="text-lg font-bold text-white flex items-center">
              <Database className="mr-2" size={20} />
              Knowledge Base
            </h3>
            <button
              onClick={() => setShowKnowledgePanel(false)}
              className="text-slate-400 hover:text-white"
            >
              <X size={20} />
            </button>
          </div>

          {/* AWS Integration Info */}
          <div className="mb-6 p-3 bg-blue-900/20 border border-blue-700/30 rounded-lg">
            <div className="flex items-center mb-2">
              <Cloud size={14} className="mr-2 text-blue-400" />
              <span className="text-blue-300 font-medium text-sm">AWS Multi-Region Integration</span>
            </div>
            <div className="text-xs text-blue-200 space-y-1">
              <div>• Embeddings: Bedrock Titan (us-west-2)</div>
              <div>• Vector Search: OpenSearch (ap-southeast-5)</div>
              <div>• Metadata: DocumentDB (ap-southeast-1)</div>
            </div>
          </div>

          {/* Upload Section */}
          <div className="mb-6 p-4 bg-slate-700/30 rounded-lg">
            <h4 className="text-white font-medium mb-3 flex items-center">
              <Upload size={16} className="mr-2" />
              Upload Document
            </h4>
            
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.docx,.doc,.txt,.md"
              onChange={(e) => setUploadFile(e.target.files[0])}
              className="w-full mb-3 text-sm text-slate-400 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-purple-600 file:text-white hover:file:bg-purple-700"
            />
            
            <div className="grid grid-cols-2 gap-2 mb-3">
              <select
                value={uploadDocType}
                onChange={(e) => setUploadDocType(e.target.value)}
                className="p-2 bg-slate-600 text-white rounded text-sm"
              >
                <option value="pdf">PDF</option>
                <option value="docx">Word Document</option>
                <option value="text">Text File</option>
              </select>
              
              <input
                type="text"
                value={uploadCategory}
                onChange={(e) => setUploadCategory(e.target.value)}
                placeholder="Category"
                className="p-2 bg-slate-600 text-white rounded text-sm"
              />
            </div>
            
            <button
              onClick={handleFileUpload}
              disabled={!uploadFile || isUploading}
              className="w-full px-4 py-2 bg-green-600 hover:bg-green-700 disabled:bg-slate-600 text-white rounded transition-colors text-sm flex items-center justify-center"
            >
              {isUploading ? (
                <>
                  <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                  Processing with Bedrock...
                </>
              ) : (
                'Upload to AWS'
              )}
            </button>
          </div>

          {/* Search Section */}
          <div className="mb-6 p-4 bg-slate-700/30 rounded-lg">
            <h4 className="text-white font-medium mb-3 flex items-center">
              <Search size={16} className="mr-2" />
              Search Knowledge (OpenSearch)
            </h4>
            
            <div className="flex space-x-2 mb-3">
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search documents..."
                className="flex-1 p-2 bg-slate-600 text-white rounded text-sm"
                onKeyPress={(e) => e.key === 'Enter' && searchKnowledge()}
              />
              <button
                onClick={searchKnowledge}
                disabled={isSearching}
                className="px-3 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-600 text-white rounded text-sm flex items-center"
              >
                {isSearching ? (
                  <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                ) : (
                  <Search size={16} />
                )}
              </button>
            </div>
            
            {searchResults.length > 0 && (
              <div className="space-y-2 max-h-40 overflow-y-auto">
                <div className="text-xs text-slate-400 mb-2">
                  Found {searchResults.length} results (AWS vector similarity)
                </div>
                {searchResults.map((result, index) => (
                  <div key={index} className="p-2 bg-slate-600 rounded text-xs">
                    <div className="text-white font-medium flex items-center justify-between">
                      <span className="truncate">{result.file_name}</span>
                      <span className="text-green-400 ml-2">{(result.similarity_score || 0).toFixed(3)}</span>
                    </div>
                    <div className="text-slate-300 truncate mt-1">{result.content?.substring(0, 100) || 'No preview'}</div>
                    <div className="text-slate-400 mt-1">
                      {result.document_type} • {result.category} • Chunk {result.chunk_index}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Documents List */}
          <div className="mb-6">
            <div className="flex items-center justify-between mb-3">
              <h4 className="text-white font-medium flex items-center">
                <FolderOpen size={16} className="mr-2" />
                Documents ({knowledgeDocuments.length})
              </h4>
              <div className="flex space-x-2">
                <button
                  onClick={loadKnowledgeDocuments}
                  className="p-1 text-slate-400 hover:text-white"
                  title="Refresh from OpenSearch"
                >
                  <RefreshCw size={14} />
                </button>
                <button
                  onClick={reindexKnowledge}
                  disabled={isReindexing}
                  className="p-1 text-slate-400 hover:text-white disabled:text-slate-600"
                  title="Reindex with fresh Bedrock embeddings"
                >
                  {isReindexing ? (
                    <div className="animate-spin rounded-full h-3.5 w-3.5 border-b border-slate-400"></div>
                  ) : (
                    <BarChart3 size={14} />
                  )}
                </button>
              </div>
            </div>
            
            <div className="space-y-2 max-h-60 overflow-y-auto">
              {knowledgeDocuments.length === 0 ? (
                <div className="text-center text-slate-400 py-4">
                  <FileText size={32} className="mx-auto mb-2 opacity-50" />
                  <div className="text-sm">No documents uploaded</div>
                  <div className="text-xs">Upload files to populate AWS knowledge base</div>
                </div>
              ) : (
                knowledgeDocuments.map((doc) => (
                  <div key={doc.document_id} className="p-3 bg-slate-700/30 rounded-lg">
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="text-white text-sm font-medium truncate">
                          {doc.file_name}
                        </div>
                        <div className="text-slate-400 text-xs">
                          {doc.document_type} • {doc.category} • {doc.chunk_count} chunks
                        </div>
                        <div className="text-slate-500 text-xs">
                          {new Date(doc.created_at).toLocaleDateString()}
                        </div>
                        {doc.total_content_length && (
                          <div className="text-slate-500 text-xs">
                            {Math.round(doc.total_content_length / 1024)}KB
                          </div>
                        )}
                      </div>
                      <button
                        onClick={() => deleteDocument(doc.document_id)}
                        className="p-1 text-red-400 hover:text-red-300 ml-2"
                        title="Delete from AWS knowledge base"
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Stats */}
          {knowledgeStats && (
            <div className="p-4 bg-slate-700/30 rounded-lg">
              <h4 className="text-white font-medium mb-3 flex items-center">
                <BarChart3 size={16} className="mr-2" />
                AWS Knowledge Statistics
              </h4>
              <div className="text-xs text-slate-400 space-y-1">
                <div className="flex justify-between">
                  <span>Total Documents:</span>
                  <span className="text-white">{knowledgeStats.total_documents}</span>
                </div>
                <div className="flex justify-between">
                  <span>Total Chunks:</span>
                  <span className="text-white">{knowledgeStats.total_chunks}</span>
                </div>
                <div className="flex justify-between">
                  <span>OpenSearch Docs:</span>
                  <span className="text-white">{knowledgeStats.opensearch_docs}</span>
                </div>
                {knowledgeStats.opensearch_index && (
                  <div className="flex justify-between">
                    <span>OpenSearch Index:</span>
                    <span className="text-blue-300">{knowledgeStats.opensearch_index}</span>
                  </div>
                )}
              </div>
              
              {knowledgeStats.aws_services && (
                <div className="mt-3 pt-3 border-t border-slate-600">
                  <div className="text-xs text-slate-500 space-y-1">
                    <div>Vector DB: {knowledgeStats.aws_services.vector_database}</div>
                    <div>Document DB: {knowledgeStats.aws_services.document_database}</div>
                    <div>Embeddings: {knowledgeStats.aws_services.embedding_service}</div>
                    <div>LLM: {knowledgeStats.aws_services.llm_service}</div>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* History Modal */}
      {showHistory && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <div className="bg-slate-800 rounded-lg p-6 max-w-2xl w-full max-h-96 overflow-y-auto">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-bold text-white flex items-center">
                <History className="mr-2" size={20} />
                Session History
                <span className="ml-2 text-xs text-slate-400">(DocumentDB)</span>
              </h3>
              <button
                onClick={() => setShowHistory(false)}
                className="text-slate-400 hover:text-white"
              >
                <X size={20} />
              </button>
            </div>
            <div className="space-y-2">
              {sessionHistory.length === 0 ? (
                <div className="text-center text-slate-400 py-4">
                  <MessageSquare size={32} className="mx-auto mb-2 opacity-50" />
                  <div>No session history found</div>
                  <div className="text-xs">Messages will be stored in DocumentDB</div>
                </div>
              ) : (
                sessionHistory.map((msg, index) => (
                  <div key={index} className="p-3 bg-slate-700 rounded text-sm text-white">
                    <div className="flex items-center mb-1">
                      <span className="font-medium capitalize">{msg.role}:</span>
                      {msg.timestamp && (
                        <span className="text-xs text-slate-400 ml-2">
                          {new Date(msg.timestamp).toLocaleString()}
                        </span>
                      )}
                    </div>
                    <div className="text-slate-200">{msg.content}</div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}

      {/* User Memories Modal */}
      {userMemories.length > 0 && (
        <div className="fixed bottom-4 right-4 bg-slate-800 rounded-lg p-4 max-w-sm shadow-lg border border-slate-700">
          <div className="flex items-center justify-between mb-2">
            <h4 className="text-white font-medium flex items-center">
              <Brain size={16} className="mr-2" />
              User Memories
              <span className="ml-2 text-xs text-slate-400">(DocumentDB)</span>
            </h4>
            <button
              onClick={() => setUserMemories([])}
              className="text-slate-400 hover:text-white"
            >
              <X size={16} />
            </button>
          </div>
          <div className="space-y-1 max-h-32 overflow-y-auto">
            {userMemories.map((memory, index) => (
              <div key={index} className="text-xs text-slate-300 p-2 bg-slate-700/50 rounded">
                {memory.memory || memory}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default LegalMultiAgentSystem;