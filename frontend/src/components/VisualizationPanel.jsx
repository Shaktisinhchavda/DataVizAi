import { useState, useEffect, useRef } from 'react'

function VisualizationPanel({ chart }) {
    const plotContainerRef = useRef(null)
    const [plotlyLoaded, setPlotlyLoaded] = useState(false)
    const [renderError, setRenderError] = useState(null)

    // Load Plotly from CDN
    useEffect(() => {
        if (window.Plotly) {
            setPlotlyLoaded(true)
            return
        }
        const script = document.createElement('script')
        script.src = 'https://cdn.plot.ly/plotly-2.35.0.min.js'
        script.onload = () => {
            console.log('[DataViz] Plotly loaded')
            setPlotlyLoaded(true)
        }
        script.onerror = () => {
            console.error('[DataViz] Failed to load Plotly CDN')
            setRenderError('Failed to load charting library')
        }
        document.head.appendChild(script)
    }, [])

    // Render chart when data or plotly changes
    useEffect(() => {
        if (!chart || !plotContainerRef.current) return

        console.log('[DataViz] Chart data received:', JSON.stringify(chart).substring(0, 200))

        // If Plotly isn't loaded yet, wait
        if (!plotlyLoaded && !window.Plotly) {
            console.log('[DataViz] Waiting for Plotly to load...')
            return
        }

        const Plotly = window.Plotly
        if (!Plotly) {
            setRenderError('Plotly not available')
            return
        }

        try {
            setRenderError(null)

            let chartData = chart
            // If chart is a string, try to parse it
            if (typeof chart === 'string') {
                try {
                    chartData = JSON.parse(chart)
                } catch (e) {
                    console.error('[DataViz] Failed to parse chart string:', e)
                    setRenderError('Invalid chart data')
                    return
                }
            }

            const data = chartData.data || []
            if (data.length === 0) {
                console.warn('[DataViz] No traces in chart data')
                setRenderError('Chart has no data traces')
                return
            }

            const layout = {
                ...(chartData.layout || {}),
                paper_bgcolor: 'rgba(0,0,0,0)',
                plot_bgcolor: 'rgba(0,0,0,0)',
                font: {
                    family: 'Inter, sans-serif',
                    color: '#9090a8',
                    size: 12,
                },
                margin: { l: 50, r: 30, t: 50, b: 50 },
                xaxis: {
                    ...(chartData.layout?.xaxis || {}),
                    gridcolor: 'rgba(255,255,255,0.05)',
                    linecolor: 'rgba(255,255,255,0.1)',
                    zerolinecolor: 'rgba(255,255,255,0.1)',
                },
                yaxis: {
                    ...(chartData.layout?.yaxis || {}),
                    gridcolor: 'rgba(255,255,255,0.05)',
                    linecolor: 'rgba(255,255,255,0.1)',
                    zerolinecolor: 'rgba(255,255,255,0.1)',
                },
                legend: {
                    ...(chartData.layout?.legend || {}),
                    font: { color: '#9090a8' },
                },
                autosize: true,
            }

            const config = {
                responsive: true,
                displayModeBar: true,
                modeBarButtonsToRemove: ['lasso2d', 'select2d'],
                displaylogo: false,
            }

            // Clear previous chart
            Plotly.purge(plotContainerRef.current)

            // Render new chart
            Plotly.newPlot(plotContainerRef.current, data, layout, config)
                .then(() => console.log('[DataViz] Chart rendered successfully'))
                .catch(err => {
                    console.error('[DataViz] Plotly render error:', err)
                    setRenderError('Failed to render chart')
                })
        } catch (err) {
            console.error('[DataViz] Chart render error:', err)
            setRenderError('Failed to render chart: ' + err.message)
        }
    }, [chart, plotlyLoaded])

    return (
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
            <div className="panel-header">
                <div className="panel-title">
                    <span className="icon">📈</span>
                    Visualization
                    {chart && <span style={{ marginLeft: 8, fontSize: 11, color: 'var(--success)' }}>● Chart Ready</span>}
                </div>
            </div>

            <div className="viz-container">
                {renderError ? (
                    <div className="viz-placeholder">
                        <div className="icon">⚠️</div>
                        <p>{renderError}</p>
                    </div>
                ) : chart ? (
                    <div
                        ref={plotContainerRef}
                        id="chart-container"
                        style={{ width: '100%', height: '100%', minHeight: '300px' }}
                    />
                ) : (
                    <div className="viz-placeholder">
                        <div className="icon">📊</div>
                        <p>
                            Ask a question about your data and the AI will generate an interactive visualization here.
                        </p>
                    </div>
                )}
            </div>
        </div>
    )
}

export default VisualizationPanel
