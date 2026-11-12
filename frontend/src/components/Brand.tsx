export function Brand() {
  return (
    <a href="#home" aria-label="FairMade home" className="brand">
      <svg viewBox="0 0 38 44" fill="none" aria-hidden="true">
        <g
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M19 40V13M19 29C7 30 4 23 4 16C14 16 19 21 19 29ZM19 23C31 24 34 17 34 10C24 10 19 15 19 23ZM19 15C11 12 12 5 19 2C26 5 27 12 19 15ZM10 40H28" />
        </g>
      </svg>
      <span>
        FairMade<span className="brand-dot">.</span>
      </span>
    </a>
  )
}
