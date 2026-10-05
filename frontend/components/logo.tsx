/**
 * ProteoLens mark: a lens ring framing a right-handed double helix.
 *
 * Drawn as raw SVG so it stays crisp at any size and renders in server
 * components with zero runtime cost. The two strands cross twice (one full
 * turn); the faint verticals are H-bond-style rungs and the dots are the
 * terminal residues.
 */
export function ProteoLensLogo({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 32 32"
      fill="none"
      className={className}
      aria-hidden="true"
    >
      <defs>
        <linearGradient id="proteolens-grad" x1="4" y1="4" x2="28" y2="28">
          <stop offset="0%" stopColor="#22d3ee" />
          <stop offset="55%" stopColor="#818cf8" />
          <stop offset="100%" stopColor="#c084fc" />
        </linearGradient>
      </defs>

      {/* Lens ring */}
      <circle
        cx="16"
        cy="16"
        r="14.25"
        stroke="url(#proteolens-grad)"
        strokeWidth="1.75"
      />

      {/* H-bond rungs between the strands */}
      <g
        stroke="url(#proteolens-grad)"
        strokeWidth="1.5"
        strokeLinecap="round"
        opacity="0.45"
      >
        <line x1="6.5" y1="10.5" x2="6.5" y2="21.5" />
        <line x1="16" y1="10.5" x2="16" y2="21.5" />
        <line x1="25.5" y1="10.5" x2="25.5" y2="21.5" />
      </g>

      {/* The two helical strands */}
      <g
        stroke="url(#proteolens-grad)"
        strokeWidth="2"
        strokeLinecap="round"
      >
        <path d="M6.5 10.5 C10 10.5 13 21.5 16 21.5 C19 21.5 22 10.5 25.5 10.5" />
        <path d="M6.5 21.5 C10 21.5 13 10.5 16 10.5 C19 10.5 22 21.5 25.5 21.5" />
      </g>

      {/* Terminal residues */}
      <g fill="url(#proteolens-grad)">
        <circle cx="6.5" cy="10.5" r="1.3" />
        <circle cx="6.5" cy="21.5" r="1.3" />
        <circle cx="25.5" cy="10.5" r="1.3" />
        <circle cx="25.5" cy="21.5" r="1.3" />
      </g>
    </svg>
  );
}
