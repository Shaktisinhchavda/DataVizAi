import { useState, useRef, useCallback } from 'react'

function FileUpload({ onUpload, isUploading }) {
    const [isDragging, setIsDragging] = useState(false)
    const inputRef = useRef(null)

    const validateFile = (file) => {
        const validTypes = [
            'text/csv',
            'application/vnd.ms-excel',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        ]
        const validExtensions = ['.csv', '.xlsx', '.xls']
        const ext = '.' + file.name.split('.').pop().toLowerCase()
        return validTypes.includes(file.type) || validExtensions.includes(ext)
    }

    const handleFile = useCallback((file) => {
        if (validateFile(file)) {
            onUpload(file)
        } else {
            alert('Please upload a CSV or Excel file (.csv, .xlsx, .xls)')
        }
    }, [onUpload])

    const handleDragOver = (e) => {
        e.preventDefault()
        setIsDragging(true)
    }

    const handleDragLeave = (e) => {
        e.preventDefault()
        setIsDragging(false)
    }

    const handleDrop = (e) => {
        e.preventDefault()
        setIsDragging(false)
        const file = e.dataTransfer.files[0]
        if (file) handleFile(file)
    }

    return (
        <div className="upload-container">
            <div className="upload-hero">
                <h1>Your Data,<br />Visualized by AI</h1>
                <p>
                    Upload your CSV or Excel file and ask questions in natural language.
                    Our AI agents will analyze your data and create beautiful visualizations.
                </p>
            </div>

            <div
                className={`upload-zone glass-card ${isDragging ? 'drag-over' : ''}`}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                onClick={() => inputRef.current?.click()}
                id="upload-zone"
            >
                <span className="upload-icon">
                    {isUploading ? '⏳' : '📊'}
                </span>
                <div className="upload-text">
                    {isUploading ? 'Processing your file...' : 'Drop your file here or click to browse'}
                </div>
                <div className="upload-subtext">
                    Supports CSV, Excel (.xlsx, .xls)
                </div>
                <div className="upload-formats">
                    <span className="format-badge">CSV</span>
                    <span className="format-badge">XLSX</span>
                    <span className="format-badge">XLS</span>
                </div>

                {isUploading && (
                    <div className="upload-progress">
                        <div className="progress-bar">
                            <div className="progress-fill" style={{ width: '80%' }}></div>
                        </div>
                        <div className="progress-text">Analyzing data structure...</div>
                    </div>
                )}

                <input
                    ref={inputRef}
                    type="file"
                    accept=".csv,.xlsx,.xls"
                    style={{ display: 'none' }}
                    onChange={(e) => {
                        const file = e.target.files[0]
                        if (file) handleFile(file)
                    }}
                    id="file-input"
                />
            </div>
        </div>
    )
}

export default FileUpload
