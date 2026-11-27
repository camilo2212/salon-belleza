export function Loading({ label }) {
  return (
    <p className="status" role="status">
      {label}
    </p>
  )
}

export function ErrorBox({ message, onRetry }) {
  return (
    <div className="status status-error" role="alert">
      <p>{message}</p>
      {onRetry && (
        <button type="button" className="btn btn-line" onClick={onRetry}>
          Reintentar
        </button>
      )}
    </div>
  )
}
