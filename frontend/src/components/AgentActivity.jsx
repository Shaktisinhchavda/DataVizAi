function AgentActivity({ steps }) {
    if (!steps || steps.length === 0) return null

    return (
        <div style={{ borderTop: '1px solid var(--border-color)' }}>
            <div className="panel-header" style={{ padding: '10px 20px' }}>
                <div className="panel-title" style={{ fontSize: '11px' }}>
                    <span className="icon">🤖</span>
                    Agent Activity
                </div>
            </div>

            <div className="agent-activity">
                {steps.map((step, i) => (
                    <div className="agent-step" key={i}>
                        <div className={`agent-icon ${step.agent.toLowerCase().includes('profiler') ? 'profiler' :
                            step.agent.toLowerCase().includes('analyst') ? 'analyst' : 'visualizer'}`}>
                            {step.agent.toLowerCase().includes('profiler') ? '🔍' :
                                step.agent.toLowerCase().includes('analyst') ? '📊' : '🎨'}
                        </div>
                        <div className="agent-info">
                            <div className="agent-name">{step.agent}</div>
                            <div className="agent-status">{step.status}</div>
                        </div>
                        {step.active && <div className="agent-spinner"></div>}
                    </div>
                ))}
            </div>
        </div>
    )
}

export default AgentActivity
