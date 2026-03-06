import { useState, useRef, useEffect } from 'react'

function ChatInterface({ messages, onSendQuery, isLoading, columns }) {
    const [input, setInput] = useState('')
    const messagesEndRef = useRef(null)
    const inputRef = useRef(null)

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }

    useEffect(() => {
        scrollToBottom()
    }, [messages])

    const handleSubmit = (e) => {
        e.preventDefault()
        if (!input.trim() || isLoading) return
        onSendQuery(input.trim())
        setInput('')
    }

    const handleSuggestion = (suggestion) => {
        if (isLoading) return
        onSendQuery(suggestion)
    }

    const handleKeyDown = (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault()
            handleSubmit(e)
        }
    }

    // Generate smart suggestions based on columns
    const suggestions = columns.length > 0 ? [
        `Show me a summary of the data`,
        `Bar chart of top ${columns[0]} values`,
        columns.length > 1 ? `Relationship between ${columns[0]} and ${columns[1]}` : null,
        `Distribution of ${columns[columns.length - 1]}`,
        `What are the trends in this data?`,
    ].filter(Boolean).slice(0, 4) : []

    return (
        <>
            <div className="panel-header">
                <div className="panel-title">
                    <span className="icon">💬</span>
                    Chat with your Data
                </div>
            </div>

            <div className="chat-messages panel-body" id="chat-messages">
                {messages.length === 0 && (
                    <div className="welcome-message">
                        <div className="icon">🤖</div>
                        <h3>Ask me anything about your data</h3>
                        <p>
                            I'll analyze your dataset using AI agents and create visualizations.
                            Try asking questions in natural language!
                        </p>
                    </div>
                )}

                {messages.map((msg, i) => (
                    <div key={i} className={`chat-message ${msg.role}`}>
                        <div className={`message-avatar ${msg.role === 'user' ? 'human' : 'ai'}`}>
                            {msg.role === 'user' ? '👤' : '🤖'}
                        </div>
                        <div className="message-content">
                            {msg.content}
                        </div>
                    </div>
                ))}

                {isLoading && (
                    <div className="chat-message assistant">
                        <div className="message-avatar ai">🤖</div>
                        <div className="message-content">
                            <div className="typing-indicator">
                                <div className="typing-dot"></div>
                                <div className="typing-dot"></div>
                                <div className="typing-dot"></div>
                            </div>
                        </div>
                    </div>
                )}

                <div ref={messagesEndRef} />
            </div>

            {/* Suggestion chips */}
            {messages.length === 0 && suggestions.length > 0 && (
                <div className="suggestions">
                    {suggestions.map((s, i) => (
                        <button
                            key={i}
                            className="suggestion-chip"
                            onClick={() => handleSuggestion(s)}
                            disabled={isLoading}
                        >
                            {s}
                        </button>
                    ))}
                </div>
            )}

            {/* Input area */}
            <form className="chat-input-area" onSubmit={handleSubmit}>
                <div className="chat-input-wrapper">
                    <textarea
                        ref={inputRef}
                        className="chat-input"
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={handleKeyDown}
                        placeholder="Ask a question about your data..."
                        disabled={isLoading}
                        rows={1}
                        id="chat-input"
                    />
                    <button
                        type="submit"
                        className="send-btn"
                        disabled={!input.trim() || isLoading}
                        id="send-btn"
                    >
                        ➤
                    </button>
                </div>
            </form>
        </>
    )
}

export default ChatInterface
