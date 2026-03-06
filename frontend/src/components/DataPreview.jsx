function DataPreview({ data, columns, summary, fileInfo }) {
    if (!data || !data.length) return null

    return (
        <div className="panel data-preview">
            <div className="panel-header">
                <div className="panel-title">
                    <span className="icon">📋</span>
                    {fileInfo?.name || 'Data Preview'}
                </div>
                <div className="data-stats">
                    <div className="stat-item">
                        Rows: <span className="stat-value">{summary?.shape?.rows?.toLocaleString()}</span>
                    </div>
                    <div className="stat-item">
                        Columns: <span className="stat-value">{summary?.shape?.columns}</span>
                    </div>
                    <div className="stat-item">
                        Types: <span className="stat-value">
                            {summary?.columns
                                ?.map(c => c.category)
                                .filter((v, i, a) => a.indexOf(v) === i)
                                .join(', ')}
                        </span>
                    </div>
                </div>
            </div>

            <div className="data-table-wrapper">
                <table className="data-table" id="data-table">
                    <thead>
                        <tr>
                            <th style={{ width: '40px', color: 'var(--text-muted)' }}>#</th>
                            {columns.map((col) => (
                                <th key={col}>{col}</th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        {data.map((row, i) => (
                            <tr key={i}>
                                <td style={{ color: 'var(--text-muted)', fontSize: '11px' }}>{i + 1}</td>
                                {columns.map((col) => (
                                    <td key={col} title={String(row[col] ?? '')}>
                                        {row[col] === null || row[col] === undefined ? (
                                            <span style={{ color: 'var(--text-muted)', fontStyle: 'italic' }}>null</span>
                                        ) : (
                                            String(row[col])
                                        )}
                                    </td>
                                ))}
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    )
}

export default DataPreview
