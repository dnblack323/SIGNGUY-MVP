import fullLogo from "@/assets/branding/signguy-ai-logo-full.png";
import markLogo from "@/assets/branding/signguy-ai-logo-mark.png";
import { cn } from "@/lib/utils";

const LOGO_BY_VARIANT = {
  full: fullLogo,
  mark: markLogo,
};

export default function SignGuyLogo({
  variant = "full",
  className,
  imgClassName,
  alt = "SignGuy AI",
  testId,
}) {
  const src = LOGO_BY_VARIANT[variant] || fullLogo;
  return (
    <span
      className={cn("inline-flex items-center justify-center overflow-hidden", className)}
      data-testid={testId}
    >
      <img
        src={src}
        alt={alt}
        className={cn("h-full w-full object-contain", imgClassName)}
        draggable="false"
      />
    </span>
  );
}
