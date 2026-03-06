/** Simplified avatar icon — bald man with glasses, mustache, navy suit.
 *  Based on the project mascot; Catppuccin Mocha palette, transparent bg. */

interface Props {
  size?: number;
  className?: string;
}

export default function AdvisorAvatar({ size = 32, className = '' }: Props) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 64 64"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
    >
      {/* Head (skin tone) */}
      <ellipse cx="32" cy="26" rx="16" ry="18" fill="#e6b88a" />

      {/* Ears */}
      <ellipse cx="15.5" cy="28" rx="3" ry="4" fill="#d4a373" />
      <ellipse cx="48.5" cy="28" rx="3" ry="4" fill="#d4a373" />

      {/* Bald head shine */}
      <ellipse cx="28" cy="14" rx="8" ry="4" fill="#f0d0a0" opacity="0.5" />

      {/* Eyes (white + dark iris) */}
      <ellipse cx="25" cy="25" rx="4" ry="3.2" fill="white" />
      <ellipse cx="39" cy="25" rx="4" ry="3.2" fill="white" />
      <circle cx="25.5" cy="25.5" r="1.8" fill="#1e1e2e" />
      <circle cx="39.5" cy="25.5" r="1.8" fill="#1e1e2e" />

      {/* Glasses (round frames) */}
      <circle cx="25" cy="25" r="5.5" stroke="#45475a" strokeWidth="1.6" fill="none" />
      <circle cx="39" cy="25" r="5.5" stroke="#45475a" strokeWidth="1.6" fill="none" />
      {/* Bridge */}
      <path d="M30.5 24.5 Q32 23 33.5 24.5" stroke="#45475a" strokeWidth="1.4" fill="none" />
      {/* Temples */}
      <line x1="19.5" y1="24" x2="16" y2="23" stroke="#45475a" strokeWidth="1.4" />
      <line x1="44.5" y1="24" x2="48" y2="23" stroke="#45475a" strokeWidth="1.4" />

      {/* Mustache */}
      <path
        d="M24 32 Q28 35 32 33 Q36 35 40 32 Q38 37 32 36 Q26 37 24 32Z"
        fill="#45475a"
      />

      {/* Slight smile below mustache */}
      <path d="M28 36 Q32 38 36 36" stroke="#a0785a" strokeWidth="0.8" fill="none" />

      {/* Suit (navy) — shoulders + collar */}
      <path
        d="M12 58 Q12 46 20 42 L26 40 L32 44 L38 40 L44 42 Q52 46 52 58 Z"
        fill="#313244"
      />

      {/* Shirt / tie area */}
      <path d="M30 40 L32 44 L34 40 L33 52 L31 52 Z" fill="#89b4fa" />

      {/* Collar lines */}
      <line x1="26" y1="40" x2="30" y2="44" stroke="#585b70" strokeWidth="0.8" />
      <line x1="38" y1="40" x2="34" y2="44" stroke="#585b70" strokeWidth="0.8" />
    </svg>
  );
}
