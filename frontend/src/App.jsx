import { useState, useCallback } from 'react'
import FileUpload from './components/FileUpload'
import DataPreview from './components/DataPreview'
import ChatInterface from './components/ChatInterface'
import VisualizationPanel from './components/VisualizationPanel'
import AgentActivity from './components/AgentActivity'
import axios from 'axios'

function App() {
    const [sessionId, setSessionId] = useState(null)
    const [fileInfo, setFileInfo] = useState(null)
    const [dataSummary, setDataSummary] = useState(null)
    const [previewData, setPreviewData] = useState(null)
    const [columns, setColumns] = useState([])
    const [messages, setMessages] = useState([])
    const [currentChart, setCurrentChart] = useState(null)
    const [isLoading, setIsLoading] = useState(false)
    const [isUploading, setIsUploading] = useState(false)
    const [agentSteps, setAgentSteps] = useState([])
    const [error, setError] = useState(null)

    const handleFileUpload = useCallback(async (file) => {
        setIsUploading(true)
        setError(null)

        try {
            const formData = new FormData()
            formData.append('file', file)

            const response = await axios.post('/api/upload', formData, {
                headers: { 'Content-Type': 'multipart/form-data' },
            })

            const data = response.data
            setSessionId(data.session_id)
            setFileInfo({ name: data.filename, session_id: data.session_id })
            setDataSummary(data.summary)
            setPreviewData(data.preview)
            setColumns(data.columns)
            setMessages([])
            setCurrentChart(null)
            setAgentSteps([])
        } catch (err) {
            setError(err.response?.data?.detail || 'Failed to upload file. Please try again.')
        } finally {
            setIsUploading(false)
        }
    }, [])

    const handleQuery = useCallback(async (query) => {
        if (!sessionId) return

        setIsLoading(true)
        setError(null)

        // Add user message immediately
        setMessages(prev => [...prev, { role: 'user', content: query }])

        // Show agent activity — 3-agent hybrid flow
        setAgentSteps([
            { agent: 'Architect', status: 'Profiling schema & planning...', active: true },
        ])

        let timer1, timer2
        try {
            timer1 = setTimeout(() => {
                setAgentSteps([
                    { agent: 'Architect', status: 'Analysis plan ready ✓', active: false },
                    { agent: 'Data Scientist', status: 'Writing & executing code...', active: true },
                ])
            }, 3000)

            timer2 = setTimeout(() => {
                setAgentSteps([
                    { agent: 'Architect', status: 'Analysis plan ready ✓', active: false },
                    { agent: 'Data Scientist', status: 'Code executed ✓', active: false },
                    { agent: 'Insight Analyst', status: 'Synthesizing final findings...', active: true },
                ])
            }, 12000)

            const response = await axios.post('/api/query', {
                session_id: sessionId,
                query: query,
            }, { timeout: 180000 })

            // Clear simulation
            clearTimeout(timer1)
            clearTimeout(timer2)

            const data = response.data
            console.log('[DataViz] Query response:', { analysis: data.analysis?.substring(0, 100), hasChart: !!data.chart })

            // Add assistant message
            setMessages(prev => [...prev, {
                role: 'assistant',
                content: data.analysis || 'Analysis complete.',
                chart: data.chart,
            }])

            if (data.chart) {
                setCurrentChart(data.chart)
            }

            // Finalize — all agents done
            setAgentSteps([
                { agent: 'Architect', status: 'Analysis plan ready ✓', active: false },
                { agent: 'Data Scientist', status: 'Analysis executed ✓', active: false },
                { agent: 'Insight Analyst', status: 'Insights ready ✓', active: false },
            ])

        } catch (err) {
            clearTimeout(timer1)
            clearTimeout(timer2)
            setError(err.response?.data?.detail || 'Failed to process query. Please try again.')
            setMessages(prev => [...prev, {
                role: 'assistant',
                content: '⚠️ Sorry, I encountered an error processing your query. Please try again.',
            }])
            setAgentSteps([])
        } finally {
            setIsLoading(false)
        }
    }, [sessionId])

    return (
        <div className="app-container">
            {/* Navbar */}
            <nav className="navbar">
                <div className="navbar-brand">
                    <div className="navbar-logo">D</div>
                    <div>
                        <div className="navbar-title">DataViz AI</div>
                        <div className="navbar-subtitle">AI-Powered Data Visualization</div>
                    </div>
                </div>
                <div className="navbar-status">
                    <span className={`status-dot ${isLoading ? 'processing' : ''}`}></span>
                    {isLoading ? 'Agents working...' : sessionId ? `Session: ${sessionId}` : 'Ready'}
                </div>
            </nav>

            {/* Error Banner */}
            {error && (
                <div className="error-banner">
                    <span className="icon">⚠️</span>
                    {error}
                </div>
            )}

            {/* Main Content */}
            {!sessionId ? (
                <div className="main-content no-data">
                    <FileUpload onUpload={handleFileUpload} isUploading={isUploading} />
                </div>
            ) : (
                <div className="main-content">
                    {/* Data Preview — spans full width */}
                    <DataPreview
                        data={previewData}
                        columns={columns}
                        summary={dataSummary}
                        fileInfo={fileInfo}
                    />

                    {/* Left: Chat */}
                    <div className="panel chat-panel">
                        <ChatInterface
                            messages={messages}
                            onSendQuery={handleQuery}
                            isLoading={isLoading}
                            columns={columns}
                        />
                    </div>

                    {/* Right: Visualization + Agent Activity */}
                    <div className="panel viz-panel" style={{ display: 'flex', flexDirection: 'column' }}>
                        <VisualizationPanel chart={currentChart} />
                        <AgentActivity steps={agentSteps} />
                    </div>
                </div>
            )}
        </div>
    )
}

export default App
