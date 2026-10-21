const paths = {
  spark: 'm12 3 2.6 6.4L21 12l-6.4 2.6L12 21l-2.6-6.4L3 12l6.4-2.6L12 3Z',
  check: 'm5 12 4 4L19 6',
  arrow: 'M12 19V5m-6 6 6-6 6 6',
  chevron: 'm9 5 7 7-7 7',
  history: 'M3 11a9 9 0 1 1 2.5 7M3 4v7h7m2-4v5l3 2',
  plus: 'M12 5v14M5 12h14',
  image:
    'M5 3h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2Zm-2 14 6-6 4 4 3-3 5 5M8 7h.01',
  compare: 'M12 3v18M8 5H4v14h4m8-14h4v14h-4',
  retry: 'M20 9a8 8 0 1 0 0 6M20 3v6h-6',
  stop: 'M6 6h12v12H6V6Z',
  alert: 'M12 8v5m0 4h.01M10 4 2 18a1 1 0 0 0 1 2h18a1 1 0 0 0 1-2L14 4a2 2 0 0 0-4 0Z',
} as const
export default function ChatIcon({
  name,
  className = '',
}: {
  name: keyof typeof paths
  className?: string
}) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className={`chat-icon ${className}`}
    >
      <path d={paths[name]} />
    </svg>
  )
}
